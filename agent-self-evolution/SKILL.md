---
name: agent-self-evolution
description: You MUST consult this skill when designing agents that improve across sessions without retraining — building experience accumulation systems, implementing workflow record/replay, creating skill-generation pipelines, designing system prompt optimization loops, or building tool-creation systems. Also trigger when asking "how does this agent get better over time?" or designing the learning lifecycle (distill → organize → apply → evolve). NOT for user memory storage/retrieval (see agent-memory), tool interface design (see agent-tool-design), prompt structure or KV-cache layout (see context-engineering), post-training or weight changes (see agent-post-training or ml-post-training), or code generation patterns (see coding-agent-design).
---

# Agent Self-Evolution

**The agent doesn't learn automatically — learning must be explicitly designed.**

The attention mechanism is closer to retrieval than to induction. Dump raw experience into context and the model can recall it, but it won't distill it into reusable patterns on its own. Self-evolution is the explicit design of that distillation: externalize experience into persistent, retrievable, reusable resources — knowledge bases, code tools, skill documents — so the agent becomes more capable with each task, not just more informed.

---

## YAGNI Gate — Does This Agent Need to Evolve?

Most agents work correctly as static systems. Self-evolution adds real complexity: distillation pipelines, storage management, verification gates, safety boundaries. Apply it only when:

1. **The domain is dynamic** — business rules, APIs, or procedures change faster than you can update the agent manually
2. **Repetition is the bottleneck** — the agent rediscovers the same solutions session after session
3. **Domain knowledge is non-public** — the base model lacks the specific knowledge, and it can only be acquired through practice

If none of these hold, a well-designed static agent with a good knowledge base is the right design. Don't add the learning machinery unless the use case demands it.

---

## Framing — Three Products of Externalized Learning

Every piece of experience the agent distills takes one of three forms. The form determines where it lives and how it's used:

| Product | Form | Content | Usage |
|---|---|---|---|
| **Knowledge Entry** | Fact or rule in a knowledge base | "Company A refunds require verifying the last four digits of the card" | Semantic search or exact retrieval |
| **Code Tool** | Executable function or MCP tool | "API call sequence for querying account balance" | Called with parameters; deterministic |
| **Skill Document** | Natural language SKILL.md | "Best practices for handling insurance claims" | Loaded on demand via progressive disclosure |

**Rule of thumb for which form:**
- Purely factual → knowledge base entry
- Repeatable procedure with stable parameters → code tool
- Strategic process with shifting business rules → skill document

Real systems mix all three. A refund workflow might produce all three: a fact ("this carrier requires branch address"), a tool (the API call sequence), and a skill (the full process with judgment calls).

---

## Framing — The Learning Lifecycle

Self-evolution operates across four layers, each building on the previous:

| Layer | Mechanisms | Problem Solved |
|---|---|---|
| **Knowledge Distillation** | Strategy summaries, workflow recording, failure reflection | Extract reusable knowledge from experience |
| **Knowledge Organization** | Skills, sleep consolidation | Structure and index knowledge for retrieval |
| **Knowledge Application** | System prompt optimization | Inject knowledge into the agent's behavior patterns |
| **Engineering Support** | Cross-session continuation | Enable long tasks to persist across sessions |

---

## §1 When to Use Which Mechanism

### Strategy Summaries
**Use when**: the agent solves complex, multi-step problems where the approach itself is the valuable artifact.

After a successful trajectory, an LLM reflects on the process and generates a structured note: what methods were used, what pitfalls were encountered, what the key steps were. The note is vectorized and stored. On future similar tasks, semantic search retrieves the relevant notes and injects them as examples.

**Transferability gate**: not every trajectory deserves to become experience. Ask: will this lesson carry over to similar tasks? A fix valid only for one specific input has no place in long-term memory.

→ Read `references/experience-distillation.md` for the GAIA pattern and transferability criteria.

