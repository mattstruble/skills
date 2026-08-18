*Synthesized from public RL generalization research — full paper list and provenance in [docs/sources/rl-generalization-literature.md](../../docs/sources/rl-generalization-literature.md).*

# Transfer Dynamics

How RL and SFT differ in their generalization properties, and the conditions
under which RL genuinely expands vs merely sharpens capability.

---

## SFT Memorizes, RL Generalizes

The clearest single finding (Chu et al. ICML 2025): trained on the same tasks,
tested on shifted versions (different rules, different visuals):
- **RL on outcomes**: generalized (+3 to +61 points on shifted tasks)
- **SFT on same trajectories**: degraded (-6 to -80 points on shifted tasks)

SFT copies the surface form of traces. RL discovers the underlying strategy.

---

## RL's Razor: Why RL Forgets Less (Shenfeld et al. 2025)

On-policy RL is implicitly biased toward **KL-minimal solutions** — among all
policies that solve the new task, RL converges to the one closest to the base
model. Measured divergence:
- RL: KL = 0.019 from base
- SFT: KL = 0.283 from base (on instruction benchmark)

This explains why RL preserves prior capabilities: it makes the smallest
change necessary. SFT can converge to distributions arbitrarily far from base.

**Mechanism** (Mukherjee et al. NeurIPS 2025): RL modifies only small
subnetworks within the model. The rest stays intact. SFT updates broadly.

---

## Does RL Teach New Abilities or Surface Existing Ones?

Two camps with evidence for each:

### "RL mostly sharpens" (Yue et al. NeurIPS 2025 Oral)
- RLVR improves pass@1 but base model achieves higher pass@k at large k
- Coverage analysis shows abilities bounded by base model's initial distribution
- Six popular RLVR algorithms all perform similarly and remain far from base
  model's potential

### "RL can genuinely expand" (ProRL, NVIDIA 2025)
- Prolonged RL with KL control + reference resetting solves tasks base model
  cannot at ANY k (including k=128)
- Reasoning boundary expansion correlates with (a) base model weakness on task
  and (b) training duration
- Requires: diverse task suite + KL divergence control + reference policy resets

### Reconciliation
Both are true under different conditions:
- **Short, single-domain RL**: mostly sharpens (and can shrink pass@k)
- **Long, multi-domain RL with diversity protected**: adds genuinely new ability
- Practical rule: a training run is most valuable where the current model is
  near zero success rate

---

## The Entropy-Performance Law (Cui et al. 2025)

Performance trades from policy entropy:

```
R = -a · e^H + b
```

Where H is answer-level entropy. As training progresses:
- Entropy drops (fewer distinct answers explored)
- Performance rises (sharper on known solutions)
- Ceiling is fully predictable: at H=0, R = -a + b

**The invisible leash** (Wu et al. 2025): RLVR improves precision but
progressively narrows exploration. Token-level entropy may rise (more
uncertainty per step) while answer-level entropy falls (fewer distinct final
answers). This means seemingly more uncertain reasoning converges onto a
smaller set of solutions.

**Practical consequence**: entropy collapse is the fundamental scaling
bottleneck for RL. Rising accuracy + falling answer variety = approaching
the ceiling. Must manage entropy to continue improving.

---

## Cross-Domain Transfer Patterns (GURU 2025)

Training on 92K verifiable examples across 6 reasoning domains reveals:
- **Saturated domains** (math, code, science): easily benefit from cross-domain
  RL training. Pretraining already laid the groundwork.
- **Thin domains** (logic, simulation, tabular): require in-domain training.
  RL facilitates genuine skill acquisition here, not just sharpening.

**Implication**: the domains that are most novel to the base model are where RL
produces the most genuine transfer — and they need dedicated training, not
just cross-domain spillover.

---

## Multi-Domain Interference

Training on multiple domains simultaneously produces both synergies and
conflicts (Li et al. 2025):
- Math, code, and logic can enhance each other
- But single-domain training can actively hurt others: math-only training
  dropped code by 22-38 points (Huan et al. 2025)
- Effects flip sign between base and instruction-tuned models under same RL

**Design rule**: always measure every *other* domain's metrics when training on
a new domain. Cross-effects are large and can be negative.

---

## The Spurious Reward Null Hypothesis

On Qwen2.5-Math-7B, a *random* reward captured 21.4 of 29.1pp gain (73%) on
MATH-500 (Shao et al. 2025). Mechanism: GRPO's clipping bias amplifies
high-prior behaviors (like "code reasoning") regardless of reward signal.

But: same random rewards produce zero gain on Llama3 and OLMo2.

**Design rule**: if a training run's gain survives a random or one-example
reward, you measured the model showing off what it already knew — not new
capability. Test on ≥2 model families.

---

## SFT-on-Traces: Recovering Breadth from RL

When the global training pipeline uses SFT-on-RL-traces (distillation), the
SFT-memorizes problem applies. Breadth discovered by in-environment RL can be
partly undone by distillation.

**Mitigations:**
- High trace diversity (many distinct solutions to same problem)
- Keep full chain-of-thought (not just final answers)
- On-policy distillation (OPD) forgets less than standard SFT (moves 0.019 KL
  vs 0.283 KL)
- The 1-shot RLVR phenomenon (Wang et al. 2025) — even a single example can
  unlock substantial capability — suggests the base model has latent capacity
  that minimal RL intervention can activate
