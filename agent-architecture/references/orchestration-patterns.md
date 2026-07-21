# Orchestration Patterns

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## Workflow Pattern

A workflow is a fixed code path where the execution sequence is determined by
the developer, not the model. The LLM runs inside individual nodes — it
generates text, classifies, or extracts — but the transitions between nodes
are controlled by code.

**Strengths:**

- **Strict process control.** Every execution follows the same path. Auditing
  is straightforward because the sequence is known in advance.
- **Confined attack surface.** A prompt injection or adversarial input in one
  node cannot redirect the agent to a different node — the code controls what
  happens next. The blast radius of a compromised node is limited to that node.
- **Predictable cost and latency.** The number of inference calls is fixed.
  Budget and SLA are easy to reason about.
- **Easier testing.** Each node can be tested in isolation. The integration
  test only needs to verify the transitions.

**Limitations:**

- **Lack of flexibility.** New execution paths require code changes. The
  workflow cannot adapt to situations the developer didn't anticipate.
- **Brittle at the edges.** When real-world inputs don't match the expected
  shape, the workflow either fails or requires explicit error branches for
  every case.

**When to use:** Tasks with well-understood, stable steps. Compliance-sensitive
processes where auditability is required. Any situation where the cost of an
unexpected execution path is high.

---

## Autonomous Agent Pattern

An autonomous agent lets the model decide the execution path at runtime. Given
a goal and a set of tools, the model plans, acts, observes results, and adapts
until it reaches a stopping condition.

**Strengths:**

- **Handles novel situations.** The agent can discover that it needs an
  additional step, recover from unexpected tool results, and adjust its plan
  without developer intervention.
- **Flexible task decomposition.** Complex tasks that resist enumeration up
  front are natural fits — the agent figures out the sub-steps as it goes.

**Limitations:**

- **Errors compound.** A wrong decision early in the trajectory can cascade.
  The agent may confidently pursue an incorrect path for many steps before
  failing or producing a wrong result.
- **Higher cost and latency.** Each reasoning step is an inference call.
  Long-horizon tasks can require many rounds, multiplying both cost and
  end-to-end time.
- **Harder to audit.** The execution path varies across runs. Reproducing a
  failure requires capturing the full trajectory.
- **Requires explicit stopping conditions.** Without them, the agent will loop.

### Stopping Condition Design

Every autonomous agent needs all three stopping conditions. Omitting any one
creates a failure mode:

**Task-complete signal.** Define a concrete, verifiable condition the model
can assert. Vague goals ("do your best") produce agents that never stop.
The signal should be checkable by code, not just by the model's self-report —
models can hallucinate completion.

**Max iterations.** A hard ceiling enforced by the harness, not the model.
Set it based on the expected number of steps for the task, with headroom for
recovery attempts. When the ceiling is hit, the harness should log the
trajectory and escalate rather than silently fail.

**Unrecoverable error.** An explicit exit path for states the agent cannot
resolve: tool unavailable, required data missing, contradictory constraints.
The harness catches these and routes to a fallback — human escalation, a
simplified workflow, or a graceful error response.

**Circuit-breaker pattern.** Track consecutive failures within a run. If the
agent fails the same step N times in a row, treat it as unrecoverable rather
than retrying indefinitely. This prevents budget exhaustion on stuck agents.

---

## Mixing Patterns

Most production systems combine both. The decision boundary is risk and
flexibility:

- **Compliance-critical or high-risk steps** → workflow. The code controls
  the transition; the model cannot deviate.
- **Flexible decision steps** → autonomous agent. The model adapts to what
  it finds.

**Example structure:** A document-processing pipeline uses a workflow for
ingestion, classification, and routing (fixed, auditable). Within the
"complex document" branch, an autonomous agent handles extraction and
reconciliation (flexible, adapts to document structure). The workflow
re-takes control for the final write and notification steps.

The boundary between workflow and autonomous should be explicit in the code.
Implicit mixing — where it's unclear which layer is in control — is a common
source of hard-to-debug failures.

---

## Framework Pattern Families

No product names — these are durable categories. Evaluate any specific tool
against the pattern family it belongs to.

| Family | What it provides | Best fit |
|---|---|---|
| **Deterministic-workflow engines** | DAG or state-machine execution, explicit node transitions, built-in retry and error handling | Compliance workflows, ETL pipelines, any task where the path is known |
| **Autonomous-loop SDKs** | ReAct loop scaffolding, tool registration, trajectory management | Single-agent tasks requiring flexible planning |
| **Visual / low-code platforms** | Drag-and-drop workflow builders, pre-built connectors | Rapid prototyping, non-engineer builders, simple automation |
| **Multi-agent orchestration frameworks** | Agent-to-agent communication, role assignment, shared memory | Tasks requiring parallel specialization or peer review |
| **All-in-one platforms** | Hosted infrastructure, model routing, built-in guardrails, observability | Teams that want managed infrastructure over framework flexibility |

**Selection heuristic:** Match the framework family to the orchestration
pattern you've chosen, not the other way around. Choosing a framework first
and then designing the orchestration to fit it inverts the decision.

---

## Latency and Cost Trade-offs

Autonomous agents trade latency and cost for task performance. The trade is
not always worth it.

**Latency arithmetic.** End-to-end time = inference rounds × per-round time.
A task that requires 20 rounds at 3 seconds per round takes 60 seconds minimum
before any tool execution time. For interactive use cases, this is often
unacceptable. Workflow alternatives that use fewer inference calls are worth
evaluating even if they require more upfront engineering.

**Cost arithmetic.** Each inference call has a token cost. Long trajectories
with large context windows (the full trajectory is in context each round) can
cost orders of magnitude more than a single well-crafted prompt. Measure
before committing to an autonomous approach.

**When the trade is worth it.** The autonomous agent's flexibility pays off
when: the task genuinely cannot be enumerated in advance, the value of
successful completion is high relative to the cost, and the failure mode of
a rigid workflow (breaking on unexpected inputs) is worse than the failure
mode of an autonomous agent (compounding errors, higher cost).

**When it isn't.** If a workflow with a few conditional branches covers 95%
of real inputs, the autonomous agent's flexibility is buying coverage for
the 5% at the cost of the 95%. Build the workflow first; add autonomous
handling only for the cases the workflow cannot reach.
