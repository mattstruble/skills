---
name: odin-gamedev
summary: Odin game architecture with Raylib/Sokol: entity management, hot reloading, game state
type: design
description: Use when working on game projects in Odin — Raylib/Sokol integration, entity management, game state architecture, hot reloading, or implementing game patterns in Odin. Takes precedence over game-patterns for Odin-specific implementation. NOT for language syntax or idioms (see odin-design). NOT for engine-agnostic pattern theory (see game-patterns).
---

# Odin Game Development

Odin-specific game architecture. The `odin-design` skill handles language correctness; this skill handles how to structure games idiomatically in Odin. When both fire, this skill takes precedence on game architecture; `odin-design` takes precedence on language syntax.

---

## Philosophy: No-Engine Game Development

Odin + a library (Raylib, Sokol) is a complete game dev stack. You do not need an engine.

- **Start simple, add complexity only when needed.** Begin with a struct and a `[dynamic]` array. Upgrade to a handle map when pointer stability matters. Reach for `#soa` only after profiling.
- **Don't build a general-purpose engine — make a game.** Resist the urge to design a reusable framework. Solve the problem in front of you.
- **Avoid premature ECS.** Start with plain structs + typed arrays. ECS is a solution to a specific cache-miss problem at scale, not a default architecture.
- **Leverage Odin's built-in features.** Array programming for math, `#soa` for hot data, `context.temp_allocator` for frame scratch, `bit_set` for flags.
- **Odin's zero-value initialization is a feature.** Design structs so the zero value is valid (or at least safe). Fewer nil checks, simpler initialization.

---

## Allocator Strategy for Games

Every allocation in Odin goes through an allocator. Games have predictable lifetime tiers — match them.

| Lifetime | Allocator | Clear point | Example |
|---|---|---|---|
| Frame scratch | `context.temp_allocator` | End of frame (`free_all`) | UI strings, query results, path arrays |
| Level/scene | Custom `mem.Arena` | Level unload | Tilemap, level entities, dialogue |
| Entity lifetime (variable) | Handle map backing arena | On entity removal (slot reuse) | Individual entities, components |
| Program lifetime | Default allocator | Shutdown | Asset registry, config, audio system |

The temp allocator is the workhorse. Use it by default for anything that doesn't outlive the current frame. Escalate to an arena when data must survive multiple frames but has a clear group lifetime. Use the default allocator only for things that live until shutdown.

```odin
// End of every frame — clear all frame-scratch allocations at once
free_all(context.temp_allocator)
```

See `odin-design` → `references/allocators.md` for arena pitfalls and tracking allocator setup.

---

## Entity Management

### Start Simple

```odin
Entity :: struct {
    pos:     [2]f32,
    vel:     [2]f32,
    health:  f32,
    alive:   bool,
}

World :: struct {
    entities: [dynamic]Entity,
}
```

This works until you need stable references — a projectile tracking its target, a UI element linked to a specific enemy. When you store `^Entity`, the pointer dangles the moment the dynamic array grows.

### Upgrade to Handle Maps

A handle is an index + generation counter. The generation detects stale references to destroyed entities.

```odin
Entity_Handle :: struct {
    idx: u32,
    gen: u32,
}

// Zero value is the null handle — zero-init safe
NULL_HANDLE :: Entity_Handle{idx = 0, gen = 0}

// Usage
enemy_handle := entity_add(&world, enemy)

// Later — resolve to pointer (nil if entity was destroyed)
if e := entity_get(&world, enemy_handle); e != nil {
    e.health -= damage
}
```

See `references/handle-systems.md` for three concrete implementations with trade-off analysis.

---

## State Machines via Tagged Unions

Tagged unions are the dominant Odin state machine pattern. Per-state data lives in the variant struct; shared data stays on the entity.

