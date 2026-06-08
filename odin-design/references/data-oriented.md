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

The array-alias pattern is idiomatic for vector types. `Vector3 :: [3]f32`
gets all array-programming arithmetic and swizzle for free. `Vector3 :: struct
{ x, y, z: f32 }` gets none of it and is unidiomatic — avoid.

---

## Built-in Matrix Type (`matrix[R, C]T`)

Odin has a built-in `matrix[R, C]T` type with native multiplication,
transpose, and element access. **Stored column-major** (internally `[C][R]T`).
Element types: integers, floats, complex numbers. No booleans or quaternions.

### Declaration and basic operations

```odin
m := matrix[2, 3]f32{
    1, 2, 3,
    4, 5, 6,
}
m[0, 1]  // row 0, col 1 → 2

// Matrix × matrix: type-checked at compile time
a := matrix[2, 3]f32{1, 0, 0,  0, 1, 0}
b := matrix[3, 2]f32{1, 2,  3, 4,  5, 6}
c := a * b   // type: matrix[2, 2]f32

// Matrix × vector (column-vector convention)
M := matrix[3, 3]f32{
    1, 0, 0,
    0, 1, 0,
    0, 0, 1,
}
v := [3]f32{3, 2, 1}
result := M * v   // [3]f32{3, 2, 1} for identity

// Scalar assignment yields scaled identity
I: matrix[3, 3]f32 = 1   // identity matrix
S: matrix[3, 3]f32 = 2   // 2× scaled identity
```

### Built-in operations

| Operation | Syntax | Notes |
|-----------|--------|-------|
| Matrix multiply | `a * b` | Dimensions must be compatible; result type is inferred |
| Matrix × vector | `M * v` | `v` treated as column vector |
| Vector × matrix | `v * M` | `v` treated as row vector |
| Transpose | `transpose(m)` | Built-in; returns transposed matrix |
| Component-wise multiply | `hadamard_product(a, b)` | Use instead of `*` when you want element-wise, not matrix, multiply |
| Element access | `m[row, col]` | Zero-indexed |
| Scalar identity | `m = scalar` | Assigns scaled identity |

`+`, `-`, `&`, `|`, `~`, `&~` all work component-wise. `/`, `%`, `%%` are
not supported on matrices.

### Submatrix casting

Square matrices of the same element type can be cast between sizes:
- Casting to a **smaller** matrix takes the top-left submatrix.
- Casting to a **larger** matrix extends with zeros and ones on the diagonal.

```odin
mat2 :: distinct matrix[2, 2]f32
mat4 :: distinct matrix[4, 4]f32

m2 := mat2{1, 3, 2, 4}
m4 := mat4(m2)   // extends with identity padding
assert(m4[2, 2] == 1)
assert(m4[3, 3] == 1)
assert(mat2(m4) == m2)
```

Non-square matrices can be cast between shapes as long as the total element
count (`R × C`) is the same and the element type matches. Column-major order
is preserved across the cast.

### `matrix[R,C]T` vs nested arrays

| Use | Type | Reason |
|-----|------|--------|
| Any matrix math | `matrix[R, C]T` | Gets `*`, `transpose`, `hadamard_product` for free |
| FFI to row-major C library | `[R][C]T` or `#row_major matrix[R,C]T` | Control over memory layout |
| File I/O / serialization | `[R][C]T` | Explicit layout, no surprises |

### `core:math/linalg`

For production use, prefer `core:math/linalg` over hand-rolling. It provides
`Matrix4f32`, `Matrix3f32`, and ready-made constructors:

```odin
import "core:math/linalg"

view := linalg.matrix4_look_at_f32(eye, target, up)
proj := linalg.matrix4_perspective_f32(fov_radians, aspect, near, far)
mvp  := proj * view * model
```

For educational renderers, hand-rolling matrix multiplication is common (see
Marian Pekar's software renderer series). For production, use `core:math/linalg`.

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
