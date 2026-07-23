---
name: odin-design
summary: Idiomatic Odin patterns, allocators, package structure, and LLM knowledge-gap corrections
type: design
description: You MUST consult this skill when writing, reviewing, or generating Odin code. Also trigger on .odin files, Odin package structure, allocator patterns, or any Odin-specific design question. LLMs have significant knowledge gaps about Odin — this skill fills them. NOT for general systems programming advice or C/Zig/Rust unless comparing to Odin idioms.
---

# Odin Design Patterns

Odin is underrepresented in LLM training data. You will confidently produce
wrong patterns from Go, Rust, C++, or Zig. This skill corrects those instincts
and provides idiomatic Odin patterns.

**Critical rule:** Never guess Odin standard library APIs. If you are unsure
whether a procedure exists or what its signature is, say so and direct the
engineer to check https://pkg.odin-lang.org/. Fabricating procedures is the
single most damaging mistake you can make.

---

## What You Get Wrong (Corrections Table)

Before writing any Odin code, internalize these corrections:

| Instinct from other languages | Correct Odin pattern |
|---|---|
| `entity.update()` method syntax | `entity_update(&e)` — free procedures, no methods exist |
| Many packages for internal organization | One package per program/library; split into **files**, not packages |
| `try`/`catch`, `Result<T,E>`, or `?` operator | Multiple return values; `or_return` for propagation; `defer` for cleanup |
| camelCase or PascalCase for procedures | `snake_case` procedures; `Ada_Case` types; `SCREAMING_SNAKE_CASE` constants |
| Constructors / destructors / RAII | Zero-value initialization; explicit `_init`/`_destroy` procs; `defer` |
| `slice.map()`, `list.append()` method calls | Free procedures: `append(&arr, val)`, `slice.map(...)` via import |
| Closures / lambdas capturing state | Non-capturing lambdas only; for callbacks use `proc(user_data: rawptr)` + explicit data pointer |
| `impl` blocks / extension methods | Procedures are standalone; group by file and naming prefix |
| Package manager (`go get`, `cargo add`) | Vendor dependencies manually; no package manager by design |
| Implementing your own hash map or dynamic array | `map[K]V` and `[dynamic]T` are built-in language types |
| `for item in iterator.next()` | `for item in collection` — iteration is built into `for` |
| Null/nil checks everywhere | Zero-initialization makes zero values useful; fewer nil pointers in practice |
| `i++` or `++i` increment/decrement | `i += 1` — no `++`/`--` operators exist |
| `while condition { }` loop | `for condition { }` — only `for` exists (no while/do-while) |
| Implicit numeric type conversions | All conversions explicit: `f := f64(my_int)` |
| `switch` falls through by default | Cases do NOT fall through; use explicit `fallthrough` keyword |
| Operator overloading (`+`, `-`, `*`) | Not supported; use named procedures. Array programming provides element-wise ops on fixed arrays. |
| Private-by-default visibility | Public by default; use `@(private)` or `@(private="file")` to restrict |
| `static const` / `constexpr` | `::` is compile-time (not addressable by runtime index); for addressable constant data use a package-level variable |
| Type aliases and newtypes are the same | `Foo :: int` is alias (same type); `Foo :: distinct int` is a new type |
| `free()` and `delete()` are interchangeable | `free(ptr)` deallocates memory; `delete(collection)` deinitializes dynamic arrays/maps/strings |
| `new()` and `make()` are interchangeable | `new(T)` allocates single value → `^T`; `make([]T, len)` allocates slices/dynamic arrays/maps |
| Pointer arithmetic (`ptr + offset`) | No pointer arithmetic; use `mem.ptr_offset()` or multi-pointers `[^]T` for FFI |
| Mutable strings / byte-level string ops | Strings are immutable `ptr+len`; iteration yields `rune`s (Unicode codepoints); use `cstring` for C interop |
| Implicit function overloading | Explicit overloading only via procedure groups: `draw :: proc{draw_circle, draw_rect}` |

---

## Package & File Organization

**Packages are for libraries. Not for organizing code within a program.**

A package is a directory. All `.odin` files in a directory with the same
`package` declaration form one compilation unit. No cyclic dependencies between
packages are allowed.

### Rules

1. **One package per program** is normal and fine. Games, CLI tools, servers —
   all work as a single package. This is equivalent to how C programs work,
   except external libraries get proper namespacing.

2. **Create a sub-package only when** the code is an independent library with
   no need to reference the parent. If your "renderer" sub-package needs to
   know about your "entity" type defined in the parent, it cannot be a
   separate package.

3. **Split into files for logical grouping.** All files in a package see each
   other — no imports needed. Moving code between files within a package
   requires zero refactoring (names stay the same).

