# Tool Categories — Design Patterns

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

Per-category design guidance for the five tool types in the agent taxonomy.

## Perception Tools (read-only, acquire information)

Perception tools observe the world without changing it. Their read-only
nature makes them safe to cache and parallelize — but their output volume
requires active management.

### Bounded output (mandatory)

Never return unbounded data. Every perception tool must support offset/limit
or equivalent pagination. An agent that reads an entire 10MB log file into
context has no room left to reason.

### Explicit truncation

When content is truncated, state how much was omitted and how to read more.
Silent truncation is dangerous: the agent believes it saw everything and
makes decisions on incomplete information.

```
// Bad return value:
{"text": "...first 500 lines of log..."}

// Good return value:
{"text": "...first 500 lines...", "truncated": true,
 "total_lines": 4200, "next_offset": 500,
 "hint": "Call again with offset=500 to read more"}
```

### Output form decision

When a perception tool can return raw image or extracted text, choose based
on content type:

| Content type | Preferred form | Reason |
|---|---|---|
| Pure text (code, logs, prose) | Text extraction | Concise; layout irrelevant |
| Layout-sensitive (tables, forms, diagrams) | Retain image | Spatial structure carries meaning |
| Mixed | Image with text overlay | Preserves both |

Text extraction is cheaper in tokens; image preserves structure the model
can reason about visually. The wrong choice degrades accuracy — a table
extracted as flat text loses column relationships.

### Caching and parallelism

Read-only tools have no side effects, so they are safe to:
- Cache by input hash (avoid redundant fetches)
- Call in parallel (no ordering constraint between reads)

Document cacheability in the tool description so the agent can plan
efficient batches.

---

## Execution Tools (change the external world)

Execution tools are the highest-risk category. A misfire can delete data,
send emails, or spend money. Three implementation-level security layers
apply here. (Strategic policy — what the agent is allowed to do at all —
belongs in agent-architecture guardrails, not in tool implementation.)

### Layer 1: Input validation

Validate at the tool boundary before any execution:

- **Path traversal**: reject `../` sequences and symlinks outside the
  permitted root
- **Injection**: sanitize shell metacharacters before passing to subprocesses
- **SSRF**: for tools accepting URLs or hostnames, validate against an
  allowlist of permitted hosts/schemes; reject private IP ranges
  (10.x, 172.16–31.x, 192.168.x, 169.254.x) and loopback addresses
- **Type correctness**: reject wrong types immediately with a clear error

Fail fast — reject and return an error. Do not "smart correct" invalid input
(e.g., silently stripping path traversal attempts). Silent correction hides
attacks and breaks the fidelity principle.

### Layer 2: Permission control

- Restrict filesystem access to declared directories
- Maintain command blacklists for dangerous operations
- Scope API credentials to the minimum required operation

### Layer 3: Pre-execution review patterns

For high-risk operations, add a review step before execution:

**Proposer-Reviewer pattern.** A second LLM of similar capability reviews
the proposed action before it executes. Both models operate under the same
rules; the proposer focuses on accomplishing the task, the reviewer focuses
on risk. When the reviewer rejects, the rejection reason is appended to the
trajectory as a tool result — the proposer can adjust and retry.

**Sidecar pattern.** A lightweight model examines only the structured
tool-call data (name, parameters) — never the free-text reasoning chain.
This blocks the rhetorical prompt-injection channel: an attacker cannot
manipulate the sidecar by embedding instructions in prose the main model
reasoned through. Sub-second latency; suitable for every execution call.
The sidecar assesses behavioral risk (unexpected tool, anomalous call
pattern) — it does not replace Layer 1 input validation, which must still
sanitize parameter values at the tool boundary.

### Post-execution validation

Immediately validate the result after execution:

- Lint or syntax-check written code; return errors as tool result
- Verify file was written by reading it back
- Check command exit code and surface stderr

Return validation results in the tool response so the agent can self-correct
without a separate observation step.

### Long output handling

When output exceeds ~200 lines, return head + tail, save full output to a
temp file, and tell the agent the path:

```
{"stdout_preview": "...first 50 lines...\n...[truncated]...\nlast 10 lines...",
 "full_output_path": "/tmp/agent_run_abc123.log",
 "total_lines": 1847}
```

### Idempotency

- **Idempotent operations** (file write, config set): carry a unique
  operation ID for deduplication. Safe to retry.
