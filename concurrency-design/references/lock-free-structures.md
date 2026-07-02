# Lock-Free Structures

Read this when you need high-throughput, low-latency communication between
concurrent units and profiling has shown that lock contention is the
bottleneck. Covers SPSC ring buffers (with Rigtorp and Snellman optimizations),
MPMC patterns (LMAX Disruptor, Vyukov), cache-line alignment, memory ordering,
and when to use each structure.

**Warning**: lock-free structures are harder to implement correctly than
locks. Use well-tested implementations. The value here is understanding the
design so you can evaluate implementations and apply them correctly — not so
you can write your own from scratch.

---

## When to Use Lock-Free vs Alternatives

Lock-free structures are not the default. Apply this decision tree first:

1. **Is this actually a bottleneck?** Profile first. Lock contention shows up
   as high `futex` time in `perf` or high `pthread_mutex_lock` time in a
   profiler. Don't optimize what you haven't measured.

2. **Can message passing solve it?** If the producer and consumer are already
   separate actors/threads, a lock-free queue is the right mechanism. If
   they're in the same thread, you don't need any synchronization.

3. **How many producers and consumers?** This determines which structure to use:
   - One producer, one consumer → SPSC ring buffer (simplest, fastest)
   - Multiple producers, one consumer → MPSC queue
   - One producer, multiple consumers → SPMC queue
   - Multiple producers, multiple consumers → MPMC queue (most complex)

4. **Is the queue bounded?** Always prefer bounded queues in production
   systems. Bounded queues provide backpressure. Unbounded queues hide
   backpressure and cause unbounded memory growth under load.

| Scenario | Structure |
|---|---|
| Single producer, single consumer, hot path | SPSC ring buffer |
| Multiple producers, single consumer | MPSC queue (or MPMC) |
| High-throughput event bus, multiple producers/consumers | LMAX Disruptor |
| General bounded MPMC | Vyukov bounded MPMC queue |
| Low contention, simple code | `std::mutex` + `std::queue` |

---

## SPSC Ring Buffer

A single-producer, single-consumer ring buffer is the simplest lock-free
structure. One thread writes; one thread reads. No CAS operations needed —
only memory ordering.

### Basic structure

```c
// Conceptual C — adapt to your language
#define CAPACITY 1024  // must be power of two
#define MASK (CAPACITY - 1)

typedef struct {
    alignas(64) atomic_size_t write_idx;
    alignas(64) atomic_size_t read_idx;
    T slots[CAPACITY];
} SPSC_Ring;
```

The `alignas(64)` on each index is critical — see "False Sharing" below.

**Push** (producer only):
```c
bool push(SPSC_Ring* ring, T value) {
    size_t w = atomic_load_explicit(&ring->write_idx, memory_order_relaxed);
    size_t r = atomic_load_explicit(&ring->read_idx, memory_order_acquire);
    if (w - r == CAPACITY) return false;  // full
    ring->slots[w & MASK] = value;
    atomic_store_explicit(&ring->write_idx, w + 1, memory_order_release);
    return true;
}
```

**Pop** (consumer only):
```c
bool pop(SPSC_Ring* ring, T* out) {
    size_t r = atomic_load_explicit(&ring->read_idx, memory_order_relaxed);
    size_t w = atomic_load_explicit(&ring->write_idx, memory_order_acquire);
    if (r == w) return false;  // empty
    *out = ring->slots[r & MASK];
    atomic_store_explicit(&ring->read_idx, r + 1, memory_order_release);
    return true;
}
```

### Snellman's unmasked indices trick

The basic code above already embodies Snellman's trick. To understand why it
matters, consider the older approach where indices are stored modulo CAPACITY:

```c
// Older approach: indices stored mod CAPACITY
typedef struct {
    atomic_size_t write_idx;  // values in [0, CAPACITY)
    atomic_size_t read_idx;   // values in [0, CAPACITY)
    T slots[CAPACITY];
} SPSC_Ring_Modulo;

bool push(SPSC_Ring_Modulo* ring, T value) {
    size_t w = atomic_load_explicit(&ring->write_idx, memory_order_relaxed);
    size_t r = atomic_load_explicit(&ring->read_idx, memory_order_acquire);
    // Can't use (w - r == CAPACITY) because indices are already masked.
    // Full condition requires wasting one slot so full != empty:
    size_t next_w = (w + 1) % CAPACITY;
    if (next_w == r) return false;  // full — one slot wasted
    ring->slots[w] = value;
    atomic_store_explicit(&ring->write_idx, next_w, memory_order_release);
    return true;
}
```

