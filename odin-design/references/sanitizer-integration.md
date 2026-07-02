# ASan Integration for Arena-Based Memory

Read this reference when integrating AddressSanitizer with arena allocators,
debugging stale-pointer bugs in reused memory, or adding sanitizer hooks to
ownership transitions.

---

## The Problem: Logical vs Physical Lifetimes

Arena allocators carve a large backing buffer at startup and never return
individual allocations to the OS. From the OS and ASan's perspective, the
entire arena is one live allocation from `malloc` to `free`. ASan tracks
**physical lifetimes** — it sees the arena's backing buffer as continuously
valid memory.

Inside the arena, however, slots are logically allocated and released as
objects come and go. A slot that held actor A's state gets reused for actor B.
ASan never sees this transition. A stale pointer into that slot — one that
escaped actor A's teardown — silently reads actor B's state. No crash. No
sanitizer report. The bug is invisible.

```
Physical view (what ASan sees):
  [arena backing buffer — always valid — never freed]

Logical view (what your program means):
  [slot 0: actor A] → [slot 0: DEAD] → [slot 0: actor B]
                                ↑
                    stale pointer here is undetectable
```

The same problem applies to any reuse pattern: scratch arenas reset between
handlers, message pool slots cycle through messages, ring buffer slots wrap
around. ASan cannot detect use-after-logical-free in any of these cases
without help.

---

## The Solution: Manual Poisoning Contract

ASan exposes a shadow memory API. Marking a region **poisoned** tells ASan
that any access to it is an error, even though the physical memory is still
allocated. Marking it **unpoisoned** restores normal access.

**The contract:**

> Poison on logical release. Unpoison on logical allocation.

When ownership of a memory region ends → poison it.  
When that region is assigned to a new logical owner → unpoison it.

These operations do not allocate, free, or move memory. They update ASan's
shadow memory only. The physical backing buffer is untouched.

---

## Odin API

The `base:sanitizer` package provides the poisoning primitives:

```odin
import "base:sanitizer"

// Poison: mark region as invalid. Any access triggers ASan error.
sanitizer.address_poison_rawptr(ptr, size)

// Unpoison: mark region as valid. Normal access resumes.
sanitizer.address_unpoison_rawptr(ptr, size)
```

Both take a `rawptr` and a `int` byte count. Alignment requirements match
ASan's shadow granularity (8 bytes).

### Compile-Time Gating

Poisoning calls must be gated on whether ASan is actually active. The
`ODIN_SANITIZER_FLAGS` built-in constant reports which sanitizers are compiled
in. Define a package-level constant and use `when` blocks:

```odin
// Define once per package
ASAN_POISONING :: .Address in ODIN_SANITIZER_FLAGS

// Use everywhere
when ASAN_POISONING {
    sanitizer.address_poison_rawptr(slot_ptr, slot_size)
}
```

When compiled without `-sanitize:address`, the `when` block is eliminated at
compile time. Zero runtime cost. Zero binary size increase. The poisoning
logic exists only in sanitizer builds.

Build with sanitizers enabled:

```bash
odin build . -sanitize:address
odin test . -sanitize:address
```

---

## Per-Domain Poisoning Patterns

Each ownership model needs its own poisoning discipline. Don't try to share
poisoning logic across domains — the ownership transitions differ.

### Isolate / Actor Slots

An isolate pool pre-allocates fixed-size slots. Each slot holds one actor's
state for the actor's lifetime. When an actor exits or crashes, its slot is
logically dead until a new actor claims it.

```odin
import "base:sanitizer"

ASAN_POISONING :: .Address in ODIN_SANITIZER_FLAGS

isolate_teardown :: proc(pool: ^Isolate_Pool, slot_idx: int) {
    slot := &pool.slots[slot_idx]

    // ... actor cleanup: flush state, close handles, etc. ...

    // Poison AFTER cleanup so cleanup code can still read the slot.
    when ASAN_POISONING {
        sanitizer.address_poison_rawptr(slot, size_of(Isolate_Slot))
    }

    pool.free_list[pool.free_count] = slot_idx
    pool.free_count += 1
}

isolate_init :: proc(pool: ^Isolate_Pool, slot_idx: int) -> ^Isolate_Slot {
    slot := &pool.slots[slot_idx]

    // Unpoison BEFORE any init code writes to the slot.
    when ASAN_POISONING {
        sanitizer.address_unpoison_rawptr(slot, size_of(Isolate_Slot))
    }

    slot^ = {}  // zero-initialize
    // ... actor init ...
    return slot
}
```

**Catches:** A stale pointer retained from actor A's teardown that reads into
actor B's slot triggers an ASan error immediately.

---

### Per-Handler Scratch Arena

A scheduler resets a scratch arena between handler invocations. Any pointer
into the arena that escapes the handler's scope is a bug — the memory will be
reused for the next handler.

