# Concurrency and Load

Thread and task management, async trade-offs, mutex discipline, queueing theory, and infrastructure minimalism.

## Concurrency is not parallelism

Parallelism means using the hardware to finish work faster — thread count
should track *core* count, not *task* count. Spinning a thread per task is
not parallelism; it is context-switch overhead dressed up as concurrency.
The distinction matters when sizing thread pools: a pool sized to the number
of pending tasks will thrash; a pool sized to the number of cores will not.

---

## Suspend work with explicit task state, not coroutines

For blocking I/O (HTTP calls, database queries), the options are: start a
thread, hand the work to a job system that writes its result to a known
place, or disentangle the job's state into an explicit data structure and
run a small scheduler loop over pending tasks.

The scheduler loop approach is your own scheduler, but far simpler than a
general-purpose one because it handles only a known, well-defined set of
cases. The constraint is that tasks in the loop must not call anything that
blocks indefinitely — if they might, use a thread instead.

Jonathan Blow argues against coroutines and Go-style goroutines as a
language feature: they add infrastructure for syntactic sugar and are
designed for general "customers," handling cases your application does not
need. The explicit-state approach gives you the same suspension semantics
with less machinery and more control over scheduling order.

---

## Async hides non-determinism

Basic async is easy to add but hard to make genuinely correct. Its failure
mode is *wrong answers*, not crashes — thread-safety bugs hide silently
rather than surfacing as exceptions. The more serious the program, the more
likely subtle bugs will appear and the more discipline is required to avoid
them.

Jonathan Blow argues against baking async in as a language-level feature for
this reason: it moves non-determinism into the architecture rather than
keeping it at the user level where it can be reasoned about explicitly.

---

## Mutex discipline

Hold locks for as little, and as *simple*, code as possible. The more code
runs under a lock, the less you know what is happening: you may acquire other
locks (lock-order inversion, deadlock) and you will log-jam threads waiting
to enter.

Two practices that pay off:

- **Assertable ownership**: a good mutex lets you assert whether you
  currently hold it. This turns "did I forget to lock?" from a data-race
  into a detectable invariant.
- **Lock-order priority**: assign each mutex a static priority and only
  allow acquiring locks in a consistent order. A runtime check that detects
  out-of-order acquisition catches inversion before it becomes a deadlock.

---

## Queueing and load realism

Queueing theory's most important result: as utilization approaches capacity,
wait times blow up far faster than intuition expects. A system at 90%
utilization does not have 10% headroom — it has a queue that grows without
bound under any transient spike.

Practical consequences:

- **Model load realistically.** "X requests per month" often means one every
  few seconds. A million registered users does not mean a million concurrent
  database requests unless the design is broken.
- **Degrade gracefully.** When a stage cannot keep up, run it in a cheaper
  "fast mode" rather than queuing indefinitely.
- **Over-provision for launch.** Launch-week traffic is temporary; the cost
  of extra capacity for a few weeks is far lower than the cost of a
  high-profile outage.

---

## Don't import web-stack complexity the problem doesn't demand

Docker, Kubernetes, microservices, and load balancers are solutions to
problems that web-scale services actually have. They are not required by
every distributed system. A multiplayer game server, for example, does not
need this stack — the client is already more complex and ships without it.

Jonathan Blow argues that this pattern reflects "web people" copying their
stack into domains where it does not belong. High-performance paths often
use user-space, direct-to-NIC I/O that bypasses kernel buffering entirely —
the opposite of adding layers.

Evaluation heuristic: judge a technical claim by whether it describes real
data structures and algorithms (how the query works, how the spatial index is
built). Distrust presentations that make uncharitable comparisons to
alternatives while exempting themselves from the same scrutiny.

---

## Fix the broken substrate instead of stacking workaround layers

When a layer spawns endless workaround layers — framework churn, transpilers,
adapter chains — the real defect is usually the layer beneath. Piling
adapters over a wrong abstraction is the architectural smell; the fix is to
correct the abstraction.

This extends the Anti-Corruption Layer guidance in the main skill: an ACL is
appropriate when integrating with an external system you do not control. When
you *do* control the source, fix the source. See §4 Cross-Boundary
Communication.

Jonathan Blow frames this as a language-substrate argument: a source
representation should not matter because the machine runs a backend
representation. Piling adapters over a wrong abstraction (his example:
JavaScript and the DOM) is the smell; the right fix is a language-agnostic
substrate. The general principle — fix the source — is uncontested; Blow's
framing is specific to language substrates.

---

## Events are usually just a queue

For scripted sequential actions — do X, pause, wait for a result, call a
subroutine — write serial code. If the sequence must span frames or
asynchronous boundaries, put it on a thread.

For "run a function when a variable changes," decide deliberately:

1. Is polling each frame acceptable? If yes, poll.
2. If you must react sooner, *exactly when* in the frame does the handler
   fire? Code that reacts at arbitrary times will produce crashes or
   ordering bugs — you would only write it by assuming code magically runs
   on change.

This reinforces the Domain Events caution in §5 of the main skill: events
used for synchronous in-process calls that should just be function calls add
indirection without benefit. Jonathan Blow argues against event systems as a
general architectural pattern for this reason.