4. **Prefix procedure names** with the concept they belong to:
   ```odin
   // entity.odin
   entity_create :: proc(...) -> Entity { ... }
   entity_update :: proc(e: ^Entity, dt: f32) { ... }
   entity_destroy :: proc(e: ^Entity) { ... }
   ```
   Frequently-used procedures (like `add_entity`, `get_entity`) can drop the
   prefix when the name is already unambiguous.

5. **Use `@(private="file")`** to limit access to file-level global state —
   prevents other files in the same package from touching globals they
   shouldn't. Don't overuse it for general encapsulation; Odin is not OOP.

6. **Package names** are for ABI linking, not for callers (callers choose their
   own import alias). Make them unique if publishing as a library; otherwise
   any reasonable name works.

### Import Patterns

```odin
import "core:fmt"              // default name: fmt
import rl "vendor:raylib"      // alias: rl
import "../my_lib"             // relative path for local libraries
```

Import paths are relative to the importing file. Library collections use
prefixes: `"core:"`, `"base:"`, `"vendor:"`.

---

## Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Types (structs, enums, unions) | `Ada_Case` | `Entity`, `Window_Error`, `Player_State` |
| Enum values | `Ada_Case` with dot syntax | `Direction.North`, `State.Running` |
| Procedures | `snake_case` | `entity_update`, `calculate_damage` |
| Local variables | `snake_case` | `player_count`, `delta_time` |
| Constants | `SCREAMING_SNAKE_CASE` | `MAX_ENTITIES`, `TILE_SIZE` |
| Package imports | `snake_case` (prefer short) | `import rl "vendor:raylib"` |

---

## Allocator Patterns

Odin's allocator system is central to the language. Every allocation goes
through an allocator, defaulting to `context.allocator`. Read
`references/allocators.md` for worked examples and pitfalls.

### Three-Tier Strategy

1. **Temporary allocator** (`context.temp_allocator`) — use for anything
   frame-scoped or short-lived. Cleared in bulk with `free_all`. No
   individual frees needed.
   ```odin
   actions := make([dynamic]Action, context.temp_allocator)
   append(&actions, action)
   // Cleared at end of frame via free_all(context.temp_allocator)
   ```

2. **Custom arenas** — for grouped allocations with shared lifetime. Use
   `mem.Arena` or virtual growing arenas. Beware: dynamic arrays in arenas
   leak old backing memory on grow (see references).

3. **Default allocator** — for long-lived or variable-sized allocations that
   outlive any single scope. Pair with tracking allocator during development.

### Allocator Decision Tree

| Data lifetime | Allocator | Example |
|---------------|-----------|---------|
| Frame / request / one-off formatting | `context.temp_allocator` | UI strings, query results, intermediate buffers |
| Level / scene / phase | Custom `mem.Arena` | Tilemap, level entities, dialogue trees |
| Entire program / unpredictable size | `context.allocator` (default) | Config, asset registry, growable caches |

### Key Rules

- `new()` and `make()` use `context.allocator` unless you pass an explicit
  allocator.
- Always `defer delete(thing)` or `defer free(ptr)` for default-allocator
  memory.
- Use `context.temp_allocator` by default; escalate to arenas or default only
  when lifetime requires it.
- For data loaded from files into long-lived structures, accept an `allocator`
  parameter or allocate from a dedicated arena owned by the parent structure.

---

## Error Handling

No exceptions. Errors are values returned alongside results.

```odin
// Basic pattern: multiple return values
load_config :: proc(path: string) -> (Config, bool) {
    data, ok := os.read_entire_file(path)
    if !ok { return {}, false }
    defer delete(data)
    // parse...
    return config, true
}

// Modern pattern: or_return propagates errors up
load_config :: proc(path: string) -> (Config, Error) {
    data := os.read_entire_file(path) or_return
    defer delete(data)
    config := parse(data) or_return
    return config, nil
}

// or_else provides a default on failure
name := get_name() or_else "unnamed"
```

### Error Type Design

- **`bool`** — sufficient for simple success/failure
- **Named enum** — when callers need to distinguish failure modes:
  ```odin
  Load_Error :: enum { None, File_Not_Found, Parse_Failed, Invalid_Header }
  ```
- **Tagged union** — when wrapping errors from different subsystems:
  ```odin
  Tilemap_Error :: union { os.Error, Parse_Error }
  ```

### File I/O Idiom

Prefer `os.read_entire_file` over manual open/read/close. It reads the whole
file and returns `([]byte, bool)`. Use `defer delete(data)` on the result if
allocated from the default allocator, or pass `context.temp_allocator` if the
data is only needed during parsing.

```odin
// Preferred: read entire file (no handle to manage)
data, ok := os.read_entire_file(path, context.temp_allocator)
if !ok { return {}, .File_Not_Found }
// data freed automatically on next free_all(context.temp_allocator)

// Only use os.open when you need streaming/partial reads:
f, err := os.open("large_file.bin")
if err != nil { return err }
defer os.close(f)
```