```odin
ASAN_POISONING :: .Address in ODIN_SANITIZER_FLAGS

// Called by the scheduler's internal alloc path — not by handlers directly.
scratch_alloc :: proc(scratch: ^Scratch_Arena, size: int) -> rawptr {
    ptr := mem.ptr_offset(scratch.base, scratch.offset)
    scratch.offset += size
    when ASAN_POISONING {
        sanitizer.address_unpoison_rawptr(ptr, size)
    }
    return ptr
}

handler_end :: proc(scratch: ^Scratch_Arena) {
    // Poison the entire used region when the handler returns.
    when ASAN_POISONING {
        sanitizer.address_poison_rawptr(scratch.base, scratch.offset)
    }
    scratch.offset = 0  // reset cursor
}
```

**Catches:** A pointer allocated during handler N that is stored somewhere
and dereferenced during handler N+1 triggers an ASan error. The pointer is
valid memory but poisoned — exactly the bug.

---

### Message Pool Envelopes

A message pool recycles fixed-size envelope slots. A slot is allocated when a
message is enqueued, and returned to the pool when the receiver processes it.
Retaining the pointer after delivery accesses a slot that may hold a different
message.

```odin
ASAN_POISONING :: .Address in ODIN_SANITIZER_FLAGS

pool_alloc_envelope :: proc(pool: ^Msg_Pool) -> ^Envelope {
    slot := pool_pop_free(pool)
    when ASAN_POISONING {
        sanitizer.address_unpoison_rawptr(slot, size_of(Envelope))
    }
    return slot
}

pool_return_envelope :: proc(pool: ^Msg_Pool, env: ^Envelope) {
    // Poison before returning to pool — the caller must not use env after this.
    when ASAN_POISONING {
        sanitizer.address_poison_rawptr(env, size_of(Envelope))
    }
    pool_push_free(pool, env)
}
```

**Catches:** Any code that retains `env` and reads it after `pool_return_envelope`
triggers an ASan error on the next access.

---

### I/O Buffer Slots

When a buffer is submitted to the kernel (via `io_uring`, `sendmsg`, etc.),
ownership transfers to the OS. Userspace must not read or write the buffer
until the completion event returns it. Poisoning enforces this boundary.

```odin
ASAN_POISONING :: .Address in ODIN_SANITIZER_FLAGS

io_submit :: proc(ring: ^IO_Ring, buf: ^IO_Buffer) {
    // Poison before submission — ownership is now the kernel's.
    when ASAN_POISONING {
        sanitizer.address_poison_rawptr(buf.data, buf.capacity)
    }
    ring_submit_write(ring, buf)
}

io_complete :: proc(ring: ^IO_Ring, completion: IO_Completion) -> ^IO_Buffer {
    buf := completion.buf
    // Unpoison when completion event returns ownership to userspace.
    when ASAN_POISONING {
        sanitizer.address_unpoison_rawptr(buf.data, buf.capacity)
    }
    return buf
}
```

**Catches:** Any userspace code that reads or writes `buf.data` between
`io_submit` and `io_complete` triggers an ASan error. This catches races
where app code writes into a buffer the kernel is actively reading.

---

### SPSC Ring Buffer Slots

Lock-free ring buffers require careful ordering. The producer writes data into
a slot and then publishes availability with an atomic store. The consumer reads
the slot after observing the atomic. Poisoning must respect this ordering or
it creates false positives.

**Critical rule: poison BEFORE publishing. Unpoison BEFORE writing.**

```odin
import "core:sync"

ASAN_POISONING :: .Address in ODIN_SANITIZER_FLAGS

// Producer side
spsc_push :: proc(ring: ^SPSC_Ring, item: Item) -> bool {
    write_idx := ring.write_idx
    next_idx   := (write_idx + 1) % RING_SIZE

    if next_idx == sync.atomic_load(&ring.read_idx) {
        return false  // full
    }

    slot := &ring.slots[write_idx]

    // Unpoison BEFORE writing — slot is about to become valid producer data.
    when ASAN_POISONING {
        sanitizer.address_unpoison_rawptr(slot, size_of(Item))
    }

    slot^ = item

    // Poison BEFORE publishing — catches producer-side stale pointers: any code
    // on the producer thread that retains a reference to this slot after handing
    // it off will hit the poison. The consumer always unpoisons before reading,
    // so this does not affect the consumer's legitimate access.
    when ASAN_POISONING {
        sanitizer.address_poison_rawptr(slot, size_of(Item))
    }

    // Publish: atomic store makes slot visible to consumer.
    sync.atomic_store(&ring.write_idx, next_idx)
    return true
}

// Consumer side
spsc_pop :: proc(ring: ^SPSC_Ring) -> (Item, bool) {
    read_idx  := ring.read_idx
    write_idx := sync.atomic_load(&ring.write_idx)

    if read_idx == write_idx {
        return {}, false  // empty
    }

    slot := &ring.slots[read_idx]

    // Unpoison immediately before reading — consumer now owns this slot.
    when ASAN_POISONING {
        sanitizer.address_unpoison_rawptr(slot, size_of(Item))
    }

    item := slot^

    // Poison after consuming — slot is logically dead until producer reuses it.
    when ASAN_POISONING {
        sanitizer.address_poison_rawptr(slot, size_of(Item))
    }

    sync.atomic_store(&ring.read_idx, (read_idx + 1) % RING_SIZE)
    return item, true
}
```

