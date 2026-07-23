---
name: agent-memory
summary: Cross-session memory design for personalized agents: storage, consolidation, retrieval
type: design
description: You MUST consult this skill when designing cross-session memory for personalized agents — choosing storage formats, handling contradictory memories, building consolidation pipelines, evaluating memory quality, or deciding what to persist. Also trigger when an agent forgets user preferences across sessions, surfaces conflicting facts, grows unbounded memory, or needs to anticipate user needs from past context. NOT for operating an existing knowledge base (see knowledge-base), managing the context window within a session (see context-engineering), building a retrieval pipeline for a document corpus (see rag-design), or agent runtime orchestration (see agent-architecture).
---

# Agent Memory

**Memory is the mechanism that turns a stateless assistant into a personalized agent.**

Without it, every session starts from zero. With it, the agent knows who the
user is, what they care about, and what they've done before — and can act on
that knowledge proactively.

---

## Framing — The Two-Tier Architecture

Production memory systems use two complementary stores:

**Tier 1 — Resident structured facts.** A compact, always-in-context
representation of what the agent knows about the user. Advanced JSON Cards
(see §1) are the canonical format: small enough to fit in every prompt,
structured enough to support partial updates and disambiguation. This tier
provides the *overview* — the agent always knows the user's name, preferences,
and key relationships.

**Tier 2 — On-demand raw conversation retrieval.** The full history of past
sessions, stored verbatim and retrieved via semantic search when the agent
needs precise details. This tier provides the *details* — the exact wording of
a past request, the specific address the user mentioned three sessions ago.

Together, these tiers enable **proactive service**: the agent can synthesize
structured facts (Tier 1) with retrieved details (Tier 2) to anticipate needs
the user hasn't expressed yet ("Your passport expires before your Tokyo trip").
Neither tier alone achieves this — Tier 1 lacks precision, Tier 2 lacks
overview.

**Cognitive science mapping.** The two-tier model loosely maps to human memory:
episodic memory (specific past events, Tier 2), semantic memory (general facts
about the user, Tier 1), and procedural memory (learned behavioral patterns,
encoded in Tier 1 preference fields). This framing is useful for communication,
not implementation — the engineering decisions are in §1–§5.

---

## Symptom Table

| Symptom | Decision Point |
|---|---|
| Agent forgets user preferences across sessions | §1 — Storage format |
| Agent surfaces contradictory memories | §2 — Conflict resolution |
| Agent's memory grows unbounded | §3 — Consolidation |
| Agent remembers facts but can't anticipate needs | §4 — Evaluation (stuck at Level 1) |
| Agent leaks PII from memory | §5 — Privacy |

---

## YAGNI Gate — Does This Agent Need Memory?

Memory adds real complexity: storage, retrieval, conflict resolution,
consolidation, and privacy surface. Apply it only when the use case demands it.

Three criteria that justify memory:

1. **Repeated user interactions** — the same user returns across multiple sessions
2. **Personalization improves outcomes** — knowing the user's history changes what the agent does
3. **State too large for single-session context** — the relevant history exceeds what fits in one context window

If none of these hold, a stateless agent is the right design. Many agents —
single-use tools, document processors, code assistants with no user model —
work correctly without any cross-session memory. Don't add the complexity
unless the use case demands it.

---

## §1 Storage Format Spectrum

**The question**: What data structure should hold user memories?

Five formats exist on a spectrum from simple to capable. The right choice
depends on the volume, criticality, and structure of the data being stored.

| Format | Structure | Update model | Best for |
|---|---|---|---|
| **Simple Notes** | Atomic key-value facts | Full replacement | High-volume, non-critical facts |
| **Enhanced Notes** | Full paragraphs with context | Full replacement | Rich context, infrequent updates |
| **JSON Cards** | Hierarchical key-value with categories | Partial field updates | Structured data with known schema |
| **Advanced JSON Cards** | JSON Cards + backstory, person, relationship, timestamp | Partial field updates + disambiguation | Critical low-volume personalization data |
| **Code** | Executable Python objects + constraint methods | Regeneration | Deterministic aggregation, constraint enforcement |

