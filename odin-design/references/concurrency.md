# Concurrency Patterns in Odin

Read this reference when building concurrent Odin systems — state machines,
cooperative scheduling, per-shard context setup, trap boundaries, or
lock-free primitives. For architectural decisions (topology, fault boundaries,
message patterns), read the language-agnostic `concurrency-design` skill first.

---

## State Machine Encoding with Tagged Unions

Odin's tagged unions are the natural encoding for state machines. Instead of
suspending mid-function (coroutines) or blocking a thread (async I/O), encode
progress as an explicit state value. The scheduler calls your handler with the
next event; the handler transitions and returns. No hidden stack frames.

```odin
// Connection state machine for a TCP server
Conn_State :: union {
    Connecting,
    Reading,
    Processing,
    Responding,
    Closed,
}

Connecting  :: struct { addr: string }
Reading     :: struct { buf: []byte, read: int }
Processing  :: struct { request: []byte }
Responding  :: struct { response: []byte, sent: int }
Closed      :: struct { reason: string }

Conn :: struct {
    state: Conn_State,
    fd:    int,
}

// Handler: called once per event, returns next state
conn_handle :: proc(c: ^Conn, event: IO_Event) {
    switch &s in c.state {
    case Connecting:
        if event.kind == .Connected {
            c.state = Reading{buf = make([]byte, 4096)}
        } else {
            c.state = Closed{reason = "connect failed"}
        }
    case Reading:
        s.read += copy(s.buf[s.read:], event.data)
        if request_complete(s.buf[:s.read]) {
            c.state = Processing{request = s.buf[:s.read]}
        }
    case Processing:
        resp := build_response(s.request)
        c.state = Responding{response = resp}
    case Responding:
        s.sent += write(c.fd, s.response[s.sent:])
        if s.sent >= len(s.response) {
            c.state = Closed{reason = "done"}
        }
    case Closed:
        // terminal — scheduler removes this connection
    }
}
```

### `#partial switch` for Sparse Transitions

When a handler only cares about a subset of states, use `#partial switch`.
Without `#partial`, the compiler enforces exhaustive matching — add a new
state variant and every switch must handle it. With `#partial`, unhandled
variants fall through silently.

```odin
// Only handle states where I/O is pending
#partial switch s in c.state {
case Reading:
    poll_read(c.fd)
case Responding:
    poll_write(c.fd)
// Connecting, Processing, Closed: no I/O to poll
}
```

Use exhaustive switches for the main dispatch (catches new variants at
compile time). Use `#partial` for secondary passes (polling, cleanup) where
handling every variant would be noise.

### Contrast with Coroutines

Coroutines suspend mid-function, hiding state in the call stack. This makes
them hard to inspect, serialize, or migrate. State machine encoding makes
every suspension point explicit: the state value IS the suspended computation.
You can log it, checkpoint it, or move it between threads without special
runtime support.

### When to Use

- Any handler that progresses through phases (connect → read → process → respond)
- Protocol parsers, request lifecycles, game entity AI
- Anywhere you'd reach for a coroutine but want debuggability

### When NOT to Use

- Deeply recursive algorithms (tree traversal, parsers with backtracking) —
  state machines for these are awkward; use explicit stacks instead
- One-shot computations with no meaningful intermediate states

---

## Effects as Yield Types for Cooperative Scheduling

Instead of async/await (which colors every function in the call chain), use
an Effect tagged union as the return type of handlers. The handler returns an
Effect describing what it needs next; the scheduler acts on it and calls back.
No colored functions. No runtime. The scheduler is the only code that loops.

```odin
// Effect variants — what a handler can request from the scheduler
Effect :: union {
    Effect_Receive,   // wait for next message
    Effect_Call,      // request-reply with timeout
    Effect_Spawn,     // create a new isolate
    Effect_Crash,     // intentional fault (let it crash)
    Effect_Done,      // handler is finished
}

Effect_Receive :: struct {}
Effect_Call    :: struct { target: Isolate_Id, msg: Message, timeout_ms: int }
Effect_Spawn   :: struct { proc_fn: proc(rawptr) -> Effect, data: rawptr }
Effect_Crash   :: struct { reason: string }
Effect_Done    :: struct {}

// Handler signature: called once per message, returns what to do next
Handler_Proc :: #type proc(isolate: ^Isolate, msg: Message) -> Effect

// Minimal scheduler loop
scheduler_run :: proc(s: ^Scheduler) {
    for {
        isolate, msg, ok := scheduler_next_message(s)
        if !ok { break }

        effect := isolate.handler(isolate, msg)

        switch e in effect {
        case Effect_Receive:
            // handler is waiting — leave it in the mailbox queue
        case Effect_Call:
            scheduler_send(s, e.target, e.msg)
            scheduler_register_reply(s, isolate, e.timeout_ms)
        case Effect_Spawn:
            child := isolate_create(e.proc_fn, e.data)
            scheduler_add(s, child)
        case Effect_Crash:
            isolate_teardown(isolate, e.reason)
            supervisor_notify(s, isolate.id, e.reason)
        case Effect_Done:
            isolate_teardown(isolate, "done")
        }
    }
}
```

