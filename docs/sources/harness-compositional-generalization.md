# Harnesses as Compositional Generalizers (Zhang & Khattab) — Source Attribution

Provenance for skill content synthesized from Alex Zhang and Omar Khattab's
blog post *Language model harnesses are compositional generalizers* (July
2026). This file is **not registered in any skill's References table** — it is
read by humans and by skill-building sessions, and is **never auto-loaded at
skill runtime**. It exists for human traceability and to lock citation
conventions.

Source (no vendoring): [Language model harnesses are compositional generalizers (Zhang & Khattab, July 2026)](https://alexzhang13.github.io/blog/2026/harness/)

## For skill-builders (read before extending this material)

**Official citation line.** Paste this verbatim into the intro of each
`references/*.md` file synthesized from this source (the `../../` path resolves
from `<skill>/references/`):

```
*Synthesized from [Language model harnesses are compositional generalizers (Zhang & Khattab, July 2026)](https://alexzhang13.github.io/blog/2026/harness/) — provenance in [docs/sources/harness-compositional-generalization.md](../../docs/sources/harness-compositional-generalization.md).*
```

**Two citation rules:**

1. **Reference files** carry the official citation line in their intro. Prose
   is paraphrased and clean — no inline source tags. Present genuinely
   contestable stances inline as "Zhang argues…".
2. **Body weaves** — material woven into an existing `SKILL.md` — carry **no
   citation line**. Record them only as a row in the map below. Attribute
   contestable stances inline as "Zhang argues…"; weave non-contestable
   technique as plain content.

**Other rules:**

- **Conceptual filenames.** Name reference files by concept (e.g.
  `harness-inductive-bias.md`), never `zhang-*`.
- **Paraphrase only.** No verbatim quotes from the post.

## Content map

| Concept | Skill | Location |
| --- | --- | --- |
| Harness as inductive-bias carrier; Locally In-Distribution (LID) principle | agent-architecture | references/harness-inductive-bias.md |
| Context offloading; programmatic sub-agent calling | agent-architecture | references/harness-inductive-bias.md |
| Equivalence classes over trajectories; context rot failure mode | agent-architecture | references/harness-inductive-bias.md |
| LID as quality criterion for the five harness functions | agent-architecture | SKILL.md body weave (Framing — The Harness Model) |

## Key claims extracted

- A harness `H: s -> a` carries the higher-level inductive bias that reduces
  unfamiliar/complex problems to compositions of simpler ones. This capacity,
  not tool invocation, is the harness's fundamental power.
- A good harness makes each individual LM call **locally in-distribution
  (LID)** — the observation is familiar even when the full task is OOD.
- **Context offloading** (input as symbolic variables) and **programmatic
  sub-agent calling** (results stored in REPL variables, never appended to the
  root context) are the two mechanisms that achieve LID.
- A good harness induces an equivalence relation over tasks: structurally
  similar tasks produce near-identical token trajectories for the root LM,
  enabling transfer across length and domain.
- Append-everything designs (ReAct, CodeAct, Claude Code, Codex) flood the
  root context and drift OOD — the "context rot" failure mode.
- Evidence (Recursive Language Models trained with RL on Qwen3-30B-A3B):
  training on short tasks generalizes to eval tasks 8–32x longer; training on
  one domain transfers to structurally similar domains. Base Transformers fail
  both, despite matching or exceeding train reward.

Contestable stances (present inline as "Zhang argues…"): that existing
production harnesses like Claude Code and Codex are architecturally flawed for
generalization because they append observations to a growing context; and that
compositional generalization must largely live in the harness rather than
emerge from the neural network.
