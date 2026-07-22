---
name: agent-architecture
description: You MUST consult this skill when designing or reviewing any system where an LLM drives execution. Trigger when deciding whether to build an agent at all, choosing workflow vs autonomous orchestration, selecting a model, or adding guardrails. Also trigger when an agent loops forever, fires irreversible actions without confirmation, or works in demos but fails in production. NOT for code-level design (see software-design), tool interface depth (see agent-tool-design), or structuring application code regardless of whether an LLM is involved (see application-architecture).
---

# Agent Architecture

**The harness — not the model — is where production agents succeed or fail.**

Every decision below starts with a YAGNI gate. Agents add real cost and
complexity; apply them only when the problem demands them.

---

## Framing — The Harness Model

A minimal agent is `Agent = LLM + Context + Tools`. A production agent adds
three more functions: `+ Constrain + Verify + Correct = Model + Harness`.

| Function | One-Sentence Responsibility | Core Principle |
|---|---|---|
| **Context** | Provides the information the model needs to decide | Information Sufficiency |
| **Tools** | Provides the means of action | Clear Interface (ACI) |
| **Constrain** | Sets behavioral boundaries before execution | Fail-Safe Defaults |
| **Verify** | Judges whether an operation produced a correct result | Input Isolation |
| **Correct** | Fixes or rolls back on failure | Don't surface unconfirmed failures |

**Refund-agent example.** Without a harness: the agent hallucinates a policy
it wasn't given, calls a refund tool with no amount cap, skips verification,
and the user discovers the failure themselves. With a harness: the 7-day
policy lives in Context so the model reasons from fact; `query_order` and
`process_refund` are the only Tools exposed; Constrain caps the refund at the
original order total; Verify checks the result against the database record;
Correct retries on timeout and escalates to a human if retries fail. All five
functions are load-bearing.

**ReAct loop.** At runtime the model iterates: reason about the current state,
act by calling a tool, observe the result, then append the observation to the
trajectory and reason again. The trajectory is the agent's working memory
across steps — it accumulates context that informs every subsequent decision.

Bojie Li argues the harness — not the model — is the durable competitive
advantage, as model capability commoditizes and competitive differentiation
shifts to the engineering outside the model.

---

## Framing — Effective Agent Principles

Three principles that apply before any decision point:

**Keep it simple.** A direct API call with a well-crafted prompt beats a
framework that obscures what's happening. Clear code that a teammate can read
and debug is worth more than a clever abstraction that hides the model
interaction.

**Keep it transparent.** Planning steps, tool calls, and decision trajectories
must be visible — to operators during development and to monitoring in
production. Transparency is the precondition for trust and the prerequisite
for debugging.

**Design a good ACI (Agent-Computer Interface).** Poka-yoke: design out
misuse so the error cannot happen. Tool names should be intuitive, parameters
unambiguous, and side effects explicit. If a tool name requires a comment to
explain what it does, rename the tool.

---

## Symptom Table

| Symptom | Decision Point |
|---|---|
| Agent loops forever or over-executes | §1 — stopping conditions |
| Autonomous agent where fixed steps would suffice | §1 — orchestration |
| Can't reliably complete multi-step tasks | §2 — non-reasoning model |
| High end-to-end latency across many inference rounds | §2 — output speed |
| Irreversible action fired with no confirmation | §3 — execution-side guardrail / HITL |
| Half-finished or hallucinated result shown to user | §3 — Verify/Correct |
| Demo works, production fragile | Framing — no harness |
| Agent can't handle user interruptions mid-task | §4 — async event handling |
| Background tasks block the agent loop | §4 — async event handling |

---

## §1 Do You Need an Agent? (Orchestration & Autonomy)

**The question**: Does this task require an LLM to decide the execution path,
or can code decide it?

### YAGNI Ladder

Start at the top. Escalate only when the rung above cannot handle the task.

1. **Single LLM call** — one prompt, one response. Covers most tasks.
2. **Workflow** — fixed code path; LLM runs inside individual nodes. The code
   decides what happens next.
3. **Autonomous agent** — LLM decides the execution path at runtime. Use when
   the path cannot be known in advance.
4. **Mixed** — critical or compliance-sensitive steps as workflow; flexible
   decision steps as autonomous.