```odin
Player_State :: union {
    State_Idle,
    State_Running,
    State_Jumping,
    State_Wall_Slide,
    State_Dashing,
}

// Stateless states are empty structs — zero allocation, clear intent
State_Idle    :: struct {}
State_Running :: struct {}

// Stateful states carry only their own data
State_Jumping :: struct {
    time_in_air:     f32,
    can_double_jump: bool,
}

State_Wall_Slide :: struct {
    wall_normal: [2]f32,
    slide_speed: f32,
}

State_Dashing :: struct {
    direction:      [2]f32,
    remaining_time: f32,
}

Player :: struct {
    // Shared data — always accessible regardless of state
    pos:   [2]f32,
    vel:   [2]f32,
    state: Player_State,
}
```

Dispatch with a type switch:

```odin
player_update :: proc(p: ^Player, dt: f32) {
    switch &s in p.state {
    case State_Idle:
        // check for movement input, transition to running
    case State_Running:
        // apply movement, check for jump
    case State_Jumping:
        s.time_in_air += dt
        if s.time_in_air > MAX_JUMP_TIME {
            p.state = State_Idle{}
        }
    case State_Wall_Slide:
        p.vel.y = min(p.vel.y, s.slide_speed)
    case State_Dashing:
        s.remaining_time -= dt
        p.pos += s.direction * DASH_SPEED * dt
        if s.remaining_time <= 0 {
            p.state = State_Running{}
        }
    }
}
```

**Design rule:** If data only makes sense in one state, it belongs in that state's variant struct. If it's needed across states, it belongs on the entity.

**What NOT to do:** OOP state objects with `enter`/`exit`/`update` methods, interface dispatch, or a separate state struct per state that all embed a common base. Odin has no interfaces; the tagged union is the idiomatic replacement.

---

## Hot Reload

Hot reload lets you recompile game logic and inject it into a running game without losing state. The architecture: an EXE host monitors a game DLL. All game state lives in a single `Game_Memory` struct. The DLL exports a fixed API. On reload, the host passes the existing memory pointer to the new DLL.

Key constraints:
- No procedure pointers in `Game_Memory` — old DLL code is unloaded. Store enum IDs instead; re-setup in `game_hot_reloaded`.
- No struct field reordering — memory layout must match. Check `memory_size()` and do a full restart if it changed.
- Raylib must be a shared library — it has internal state that must persist across reloads. Build with `-define:RAYLIB_SHARED=true`.

See `references/hot-reload.md` for the full DLL API, build scripts, PDB management, and file organization.

---

## Raylib Integration Patterns

```odin
import rl "vendor:raylib"
import "core:strings"
```

**String conversion** — Raylib's C API takes `cstring`. Convert from Odin strings using the temp allocator:

```odin
load_texture :: proc(path: string) -> rl.Texture2D {
    cpath := strings.clone_to_cstring(path, context.temp_allocator)
    return rl.LoadTexture(cpath)
}
```

**Basic game loop:**

```odin
main :: proc() {
    rl.InitWindow(1280, 720, "Game")
    defer rl.CloseWindow()
    for !rl.WindowShouldClose() {
        dt := rl.GetFrameTime()
        update(dt)
        rl.BeginDrawing()
        render()
        rl.EndDrawing()
        free_all(context.temp_allocator)
    }
}
```

**Hot reload build flag:** `-define:RAYLIB_SHARED=true` when building the game DLL.

See `references/game-architecture.md` for asset caching, level serialization, camera smoothing, and editor/game coupling patterns.

### Custom Rendering on Raylib

For CPU-side rendering — software rasterizers, raymarchers, fractal viewers, retro demos — the central performance technique is the **`rl.Image` framebuffer pattern**: draw to a backing image with `rl.ImageDrawPixel`, upload it to a texture once per frame with `rl.UpdateTexture`, then blit it with `rl.DrawTexture`. Per-pixel `rl.DrawPixel` calls go through the GPU pipeline individually and become the bottleneck.

For the **rendering theory itself** — coordinate spaces, perspective projection, triangle rasterization, barycentric coordinates, z-buffering, backface culling, UV mapping with perspective-correct interpolation, lighting models — see the `game-rendering` skill.

For **Odin/raylib implementation specifics** — `[^]rl.Color` multi-pointers from `rl.LoadImageColors`, the framebuffer lifecycle, power-of-2 texture sampling, FPS overlay — see `references/raylib-rendering.md`.

