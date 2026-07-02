# Topology Reference

Read this when choosing between thread-per-core, work-stealing, event loop,
and thread pool. Covers trade-offs, decision criteria, and real-world
implementations for each model.

---

## Thread-Per-Core

**Model**: One OS thread is pinned to each CPU core. Each thread owns a
partition of the data (a "shard"). Cross-shard operations require explicit
message passing — no thread touches another's data directly.

**Canonical implementations**: Seastar (C++, used by ScyllaDB), Tina (Odin).

### How it works

At startup, the application creates N threads (one per core) and pins each to
a specific CPU using `pthread_setaffinity_np` or equivalent. Each thread runs
its own event loop, owns its own allocator, and processes its own queue of
work. When work arrives that belongs to a different shard (e.g., a network
connection hashed to shard 3 receives a request that needs data from shard 7),
the handling thread sends a message to shard 7's queue and either waits for a
reply or registers a continuation.

### Strengths

- **Predictable latency**: no lock contention, no cache line bouncing between
  cores. A thread's working set stays in L1/L2 cache because no other thread
  touches it.
- **No lock contention**: shared-nothing means no mutexes on the hot path.
  The only synchronization is the cross-shard message queue, which can be a
  lock-free SPSC ring (one per sender/receiver pair).
- **Cache-friendly**: data locality is maximized. The thread that owns the
  data is the thread that processes it.
- **Deterministic resource usage**: each shard's memory footprint is bounded
  and predictable.

### Weaknesses

- **Load imbalance**: if one shard receives 80% of the traffic, it saturates
  while others idle. Mitigation requires work-stealing or explicit rebalancing,
  which reintroduces coordination complexity.
- **Cross-shard coordination complexity**: operations that span multiple shards
  require scatter-gather patterns, distributed transactions, or saga-style
  coordination. This is manageable but requires discipline.
- **Harder to retrofit**: existing codebases with shared mutable state cannot
  be converted to thread-per-core without significant refactoring.

### When to choose

- Latency-sensitive services where tail latency matters (databases, proxies,
  game servers)
- High-throughput I/O where lock contention would otherwise dominate
- Systems where data can be partitioned by a natural key (user ID, connection
  ID, session ID)
- New systems where you can design shared-nothing from the start

### Seastar / ScyllaDB example

ScyllaDB (a Cassandra-compatible database) uses Seastar's thread-per-core
model. Each shard owns a subset of the token ring. A query arriving on shard 2
that needs data from shard 5 sends a message to shard 5's queue. The result
comes back as a future. This architecture allows ScyllaDB to sustain millions
of operations per second with sub-millisecond p99 latency on commodity hardware
— performance that would be impossible with a traditional thread-pool-plus-locks
design.

---

## Work-Stealing

**Model**: A thread pool where each thread has its own work queue. When a
thread exhausts its queue, it "steals" tasks from the tail of another thread's
queue. Work is submitted to any thread's queue (or a global queue).

**Canonical implementations**: Go runtime, Tokio (Rust), Java ForkJoinPool,
Rayon (Rust).

### How it works

Each worker thread maintains a double-ended queue (deque). New tasks are pushed
to the local thread's deque. The thread pops tasks from its own deque's front.
When the local deque is empty, the thread picks a random victim thread and
steals from the *back* of that thread's deque. This LIFO/FIFO split reduces
contention: the owner operates on the front (LIFO, cache-warm), stealers
operate on the back (FIFO, older tasks).

### Strengths

- **Automatic load balancing**: idle threads automatically pick up work from
  busy threads. No manual partitioning required.
- **Simpler programming model**: callers don't need to know which thread will
  execute their task. Submit work, get a result.
- **Good for recursive decomposition**: fork-join patterns (divide work into
  subtasks, join results) map naturally onto work-stealing. The spawning thread
  processes its own half while a stealer picks up the other.

### Weaknesses

- **Unpredictable latency under contention**: when many threads are stealing
  simultaneously, the steal mechanism itself becomes a bottleneck. Cache
  pollution from task migration adds latency variance.
- **Cache pollution**: a stolen task runs on a different core than where its
  data was last touched. The new core must fetch data from L3 or main memory.
- **Harder to reason about ordering**: tasks may execute in any order across
  threads. If your tasks have implicit ordering assumptions, work-stealing
  will expose them.

### When to choose

- CPU-bound workloads with variable task sizes (ray tracing, compilation,
  data processing)
- Systems where work cannot be cleanly partitioned upfront
- When you want the runtime to handle load balancing automatically
- When average throughput matters more than tail latency

### Go runtime example

Go's scheduler uses a work-stealing design. Each OS thread (P) has a local
run queue of goroutines. When the local queue is empty, the P steals from
another P's queue or the global queue. This is why Go programs scale well
across cores without explicit thread management — the runtime handles
distribution automatically.

---

## Event Loop

**Model**: A single thread multiplexes I/O events using the OS's I/O
notification mechanism (epoll on Linux, kqueue on BSD/macOS, io_uring for
newer Linux). When an I/O event is ready, the loop dispatches a callback or
resumes a coroutine/future.

**Canonical implementations**: Node.js (libuv), nginx, Redis, Python asyncio.

### How it works

