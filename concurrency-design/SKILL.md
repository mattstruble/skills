---
name: concurrency-design
description: You MUST consult this skill when choosing a concurrency architecture: thread topology (thread-per-core, work-stealing, event loop), unit of concurrency (actors, goroutines, state machines), or inter-component communication model (message passing, channels, shared memory). Also trigger when designing fault isolation boundaries, supervision trees, or backpressure propagation; when scaling a single-threaded design to multi-core; or when choosing between actor vs CSP channel models. NOT for lock primitive implementation, network protocol state machines, database connection pooling, language-specific async runtime config (tokio, asyncio), compute parallelism (SIMD, GPU), or distributed consensus (Raft, Paxos).
---

# Concurrency Design

**Concurrency is an architectural decision, not a library choice.** The model
you pick determines your fault boundaries, your communication patterns, your
latency profile, and how hard the system is to reason about under load. Choose
wrong and no amount of tuning recovers you.

Work through these five questions in order. Each answer constrains the next.

---

## 1. Topology: How Do Threads Map to Cores?

Topology is the first decision because it determines whether threads share
state at all, and what the cost of cross-thread communication is.

| Model | Core idea | Choose when |
|---|---|---|
| **Thread-per-core** | One OS thread per core, shared-nothing. Cross-core work is explicit messaging. | Latency-sensitive, high-throughput I/O (databases, proxies). Seastar/ScyllaDB. |
| **Work-stealing** | Thread pool; idle threads steal tasks from busy threads' queues. | CPU-bound work with variable task sizes. Go runtime, Tokio, Java ForkJoinPool. |
| **Event loop** | Single-threaded I/O multiplexing (epoll/kqueue/io_uring). | I/O-bound services where compute per request is minimal. Node.js, nginx. |
| **Thread pool** | Fixed-size pool dispatching work items from a shared queue. | Simple bounded concurrency, legacy systems. Classic Java ExecutorService. |

**Thread-per-core** eliminates lock contention by construction — each shard
owns its data exclusively. Cross-shard operations require explicit messages,
which is a feature: the communication cost is visible. The weakness is load
imbalance: a hot shard can't borrow capacity from an idle one without
coordination.

**Work-stealing** gives you automatic load balancing at the cost of
unpredictable latency. A task migrated to another thread loses its cache
warmth. Under contention, the steal mechanism itself becomes a bottleneck.

**Event loop** is simple for I/O-heavy code but doesn't scale to multiple
cores without clustering (multiple processes or worker threads). Any
CPU-intensive work blocks the loop.

See `references/topology.md` for decision matrix, trade-off analysis, and
worked examples.

---

## 2. Unit of Concurrency: What's Your Fault Boundary?

Once you've chosen a topology, decide what the *unit* of concurrent execution
is. This is also your fault boundary — what crashes independently.

| Unit | Fault boundary | Scheduling | When to choose |
|---|---|---|---|
| **Actors / isolates** | Per-actor — crash doesn't corrupt neighbors | Cooperative mailbox; sequential per actor | Long-lived stateful entities, maximum fault isolation |
| **OS threads** | Process — a thread crash (SIGSEGV) kills the process unless trapped | Preemptive, OS-managed | Legacy systems, FFI-heavy code, blocking I/O you can't avoid |
| **Green threads / goroutines** | Runtime-dependent — Go panics kill the program unless recovered | M:N, cooperative or preemptive (Go 1.14+) | High concurrency with cheap creation; accept weaker fault isolation |
| **Coroutines** | Caller — no isolation | Cooperative, explicit yield points | I/O-bound code in an existing async ecosystem |
| **State machine encoding** | Per-struct — explicit state, no hidden frames | Driven by event loop or scheduler | Coroutine-like behavior without colored functions or runtime complexity |

**Actors / isolates**: independent units with private state, communicating
only via messages. Process messages sequentially from a mailbox. No shared
memory. A crash in one actor doesn't corrupt another's state. Erlang
processes, Tina isolates, Pony actors.

