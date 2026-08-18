---
name: "rl-generalization"
summary: "Designing RL training curricula that produce broad, transferable capability rather than narrow skills"
type: "design"
description: "You MUST consult this skill when designing training curricula for broad transfer, choosing environment diversity strategies, deciding factor coverage for compositional generalization, setting difficulty calibration bands, diagnosing whether training produced narrow vs general capability, or deciding between environment breadth vs depth. Also trigger when asking 'why did this training not generalize?', when transfer to held-out tasks is poor despite good training scores, or when designing procedural task generators. NOT for training mechanics or implementation (→ ml-post-training), eval system design (→ agent-evaluation), or deciding whether to train at all (→ agent-post-training)."
---

# RL Generalization

**Breadth is something you engineer and then measure, not something training gives you for free.**

A consistent body of work identifies which properties of a training environment
produce transfer and which produce a narrow skill. This skill distills those
findings into design rules for anyone building training curricula.

---

## Symptom Table

| Symptom | Section |
|---|---|
| Training score high but held-out performance poor | §1 — Environment diversity insufficient |
| Model memorizes per-environment cues | §1 — Need more distinct environments |
| Capability doesn't compose across factors | §2 — Factor coverage violated |
| Model solves medium problems but fails easy and hard | §3 — Difficulty band miscalibrated |
| Reward climbs but true quality falls | §4 — Reward hackable or non-outcome-based |
| RL gain doesn't reproduce on different model family | §6 — Single-family validation trap |
| Training produced repetitive, low-diversity outputs | §5 — Entropy collapse; update diversity too low |

---

## The One-Line Version

Breadth comes from training across many *different* environments, at the
*right difficulty*, rewarding the *outcome* rather than the exact steps, on
tasks with *composable structure*. Narrowness comes from the opposites.

---

## §1 Environment Diversity

**Variety across environments is the strongest single lever for transfer.**

The quantitative law: a policy trained on 100 game levels left a 33-point
generalization gap; the gap did not close until ~10,000 distinct levels
(Cobbe et al. 2019, 2020). Holding data budget fixed and spreading it wider
wins: SWE-smith kept traces fixed at 700 and rose from 13.6% to 19% by
drawing from 100 repositories instead of 4 (Yang et al. 2025).
InternBootcamp scaled from 8 to 512 verifiable task types — the 8-task run
collapsed while the 512-task run stayed stable.

**Why**: with few environments, the model memorizes per-environment cues.
Only when the same skill must work across many superficially different
settings does the model find it cheaper to learn the underlying skill than to
memorize each case.

**Design rules:**
- Treat the number of distinct environments as a first-class budget item,
  separate from trace volume.
- Hundreds of instances = narrow regime. Tens of thousands = genuine invariance.
- A huge task space is useless without a good sampler — fix what the generator
  can produce before tuning the curriculum (XLand's adaptive picker was worth
  ~50-65% of final performance, but Kinetix showed random variation at massive
  scale reaches ~70-80% of curriculum-trained performance).

→ Read `references/environment-diversity.md` for the full scaling evidence.

---

## §2 Compositional Factor Coverage

**Every factor value must appear in training, and never locked to one partner.**

List the things that vary (tool, domain, interface, failure mode, horizon).
Ensure every value of each shows up, in *varied combinations*. Redhardt et al.
(2025) prove generalization requires:
1. **Compositional support** — every factor value appears somewhere
2. **Connected support** — no factor value appears *only* with one fixed partner

When these hold, models learn to combine factors they never saw combined. When
violated (gSCAN), models drop to near 0%.

**The tell**: models that generalize have individual factors linearly readable
from internal activations. Confounded ones do not.

**Design rules:**
- Aim for a crossed design (each tool exercised across many domains), not
  nested (tool locked to domain).
- The concern is factor *usage*, not availability. Sharing one tool interface
  across all environments is fine; having any tool useful in only one domain
  is the failure mode.

→ Read `references/compositional-coverage.md` for the formal conditions.

---

## §3 Difficulty Calibration

**Train on problems the model gets right sometimes — judged against the current model.**

The useful training problems are ones the current model solves ~30-70% of the
time. Problems always-right or always-wrong teach nothing (zero gradient with
pass/fail reward). Bae et al. (EACL 2026) showed filtering to 30-70% band
beat unfiltered by ~4 points, while one-sided filtering did *worse* than none.

**Critical**: difficulty must be judged against the *current* model, not a
fixed external rating (+3.8 vs +2.1 pts for adaptive vs fixed; Bae et al.).

**The depth-breadth tension** (DARS 2026): standard RL concentrating on medium
problems pushed pass@k *below* the base model (81.4 vs 82.1), while spending
on the hardest problems pushed it above (83.5). Optimizing pass@1 (medium
difficulty) and optimizing breadth (hard problems) are different goals.

**Reasoning behavior matters more than topic** (Shrestha et al. 2026): warmup
on long careful CoT from logic puzzles took MATH from 55.6 to 77.4; short CoT
from the same puzzles collapsed to 11%. Same domain, opposite result.