### Workflow Recording and Replay
**Use when**: the agent performs repetitive procedural tasks where the steps are stable, the parameters vary (different recipient, different search keyword, same core flow), **and the environment changes infrequently**. UI redesigns, API version changes, or frequent A/B tests cause high replay failure rates and negate the speedup — in those environments, the overhead of constant fallback-and-relearn may exceed the cost of running the full agent every time.

Record the first successful execution as a parameterized state machine. Each state carries a verification predicate — a condition that must hold before the next action. On replay, check the predicate against the live environment before acting. If a predicate fails, fall back to full agent reasoning and regenerate the workflow.

**Pre-storage verification gate**: after compiling a workflow, reset the environment and replay from scratch before storing. This blocks workflows that execute all steps but never accomplish the task.

→ Read `references/experience-distillation.md` for state machine design and verification predicates.

### Failure Reflection (Reflexion Pattern)
**Use when**: the agent encounters recoverable failures and the failure mode is likely to recur.

After a task fails, the agent reflects in natural language on the cause and stores the reflection in episodic memory. On the next similar task, the reflection is read back as context. No model parameters are updated — this is evolution without weight changes.

Failure experience crystallizes into two forms: error pattern libraries (which method fails under which circumstances) and negative rules ("never cancel subscriptions with this carrier by phone").

→ Read `references/experience-distillation.md` for the Reflexion pattern and negative rule design.

### System Prompt Optimization
**Use when**: the agent's behavioral rules need sharpening from edge cases, and the failures are interpretable enough to generate precise rule updates.

Bojie Li argues the essence of system prompt learning is sharpening rule boundaries through edge cases. Most rules work in typical scenarios; the gray zone is where they fail. A single failure case can produce a precise rule update — far more data-efficient than RL, and fully interpretable.

Two modes:
- **Online (case-by-case)**: a coding agent reads the existing prompt, generates a diff for the specific failure, and submits for human review. Interpretable, accountable, fits high-stakes settings.
- **Offline (batch)**: automated frameworks (DSPy, OPRO, GEPA) optimize against an evaluation set. Efficient but requires scored task sets; liable to overfit phrasing.

In practice: batch-optimize the initial prompt with an automated framework, then let the online diff approach carry continuous evolution after launch.

→ Read `references/prompt-evolution.md` for the full treatment.

### Sleep Consolidation
**Use when**: the agent accumulates user memory or experience across many sessions and the store is growing noisy — redundant entries, contradictory facts, stale pointers.

Consolidation is a background process that runs asynchronously, never during user interaction. Two gating conditions must both hold before it triggers: enough time since the last consolidation, AND enough new sessions accumulated. Either condition alone produces runs that are too frequent or too infrequent.