"Start simple, escalate only when forced."

### Workflow vs Autonomous

| Criterion | Workflow | Autonomous Agent |
|---|---|---|
| Execution path | Fixed in code | Decided by the model at runtime |
| Control | Deterministic, auditable | Flexible, harder to audit |
| Security | Attack surface confined to one node | Broader — model can invoke any tool |
| Flexibility | Low — new paths require code changes | High — adapts to novel situations |
| Cost / latency | Lower | Higher — more inference rounds |

### Stopping Conditions (mandatory for autonomous agents)

Every autonomous agent must have all three:

- **Task-complete signal** — explicit condition the model can assert
- **Max iterations** — hard ceiling; never rely on the model to stop itself
- **Unrecoverable error** — exit path when the agent cannot proceed

An agent without stopping conditions will loop until it exhausts budget or
corrupts state.

**Flight-booking example.** Workflow: four fixed nodes — verify identity →
search flights → process payment → send confirmation. The code controls every
transition. Autonomous: the agent figures out the path as it goes, discovers
it needs to log in first, adjusts when the outbound flight is cancelled and
rebooks via a connection. Workflow is right when the steps are known; autonomous
is right when the agent must adapt to what it finds.

-> Read `references/orchestration-patterns.md` for deeper trade-offs, mixing
patterns, stopping-condition design, and framework pattern families.

---

## §2 Model Selection

**The question**: Which model capability profile fits this agent's task?

Four durable axes — no product names, because models iterate faster than any
recommendation:

**Reasoning-required gate.** The vast majority of agents need a reasoning
model. Exceptions: single simple step, fixed-position GUI click. If the agent
must plan, decompose, or recover from unexpected states, use a reasoning model.

**Output speed.** Multi-round agent latency = rounds × per-round time. Slower
output directly extends end-to-end wait. *A 20-round agent task 2s slower per
round = +40s end-to-end.* For interactive agents, output speed is a first-class
requirement.

**Multimodal.** Hard requirement if the agent processes images, audio, or
video. Not optional — a text-only model cannot handle these inputs.

**Open vs closed.** Closed frontier models lead on capability. Open models
enable privacy, cost control, and customization (fine-tuning, local
deployment). Evaluate the trade on your actual task. For post-training
decisions (when/whether to fine-tune, SFT vs RL), see `agent-post-training`.

"Evaluate on your own tasks — benchmarks don't transfer."

Durability caveat: these axes are stable; specific model versions are not.
Revisit model choice when capability or cost changes materially.

-> Read `references/real-time-thinking.md` for fast/slow thinking decomposition (when to decouple interaction from reasoning), cascade vs end-to-end tradeoffs, and the God's-eye-view labeling problem.

---

## §3 Guardrails & Safety

**The question**: How do you prevent the agent from doing the wrong thing?

Operationalizes Constrain, Verify, and Correct from the harness model.

**Defense in depth.** No single guardrail is sufficient. Each layer catches
what the previous missed. Layer them.

### Input-side (Constrain)

- **Relevance classifiers** — reject off-topic requests before they reach the model
- **Safety classifiers** — two distinct threats:
  - *Jailbreak*: the user directly attempts to bypass restrictions
  - *Prompt injection*: an attacker embeds malicious instructions in external data the agent reads (a document, a web page, a tool result)
- **Content moderation** — filter harmful content at ingress
- **Rule-based protections** — hard blocks that cannot be overridden by the model

### Execution-side (Constrain + Verify)

Tool risk rating drives confirmation requirements. Rate each tool call on:

- **Reversibility** — can the action be undone?
- **Permission level** — what access does it require?
- **Financial impact** — does it spend money or modify billing?

Risk must be **dynamic, not per-tool**. *Same tool, parameter-dependent risk:
`delete_file(normal_file)` = low-risk; `delete_file(system_file)` = high-risk.*
High-risk operations require explicit confirmation before execution.

### Output-side (Verify + Correct)

- **PII filters** — strip personal data before returning to the user
- **Output validation** — check for brand alignment, factual consistency, and
  format compliance
- **Silent retry** — on transient failure, retry before surfacing an error
- **Continuation generation** — if output is incomplete, continue rather than
  fail
