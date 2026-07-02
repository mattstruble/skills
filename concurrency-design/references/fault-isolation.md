# Fault Isolation

Read this when designing for failure: what crashes independently, how
supervisors restart failed units, how to prevent crash loops, and how to
test recovery paths. Covers trap boundaries, supervision trees (Erlang/OTP
model), recovery budgets, "let it crash" prerequisites, and simulation
testability.

---

## The Core Question: What Is Your Fault Boundary?

A fault boundary is the unit that can fail without taking down anything else.
Design your system so that the fault boundary is as small as possible and
failures are as cheap as possible to recover from.

| Unit | Fault boundary | Notes |
|---|---|---|
| Erlang process | Per-process | Crash is isolated; supervisor restarts it |
| Tina isolate | Per-isolate | Trap catches hardware faults within the isolate |
| OS thread | Per-process (usually) | SIGSEGV in a thread kills the process unless trapped |
| Go goroutine | Per-program | Unrecovered panic kills the program |
| OS process | Per-process | Strongest isolation; restart via supervisor (systemd, etc.) |

**Erlang processes are the gold standard for fault isolation.** A process
crash is caught by the runtime, the process's mailbox is discarded, and the
supervisor decides what to do next. No other process is affected. This is why
Erlang systems achieve "nine nines" uptime — not because they prevent crashes,
but because crashes are cheap and isolated.

---

## Trap Boundaries

A *trap* is a mechanism for catching hardware faults (SIGSEGV, SIGBUS,
SIGFPE) within a unit and converting them into recoverable errors rather than
process termination.

Tina's isolate model uses per-isolate trap boundaries: if an isolate
dereferences a null pointer, the trap catches the SIGSEGV, marks the isolate
as faulted, and returns control to the scheduler. The scheduler can then
restart the isolate or escalate to the shard supervisor.

### Nested trap levels

A well-designed system has multiple trap levels:

1. **Per-isolate/actor**: catches faults within a single unit. The unit is
   restarted or discarded. Other units are unaffected.
2. **Per-shard/thread**: catches faults that escape the per-isolate trap (e.g.,
   a fault in the scheduler itself). The shard is restarted. Other shards
   continue.
3. **Per-process**: the last line of defense. A fault here kills the process.
   An external supervisor (systemd, Kubernetes) restarts the process.

Each level is a backstop for the level below. The goal is to handle failures
at the lowest level possible.

### Implementing trap boundaries

On POSIX systems, `sigaction` with `SA_SIGINFO` installs a signal handler.
The handler can use `siglongjmp` to jump to a recovery point. This is how
Erlang's runtime implements per-process fault isolation.

The key constraint: the signal handler must be async-signal-safe. It cannot
call `malloc`, `printf`, or most library functions. The recovery point
(established with `sigsetjmp`) must be set up before entering the potentially
faulting code.

```c
// Conceptual — simplified
sigjmp_buf recovery_point;

void fault_handler(int sig, siginfo_t* info, void* ctx) {
    siglongjmp(recovery_point, 1);  // jump to recovery point
}

bool run_isolate(Isolate* isolate) {
    if (sigsetjmp(recovery_point, 1) != 0) {
        // Fault was caught — isolate is faulted
        isolate->state = FAULTED;
        return false;
    }
    // Install fault handler for this isolate
    struct sigaction sa = { .sa_sigaction = fault_handler, .sa_flags = SA_SIGINFO };
    sigaction(SIGSEGV, &sa, NULL);
    
    // Run the isolate
    isolate->run(isolate);
    return true;
}
```

---

## Supervision Trees

A supervision tree is a hierarchy of supervisors and workers. Workers do the
actual work; supervisors watch workers and restart them when they fail.

This is the Erlang/OTP model, but the concept applies to any language.

### Restart strategies

**One-for-one**: when a child crashes, restart only that child. Use when
children are independent — a crash in one doesn't affect the others.

```
Supervisor
├── Worker A  ← crashes → restart A only
├── Worker B  ← unaffected
└── Worker C  ← unaffected
```

**One-for-all**: when any child crashes, restart all children. Use when
children share invariants — if one is in a bad state, the others may be too.

```
Supervisor
├── Worker A  ← crashes → restart A, B, C
├── Worker B  ← restarted
└── Worker C  ← restarted
```

**Rest-for-one**: when a child crashes, restart it and all children started
after it. Use for ordered pipelines where later stages depend on earlier ones.

```
Supervisor (start order: A, B, C)
├── Worker A  ← unaffected
├── Worker B  ← crashes → restart B, C
└── Worker C  ← restarted (depends on B)
```

### Supervision tree depth

Supervision trees can be nested. A top-level supervisor watches
sub-supervisors, which watch workers. This allows fine-grained restart
strategies at each level.