### Low-Level GPU Access in Odin

Raylib and Sokol are the default. Drop below them — to SDL3 GPU, raw Vulkan, or the `no_gfx` paradigm — only for: **bindless textures**, **GPU-driven/indirect rendering**, **compute shaders**, or **hardware raytracing**.

The `gpu-rendering-architecture` skill covers the GPU model (descriptor sets, barriers, render passes). This section covers Odin-specific idioms from [`leotmp/no_gfx_api`](https://github.com/leotmp/no_gfx_api).

**ZII (Zero-Is-Initialization)** — zero struct = valid default; no nil checks, no sentinels.
```odin
depth := gpu.Depth_State{mode = {.Read, .Write}, compare = .Less_Equal}
// gpu.Depth_State{} = no depth test/write — also valid, not a crash
```

**`{cpu, gpu}` allocation pairs** — `gpu.arena_alloc` returns `ptr_t(T)`; write via `.cpu`, GPU address flows implicitly to commands.
```odin
gpu.arena_free_all(frame_arena) // reset at start of each frame
data := gpu.arena_alloc(frame_arena, ShaderData)
data.cpu.transform   = calculate_mvp()
data.cpu.texture_idx = tex_id
gpu.cmd_dispatch(cmd, data, num_groups_x, num_groups_y) // .gpu implicit
```

**Timeline-semaphore frame pacing** — one `Semaphore` + incrementing `u64`; wait before recycling frame resources.
```odin
frame_sem, next_frame := gpu.semaphore_create(0), u64(1)
for !quit {
    if next_frame > Frames_In_Flight do gpu.semaphore_wait(frame_sem, next_frame - Frames_In_Flight)
    // acquire swapchain image; record commands into cmd; present after submit — not shown
    gpu.cmd_add_signal_semaphore(cmd, frame_sem, next_frame)
    gpu.queue_submit(.Main, {cmd})
    next_frame += 1
}
```

**`#load` SPIR-V** — embed bytecode at compile time; pass `[]u32` directly.
```odin
vert := gpu.shader_create(#load("shaders/main.vert.spv", []u32), .Vertex)
comp := gpu.shader_create_compute(#load("shaders/cull.comp.spv", []u32), 64, 1, 1)
```

---

## Pattern Mapping (Quick Reference)

**This skill takes precedence over game-patterns for Odin implementation.** When both fire, use the Odin-idiomatic approach below. For full implementations with code examples, see `references/odin-pattern-mappings.md`.

| Pattern | Odin Approach |
|---|---|
| **State** | Tagged union + type switch |
| **Object Pool** | Arena + free list (or handle map slot reuse) |
| **Observer** | `[dynamic]` callback list with `rawptr` data |
| **Component** | `using` embedding + typed arrays per component |
| **Flyweight** | `#soa` arrays for shared intrinsic data |
| **Service Locator** | `context.user_ptr` → `App_State` |
| **Command** | Union variants + ring buffer for undo |
| **Spatial Partition** | Flat grid: `[GRID_W * GRID_H][dynamic]Entity_Handle` |
| **Event Queue** | Ring buffer of `Event` union variants |
| **Type Object** | Enum + lookup table: `stats: [Enemy_Type]Enemy_Stats` |
| **Dirty Flag** | `bit_set[Entity_Flag]` or plain `bool` field |
| **Prototype** | Struct copy: `new_entity := template_entity` |

---

## Further Reading

| Reference | When to read it |
|---|---|
| `references/hot-reload.md` | Setting up DLL hot reload, build scripts, PDB management, constraints |
| `references/handle-systems.md` | Three handle map implementations, free list pattern, iteration |
| `references/game-architecture.md` | Game loop, asset caching, level serialization, camera, undo system |
| `references/odin-pattern-mappings.md` | Full Odin code for all 12 pattern mappings with NOT-to-do examples |
| `references/raylib-rendering.md` | Software framebuffer pattern, per-pixel rendering, texture interop on raylib |