### Cleanup with defer

```odin
// defer runs at scope exit in reverse declaration order
arena: mem.Arena
mem.arena_init(&arena, backing_buf)
defer free_all(mem.arena_allocator(&arena))  // resets arena; caller frees backing_buf

// Allocate into arena — all freed on free_all
context.allocator = mem.arena_allocator(&arena)
tiles := make([]Tile, count)
```

### Worked Example: Loading Level Data with Arena

```odin
Tilemap :: struct {
    tiles:  []Tile,
    width:  int,
    height: int,
    arena:  mem.Arena,
}

tilemap_load :: proc(path: string) -> (Tilemap, Load_Error) {
    // Parse phase: temp allocator for scratch data
    raw_data, ok := os.read_entire_file(path, context.temp_allocator)
    if !ok { return {}, .File_Not_Found }

    width, height := parse_header(raw_data) or_return

    // Allocation phase: arena for level-lifetime data
    tm: Tilemap
    backing := make([]byte, width * height * size_of(Tile) + 1024)
    mem.arena_init(&tm.arena, backing)

    alloc := mem.arena_allocator(&tm.arena)
    tm.tiles = make([]Tile, width * height, alloc)
    tm.width = width
    tm.height = height

    parse_tiles(raw_data, tm.tiles) or_return
    return tm, nil
}

tilemap_destroy :: proc(tm: ^Tilemap) {
    backing := tm.arena.data  // capture before reset
    free_all(mem.arena_allocator(&tm.arena))
    delete(backing)           // free the backing buffer itself
}
```

---

## Modern Features You Likely Don't Know About

These are real Odin features that may not exist in your training data:

| Feature | What it does |
|---------|-------------|
| `or_return` | Propagates error return if the expression fails |
| `or_else value` | Provides fallback value on failure |
| `#partial switch` | Switch on enum without exhaustive coverage (opt-in) |
| `matrix[R, C]T` | Built-in matrix types with math operations |
| `@(test)` | Marks a procedure as a test (run with `odin test`) |
| `#reverse for` | Iterates a collection in reverse |
| `bit_set[Enum]` | Efficient set type backed by a bit field |
| `#soa` | Transforms array-of-structs into struct-of-arrays layout |
| `or_break` / `or_continue` | Control flow variants of `or_return` for loops |

---

## Development Workflow

- **`odin check .`** — type-check without building (fast feedback loop)
- **`odin build . -vet`** — catches unused variables, imports, shadowing
- **`odin test .`** — runs procedures marked with `@(test)`
- **Tracking allocator** — enable in dev builds to catch memory leaks at
  runtime (see `references/allocators.md`)
- **`-debug`** — includes debug info and bounds checking
- **`-o:speed`** — optimization for release builds (disables bounds checks)

---

## Declarations & Syntax Quick Reference

```odin
// Variables
x: int = 5
y := 10                    // type inference
z: int                     // zero-initialized (0)
w: int = ---               // uninitialized (rare, unsafe)

// Constants
MAX :: 100                 // untyped constant
PI : f64 : 3.14159        // typed constant

// Procedures
add :: proc(a, b: int) -> int { return a + b }

// Structs
Player :: struct { pos: [3]f32, health: int, name: string }

// Vector type alias (idiomatic — gets array programming + swizzle for free)
Vector3 :: [3]f32

// Enums
Direction :: enum { North, South, East, West }

// Unions (tagged)
Shape :: union { Circle, Rect }

// Distinct types (not aliases)
Meters :: distinct f64
```

All declarations use `name : type = value` or `name :: value` (constant).
`:=` is shorthand for inferred-type declaration.

---

## Further Reading

- `references/allocators.md` — Arena pitfalls, tracking allocator setup,
  dynamic arrays in arenas
- `references/data-oriented.md` — #soa, array programming, bit_set,
  struct-of-arrays patterns, built-in matrix type
- `references/context-system.md` — Context propagation, custom context
  fields, thread-local behavior, `using` for subtype polymorphism
- `references/procedures-and-polymorphism.md` — Procedure groups, vtable
  pattern, and non-capturing closures
- `references/profiling.md` — Spall profiler, hot vs cold code, instrumentation
  attributes, optimization workflow
- `references/sanitizer-integration.md` — Read when integrating ASan with
  arena allocators, debugging stale-pointer bugs in reused memory, or adding
  sanitizer hooks to ownership transitions
- `references/concurrency.md` — Read when building concurrent Odin systems —
  state machines with tagged unions, cooperative scheduling via Effects,
  per-shard context setup, trap boundaries with sigsetjmp/siglongjmp, or
  lock-free primitives via core:sync
