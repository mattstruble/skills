# Context System & Subtype Polymorphism

Read this reference for details on Odin's implicit context system, thread-local
behavior, and how to achieve polymorphism without methods or inheritance.

---

## The Context System

Every procedure in Odin implicitly receives a `context` parameter. This is not
magic — it's a real struct passed on the stack, just hidden from the signature.

```odin
// These are equivalent:
foo :: proc() { ... }
foo :: proc "odin" (/* implicit context */) { ... }
```

### What Context Contains

```odin
// Simplified — actual struct has more fields
Context :: struct {
    allocator:      Allocator,
    temp_allocator: Allocator,
    logger:         Logger,
    user_ptr:       rawptr,
    user_index:     int,
}
```

### Overriding Context

Context is value-typed. Modifications in a child scope don't affect the parent:

```odin
main :: proc() {
    // Default context.allocator is the heap allocator
    fmt.println(new(int))  // uses heap

    {
        context.allocator = my_arena_allocator
        fmt.println(new(int))  // uses arena
        do_stuff()  // do_stuff and all its callees also use arena
    }

    fmt.println(new(int))  // back to heap — context restored
}
```

### Thread-Local Behavior

Each OS thread gets its own context. When spawning threads, you may need to
propagate context explicitly:

```odin
import "core:thread"

worker :: proc(ctx: runtime.Context) {
    context = ctx  // Restore parent's context
    // Now uses same allocator, logger, etc.
}

spawn_worker :: proc() {
    t := thread.create(worker)
    // Pass current context as parameter if needed
}
```

### User Data

Pass application-specific data through the context without threading it
through every procedure signature:

```odin
App_State :: struct {
    frame_count: int,
    // ...
}

main :: proc() {
    state: App_State
    context.user_ptr = &state
    run_game()
}

// Deep in the call stack:
get_app_state :: proc() -> ^App_State {
    return cast(^App_State)context.user_ptr
}
```

---

## Subtype Polymorphism with `using`

Odin has no inheritance, but `using` on struct fields promotes the embedded
struct's fields to the parent, enabling a form of composition-based
polymorphism.

```odin
Base_Entity :: struct {
    pos:    Vector3,
    health: int,
    id:     u64,
}

Player :: struct {
    using base: Base_Entity,  // fields promoted
    inventory: [20]Item,
    mana:      int,
}

Enemy :: struct {
    using base: Base_Entity,  // fields promoted
    aggro_range: f32,
    patrol_path: []Vector3,
}

// Access promoted fields directly:
p: Player
p.pos = {10, 20, 0}    // equivalent to p.base.pos
p.health = 100          // equivalent to p.base.health

// Procedures accepting ^Base_Entity work with ^Player via pointer cast:
damage_entity :: proc(e: ^Base_Entity, amount: int) {
    e.health -= amount
}

// But you must cast explicitly:
damage_entity(&p.base, 10)
```

### When to Use `using`

- Embedding a common "header" struct in variants (entity types, widget types)
- When procedures operate on the base fields only
- Composition over inheritance — Odin's version of "has-a with field access"

### When NOT to Use

- Don't use `using` for unrelated data that happens to share a field name
- Don't build deep hierarchies — one level of embedding is typical
- If you need runtime dispatch, use tagged unions instead

---

## Tagged Unions for Runtime Polymorphism

When you need to dispatch on type at runtime, use a tagged union:

```odin
Shape :: union {
    Circle,
    Rect,
    Triangle,
}

Circle :: struct {
    center: Vector2,
    radius: f32,
}

Rect :: struct {
    min, max: Vector2,
}

Triangle :: struct {
    a, b, c: Vector2,
}

// Type switch for dispatch
area :: proc(s: Shape) -> f32 {
    switch v in s {
    case Circle:
        return math.PI * v.radius * v.radius
    case Rect:
        size := v.max - v.min
        return size.x * size.y
    case Triangle:
        // ... compute area
        return 0
    }
    return 0
}
```

### Union + #partial

Use `#partial switch` when you only care about some variants:

```odin
#partial switch v in shape {
case Circle:
    draw_circle(v)
case Rect:
    draw_rect(v)
// Triangle and future variants: no compile error
}
```

Without `#partial`, the compiler enforces exhaustive matching — add a new
variant and every switch must handle it.

---

## Procedure Groups (Overloading)

Odin supports explicit overloading via procedure groups:

```odin
draw_circle :: proc(c: Circle) { ... }
draw_rect :: proc(r: Rect) { ... }
draw_line :: proc(from, to: Vector2) { ... }

// Group them under one name:
draw :: proc{draw_circle, draw_rect, draw_line}

// Call dispatches based on argument types:
draw(my_circle)  // calls draw_circle
draw(my_rect)    // calls draw_rect
```

### Rules

- All overloads must be unambiguous for any given call site
- You can still call specific overloads directly: `draw_circle(c)`
- Use when the concept is the same but the data type varies
- Don't overuse — if the implementations are substantially different,
  separate names are clearer

---

## Interfaces via Procedure Pointers

For runtime-configurable behavior (plugins, backends, strategies):

```odin
Renderer_VTable :: struct {
    init:    proc(r: rawptr),
    draw:    proc(r: rawptr, commands: []Draw_Command),
    cleanup: proc(r: rawptr),
}

Renderer :: struct {
    vtable: ^Renderer_VTable,
    data:   rawptr,
}

renderer_draw :: proc(r: ^Renderer, commands: []Draw_Command) {
    r.vtable.draw(r.data, commands)
}
```

This is the manual vtable pattern — use it sparingly, only when you need
runtime dispatch between implementations that aren't known at compile time
(e.g., OpenGL vs Vulkan backend selection).

For most cases, a tagged union with a type switch is simpler and faster.
