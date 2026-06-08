# Procedures and Polymorphism in Odin

Odin has no methods, no interfaces, no inheritance, and no implicit overloading.
Every dispatch mechanism is explicit. This file covers the patterns that replace
those constructs and when to use each.

---

## No Methods, No UFCS

Data and code are separate. Structs hold data; procedures are standalone. There
is no method syntax and no uniform function call syntax (UFCS).

```odin
// WRONG — does not compile
entity.update(dt)
entity.draw(renderer)

// CORRECT — free procedures with type prefix
entity_update(&entity, dt)
entity_draw(&entity, renderer)
```

Group related procedures by file and naming prefix. The prefix acts as the
namespace. Callers read `entity_update` and immediately know which type is
being operated on.

---

## Procedure Groups (Explicit Overloading)

Odin does not allow two procedures with the same name. Overloading is opt-in
via procedure groups, which bundle separately-named procedures under one
dispatch name.

```odin
bool_to_string   :: proc(v: bool)   -> string { return v ? "true" : "false" }
int_to_string    :: proc(v: int)    -> string { return fmt.tprintf("%d", v) }
entity_to_string :: proc(e: Entity) -> string { return fmt.tprintf("Entity(%d)", e.id) }

// Explicit group — compiler resolves at call site based on argument type
to_string :: proc{bool_to_string, int_to_string, entity_to_string}

// Usage — dispatches by argument type
s1 := to_string(true)       // calls bool_to_string
s2 := to_string(42)         // calls int_to_string
s3 := to_string(my_entity)  // calls entity_to_string
```

### Rules

- All overloads must be unambiguous for any given call site; the compiler
  rejects ambiguous groups.
- You can always call the specific procedure directly (`int_to_string(42)`).
- Don't overuse: if implementations are substantially different, separate names
  are clearer than forcing a group.

---

## Interfaces via Procedure Pointer Structs

When you need runtime dispatch between implementations not known at compile time
(e.g., platform backends, plugin systems), use a manual vtable: a struct of
procedure pointers paired with a `rawptr` to the implementation state.

```odin
Window_Interface :: struct {
    init:     proc(state: rawptr),
    shutdown: proc(state: rawptr),
    present:  proc(state: rawptr),
}

Window :: struct {
    vtable: ^Window_Interface,
    state:  rawptr,
}

window_present :: proc(w: ^Window) {
    w.vtable.present(w.state)
}
```

For compile-time platform selection, use `when` instead — it generates no
runtime overhead and keeps the code readable:

```odin
when ODIN_OS == .Windows {
    window_init :: proc(w: ^Window) { /* win32 */ }
} else when ODIN_OS == .Linux {
    window_init :: proc(w: ^Window) { /* x11 */ }
}
```

Use the vtable pattern only when the selection must happen at runtime (e.g.,
the user picks a backend from a config file). For most cases, a tagged union
with a type switch is simpler and faster.

---

## `using` for Field Promotion (Subtype Polymorphism)

`using` on a struct field promotes the embedded struct's fields to the parent,
enabling composition-based polymorphism. One level deep is the norm. See the
"Subtype Polymorphism with `using`" section in `references/context-system.md`
for worked examples and caveats.

The key rule: procedures that accept `^Base_Entity` work with `^Player` only
via an explicit `&p.base` cast — Odin does not implicitly upcast pointers.

---

## Tagged Unions for Runtime Polymorphism

Tagged unions replace inheritance hierarchies for runtime dispatch. See the
"Tagged Unions for Runtime Polymorphism" section in `references/context-system.md`
for the full pattern with `#partial switch`.

One pattern not covered there: **per-state data in a state machine**. Each
variant carries only the data relevant to that state, eliminating the "fat
struct with mostly-nil fields" problem:

```odin
Enemy_State :: union {
    Idle,
    Patrolling,
    Chasing,
    Attacking,
}

Idle       :: struct {}
Patrolling :: struct { path: []Vector2, path_index: int }
Chasing    :: struct { target_id: u64, last_known_pos: Vector2 }
Attacking  :: struct { target_id: u64, cooldown: f32 }

Enemy :: struct {
    pos:   Vector2,
    state: Enemy_State,
}

enemy_update :: proc(e: ^Enemy, dt: f32) {
    switch &s in e.state {
    case nil:
        // uninitialized — set e.state = Idle{} before first update
    case Idle:
        // ...
    case Patrolling:
        if len(s.path) > 0 {
            s.path_index = (s.path_index + 1) % len(s.path)
        }
    case Chasing:
        // use s.target_id, s.last_known_pos
    case Attacking:
        s.cooldown -= dt
    }
}
```

Transitioning states is an assignment: `e.state = Chasing{target_id = id, ...}`.
Old state data is discarded automatically.

---

## When to Use Which

| Need | Approach |
|------|----------|
| Same operation on different data shapes | Procedure group |
| Compile-time platform/config selection | `when` conditional + specific procs |
| Runtime dispatch between known variants | Tagged union + type switch |
| Entity composition (shared fields) | `using` field promotion |
| Plugin/backend selection at runtime | Procedure pointer struct (vtable) |
| Callback with state | `proc(data: rawptr)` + data pointer |

---

## Non-Capturing Closures

Odin procedures cannot capture variables from an enclosing scope. A procedure
literal assigned to a variable is valid, but it cannot reference outer locals:

```odin
// WRONG — does not compile; count is captured from outer scope
count := 0
increment := proc() { count += 1 }

// CORRECT — pass state explicitly
Incrementer :: struct { count: int }

increment :: proc(data: rawptr) {
    state := (^Incrementer)(data)
    state.count += 1
}

inc: Incrementer
some_api_register_callback(increment, &inc)
```

This pattern appears everywhere callbacks are needed: sorting comparators,
event handlers, deferred work, and platform API callbacks. The `rawptr` carries
the state; the procedure is stateless and reusable.

For comparator-based sorting, check `pkg.odin-lang.org/core/slice/` for the
exact procedure signatures — some take value comparators directly, so no rawptr
is needed. The rawptr pattern is for APIs that store the callback for later
invocation.