**Simple Notes** store atomic facts as flat key-value pairs. O(1) read/write
operations, but associations between facts are lost. Suitable for
high-volume non-critical preferences where context doesn't matter.

**Enhanced Notes** store memories as full paragraphs preserving the context
in which a fact was learned. Semantically complete but hard to partially
update — changing one field requires rewriting the whole note.

**JSON Cards** add hierarchical structure and categories, enabling partial
field updates without rewriting the whole record. Schema rigidity is the
trade-off: new fact types require schema changes.

**Advanced JSON Cards** extend JSON Cards with `backstory`, `person`,
`relationship`, and `timestamp` fields. The `backstory` field is the key
addition — it records *why* a fact was stored, enabling disambiguation when
the same user provides different values in different contexts (e.g., "home
address for work deliveries" vs "vacation address"). This is the recommended
format for resident structured facts (Tier 1).

**Code** (Bojie Li argues) represents user memory as executable Python objects
with constraint methods. This enables deterministic aggregation across sessions,
conflict detection via constraint violations, and enforcement of invariants
(e.g., "age must be consistent with birth year"). Highest capability, highest
complexity — justified only when constraint enforcement is a hard requirement.

**The hybrid recommendation.** Most production systems use:
- Advanced JSON Cards for Tier 1 (resident structured facts, always in context)
- Raw conversation storage for Tier 2 (on-demand retrieval via RAG techniques)

This combination captures the overview (Tier 1) and the details (Tier 2)
without the complexity of a full Code-based memory system.

-> Read `references/memory-formats.md` for concrete schema examples, migration
patterns, and format selection decision criteria.

---

## §2 Conflict Resolution

**The question**: When the same user provides contradictory information across
sessions, which value wins?

Contradictions are inevitable in long-running memory systems. A user moves,
changes preferences, or corrects a previous statement. Three resolution
strategies cover most cases:

**Timestamp-based priority.** For mutable facts (address, phone number,
current preference), the most recent explicit statement wins. Requires
reliable timestamps on every memory write.

**Source credibility.** An explicit user correction ("Actually, my address is
now...") outranks an inferred fact ("the user mentioned this address in
passing"). Tag memories with their source type at write time.

**Contextual disambiguation.** Advanced JSON Cards carry a `backstory` field
that records the context in which a fact was stored. Two different home
addresses may both be correct — one for work deliveries, one for personal
mail. The backstory field enables the agent to distinguish them rather than
treating them as a conflict.

**The Mem0 pattern.** Extract-compare-decide pipeline: when a new memory
arrives, extract the candidate fact, compare it against existing memories,
then decide: ADD (no existing fact), UPDATE (same fact, new value), DELETE
(user explicitly revokes a fact), or NOOP (duplicate). This pipeline makes
conflict resolution explicit and auditable rather than implicit in storage
logic.

---

## §3 Consolidation and Compression

**The question**: How do you prevent memory from growing unbounded?

Without active management, memory accumulates indefinitely. Raw session logs
grow faster than they can be retrieved efficiently, and redundant facts
accumulate across sessions.

**Dual gating.** Trigger consolidation when *both* conditions hold:
(a) enough time has elapsed since the last consolidation, AND
(b) enough new sessions have accumulated since the last consolidation.
Either condition alone produces either too-frequent or too-infrequent runs.

**Consolidation pipeline.** Three stages:
1. **Importance scoring** — rank memories by recency, frequency of reference, and explicit user emphasis
2. **Clustering** — group related memories (all facts about the user's car, all address variants)
3. **Abstraction** — generalize clusters into a single canonical memory, discarding redundant detail

**Separate accumulation from consolidation.** Accumulation is fast and
continuous (every session appends). Consolidation is periodic and expensive
(requires re-reading and re-writing many memories). Running them on different
time windows prevents consolidation from blocking session writes.

**The "User as Code" pattern** (Bojie Li argues): split memory into two phases.
The *memory phase* is an append-only log of raw facts from each session —
cheap to write, never modified. The *structuring phase* periodically reads
the log and regenerates the executable Python object (see §1 Code format)
from scratch. This makes the structured representation always consistent with
the full history, at the cost of periodic regeneration overhead.

For retrieval-based memory compression (compressing Tier 2 raw conversation
storage), → see `rag-design` for contextual retrieval patterns.

---

## §4 Three-Level Evaluation

**The question**: How do you know if your memory system is actually working?

Most memory systems are tested only at Level 1. Levels 2 and 3 require
deliberate test design.

**Level 1 — Basic Recall.** The agent retrieves a fact that was explicitly
stored in a single session. "What's my account number?" → returns the stored
value. Passing Level 1 means storage and retrieval work. Most systems reach
this level.

**Level 2 — Multi-Session Retrieval.** The agent gathers and reconciles
information scattered across multiple sessions, including disambiguation.
"Which car needs service?" → correctly identifies the right vehicle when the
user has two cars mentioned in different sessions. Passing Level 2 requires
correct conflict resolution (§2) and the ability to aggregate across sessions.

**Level 3 — Proactive Service.** The agent synthesizes memories to anticipate
needs the user hasn't expressed. "Your passport expires before your Tokyo
trip" — the agent connected the passport expiry date (one session) with the
trip dates (another session) and surfaced the conflict unprompted. Passing
Level 3 requires the two-tier architecture: Tier 1 provides the overview that
enables synthesis, Tier 2 provides the precise details.

Most systems plateau at Level 1. Level 3 is the goal for personalized agents
that provide genuine value across sessions.

-> Read `references/memory-evaluation.md` for concrete test scenarios, per-level
rubrics, and the two-tier architecture as a prerequisite for Level 3.

---

## §5 Privacy and PII

**The question**: How do you prevent the memory system from becoming a PII
liability?

Memory systems accumulate sensitive data by design. Without active management,
they become a liability.

**Detect locally.** Use a local model for PII classification — don't send
potentially sensitive data to an external API to decide whether it's sensitive.
The classification step itself is a privacy boundary.

**Sanitize before storage, not after retrieval.** Filtering PII at retrieval
time means it was stored in the first place. Sanitize at the write path so
the data never enters the store.

**Define the policy explicitly.** The boundary between "useful personalization"
and "privacy violation" is context-dependent. Document which categories the
system detects and stores: names, addresses, financial data, health data,
relationship data. The policy must be explicit — implicit policies drift.

**Minimum necessary principle.** Store only what the agent needs to provide
the service. A preference for dark mode doesn't require storing the user's
home address. Scope each memory category to the capabilities it enables.

---

## Routing Map

These are companion skills in the ai-agents family. Load the relevant one
when building that layer.

| Concern | Companion Skill | Source |
|---|---|---|
| Retrieval pipeline for memory at scale | rag-design *(planned)* | Ch3 §3.2–3.3 |
| Context-window injection of memories | context-engineering | Ch2 |
| Memory tool interface design | agent-tool-design | Ch4 |
| Orchestration & autonomy | agent-architecture | Ch1 |
| Operating a personal wiki | knowledge-base | — |
| Sleep consolidation / experience distillation lifecycle | agent-self-evolution | Ch8 |

---

## NOT For

**Litmus**: Is the question about designing how an agent persists and recalls
user-specific information across sessions? → here.

- Operating a specific knowledge base (Obsidian, Notion, a personal wiki) → `knowledge-base`
- Managing what fits in the context window for a single session → `context-engineering`
- Building a retrieval pipeline for a document corpus (not user memory) → `rag-design`
- Agent runtime loop, orchestration, guardrails → `agent-architecture`

---

## References

| Reference | When to read |
|---|---|
| `references/memory-formats.md` | Concrete schema examples for each format, migration patterns, format selection decision criteria, the hybrid recommendation in detail |
| `references/memory-evaluation.md` | Three-level evaluation framework with concrete test scenarios, per-level rubrics, two-tier architecture as Level 3 prerequisite |
