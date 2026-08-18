*Synthesized from public RL generalization research — full paper list and provenance in [docs/sources/rl-generalization-literature.md](../../docs/sources/rl-generalization-literature.md).*

# Curriculum Calibration

How to set and maintain the difficulty of training problems for maximum
learning signal and generalization.

---

## The Optimal Difficulty Band

RL with pass/fail rewards produces zero gradient when all attempts agree
(all-pass or all-fail). Maximum signal is at 50% success rate. The practical
band is **30-70%** — filtering to this range beat unfiltered training by ~4
points (Bae et al. EACL 2026).

**Critical caveat**: one-sided filtering (dropping only easy OR only hard) did
*worse* than no filtering at all. Both endpoints of the distribution contain
information; removing either biases the gradient.

---

## Adaptive vs Fixed Difficulty

Difficulty must be judged against the **current model as it trains**, not a
fixed external rating:
- Adaptive difficulty: +3.8 pts over unfiltered (Bae et al. 2026)
- Fixed external rating: +2.1 pts over unfiltered

The model's competence shifts during training — problems that were at 30%
success early may reach 90% partway through. An author's difficulty label is a
starting guess, not a curriculum.

**Implementation pattern**: estimate per-problem success rate from the model's
own rollouts, refresh every N gradient steps, concentrate compute on problems
in the 30-70% band.

---

## The Depth-Breadth Tension

Optimizing for first-try accuracy (pass@1) and optimizing for breadth (pass@k,
diverse problem solving) are **different goals** (DARS 2026):

| Strategy | Pass@1 | Pass@k | Breadth |
|---|---|---|---|
| Standard RL (medium difficulty) | ↑ | ↓ below base (81.4 vs 82.1) | Narrowing |
| DARS (spend on hardest) | ↑ | ↑ above base (83.5) | Expanding |
| Large diverse batches | +1.9-3.7 | Maintained | Preserved |

**Takeaway**: state which goal a training run is optimizing. Medium-difficulty
sharpens; hard-difficulty expands. DARS-Breadth shows they're complementary
when combined (adaptive rollouts for depth + large batches for breadth).

---

## Self-Evolving Curriculum (SEC)

Formulates curriculum selection as a non-stationary Multi-Armed Bandit:
- Each problem category = one arm
- Reward signal = absolute advantage from policy gradient (proxy for learning gain)
- Updated via TD(0)
- Result: +13-33% relative OOD improvement; roughly flat in-distribution

Key finding: adaptive curriculum helps out-of-distribution far more than
in-distribution. If your goal is generalization, curriculum matters most.

---

## Warm-Up: Behavior Over Topic

What transfers is the *shape* of reasoning, not the subject matter (Shrestha
et al. 2026):

| Warm-up | Then RLVR on math | MATH score |
|---|---|---|
| Long CoT from logic puzzles | ≤100 examples | 77.4 |
| Short CoT from same logic puzzles | ≤100 examples | 11.0 |
| No warm-up | ≤100 examples | 55.6 |

Same domain, same difficulty, opposite result — driven entirely by reasoning
trace quality. The long CoT instilled careful multi-step decomposition behavior
that transferred cross-domain.

**Design rule**: choose training tasks for the control structure they force
(multi-step decomposition, interacting constraints, opportunities to verify),
not for topic proximity to the target evaluation.

---

## UED Methods (Ranked by Practicality)

| Method | Mechanism | Strength | Limitation |
|---|---|---|---|
| Random sampling at scale | Generate randomly, train on all | Strong baseline; ~70-80% of curriculum perf | Wastes compute on trivial/impossible |
| PLR (Prioritized Level Replay) | Score by learning potential, replay high | Simple; ~70% vs 55% uniform on ProcGen | Requires stored level buffer |
| Robust PLR | PLR + regret-gated generator | 3-50× more efficient than PAIRED | More complex; needs generator |
| ACCEL | Mutate existing high-regret levels | Finds complex structures others miss | Needs mutation operators |
| SFL / "No Regrets" | Select for "solved sometimes but not always" | Beats regret-based on hard tail | Standard regret approximations unreliable |
| DIPLR | Diversity-only selection | Recovers most regret benefit | May miss specific hard problems |

**Practical recommendation**: Start with random generation at maximum scale.
Layer PLR-style replay only when random is demonstrably insufficient. The
difference between fancy curriculum and massive random is often smaller than
expected (minimax 2023; Kinetix 2025).

---

## Aiming at the Base Model's Weak Spots

RL adds genuinely new capability where the base model is weak, and mostly
sharpens where it's strong (ProRL, Liu et al. 2025):
- Tasks at 0-30% base success: room for genuine new capability
- Tasks at 70%+ base success: mostly re-weighting existing behavior

GURU (2025) confirms: domains thin in pretraining (logic, tables, simulation)
need their own dedicated training and transfer most broadly. Saturated domains
(math, code) mostly get sharpened.

**Design rule**: report each training run's base-model success-rate
distribution and put the training mass where the base sits around 0-30%.
