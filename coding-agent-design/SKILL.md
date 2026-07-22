---
name: coding-agent-design
description: You MUST consult this skill when building or improving a coding agent or copilot, choosing its toolset, designing its security model, defining its engineering workflow, handling failures and retries, or deciding whether code generation is the right approach for a problem. Also trigger when a coding agent loops without progress, executes dangerous commands, or can't find files in large codebases. NOT for code-level design patterns (see software-design), code review (see code-reviewer), or agent orchestration decisions unrelated to code execution (see agent-architecture).
---

# Coding Agent Design

**The file system is the hub. Decades of software engineering infrastructure
already form the harness.**

---

## Framing — Coding Agent = LLM + 7 Tools + File System

The file system is the central hub of a coding agent: memory lives in
`MEMORY.md`, knowledge in Markdown, code in source files, experience written
back as documentation. Decades of software engineering infrastructure — test
suites, linters, Git — naturally form a robust harness. Bojie Li argues this
makes coding agents the most mature and reliable agent category: the
verification infrastructure already exists.

**Minimal toolset pattern** (current consensus, not immutable law):

| # | Tool | Role |
|---|---|---|
| 1 | Code Interpreter | Sandboxed Python execution — precise computation, logic, data |
| 2 | Bash Shell | System commands, build tools, package management |
| 3 | Read File | Perception — load source files, configs, docs |
| 4 | Write File | Create new files |
| 5 | Edit File | Targeted in-place modification |
| 6 | Search File Name | Glob — structure exploration without reading content |
| 7 | Search File Content | Grep — locate known identifiers, error messages, imports |

These seven tools cover perception + execution for code. Additional tools
(LSP, semantic search) are optimizations, not requirements.

**Applicability boundary.** "Coding as core architecture" applies to
general-purpose agents targeting open-ended tasks. Vertical-domain agents
(customer service, data entry) use code as one tool, not the architectural
hub.

-> Read `references/search-and-editing.md` for detailed search strategy
comparisons and editing scheme trade-offs.

---

## Symptom Table

| Symptom | Section |
|---|---|
| Agent writes code that doesn't work / doesn't stop | §3 — Workflow (tests-pass criterion) |
| Agent executes dangerous commands | §2 — Security |
| Agent gets stuck in retry loops or exhausts budget | §4 — Failure Recovery |
| Agent can't find files in a large codebase | References — search strategy |
| Agent edits corrupt files or loses content | References — editing scheme |
| Agent hallucinates API calls that don't exist | §5 — Code as verification |

---

## YAGNI Gate — Does This Need to Be a Coding Agent?

Coding agents are expensive (many inference rounds) and risky (arbitrary code
execution). Use only when:

- The task requires adaptive code generation
- The solution path can't be enumerated in advance
- The code changes frequently enough that a fixed workflow breaks

Otherwise, a workflow with fixed code nodes or structured-output calls is
cheaper and safer.

---

## §1 Minimal Toolset

The seven tools above are sufficient for most coding tasks. Each earns its
place:

- **Code Interpreter** — offloads precise computation; LLM understands the
  problem, interpreter provides exact answers
- **Bash Shell** — system-level operations the interpreter can't reach
- **Read/Write/Edit File** — the three file-system primitives; Edit is
  separate from Write to enable targeted changes without full rewrites
- **Search File Name** — coarse navigation; find modules and configs by
  structure
- **Search File Content** — fine navigation; locate specific identifiers or
  patterns

**File-system-as-hub philosophy.** Bojie Li argues choosing Markdown over a
vector database for agent memory is deliberate — human-readable, editable,
and version-controllable via Git. The file system is the one store that
humans, agents, and tooling all share natively.

**Applicability boundary.** General-purpose agents: code is the hub.
Vertical-domain agents: code is one tool among many. The minimal toolset
pattern applies to the former.

