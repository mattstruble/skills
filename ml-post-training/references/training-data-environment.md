# Training Data and Environment

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## The Priority Order

The industry's most counterintuitive and most valuable lesson: **data and environment matter more than algorithms**.

Off-the-shelf RL algorithms (PPO, GRPO) are fine. What separates successful teams from unsuccessful ones is:
1. **Base model quality**: the ceiling of post-training is set by the base model's pre-training
2. **Environment fidelity**: does the simulation environment truly resemble the real deployment scenario?
3. **Data quality**: are the demonstrations and reward signals good enough?

Algorithms come last. Differences between PPO and GRPO only show up when everything else is already good. Chasing algorithm improvements before the environment and data are ready is the classic cart-before-horse mistake.

---

## Simulation Environment Requirements

RL cannot train against real APIs. Rate limits, account bans, side effects, and irreversibility make direct training infeasible. You must build a stable, controllable, replayable shadow environment first.

### Reset Semantics

The environment must support clean resets between episodes — this is a qualitative requirement the source describes as making the environment "stable, controllable, replayable." Without replayability:
- State bleeds across trajectories (the model's action in episode N affects episode N+1)
- The reward signal becomes meaningless (the model is being rewarded/penalized for state it did not create)
- Training diverges or produces nonsensical policies

For stateful environments (databases, file systems, UI state): implement snapshot/restore or use ephemeral containers per episode.

### Throughput and Parallelism

On-policy training requires generating many rollouts per gradient step. The environment must support parallel execution — the source experiments illustrate the scale required: ReTool used 128 parallel Python sandbox workers; AWorld-train achieved a 14.6× speedup from distributed rollout architecture (reducing a 7-day run to 12 hours). These are examples from specific experiments, not universal targets — the right parallelism depends on your environment's overhead and your compute budget.

The key principle: if your environment can only run one rollout at a time, on-policy training will be prohibitively slow. Design for parallelism from the start.

- **Real-time execution feedback**: the sandbox must return results fast enough that the model can continue generating within the same context window

### Fidelity

The environment must resemble the real deployment scenario. Training on a simplified environment that differs from production is a form of distribution shift — the model learns a policy that works in the simulation but fails in production.

Fidelity checklist:
- Same tool interfaces (same API signatures, same error formats)
- Same failure modes (timeouts, malformed inputs, partial results)
- Same context window constraints
- Representative task distribution (sample from actual deployment queries, not synthetic ones)

### Reward Computability

The environment must be able to determine success/failure (or partial progress) deterministically for most trajectories. If the reward function returns NaN or errors on more than ~20% of trajectories, training will be unstable.

Pre-training diagnostic: run 50–100 rollouts from the base model and measure:
- What fraction produce parseable output? (< 10% failure = SFT phase complete)
- What fraction produce non-zero reward? (< 5% success = reward too sparse, need milestone rewards)
- What is within-group variance for GRPO? (= 0 → all-fail or all-pass problem)

---

## Data Quality Practices

### The Iron Rule

**Data quality trumps algorithms.** Feed the most sophisticated algorithm dirty data, patchy data, or systematically biased data, and the policy it learns will be dirty too.

- SFT bakes noise and bias into parameters verbatim
- RL optimizes relentlessly toward a biased reward, pushing further and further in the wrong direction

Garbage in, garbage out is on full display in post-training.

### SFT Data Quality

For SFT demonstrations:
- **Filter incorrect responses**: use a rule-based validator or a strong model to check correctness before including in the training set. Imitating erroneous reasoning is worse than having no data.
- **Consistent format**: every sample must use the same chat template and output structure
- **Representative coverage**: sample from the actual deployment distribution; gaps in coverage become gaps in capability
- **No factual knowledge injection**: SFT is poor at memorizing facts; use RAG for facts

### RL Task Distribution

For RL training prompts:
- **Difficulty calibration**: prompts where the model already achieves 100% success rate contribute no gradient (all-pass groups). Prompts where the model achieves 0% success rate also contribute no gradient (all-fail groups). The most informative prompts are in the 20–80% success rate range.
- **Dynamic sampling**: measure per-prompt success rate during training and concentrate compute on the informative range. Discard or reduce sampling for prompts outside this range.
- **Distribution match**: the training task distribution should match the deployment distribution. Systematic differences produce policies that work in training but fail in production.

### Reward Signal Quality

A biased reward function is worse than no reward function — RL will optimize relentlessly toward the bias. Common reward quality failures:
- **Reward hacking surface**: the reward can be gamed without actually doing the task (e.g., a reward for "answer length" incentivizes verbosity, not quality)
- **Annotation perspective mismatch**: labels annotated from a "God's eye view" (with information not available at decision time) produce a model that assumes information it cannot have
- **Inconsistent labeling**: the same behavior gets different rewards depending on the annotator

---

## Reward Signal Density Engineering

### The Density Spectrum

```
Binary (0/1) → Milestone → Process (per-step) → Vector → Generative
←— easier to implement ——————————————————— richer signal —→
←— less annotation cost ——————————————————— higher cost —→
```

### Binary Rewards

For tasks with clear correct answers (math, SQL, unit tests), binary rewards are the simplest and most reliable. The answer is either right or wrong. No complex design needed.

**When binary rewards fail**: tasks with long horizons where the model never reaches success by random exploration. If the base model achieves 0% success rate on a task, binary rewards provide no learning signal — the model never sees a positive example.

### Milestone Rewards

Add partial credit at verifiable intermediate checkpoints. Example (customer service task):
- Identity verification completed: +0.1
- Correct information retrieved: +0.3
- Plan change executed: +0.4
- User confirmation received: +0.2

Milestone rewards reduce credit assignment difficulty and provide signal even when the full task is not completed. The risk: over-constraining exploration (the model learns to hit milestones, not to solve the task).

**Calibration guidance**: milestone weights should be small relative to the final outcome reward — milestones should sum to ≤30% of total possible reward. If the model consistently hits milestones but fails task completion, reduce milestone weights or gate them: award milestone credit only when the final outcome is also achieved. This prevents the model from optimizing for partial credit at the expense of the actual goal.

### Process Rewards (PRM)

Process Reward Models score each intermediate reasoning step. Representative work: OpenAI's "Let's Verify Step by Step" showed that PRMs trained with step-by-step human annotations significantly outperformed outcome-only supervision on mathematical reasoning.

Implementation cost is high (requires step-level annotation). Use when:
- The task has a well-defined reasoning structure
- Binary rewards are too sparse to learn from
- You have annotators who can evaluate intermediate steps

### Vector Rewards

When the task has multiple independent quality dimensions, use a vector of scalar rewards rather than a single score. Example (customer service):
- Information accuracy: 9/10
- Information completeness: 6/10
- Communication fluency: 8/10
- Communication accuracy: 7/10

Vector rewards enable dimension-wise diagnosis and targeted improvement.

### Generative Rewards

A language model judge that produces a natural-language evaluation with reasoning. More transparent than scalar scores; naturally extends to open-ended tasks that are difficult to cover with rules.

Training generative reward models (DeepSeek's approach):
1. The model automatically generates evaluation principles for the specific task
2. The model evaluates cases against those principles, producing scored examples
3. The model is fine-tuned on these self-generated evaluations

The core value: transforms rich environmental feedback into learnable knowledge. The model can learn improvement directions from a single failure, rather than requiring hundreds of blind trial-and-error attempts.

---

## Multi-Turn Credit Assignment

### The Core Challenge

In multi-turn interactions, the final reward must be attributed to specific steps in the trajectory. A customer service agent that solves a problem after 10 turns receives a positive review — but which turn earned it?

### PPO Credit Assignment (GAE)

PPO uses Generalized Advantage Estimation with a value network. The value network estimates "how much better this step is than expected" for each step in the trajectory, making a weighted trade-off between bias and variance.

For multi-turn LLM tasks, the discount factor γ is typically set to 1.0 — tasks only last a few to dozens of turns, and the optimization goal is ultimate success or failure. No need to discount earlier rewards.

### GRPO Credit Assignment

GRPO treats the entire response as a single action. Advantage is within-group variance across N rollouts of the same prompt. This is coarse credit assignment — all tokens in the response receive the same advantage signal.

For long trajectories, this coarseness is a real limitation. PPO's per-step advantage is more appropriate for multi-turn tasks.

### RLVP: Reward Outcome, Penalize Path

RLVP (Reinforcement Learning with Verified Penalty) addresses a class of constraints that outcome rewards cannot express: process constraints whose observance has no necessary connection to task success.

Examples of outcome-neutral constraints:
- Don't call back a user who has explicitly declined
- Don't skip identity verification
- Don't run destructive commands (`rm -rf`)
- Don't edit test files to make tests pass
- Don't overwrite a file you never read

Pure outcome rewards actively incentivize violating these constraints — cutting corners often raises the apparent success rate.

**Core insight**: bad actions are cheap to verify deterministically. A verified penalty for bad actions:
1. Restores gradient signal in all-fail GRPO groups (even when all rollouts fail, they differ in *how* they fail — some run destructive commands, others don't; the penalty creates within-group variance)
2. Teaches process compliance without requiring the model to discover it through random exploration

**Partial credit (progress rewards)**: the same `+μ` mechanism can reward reachable progress. Diagnose reachability before committing to dense rewards: measure within-group variance on a handful of base-model rollouts. If variance is zero (all rollouts fail at the same step), progress is unreachable and dense rewards will not help.

RLVP recipe:
1. Use a few scripted demonstrations to show the model compliant paths (otherwise it may never explore them)
2. Implement penalty checks as deterministic code, not a learned compliance scorer (otherwise the model games the judge)
3. Combine with outcome rewards: `r = r_outcome + μ·(compliant) - μ·(violation)`

**Setting μ**: set the penalty magnitude so it is comparable to the expected outcome reward. A practical starting point: `μ ≈ 0.5 × r_outcome_max`. Monitor the penalty trigger fraction during early training — if it is near zero, the model may be avoiding penalized actions entirely (good) or avoiding the task altogether (bad). Distinguish by checking whether task-relevant actions are also being attempted.

---

## On-Policy Distillation

On-policy distillation combines the dense supervision of SFT with the online advantage of RL. A teacher model scores the student's own trajectories at each token position, providing a full probability distribution rather than a binary success/failure signal.

**Why it works**: the teacher doesn't just judge whether the student's step is correct — it provides the complete probability distribution for the next token at the current position. The student minimizes KL divergence between its distribution and the teacher's at every step. This is denser by more than an order of magnitude compared to binary outcome rewards.

**Results**: on mathematical reasoning tasks, on-policy distillation matches pure RL performance with roughly 1/10 the training steps. The advantage is most pronounced in long-chain reasoning.

**Why it beats standard SFT**: standard SFT trains on a fixed dataset (off-policy). On-policy distillation trains on the student's own trajectories — the teacher evaluates wherever the student actually goes, not where a human demonstrator went. This eliminates covariate shift and allows data to be reused far more heavily without overfitting.

**Multi-turn advantage**: in multi-turn agent scenarios, binary outcome rewards are extremely sparse (success/failure only at the end of a long trajectory). On-policy distillation provides dense per-token signal at every step, making it particularly valuable for long-horizon tasks.

Implementation requirements:
- Teacher model must be accessible at training time (not just inference time)
- Teacher must be able to evaluate the student's partial trajectories (not just complete ones)
- KL divergence computation between teacher and student distributions at each token position
