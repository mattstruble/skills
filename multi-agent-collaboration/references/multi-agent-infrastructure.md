# Multi-Agent Infrastructure

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## Workspace Area Types

Four distinct workspace areas, each with different visibility, persistence,
and concurrency requirements.

### 1. Agent-Specific Workspace (Scratchpad)

Private to one agent instance. Destroyed when the instance terminates. No
concurrency control needed — only one agent ever writes here.

- **Use for**: intermediate calculations, draft attempts, working notes
- **Key property**: ephemeral; never rely on scratchpad content surviving
  beyond the agent's lifetime

### 2. Multi-Agent Shared Space

Visible to all agents and to the user. Persistent across agent instances.
Requires concurrency control — multiple agents may read and write simultaneously.

- **Use for**: deliverables, shared state, coordination files, final artifacts
- **Key property**: the source of truth for the collaboration's outputs; must
  be treated with the same care as a shared database

### 3. Mounted External Resources

Third-party sources (Google Drive, Notion, GitHub repositories). Read-mostly.
Constrained by external permissions — agents can only access what the
integration allows.

- **Use for**: reference material, source data, upstream dependencies
- **Key property**: agents don't own this space; writes may be restricted or
  require explicit authorization

### 4. Built-in System Resources

Skills, templates, manuals, operational procedures. Globally shared and
read-only. Stable across sessions.

- **Use for**: shared knowledge, operational procedures, capability definitions
- **Key property**: immutable from the agent's perspective; changes require
  out-of-band updates to the system

---

## Communication Plane

### Message passing

**Point-to-point** (suitable for small systems, <5 agents): direct calls
between agents. Simple to implement; coupling grows with agent count.

**Message bus** (suitable for larger or async systems): agents publish to
topics; subscribers receive relevant messages. Decouples senders from
receivers; enables fan-out and cascading termination.

Structured message envelope:
```
sender: agent_id
target: agent_id | broadcast | topic
type: task | result | status | termination
payload: structured content
timestamp: ISO 8601
```

**Design principle**: "File path as universal interface." Agents exchange
artifacts by passing lightweight path strings, not by loading content into
context. The receiver fetches what it needs; the sender doesn't decide what
the receiver should load.

### Status query

**Pull model**: the Manager calls `get_subagent_status(agent_id)` to check
progress. Simple; adds latency between status change and detection.

**Push model**: sub-agents proactively report to the message bus on state
transitions. Lower latency; requires agents to implement reporting discipline.

**State machine** for sub-agent lifecycle:
```
submitted → executing → needs-input → completed
                     ↘ failed
```

`needs-input` is the critical state: the sub-agent has hit a decision point it
cannot resolve autonomously and is waiting for the Manager or a human to
provide direction. Systems that don't model this state leave sub-agents
blocked silently.

### Execution termination

**Graceful termination**: signal → cleanup → acknowledgment → exit. The agent
finishes its current operation, writes any pending state, and confirms
termination. Preferred for normal completion and planned shutdown.

**Forced termination**: process kill. Used when the agent is unresponsive or
has exceeded its budget. Risks leaving shared state in an inconsistent
condition — design shared state writes to be atomic or idempotent.

**Cascading termination**: for parallel exploratory tasks where any one success
is sufficient. The first agent to succeed broadcasts a termination signal;
remaining agents stop cleanly. Avoids wasted compute when multiple agents are
racing toward the same goal.

---

## Concurrency Control

### Optimistic locking

Read the current version → modify locally → write-if-version-matches → retry
on conflict.

- **Suitable for**: most multi-agent tasks, where agents work on different
  files and conflicts are rare
- **Trade-off**: retry overhead on conflict; starvation possible under high
  contention
- **Implementation**: version field on each shared artifact; write operation
  is conditional on version match

### Working copy isolation

Each agent gets its own Git branch or worktree. Agents work independently;
results are merged after completion.

- **Suitable for**: code-heavy collaboration where semantic conflicts are
  possible (two agents refactoring the same module in incompatible ways)
- **Trade-off**: merge conflicts must be resolved; requires a merge step after
  parallel phases
- **Key advantage**: agents never block each other; the merge surface is
  explicit and reviewable

### Task-level dependency management

An explicit DAG of which tasks can run concurrently vs which must serialize.
The Manager uses this DAG for scheduling — tasks with no shared dependencies
run in parallel; tasks that write to the same artifacts or depend on each
other's outputs run sequentially.

- **Suitable for**: Manager pattern with complex task graphs
- **Trade-off**: DAG construction requires upfront planning; dynamic tasks
  (discovered during execution) must be inserted into the DAG correctly
- **Key advantage**: prevents semantic conflicts by design, not by detection

---

## Step Budget Awareness

Simply increasing available steps doesn't improve outcomes by default. A loop
with more steps and no convergence signal runs longer and costs more — it
doesn't produce better output.

### Budget-aware design

Allocate budget explicitly across phases:

- **Exploration budget** (early rounds): broad attempts, diverse approaches,
  high tolerance for failure
- **Exploitation budget** (later rounds): focus on the most promising
  direction identified during exploration; tighter iteration

### Convergence tracking

Track cost-per-improvement across rounds. If the last N rounds show
diminishing returns — output quality is not improving despite continued
iteration — the loop should escalate to a human or terminate.

Signals of diminishing returns:
- Verifier scores plateau across consecutive rounds
- Agent is making the same edits repeatedly
- Agent is undoing and redoing the same changes

### Human escalation

When automated verification stalls — the verifier cannot distinguish between
good and bad outputs, or the agent is stuck in a local optimum — escalate to
a human. The human acts as "engineer of the loop": they can provide new
direction, adjust the verifier, or terminate the loop with a partial result.

Budget exhaustion without convergence is a signal about the task or the
verifier, not just the agent. Investigate the verification signal before
increasing the budget.
