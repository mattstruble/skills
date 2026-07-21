# Guardrails and Safety

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## Defense in Depth

No single guardrail is sufficient. Each layer catches what the previous missed.
An agent that relies on one mechanism — a single safety classifier, or a single
confirmation prompt — will fail when that mechanism is bypassed, confused, or
simply wrong.

Layer guardrails across input, execution, and output. Treat each layer as
independently necessary, not as a backup for the others.

---

## Constrain / Verify / Correct → Layer Mapping

The three harness functions map onto the three guardrail layers:

| Harness Function | Primary Layer | Secondary Layer |
|---|---|---|
| **Constrain** | Input-side (prevent bad requests) | Execution-side (tool permissions, fail-safe defaults) |
| **Verify** | Execution-side (tool result validation) | Output-side (PII, content checks) |
| **Correct** | Output-side (retry, continuation, fallback) | — |

---

## Input-Side Guardrails (Constrain)

Input-side guardrails run before the model sees the request. Their job is to
prevent bad inputs from reaching the model at all.

### Relevance Classifiers

Reject requests that are outside the agent's intended scope before spending
inference budget on them. A customer-service agent that receives a request to
write poetry should reject it at the input layer, not after the model has
processed it.

### Safety Classifiers — Jailbreak vs Prompt Injection

These are distinct threats with different mitigations:

**Jailbreak.** The user directly attempts to bypass the agent's restrictions.
The attacker is the user; the attack surface is the user's own input. Common
patterns: role-play instructions ("pretend you have no restrictions"),
instruction overrides ("ignore previous instructions"), and social engineering.
Mitigation: classifier trained on jailbreak patterns, hard rule-based blocks
for known patterns, and system prompt hardening.

**Prompt injection.** An attacker embeds malicious instructions in external
data that the agent reads — a document, a web page, a database record, a tool
result. The user may be entirely innocent; the attack arrives through the
agent's environment. This is the more dangerous threat for agents with broad
tool access, because the agent may faithfully execute the injected instruction
believing it came from a legitimate source.

Mitigation for prompt injection: treat all external data as untrusted. Apply
input isolation — the model should not be able to act on instructions embedded
in tool results without explicit authorization. Classifiers that detect
instruction-like patterns in external data. Sandboxing tool execution so that
injected instructions cannot reach high-risk tools.

### Content Moderation

Filter harmful content categories at ingress: violence, self-harm, illegal
activity, and similar. This is a baseline, not a complete safety strategy.

### Rule-Based Protections

Hard blocks that cannot be overridden by the model or by user input. These
are the last line of input-side defense and should cover the highest-risk
categories unconditionally. Examples: never process requests involving
specific prohibited content categories, always require authentication before
accessing user data.

---

## Execution-Side Guardrails (Constrain + Verify)

Execution-side guardrails govern what the agent can do and whether it did it
correctly.

### Tool Risk Rating

Rate every tool call before execution. Three dimensions:

- **Reversibility.** Can the action be undone? Reading data is reversible;
  deleting it is not. Sending a message is not reversible once delivered.
- **Permission level.** What access does the tool require? Read-only access
  to user data is lower risk than write access to system configuration.
- **Financial impact.** Does the action spend money, modify billing, or
  trigger a chargeable event?

Map these dimensions to a risk level:

| Risk Level | Characteristics | Required Action |
|---|---|---|
| Low | Reversible, read-only or scoped write, no financial impact | Execute without confirmation |
| Medium | Partially reversible, broader write access, minor financial impact | Log and monitor; confirm on anomaly |
| High | Irreversible, system-level access, or significant financial impact | Require explicit confirmation before execution |

### Dynamic Risk Rating

Risk is parameter-dependent, not tool-dependent. The same tool can be
low-risk or high-risk depending on what it's called with.

`delete_file(normal_file)` = low-risk (user file, recoverable from backup).
`delete_file(system_file)` = high-risk (system integrity, potentially
unrecoverable).

A static per-tool risk rating will misclassify these. The harness must
evaluate risk at call time, inspecting the actual parameters, not just the
tool name.

**Implementation pattern:** Each tool call passes through a risk evaluator
that inspects the tool name and parameters against a set of risk rules. The
evaluator returns a risk level. The harness routes high-risk calls to a
confirmation step before execution.

### Tool Result Validation (Verify)

After a tool executes, validate the result before the model uses it. Checks:

- **Schema conformance.** Does the result match the expected structure?
- **Consistency.** Does the result contradict known state? (A refund result
  showing a larger amount than the original order is a signal to halt.)
- **Completeness.** Is the result truncated or partial in a way that would
  mislead the model?

Failed validation should not be silently passed to the model. Route to the
Correct layer.

---

## Output-Side Guardrails (Verify + Correct)

Output-side guardrails run after the model has produced a response but before
it reaches the user.

### PII Filters

Strip or redact personal data from outputs. This applies even when the agent
legitimately accessed PII during execution — the output to the user should
contain only what the user is authorized to see and what is necessary for the
response.

### Output Validation

Check outputs for:

- **Brand alignment.** Does the response match the agent's intended persona
  and tone?
- **Factual consistency.** Does the response contradict information in the
  context or tool results?
- **Format compliance.** If the output is structured (JSON, a form, a
  specific template), validate the structure before returning it.

### Correct Layer — Retry, Continuation, Fallback

When verification fails or output validation rejects a response:

**Silent retry.** On transient failures (tool timeout, malformed output),
retry before surfacing an error. Most transient failures resolve on the first
retry. Set a retry limit — typically 2-3 attempts — before escalating.

**Continuation generation.** If the model's output is incomplete (truncated
mid-sentence, partial JSON), prompt for continuation rather than failing.
This handles context-length edge cases and model output truncation.

**Fallback to human (circuit breaker).** When retries are exhausted or the
failure is non-transient, escalate to a human operator. Log the full
trajectory so the operator has context. This is the final backstop — it must
always exist. An agent with no human fallback path will eventually fail
silently.

---

## Human-in-the-Loop (HITL)

HITL is not a sign of an immature agent. It is a required component of any
agent that takes consequential actions, and it remains relevant even in mature
deployments for high-risk operations.

### When to Trigger HITL

**Failure threshold exceeded.** Track the agent's error rate in a session or
over a time window. When the rate exceeds a defined threshold, pause and
escalate. This catches systematic failures before they compound.

**High-risk operation pending.** Before executing any high-risk tool call,
require human confirmation. This is non-negotiable in early deployment and
should remain in place for the highest-risk operations indefinitely.

**Ambiguous state.** When the agent reaches a state where it cannot determine
the correct next action — contradictory tool results, missing required
information, conflicting constraints — escalate rather than guess.

### HITL in Early Deployment

During the initial deployment period, HITL thresholds should be conservative.
The goal is to build a dataset of real-world agent behavior and to catch
failure modes that didn't appear in testing. As confidence is established —
measured by observed error rates and human reviewer agreement — thresholds
can be relaxed.

The escalation path must always exist, even after thresholds are relaxed.
Removing the human fallback entirely is a design error.

### HITL Interface Design

The human reviewer needs:

- The full trajectory up to the escalation point
- The specific action or decision that triggered escalation
- Clear options: approve, reject, modify, or hand off to a specialist

A HITL interface that dumps raw model output without context is not useful.
Design it for the reviewer's decision, not for the engineer's debugging.