-> Read `references/search-and-editing.md` for search strategy selection
(regex vs glob vs semantic vs LSP) and editing scheme comparisons.

---

## §2 Security

**The question**: How do you prevent a coding agent from becoming a liability?

### Threat Model — The Lethal Triad + Amplifier

Three conditions that, when combined, create a high-severity attack surface:

1. **Access to private data** — source code, credentials, user data in the
   workspace
2. **Exposure to untrusted content** — user input, fetched web pages,
   imported packages
3. **Ability to communicate externally** — network access, git push, send
   email

**Amplifier**: persistent memory. An injected instruction in `MEMORY.md`
persists across sessions, turning a one-time injection into a persistent
compromise.

### Sandbox Isolation

Engineering choices that contain the blast radius:

- **Network**: no egress by default; whitelist proxy for approved domains
  only. Example: allow `pypi.org` for package installs, block everything else.
- **Filesystem**: source code as read-only mount; credentials never mounted
  in the sandbox. The agent reads code but can't exfiltrate it.
- **Resources**: CPU/memory limits and execution timeouts prevent runaway
  processes.
- **Persistent sessions**: mount the workspace directory, not the host
  filesystem. The agent's working state persists; the host is isolated.

### Semantic Parsing Over Keyword Blacklists

Shell commands bypass static keyword rules via pipes, subshells, and variable
expansion. Example: `cat /etc/passwd` is blocked by a naive filter, but
`c""at /et''c/pas''swd` bypasses string matching. Production harnesses parse
command semantics (intent), not surface syntax.

### Principal Loyalty

Under multi-party delegation (user asks agent to negotiate with a vendor),
models default to "help whoever speaks." The harness must explicitly define
whom the agent serves. This is a design-time decision, not a prompt-time
afterthought.

### Trust Boundary Below the Application Layer

When AI-written code can't be trusted, push data invariant enforcement to a
layer beneath the application — database-level constraints, permission-embedded
data objects. The code can't violate what the infrastructure prevents.
Example: a database constraint that prevents negative account balances holds
regardless of what the agent writes.

---

## §3 Workflow

**The question**: What is the right engineering process for a coding agent?

Five stages, applied proportionally to task complexity:

### Stage 1 — Project Documentation

Build the cognitive framework before touching code. Generate `AGENTS.md` or
`README.md` if missing. "Teams friendly to remote work are friendly to AI
agents" — the same documentation that onboards a remote engineer onboards an
agent.

### Stage 2 — Requirements Clarification

Skip for simple tasks. For complex ones, clarify through dialogue before
coding. Ambiguity resolved in dialogue is cheaper than ambiguity discovered
in a failing test.

### Stage 3 — Design Document

Translate requirements into an implementation plan. Submit for user review
before writing code. A design document is the cheapest artifact to change.

### Stage 4 — Code Implementation + Testing

**"Tests pass" is the completion criterion, not "code written."** TDD-like
cycle: write test → implement → verify. The agent is not done until the
harness confirms correctness.

### Stage 5 — Documentation Synchronization

Update architecture docs when structural code changes land. Documentation
drift is a future agent's context failure.

### Harness Principles Applied to Coding

| Principle | Application |
|---|---|
| Constraints > guidance | Linter rules > "please follow style" in prompts |
| Automate verification | Test suites > human review |
| Fast structured feedback | Lint errors in tool return, not a separate step |
| Reliable rollback | Git branches, sandbox snapshots |

### Proposer-Reviewer for Code Quality

Advanced verification pattern: Proposer generates code → render → Reviewer
(vision LLM) evaluates visual result → feedback loop. Useful for UI code,
document generation, and any output where "running it" produces verifiable
artifacts.

---

## §4 Failure Recovery

**The question**: What happens when something goes wrong?

### Four Failure Layers

| Layer | Examples |
|---|---|
| **API** | Model provider errors, rate limits, timeouts, malformed responses |
| **Tool** | Command errors, file not found, permission denied |
| **Context** | Context overflow, lost state, stale information |
| **Control-flow** | Infinite loops, stuck states, budget exhaustion |

