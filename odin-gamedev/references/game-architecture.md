# Game Architecture

Practical patterns for structuring an Odin game. Start with the minimal loop, add complexity only when the problem demands it.

---

## Minimal Game Loop (Raylib)

```odin
package game

import rl "vendor:raylib"
import "core:math"

main :: proc() {
    rl.InitWindow(1280, 720, "My Game")
    defer rl.CloseWindow()

    for !rl.WindowShouldClose() {
        dt := rl.GetFrameTime()
        update(dt)

        rl.BeginDrawing()
        rl.ClearBackground(rl.RAYWHITE)
        render()
        rl.EndDrawing()

        free_all(context.temp_allocator)  // clear all frame-scratch allocations
    }
}
```

`free_all(context.temp_allocator)` at the end of every frame is the most important single line in a game loop. It reclaims all frame-scratch memory in one call — no individual frees needed for anything allocated with `context.temp_allocator`.

---

## Entity Progression

Start simple. Upgrade only when the current approach breaks.

**Step 1 — Plain dynamic array.** Works for most games.

```odin
Entity :: struct {
    pos:    [2]f32,
    vel:    [2]f32,
    health: f32,
    alive:  bool,
}

entities: [dynamic]Entity

// Iterate — use `&` to get a pointer to the element in place
for &e in entities {
    if !e.alive { continue }
    e.pos += e.vel * dt
}
```

**Step 2 — Handle map.** Add when you need stable references across frames (projectile tracking a target, UI linked to an enemy). See `handle-systems.md`.

**Step 3 — `#soa` arrays.** Add only after profiling shows cache misses on a hot path. `#soa [dynamic]Entity` transforms array-of-structs into struct-of-arrays layout — all positions contiguous, all velocities contiguous, etc.

```odin
// Only reach for this after profiling
entities: #soa [dynamic]Entity
for i in 0..<len(entities) {
    entities[i].pos += entities[i].vel * dt
}
```

---

## Asset Caching

Load assets once; return the cached version on subsequent calls. Use the temp allocator for the intermediate `cstring` conversion.

```odin
import "core:strings"
import rl "vendor:raylib"

textures: map[string]rl.Texture2D
sounds:   map[string]rl.Sound

load_texture :: proc(path: string) -> rl.Texture2D {
    if t, ok := textures[path]; ok { return t }
    cpath := strings.clone_to_cstring(path, context.temp_allocator)
    t := rl.LoadTexture(cpath)
    if t.id != 0 { textures[path] = t }
    return t
}

load_sound :: proc(path: string) -> rl.Sound {
    if s, ok := sounds[path]; ok { return s }
    cpath := strings.clone_to_cstring(path, context.temp_allocator)
    s := rl.LoadSound(cpath)
    if s.stream.buffer != nil { sounds[path] = s }  // only cache on success
    return s
}

unload_all_assets :: proc() {
    for _, t in textures { rl.UnloadTexture(t) }
    for _, s in sounds   { rl.UnloadSound(s) }
    delete(textures)
    delete(sounds)
}
```

---

## Level Serialization (JSON)

```odin
import "core:encoding/json"
import "core:os"

Tile_Data :: struct {
    type: int,
    x:    int,
    y:    int,
}

Enemy_Spawn :: struct {
    type: string,
    pos:  [2]f32,
}

Level_Data :: struct {
    tiles:       []Tile_Data,
    spawn_point: [2]f32,
    enemies:     []Enemy_Spawn,
}

level_save :: proc(level: ^Level_Data, path: string) -> bool {
    data, err := json.marshal(level^, allocator = context.temp_allocator)
    if err != nil { return false }
    return os.write_entire_file(path, data)
}

level_load :: proc(path: string, allocator := context.allocator) -> (Level_Data, bool) {
    raw, ok := os.read_entire_file(path, context.temp_allocator)
    if !ok { return {}, false }
    level: Level_Data
    err := json.unmarshal(raw, &level, allocator = allocator)
    return level, err == nil
}

level_destroy :: proc(level: ^Level_Data) {
    delete(level.tiles)
    for &e in level.enemies { delete(e.type) }
    delete(level.enemies)
}
```

Pass an arena allocator to `level_load` for level-lifetime data — then `level_destroy` is just `free_all(arena_allocator)`.

---