### Why This Beats async/await

`async/await` propagates through the type system: every function that calls
an async function must itself be async. Effects don't propagate — a handler
returns an Effect value, and only the scheduler interprets it. Regular
procedures called from the handler remain regular procedures.

```odin
// This is a plain proc — no async annotation needed
parse_request :: proc(data: []byte) -> (Request, bool) {
    // ... pure computation, no I/O
    return req, true
}

// Handler calls it normally, then returns an Effect
my_handler :: proc(isolate: ^Isolate, msg: Message) -> Effect {
    req, ok := parse_request(msg.data)
    if !ok { return Effect_Crash{reason = "bad request"} }
    // ... process req
    return Effect_Receive{}
}
```

### When to Use

- Building a scheduler or actor framework from scratch
- Systems where you want zero-cost cooperative scheduling without a runtime
- When you need to serialize or inspect "what is this handler waiting for"

### When NOT to Use

- When you need true parallelism within a single handler (use OS threads)
- Simple single-threaded programs — the scheduler overhead isn't worth it

---

## Context System for Per-Shard/Per-Isolate State

Odin's implicit context is value-typed and stack-propagated. Override it at
shard initialization and every procedure called from that shard inherits the
override automatically — no parameter threading required.

```odin
Shard_State :: struct {
    id:      int,
    metrics: ^Metrics,
    routes:  map[string]Handler_Proc,
}

// Called once per shard thread at startup
shard_init :: proc(shard_id: int) {
    // Per-shard arena: all allocations within this shard use this memory
    arena_backing := make([]byte, 64 * 1024 * 1024)  // 64 MiB per shard
    arena: mem.Arena
    mem.arena_init(&arena, arena_backing)
    context.allocator = mem.arena_allocator(&arena)

    // Per-shard scratch space for handler invocations
    scratch_backing := make([]byte, 1 * 1024 * 1024, context.allocator)
    scratch: mem.Arena
    mem.arena_init(&scratch, scratch_backing)
    context.temp_allocator = mem.arena_allocator(&scratch)

    // Shard-local state accessible anywhere in the call tree
    state := new(Shard_State)
    state.id = shard_id
    state.metrics = metrics_create()
    state.routes = make(map[string]Handler_Proc)
    context.user_ptr = state

    shard_run()
}

// Per-handler invocation: reset scratch space between calls
shard_dispatch :: proc(msg: Message) {
    free_all(context.temp_allocator)  // reset scratch for this handler call
    handler := get_handler(msg)
    handler(msg)
    // scratch allocations from handler are now reclaimed
}

// Deep in the call tree — no allocator parameter needed
build_response :: proc(req: Request) -> []byte {
    // Uses context.temp_allocator automatically — shard scratch space
    buf := make([dynamic]byte, context.temp_allocator)
    // ... build response
    return buf[:]
}

// Access shard state without passing it explicitly
get_shard_state :: proc() -> ^Shard_State {
    return cast(^Shard_State)context.user_ptr
}
```

### Shared-Nothing by Construction

Each shard has its own arena allocator. Pointers into shard A's arena are
invalid in shard B. This is enforced by convention (not the type system), but
the context scoping makes violations visible: any allocation that escapes a
shard's context is an explicit `new()` or `make()` call that you can audit.

### When to Use

- Thread-per-core shards where each shard owns its data
- Any system where you want allocator isolation between concurrent units
- Passing shard-local state (routing tables, metrics, caches) without
  threading it through every procedure signature

### When NOT to Use

- Single-threaded programs — the default context is fine
- When shard state needs to be shared across threads (use explicit parameters
  or a shared data structure with proper synchronization)

---

## Trap Boundaries with sigsetjmp/siglongjmp

OS signals (SIGSEGV, SIGBUS, SIGFPE) normally kill the process. With
`sigsetjmp`/`siglongjmp`, you can catch them at a defined boundary, tear down
the faulting isolate, and continue the scheduler loop. This is how you get
Erlang-style "let it crash" semantics in a native process.

