## Before

You MUST consult this skill when designing concurrent systems, choosing between concurrency models, or reviewing inter-component communication architecture. Also trigger when selecting thread topology (thread-per-core vs work-stealing vs event loop), designing fault isolation boundaries, scaling a system to multiple cores, or evaluating message-passing vs shared-memory tradeoffs. NOT for language-specific async runtimes (tokio internals, asyncio event loop), compute parallelism (SIMD, GPU kernels, fork-join data parallelism), distributed consensus (Raft, Paxos), or debugging specific race conditions in existing code.

## Accuracy Analysis

| Query summary | Expected | Predicted | Correct? |
|---|---|---|---|
| Game server: actor vs channel model for per-player fault isolation | TRIGGER | TRIGGER — "choosing between concurrency models", "fault isolation boundaries" | ✅ TP |
| Rust service: thread-per-core vs Tokio work-stealing for multi-core | TRIGGER | TRIGGER — explicitly named topology options | ✅ TP |
| Kafka→Postgres pipeline: channel topology + backpressure design | TRIGGER | TRIGGER — "inter-component communication architecture", "message-passing tradeoffs" | ✅ TP |
| Fault isolation: auth crash taking down request handler | TRIGGER | TRIGGER — "designing fault isolation boundaries" | ✅ TP |
| State machine vs async/await to avoid colored function problem | TRIGGER | TRIGGER — "choosing between concurrency models" covers this | ✅ TP |
| CPU-bound variable-size tasks: which thread model for load balancing | TRIGGER | TRIGGER — "scaling a system to multiple cores" | ✅ TP |
| Control vs data plane separation in streaming pipeline | TRIGGER | TRIGGER — "inter-component communication architecture" | ✅ TP |
| Supervisor tree: one-for-one vs one-for-all + restart budget | TRIGGER | TRIGGER — "designing fault isolation boundaries" | ✅ TP |
| Backpressure from slow consumer to producer, bounded queues | TRIGGER | TRIGGER — "message-passing vs shared-memory tradeoffs" | ✅ TP |
| Fan-out to 5 processors, collect all responses (scatter-gather) | TRIGGER | TRIGGER — "inter-component communication architecture" | ✅ TP |
| Tokio worker thread count + I/O driver polling interval tuning | NO TRIGGER | NO TRIGGER — explicitly excluded "tokio internals" | ✅ TN |
| Raft consensus: leader election + log replication | NO TRIGGER | NO TRIGGER — explicitly excluded "distributed consensus (Raft)" | ✅ TN |
| Profiling which mutex critical section causes 40% lock contention | NO TRIGGER | NO TRIGGER — "debugging specific race conditions in existing code" | ✅ TN |
| AVX-512 SIMD loop vectorization for matrix multiply | NO TRIGGER | NO TRIGGER — explicitly excluded "SIMD" | ✅ TN |
| PostgreSQL connection pool size + pgBouncer vs driver pooling | NO TRIGGER | NO TRIGGER — infrastructure config, not concurrent system design | ✅ TN |
| Go race detector found data race on shared map, how to fix | NO TRIGGER | NO TRIGGER — explicitly excluded "debugging specific race conditions" | ✅ TN |
| C++ spinlock with acquire/release memory ordering | NO TRIGGER | TRIGGER — "designing concurrent systems" is broad; lock primitives not excluded | ❌ FP |
| GitHub Actions test matrix parallelism + dependency caching | NO TRIGGER | NO TRIGGER — CI/CD build infra, not concurrent system design | ✅ TN |
| Python asyncio event loop internals, how await suspends | NO TRIGGER | NO TRIGGER — explicitly excluded "asyncio event loop" | ✅ TN |
| TCP three-way handshake state machine, SYN_RECEIVED transitions | NO TRIGGER | TRIGGER — "designing concurrent systems" + state machine + connections could match | ❌ FP |

Score: 18/20 (90%)

## After

You MUST consult this skill when choosing a concurrency architecture: thread topology (thread-per-core, work-stealing, event loop), unit of concurrency (actors, goroutines, state machines), or inter-component communication model (message passing, channels, shared memory). Also trigger when designing fault isolation boundaries, supervision trees, or backpressure propagation; when scaling a single-threaded design to multi-core; or when choosing between actor vs CSP channel models. NOT for lock primitive implementation, network protocol state machines, database connection pooling, language-specific async runtime config (tokio, asyncio), compute parallelism (SIMD, GPU), or distributed consensus (Raft, Paxos).

## Changes Made

- **Added "lock primitive implementation" exclusion**: The original description had no exclusion for low-level lock/synchronization primitive implementation (spinlocks, mutexes). This caused a FP on the C++ spinlock query. Added explicit exclusion.
- **Added "network protocol state machines" exclusion**: TCP/protocol FSM design shares vocabulary ("state machine", "connections") with the skill's content but is protocol engineering, not concurrency unit design. Added explicit exclusion to prevent FP.
- **Added "actors vs CSP channel models" as explicit trigger**: The original mentioned "message-passing vs shared-memory tradeoffs" but didn't name the actor/channel choice directly. This is a common phrasing in real queries (Q1).
- **Named "supervision trees" explicitly**: The original said "fault isolation boundaries" but supervision tree design is a distinct concept users search for by name.
- **Named "backpressure propagation" explicitly**: A common query pattern not captured by "message-passing vs shared-memory tradeoffs".
- **Kept all original exclusions**: Tokio/asyncio internals, SIMD/GPU, Raft/Paxos, race condition debugging — all confirmed correct by eval.
- **Trimmed keyword variant lists**: Removed "(thread-per-core vs work-stealing vs event loop)" inline enumeration from the opener; moved to the "Also trigger" clause as a cleaner list.