The problem: with indices in `[0, CAPACITY)`, you can't distinguish full
(`w` has lapped `r`) from empty (`w == r`) without wasting one slot as a
sentinel.

**Snellman's fix**: let indices grow unbounded — never mask them except when
indexing into the array (`w & MASK`). Full is `w - r == CAPACITY`; empty is
`w == r`. These conditions are unambiguous. No wasted slot. The indices wrap
naturally at `SIZE_MAX`, and unsigned subtraction handles the wrap correctly.

The basic implementation shown above already uses this approach. The
improvement over the modulo variant is one recovered slot and cleaner
full/empty logic.

### Rigtorp's cached-index optimization

**Problem**: In the basic implementation, every `push` reads `read_idx` (to
check if full), and every `pop` reads `write_idx` (to check if empty). These
reads cross cache lines — the producer's cache line (holding `write_idx`) and
the consumer's cache line (holding `read_idx`) are on different cores. Each
cross-read causes a cache coherency message.

In steady state (producer and consumer running at similar rates), the ring is
neither full nor empty most of the time. The cross-reads are wasted.

**Rigtorp's fix**: cache the other side's index locally.

```c
typedef struct {
    alignas(64) atomic_size_t write_idx;
    size_t cached_read_idx;   // producer's cached copy of read_idx
    alignas(64) atomic_size_t read_idx;
    size_t cached_write_idx;  // consumer's cached copy of write_idx
    alignas(64) T slots[CAPACITY];
} SPSC_Ring_Rigtorp;
```

**Push** (producer):
```c
bool push(SPSC_Ring_Rigtorp* ring, T value) {
    size_t w = atomic_load_explicit(&ring->write_idx, memory_order_relaxed);
    if (w - ring->cached_read_idx == CAPACITY) {
        // Cached value says full — refresh from actual read_idx
        ring->cached_read_idx = atomic_load_explicit(&ring->read_idx, memory_order_acquire);
        if (w - ring->cached_read_idx == CAPACITY) return false;  // actually full
    }
    ring->slots[w & MASK] = value;
    atomic_store_explicit(&ring->write_idx, w + 1, memory_order_release);
    return true;
}
```

**Pop** (consumer):
```c
bool pop(SPSC_Ring_Rigtorp* ring, T* out) {
    size_t r = atomic_load_explicit(&ring->read_idx, memory_order_relaxed);
    if (r == ring->cached_write_idx) {
        // Cached value says empty — refresh from actual write_idx
        ring->cached_write_idx = atomic_load_explicit(&ring->write_idx, memory_order_acquire);
        if (r == ring->cached_write_idx) return false;  // actually empty
    }
    *out = ring->slots[r & MASK];
    atomic_store_explicit(&ring->read_idx, r + 1, memory_order_release);
    return true;
}
```

**Effect**: In steady state, the producer only reads its own `write_idx` and
the cached `read_idx` (which is on the same cache line). The consumer only
reads its own `read_idx` and the cached `write_idx`. Cross-cache-line reads
happen only when the ring is actually full or empty.

**Measured impact** (from Rigtorp's benchmarks): 5.5M ops/sec → 112M ops/sec
on a typical x86 system. The improvement is from reducing cache coherency
traffic from 3 cache misses per operation to near-zero in steady state.

---

## False Sharing and Cache-Line Alignment

A cache line is 64 bytes on x86. If two variables share a cache line, writes
to one invalidate the other in every other core's cache — even if the cores
never actually share that variable.

In a ring buffer, `write_idx` and `read_idx` are written by different threads.
If they share a cache line, every write to `write_idx` (by the producer)
invalidates the consumer's cache line containing `read_idx`, and vice versa.
This is *false sharing* — the cores are fighting over a cache line they don't
actually need to share.

**Fix**: align each index to a separate cache line with `alignas(64)`.

```c
alignas(64) atomic_size_t write_idx;  // producer's cache line
alignas(64) atomic_size_t read_idx;   // consumer's cache line
```

Also align the slots array to a cache line to prevent the last index from
sharing a line with the first slot.

---

## Memory Ordering

Lock-free code requires explicit memory ordering. The rules for SPSC:

- **Own index**: load with `relaxed`. Only one thread writes it; no
  synchronization needed.
- **Other's index**: load with `acquire`. You need to see all writes the
  other thread made before it updated its index.
- **Store own index**: store with `release`. You need to publish all your
  writes (to slots) before the other thread sees the updated index.

The acquire/release pair forms a happens-before relationship: the producer's
`release` store of `write_idx` synchronizes with the consumer's `acquire`
load of `write_idx`. This guarantees the consumer sees the slot data written
before the index update.

**Never use `relaxed` for the other thread's index** — this is the most
common lock-free bug. It allows the compiler and CPU to reorder the slot
read before the index check, reading uninitialized or stale data.

---

## MPMC: LMAX Disruptor

The LMAX Disruptor is a high-throughput MPMC ring buffer designed for the
LMAX financial exchange. It achieves 25M+ operations/second by eliminating
CAS contention through sequence numbers and the single-writer principle.

### Core ideas

**Pre-allocated ring**: the ring is allocated at startup with a fixed capacity.
No dynamic allocation during operation. Slots are reused in order.

**Sequence numbers**: each slot has a sequence number. Producers claim slots
by atomically incrementing a shared producer sequence. Consumers track their
own consumer sequence. The sequence number in each slot tells consumers
whether the slot is ready to read.

**Single-writer principle**: each slot is written by exactly one producer
(the one that claimed it). Multiple producers don't contend on the same slot.
Contention is only on the producer sequence counter (to claim the next slot).

**Batching effect**: a slow consumer doesn't block producers (up to ring
capacity). When the consumer catches up, it processes all available slots in
a batch without contention — it just reads until it reaches the producer's
sequence. This amortizes the cost of the sequence check across many slots.