### Detection

- **Repeated-call fingerprinting** — same tool + same params = stuck
- **Consecutive-failure counters** per layer
- **Idle watchdog** — detect stalled streaming and silent hangs
- **Trajectory integrity monitoring** — structural repair if context corrupts

### Recovery Escalation (increasing visibility)

1. **Silent retry** — exponential backoff; distinguish foreground (user
   waiting, shorter backoff) vs background (can wait longer)
2. **Degrade and continue** — raise output cap, fallback model, continuation
   generation
3. **Surface to user** — only after all automatic recovery is exhausted

**Tool-layer errors: don't terminate the agent.** Turn the error into the
model's next input — the model can often self-correct. "File not found" →
model adjusts the path. The error is information, not a stop signal.

### Termination

- **Circuit breakers** — max consecutive failures of the same type
- **Death-spiral defense** — on error paths, disable model-invoking side
  effects; recursion-depth counter
- **Global caps** — max turns, budget cap, human escalation threshold

> "An agent's reliability is determined not by whether it makes mistakes, but
> by whether every class of error has detection, recovery, and termination
> paths."

---

## §5 Code as Problem-Solving

**The question**: When should the agent offload reasoning to code execution,
and how do you enforce business rules safely?

### Offload Reasoning to Code (5.2.1)

LLMs are weak at precise calculation, symbolic manipulation, and strict
logical deduction. Code enforces rigor. Division of labor: LLM understands
the problem and writes code; interpreter provides exact answers.

| Domain | Library |
|---|---|
| Math | sympy / scipy |
| Logic | constraint solvers |
| Data | pandas |

Trade-off: on weak models, code assistance dramatically lifts accuracy; on
strong reasoning models, the gain converges to near-zero. "How thick the
harness should be depends on where the model's capability boundary lies."

### Three-Tier Business Rule Safeguard (5.2.2)

For any agent that applies business rules (pricing, eligibility, policy):

1. **Natural language rules in system prompt** — for understanding and
   explanation
2. **Tool descriptions + parameter design as checklist** — guides the model
   to verify conditions before calling
3. **Server-side code validation from database ground truth** — final
   gatekeeper; never trusts the model's self-reported parameters

Key design: all policy facts read from the database; current time from the
server clock. The model's `expected_*` parameters exist for audit and
comparison only, never as trusted facts. Mismatch logging detects erroneous
beliefs or injection attempts.

-> Read `references/code-meta-patterns.md` for advanced applications:
sessionless design, code-driven multimedia generation, code as system
adapter, generative UI, and agent bootstrapping.

---

## Routing Map

These are companion skills in the ai-agents family. Co-triggering with
`agent-architecture` is expected when someone asks "I'm designing a system
that uses an LLM to write and execute code."

| Concern | Companion Skill |
|---|---|
| Agent orchestration & autonomy | agent-architecture |
| Tool interface design | agent-tool-design |
| Code design patterns | software-design |
| Code review | code-reviewer |
| Test design | test-design |
| Context window management | context-engineering |
| Cross-session capability growth / skill generation | agent-self-evolution |

---

## NOT For

**Litmus**: Is the question about building or improving a system that
generates and executes code autonomously? → here.

- "How do I write good code?" → `software-design`
- "Review this code someone wrote" → `code-reviewer`
- "Should I use an agent at all, or which orchestration pattern?" →
  `agent-architecture`

---

## References

| Reference | When to read |
|---|---|
| `references/search-and-editing.md` | Choosing a search strategy (regex vs glob vs semantic vs LSP); selecting an editing scheme; implementation tips for parallel tool calls, context management, and instant feedback |
| `references/code-meta-patterns.md` | Advanced applications: sessionless design, code-driven multimedia generation, code as system adapter, generative UI, agent bootstrapping |