**OS threads**: preemptively scheduled, share address space. Fault boundary
is the process, not the thread — a thread crash (SIGSEGV) typically kills the
process unless you trap it explicitly.

**Green threads / goroutines**: M:N scheduling, cooperative or preemptive
depending on runtime. Go goroutines are preemptive since Go 1.14. Cheap to
create; fault boundary depends on whether the runtime provides supervision
(Go does not — a panicking goroutine kills the program unless recovered).

**Coroutines**: cooperative suspension at explicit yield points. No hidden
preemption. The "colored function" problem (async/await propagation) is a
symptom of coroutines leaking into the type system.

**State machine encoding**: instead of suspending mid-function, encode
progress as an explicit state enum. The scheduler calls back with the next
event; the state machine transitions and returns. No hidden stack frames, no
colored functions, no implicit suspension points. This is the preferred
pattern when you want coroutine-like behavior without the runtime complexity.

See `references/actors-and-state-machines.md` for the actor model, state
machine encoding, cooperative scheduling via effects, and comparisons with
CSP channels and async/await.

---

## 3. Communication: How Do Units Exchange Data?

| Mechanism | Model | When to use |
|---|---|---|
| **Message passing** | Async fire-and-forget to a mailbox | Actors, cross-shard work, decoupled producers |
| **Channels (CSP)** | Synchronous or buffered rendezvous | Go-style pipelines, backpressure via bounded buffers |
| **Shared memory + locks** | Mutex-protected critical sections | Small, infrequent shared state; well-understood contention |
| **Lock-free structures** | SPSC/MPMC ring buffers, CAS-based queues | High-throughput, latency-sensitive paths; known producer/consumer counts |

**Default to message passing.** It makes data ownership explicit and
eliminates data races by construction. Shared memory is appropriate when the
shared data is small, access is infrequent, and the contention is understood.

**Lock-free structures** are not simpler than locks — they're harder to get
right and harder to reason about. Use them on hot paths where profiling shows
lock contention is the bottleneck, and only with well-tested implementations
(LMAX Disruptor, Rigtorp SPSC, Vyukov MPMC). Rolling your own is a bug.

**Channels provide backpressure** when bounded. A full channel blocks the
producer, which propagates pressure upstream. This is a feature. Unbounded
queues hide backpressure and cause unbounded memory growth under load.

See `references/lock-free-structures.md` for SPSC ring buffer implementation
details (Rigtorp cached-index optimization, Snellman unmasked indices), MPMC
patterns (LMAX Disruptor, Vyukov), and when to use each.

---

## 4. Fault Isolation: What Crashes Independently?

Design for failure before designing for success. The question is not "how do
I prevent crashes?" but "when this unit crashes, what else goes down with it?"

**Architectural constraint**: every unit of concurrency should be cheap to
restart, own isolated state, and sit under a supervisor that decides whether
to restart it, escalate, or shut down.

**Supervision strategies** (Erlang/OTP model):
- *One-for-one*: restart only the crashed child. Use when children are independent.
- *One-for-all*: restart all children when one crashes. Use when children share invariants.
- *Rest-for-one*: restart the crashed child and all children started after it. Use for ordered pipelines.

**Recovery budgets**: rate-limit restarts. After N crashes in T seconds,
escalate to the next supervision level. This prevents infinite crash loops
from consuming all resources.

**"Let it crash"** is a design philosophy, not an excuse for sloppy code. It
works only when: (1) restart is cheap and fast, (2) state is isolated and
recoverable, (3) a supervisor is watching. Without all three, "let it crash"
is just "let it fail silently."

See `references/fault-isolation.md` for trap boundaries, supervision trees,
recovery budgets, guard pages, and designing for simulation testability.

---

## 5. Message Patterns: How Do Units Coordinate?

Within your chosen communication mechanism, pick the right interaction
pattern for each operation.

| Pattern | Shape | Use for |
|---|---|---|
| **Fire-and-forget** | Send, don't wait | Logging, metrics, non-critical notifications |
| **Request-reply** | Send, await response with timeout | Any operation where the caller needs a result |
| **Pub/sub** | One sender, many receivers | Events, state change notifications |
| **Scatter-gather** | Fan out to N, collect M responses | Parallel queries, redundant reads |

