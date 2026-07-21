# Code Meta-Patterns for Coding Agents

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## Sessionless Design (§5.1.3)

Coding agents operate across sessions. File system state is inherently
persistent (workspace on persistent storage), but process state is not.

**The split:**

- **File system state** — always persistent; source files, `MEMORY.md`,
  documentation survive session boundaries naturally
- **Process state** — terminal sessions, environment variables, running
  servers — kept alive during active periods, serialized to workspace files
  before destruction, rebuilt on wake-up

**Engineering challenge**: every user message requires reloading the complete
trajectory and working state. The cost of session restoration grows with
trajectory length.

**Pattern**: checkpoint critical process state to workspace files at natural
pause points (end of a task, before a long-running operation). Don't rely on
the process staying alive.

---

## Code-Driven Multimedia Generation (§5.2.3)

Reframe document creation as code generation. Instead of asking the agent to
produce a PowerPoint directly, ask it to generate Slidev markup or Blender
Python — then render.

**Why code beats direct generation**: code is deterministic, diffable, and
correctable. A Slidev file can be reviewed and edited; a binary `.pptx`
cannot.

**Proposer-Reviewer architecture:**

```
Proposer (LLM) → generates code → render → Reviewer (vision LLM) → evaluates quality
                                                    ↓
                                          feedback → Proposer (next round)
```

**Context management advantage**: the Reviewer only sees current screenshots;
the Proposer only accumulates text feedback. Neither accumulates the other's
context. This prevents context explosion across many revision rounds.

**Stop conditions:**

- "Quality meets standard" — the Reviewer decides, based on visual evaluation
- "Maximum rounds" — hard budget cap; the last accepted version is the output

---

## Code as System Adapter (§5.2.4)

Code is "universal glue" — an agent can read interface documentation (or
observe real API responses) and generate adapter code on the fly, without
requiring a pre-built tool for every system.

**Adaptive pattern:**

1. Agent encounters a system with no pre-built tool
2. Agent reads the interface docs or probes with sample calls
3. Agent generates adapter code, tests it, and uses it as a tool

**Computer Use extension**: when a system has no API at all, Computer Use
(visual interaction) discovers the interaction pattern. Successful operations
are then solidified into RPA code tools — turning one-off visual interactions
into reusable, reliable adapters.

**Production log analysis pattern:**

```
Production logs → agent reads + analyzes → generates problem reports
               → generates regression tests → creates issues
```

The agent doesn't just report problems — it generates the artifacts (tests,
issues) that make the problems actionable.

**Frontend parsing pattern**: frontend reports an unparseable format → agent
generates parsing code → tests it → hot-deploys. The adapter evolves with
the system it wraps.

---

## Generative UI (§5.2.5)

Agents can generate user interfaces, but the security model matters more than
the generation capability.

### A2UI Protocols (Security-First)

The agent outputs a UI description manifest (JSON); the client renders using
pre-defined safe components. The agent cannot inject arbitrary code into the
UI. This is the correct default: agent describes, client renders.

### Artifact Pattern

Agent generates SQL or code; the frontend executes it directly. Data flows:

```
Database → Frontend → Visualization
```

The LLM is not in the data path at query time. This bypasses the LLM for
data retrieval — faster, cheaper, and more accurate than asking the LLM to
summarize query results.

### Dynamic Forms

Replace multi-round text Q&A with a single structured form. Cascading logic
via JavaScript handles conditional fields. One form submission replaces four
clarification turns.

### Semi-Custom Modification

Start from an existing framework, apply targeted modifications with Hot Module
Replacement (HMR). More pragmatic than full generation from scratch — the
framework handles the structure; the agent handles the customization.

---

## Code Creating Code — Agent Bootstrapping (§5.2.6)

Agents can generate agents of their own kind. This is distinct from
self-evolution (Ch8):

| Pattern | What changes |
|---|---|
| **Bootstrapping (Ch5)** | Structure — agents create agents with the same architecture |
| **Self-evolution (Ch8)** | Capability — knowledge and strategies grow without weight changes |

### Agent Self-Repair (Doctor Pattern)

Two-tier repair:

1. **Deterministic checks** for common problems: expired tokens, stale locks,
   missing environment variables — fast, reliable, no LLM needed
2. **LLM analysis** for hard problems: error log interpretation, root cause
   reasoning, repair plan generation

The deterministic tier handles the 80% case cheaply; the LLM tier handles
the long tail.

### Self-Replication with Adaptive Modification

Pattern for bootstrapping a new agent from an existing one:

1. Copy own code as the starting point
2. Adjust the system prompt for the new role
3. Replace tools with those appropriate for the new task
4. Modify business logic while preserving the architectural framework

Key technique: provide high-quality agent implementations as reference
examples. Guide modification rather than generation from scratch. The
architectural framework (harness, error handling, trajectory management) is
the expensive part — reuse it.
