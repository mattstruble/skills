# RL Training

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## Why RL Has a Higher Ceiling Than SFT

Three structural advantages of on-policy RL over SFT:

1. **The ceiling is the task, not the data.** SFT's ceiling is the quality of the demonstrations — it can at most approach, and almost never surpass, the level of the annotator. RL optimizes against outcome rewards: any behavior that yields higher reward is reinforced, even if no one has ever demonstrated it. The model can independently discover strategies that do not exist in the training data.

2. **Verifying is easier than generating.** SFT requires someone to write the correct answer first. RL only needs a way to judge whether an answer is good. In many tasks, judging is far easier than producing — math answers can be checked against a key, code can be run through tests. This verification-generation asymmetry is the source of RLVR's power.

3. **Online training eliminates covariate shift.** SFT trains on a fixed dataset describing someone else's behavior. As the model improves, that data becomes increasingly irrelevant. RL trains on the model's own trajectories — the training distribution matches the deployment distribution, and feedback targets the model's current actual weaknesses.

---

## RLHF Pipeline

RLHF (Reinforcement Learning from Human Feedback) trains a reward model from human preferences, then uses that reward model to drive PPO training.

### Step 1: Collect Preference Data

Present human annotators with pairs of model responses to the same prompt and ask which is better. Pairwise comparisons ("A or B?") are far more reliable than absolute ratings ("score this 1–10"). Collect thousands to tens of thousands of preference pairs.

### Step 2: Train the Reward Model

The reward model is trained using the Bradley-Terry model, which converts pairwise preferences into a scalar score. Given a preferred response `y_w` and a rejected response `y_l` for the same prompt `x`:

```
Loss = -log(σ(r(x, y_w) - r(x, y_l)))
```

The reward model learns to assign higher scores to preferred responses. It is typically initialized from the SFT model (same architecture, different head).

### Step 3: PPO Training with KL Penalty

Use the reward model's score as the reward signal for PPO, with a KL penalty to prevent the policy from drifting too far from the SFT starting point:

```
r_effective = r_RM(x, y) - β · KL(π_θ(y|x) ‖ π_ref(y|x))
```

`β` (the `kl_coef` hyperparameter) controls the penalty strength. The KL is computed per-token across the response.

---

## KL Divergence: Design and Failure Modes

### What KL Divergence Measures

