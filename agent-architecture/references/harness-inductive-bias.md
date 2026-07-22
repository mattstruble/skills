*Synthesized from [Language model harnesses are compositional generalizers (Zhang & Khattab, July 2026)](https://alexzhang13.github.io/blog/2026/harness/) — provenance in [docs/sources/harness-compositional-generalization.md](../../docs/sources/harness-compositional-generalization.md).*

# Harness as Inductive Bias

The five harness functions (`Context`, `Tools`, `Constrain`, `Verify`,
`Correct`) describe what a harness *does*. This reference describes what makes
a harness *good*: its capacity to carry a higher-level inductive bias that
reduces unfamiliar, complex problems to compositions of familiar, simple ones.

A harness is the program `H: s -> a` that sits between the environment and the
model. Its most-cited job is invoking tools. Zhang argues its more fundamental
job is simplifying an arbitrarily complex state `s` into smaller observations
that each individual LM call can reliably handle. Transformers are unreliable
compositional generalizers; the harness is where that missing inductive bias
can live.

---

## The Locally In-Distribution (LID) Principle

**A good harness shapes each LM call so its observation is locally
in-distribution** — familiar in structure relative to training data, even when
the full task trajectory is out-of-distribution (OOD).

This is the quality criterion for the five harness functions. "Verify" is
something the harness *does*; LID is a property the harness *achieves*. Two
harnesses can both provide context, call tools, and verify results, yet one
keeps every LM call in-distribution while the other drifts OOD over a long
trajectory. The first generalizes; the second rots.

Use LID as a design lens: for each LM call in your harness, ask whether its
prompt resembles something the model saw in training. If a call sees a bloated,
interleaved history no training example ever looked like, that call is OOD and
its output degrades — regardless of how much "context" it technically has.

---

## Two Mechanisms That Achieve LID

**Context offloading.** Pass input-specific context as a symbolic variable so
the root LM never sees the raw tokens directly. Two different tasks that share
a decomposition strategy then look near-identical at the first step, because
the domain-specific content has been abstracted behind a reference. Offloading
alone is insufficient — it does not stop tool outputs and sub-results from
flowing back into the root context over a long horizon.

**Programmatic sub-agent calling.** Treat sub-agents and tools as functions in
a code REPL. Their outputs are stored in variables in memory and passed between
further calls without the root LM ever reading them. This is what prevents
task-specific information from leaking back and pushing the root context OOD.
It is as important as offloading, not a nice-to-have on top of it.

Together they let the root LM move information through variables rather than
through its own context window.

---

## Equivalence Classes Over Trajectories

A good harness induces an equivalence relation over tasks: structurally similar
problems fall into the same class and produce near-identical token trajectories
for the root LM. If the root LM's view of a long task with context offloaded
looks token-for-token like a short task, the harness has effectively already
seen the long task. The same holds across domains that share a decomposition
(sort, filter, search, MapReduce): abstract away the domain tokens and two
problems become the same problem.

This is the mechanism behind compositional generalization: *if the system can
solve task X, it can transitively solve any Y in X's equivalence class* —
including tasks longer than the base model's context window and tasks in
unseen domains.

---

## Context Rot: The Failure Mode LID Prevents

Standard agent designs — ReAct, CodeAct, and production coding harnesses like
Claude Code and Codex — append every observation, tool output, and reasoning
step to a growing prefix. This supplies context, but the bloated history
quickly falls outside the training distribution. The root context drifts OOD,
and quality degrades even though nothing "failed." Zhang argues this makes
these harnesses architecturally weak at generalization, not merely unoptimized.

When an agent works on short tasks but degrades on long ones, or transfers
poorly to a new domain, suspect context rot before suspecting the model.

---

## Evidence

Recursive Language Models (an offloading + programmatic-subcall harness)
trained with RL on Qwen3-30B-A3B:

- **Length generalization.** Training only on short tasks generalized to
  held-out tasks 8–32x longer, across six benchmarks (MRCRv2, GraphWalks,
  LongBenchPro, OOLONG, OOLONG-Pairs, Ada-LEval).
- **Domain transfer.** Training on one domain transferred to structurally
  similar but token-disjoint domains (e.g., essay-authorship search → math
  reasoning search).
- **Baseline contrast.** The base Transformer's eval performance stayed flat
  despite its train reward matching or exceeding the harness's — what it
  learned did not extrapolate.

Caveat: the harness only helps if it learns a *generalizable* decomposition.
A short task can often be solved by offloading the whole problem to one
sub-call, collapsing back to the context-appending baseline. A light "nudge to
decompose" hint in the prompt corrects this where it occurs.

Cost: harness training ran 1.5–3x slower than base-Transformer training
(multiple steps per sample, waiting on sub-calls), but scales better as task
complexity grows.

---

## When This Applies

This is a harness-design lens, not a mandate to build RLMs or impose rigid
programmatic strategies (MapReduce, DP) on every agent — doing so invites the
bitter lesson. The transferable principle is narrow and durable: make each LM
call see a locally in-distribution observation, and let structurally similar
tasks look the same to the model. Most relevant when an agent must handle
long-horizon tasks, variable-length inputs, or transfer across domains — the
regimes where context-appending harnesses drift OOD.
