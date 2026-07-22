---
name: context-engineering
description: You MUST consult this skill when designing or reviewing the context an LLM agent sees at each inference call — system prompt structure, KV-cache layout, or context growth strategy. Also trigger when an agent repeats tool calls it already ran, when system prompt instructions fade mid-conversation, when cache-hit rates are unexpectedly low, or when deciding where to place volatile vs stable content in a long-running agent. NOT for cross-session memory (see agent-memory-rag), application code structure (see application-architecture), or orchestration patterns (see agent-architecture).
---

# Context Engineering

**What you show the model, and how you organize it, matters more to the
outcome than how smart the model is.**

This is the depth of the Context leg of the harness model — see
`agent-architecture` for the full model, the five harness functions, and
the ReAct loop.

---

## Framing — Context-Window Anatomy

Every inference call presents the model with a single flat sequence of
tokens. That sequence has two structural zones:

**Static prefix** — system prompt and tool definitions. Set once per
session (or per deployment). The model reads this on every turn.

**Dynamic trajectory** — message history and tool results. Grows with
each ReAct step. The model's working memory across the conversation.

The boundary between these zones is not just conceptual — it is the
architectural seam that determines cache efficiency (§2), compression
strategy (§3), and prompt stability (§1). Every design decision in this
skill operates on one or both zones.

---

## Symptom Table

| Symptom | Decision Point |
|---|---|
| Agent ignores instructions buried in a long prompt | §1 — prompt organization |
| System prompt maintained by many people has drifted into contradictions | §1 — prompt entropy |
| Low cache-hit rate; every turn reprocesses the whole context | §2 — unstable prefix |
| Timestamp or tool-order change at the top busts the cache each turn | §2 — volatile-data placement |
| Cost balloons as conversation grows unbounded | §3 — compression |
| Agent repeats tool calls already run / forgets earlier decisions | §3 — sliding-window info loss |
| Main context flooded with raw file/search output | §3 — isolation |
| Agent loses track of task progress or current state | §3 — status bar |

---

## §1 System Prompt Design

**The question**: How do you structure the static prefix so the model
reliably follows it?

**YAGNI gate.** Start minimal. Add prompt structure when ablation shows
the agent drifts without it. Disorganized information drops task success
significantly in experiments — but the fix is structure, not more
information.

**Process-driven vs rule-stacking.** Rules pile up over time and
contradict each other. A process-driven prompt sequences the agent through
steps: "First do X, then do Y, then decide Z." The model follows a
sequence reliably; it resolves contradictions poorly. When a flat rule
list grows beyond a handful of items, restructure it as a process.

**Structured prompts.** Section headers, XML or markdown delineation, and
consistent formatting are not cosmetic. The model treats structural
boundaries as semantic signal — content inside a clearly labeled section
is processed in that section's context. In tool-calling agents, where the
system prompt must simultaneously define persona, constraints, and tool
usage policy, structure is the difference between coherent and incoherent
behavior.

**Few-shot timing.** Examples are powerful but expensive: they consume
tokens in the prefix and bust the cache if they change. Use them when the
output format is complex or the target behavior is hard to describe
declaratively. Defer them until ablation confirms they improve outcomes.

**Business-rule refinement.** Distill rules from negative examples — each
rule should prevent a specific observed failure. Don't add speculative
rules. A rule that has no corresponding failure case is dead weight that
increases entropy without reducing errors.

**Entropy control.** Prompts maintained by many people decay. Engineering
practices that slow decay: version control the prompt as code, assign
ownership, run periodic ablation tests to verify each section still
improves outcomes, and remove sections that no longer do.

**Worked example.** Same agent instructions as a flat pile of 12 rules vs
organized into 3 process sections. Rule-stacking version: the agent skips
step 3 because rule 7 appears to contradict rule 3 — both are present but
their interaction is undefined. Process version: steps are sequential, the
contradiction is impossible because step 3 only executes after step 2
completes and its output is in scope.

Cross-refs: prompt injection → `agent-architecture` guardrails;
tool-definition design → `agent-tool-design`.

-> Read `references/prompt-design.md` for deeper trade-offs, structured-prompt
patterns, few-shot economics, and entropy-control practices.

---

## §2 KV-Cache-Friendly Layout

**The question**: How do you arrange the context so the model reuses
prior computation rather than reprocessing everything each turn?

The cache-cost lens: every design choice in §1 and §3 has a cache-hit
cost. This section makes the constraint explicit.

**Stable/append-only prefix.** The system prompt and tool definitions form
the prefix. If any part of the prefix changes between turns, the cache is
invalidated from that point forward — no reuse. Keep the prefix static;
append new information after it.

**Volatile-data-last.** Timestamps, counters, tool-list reordering —
anything that changes per-turn must go at the end of the context, never
in the prefix. The prefix is sacred. A single volatile field embedded in
the system prompt means the entire prefix is recomputed on every turn.

