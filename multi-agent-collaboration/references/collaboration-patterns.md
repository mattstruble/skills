# Collaboration Patterns

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## Proposer-Reviewer (Peer Pattern — Detailed Mechanics)

The Proposer-Reviewer is the canonical peer pattern. One agent generates; one
reviews. The critical design question is whether the Reviewer has access to
information the Proposer doesn't.

### Context separation advantage

The Reviewer sees only the current version of the output — a fresh perspective
uncontaminated by the Proposer's accumulated reasoning history. The Proposer
accumulates feedback across rounds. This asymmetry is intentional: it prevents
context explosion on the Reviewer side and keeps the review signal clean.

### When the Reviewer is effective

| Reviewer action | Effective? | Why |
|---|---|---|
| Re-reads the same text and offers opinions | No | Same model, same context — no new signal |
| Runs tests and reports pass/fail | Yes | Execution results are new information |
| Renders output and visually inspects | Yes | Visual signal the Proposer didn't have |
| Calls external tools to verify facts | Yes | Tool feedback grounds the review in reality |

### Stop conditions

Two conditions, whichever comes first:

1. **Quality meets standard** — the Reviewer, using its verifier, determines the output is acceptable
2. **Maximum rounds reached** — hard budget cap; the loop terminates regardless of quality

Never rely on the model to declare itself done. The Reviewer must have a
concrete verifier (test suite, rendering pipeline, fact-check tool) — not just
a subjective quality judgment.

### Dual-model variant

The Proposer optimizes for task completion; the Reviewer optimizes for
risk and quality. Same structural rules, different model focus. Useful when
the task domain has asymmetric failure costs (e.g., security review, medical
content).

### Variants

**Debate**: two agents take adversarial positions on a question and argue
toward a conclusion. Effective when the goal is stress-testing a decision, not
when the goal is generating content — debate produces analysis, not artifacts.

**Brainstorm**: agents generate independently, then cross-pollinate. Each agent
sees the others' outputs after its own generation round. Useful for creative
tasks where premature convergence is the failure mode.

**Panel**: multiple agents with complementary domain expertise each review from
their perspective. Useful when a single reviewer can't cover all relevant
dimensions (e.g., security + UX + performance).

---

## Manager Pattern — Sub-Patterns

### Sequential coordination

A linear pipeline where each sub-agent finishes before the next starts.
Dependency ordering is explicit. The Manager waits for each result before
dispatching the next task.

- **Use when**: tasks have strict ordering requirements, each task depends on
  the previous output
- **Trade-off**: no parallelism; total latency is the sum of all sub-task latencies

### Parallel coordination

The Manager fans out to multiple sub-agents simultaneously. A message bus
coordinates results. The Manager waits for all (or a quorum) to complete.

**Cascading termination**: for exploratory tasks where any one success is
sufficient, the first sub-agent to succeed sends a termination signal to the
bus; remaining sub-agents stop cleanly. This avoids wasted compute when
multiple agents are racing toward the same goal.

- **Use when**: sub-tasks are independent, latency matters, or the task is
  exploratory (multiple approaches in parallel)
- **Trade-off**: concurrency control required; semantic conflicts possible if
  sub-agents write to shared state

### What sub-agents return

Sub-agents return structured summaries to the Manager — never full
trajectories. A full trajectory would flood the Manager's context and make
planning harder.

Structured summary format:
- **Conclusion**: one-sentence outcome
- **Key findings**: facts established, decisions made
- **File paths modified**: explicit list of artifacts produced
- **Problems encountered**: blockers, uncertainties, partial failures

This keeps Manager context growth linear in the number of sub-tasks, not in
the depth of each sub-task's reasoning.

### Planner quality

Bojie Li argues a weak planner is the most critical bottleneck of the entire
system. The Manager/planner should receive:
- The strongest available model
- The most carefully crafted prompt in the system
- Explicit task decomposition guidance (how to split, what to parallelize, how
  to handle dependencies)

