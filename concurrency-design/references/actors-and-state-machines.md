# Actors and State Machines

Read this when designing the unit of concurrency — the thing that runs
independently, owns state, and can crash without corrupting its neighbors.
Covers the actor/isolate model, state machine encoding as an alternative to
coroutines, shared-nothing as an architectural constraint, and comparisons
with CSP channels and async/await.

---

## The Actor / Isolate Model

An actor (called an *isolate* in some systems) is the minimal unit of
concurrent execution with these properties:

1. **Private state**: no other actor can read or write its state directly.
2. **Mailbox**: receives messages asynchronously; processes them one at a time.
3. **Sequential processing**: messages are handled sequentially within the
   actor. No internal concurrency, no locks needed.
4. **Location transparency**: sending a message to an actor looks the same
   whether the actor is on the same thread, a different core, or a remote
   machine.

The actor model eliminates data races *by construction*. There is no shared
mutable state to race on. The only way to affect another actor's state is to
send it a message, which it processes at its own pace.

### Mailbox semantics

Messages arrive in the mailbox in the order they were sent from a single
sender. Ordering between messages from *different* senders is not guaranteed
unless the system provides it explicitly (e.g., a sequencer actor).

The mailbox is bounded in well-designed systems. An unbounded mailbox is an
unbounded buffer — it hides backpressure and causes unbounded memory growth
under load. When the mailbox is full, the sender should block, drop, or
receive an error.

### Canonical implementations

- **Erlang/Elixir processes**: the original actor model. Processes are cheap
  (a few hundred bytes), preemptively scheduled, and supervised by OTP
  supervision trees. Millions of processes per node is normal.
- **Tina isolates (Odin)**: thread-per-core actors with explicit cross-shard
  messaging. Each isolate runs on a specific shard; cross-shard messages are
  routed through lock-free queues.
- **Pony actors**: actors with a reference capability system that statically
  prevents sharing mutable state. The compiler enforces the shared-nothing
  constraint.
- **Akka actors (JVM)**: actor framework for Java/Scala. Heavier than Erlang
  processes but provides location transparency across a cluster.

---

## Shared-Nothing as an Architectural Constraint

Shared-nothing means: no actor holds a pointer to another actor's data. All
communication is by value (copy) or by transferring ownership.

This is not just a performance optimization — it is a correctness constraint.
When data is shared by pointer, the invariants of that data become a global
concern: every actor that holds a pointer is a potential writer, and every
write must be coordinated. Shared-nothing makes invariants local: an actor's
state is only modified by the actor itself, in response to messages it
processes.

**Practical implication**: when designing message types, ask "is this a copy
or a transfer?" If it's a copy, both sender and receiver have independent
copies — no coordination needed. If it's a transfer (ownership moves to the
receiver), the sender must not use the data after sending. Pony's reference
capabilities enforce this statically; most other systems rely on convention.

---

## Cooperative Scheduling via Effects

Coroutines (async/await, generators) achieve concurrency by suspending
mid-function and resuming later. This has a hidden cost: the suspended
function's stack frame must be preserved, and the suspension point is an
implicit state machine encoded in the compiler's generated code.

The "colored function" problem is a symptom: once a function is async, every
caller must also be async. The async color propagates up the call stack.

**State machine encoding** is an alternative that avoids both problems:

Instead of suspending mid-function, encode the actor's progress as an
explicit state enum. Each state represents a point in the computation. The
actor processes one message, transitions to the next state, and returns. The
scheduler calls back when the next event arrives.

```
// Conceptual state machine for a request handler
State :: enum {
    Waiting_For_Request,
    Reading_Body,
    Processing,
    Sending_Response,
    Done,
}

// Each call to handle() processes one event and returns the next state
handle :: proc(actor: ^Handler, event: Event) -> State {
    switch actor.state {
    case .Waiting_For_Request:
        if event is Request_Arrived {
            actor.request = event.request
            return .Reading_Body
        }
    case .Reading_Body:
        if event is Body_Chunk {
            append(&actor.body, event.chunk)
            if event.last_chunk { return .Processing }
            return .Reading_Body
        }
    case .Processing:
        actor.response = compute_response(actor.request, actor.body)
        return .Sending_Response
    // ...
    }
}
```

