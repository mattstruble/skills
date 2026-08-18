*Synthesized from public RL generalization research — full paper list and provenance in [docs/sources/rl-generalization-literature.md](../../docs/sources/rl-generalization-literature.md).*

# Breadth Measurement

How to measure whether training produced broad, transferable capability or a
narrow skill. These techniques complement standard evaluation methodology —
they diagnose the *generalization quality* of a trained model, not just its
raw performance.

---

## The Core Principle

Do not take a training run's own score at face value. Every metric below exists
to answer: "Is this capability real and transferable, or a narrow artifact?"

---

## §1 Pass@k vs First-Try Accuracy

**What to measure**: both pass@1 (first-try) AND pass@k (can the model solve
this given k attempts).

**How to interpret**:

| Pattern | Meaning |
|---|---|
| Pass@1 ↑, Pass@k ↑ | Genuine improvement — model got better |
| Pass@1 ↑, Pass@k ↓ | **Narrowing** — model sharpened but lost diversity |
| Pass@1 ↑, Pass@k unchanged | Sharpened existing capability only |
| Pass@1 unchanged, Pass@k ↑ | Expanded solution space (rare but ideal) |

The critical failure mode is **pass@1 ↑ with pass@k ↓**. This means training
pushed the model toward fewer solutions that happen to work more often on first
try, but the model lost the ability to find solutions it previously could find
given enough attempts. The model got narrower, not better.

**Example** (DARS 2026): standard RL concentrated on medium difficulty — pass@1
improved but pass@k dropped below the base model (81.4 vs 82.1). The model
became a better first-try guesser at the cost of overall problem-solving range.

**Practical implementation**: always report pass@k alongside pass@1.
Recommended k values: 1, 8, 64, 128. If pass@k at large k drops after
training, the training narrowed the model.

---

## §2 Answer Variety (Entropy) Tracking

**What to measure**: the diversity of distinct solutions the model produces
across multiple attempts at the same problem.

**The entropy law** (Cui et al. 2025):
```
R = -a · e^H + b
```
Performance R and entropy H trade off predictably. The ceiling is at H=0.
You can forecast a training run's ceiling from its first few hundred steps
by tracking the entropy trajectory.

**How to interpret**:
- Rising accuracy + stable entropy = healthy learning
- Rising accuracy + falling entropy = approaching ceiling; narrowing
- Accuracy plateau + falling entropy = overfitting to narrow modes
- Entropy collapse (sharp drop to near zero) = training should stop or
  entropy intervention needed

**Practical implementation**:
```python
def answer_entropy(model, problem, n_samples=64):
    """Measure solution diversity for a single problem."""
    solutions = [model.generate(problem) for _ in range(n_samples)]
    # Normalize solutions (strip whitespace, canonicalize)
    canonical = [canonicalize(s) for s in solutions]
    # Count distinct solutions
    counts = Counter(canonical)
    probs = [c/n_samples for c in counts.values()]
    return -sum(p * log(p) for p in probs)
```

Track this metric at regular intervals during training. Plot alongside accuracy.

---

## §3 Held-Out vs Own-Eval Ratio

**What to measure**: the gap between performance on the training run's own
evaluation tasks and an independently written held-out benchmark of the same
skill.

**Example** (Endless Terminals 2026): the model scored ~10× higher on its own
generator's tasks than on a human-written benchmark of the same terminal skill.
The own-eval was inflated by distributional overlap with training.

**How to interpret**:
| Ratio (own / held-out) | Meaning |
|---|---|
| 1.0 - 2.0× | Genuine generalization |
| 2.0 - 5.0× | Moderate distributional overfitting |
| 5.0 - 10×+ | Severe overfitting; capability is narrow |

**Design rule**: every training run should be graded on an **independently
authored** held-out test, not the training system's own eval. Report the ratio
explicitly. The held-out test must differ in surface features (different
problems, different phrasing, different tools) while testing the same
underlying skill.

---

## §4 Cross-Task Interference Measurement

**What to measure**: the effect on OTHER capabilities when you train on a new
domain.

**Quantitative baselines** from the literature:
- Meta-World (Yu et al. 2019): multi-task agent at ~88% on 10 tasks → ~35-38%
  on 50 tasks (same model, negative transfer from capacity saturation)
- Huan et al. (2025): math-only RL training dropped code performance by
  22-38 points
- Li et al. (2025): cross-domain effects flip sign between base and
  instruction-tuned models under identical RL

**Implementation**: maintain a suite of canonical benchmarks across domains.
After every training run, measure ALL domains — not just the target. Report:
1. Target domain improvement
2. Every other domain's score change
3. Net effect (sum of all changes)

A training run that gains +10 on math but loses -15 on code is a net negative,
even if math was the target.

---

## §5 Fake-Reward Sanity Check

**What to test**: whether the observed training gain is from genuine learning
or from model-specific artifacts.

**The null hypothesis** (Shao et al. 2025): on Qwen2.5-Math-7B, a completely
random reward captured 21.4 of 29.1pp gain (73%) from GRPO training on
MATH-500. The gain came from GRPO's clipping bias amplifying pre-existing
high-prior behaviors, not from the reward signal.

But: the same random rewards produced zero gain on Llama3 and OLMo2.

**Protocol**:
1. Run the full training with correct rewards → measure gain
2. Run identical training with random rewards → measure gain
3. Run with a single training example (1-shot) → measure gain
4. If random or 1-shot captures most of the gain on your model family,
   the "training" is just activating latent capability

**When to deploy this check**:
- Whenever reporting a new training method's results
- When gains seem "too good" relative to training effort
- Before attributing improvement to environment design vs model artifacts

**Design rule**: validate training results on at least **two model families**.
Single-family results are provisional. Qwen-specific RLVR evidence is
particularly suspect for this artifact.

---

## §6 Multi-Family Validation Requirement

Much 2025 RLVR evidence is on one model family (Qwen) with unusual latent
behaviors. Treatment: any training result validated on only one family should
be marked provisional.

**Minimum standard**: test on ≥2 base model families (e.g., Qwen + Llama, or
Qwen + OLMo). If the effect doesn't reproduce, the finding is model-specific
and cannot be relied upon for general training design decisions.

---

## Integration with Existing Eval Methodology

These breadth metrics complement (not replace) the existing agent-evaluation
framework:

| Existing Metric | Breadth Complement |
|---|---|
| Pass@1 accuracy | Add Pass@k at multiple k values |
| Task success rate | Add answer variety/entropy |
| In-distribution performance | Add held-out ratio |
| Target task improvement | Add cross-task interference |
| Single model eval | Add multi-family validation |
| Standard benchmark score | Add fake-reward sanity check |

The reframing: evaluation is not just "how good is the model?" but "how
*broadly* capable is it, and are we confident the scores reflect real
capability?"