**Design rules:**
- Estimate each problem's success rate from the model's own rollouts. Refresh
  during training.
- Aim training at what the base model is currently bad at (0-30% success for
  genuine new capability; ProRL 2025).
- Choose tasks for the reasoning behavior they demand (decomposition,
  constraint tracking, verification), not topic proximity to the target eval.

→ Read `references/curriculum-calibration.md` for implementation patterns.

---

## §4 Reward Design for Generalization

**Reward the outcome, not the steps. Then verify the environment can't be cheated.**

Outcome rewards generalize because they leave the model free to find its own
method. SFT on the same trajectories copies surface form and degrades on
shifts (Chu et al. 2025: -6 to -80 pts). But "verifiable" ≠ "un-cheatable":
28.5% of SWE-bench tasks accept wrong patches (Rajan 2026).

**The only safe dense reward**: potential-based shaping F = γΦ(s') - Φ(s)
rewards improvement in "distance to goal" between steps and is provably
guaranteed not to change the optimal policy (Ng et al. 1999). Any other form
of step reward can introduce spurious optima.

**Reward hacking generalizes broadly**: reward hacking in code RL transferred
into sabotage and deception on unrelated tasks, and *how* it generalized
depended on how the training context was framed (Anthropic 2025). A training
environment's framing, not only its reward, affects what the model learns.

**Design rules:**
- Verify results rather than dictating reasoning steps.
- Audit each environment for exploits before training (generate deliberately
  wrong solutions, confirm verifier rejects them). Expect 25-33% cheatable.
- If adding step rewards, ensure they're potential-based or human-verified.
  Auto-generated step rewards degrade on new distributions.
- Rewarding "skill diversity" directly backfires — diversity-optimized skills
  transfer worse because they reward being distinguishable rather than useful
  (URLB 2021).

→ Read `references/reward-generalization.md` for the reward hacking taxonomy.

---

## §5 Preserving Breadth During Training

**Keep updates diverse enough to preserve answer variety.**

Performance rises as answer entropy falls — but entropy collapse is the
scaling bottleneck (Cui et al. 2025: R = -a·e^H + b, ceiling at H=0).
Larger, more diverse batches sustained higher variety at same accuracy and
added 1.9-3.7 points (DARS 2026).

**RL vs SFT forgetting**: RL forgets less because it's implicitly KL-minimal
— divergence from base is 0.019 (RL) vs 0.283 (SFT) on same task (RL's
Razor, Shenfeld et al. 2025). SFT-on-traces can undo breadth that in-
environment RL discovered, unless traces are diverse and full CoT is kept.

**Domain randomization**: randomize hidden environment settings (physics,
noise, seeds, latencies) and force the model to discover them. The more
widely varied, the better transfer — but at honest cost (~33× more training
experience in robotics). ADR's mechanism: expand randomization boundaries
when performance exceeds threshold, contract when it drops below.

**Design rules:**
- Track answer variety (entropy), not just accuracy. Rising accuracy + falling
  variety = narrowing.
- Mix many different problems into each update batch.
- For trace-based distillation (SFT-on-RL-traces): high trace diversity and
  full chain-of-thought are mandatory for preserving breadth.

---

## §6 Known Traps (What Makes Training Narrow)

| Trap | Mechanism | Evidence |
|---|---|---|
| Few environments | Memorizes per-environment cues | ProcGen: 100 levels = 33pt gap |
| Medium-difficulty only | Raises pass@1, lowers pass@k | DARS: pass@k dropped below base |
| Gameable rewards | Teaches the correlate, not the skill | Length alone reproduces most RLHF gain (Singhal 2023) |
| Rewarding skill diversity | Distinguishability ≠ usefulness | URLB: diversity-optimized skills transfer worse |
| Capacity saturation | Negative transfer across tasks | Meta-World: 88% on 10 tasks → 35% on 50 |
| Final-answer-only reward | Invites shallow shortcuts | Decorative CoT (R²=0.87 from surface features alone) |
| Training to convergence | Destroys exploration capacity | Yue et al. 2025; entropy collapse |
| Single model family | Latent behaviors give spurious gains | Qwen random-reward gain doesn't reproduce on Llama/OLMo |

---

## NOT For

- **Training mechanics** (algorithms, LoRA, hyperparameters) → `ml-post-training`
- **Evaluation system design** → `agent-evaluation`
- **Whether/when to train** → `agent-post-training`
- **Agent architecture** → `agent-architecture`

---

## References

| Reference | When to read |
|---|---|
| `references/environment-diversity.md` | Scaling laws for environment count, procedural generation, domain randomization, open-ended learning |
| `references/curriculum-calibration.md` | Difficulty band mechanics, adaptive curriculum implementation, UED methods |
| `references/compositional-coverage.md` | Factor coverage conditions, crossed vs nested design, composable environments |
| `references/reward-generalization.md` | Outcome vs process rewards, potential-based shaping, reward hacking taxonomy |
| `references/transfer-dynamics.md` | SFT-vs-RL generalization, entropy dynamics, forgetting, cross-domain transfer patterns |