- **Fallback to human** — circuit breaker when retries are exhausted

### Human-in-the-Loop

HITL is not optional in early deployment. Trigger human oversight when:

- Failure rate exceeds a defined threshold
- A high-risk operation is about to execute
- The agent reaches an ambiguous state it cannot resolve

As confidence is established, HITL thresholds can be relaxed — but the
escalation path must always exist.

-> Read `references/guardrails-and-safety.md` for the full taxonomy, C/V/C
layer mapping, tool risk-rating mechanics, and HITL trigger design.

---

## §4 Async Event Handling

**The question**: How does the agent handle events that arrive while it is
already executing?

Synchronous LLM APIs require the harness to manage concurrency explicitly.
Three strategies cover the space:

- **Cancellation-based** — urgent events (user interrupt, supervisor
  instruction): cancel the in-flight operation, drain the queue, append all
  events + the urgent event, re-invoke.
- **Queue-based** — routine events (supplementary user input, timer): enqueue
  without interrupting; append the batch when the current cycle completes.
- **Parallel** — independent events (unrelated user question): spawn a
  separate LLM call; result goes to the user without touching the main
  trajectory.

Hardcoded routing rules are insufficient — event semantics determine the
strategy. Use a lightweight classification LLM as event router.

**Trajectory integrity** across all three strategies requires five rules:
write assistant messages immediately upon emission; append async tool results
as new events; inject placeholder tool results on interruption; discard
partial LLM thinking on interruption; hold non-interrupting events in queue
until the current cycle completes.

-> Read `references/async-event-handling.md` for the full event model
(source/channel/content/context), detailed strategy steps, trajectory
integrity rules, attention-dispersion mitigations, and the sync-to-async
engineering pattern.

---

## Routing Map

These are companion skills in the ai-agents family. Load the relevant one
when building that layer.

| Harness Concern | Companion Skill | Source |
|---|---|---|
| Context depth & prompt design | context-engineering | Ch2 |
| Memory & knowledge persistence | agent-memory-rag | Ch3 |
| Tool taxonomy & interface design | agent-tool-design | Ch4 |
| Async event handling | async-event-handling.md | When building agents that handle interruptions, background tasks, or multi-channel events |
| Code generation & coding agents | coding-agent-design | Ch5 |
| Evaluation & observability | agent-evaluation | Ch6 |
| Post-training decisions (when/whether to fine-tune, SFT vs RL) | agent-post-training | Ch7 |
| Post-training implementation (SFT/RL mechanics) | ml-post-training | Ch7 |
| Multi-agent orchestration & collaboration | multi-agent-collaboration | Ch10 |

Self-evolution (Ch8) shipped as `agent-self-evolution`. Ch9 (multimodal & real-time interaction) is deferred as a standalone skill; its three transferable principles are folded here as `references/real-time-thinking.md`.

---

## NOT For

**Litmus**: Is the decision specific to running an LLM in a loop? → here. Is
it how you'd structure any application regardless of whether an LLM is
involved? → `application-architecture`.

**The common confusion case**: Choosing a workflow orchestration pattern
(fixed LLM nodes vs autonomous) is agent-architecture. Wiring those nodes as
deterministic code, queues, or events is application-architecture.

- Code-level design → `software-design`
- API surface conventions → `api-design`
- Infrastructure and deployment → ops skills

---

## References

| Reference | When to read |
|---|---|
| `references/orchestration-patterns.md` | Choosing workflow vs autonomous vs mixed; deeper trade-offs, mixing patterns, stopping-condition mechanics, framework pattern families |
| `references/guardrails-and-safety.md` | Full input/execution/output guardrail taxonomy, C/V/C layer mapping, tool risk-rating mechanics, HITL trigger design, jailbreak vs injection in depth |
| `references/async-event-handling.md` | Structured event modeling, cancellation/queue/parallel strategies, trajectory integrity rules, attention-dispersion mitigations, sync-to-async engineering pattern |
| `references/real-time-thinking.md` | Fast/slow thinking decomposition (decouple interaction from reasoning); cascade vs end-to-end tradeoff and the bottleneck-information principle; God's-eye-view labeling problem in online decision-making |