**Advantages over coroutines**:
- No hidden stack frames. The state is explicit in the enum.
- No colored functions. `handle` is a plain function; callers don't need to
  be async.
- Serializable: the state enum can be written to disk and restored. This
  enables checkpointing and replay.
- Testable: inject any sequence of events and verify state transitions.

**Disadvantages**:
- More verbose for simple sequential logic. A coroutine that reads three
  values in sequence is three lines; the equivalent state machine is a
  multi-case switch.
- Requires discipline to avoid implicit state in local variables. All
  persistent state must live in the actor struct, not on the stack.

The right choice depends on the complexity of the interaction. For simple
request-response handlers, coroutines are fine. For complex multi-step
protocols with many intermediate states, explicit state machines are more
maintainable.

---

## Actors vs CSP Channels vs Async/Await

These three models solve the same problem (coordinating concurrent work) with
different tradeoffs.

### Actor model

- Communication is *to an actor* (addressed by identity).
- The actor decides when to process each message.
- Backpressure is the actor's mailbox capacity.
- Fault isolation is per-actor: a crashed actor doesn't affect others.
- Best for: long-lived stateful entities (user sessions, game entities,
  connection handlers).

### CSP (Communicating Sequential Processes) — Go channels

- Communication is *through a channel* (no actor identity).
- Both sender and receiver must be ready (synchronous) or the channel buffers
  (buffered channels).
- Backpressure is natural: a full buffered channel blocks the sender.
- Fault isolation is weaker: a panicking goroutine kills the program unless
  explicitly recovered.
- Best for: pipelines, fan-out/fan-in patterns, producer-consumer with
  natural flow control.

### Async/await

- Communication is through futures/promises.
- Execution is cooperative: a task suspends at `await` points.
- Backpressure requires explicit mechanisms (semaphores, bounded channels).
- Fault isolation depends on the runtime (Tokio tasks can be aborted; Python
  asyncio tasks can be cancelled).
- Best for: I/O-bound code where the async overhead is acceptable and the
  colored function problem is manageable.

### Decision table

| Need | Model |
|---|---|
| Long-lived stateful entities with independent lifecycles | Actors |
| Pipeline processing with natural backpressure | CSP channels |
| I/O-bound code in an existing async ecosystem | Async/await |
| Maximum fault isolation | Actors (Erlang processes) |
| Simplest possible concurrent pipeline | CSP channels (Go) |
| Avoiding colored functions entirely | State machine encoding |

---

## Worked Example: Connection Handler as State Machine

A TCP connection handler that reads a request, processes it, and sends a
response. Implemented as a state machine actor.

```
Connection_State :: enum {
    Reading_Header,
    Reading_Body,
    Dispatching,
    Writing_Response,
    Closing,
}

Connection :: struct {
    state:        Connection_State,
    fd:           int,
    header_buf:   [512]byte,
    header_len:   int,
    body_buf:     [dynamic]byte,
    response:     []byte,
    bytes_sent:   int,
}

// Called by the event loop when the fd is readable/writable
connection_handle :: proc(conn: ^Connection, event: IO_Event) -> bool {
    switch conn.state {
    case .Reading_Header:
        n := read(conn.fd, conn.header_buf[conn.header_len:])
        conn.header_len += n
        if header_complete(conn.header_buf[:conn.header_len]) {
            conn.state = .Reading_Body
        }
    case .Reading_Body:
        chunk := read_chunk(conn.fd)
        append(&conn.body_buf, ..chunk)
        if body_complete(conn) {
            conn.state = .Dispatching
        }
    case .Dispatching:
        conn.response = dispatch(conn.header_buf[:conn.header_len], conn.body_buf[:])
        conn.bytes_sent = 0
        conn.state = .Writing_Response
    case .Writing_Response:
        n := write(conn.fd, conn.response[conn.bytes_sent:])
        conn.bytes_sent += n
        if conn.bytes_sent == len(conn.response) {
            conn.state = .Closing
        }
    case .Closing:
        close(conn.fd)
        return false  // done
    }
    return true  // keep going
}
```

All state is in `Connection`. No hidden stack frames. The event loop calls
`connection_handle` whenever the fd is ready. The function returns `false`
when the connection is done, signaling the loop to remove it.

This pattern is used by nginx, Redis, and Seastar internally — it's the
foundation of high-performance event-driven servers.
