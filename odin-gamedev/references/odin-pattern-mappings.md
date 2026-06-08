# Odin Pattern Mappings

Idiomatic Odin implementations of the 12 patterns from `game-patterns`. For each: when to use it, Odin code, and the OOP/C++ version to avoid.

This skill takes precedence over `game-patterns` for Odin-specific implementation.

---

## 1. State Machine

**When:** An entity has mutually exclusive modes with different logic and some modes carry their own data.

```odin
// Per-state data lives in the variant struct
State_Idle    :: struct {}
State_Running :: struct {}
State_Jumping :: struct { time_in_air: f32, can_double_jump: bool }
State_Dashing :: struct { direction: [2]f32, time_left: f32 }

Player_State :: union { State_Idle, State_Running, State_Jumping, State_Dashing }

Player :: struct {
    pos:   [2]f32,
    vel:   [2]f32,
    state: Player_State,
}

player_update :: proc(p: ^Player, dt: f32) {
    switch &s in p.state {
    case State_Idle:
        if rl.IsKeyDown(.RIGHT) { p.state = State_Running{} }
    case State_Running:
        p.pos.x += 200 * dt
        if rl.IsKeyPressed(.SPACE) { p.state = State_Jumping{can_double_jump = true} }
    case State_Jumping:
        s.time_in_air += dt
        p.pos.y -= 300 * dt
        if s.time_in_air > 0.5 { p.state = State_Idle{} }
    case State_Dashing:
        s.time_left -= dt
        p.pos += s.direction * 600 * dt
        if s.time_left <= 0 { p.state = State_Running{} }
    }
}
```

**NOT:** Interface with `enter()/exit()/update()` methods. NOT: enum + scattered per-state variables on the entity.

---

## 2. Object Pool

**When:** You need many short-lived objects of the same type (bullets, particles, explosions) with predictable max count.

```odin
MAX_BULLETS :: 256

Bullet :: struct {
    pos:      [2]f32,
    vel:      [2]f32,
    lifetime: f32,
}

Bullet_Pool :: struct {
    items:     [MAX_BULLETS]Bullet,
    alive:     [MAX_BULLETS]bool,
    free_list: [dynamic]u32,
}

bullet_pool_init :: proc(pool: ^Bullet_Pool) {
    // Pre-fill free list with all slot indices — required before first spawn
    for i in 0..<MAX_BULLETS {
        append(&pool.free_list, u32(i))
    }
}

bullet_spawn :: proc(pool: ^Bullet_Pool, pos, vel: [2]f32) -> bool {
    if len(pool.free_list) == 0 { return false }  // pool full
    idx := pop(&pool.free_list)
    pool.items[idx] = Bullet{pos = pos, vel = vel, lifetime = 2.0}
    pool.alive[idx] = true
    return true
}

bullet_update :: proc(pool: ^Bullet_Pool, dt: f32) {
    for i in 0..<MAX_BULLETS {
        if !pool.alive[i] { continue }
        pool.items[i].pos += pool.items[i].vel * dt
        pool.items[i].lifetime -= dt
        if pool.items[i].lifetime <= 0 {
            pool.alive[i] = false
            append(&pool.free_list, u32(i))
        }
    }
}
```

**NOT:** Class-based pool with virtual `allocate()/deallocate()`. NOT: `new(Bullet)` per spawn.

---

## 3. Observer

**When:** One system needs to notify others of events without knowing who's listening (e.g., enemy death triggers score, sound, and particle effects).

```odin
Event :: union { Evt_Enemy_Died, Evt_Player_Damaged, Evt_Level_Complete }
Evt_Enemy_Died    :: struct { pos: [2]f32, score_value: int }
Evt_Player_Damaged :: struct { amount: f32 }
Evt_Level_Complete :: struct {}

Listener :: struct {
    callback: proc(data: rawptr, event: Event),
    data:     rawptr,
}

Event_Bus :: struct {
    listeners: [dynamic]Listener,
}

event_subscribe :: proc(bus: ^Event_Bus, cb: proc(rawptr, Event), data: rawptr) {
    append(&bus.listeners, Listener{callback = cb, data = data})
}

event_notify :: proc(bus: ^Event_Bus, event: Event) {
    for l in bus.listeners {
        l.callback(l.data, event)
    }
}

// Usage:
score_listener :: proc(data: rawptr, event: Event) {
    score := (^int)(data)
    if e, ok := event.(Evt_Enemy_Died); ok {
        score^ += e.score_value
    }
}
// event_subscribe(&bus, score_listener, &game.score)
```

