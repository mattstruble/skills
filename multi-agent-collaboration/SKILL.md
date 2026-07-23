---
name: multi-agent-collaboration
summary: Designing multi-agent topologies, context sharing, handoff protocols, and failure modes
type: behavioral
description: You MUST consult this skill when designing systems where multiple LLM agents collaborate — choosing collaboration topology (peer, manager, decentralized), deciding context sharing vs isolation, designing handoff protocols, implementing verification loops, or debugging multi-agent failure modes (conflicting edits, error cascading, runaway iteration). Also trigger when deciding whether multi-agent adds value over a single agent with more compute. NOT for single-agent workflow orchestration or sub-agent spawning (see agent-architecture), or for the tool interface design of spawn_subagent or send_message (see agent-tool-design).
---

# Multi-Agent Collaboration

**Multi-agent adds value only when collaboration introduces information unavailable during single-agent generation.**

Everything else is cost without benefit.

---

## Framing — The Classification Framework

Two orthogonal dimensions define every multi-agent design:

1. **Context sharing**: shared trajectory (agents see the same conversation) vs non-shared (agents communicate via files, messages, or structured parameters)
2. **Collaboration topology**: peer (equal agents, iterative improvement), manager (centralized coordination), decentralized (peer-to-peer handoff, no controller)

The north star: **does the collaboration introduce new information?**

| Reviewer action | New information? | Effective? |
|---|---|---|
| Re-reads the same text | No | No — same model, same context |
| Runs tests and reports results | Yes — execution feedback | Yes |
| Renders output and visually inspects | Yes — visual signal | Yes |
| Calls external tools to verify facts | Yes — tool feedback | Yes |

**Cost reality.** Anthropic disclosed ~15x token consumption for multi-agent research systems. Bojie Li argues 80% of the performance difference between multi-agent and single-agent is explained by compute alone — the collaboration structure accounts for the rest. Multi-agent must clear this bar.

---

## Symptom Table

| Symptom | Section |
|---|---|
| Adding a "reviewer" agent doesn't improve output | §1 — New information criterion (reviewer has no new info) |
| Multi-agent costs 15x but only marginally better | YAGNI Gate — single agent with equal compute is comparable |
| Agents produce conflicting file edits | §4 — Failure modes (concurrency) |
| Error in one agent propagates and gets "confirmed" by others | §4 — Failure modes (cascading amplification) |
| Agent never stops iterating / iterates without improving | §3 — Loop Engineering (verifier bottleneck) |
| Complex task needs >5 sub-tasks with dependencies | §2 — Manager pattern |

---

## YAGNI Gate

Multi-agent is only justified when collaboration introduces **new information**. Self-review by the same model is ineffective or harmful — the model has no new signal to improve on.

When thinking budget is controlled to be equal, single-agent performs on par with or better than multi-agent debate. The gain in multi-agent systems comes from the new-information channel, not from multiple "opinions."

**Multi-agent pays off when:**
- Different agents access different tools or data sources
- Verification requires execution (tests, rendering, tool calls)
- Task parallelism is the goal and tasks are genuinely independent

If none of these apply, invest the compute in a better single agent.

---

## §1 Context Sharing Decision

**The question**: Should agents share a single conversation trajectory, or communicate via structured handoffs?

### Shared context (trajectory inheritance)

Agents share one conversation. Each stage gets a different system prompt and tool set but sees the full history. This is essentially workflow orchestration viewed through a multi-agent lens.

- **Use when**: stages are tightly coupled, information loss between stages is unacceptable, combined trajectory fits in the context window
- **Stage transitions**: via explicit tool calls (e.g., `complete_requirements_analysis()`)
- **Trade-off**: context grows with every stage; later agents inherit noise from earlier stages

### Non-shared context (independent trajectories)

Agents communicate via files, messages, or structured parameters. Each agent sees only what's explicitly passed.

- **Use when**: cumulative context would exceed ~50% of window (heuristic, not law), agents need different model capabilities, parallelism is required
- **Trade-off**: information loss at handoff boundaries; handoff package design becomes critical

### Handoff package design (for non-shared)

The handoff package is what one agent passes to the next. Include:
- Task description and confirmed constraints
- References to structured artifacts (file paths, not content)
- Key facts established so far

Deliberately exclude: full prior trajectory, intermediate reasoning, unrelated context. The receiver needs conclusions, not the journey.

**Rule of thumb**: "If zero information loss is a hard requirement, share. If context would be wasted on irrelevant history, isolate."

---

## §2 Collaboration Topologies

**The question**: Which structural pattern fits this collaboration?

### Peer pattern (2–3 equal agents, iterative improvement)

Core: **Proposer-Reviewer**. One agent generates; one reviews with access to new information (execution results, rendered output, external verification).

- **Variants**: debate (adversarial positions), brainstorm (independent generation + cross-pollination), panel (multi-domain complementary perspectives)
- **When to use**: task has a clear quality verifier — tests pass/fail, rendering succeeds, facts are tool-checkable
- **Research caveat**: when compute budget is strictly equal, multi-agent debate performs comparably to single agent. The gain comes from the new-information channel, not from multiple opinions.
- **Context separation advantage**: Reviewer sees only the current output (fresh perspective); Proposer accumulates feedback history. This prevents context explosion and keeps the Reviewer's signal clean.

### Manager pattern (centralized coordination)

A Manager agent decomposes the task and coordinates sub-agents. Sub-agents are the Manager's tools.

