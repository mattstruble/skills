*Synthesized from public RL generalization research — full paper list and provenance in [docs/sources/rl-generalization-literature.md](../../docs/sources/rl-generalization-literature.md).*

# Compositional Coverage

How to structure training environments so the model learns reusable,
composable skills rather than fused, per-environment behaviors.

---

## The Two Conditions (Redhardt et al. 2025)

A model can generalize to unseen factor combinations from a training set that
grows only modestly with the number of factors, BUT only under two conditions:

1. **Compositional support**: every factor value appears somewhere in training.
   Missing values = guaranteed failure on any combination involving them.

2. **Connected support**: no factor value appears *only* glued to one fixed
   partner. If "database tool" only ever co-occurs with "retail domain," the
   model learns one fused behavior ("retail database lookup") rather than
   independent "use database" and "retail reasoning" skills.

When both hold, the required training set grows linearly with the number of
factors (not exponentially with combinations). When violated (gSCAN 2020),
models drop to near 0% on the violated split.

---

## The Diagnostic: Linear Decodability

Models that generalize compositionally have individual factors **linearly
readable** from their internal activations. Confounded models do not.

This provides a concrete check: if you can train a linear probe to identify
"which tool was used" from intermediate activations regardless of domain, the
model has learned the tool as an independent factor. If the probe only works
within one domain, the factors are confounded.

---

## Crossed vs Nested Design

| Design | Structure | Result |
|---|---|---|
| **Crossed** | Each tool exercised across many domains | Reusable skills |
| **Nested** | Tool locked to one domain | Fused behaviors, no transfer |

**Construction check**: for each factor (tool, domain, failure mode, horizon),
verify that every value appears in combination with multiple values of every
other factor. The concern is factor *usage* patterns, not mere availability.

Sharing one tool interface across all environments is fine and helpful. What
you must avoid is any tool being useful in *only* one domain.

---

## Composable Environment Building (RACES 2026)

Environments built from composable verified building blocks produce more
reusable capability than flat lists of unrelated tasks:
- 50 composed environments achieved same transfer as 300 standalone
- Composition operators: SEQUENTIAL (chain outputs), PARALLEL (combine
  independent), SORT (order results), SELECT (conditional routing)
- Key insight: codomain of one environment matching domain of another enables
  automatic fusion

**Requirements for composability:**
- Each environment has well-defined input/output types
- Verification is preserved across composition (if each piece verifiable,
  composition is verifiable)
- Intermediate results are checkable (for learning signal in deep chains)

**Caveat**: deep dependency chains (8+ steps, like Craftax's achievement tree)
need intermediate signal. A single reward at the end of a very deep chain
produces no learning if the model can't even reach the first intermediate
milestone.

---

## The URLB Trap: Don't Reward Diversity Directly

Methods that explicitly optimize for a diverse set of reusable skills transfer
*worse* downstream (URLB, Laskin et al. 2021).

**Why**: optimizing for skill diversity rewards being *distinguishable* (each
skill maximally different from others) rather than being *useful* (each skill
actually accomplishes something). The resulting skills are theatrical —
visually distinct but functionally useless.

**Correct approach**: get reusability as a by-product of task diversity plus
outcome checking. If the model must actually solve varied tasks to get reward,
it naturally develops reusable components. Directly optimizing for the
components themselves short-circuits this.

---

## Capacity Saturation and Negative Transfer

Multi-task training has capacity limits (Meta-World, Yu et al. 2019):
- 10 tasks: ~88% success rate
- 50 tasks: ~35-38% success rate (same model)

Single-domain training can actively hurt other domains: math-only RL dropped
code performance by 22-38 points (Huan et al. 2025). Cross-domain effects can
even flip sign between base and instruction-tuned models (Li et al. 2025).

**Design rules:**
- Measure the effect on *other* capabilities when you add training on new domains
- Scale model capacity or keep training modular when interference appears
- Report cross-task metrics, not just the target task's score