**NOT:** Interface-based listener. NOT: Capturing closures (Odin has none). NOT: Storing `^Listener` — store value copies.

---

## 4. Component

**When:** Different entity types share some fields but not others (all entities have position; only enemies have health; only projectiles have damage).

```odin
// Shared base via `using` embedding — fields promoted to the outer struct
Base_Entity :: struct {
    pos: [2]f32,
    vel: [2]f32,
}

Player :: struct {
    using base: Base_Entity,
    health:     f32,
    stamina:    f32,
}

Enemy :: struct {
    using base:   Base_Entity,
    health:       f32,
    aggro_range:  f32,
    target:       Entity_Handle,
}

Projectile :: struct {
    using base: Base_Entity,
    damage:     int,
    owner:      Entity_Handle,
    lifetime:   f32,
}

// `using` means you can write p.pos instead of p.base.pos
move_entity :: proc(e: ^Base_Entity, dt: f32) {
    e.pos += e.vel * dt
}

// Call with any type that has Base_Entity embedded via `using`:
move_entity(&player.base, dt)
move_entity(&enemy.base, dt)
```

**NOT:** Inheritance hierarchy. NOT: Component interface with `update()` virtual method. NOT: `Entity` base class with virtual dispatch.

---

## 5. Flyweight

**When:** Many instances share identical read-only data (tile types, enemy stats, item definitions).

```odin
Tile_Type :: enum { Grass, Stone, Water, Sand, Lava }

// Intrinsic (shared per-type) — one entry per type, never per-instance
Tile_Info :: struct {
    walkable:   bool,
    texture_id: u16,
    name:       string,
    move_cost:  f32,
}

// Compile-time lookup table — zero runtime overhead
TILE_INFO :: [Tile_Type]Tile_Info{
    .Grass = {walkable = true,  texture_id = 0, name = "Grass", move_cost = 1.0},
    .Stone = {walkable = true,  texture_id = 1, name = "Stone", move_cost = 1.5},
    .Water = {walkable = false, texture_id = 2, name = "Water", move_cost = 0},
    .Sand  = {walkable = true,  texture_id = 3, name = "Sand",  move_cost = 1.2},
    .Lava  = {walkable = false, texture_id = 4, name = "Lava",  move_cost = 0},
}

// Extrinsic (per-instance) — just the enum, 1 byte per tile
MAP_W :: 256
MAP_H :: 256
tiles: [MAP_W * MAP_H]Tile_Type

// Access shared data:
info := TILE_INFO[tiles[x + y * MAP_W]]
if info.walkable { /* ... */ }
```

**NOT:** Shared pointer to a flyweight object. NOT: Flyweight factory class. NOT: Storing `Tile_Info` per tile instance.

---

## 6. Service Locator

**When:** Multiple systems need access to shared services (audio, physics, assets) without passing them through every call.

```odin
Game_Services :: struct {
    audio:   ^Audio_System,
    physics: ^Physics_World,
    assets:  ^Asset_Cache,
    events:  ^Event_Bus,
}

// Store in context.user_ptr — available anywhere without parameter threading
get_services :: proc() -> ^Game_Services {
    return (^Game_Services)(context.user_ptr)
}

// Setup at program start:
services := Game_Services{
    audio   = audio_system_create(),
    physics = physics_world_create(),
    assets  = asset_cache_create(),
    events  = event_bus_create(),
}
context.user_ptr = &services

// Usage anywhere in the call stack:
svc := get_services()
audio_play(svc.audio, "explosion.wav")
```

**NOT:** Global singleton registry. NOT: Dependency injection container. NOT: `ServiceLocator.get<AudioSystem>()` class.

---

## 7. Command

**When:** You need undoable actions (level editor), input replay, or deferred execution.