- **When**: >5 sub-tasks, complex dependencies, need dynamic scheduling
- **Critical finding**: Bojie Li argues "a weak planner is the most critical bottleneck of the entire system." Give the strongest available model and the most carefully crafted prompt to the Manager.
- **Sub-agent return format**: structured summary — conclusion, key findings, file paths modified, problems encountered. Never full trajectories. Keeps Manager context growth linear.
- **Sub-patterns**:
  - *Sequential coordination*: linear pipeline, each sub-agent finishes before the next starts
  - *Parallel coordination*: fan-out to multiple agents simultaneously; message bus for coordination; cascading termination (first success cancels remaining) for exploratory tasks

### Decentralized pattern (peer-to-peer handoff, no central controller)

Each agent is autonomously capable. Control flows like a baton — whoever holds it acts, then passes.

- **When**: each agent is autonomously capable, routing decisions are local, no single task requires global coordination
- **Handoff**: `transfer_to_agent(target, reason)` + handoff package
- **Progression**: MetaGPT (shared message pool + subscription by role) → AutoGen Group Chat (shared history + centralized speaker selector) → Swarm/Agents SDK (true peer-to-peer baton passing)
- **When NOT**: tasks with complex inter-dependencies need a Manager; decentralized patterns have no global scheduler to resolve them

-> Read `references/collaboration-patterns.md` for detailed mechanics of each pattern, A2A protocol, and shared-context role switching.

---

## §3 Loop Engineering

The meta-pattern unifying all iterative multi-agent work.

**Core structure**: discover work → execute → verify → record progress

**Key principle**: let a **verifier** — not the model itself — decide when to stop. The verifier must have access to information the generator doesn't: execution results, rendered output, external tool feedback. Without this asymmetry, the loop has no signal to improve on.

"The bottleneck of the loop is the verifier, not the model." With unreliable verification, a faster loop merely marks poor output as complete sooner.

### Three premature termination modes to design against

| Mode | Description | Counter |
|---|---|---|
| **Lazy fake-done** | Model claims completion without verifying | Always verify; never trust self-report |
| **Premature give-up** | Model stops on first difficulty | Explicit retry budget; budget awareness |
| **False success** | Output passes shallow checks but fails deeper ones | Multi-signal verification — tests + lint + runtime behavior |

### Step budget awareness

Simply increasing available steps doesn't guarantee improvement. Design budget-aware mechanisms: broad exploration early, focus on promising directions later. Track cost-per-improvement — if the last N rounds show diminishing returns, escalate to human or terminate.

---

## §4 Failure Modes

### Concurrency conflicts in shared file systems

Two agents writing the same file simultaneously produces corrupted state. Two agents making logically contradictory edits to different files is harder to detect.

- **File-level conflicts**: optimistic locking — read version, modify, write-if-version-matches, retry on conflict
- **Semantic-level conflicts**: task-level dependency management or global consistency checks after parallel phases complete
- **For code specifically**: working copy isolation — Git branches or worktrees per agent; merge after completion

### Cascading amplification of errors

A single error gains credibility through "consistency" as it propagates through multiple agents. Each downstream agent treats the error as established fact, and the system converges on a confident wrong answer.

- **Mitigation**: cross-validation from an independent perspective (an agent that hasn't seen prior output); external validation (tests, compilers, DB queries) as "chain breakers" that ground the system in reality

### Runaway loops

Three failure modes when loops don't converge:

- **Token cost spiraling**: no convergence signal, loop runs to budget exhaustion
- **Comprehension debt**: context fills with failed attempts; model loses the thread
- **Cognitive surrender**: model starts agreeing with everything to end the loop

**Antidotes**: explicit budgets (max rounds), verifiers grounded in real observations (not model self-assessment), human as "engineer of the loop" who can intervene when automated verification stalls.

---

## Routing Map

These are companion skills in the ai-agents family. Load the relevant one when building that layer.

| Concern | Companion Skill | Source |
|---|---|---|
| Agent orchestration & autonomy | agent-architecture | Ch1 — single-agent patterns |
| Collaboration tool interface | agent-tool-design | Ch4 — spawn_subagent schema, context-passing |
| Coding agent patterns | coding-agent-design | Ch5 — Proposer-Reviewer applied to code |
| Context isolation | context-engineering | Ch2 — §2.7.7 sub-agent isolation |
| Memory & retrieval | agent-memory / rag-design | Ch3 |

Co-triggering with `agent-architecture` is expected when someone asks "should I use multiple agents or one agent with more compute?" — agent-architecture handles the orchestration decision, this skill handles the collaboration protocol.

---

## NOT For

**Litmus**: Is the question about how multiple LLM agents coordinate, communicate, and verify each other's work? → here. Is it about single-agent workflow orchestration or sub-agent spawning? → `agent-architecture`. Is it about the tool interface for `spawn_subagent` or `send_message`? → `agent-tool-design`.

**Coexistence note**: both this skill and `agent-architecture` can fire together when deciding whether to split into independent agents or keep a single trajectory with role switching. `agent-architecture` handles the orchestration; this skill handles the collaboration protocol and handoff design.

- Single-agent workflow orchestration → `agent-architecture`
- Tool interface design (spawn_subagent, send_message schemas) → `agent-tool-design`
- Application code structure → `application-architecture`

---

## References

| Reference | When to read |
|---|---|
| `references/collaboration-patterns.md` | Detailed mechanics: Proposer-Reviewer stop conditions and context separation, Manager sub-patterns, decentralized handoff mechanics (MetaGPT/AutoGen/Swarm), A2A protocol for cross-org collaboration, shared-context role switching |
| `references/multi-agent-infrastructure.md` | Workspace area types (scratchpad vs shared vs external), communication plane (message passing, status query, termination), concurrency control strategies, step budget design |
