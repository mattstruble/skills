# Hot Reload Architecture

Hot reload lets you recompile game logic and inject it into a running game without losing state. Iteration time drops from 5–10 seconds (restart) to under 1 second (recompile DLL only).

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  main_hot_reload.odin (EXE host)                        │
│  - Owns the window and OS resources                     │
│  - Monitors game.dll file timestamp each frame          │
│  - Calls game_* procs via function pointers             │
│  - Retrieves Game_Memory pointer from DLL; never frees  │
└────────────────────────┬────────────────────────────────┘
                         │  rawptr (Game_Memory*)
                         ▼
┌─────────────────────────────────────────────────────────┐
│  game.dll (compiled from game.odin)                     │
│  - Exports game_init, game_update, game_memory, etc.    │
│  - Allocates Game_Memory on game_init; owns the pointer │
│  - Recompile and reload without losing state            │
└─────────────────────────────────────────────────────────┘
```

The DLL allocates `Game_Memory` on the first `game_init` call. On reload, the host retrieves the pointer via `game_memory()`, unloads the old DLL, loads the new DLL, and passes the pointer back via `game_hot_reloaded()`. No serialization — the memory layout is preserved in place.

---

## File Organization

```
source/
  game.odin              — all gameplay code (compiled as DLL)
  main_hot_reload.odin   — host: monitors DLL, owns window
  main_release.odin      — release: statically links game code, no DLL
build/
  game.dll               — hot reload target
  game_0.dll             — copy loaded by host (avoids compiler lock)
  game.exe               — release build
```

The release build includes `game.odin` directly — no DLL, no overhead, same code path.

---

## DLL API (game.odin)

All exported procedures form the contract between host and DLL. Never change signatures without updating both sides.

```odin
package game

import rl "vendor:raylib"

Game_Memory :: struct {
    player:   Player,
    enemies:  [dynamic]Enemy,
    camera:   Camera_2D_State,  // custom smoothing struct, not rl.Camera2D
    running:  bool,
    // All game state here — no globals outside this struct
}

// Package-level pointer — set by game_init, restored by game_hot_reloaded
g: ^Game_Memory

@(export)
game_init :: proc() {
    g = new(Game_Memory)
    g.running = true
    // load assets, setup initial state
    rl.InitAudioDevice()
}

@(export)
game_update :: proc() -> bool {
    if rl.IsKeyPressed(.ESCAPE) { g.running = false }
    update_player(&g.player, rl.GetFrameTime())
    rl.BeginDrawing()
    rl.ClearBackground(rl.RAYWHITE)
    render_player(&g.player)
    rl.EndDrawing()
    return g.running
}

@(export)
game_shutdown :: proc() {
    rl.CloseAudioDevice()
    free(g)
}

@(export)
game_memory :: proc() -> rawptr {
    return g
}

@(export)
game_memory_size :: proc() -> int {
    return size_of(Game_Memory)
}

@(export)
game_hot_reloaded :: proc(mem: rawptr) {
    g = (^Game_Memory)(mem)
    // Re-establish any proc pointers or caches that reference DLL code
    // e.g., g.update_fn = my_update  (stored as enum ID in Game_Memory)
}
```

---

## Host (main_hot_reload.odin)

```odin
package main

import "core:dynlib"
import "core:os"
import "core:fmt"
import "core:runtime"
import rl "vendor:raylib"

Game_API :: struct {
    lib:              dynlib.Library,
    game_init:        proc(),
    game_update:      proc() -> bool,
    game_shutdown:    proc(),
    game_memory:      proc() -> rawptr,
    game_memory_size: proc() -> int,
    game_hot_reloaded: proc(mem: rawptr),
    dll_time:         os.File_Time,
    dll_index:        int,
}

load_game_api :: proc(index: int) -> (api: Game_API, ok: bool) {
    // Copy DLL to avoid compiler lock on output file
    src := "build/game.dll"
    dst := fmt.tprintf("build/game_{}.dll", index)
    // Use the default allocator — dll_data must outlive any frame arena that
    // context.allocator might point to at call time
    dll_data, ok2 := os.read_entire_file(src, runtime.default_allocator())
    if !ok2 { return {}, false }
    defer delete(dll_data, runtime.default_allocator())
    if !os.write_entire_file(dst, dll_data) { return {}, false }

    api.lib = dynlib.load_library(dst) or_return

    // dynlib.symbol_address returns rawptr — must transmute to the target proc type
    // Each symbol is checked for nil before use
    sym_init        := dynlib.symbol_address(api.lib, "game_init")
    sym_update      := dynlib.symbol_address(api.lib, "game_update")
    sym_shutdown    := dynlib.symbol_address(api.lib, "game_shutdown")
    sym_memory      := dynlib.symbol_address(api.lib, "game_memory")
    sym_memory_size := dynlib.symbol_address(api.lib, "game_memory_size")
    sym_hot_reload  := dynlib.symbol_address(api.lib, "game_hot_reloaded")

    if sym_init == nil || sym_update == nil || sym_shutdown == nil ||
       sym_memory == nil || sym_memory_size == nil || sym_hot_reload == nil {
        fmt.eprintln("Missing required symbol in game DLL")
        dynlib.unload_library(api.lib)
        return {}, false
    }

    api.game_init         = transmute(proc())sym_init
    api.game_update       = transmute(proc() -> bool)sym_update
    api.game_shutdown     = transmute(proc())sym_shutdown
    api.game_memory       = transmute(proc() -> rawptr)sym_memory
    api.game_memory_size  = transmute(proc() -> int)sym_memory_size
    api.game_hot_reloaded = transmute(proc(rawptr))sym_hot_reload

    api.dll_index = index
    api.dll_time, _ = os.last_write_time_by_name(src)
    return api, true
}