Investing in the planner pays larger dividends than investing in sub-agent
capability.

---

## Decentralized Pattern — Handoff Mechanics

### MetaGPT approach

Fixed pipeline control flow with decoupled communication. Agents post to a
shared message pool; other agents subscribe by role or topic. No central
controller — each agent pulls what it needs.

- **Strength**: loose coupling; agents don't need to know each other's
  internals
- **Limitation**: fixed pipeline means the routing is still predetermined;
  dynamic task routing requires a different approach

### AutoGen Group Chat

Shared conversation history with a centralized speaker selector. Content is
decentralized (any agent can contribute); turn-taking is centralized (a
selector decides who speaks next). A hybrid: decentralized content, centralized
coordination.

- **Strength**: flexible turn-taking without full peer-to-peer complexity
- **Limitation**: the speaker selector is a single point of coordination
  failure; it must be robust

### Swarm / Agents SDK

True peer-to-peer baton passing. Each agent has a set of `handoff_to` options.
Whoever holds the baton acts, then passes it to the next agent with a reason.
No central controller exists.

- **Strength**: maximum flexibility; routing decisions are local and contextual
- **When NOT**: tasks with complex inter-dependencies need a Manager to
  maintain global state; decentralized patterns have no scheduler to resolve
  cross-agent dependencies

### Handoff package

What one agent passes to the next when transferring control:

**Include:**
- Task description and confirmed constraints
- Key facts established so far
- References to artifacts (file paths, not content)
- Reason for the handoff (why this agent, why now)

**Exclude:**
- Full prior trajectory
- Intermediate reasoning and failed attempts
- Unrelated context from earlier in the session

The receiver needs conclusions and orientation, not the journey. A bloated
handoff package degrades the receiving agent's performance by flooding its
context with noise.

---

## A2A Protocol (Cross-Organization Collaboration)

The Agent-to-Agent (A2A) protocol addresses collaboration across organizational
boundaries, where agents from different vendors or organizations need to
interoperate without exposing internal architecture.

**Positioning**: MCP = Agent↔Tool interoperability; A2A = Agent↔Agent
interoperability across trust boundaries. They are complementary, not
competing.

**Three elements:**

1. **Agent Card**: capability discovery. An agent publishes what it can do,
   what inputs it accepts, and what outputs it produces — without revealing
   how.
2. **Task Lifecycle Management**: a state machine (submitted → executing →
   needs-input → completed → failed) that both sides can observe and act on.
3. **Opaque Collaboration**: the internal reasoning, tools, and architecture
   of each agent remain private. Only the task interface is shared.

**When to consider A2A:**
- Collaboration crosses organizational boundaries
- Agents from different vendors need to interoperate
- Internal architecture must remain private for security or IP reasons

For intra-organization multi-agent systems, direct API calls or message buses
are simpler and sufficient.

---

## Shared-Context Role Switching (Lightest Form)

The lightest multi-agent pattern: a single conversation trajectory with
pre-determined stages, each stage using a different system prompt and tool set.

**Structure:**
- Stage 1: requirements analysis role (system prompt A, tools A)
- Stage 2: implementation role (system prompt B, tools B)
- Stage 3: review role (system prompt C, tools C)

**Stage transitions**: via explicit tool calls that signal completion of the
current stage (e.g., `complete_requirements_analysis()`). The tool call is the
handoff — it triggers the harness to swap the system prompt and tool set for
the next stage.

**Cross-domain dynamic routing**: `transfer_to_agent(target_role, reason)` can
be made available to all roles, enabling non-linear routing when the current
agent determines a different role is better suited.

**Boundary note**: this is essentially workflow orchestration (agent-architecture
territory) viewed through a multi-agent lens. It belongs here because the
role-switching design — which roles exist, what each sees, how handoffs are
triggered — is a multi-agent collaboration concern. The orchestration
mechanics (how the harness swaps prompts) belong to agent-architecture.
