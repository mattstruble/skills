# Handle Systems

Raw pointers to entities dangle when dynamic arrays grow or entities are destroyed. Plain indices silently alias reused slots. Handle systems solve both problems with a generation counter.

---

## The Problem

```odin
// WRONG: raw pointer — dangles when enemies array grows
target: ^Enemy = &enemies[3]
append(&enemies, new_enemy)  // realloc! target is now garbage

// WRONG: plain index — silently aliases reused slot
target_idx: int = 3
remove_enemy(3)              // slot 3 freed
spawn_enemy()                // slot 3 reused for a new enemy
// target_idx still = 3, now points to wrong enemy — no error
```

---

## Handle = Index + Generation

On removal, increment the slot's generation. On access, compare the handle's generation with the slot's generation — a mismatch means the reference is stale.

```odin
Entity_Handle :: struct {
    idx: u32,
    gen: u32,
}
```

**Zero sentinel:** `Entity_Handle{}` (idx=0, gen=0) means "null." Reserve slot 0 as a dummy entry. Zero-initialized handles are always invalid — safe as a default struct field value.

```odin
NULL_HANDLE :: Entity_Handle{idx = 0, gen = 0}
```

---

## Three Variants

| Variant | Backing | Capacity | Pointer stable? | WASM? | Best for |
|---------|---------|----------|-----------------|-------|----------|
| `handle_map_static` | `[N]T` fixed array | Compile-time N | Yes | Yes | Known max, simplest, WASM games |
| `handle_map_static_virtual` | `[dynamic]T` + virtual arena | Up to reserved size | Yes | No | Default choice — reserve generously |
| `handle_map_growing` | `[dynamic]^T` + growing arena | Unbounded | Yes | Yes | When you truly cannot estimate max |

**Default recommendation:** Use `handle_map_static_virtual` with a generous reservation (virtual memory is cheap — reserve 100K slots if you want). Use `handle_map_static` for WASM targets. Use `handle_map_growing` only when the upper bound is genuinely unknown.

---

## Core API Pattern

```odin
package game

Entity :: struct {
    pos:    [2]f32,
    vel:    [2]f32,
    health: f32,
    // ... entity data
}

Entity_Storage :: struct {
    items:       [dynamic]Entity,
    generations: [dynamic]u32,
    alive:       [dynamic]bool,
    free_list:   [dynamic]u32,
}

entity_storage_init :: proc(s: ^Entity_Storage) {
    // Reserve slot 0 as the null sentinel — never used for real entities
    append(&s.items, Entity{})
    append(&s.generations, 0)
    append(&s.alive, false)
}

entity_add :: proc(s: ^Entity_Storage, e: Entity) -> Entity_Handle {
    idx: u32
    if len(s.free_list) > 0 {
        idx = pop(&s.free_list)
    } else {
        idx = u32(len(s.items))
        append(&s.items, Entity{})
        append(&s.generations, u32(0))
        append(&s.alive, false)
    }
    s.items[idx] = e
    s.alive[idx] = true
    return Entity_Handle{idx = idx, gen = s.generations[idx]}
}

entity_get :: proc(s: ^Entity_Storage, h: Entity_Handle) -> ^Entity {
    if h.idx == 0 { return nil }                          // null sentinel
    if h.idx >= u32(len(s.items)) { return nil }          // out of range
    if !s.alive[h.idx] { return nil }                     // destroyed
    if s.generations[h.idx] != h.gen { return nil }       // stale handle
    return &s.items[h.idx]
}

entity_remove :: proc(s: ^Entity_Storage, h: Entity_Handle) {
    if entity_get(s, h) == nil { return }  // already dead or invalid
    s.alive[h.idx] = false
    s.generations[h.idx] += 1             // invalidate all existing handles to this slot
    append(&s.free_list, h.idx)
}
```

---

## Iteration Pattern

Skip dead slots. Start at index 1 to skip the null sentinel at slot 0.

```odin
// Update all living entities
for i in 1..<len(storage.items) {
    if !storage.alive[i] { continue }
    e := &storage.items[i]
    entity_update(e, dt)
}

// Collect all living handles (e.g., for spatial queries)
living: [dynamic]Entity_Handle
for i in 1..<len(storage.items) {
    if !storage.alive[i] { continue }
    append(&living, Entity_Handle{idx = u32(i), gen = storage.generations[i]})
}
```

---

## Static Variant (WASM / Known Max)

When the maximum entity count is known at compile time, a fixed array avoids dynamic allocation entirely — required for WASM targets where virtual memory tricks don't apply.

```odin
MAX_ENEMIES :: 1024

Enemy_Storage_Static :: struct {
    items:       [MAX_ENEMIES]Enemy,
    generations: [MAX_ENEMIES]u32,
    alive:       [MAX_ENEMIES]bool,
    free_list:   [dynamic]u32,  // still dynamic — just the index list
    count:       int,           // starts at 1 to reserve slot 0 as null sentinel
}

enemy_storage_static_init :: proc(s: ^Enemy_Storage_Static) {
    s.count = 1  // reserve slot 0 as null sentinel — never used for real entities
}

enemy_add_static :: proc(s: ^Enemy_Storage_Static, e: Enemy) -> (Entity_Handle, bool) {
    if len(s.free_list) == 0 && s.count >= MAX_ENEMIES {
        return {}, false  // at capacity
    }
    idx: u32
    if len(s.free_list) > 0 {
        idx = pop(&s.free_list)
    } else {
        idx = u32(s.count)
        s.count += 1
    }
    s.items[idx] = e
    s.alive[idx] = true
    return Entity_Handle{idx = idx, gen = s.generations[idx]}, true
}
```

---

## Growing Variant (Unbounded)

When the upper bound is genuinely unknown, store pointers into a growing arena. Pointers remain stable even as the index array grows.

```odin
Entity_Storage_Growing :: struct {
    ptrs:        [dynamic]^Entity,   // stable pointers into arena
    generations: [dynamic]u32,
    alive:       [dynamic]bool,
    free_list:   [dynamic]u32,
    arena:       mem.Arena,          // backing memory for Entity values
}
```

The arena grows in chunks; old chunks are never freed until shutdown, so pointers remain valid.

---

## Key Rules

- **Store handles, not pointers.** Resolve handles to pointers only when needed within a frame. Never store the resolved pointer across frames.
- **Zero-initialized handles are always invalid.** `Entity_Handle{}` is the safe default for struct fields — no explicit "null" check needed beyond `entity_get` returning nil.
- **Generation overflow is not a practical concern.** A u32 generation requires 2^32 reuses of a single slot before aliasing. At 60 fps, a slot would need to be reused ~2 billion times — about 2.3 years of continuous reuse.
- **Free list reuse is LIFO.** `pop` from the free list reuses the most recently freed slot. This is cache-friendly and keeps the active range compact.
- **Don't store handles to temporary entities.** If an entity is created and destroyed within the same frame, any handle to it is immediately stale. This is correct behavior — callers that resolve the handle get nil.