main :: proc() {
    rl.InitWindow(1280, 720, "Game (Hot Reload)")
    defer rl.CloseWindow()

    game, ok := load_game_api(0)
    if !ok { fmt.eprintln("Failed to load game DLL"); return }
    game.game_init()

    for !rl.WindowShouldClose() {
        // Check for reload each frame
        dll_time, _ := os.last_write_time_by_name("build/game.dll")
        force_reload := rl.IsKeyPressed(.F5)
        force_restart := rl.IsKeyPressed(.F6)

        if force_restart {
            game.game_shutdown()
            dynlib.unload_library(game.lib)
            new_game, new_ok := load_game_api(game.dll_index + 1)
            if !new_ok {
                fmt.eprintln("Failed to load game DLL on restart — exiting")
                break
            }
            game = new_game
            game.game_init()
        } else if force_reload || dll_time != game.dll_time {
            // Save old state before unloading — keep running old DLL on failure
            mem := game.game_memory()
            old_size := game.game_memory_size()
            new_game, new_ok := load_game_api(game.dll_index + 1)
            if !new_ok {
                fmt.eprintln("Hot reload failed — continuing with old DLL")
                // old game DLL still loaded and valid; do nothing
            } else {
                dynlib.unload_library(game.lib)
                game = new_game
                // Validate layout hasn't changed
                if game.game_memory_size() != old_size {
                    fmt.eprintln("Game_Memory size changed — doing full restart")
                    game.game_init()
                } else {
                    game.game_hot_reloaded(mem)
                }
            }
        }

        if !game.game_update() { break }
    }

    game.game_shutdown()
    dynlib.unload_library(game.lib)
}
```

---

## Constraints Table

| Constraint | Why | Workaround |
|---|---|---|
| No struct field reordering in `Game_Memory` | Memory layout mismatch corrupts state silently | Check `game_memory_size()` — if changed, do full restart instead of hot reload |
| No proc pointers in `Game_Memory` | Old DLL code is unloaded; pointers dangle | Store enum IDs in `Game_Memory`; re-setup proc pointers in `game_hot_reloaded` |
| No globals outside `Game_Memory` | DLL data section is destroyed on unload | Make all globals point into `Game_Memory` via `g` |
| Raylib must be a shared library | Raylib has internal state (window, GL context) that must persist across reloads | Build with `-define:RAYLIB_SHARED=true` |
| Dynamic arrays in `Game_Memory` need stable backing | `[dynamic]T` stores a pointer; if backed by a destroyed arena, it dangles | Use the default allocator for dynamic arrays in `Game_Memory`, or a persistent arena allocated outside the DLL |

---

## Build Commands

```sh
# Hot reload — compile DLL only (fast, ~0.3s):
odin build source -build-mode:dll -define:RAYLIB_SHARED=true -out:build/game.dll

# Hot reload host — compile once at startup:
odin build source/main_hot_reload -out:build/game_host.exe

# Release — single exe, statically linked:
odin build source/main_release -out:build/game.exe -o:speed

# Windows: include debug info for each reload (unique PDB per reload):
odin build source -build-mode:dll -define:RAYLIB_SHARED=true \
    -out:build/game.dll -pdb-name:build/game_$(date +%s).pdb
```

---

## Reload Triggers

| Trigger | Behavior |
|---|---|
| DLL file timestamp changes | Automatic reload — preserves state |
| F5 | Manual reload — preserves state |
| F6 | Full restart — calls `game_shutdown` + `game_init` |
| `game_memory_size()` changed | Forced full restart — layout mismatch detected |

---

## PDB Management (Windows)

Each reload gets a unique PDB filename so the debugger doesn't lock the previous one.

In the host, generate a unique PDB name before triggering a recompile:

```odin
// In host — generate unique PDB path to pass to the build command
pdb_name := fmt.tprintf("build/game_{}.pdb", game.dll_index + 1)
```

Then pass it to the build command:

```sh
odin build source -build-mode:dll -define:RAYLIB_SHARED=true \
    -out:build/game.dll -pdb-name:build/game_1.pdb
```

Without unique PDB names, the debugger locks `game.pdb` and the next compile fails.

---

## Tracking Allocator for Leak Detection

Wrap DLL allocations in a tracking allocator during development. After each reload, report any allocations that weren't freed by the outgoing DLL:

```odin
// In host, before loading DLL:
track: mem.Tracking_Allocator
mem.tracking_allocator_init(&track, context.allocator)
context.allocator = mem.tracking_allocator(&track)

// After unloading old DLL:
for _, leak in track.allocation_map {
    fmt.printf("LEAK: %v bytes at %v\n", leak.size, leak.location)
}
mem.tracking_allocator_destroy(&track)
```

This catches allocations the game code made but forgot to free before reload — common when adding new systems.
