# Profiling in Odin

Read this when measuring Odin code performance, identifying hot paths, or
deciding what to optimize. For allocator-related leak detection see
`references/allocators.md` (tracking allocator).

---

## Hot vs Cold Code

Not all code deserves optimization attention. Classify before you profile.

**Cold code** runs once at startup or shutdown: asset loading, config parsing,
arena initialization, factory setup. Optimization is rarely worth the effort
unless the wall-clock time is user-noticeable (e.g., a multi-second load
screen).

**Hot code** runs every frame, every iteration, every request. Nanoseconds
compound: 100 ns × 800×600 pixels × 60 Hz = 2.88 seconds per second of
render time. Even modest improvements here have outsized impact.

```odin
// cold — runs once
init_game(&state)

for !should_quit {
    // hot — runs every frame
    update(&state, dt)
    render(&state)
    free_all(context.temp_allocator)
}

// cold — runs once
shutdown_game(&state)
```

**Rule:** Profile first. Optimize only what the profiler identifies as hot.
Guessing wastes time and often makes code worse.

---

## `core:prof/spall`

Spall is Odin's standard-library profiler. It outputs `.spall` binary trace
files viewable in [Spall-Web](https://gravitymoth.com/spall/spall-web.html)
(free, in-browser, no install).

Package docs: https://pkg.odin-lang.org/core/prof/spall/

Two integration paths:

| Path | When to use |
|------|-------------|
| **Manual scoping** (`SCOPED_EVENT`) | Profile specific procedures or code regions |
| **Auto-instrumentation** (`@(instrumentation_enter/exit)`) | Profile everything; find unknown bottlenecks |

---

## Manual Scoping

Add `spall.SCOPED_EVENT` at the top of any procedure you want to time. The
event is opened on entry and closed automatically at scope exit (it uses
`defer` internally).

```odin
package main

import "core:prof/spall"
import "core:sync"

spall_ctx:    spall.Context
@(thread_local) spall_buffer: spall.Buffer

main :: proc() {
    spall_ctx = spall.context_create("trace.spall")
    defer spall.context_destroy(&spall_ctx)

    buffer_backing := make([]u8, spall.BUFFER_DEFAULT_SIZE)
    defer delete(buffer_backing)

    spall_buffer = spall.buffer_create(
        buffer_backing,
        u32(sync.current_thread_id()),
    )
    defer spall.buffer_destroy(&spall_ctx, &spall_buffer)

    // Mark this procedure in the trace
    spall.SCOPED_EVENT(&spall_ctx, &spall_buffer, #procedure)

    game_loop()
}

game_loop :: proc() {
    spall.SCOPED_EVENT(&spall_ctx, &spall_buffer, #procedure)
    for !should_quit {
        update()
        render()
    }
}
```

`#procedure` is a compile-time constant string containing the current
procedure's name. Pass any string literal if you want a custom label.

`buffer_create` takes an optional `tid` (thread ID) and `pid` (process ID).
Passing `sync.current_thread_id()` ensures correct thread attribution in
multi-threaded traces. The `@(thread_local)` annotation on `spall_buffer` is
the correct pattern for multi-threaded programs — each thread gets its own
buffer; all share one `spall_ctx`.

---

## Automatic Instrumentation

The compiler can insert profiling calls at every Odin procedure boundary when
you define procedures with `@(instrumentation_enter)` and
`@(instrumentation_exit)`. The signatures are mandated by the compiler:

```odin
package main

import "base:runtime"
import "core:prof/spall"
import "core:sync"

spall_ctx:    spall.Context
@(thread_local) spall_buffer: spall.Buffer

@(instrumentation_enter)
spall_enter :: proc "contextless" (
    proc_address, call_site_return_address: rawptr,
    loc: runtime.Source_Code_Location,
) {
    spall._buffer_begin(&spall_ctx, &spall_buffer, "", "", loc)
}

@(instrumentation_exit)
spall_exit :: proc "contextless" (
    proc_address, call_site_return_address: rawptr,
    loc: runtime.Source_Code_Location,
) {
    spall._buffer_end(&spall_ctx, &spall_buffer)
}
```

**Requirements:**
- Must be `"contextless"` — these run before the Odin context is set up
- Signature is fixed; the compiler enforces it
- `spall._buffer_begin` / `spall._buffer_end` are internal procedures
  (underscore prefix); they are the correct API for instrumentation callbacks

**Warnings:**
- Generates massive trace files quickly — profile 1–2 seconds at most
- Every procedure call has overhead; absolute timings read slightly worse
  than reality; use for relative comparisons, not wall-clock budgets
- Disable before shipping; leave the `main` setup behind a `when ODIN_DEBUG`
  guard

```odin
when ODIN_DEBUG {
    spall_ctx = spall.context_create("trace.spall")
    // ... buffer setup ...
}
```

---

## Spall-Web Viewer

Open https://gravitymoth.com/spall/spall-web.html and drag in the `.spall`
file. No account, no install.

| Panel | What to look at |
|-------|----------------|
| Flame graph (top) | Call hierarchy; wide bars are slow callers |
| Per-procedure table (bottom) | **Self time** — time spent in the procedure itself, excluding callees |
| Thread rows | Identify which thread is the bottleneck |

**Self time** is the number to optimize. A procedure with high total time but
low self time is slow because of what it calls, not what it does itself.

Trace file size is the constraint. Keep traces short (1–2 seconds of
representative workload). Longer traces are slow to open and hard to navigate.

---

## Optimization Patterns Found by Profiling

### Per-element API calls

A function that takes 100 ns each becomes 60 ms when called for every pixel
of an 800×600 frame at 60 Hz. The fix: render to a buffer once, blit at frame
end.

```odin
// SLOW: one API call per pixel
for y in 0..<height {
    for x in 0..<width {
        rl.DrawPixel(i32(x), i32(y), color)
    }
}

// FAST: write to backing image, update texture once per frame
rl.ImageDrawPixel(&backing_image, i32(x), i32(y), color)
// ... (all pixels written) ...
rl.UpdateTexture(texture, raw_data(backing_image.data))
rl.DrawTexture(texture, 0, 0, rl.WHITE)
```

### Cache misses on field iteration

When profiling shows a hot loop touching only a subset of struct fields,
consider `#soa` layout (see `data-oriented.md`). SoA groups same-typed fields
together, so iterating positions doesn't pull health/color/etc. into cache.

### Modulo on power-of-2 sizes

`x % 64` compiles to a division. `x & 63` is a single bitwise AND. For any
power-of-2 modulus `N`, replace `x % N` with `x & (N - 1)`.

```odin
// Before
idx := write_head % RING_SIZE   // RING_SIZE = 64

// After (RING_SIZE must be a power of 2)
idx := write_head & (RING_SIZE - 1)
```

### Don't optimize cold code

Startup time is cold code. Unless the load screen is user-noticeable (> ~0.5s),
leave it alone. Profiler time is better spent on the hot loop.

---

## Workflow

1. **Get something working first.** Never profile code that isn't correct.
2. **Add Spall setup** in `main` behind a `when ODIN_DEBUG` guard.
3. **Run a representative sample** — 1–2 seconds of typical workload, not a
   synthetic benchmark.
4. **Open in Spall-Web.** Sort the per-procedure table by self time descending.
5. **Find the top 1–3 self-time procedures.** Those are your targets.
6. **Optimize one thing.** Re-profile. Confirm the improvement. Find the next
   bottleneck.
7. **Repeat** until you hit your performance target or diminishing returns.

Profiling after each change is non-negotiable. Optimizations interact; what
helped before may no longer be the bottleneck.

---

## Reference

| Resource | URL |
|----------|-----|
| `core:prof/spall` package docs | https://pkg.odin-lang.org/core/prof/spall/ |
| Spall-Web viewer | https://gravitymoth.com/spall/spall-web.html |
| Worked renderer example (Part XI) | https://marianpekar.com/blog/software-renderer-in-odin-from-scratch-part-xi |