```odin
Cmd_Move_Entity   :: struct { entity: Entity_Handle, from, to: [2]f32 }
Cmd_Place_Tile    :: struct { x, y: int, old_type, new_type: Tile_Type }
Cmd_Delete_Entity :: struct { entity: Entity_Handle, snapshot: Entity }

Command :: union { Cmd_Move_Entity, Cmd_Place_Tile, Cmd_Delete_Entity }

undo_stack: [dynamic]Command

command_execute :: proc(world: ^World, cmd: Command) {
    switch c in cmd {
    case Cmd_Move_Entity:
        if e := entity_get(&world.entities, c.entity); e != nil {
            e.pos = c.to
        }
    case Cmd_Place_Tile:
        world.tiles[c.x + c.y * MAP_W] = c.new_type
    case Cmd_Delete_Entity:
        entity_remove(&world.entities, c.entity)
    }
    append(&undo_stack, cmd)
}

command_undo :: proc(world: ^World) {
    if len(undo_stack) == 0 { return }
    cmd := pop(&undo_stack)
    switch c in cmd {
    case Cmd_Move_Entity:
        if e := entity_get(&world.entities, c.entity); e != nil { e.pos = c.from }
    case Cmd_Place_Tile:
        world.tiles[c.x + c.y * MAP_W] = c.old_type
    case Cmd_Delete_Entity:
        // Restore from snapshot — handle may differ
        entity_add(&world.entities, c.snapshot)
    }
}
```

**NOT:** Command interface with `execute()/undo()` virtual methods. NOT: Heap-allocated command objects.

---

## 8. Spatial Partition

**When:** You need fast neighbor queries (collision detection, AI aggro range, area-of-effect) without checking every entity against every other.

```odin
CELL_SIZE :: f32(64)
GRID_W    :: 64
GRID_H    :: 64

Spatial_Grid :: struct {
    cells: [GRID_W * GRID_H][dynamic]Entity_Handle,
}

grid_cell :: proc(pos: [2]f32) -> int {
    cx := clamp(int(pos.x / CELL_SIZE), 0, GRID_W - 1)
    cy := clamp(int(pos.y / CELL_SIZE), 0, GRID_H - 1)
    return cy * GRID_W + cx
}

grid_insert :: proc(grid: ^Spatial_Grid, h: Entity_Handle, pos: [2]f32) {
    append(&grid.cells[grid_cell(pos)], h)
}

grid_clear :: proc(grid: ^Spatial_Grid) {
    for &cell in grid.cells { clear(&cell) }
}

// Rebuild each frame (simple and correct for most games):
grid_rebuild :: proc(grid: ^Spatial_Grid, storage: ^Entity_Storage) {
    grid_clear(grid)
    for i in 1..<len(storage.items) {
        if !storage.alive[i] { continue }
        h := Entity_Handle{idx = u32(i), gen = storage.generations[i]}
        grid_insert(grid, h, storage.items[i].pos)
    }
}

// Query neighbors in a radius:
grid_query_radius :: proc(grid: ^Spatial_Grid, pos: [2]f32, radius: f32, out: ^[dynamic]Entity_Handle) {
    min_cx := clamp(int((pos.x - radius) / CELL_SIZE), 0, GRID_W - 1)
    max_cx := clamp(int((pos.x + radius) / CELL_SIZE), 0, GRID_W - 1)
    min_cy := clamp(int((pos.y - radius) / CELL_SIZE), 0, GRID_H - 1)
    max_cy := clamp(int((pos.y + radius) / CELL_SIZE), 0, GRID_H - 1)
    for cy in min_cy..=max_cy {
        for cx in min_cx..=max_cx {
            for h in grid.cells[cy * GRID_W + cx] {
                append(out, h)
            }
        }
    }
}
```

**NOT:** Quadtree class hierarchy. NOT: Recursive tree traversal. NOT: Pointer-based tree nodes.

---

## 9. Event Queue

**When:** Systems need to communicate without tight coupling, and events should be processed in batch at a defined point in the frame.

```odin
Evt_Damage       :: struct { target: Entity_Handle, amount: int, source: Entity_Handle }
Evt_Spawn_Effect :: struct { pos: [2]f32, effect_type: int }
Evt_Play_Sound   :: struct { sound_id: int, pos: [2]f32 }

Game_Event :: union { Evt_Damage, Evt_Spawn_Effect, Evt_Play_Sound }

Event_Queue :: struct {
    events: [dynamic]Game_Event,
}

event_push :: proc(q: ^Event_Queue, e: Game_Event) {
    append(&q.events, e)
}

event_process :: proc(q: ^Event_Queue, world: ^World) {
    for evt in q.events {
        switch e in evt {
        case Evt_Damage:
            if entity := entity_get(&world.entities, e.target); entity != nil {
                entity.health -= f32(e.amount)
            }
        case Evt_Spawn_Effect:
            effect_spawn(&world.effects, e.pos, e.effect_type)
        case Evt_Play_Sound:
            audio_play_at(world.audio, e.sound_id, e.pos)
        }
    }
    clear(&q.events)
}
```