The loop calls `epoll_wait` (or equivalent) with a list of file descriptors to
watch. The OS blocks until at least one descriptor is ready. The loop then
dispatches the ready events to their registered handlers. Handlers must return
quickly — any blocking operation stalls the entire loop.

io_uring (Linux 5.1+) improves on epoll by batching syscalls and supporting
true async I/O for disk operations, not just network I/O.

### Strengths

- **Simple mental model for I/O-bound code**: one thread, one execution
  context. No locks needed for shared state within the loop.
- **Low overhead for many idle connections**: a single thread can manage
  thousands of open connections that are mostly idle (the C10K problem).
- **No thread safety concerns within the loop**: all handlers run on the same
  thread, so in-loop data structures need no synchronization.

### Weaknesses

- **Compute blocks the loop**: a CPU-intensive handler (image processing,
  cryptography, JSON parsing of large payloads) stalls all other pending I/O.
  The fix is to offload compute to a thread pool, which reintroduces
  coordination.
- **Doesn't scale to multiple cores without clustering**: a single event loop
  uses one core. To use N cores, you run N processes (nginx's worker model) or
  N threads each with their own loop (which is effectively thread-per-core).
- **Callback hell / colored functions**: deep async chains are hard to read
  and debug. Async/await syntax helps but doesn't eliminate the underlying
  complexity.

### When to choose

- I/O-bound services where compute per request is minimal (reverse proxies,
  static file servers, WebSocket hubs)
- When simplicity of the single-threaded model outweighs multi-core scaling
- When you'll cluster at the process level (nginx worker processes)

---

## Thread Pool

**Model**: A fixed number of threads draw work items from a shared queue.
Callers submit work to the queue; any available thread picks it up.

**Canonical implementations**: Java `ExecutorService`, Python
`ThreadPoolExecutor`, C++ `std::async` with a pool.

### How it works

A bounded queue holds pending work items. Worker threads block on the queue
when it's empty. When a work item arrives, one thread wakes, dequeues it, and
executes it. The pool size is fixed (or bounded), preventing unbounded thread
creation.

### Strengths

- **Simple**: easy to understand and implement. Well-understood semantics.
- **Bounded resource usage**: fixed thread count means bounded memory and
  context-switch overhead.
- **Broad applicability**: works for any workload that can be expressed as
  independent tasks.

### Weaknesses

- **Context switch overhead**: threads block on the shared queue, causing
  frequent context switches under load.
- **Lock contention on shared queue**: all threads contend for the same queue
  under high submission rates. Mitigated by per-thread queues (which is
  work-stealing).
- **No automatic load balancing**: if tasks have variable duration, some
  threads may finish early and sit idle while others are overloaded.
- **Shared state requires explicit synchronization**: threads share an address
  space, so any shared data needs locks or atomic operations.

### When to choose

- Simple bounded concurrency for I/O-bound tasks (HTTP clients, database
  connection pools)
- Legacy systems where the threading model is already established
- When work-stealing's complexity isn't justified by the workload

---

## Decision Matrix

| Requirement | Recommended topology | Reason |
|---|---|---|
| Sub-millisecond p99 latency | Thread-per-core | No lock contention, cache-local execution |
| Maximum throughput, variable task sizes | Work-stealing | Automatic load balancing |
| Thousands of idle connections, minimal compute | Event loop | Low overhead per connection |
| Simple bounded concurrency | Thread pool | Easiest to implement and reason about |
| Data naturally partitioned by key | Thread-per-core | Shard by key, eliminate cross-shard ops |
| Recursive decomposition (fork-join) | Work-stealing | Native fit for the model |
| Single-core compute with I/O | Event loop | No multi-core needed |
| Mixed I/O + CPU-heavy tasks | Work-stealing + offload | Steal for I/O, dedicated pool for CPU |

---

## Hybrid Patterns

Real systems often combine topologies:

**Thread-per-core for I/O + work-stealing for CPU**: Each shard handles its
own I/O. CPU-intensive work (compression, encryption, serialization) is
dispatched to a separate work-stealing pool. The shard submits work and
registers a continuation; the pool executes and sends the result back.

**Event loop per core**: Run one event loop per core, each handling a subset
of connections. This is nginx's worker model and effectively thread-per-core
with an event loop inside each shard.

**Thread pool with per-thread queues**: Upgrade a basic thread pool to
work-stealing by giving each thread its own queue and adding steal logic.
This is how Java's ForkJoinPool evolved from ExecutorService.

---

## Practical Notes

**Pinning threads to cores** (`pthread_setaffinity_np`, `sched_setaffinity`)
prevents the OS scheduler from migrating threads between cores. This is
essential for thread-per-core to deliver its latency guarantees. Without
pinning, the OS may migrate a thread mid-execution, evicting its cache.

**NUMA awareness**: on multi-socket systems, memory access latency depends on
which socket owns the memory. Thread-per-core designs should pin threads to
cores on the same NUMA node as the memory they access. `numactl` and
`libnuma` provide NUMA-aware allocation.

**Measuring topology impact**: use `perf stat -e cache-misses,cache-references`
to measure cache efficiency. High cache-miss rates under a thread pool often
indicate that migrating to thread-per-core or work-stealing would help.