```odin
import "core:sys/posix"

// Trap context — one per shard (outer boundary)
Trap_Context :: struct {
    env:   posix.sigjmp_buf,
    valid: bool,
}

@(thread_local)
g_trap: Trap_Context

// Signal handler — called by the OS on fault
@(cold)  // hint: this path is never the hot path
signal_handler :: proc "c" (sig: posix.Signal) {
    if g_trap.valid {
        g_trap.valid = false
        posix.siglongjmp(&g_trap.env, i32(sig))
    }
    // No trap registered — re-raise to get a real crash
    posix.signal(sig, auto_cast posix.SIG_DFL)
    posix.raise(sig)
}

// Install signal handlers at shard startup
trap_install :: proc() {
    posix.signal(.SIGSEGV, signal_handler)
    posix.signal(.SIGBUS,  signal_handler)
    posix.signal(.SIGFPE,  signal_handler)
}

// Dispatch with trap boundary around each isolate call
shard_dispatch_with_trap :: proc(isolate: ^Isolate, msg: Message) -> bool {
    g_trap.valid = true
    sig := posix.sigsetjmp(&g_trap.env, 1)
    if sig != 0 {
        // Landed here via siglongjmp — isolate faulted
        g_trap.valid = false
        isolate_teardown(isolate, "signal fault")
        return false
    }

    // Normal dispatch path
    effect := isolate.handler(isolate, msg)
    g_trap.valid = false
    scheduler_apply_effect(effect)
    return true
}
```

### Nested Trap Levels

Use two levels: outer (shard recovery) and inner (isolate dispatch). The
inner trap catches isolate faults and tears down just that isolate. The outer
trap catches shard-level faults (e.g., a bug in the scheduler itself) and
restarts the entire shard.

```odin
shard_run :: proc() {
    // Outer trap: shard-level recovery
    sig := posix.sigsetjmp(&g_shard_trap.env, 1)
    if sig != 0 {
        log.errorf("shard %d faulted with signal %d — restarting", shard_id(), sig)
        shard_reinit()
        return
    }
    g_shard_trap.valid = true

    for {
        isolate, msg, ok := scheduler_next_message(&g_scheduler)
        if !ok { break }
        // Inner trap: isolate-level recovery
        shard_dispatch_with_trap(isolate, msg)
    }
}
```

### Guard Pages

Allocate guard pages between shard memory regions to turn buffer overflows
into hard faults (SIGSEGV) rather than silent corruption:

```odin
// Allocate shard arena with guard page after it
shard_alloc_with_guard :: proc(size: int) -> []byte {
    page_size := int(posix.sysconf(._PAGESIZE))
    total := size + page_size
    ptr := posix.mmap(nil, uint(total), {.READ, .WRITE},
                      {.PRIVATE, .ANONYMOUS}, -1, 0)
    // Make the last page a guard (no access)
    guard := uintptr(ptr) + uintptr(size)
    posix.mprotect(rawptr(guard), uint(page_size), {})
    return ([^]byte)(ptr)[:size]
}
```

### `@(cold)` for Branch Prediction

Mark recovery procedures with `@(cold)` to tell the compiler this path is
never the hot path. This improves branch prediction for the normal dispatch
path and keeps recovery code out of instruction caches.

```odin
@(cold)
isolate_teardown :: proc(isolate: ^Isolate, reason: string) {
    log.warnf("isolate %d crashed: %s", isolate.id, reason)
    // ... cleanup
}
```

### When to Use

- Scheduler loops that must survive isolate faults (SIGSEGV, SIGFPE)
- Systems where "let it crash" requires the scheduler to keep running
- Any native process that hosts untrusted or user-provided computation

### When NOT to Use

- Simple programs — `sigsetjmp` is complex; don't add it without a real need
- When you can validate inputs before dispatch (prefer that)
- Windows targets — `sigsetjmp`/`siglongjmp` are POSIX; use SEH on Windows

---

## Lock-Free Primitives via core:sync

`core:sync` provides atomic operations with explicit memory ordering. Use
these on hot paths where profiling shows lock contention is the bottleneck.
For algorithmic patterns (SPSC ring, MPMC queue), see
`concurrency-design/references/lock-free-structures.md`.

