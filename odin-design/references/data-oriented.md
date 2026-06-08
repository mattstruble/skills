# Data-Oriented Patterns in Odin

Read this reference when working with performance-sensitive data layouts,
array programming, or Odin's data-oriented features.

---

## Structure of Arrays (#soa)

By default, an array of structs stores fields interleaved (AoS):

```
[Entity0.pos, Entity0.health, Entity1.pos, Entity1.health, ...]
```

`#soa` reorders to group same fields together (SoA):

```
[Entity0.pos, Entity1.pos, ...], [Entity0.health, Entity1.health, ...]
```

### Usage

```odin
Particle :: struct {
    pos:      Vector3,
    vel:      Vector3,
    lifetime: f32,
    color:    [4]u8,
}

// Fixed-size SoA array
particles: #soa[1024]Particle

// Access individual field arrays for cache-friendly iteration
update_positions :: proc(ps: ^#soa[1024]Particle, dt: f32) {
    for i in 0..<1024 {
        ps.pos[i] += ps.vel[i] * dt
    }
    // Only pos and vel cache lines are touched — color/lifetime stay cold
}
```

### When to Use

- **Proven performance benefit** — profile first, SoA second
- Hot loops that touch only a subset of fields
- Large arrays (thousands of elements) where cache pressure matters
- Particle systems, ECS-style entity storage, physics simulations

### When NOT to Use

- Small arrays or infrequent access — overhead not worth it
- When you need to pass individual structs around (SoA makes this awkward)
- Prototyping — switch to SoA once the data layout stabilizes

---

## Array Programming

Odin supports element-wise operations on fixed-size arrays natively:

```odin
Vector3 :: [3]f32

a := Vector3{1, 2, 3}
b := Vector3{4, 5, 6}

c := a + b        // {5, 7, 9}
d := a * b        // {4, 10, 18}
e := a * 2.0      // {2, 4, 6} — scalar broadcast
f := a / b        // {0.25, 0.4, 0.5}
```

This works for any fixed-size array with numeric element types. No operator
overloading needed — it's built into the language.

### Swizzle

```odin
v := [4]f32{1, 2, 3, 4}
xy := v.xy        // [2]f32{1, 2}
zw := v.zw        // [2]f32{3, 4}
yx := v.yx        // [2]f32{2, 1}
xxx := v.xxx      // [3]f32{1, 1, 1}
```

Fields: `.x`, `.y`, `.z`, `.w` (or `.r`, `.g`, `.b`, `.a` for colors).

---

## Bit Sets

Efficient membership testing backed by a single integer:

```odin
Direction :: enum { North, South, East, West }

// A set of directions
Directions :: bit_set[Direction]

allowed: Directions = {.North, .East}

if .North in allowed { /* ... */ }

// Set operations
all := Directions{.North, .South, .East, .West}
remaining := all - allowed   // {.South, .West}
combined := allowed | {.South}  // {.North, .East, .South}
```

### Bit Sets with Integer Ranges

```odin
Small_Set :: bit_set[0..<32]  // set of integers 0-31

s: Small_Set
s += {1, 5, 17}
if 5 in s { /* ... */ }
```

### When to Use

- Flags, capabilities, permissions
- Tile properties, collision layers
- Any small enum where you need set operations
- Replace `bool` arrays for small domains (more cache-friendly, supports
  set operations)

---

## Zero Is Initialization (ZII)

All variables in Odin are zero-initialized by default:

```odin
x: int           // 0
v: Vector3       // {0, 0, 0}
s: string        // "" (zero-length slice)
p: ^Thing        // nil
arr: [10]int     // all zeros
m: map[string]int  // nil map (safe to read, not to write)
```

### Design Implication

Design structs so that zero is a valid/useful initial state:

```odin
// GOOD: zero value is a valid empty entity
Entity :: struct {
    pos:    Vector3,    // {0,0,0} is fine
    health: int,       // 0 means dead or uninitialized — handle both
    flags:  Entity_Flags,  // empty bit_set
}

// If zero ISN'T useful, use an explicit init proc:
Camera :: struct {
    fov:       f32,   // 0 is not useful
    near_clip: f32,   // 0 is not useful
}

camera_init :: proc(c: ^Camera) {
    c.fov = 60.0
    c.near_clip = 0.1
}
```

### Opting Out

```odin
x: int = ---   // UNINITIALIZED — use only when you know you'll write before read
```

This is rare and primarily for performance-critical bulk allocations where
you'll immediately overwrite the memory.

---

## Designated Initializers

Always prefer named field initialization for clarity:

```odin
// GOOD: clear what each field is
player := Entity{
    pos    = {100, 200, 0},
    health = 100,
}
// Unmentioned fields are zero-initialized

// AVOID: positional initialization (brittle, unclear)
player := Entity{{100, 200, 0}, 100, {}}
```

---

## Slices vs Dynamic Arrays vs Fixed Arrays

| Type | Syntax | Owns memory? | Growable? | Use case |
|------|--------|-------------|-----------|----------|
| Fixed array | `[N]T` | Value (stack) | No | Small, known-size data |
| Slice | `[]T` | No (view) | No | Passing array data to procedures |
| Dynamic array | `[dynamic]T` | Yes (heap) | Yes | Collections that grow |
| SOA array | `#soa[N]T` | Value | No | Cache-friendly fixed collections |

**Key rules:**
- Procedures should accept `[]T` (slices) as parameters, not `[dynamic]T`
- Convert dynamic array to slice with `arr[:]`
- Fixed arrays implicitly convert to slices when passed to procedures
- `make([dynamic]T)` allocates; pair with `delete(arr)`
- `make([]T, count)` allocates a fixed slice; pair with `delete(slice)`

---

## Multi-Pointers

For interop with C or bulk memory operations:

```odin
// [^]T is a multi-pointer — pointer to multiple T values (like C's T*)
raw_data: [^]u8 = raw_ptr
slice := raw_data[:count]  // Convert to slice with known length
```

Use slices (`[]T`) in Odin-native code. Multi-pointers are for FFI boundaries.