- **Non-idempotent operations** (send_email, charge_card): use a
  pre-check-then-confirm two-phase pattern. The agent calls `preview_email`
  first, then `send_email` only after confirming the preview is correct.

### Sandboxing

Python `venv` is **not** a sandbox — it only isolates packages. True
sandboxing requires OS-level isolation: containers (Docker, gVisor) or VMs.
Any execution tool that runs agent-generated code must use OS-level
isolation. Document the sandbox boundary in the tool description.

---

## Collaboration Tools (drive other agents or humans)

Collaboration tools delegate work — to sub-agents, specialized models, or
humans. The design challenge is context passing: how much does the
sub-agent need to do its job?

### Sub-agent prompt design

A sub-agent prompt needs four elements:

1. **Role definition** — what the sub-agent is and what it is responsible for
2. **Labeled context sources** — tag where each piece of context came from:
   `[FROM_MAIN_AGENT]`, `[FROM_USER]`, `[TOOL_RESULT]`
3. **Task boundary** — what is in scope, and when to escalate vs proceed
4. **Standardized output format** — structured so the calling agent can parse
   the result without ambiguity

### Context passing strategies

Choose by task complexity:

| Strategy | When to use | Trade-off |
|---|---|---|
| **Minimal** (zero context) | Simple, frequent sub-tasks | Fast; sub-agent may lack needed info |
| **Manual filtered** | Explicit selection of relevant context | Flexible; higher design cost |
| **Automatic truncated** | User info + last N rounds + relevant results | Balanced; may include noise |
| **LLM-generated** | Complex tasks with privacy rules | Most flexible; costs one extra LLM call |

LLM-generated context: the orchestrator calls a model to produce a
structured summary of what the sub-agent needs. Supports privacy rules
(the summary can omit sensitive fields). Most flexible but adds latency.

### Human-in-the-loop (HITL) tools

HITL tools (`request_approval`, `request_input`) must define:

- **Timeout + default**: what happens if the human doesn't respond in time
- **Multi-channel notification**: IM for urgent, email for async, push for
  mobile — match channel to urgency and context

---

## Event-Triggered Tools (agent registers; external system triggers)

Event-triggered tools invert the call pattern: the agent registers interest,
then sleeps until an external event wakes it.

Three subtypes:
- **Timer/scheduler** — wake at a specified time or interval
- **Background task monitor** — wake when a long-running operation completes
- **External event channel** — wake on webhook, queue message, or file change

### Trigger clarity

Define precise trigger conditions and filtering rules. Vague triggers cause
irrelevant wake-ups that consume budget and pollute the trajectory.

```
// Vague: triggers on any file change in /data
watch_directory(path="/data")

// Precise: triggers only on new .csv files, ignoring temp files
watch_directory(path="/data", pattern="*.csv", ignore_pattern="*.tmp",
                events=["created"])
```

### Payload completeness

Event payloads must contain sufficient context to minimize follow-up queries
after wake-up. An agent woken by a sparse event (just an ID) must immediately
call several tools to reconstruct context — wasting steps and budget.

```
// Sparse (bad): forces follow-up queries
{"event": "order_created", "order_id": "ord_123"}

// Rich (good): agent can act immediately
{"event": "order_created", "order_id": "ord_123",
 "customer_id": "cust_456", "total": 89.99,
 "items": [...], "shipping_address": {...}}
```

For the runtime mechanism that handles event interruptions and maintains
trajectory integrity, see
`agent-architecture/references/async-event-handling.md`.

---

## User Communication Tools (convey info to user)

User communication tools are needed when the agent's interaction with the
user expands beyond single-session Q&A — multi-channel, async, or
notification-driven messaging.

### When to add communication tools

A basic agent that returns text in the same session needs no communication
tools. Add them when:

- The agent runs async and must notify the user when done
- The task spans multiple sessions and requires status updates
- Different message types warrant different channels (urgent vs informational)

### Channel selection

Match channel to urgency and context:

| Channel | Use for |
|---|---|
| IM / chat | Urgent, interactive, short messages |
| Email | Async, long-form, formal |
| Push notification | Mobile, time-sensitive alerts |
| In-app notification | Context-anchored updates |

For the runtime event-handling mechanism (how the agent manages async
communication without blocking), see
`agent-architecture/references/async-event-handling.md`.