**Every request-reply must have a mandatory timeout.** A missing timeout
converts a transient failure into a permanent hang. The timeout is not an
optimization — it is a correctness requirement.

**Separate control plane from data plane.** Control messages (configuration
changes, shutdown signals, health checks) should travel on a separate channel
from data messages. A congested data plane must not block control messages.
This is how you drain a system gracefully under load.

**Backpressure propagates upstream.** When a downstream consumer is slow, the
pressure should flow back to the producer, not accumulate in an unbounded
buffer. Bounded channels, bounded mailboxes, and explicit flow control are
the mechanisms. Design for this from the start — retrofitting backpressure is
painful.

---

## Worked Example: Go Pipeline with Fault Isolation

A Kafka→Postgres pipeline — four stages, buffered channels, worker pool. This
example shows how the five decisions interact.

**Topology**: work-stealing (Go's M:N scheduler). Correct for mixed I/O + CPU
with variable task sizes. No topology change needed.

**Fault boundary**: goroutines have no fault boundary by default — an
unrecovered panic kills the process. Fix: `defer/recover` in every worker
goroutine, supervised by a goroutine that restarts crashed workers.

```go
// Worker with trap boundary
func runWorker(id int, in <-chan Event, out chan<- Result, faults chan<- int) {
    defer func() {
        if r := recover(); r != nil {
            log.Printf("worker %d panic: %v\n%s", id, r, debug.Stack())
            faults <- id  // signal supervisor to restart
        }
    }()
    for event := range in {
        out <- process(event)
    }
}

// Supervisor: one-for-one restart with recovery budget
// one-for-one because workers are independent — a crash in one doesn't
// affect the others. Budget: 5 restarts in 30s; exceed → escalate.
func supervise(ctx context.Context, count int, in <-chan Event, out chan<- Result) {
    faults := make(chan int, count)
    history := make([][]time.Time, count)
    for i := range count { go runWorker(i, in, out, faults) }
    for {
        select {
        case <-ctx.Done(): return
        case id := <-faults:
            if exceedsBudget(history, id, 5, 30*time.Second) {
                cancelPipeline()  // escalate: budget exceeded
                return
            }
            time.AfterFunc(backoff(history[id]), func() {
                go runWorker(id, in, out, faults)
            })
        }
    }
}
```

**Communication**: CSP channels. Bounded (capacity 1000) — backpressure
propagates upstream automatically: slow Postgres → aggregator blocks →
workers block → Kafka consumer stops reading. This is correct; don't fight it.

**Supervision strategy**: **one-for-one** — workers are independent. If the
aggregator and writer shared invariants, use **one-for-all**.

**Control vs data plane**: shutdown signal (`ctx.Done()`) travels on a
separate path from data channels. Every stage has a `select` watching both.
A congested data channel must not block a shutdown signal.

```go
// Each stage: ctx.Done() is a separate select arm, not in the data path
for {
    select {
    case <-ctx.Done(): flush(); return   // control plane
    case event := <-in: process(event)  // data plane
    }
}
```

**Graceful drain**: close channels in pipeline order. Consumer closes its
output when done → workers drain → aggregator closes its output → writer
drains. `sync.WaitGroup` lets main wait for complete drain.

---

## Decision Checklist

1. **Topology first**: thread-per-core, work-stealing, event loop, or thread pool?
2. **Fault boundary**: what is the unit that crashes independently?
3. **Communication**: message passing, channels, shared memory, or lock-free?
4. **Supervision**: who restarts what, under what conditions?
   - *One-for-one*: independent workers. *One-for-all*: shared invariants. *Rest-for-one*: ordered pipeline.
5. **Message patterns**: fire-and-forget, request-reply (with timeout!), pub/sub, scatter-gather?
6. **Control vs data plane**: are they separated? Control signals must not be blocked by data congestion.
7. **Backpressure**: does pressure propagate upstream, or does it accumulate?