The four-stage pattern (from Claude Code's background consolidation): **Orient** — read the existing memory index to understand the current knowledge landscape; **Gather** — search recent sessions for new information worth persisting and detect contradictions; **Consolidate** — merge new signals into existing topic files rather than spawning near-duplicates, convert relative dates to absolute, delete disproven facts; **Prune & Index** — cap index size, drop stale pointers.

Key design constraints: the consolidation sub-agent's permissions are confined to the memory directory; distributed locks prevent concurrent runs; failures roll back and retry next time.

**Boundary with agent-memory**: this skill owns *when* to consolidate and *how to structure the consolidation pipeline*. The storage algorithms (clustering, conflict versioning, retrieval) live in `agent-memory`.

→ See `agent-memory` for storage format selection, conflict resolution, and the consolidation algorithms.

### Tool Creation (Voyager Cycle)
**Use when**: the agent repeatedly needs capabilities that don't exist in its current tool set, and the domain is open enough that predefined tools can't cover it.

The cycle: explore → iterate on failure → verify task completion → store → reuse. The agent identifies a capability gap, searches for or writes code to fill it, iterates on failures using environmental feedback, verifies the task actually succeeded, then stores the tool for future reuse. Tools are hierarchical and composable — a "portfolio analysis" tool can build on a "get stock price" tool.

**Safety first**: run tool creation in a sandbox; security-scan newly created tools; maintain a whitelist of permitted tool types; set limits on library growth; schedule periodic human review.

→ Read `references/autonomous-capability-growth.md` for the Voyager cycle and safety boundaries.

---

## §2 Three-Layer Capability Accumulation

Self-evolution compounds across three levels:

**Tool level**: successfully created tools enter the library and become building blocks for future tools. Capability grows hierarchically.

**Knowledge level**: every tool created brings heuristic knowledge — which libraries suit which tasks, which APIs work without registration, which libraries fight the environment. This meta-knowledge guides future tool creation.

**Strategy level**: through repeated practice, the agent improves its self-evolution strategy itself — better library selection, more concise implementation, more thorough testing. In the short run, this accumulates in system prompts and skills; once stable, it can be baked into weights via RL.

Bojie Li argues this is the fullest expression of the "endorse the direction, stay pragmatic about the pace" stance toward the Bitter Lesson: extend the logic of capability growth from inside the model (parameter scale) to the outside world (the scale of tools and knowledge bases). This is a contestable philosophical stance — the pace and ultimate ceiling of externalized learning relative to parameter learning remain open questions.

---

## Symptom Table

| Symptom | Decision Point |
|---|---|
| Agent rediscovers the same solution every session | §1 — Strategy summaries or workflow recording |
| Repetitive browser/API tasks burn expensive LLM calls every time | §1 — Workflow recording (only if environment is stable; high-churn UIs negate the speedup) |
| Agent repeats the same failure mode across sessions | §1 — Failure reflection |
| Agent's behavioral rules are too coarse for edge cases | §1 — System prompt optimization |
| Agent can't complete tasks because the tool doesn't exist | §1 — Tool creation (Voyager cycle) |
| Tool library is growing but selection accuracy is dropping | §2 — Tool discovery (see agent-tool-design) |
| Self-evolution is drifting from original intent | §1 — Safety boundaries |

---

## Routing Map

| Concern | Companion Skill | Source |
|---|---|---|
| Storage mechanics for distilled knowledge | agent-memory | Ch3 |
| Retrieval pipeline for knowledge bases | rag-design *(planned)* | Ch3 §3.2–3.3 |
| Tool interface design (schema, descriptions) | agent-tool-design | Ch4 |
| Prompt structure and KV-cache layout | context-engineering | Ch2 |
| Weight changes (SFT, RL, reward design) | agent-post-training / ml-post-training | Ch7 |
| Code generation patterns | coding-agent-design | Ch5 |
| Skill generation as a meta-capability | skill-creator | Ch2 §2.5 |
| Agent orchestration and guardrails | agent-architecture | Ch1 |

---

## NOT For

**Litmus**: Is the question about designing how an agent accumulates and applies experience across sessions without changing weights? → here.

- Storing and retrieving user preferences or facts → `agent-memory`
- Designing the schema, descriptions, or interface of a tool → `agent-tool-design`
- Structuring the system prompt or managing KV-cache → `context-engineering`
- Fine-tuning, SFT, RL, or reward design → `agent-post-training` / `ml-post-training`
- Code generation patterns in a coding agent → `coding-agent-design`

---

## References

| Reference | When to read |
|---|---|
| `references/experience-distillation.md` | Strategy summaries (GAIA pattern), workflow recording (state machine + verification predicates), failure reflection (Reflexion), transferability criteria |
| `references/autonomous-capability-growth.md` | Tool discovery, tool creation (Voyager cycle), three-layer capability accumulation, safety boundaries |
| `references/prompt-evolution.md` | System prompt learning (Karpathy), edge-case sharpening, coding-agent-as-prompt-editor, automated frameworks (DSPy, OPRO, GEPA) |