**NOT:** Priority queue with polymorphic event base class. NOT: Immediate dispatch (loses deferred processing benefits).

---

## 10. Type Object

**When:** Many instances share behavior defined by a type (enemy types, item types, spell types) and you want data-driven configuration.

```odin
Enemy_Type :: enum { Slime, Skeleton, Dragon, Goblin }

Enemy_Stats :: struct {
    max_health: int,
    speed:      f32,
    damage:     int,
    xp_reward:  int,
}

// Compile-time table — indexed by enum, zero overhead
ENEMY_STATS :: [Enemy_Type]Enemy_Stats{
    .Slime    = {max_health = 10,  speed = 50,  damage = 2,  xp_reward = 5},
    .Skeleton = {max_health = 25,  speed = 80,  damage = 5,  xp_reward = 15},
    .Dragon   = {max_health = 200, speed = 40,  damage = 30, xp_reward = 100},
    .Goblin   = {max_health = 15,  speed = 100, damage = 3,  xp_reward = 8},
}

Enemy :: struct {
    pos:    [2]f32,
    health: int,
    type:   Enemy_Type,
}

enemy_spawn :: proc(type: Enemy_Type, pos: [2]f32) -> Enemy {
    stats := ENEMY_STATS[type]
    return Enemy{pos = pos, health = stats.max_health, type = type}
}
```

**NOT:** Class-per-enemy-type hierarchy. NOT: Abstract factory. NOT: Runtime map lookup for stats.

---

## 11. Dirty Flag

**When:** Recomputing a derived value is expensive and should only happen when inputs change (transform matrices, pathfinding, shadow maps).

```odin
Entity_Flag :: enum { Dirty_Transform, Dirty_Sprite, Needs_Pathfind, Needs_Shadow }

Entity :: struct {
    pos:       [2]f32,
    rot:       f32,
    scale:     [2]f32,
    flags:     bit_set[Entity_Flag],
    transform: matrix[3, 3]f32,  // cached, recomputed when dirty
}

entity_set_pos :: proc(e: ^Entity, pos: [2]f32) {
    e.pos = pos
    e.flags += {.Dirty_Transform}
}

entity_update_transform :: proc(e: ^Entity) {
    if .Dirty_Transform not_in e.flags { return }
    // Recompute transform matrix from pos/rot/scale
    e.transform = make_transform(e.pos, e.rot, e.scale)
    e.flags -= {.Dirty_Transform}
}

// Check multiple flags at once:
if e.flags & {.Dirty_Transform, .Dirty_Sprite} != {} {
    // at least one dirty flag is set
}
```

**NOT:** Reactive/observable property system. NOT: Listener-based change notification. NOT: Recomputing every frame unconditionally.

---

## 12. Prototype

**When:** You spawn many instances of a common template with minor variations (enemy variants, item drops, projectile types).

```odin
Enemy :: struct {
    pos:         [2]f32,
    health:      int,
    speed:       f32,
    aggro_range: f32,
    sprite_id:   int,
}

// Compile-time templates — named constants, not heap objects
TEMPLATE_GOBLIN :: Enemy{
    health      = 30,
    speed       = 100,
    aggro_range = 150,
    sprite_id   = 3,
}

TEMPLATE_GOBLIN_ELITE :: Enemy{
    health      = 60,
    speed       = 120,
    aggro_range = 200,
    sprite_id   = 4,
}

// Spawn: copy template, override position (and any variant fields)
enemy_spawn_goblin :: proc(pos: [2]f32) -> Enemy {
    e := TEMPLATE_GOBLIN
    e.pos = pos
    return e
}

enemy_spawn_goblin_elite :: proc(pos: [2]f32, extra_health: int) -> Enemy {
    e := TEMPLATE_GOBLIN_ELITE
    e.pos = pos
    e.health += extra_health
    return e
}
```

**NOT:** Clone interface with deep-copy methods. NOT: Prototype registry class. NOT: `new(Enemy)` + field-by-field copy.