**Why the ordering matters:** Poison before publish catches producer-side stale
pointers — references the producer retains to a slot after writing it. If the
producer poisoned *after* publishing, there would be a window where producer
code could still hold a live reference to an unpoisoned slot it has already
handed off. The consumer is unaffected: it always unpoisons before reading,
so the producer's poison is cleared before any legitimate consumer access.

**Catches:** Any code that reads a slot outside the consumer's ownership window
(e.g., a stale pointer to a previously consumed slot) triggers an ASan error.

---

### Logging Circular Buffer

A logging ring keeps only the unflushed region valid. As the write cursor
advances, new entries are unpoisoned. As the read cursor flushes entries, those
regions are poisoned.

```odin
ASAN_POISONING :: .Address in ODIN_SANITIZER_FLAGS

log_write :: proc(log: ^Log_Ring, entry: Log_Entry) {
    slot := &log.slots[log.write_cursor % LOG_CAPACITY]

    // Unpoison new entry before writing.
    when ASAN_POISONING {
        sanitizer.address_unpoison_rawptr(slot, size_of(Log_Entry))
    }

    slot^ = entry
    log.write_cursor += 1
}

log_flush :: proc(log: ^Log_Ring, flush_up_to: int) {
    for log.read_cursor < flush_up_to {
        slot := &log.slots[log.read_cursor % LOG_CAPACITY]

        // ... write slot to output ...

        // Poison flushed region — stale pointers into it are now detectable.
        when ASAN_POISONING {
            sanitizer.address_poison_rawptr(slot, size_of(Log_Entry))
        }

        log.read_cursor += 1
    }
}
```

**Catches:** A stale pointer into a flushed log region (e.g., a reference
captured during a log callback) triggers an ASan error on the next access.

---

## Key Principles

**Ordering matters for lock-free structures.** Poison before publishing
availability; unpoison before writing new data. Getting this backwards
produces false positives that are hard to diagnose.

**One domain per ownership model.** Each ownership transition pattern (slot
pool, scratch arena, ring buffer) needs its own poisoning discipline. Sharing
logic across domains obscures which transition is responsible for a bug.

**Poison after cleanup, unpoison before init.** Cleanup code must still be
able to read the region it's tearing down. Init code must be able to write
before any reads happen. Poisoning at the boundary between these phases is
the correct position.

**Production builds have zero overhead.** The `when ASAN_POISONING { ... }`
blocks are eliminated at compile time when `-sanitize:address` is absent.
No branches, no function calls, no binary size increase in release builds.

**Complementary to tracking allocator.** The tracking allocator (`mem.Tracking_Allocator`,
see `references/allocators.md`) catches leaks — allocations that are never
freed. Manual poisoning catches use-after-logical-free — accesses to memory
that is physically live but logically dead. Use both in development builds.

```odin
// Development build: both tools active
when ODIN_DEBUG {
    track: mem.Tracking_Allocator
    mem.tracking_allocator_init(&track, context.allocator)
    context.allocator = mem.tracking_allocator(&track)
    defer { /* report leaks */ }
}
// ASan poisoning active separately when compiled with -sanitize:address
// The two tools are independent and complementary.
```

---

## Common Mistakes

1. **Poisoning before cleanup completes** — cleanup code reads the slot it's
   tearing down. Poison after the last read in teardown, not before.

2. **Unpoisoning the entire arena on reset** — unpoison only the bytes
   actually allocated to a new owner. Unpoisoning the whole arena defeats
   the purpose: accesses to unallocated regions go undetected.

3. **Reversing poison/publish order in lock-free code** — see the SPSC
   section. Publish-then-poison creates a window where the consumer reads
   a poisoned slot legitimately.

4. **Forgetting the compile-time gate** — calling `sanitizer.address_poison_rawptr`
   without a `when ASAN_POISONING` guard is harmless (the call is a no-op
   without ASan), but the gate makes intent explicit and documents that the
   call is a sanitizer hook, not production logic.

5. **Misaligned poison regions** — ASan's shadow granularity is 8 bytes.
   Poisoning a region that doesn't start on an 8-byte boundary or has a
   size that isn't a multiple of 8 may leave partial granules in an
   ambiguous state. Align slot sizes to 8 bytes.
