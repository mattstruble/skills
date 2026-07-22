*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

# Real-Time Thinking: Three Transferable Principles

Three design principles from Ch9 (Multimodal & Real-Time Interaction) that
apply to any agent needing deep reasoning while staying responsive.

---

## 1. Fast/Slow Thinking Decomposition

**Design trigger**: Does your agent need deep reasoning while staying
responsive? If yes, decouple the interaction model from the reasoning model.

The fast model owns the interaction loop — holds the conversation, responds
immediately, keeps the user engaged. The slow model runs in the background for
complex reasoning, search, or multi-step planning; results stream back and the
fast model weaves them in at a natural moment.

Three patterns illustrate the design space:

- **Delegation** (GPT-Live): interactive model holds the conversation; when
  it hits a task requiring search or reasoning, it delegates to a background
  frontier model (GPT-5.5 at launch) while continuing to hold the floor.
- **Separation** (Pine AI): the phone interaction layer and the reasoning
  model are explicit separate services — interaction stays responsive,
  reasoning runs asynchronously.
- **Internalization** (Step-Audio R1): thinking baked directly into a single
  model — "thinks while speaking," no separate slow model.

Delegation is the most general: reasoning-model depth with interaction-model
latency, and the two can be upgraded independently.

---

## 2. Cascade vs End-to-End Tradeoff

Cascade (modular pipeline) gives per-module tuning, interpretability,
debuggability, and independent optimization. End-to-end buys lower latency
and preserves cross-modal fidelity that discrete interfaces discard — at the
cost of heavier training data requirements and weaker interpretability.

**The bottleneck-information principle**: What decides performance is usually
not whether an intermediate representation (a bottleneck) exists, but what
information that bottleneck carries. Upgrade the bottleneck to carry
task-relevant information and the end-to-end accuracy advantage narrows.

Before switching from a modular pipeline to a unified model, ask whether the
bottleneck is discarding information the downstream stage needs. Enriching the
bottleneck is usually cheaper than retraining a unified model.

---

## 3. Data > Architecture in Labels

Bojie Li argues that when a model wavers on a decision — turn-taking, action
selection, boundary classification — the root cause is often not the
architecture but the training labels. Specifically: labels annotated from a
"God's-eye view," using information available to the annotator but unavailable
to the model at decision time.

The fix is re-annotation using only the information the model can observe at
the moment it must decide. Causally consistent labels eliminate the spurious
wavering.

This echoes Ch7's "data matters more than algorithms" but is specific to
online decision-making under partial observability. Before adding architectural
complexity to fix wavering behavior, audit the training labels for future
information leakage.