```odin
import "core:sync"

// Basic atomic operations
counter: i64
sync.atomic_store_explicit(&counter, 0, .Seq_Cst)
val := sync.atomic_load_explicit(&counter, .Acquire)
sync.atomic_add_explicit(&counter, 1, .Relaxed)

// Compare-and-exchange: returns (old_value, swapped)
old, ok := sync.atomic_compare_exchange_weak_explicit(&counter, 0, 1, .Acquire, .Relaxed)
```

### Memory Ordering

| Ordering | Use when |
|---|---|
| `.Relaxed` | Counter increments, statistics — no ordering guarantee needed |
| `.Acquire` | Load that "acquires" data written by a Release store |
| `.Release` | Store that "publishes" data for an Acquire load to see |
| `.Seq_Cst` | Need a total order across all threads — use sparingly (expensive) |

The Acquire/Release pair is the building block for all lock-free communication:
the producer does a Release store on the sequence number; the consumer does an
Acquire load. This guarantees the consumer sees all writes the producer made
before the Release.

### SPSC Ring Buffer

Single-producer, single-consumer ring: the canonical lock-free queue for
thread-per-core systems where one shard sends to another.

```odin
RING_SIZE :: 1024  // must be power of two

// #align(64) aligns the struct to a cache-line boundary.
// Padding between head and tail is what prevents false sharing
// (they're written by different threads and must not share a cache line).
SPSC_Ring :: struct #align(64) {
    buf:  [RING_SIZE]rawptr,
    _pad: [64 - size_of(int)]byte,  // separate head and tail onto different cache lines
    head: int,  // written by consumer
    _pad2:[64 - size_of(int)]byte,
    tail: int,  // written by producer
}

// Producer: returns false if full
spsc_push :: proc(r: ^SPSC_Ring, item: rawptr) -> bool {
    tail := sync.atomic_load_explicit(&r.tail, .Relaxed)
    next := (tail + 1) & (RING_SIZE - 1)
    if next == sync.atomic_load_explicit(&r.head, .Acquire) {
        return false  // full
    }
    r.buf[tail] = item
    sync.atomic_store_explicit(&r.tail, next, .Release)  // publish
    return true
}

// Consumer: returns nil if empty
spsc_pop :: proc(r: ^SPSC_Ring) -> rawptr {
    head := sync.atomic_load_explicit(&r.head, .Relaxed)
    if head == sync.atomic_load_explicit(&r.tail, .Acquire) {
        return nil  // empty
    }
    item := r.buf[head]
    sync.atomic_store_explicit(&r.head, (head + 1) & (RING_SIZE - 1), .Release)
    return item
}
```

### Cache-Line Alignment

False sharing occurs when two threads write to different variables that share
a cache line (64 bytes on x86). Use `#align(64)` on structs written by
different threads, and pad fields to separate hot write targets:

```odin
// Without alignment: head and tail may share a cache line
// Every producer write invalidates the consumer's cache line and vice versa
Bad_Ring :: struct {
    head: int,
    tail: int,
    buf:  [1024]rawptr,
}

// With alignment: head and tail on separate cache lines
Good_Ring :: struct {
    _:    [64]byte `fmt:"-"`,  // ponytail: explicit pad; replace with #align field when Odin adds it
    head: int,
    _:    [56]byte `fmt:"-"`,  // pad to fill cache line
    tail: int,
    _:    [56]byte `fmt:"-"`,
    buf:  [1024]rawptr,
}
```

### When to Use

- SPSC ring between a producer shard and a consumer shard (thread-per-core)
- Metrics counters updated on hot paths (`.Relaxed` add is nearly free)
- Sequence numbers for publish/subscribe patterns

### When NOT to Use

- When a mutex is simpler and profiling shows it's not the bottleneck
- MPMC scenarios without a well-tested implementation — roll your own MPMC
  ring only after reading Vyukov's queue and understanding every ordering
  decision. Use a mutex-protected queue until you have proof you need more.
- Any path that isn't proven hot by profiling

---

## Cross-References

| Topic | Where to read |
|---|---|
| Architectural decisions (topology, fault model, message patterns) | `concurrency-design` skill |
| Actor model, state machine encoding theory, CSP vs async/await | `concurrency-design/references/actors-and-state-machines.md` |
| SPSC/MPMC algorithmic patterns (Rigtorp, Snellman, Vyukov, Disruptor) | `concurrency-design/references/lock-free-structures.md` |
| Supervision trees, recovery budgets, "let it crash" prerequisites | `concurrency-design/references/fault-isolation.md` |
| Odin context system details, thread-local behavior | `odin-design/references/context-system.md` |
| Arena allocators, dynamic arrays in arenas | `odin-design/references/allocators.md` |