**Cache-cost awareness.** Every dynamic injection — a status bar update,
a tool-list reorder, a few-shot swap — busts the cache from its insertion
point forward. Design context layout so the stable portion is maximized
and volatile content is pushed as late as possible.

**Worked example.** An agent embeds `current_time: 2024-07-20T15:32:00Z`
at the top of the system prompt. Every turn, the entire prefix is
recomputed from scratch — thousands of tokens of tool definitions and
policy text re-tokenized and re-attended on every call. Moving the
timestamp to a trailing user message leaves the prefix unchanged: cache
hits resume, latency drops, cost drops.

-> Read `references/kv-cache-context.md` for chat-template internals,
prompt-cache vs KV-cache mechanics, editable/composable cache patterns,
and cache-hit maximization strategies.

---

## §3 Managing Context Growth

**The question**: How do you keep the growing trajectory useful and
bounded?

As the ReAct loop accumulates steps, the trajectory grows. Left
unmanaged, it exceeds the context window, degrades retrieval quality, and
drives up cost. Three tactics, in order of preference:

1. **Compression with retention priorities.** When the trajectory exceeds
   the window, summarize. Compression is lossy, so apply retention
   priorities: (1) architectural decisions and constraints — never
   summarize; (2) modified files and change records — keep completely;
   (3) verification status (pass/fail) — retain; (4) unresolved TODOs —
   retain; (5) tool output — can be deleted, keep only the conclusion.
   Identifiers — UUIDs, hashes, URLs, filenames — must be preserved
   exactly; a summarized identifier is a broken reference.

2. **Isolation over compression.** Bojie Li argues isolation over
   compression: keep bulky intermediate content out of the main context
   entirely by delegating to sub-agents, rather than compressing after
   the fact. Compression is a lossy post-hoc remedy; isolation insulates
   the main context from noise from the start. The cost: the sub-agent
   doesn't see the full main context, so the task description must be
   self-contained. The deeper reason isolation beats compression: it keeps
   each LM call *locally in-distribution* — offloading task-specific tokens
   behind references so the main context stays familiar and structurally
   similar tasks look the same to the model. Cross-ref sub-agent mechanics →
   `agent-tool-design`; multi-agent context architecture →
   `multi-agent-collaboration`; the LID rationale and context-offloading /
   programmatic-sub-call mechanisms → `agent-architecture`
   `references/harness-inductive-bias.md`.

3. **Agent status bar.** Convert implicit state — step count, tool budget
   remaining, task progress, time elapsed — into explicit structured
   information appended to the trajectory. Makes the agent's sense of
   current position legible. Cache-cost: status-bar updates bust the
   cache from their insertion point — design placement using §2's
   volatile-data-last principle.

**Worked example.** "Find the payment callback handler in the codebase."
Main agent greps directly: dozens of files, tens of thousands of tokens
of raw code enter the context — most becomes permanent noise that the
model must attend through on every subsequent turn. Delegated to a search
sub-agent: the main context gains only two messages (task description +
conclusion: "`handle_callback` in `src/payment/callbacks.py`, 2 call
sites") — tens of thousands of intermediate tokens are discarded with the
sub-agent's context.

-> Read `references/compression-strategies.md` for hierarchical
compression mechanisms, the ILC-is-retrieval premise, task-type-coupled
strategies, and status-bar composition patterns.

---

## Routing Map

These are companion skills in the ai-agents family. Load the relevant one
when building that layer.

| Concern | Companion Skill | Source |
|---|---|---|
| Cross-session memory (what to persist) | agent-memory | Ch3 |
| Retrieval pipeline for knowledge bases | rag-design *(planned)* | Ch3 §3.2–3.3 |
| Tool interface design (schema, descriptions) | agent-tool-design | Ch4 |
| Agent orchestration & guardrails | agent-architecture | Ch1 |
| System prompt optimization from experience | agent-self-evolution | Ch8 |

---

## NOT For

**Primary litmus**: Information living in the context window this session
→ here. Knowledge that persists across sessions or is retrieved on demand
→ `agent-memory-rag`. (Forward-reference — `agent-memory-rag` does not
exist yet.)

- Agent Skills as progressive-disclosure context → `skill-creator`
- Code-level design → `software-design`
- The harness model itself / orchestration / guardrails → `agent-architecture`

---

## References

| Reference | When to read |
|---|---|
| `references/prompt-design.md` | Deeper prompt-organization trade-offs, structured-prompt patterns, few-shot economics, business-rule refinement, entropy-control practices |
| `references/kv-cache-context.md` | Chat-template internals, prompt-cache vs KV-cache mechanics, editable/composable cache patterns, cache-hit maximization under changing tool sets |
| `references/compression-strategies.md` | Hierarchical compression mechanisms, the ILC-is-retrieval premise, retention-priority design, task-type-coupled compression, isolation mechanics, status-bar composition patterns |