```
Top Supervisor (one-for-one)
├── Network Supervisor (one-for-all)
│   ├── Listener
│   └── Connection Pool
└── Storage Supervisor (rest-for-one)
    ├── WAL Writer
    ├── Index Manager
    └── Cache
```

When the Network Supervisor's children crash, only network components restart.
The Storage Supervisor is unaffected.

---

## Recovery Budgets

A supervision strategy without a recovery budget creates infinite crash loops.
If a worker crashes immediately on restart (e.g., due to a persistent bug or
a bad environment), the supervisor will restart it forever, consuming CPU and
filling logs.

**Recovery budget**: allow at most N restarts in T seconds. If the budget is
exceeded, escalate to the next supervision level.

Erlang's OTP supervisor implements this as `max_restarts` and `max_seconds`:
if more than `max_restarts` crashes occur within `max_seconds`, the supervisor
itself terminates and its parent supervisor handles the failure.

### Escalation chain

```
Worker crashes
  → Supervisor: restart (budget: 5 in 10s)
    → If budget exceeded: Supervisor crashes
      → Parent supervisor: restart supervisor (budget: 3 in 60s)
        → If budget exceeded: Parent supervisor crashes
          → Top-level supervisor: shut down application
```

Each level has its own budget. Transient failures (network blip, temporary
resource exhaustion) are handled at the lowest level. Persistent failures
escalate until a human can investigate.

### Exponential backoff

Add a backoff delay between restarts to prevent hammering a failing dependency:

```
restart 1: immediate
restart 2: 100ms
restart 3: 200ms
restart 4: 400ms
restart 5: 800ms
→ budget exceeded, escalate
```

This gives transient failures time to resolve while preventing tight crash
loops.

---

## "Let It Crash"

"Let it crash" is a design philosophy from Erlang: instead of writing
defensive code to handle every possible error, let the process crash and let
the supervisor restart it in a clean state.

This is not an excuse for sloppy code. It works only when all three
preconditions are met:

1. **Restart is cheap and fast**: the unit can be restarted in milliseconds,
   not seconds. If restart requires re-reading a large database or
   re-establishing expensive connections, "let it crash" is too costly.

2. **State is isolated and recoverable**: the crashed unit's state is
   discarded. The system can continue without it. If the crashed unit held
   the only copy of important state, crashing loses data.

3. **A supervisor is watching**: someone is responsible for restarting the
   unit and deciding when to escalate. Without supervision, "let it crash"
   is just "crash and stay down."

When these preconditions hold, "let it crash" is strictly better than
defensive error handling: it's simpler code, cleaner state after recovery,
and no risk of the "partially initialized" state that defensive code often
leaves behind.

**Where defensive code still belongs**: at trust boundaries (validating
external input), at resource acquisition (checking that a file exists before
opening it), and in supervisors themselves (supervisors must not crash).

---

## Guard Pages and Memory Isolation

For stronger isolation between units in the same process, use guard pages:
allocate a page of memory with `PROT_NONE` between each unit's stack or heap
region. Any access to the guard page triggers a SIGSEGV, which the trap
boundary catches.

This prevents a buffer overflow in one unit from silently corrupting another
unit's memory. Without guard pages, a stack overflow in one isolate might
overwrite the adjacent isolate's stack — a silent corruption that produces
wrong results rather than a clean crash.

Guard pages are used by:
- OS thread stacks (the OS places a guard page below each thread's stack)
- Tina isolates (per-isolate guard pages between isolate stacks)
- Sandboxed execution environments (WebAssembly runtimes, browser tabs)

---

## Designing for Simulation Testability

The hardest bugs in concurrent systems are fault recovery paths: what happens
when a unit crashes at exactly the wrong moment? These paths are rarely
exercised in normal operation and often contain subtle bugs.

**Simulation testing** (also called deterministic simulation testing, or DST)
makes these paths testable by:

1. **Seeded randomness**: all non-determinism (network delays, disk latency,
   crash timing) is driven by a seeded random number generator. Given the
   same seed, the simulation produces the same execution.

2. **Fault injection**: the simulation can inject faults at any point —
   crash a unit, delay a message, corrupt a response. This exercises recovery
   paths that would take years to encounter in production.

3. **Replay**: when a bug is found, the seed reproduces it exactly. No
   "Heisenbug" that disappears under a debugger.

**Architectural requirements for DST**:
- All I/O must go through an abstraction layer that the simulator can
  intercept. No direct syscalls on the hot path.
- All time must come from a clock that the simulator controls. No
  `gettimeofday()` or `clock_gettime()` directly.
- All randomness must come from the seeded RNG.

TigerBeetle (a financial database) uses DST extensively. Their simulator
runs millions of simulated years of operation, injecting faults at every
step, to verify that the recovery logic is correct. Bugs that would take
years to encounter in production are found in minutes.

**Practical implication**: design your fault boundaries and recovery logic
with testability in mind from the start. If your recovery paths can't be
exercised in a test, you don't know if they work.
