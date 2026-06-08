# Allocator Patterns in Odin

Read this reference when working with memory allocation, debugging leaks, or
choosing between allocator strategies.

---

## The Context System & Allocators

Every procedure in Odin receives an implicit `context` parameter. This context
carries:

- `context.allocator` — the default allocator for `new()`, `make()`, `append()`
- `context.temp_allocator` — a bulk-freeable allocator for short-lived data
- `context.logger` — structured logging
- User-defined fields via `context.user_ptr`

You can override the allocator for a scope:

```odin
context.allocator = my_arena_allocator
// All allocations in this scope (and callees) use my_arena_allocator
thing := new(Thing)  // allocated from my_arena_allocator
```

---

## Temporary Allocator

The temp allocator is a ring buffer / arena that you clear in bulk. It is the
first tool you should reach for.

**When to use:** Any allocation that doesn't outlive the current frame, request,
or logical operation.

```odin
// Game loop example
game_loop :: proc() {
    for !should_quit {
        update()
        render()
        free_all(context.temp_allocator)  // clear all temp allocations
    }
}

// Using temp allocator explicitly
format_debug :: proc(entity: ^Entity) -> string {
    // String lives until next free_all — don't store it long-term
    return fmt.tprintf("Entity %d at (%f, %f)", entity.id, entity.pos.x, entity.pos.y)
}

// Dynamic array with temp allocator
get_nearby_entities :: proc(pos: Vector2, radius: f32) -> []Entity {
    results := make([dynamic]Entity, context.temp_allocator)
    for &e in world.entities {
        if distance(e.pos, pos) < radius {
            append(&results, e)
        }
    }
    return results[:]
}
```

**Key points:**
- `fmt.tprintf` and `fmt.tprint` allocate from temp allocator automatically
- No individual frees needed — everything cleared in bulk
- Don't store temp-allocated data in long-lived structures
- Default temp allocator size is sufficient for most use cases

---

## Custom Arenas

Use arenas when a group of allocations shares a lifetime that isn't frame-scoped.

```odin
import "core:mem"

// Fixed-size arena from a byte buffer
Level :: struct {
    arena: mem.Arena,
    // ... level data ...
}

level_init :: proc(level: ^Level) {
    buf := make([]byte, mem.Megabyte * 64)
    mem.arena_init(&level.arena, buf)
}

level_destroy :: proc(level: ^Level) {
    free_all(mem.arena_allocator(&level.arena))
    // All level allocations freed in one shot
}

// Use it
load_level_data :: proc(level: ^Level, path: string) {
    context.allocator = mem.arena_allocator(&level.arena)
    // Everything allocated here lives until level_destroy
    tiles := make([]Tile, tile_count)
    entities := make([]Entity, entity_count)
}
```

---

## Arena Pitfall: Dynamic Arrays

**Problem:** Dynamic arrays (`[dynamic]T`) grow by allocating a new, larger
backing array and freeing the old one. In an arena, "free" is a no-op —
the old backing memory leaks (stays allocated until the arena is freed in bulk).

```odin
// PROBLEMATIC: growing dynamic array in an arena leaks old backing arrays
arena_alloc := mem.arena_allocator(&my_arena)
arr := make([dynamic]int, 0, 0, arena_alloc)
for i in 0..<1000 {
    append(&arr, i)  // Each grow leaks the previous backing array
}
```

**Solutions:**

1. **Pre-allocate with known max size:**
   ```odin
   arr := make([dynamic]int, 0, MAX_EXPECTED, arena_alloc)
   // Won't grow if you stay under MAX_EXPECTED
   ```

2. **Use a virtual/growing arena** (`mem.virtual.Arena`):
   ```odin
   import vmem "core:mem/virtual"

   varena: vmem.Arena
   vmem.arena_init_growing(&varena)
   alloc := vmem.arena_allocator(&varena)
   // Reserves address space; commits pages on demand
   // No old backing memory to leak since addresses are stable
   ```

3. **Use the default allocator** for dynamic arrays that grow unpredictably,
   and the arena for everything else.

---

## Tracking Allocator (Development Builds)

Wraps another allocator to detect leaks and double-frees at runtime.

```odin
import "core:mem"

main :: proc() {
    track: mem.Tracking_Allocator
    mem.tracking_allocator_init(&track, context.allocator)
    context.allocator = mem.tracking_allocator(&track)
    defer {
        if len(track.allocation_map) > 0 {
            fmt.eprintln("=== MEMORY LEAKS ===")
            for _, entry in track.allocation_map {
                fmt.eprintf("  %v bytes at %v\n", entry.size, entry.location)
            }
        }
        if len(track.bad_free_array) > 0 {
            fmt.eprintln("=== BAD FREES ===")
            for entry in track.bad_free_array {
                fmt.eprintf("  %v\n", entry.location)
            }
        }
        mem.tracking_allocator_destroy(&track)
    }

    // ... rest of program ...
    // On exit, any unfreed allocations are reported with source location
}
```

**When to use:** Always in debug builds. Wrap it conditionally:

```odin
when ODIN_DEBUG {
    track: mem.Tracking_Allocator
    mem.tracking_allocator_init(&track, context.allocator)
    context.allocator = mem.tracking_allocator(&track)
    defer { /* report leaks */ }
}
```

---

## Panic Allocator (Catching Unexpected Allocations)

Use as a fallback to catch code paths that allocate when they shouldn't:

```odin
import "core:mem"

// Ensure a procedure never allocates
context.allocator = mem.panic_allocator()
pure_computation(data)  // If this allocates, program panics with location info
```

---

## Allocation Patterns Summary

| Lifetime | Allocator | Free strategy |
|----------|-----------|---------------|
| Frame / request / temporary | `context.temp_allocator` | `free_all()` in bulk |
| Grouped (level, scene, phase) | Custom `mem.Arena` | `free_all()` on group end |
| Program lifetime / variable size | `context.allocator` (default) | Individual `free()`/`delete()` |
| Debug wrapper | `mem.Tracking_Allocator` | Reports leaks on destroy |
| "Should never allocate" guard | `mem.panic_allocator()` | Panics if called |

---

## Common Mistakes

1. **Forgetting `free_all(context.temp_allocator)`** — temp memory grows
   unbounded. Call it at a natural boundary (end of frame, end of request).

2. **Storing temp-allocated data long-term** — the data is invalidated on
   the next `free_all`. Copy it to a persistent allocator if needed.

3. **Growing dynamic arrays in fixed arenas** — use pre-allocation or
   virtual arenas (see above).

4. **Not using tracking allocator in dev** — leaks are silent by default.
   Always wrap in debug builds.

5. **Passing allocator-dependent data across threads** — the context is
   thread-local. If sharing data, ensure the allocator is thread-safe or
   allocate from a shared arena.