**Separation of concerns**: the Disruptor separates storage (the ring),
claiming (producer sequence), and consumption (consumer sequence). Each
concern is independently optimizable.

### When to use

- High-throughput event buses where multiple producers publish to multiple
  consumers
- Financial systems, game engines, telemetry pipelines
- When you need ordered delivery with high throughput

### When not to use

- Simple single-producer, single-consumer paths (SPSC ring is simpler and
  faster)
- When you need dynamic resizing (Disruptor is fixed-size)
- When simplicity matters more than throughput

---

## MPMC: Vyukov Bounded Queue

Dmitry Vyukov's bounded MPMC queue uses per-slot sequence numbers and CAS
to claim slots. It's simpler than the Disruptor and suitable for general
MPMC use.

### Core idea

Each slot has a sequence number initialized to its index. Producers claim a
slot by atomically incrementing a shared `enqueue_pos` counter
(`fetch_add(1)`). The returned value is the producer's claimed position. The
producer then spin-waits until the slot's sequence number equals the claimed
position (another producer may have claimed it first and not yet published).
Once the sequence matches, the producer writes the value and stores
`claimed_pos + 1` to the slot's sequence to publish it.

Consumers work symmetrically: they `fetch_add` a shared `dequeue_pos`, spin-
wait until the slot's sequence equals `claimed_pos + 1` (the producer has
published), read the value, then store `claimed_pos + capacity` to the slot's
sequence to mark it available for the next lap.

The sequence number encodes the slot's state across laps of the ring: a
sequence of `n` means available for write at lap `n/capacity`; a sequence of
`n + 1` means published and available for read. No separate lock needed.

### Properties

- Bounded: fixed capacity, no dynamic allocation
- Lock-free: at least one thread always makes progress; busy-spins on
  contention (not blocking)
- Simpler than Disruptor for general use

---

## Bounded vs Unbounded

**Always prefer bounded queues in production systems.**

An unbounded queue is an unbounded buffer. Under load, if the consumer is
slower than the producer, the queue grows without limit. This causes:
- Unbounded memory growth (OOM)
- Increasing latency as items wait longer in the queue
- No backpressure signal to the producer

A bounded queue provides backpressure: when full, the producer blocks (or
receives an error). This pressure propagates upstream, slowing the producer
to match the consumer's capacity. The system degrades gracefully instead of
running out of memory.

**The only valid use case for unbounded queues** is when you can prove the
producer rate is always bounded below the consumer rate — which is rarely
provable in practice.

---

## Common Patterns

**Single-writer principle**: only one thread writes to any given memory
location. Multiple readers are fine. This eliminates write-write contention
entirely. The Disruptor's per-slot ownership is an application of this
principle.

**Power-of-two sizing**: ring buffers sized to a power of two allow index
masking with `& (capacity - 1)` instead of `% capacity`. Modulo is a
division; masking is a single AND instruction. For hot-path code, this
matters.

**Padding to avoid false sharing**: if a struct has fields accessed by
different threads, pad between them to ensure they land on separate cache
lines. This is especially important for sequence numbers in MPMC structures.

**Avoid dynamic allocation on the hot path**: pre-allocate all ring buffer
slots at startup. Dynamic allocation (malloc/free) under contention is a
common source of unexpected latency spikes.