## Camera with Exponential Smoothing

```odin
import "core:math"
import rl "vendor:raylib"

Camera_2D_State :: struct {
    pos:    [2]f32,
    target: [2]f32,
    zoom:   f32,
}

camera_update :: proc(cam: ^Camera_2D_State, dt: f32) {
    // Exponential smoothing — framerate-independent, no overshoot
    t := 1.0 - math.exp_f32(-10.0 * dt)
    cam.pos += (cam.target - cam.pos) * t
}

camera_to_raylib :: proc(cam: Camera_2D_State) -> rl.Camera2D {
    return rl.Camera2D{
        target = cam.pos,
        offset = {f32(rl.GetScreenWidth()) / 2, f32(rl.GetScreenHeight()) / 2},
        zoom   = cam.zoom,
    }
}
```

Set `cam.target` to the player position each frame. The camera follows with smooth lag. Adjust the `10.0` constant to control responsiveness (higher = snappier).

---

## Editor / Game Coupling

Don't build a separate editor application. The editor is gameplay code that renders handles and responds to mouse input.

```odin
App_Mode :: enum { Game, Editor }

App :: struct {
    mode:   App_Mode,
    level:  Level_Data,
    player: Player,
    // editor state — only used when mode == .Editor
    selected_tile: int,
    cursor_pos:    [2]f32,
}

app_update :: proc(app: ^App, dt: f32) {
    switch app.mode {
    case .Game:
        game_update(app, dt)
        if rl.IsKeyPressed(.F1) { app.mode = .Editor }
    case .Editor:
        editor_update(app, dt)
        if rl.IsKeyPressed(.F1) { app.mode = .Game }
    }
}
```

Toggle between modes with a key press. The same level data and entity storage are shared — no serialization round-trip to switch modes.

---

## Undo System (Level Editor)

Serialize full state after each action into a ring buffer. Undo restores the previous snapshot. Simple, correct, and memory-cheap with arena-backed snapshots.

```odin
import "core:encoding/json"
import "core:fmt"

MAX_UNDO :: 64

Undo_Stack :: struct {
    snapshots: [MAX_UNDO][]byte,  // serialized level state
    head:      int,
    count:     int,
}

undo_push :: proc(stack: ^Undo_Stack, level: ^Level_Data) {
    data, err := json.marshal(level^, allocator = context.allocator)
    if err != nil { return }
    idx := stack.head % MAX_UNDO
    if stack.snapshots[idx] != nil { delete(stack.snapshots[idx]) }
    stack.snapshots[idx] = data
    stack.head = (stack.head + 1) % MAX_UNDO
    stack.count = min(stack.count + 1, MAX_UNDO)
}

undo_pop :: proc(stack: ^Undo_Stack, level: ^Level_Data) -> bool {
    if stack.count == 0 { return false }
    stack.head = (stack.head - 1 + MAX_UNDO) % MAX_UNDO
    stack.count -= 1
    data := stack.snapshots[stack.head]
    level_destroy(level)
    if err := json.unmarshal(data, level); err != nil {
        fmt.eprintln("undo_pop: failed to deserialize snapshot:", err)
        return false
    }
    return true
}
```

---

## Debug Overlay

Use `when ODIN_DEBUG` to include debug rendering only in debug builds — zero cost in release.

```odin
import "core:fmt"
import "core:strings"
import rl "vendor:raylib"

render_debug_overlay :: proc(world: ^World) {
    when ODIN_DEBUG {
        fps_text := fmt.tprintf("FPS: {}", rl.GetFPS())
        rl.DrawText(strings.clone_to_cstring(fps_text, context.temp_allocator), 10, 10, 20, rl.GREEN)

        entity_text := fmt.tprintf("Entities: {}", count_living(world))
        rl.DrawText(strings.clone_to_cstring(entity_text, context.temp_allocator), 10, 35, 20, rl.GREEN)
    }
}
```

---

## Single-Exe Distribution

```sh
# Release build — one binary, no DLL dependencies (except system libs)
odin build . -o:speed -out:game.exe

# Embed assets directly into the binary (small assets only):
icon_data :: #load("assets/icon.png")
```

Ship the executable alongside the `assets/` directory. For small assets (fonts, icons, shaders), `#load` embeds them at compile time — no separate files needed.
