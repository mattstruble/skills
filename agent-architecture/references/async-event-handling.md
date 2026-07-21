# Async Event Handling

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

The runtime mechanism for handling asynchronous events in agent systems.
Covers structured event modeling, the three processing strategies, trajectory
integrity rules, and the sync-to-async engineering pattern.

→ See [agent-tool-design/references/tool-categories.md](../../agent-tool-design/references/tool-categories.md) for event-triggered and user-communication tool interface design.

---

## Structured Event Modeling

Every input is modeled as a structured event with four dimensions:

| Dimension | What it captures | Examples |
|---|---|---|
| **Source** (who) | Origin of the event | user, contact, stranger, system notification |
| **Channel** (how) | Delivery medium | phone, SMS, IM, email, timer, tool result, CLI monitor |
| **Content** (what) | Payload semantics | text, emotional tone, urgency, whether reply needed |
| **Context** (background) | Relationship to current state | reply to prior conversation vs new; relevance to active task |

Modeling inputs as structured events rather than raw strings enables the
routing logic below — the strategy applied depends on source, urgency, and
relationship to the current trajectory.

---

## Three Processing Strategies

### 1. Cancellation-based (urgent events)

Stop the current operation, drain the pending queue, append all queued events
plus the urgent event to the trajectory, and re-invoke the LLM.

Steps:
1. Cancel the in-flight streaming LLM call or tool execution
2. Drain the event queue
3. Append all pending events + the urgent event to the trajectory
4. Re-invoke the LLM with the updated trajectory

**Example:** User says "Stop!" during an operation that is producing incorrect
results. The agent must abandon the current path immediately.

### 2. Queue-based (routine events)

Add the event to a queue without interrupting the current operation. When the
current tool call returns, check the queue, append all queued events at once,
then let the LLM process the updated trajectory.

Steps:
1. Enqueue the event
2. Continue current operation to completion
3. On tool-call return: drain queue, append all events to trajectory
4. LLM processes the full updated trajectory in the next cycle

**Example:** User sends supplementary information while a long data analysis
task is running. The new information should be incorporated at the next natural
checkpoint, not mid-execution.

### 3. Parallel (independent events)

Tag the event as independent of the current task. Spawn a separate LLM call
to handle it. The result goes directly to the user without affecting the main
trajectory.

Steps:
1. Identify event as independent
2. Spawn a separate LLM invocation with the event as its only context
3. Return the result to the user
4. Main trajectory continues unaffected

**Example:** User asks about the weather while a data analysis task runs.
The weather query is fully independent — it can be answered in parallel
without touching the main task state.

---

## Event Routing

Hardcoded routing rules have a fundamental limitation: the correct strategy
depends on event semantics, not just event type. A message from the user can
be urgent ("Stop, that's wrong") or routine ("here's some extra context") —
the same source, different strategy.

**Recommended approach:** a lightweight classification LLM as event router.
The router reads the event and current agent state, then assigns a strategy.

**Priority categories:**

| Priority | Event types |
|---|---|
| Urgent | `user.interrupt`, `supervisor.instruction`, `agent.interrupt` |
| Non-urgent | Regular `user.input`, `tool.result`, `timer.trigger` |

---

## Five Rules for Trajectory Integrity

These rules keep the trajectory in a valid format across all three strategies,
so the LLM always receives a well-formed context regardless of interruption
timing.

1. **Immediate assistant-message write.** Tool calls are written to the
   trajectory immediately upon emission — before the tool result returns.
   This prevents gaps if an interruption arrives while the tool is executing.

2. **Async tool results as new events.** Tool results that arrive
   asynchronously are appended as new events, not inserted retroactively.
   Trajectory order is append-only.

3. **Interruption during tool execution.** Generate a placeholder tool result
   (`"Tool executing in background, prioritize new event"`), append it to the
   trajectory, append the interrupting event, then re-invoke the LLM. The
   trajectory format stays valid; the LLM knows the tool is still running.

4. **Interruption during LLM thinking.** Discard the current thinking output
   entirely. Append the new event. Start a fresh LLM invocation. Partial
   reasoning is not appended — it would corrupt the trajectory with an
   incomplete assistant turn.

5. **Non-interrupting events stay queued.** Events that do not interrupt are
   appended only after the current cycle completes. This prevents mid-cycle
   trajectory mutations that would invalidate the in-flight LLM call.

---

## Attention Dispersion in Batch Events

When multiple events are appended to the trajectory at once, models tend to
focus on the last event and underweight earlier ones. Three mitigations:

**Prompt instruction.** Explicitly instruct the model to consider all queued
events comprehensively before responding.

**Status bar markers.** Prefix each queued event with a positional marker:

```
[Unprocessed Event 1/4] <event content>
[Unprocessed Event 2/4] <event content>
[Unprocessed Event 3/4] <event content>
[Unprocessed Event 4/4] <event content>
```

**Batch summary.** Prepend a summary line before the batch:

```
4 unprocessed events above, including 1 tool result, 2 user messages, 1 system reminder.
```

The summary gives the model a count and composition before it reads the
individual events, reducing the recency bias.

---

## Sync-to-Async Engineering Pattern

Current synchronous LLM APIs require the harness to simulate async behavior
through prompt engineering: placeholder injection for interrupted tools,
event queuing to serialize concurrent inputs, status markers to counteract
attention dispersion.

Bojie Li argues this engineering is "using prompt engineering to compensate
for shortcomings of model training — a temporary expedient." Three capabilities
next-generation models need to acquire through reinforcement learning:

1. **Understanding async interleaving** — reasoning correctly about
   trajectories where events arrive out of order relative to the operations
   that triggered them
2. **Resuming interrupted tasks** — picking up a partially-completed task
   after an interruption without losing the prior state
3. **Comprehensive batch processing** — attending to all events in a batch
   with equal weight, not just the last one

"Orchestration makes the behavior possible; training makes the behavior good."

The implication for current harness design: the engineering patterns above
are load-bearing today and should be implemented correctly, but they are
designed to be replaced as model training catches up.