KL divergence measures the difference between two probability distributions. Here, it compares the current policy's next-token distribution to the reference policy's (the SFT model's) distribution at each position in the response. KL = 0 when the distributions are identical; KL grows as they diverge.

### Forward vs Reverse KL

**Mass-covering (forward KL, used by SFT/MLE)**: tries to cover all modes in the demonstration distribution, assigning probability even to lower-quality modes. The model spreads probability mass across all reasonable answer styles.

**Mode-seeking (reverse KL, used by RL with KL constraints)**: concentrates probability on the few highest-reward modes, decisively discarding lower-quality alternatives. This is why RL-trained models are more "decisive" and focused — and why they sacrifice output diversity.

This distinction matters for reward design: if you need diverse outputs (creative tasks), be cautious about strong KL constraints. If you need focused, high-quality outputs (tool calling, structured reasoning), mode-seeking is desirable.

### Why KL Penalty is Mandatory

Without KL regularization:
- The reward model's scores become unreliable extrapolation once the policy drifts outside the distribution the RM was trained on
- The model learns to game the reward proxy (reward hacking): verbose, ingratiating, rigorous-sounding empty responses that score well but solve nothing
- Outputs can degenerate into repetition or gibberish (distribution collapse)

Even in RLVR training with verifiable rewards (where reward hacking is less of a concern), KL regularization stabilizes training. Some recent work (DAPO, Open-Reasoner-Zero) intentionally removes it — this is an active research area, not a general recommendation.

### Reward Model Over-Optimization

Goodhart's Law applies directly: when the RM score becomes the optimization target, it ceases to be a good metric. As RL training progresses, proxy reward (RM score) climbs monotonically while true quality (human evaluation) first rises and then falls. Mitigations:
- KL penalty (primary)
- Early stopping based on held-out human evaluation
- Periodic reward model refresh

---

## Algorithm Mechanics

### Policy Gradient Foundation

All modern RL algorithms for LLMs build on policy gradient. The core update rule:

```
∇J(θ) = E[∇log π_θ(a|s) · G]
```

where `G` is the cumulative return for the trajectory. Actions with higher returns get their probability increased; actions with lower returns get decreased. A baseline `b` is subtracted to reduce variance: `A = G - b` (advantage).

### PPO Mechanics

PPO limits the update magnitude per step using a clipping objective:

```
L(θ) = E[min(ρ·Â, clip(ρ, 1-ε, 1+ε)·Â)]
ρ = π_θ(a|s) / π_θ_old(a|s)
```

`ε` (typically 0.2) limits how much the policy can change in a single update. The value network estimates per-step advantage using GAE (Generalized Advantage Estimation), making credit assignment finer-grained.

**Clip-Higher variant**: relaxes the upper bound `1+ε` to allow larger upward updates for high-advantage actions, while keeping the lower bound tight. Useful when the model needs to make large improvements on high-reward trajectories.

### GRPO Mechanics

GRPO eliminates the value network. For each prompt, sample N trajectories and compute advantage as within-group relative rank:

```
Â_i = (r_i - mean(r_1,...,r_N)) / std(r_1,...,r_N)
```

"Positive if better than group average, negative if worse." No value network needed — cheaper to run.

**Critical limitation**: if all N trajectories in a group receive the same reward (all-pass or all-fail), the standard deviation is zero, every advantage is zero, and the group contributes no gradient. This "zero-variance deadlock" is common at the beginning of training (all-fail) and end of training (all-pass). Mitigations: dynamic sampling (discard zero-variance groups), or RLVP (add verified penalties to restore variance).

### DPO Mechanics

DPO bypasses the explicit reward model entirely. It directly optimizes a classification loss on preference pairs:

```
L_DPO(θ) = -E[log σ(β · (log π_θ(y_w|x)/π_ref(y_w|x) - log π_θ(y_l|x)/π_ref(y_l|x)))]
```

The implicit reward is the log-ratio between the policy and the reference model. No online sampling, no reward model training, no PPO loop. Extremely simple to implement.

**Hard constraint**: DPO cannot explore new policies. It is bounded by the quality and coverage of the offline preference dataset. If the dataset does not contain examples of the behavior you want, DPO cannot learn it.

---

## Algorithm Selection Guide

| Scenario | Recommended Algorithm | Rationale |
|---|---|---|
| Single-turn, verifiable reward (math, code), budget-constrained | GRPO | No value network; simple; works well when rewards are discriminative |
| Multi-turn agent, long trajectories, fine credit assignment needed | PPO | Value network provides per-step advantage; more stable for long horizons |
| High-quality preference pairs already exist | DPO | No online sampling; extremely low implementation cost |
| Very limited annotation budget | KTO | Binary good/bad labels only |
| Early exploration, no training budget | Best-of-N | No training; quick upper-bound estimate |
| Need to embed capabilities in weights (not just inference-time) | GRPO or PPO | Best-of-N does not update weights |

---

## Training Stability Practices

### Hyperparameter Starting Points

The LoRA learning rate rule (~10× full fine-tuning LR) is sourced from the book (§7.1). The remaining ranges below are practitioner defaults, not from the source text — treat them as starting points to tune against your specific task and reward scale.

| Hyperparameter | Practitioner Default | Notes |
|---|---|---|
| `kl_coef` (β) | 0.01–0.1 | For normalized reward model scores. For binary/verifiable rewards (RLVR), reward magnitude is larger — start at the higher end (0.05–0.1) and monitor KL divergence directly. Increase if reward hacking appears. |
| Learning rate | Lower than SFT | RL updates are noisier; LoRA LR rule (~10× full fine-tuning LR) still applies as the base |
| Batch size | Larger = more stable | More prompts per step → more stable gradient estimates |
| Rollouts per prompt | 4–16 (GRPO) | More = better advantage estimate; higher cost |
| Clip ε | 0.2 | Standard; reduce to 0.1 for conservative updates |
| γ (discount) | 1.0 | For multi-turn LLM tasks (short horizons, no need to discount) |

### Common Failure Modes

**Training loss diverges early**: learning rate too high, or format not stable (SFT phase incomplete). Check parse failure rate first.

**Reward climbs but eval quality falls**: reward hacking. Increase `kl_coef`; add early stopping on human eval.

**Training oscillates without converging**: reward too sparse; environment reset semantics broken; or all-fail/all-pass groups dominating (GRPO). Add milestone rewards or switch to PPO.

**Model becomes repetitive**: KL penalty too low. Increase `kl_coef` or verify the reference model is frozen.

**GRPO produces no gradient after initial progress**: all-pass groups dominating (model has learned the easy cases). Use dynamic sampling to filter; or add harder prompts to the training distribution.

---

## Safety Alignment and Fine-Tuning

Fine-tuning is the primary vector for removing safety alignment. Safety behaviors are a learned capability — SFT and RL can overwrite them just as readily as they write other behaviors.

**KL reference policy**: when fine-tuning a safety-aligned model, the KL reference policy (`π_ref`) must be the safety-aligned SFT checkpoint, not the raw pre-trained base. Using the raw base as the reference allows the policy to drift away from safety-aligned behavior without penalty.

**Reward function omissions**: reward functions that do not include safety constraints cause RL to optimize them away. If the reward only measures task success, the model will learn to succeed by any means — including unsafe ones. Add safety violations as RLVP penalties (deterministic checks, not a learned compliance scorer) to make safety constraints part of the training signal.

**Monitoring**: track safety benchmark scores alongside task performance throughout RL training. A model that improves on task metrics while degrading on safety benchmarks is exhibiting safety erosion — stop training and revise the reward function.
