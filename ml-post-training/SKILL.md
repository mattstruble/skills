---
name: ml-post-training
description: You MUST consult this skill when implementing SFT data pipelines, running RL training (PPO/GRPO/DPO), designing reward functions, configuring LoRA, building simulation/training environments, or debugging training instability. Also trigger when choosing between on-policy vs off-policy algorithms, engineering multi-turn credit assignment, or building tool-calling RL pipelines. NOT for deciding whether/when to fine-tune (→ agent-post-training), pre-training from scratch, model serving/inference, or eval-system design (→ agent-evaluation).
---

# ML Post-Training

**The algorithm is rarely the bottleneck. The data and environment almost always are.**

This skill covers the mechanics of SFT and RL post-training: how to implement each stage, which algorithm to pick, how to design reward functions, and how to debug when things go wrong.

---

## Symptom Table

| Symptom | Decision Point |
|---|---|
| RL fails immediately (NaN reward, zero gradients) | §1 — SFT not complete; format not stable |
| Reward climbs but human eval quality falls | §2 — reward hacking; KL penalty too low |
| GRPO produces no gradient | §2 + §3 — zero-variance deadlock (all-pass or all-fail groups) |
| Model collapses to repetitive output | §2 — KL penalty absent or too low |
| SFT performance degrades on OOD inputs | §1 → §2 — SFT memorized; switch to RL for generalization |
| RL training oscillates without converging | §3 — reward too sparse; broken environment reset semantics |
| Post-training eroded safety behaviors | §2 — KL ref is wrong checkpoint; reward omits safety constraints |

---

## The Three-Stage Pipeline

Post-training always follows the same order: **SFT → RL**. The order is not arbitrary.

SFT must come before RL because RL needs parseable output to compute rewards. If the model produces malformed JSON or unstructured text, the reward function returns NaN, gradients go to zero, and training fails completely. SFT's job in the pipeline is not to maximize task performance — it is to stabilize output format so RL has a starting point.

| Stage | Goal | Signal | Cost |
|---|---|---|---|
| SFT | Stabilize format, solidify protocols | Token-level loss on responses only | Low (hours–days) |
| RL | Generalize strategy, break through SFT ceiling | Reward per trajectory | High (10–100× SFT) |

**Stopping condition for SFT**: format is stable and basic capability is present. Overtraining SFT collapses the model onto the training distribution, limiting RL's optimization space. For structured-output tasks (JSON, tool calls): stop when parse failure rate drops below ~5–10%. For free-form tasks (CoT, dialogue): use format-agnostic proxies — response length distribution stability, instruction-following rate on a held-out set.

**Exception — strong base models**: the SFT-first rule holds for smaller models with strictly structured output requirements. A sufficiently strong base model may produce adequate output from the start and can attempt direct RL (DeepSeek-R1-Zero demonstrated this at scale). The cost is poor output readability; DeepSeek ultimately added "cold-start SFT" in R1 to re-establish format. When in doubt, run SFT first.

---

## §1 SFT Implementation

### Loss Masking

SFT computes loss only on the response tokens, not the prompt. This is the only substantive engineering difference from pre-training. In practice: mask all tokens in the question/system-prompt portion before computing cross-entropy. Most frameworks (TRL, LLaMA-Factory) handle this automatically — verify it is actually on.

### Data Preparation

**Quality over quantity.** A few thousand high-quality demonstrations outperform tens of thousands of noisy ones. SFT bakes noise into parameters verbatim — there is no filtering at training time.

Practical checklist:
- **Format consistency**: every sample must use the same chat template (system/user/assistant structure). Mixed formats produce mixed outputs.
- **Diversity**: cover the full distribution of inputs the model will see at deployment. SFT generalizes poorly to inputs outside the training distribution — coverage is the only mitigation.
- **Response quality**: demonstrations set the ceiling. A dataset labeled by a 60-point annotator cannot train a 90-point model. Filter aggressively.
- **No factual knowledge injection**: SFT is poor at memorizing facts. Use RAG for facts; use SFT for protocols, formats, and behavioral patterns.

### LoRA Configuration

LoRA is the default for all post-training. Full-parameter fine-tuning is rarely justified.

| Parameter | SFT | RL |
|---|---|---|
| Rank | 64–256 | 8–32 (or rank=1) |
| Learning rate | ~10× full fine-tuning LR | ~10× full fine-tuning LR |
| Target modules | **All major weight matrices** (especially MLP layers) | Same |
| Alpha | Typically 2× rank | Same |

**Critical**: applying LoRA only to attention layers costs accuracy. MLP layers have the largest parameter count and must be included.

### Format Stabilization

The SFT phase is complete when the model reliably produces parseable structured output. Test this before starting RL (applies to structured-output tasks; for free-form tasks use instruction-following rate on a held-out set):

```python
# Quick format stability check (structured-output tasks)
parse_failures = 0
for sample in eval_set:
    output = model.generate(sample.prompt)
    try:
        json.loads(extract_json(output))
    except:
        parse_failures += 1
failure_rate = parse_failures / len(eval_set)
# Target: < 10% before starting RL
```

-> Read `references/sft-methodology.md` for prompt distillation recipes, LoRA tuning guidance, and format stabilization details.

---

## §2 RL Algorithm Selection

**Default recommendation: use GRPO for single-turn or short-trajectory tasks (≤~5 turns). Use PPO when trajectories exceed ~5 turns or fine-grained per-step credit assignment is required.** GRPO requires no value network, is cheaper to run, and works well with discriminative rewards. PPO's value network pays off when coarse credit assignment would obscure which steps drove the outcome.

### Algorithm Comparison

| Algorithm | Type | Core Mechanism | When to Use | Watch Out For |
|---|---|---|---|---|
| **GRPO** | On-policy | Sample N trajectories per prompt; advantage = within-group relative rank | Single-turn tasks, verifiable rewards, budget-constrained | Coarse credit assignment; fails when all-pass or all-fail groups dominate |
| **PPO** | On-policy | Clip update magnitude per step; value network estimates per-step advantage | Multi-turn agents, long trajectories, fine-grained credit assignment | Requires training and storing a value network; sensitive to hyperparameters |
| **DPO** | Off-policy | Turns preference pairs into a classification loss; implicit reward | High-quality preference data already exists; no online sampling needed | Cannot explore new policies; quality bounded by offline data coverage |
| **KTO** | Off-policy | Binary good/bad label per sample | Extremely limited annotation budget | Coarse signal |
| **Best-of-N** | Inference-time | Generate N, pick best | Early-stage rapid quality improvement; upper-bound estimation | Capabilities not embedded in weights; inference cost scales with N |

### On-Policy vs Off-Policy

**On-policy** (GRPO, PPO): the model generates its own trajectories during training. Training distribution matches deployment distribution. Higher cost, better generalization.

**Off-policy** (DPO, KTO): learns from a fixed dataset of existing trajectories. Cheaper, but bounded by data coverage. Cannot discover strategies not present in the data.

**Practical selection path:**
- Reliable reward signal + compute available → GRPO (simple) or PPO (flexible, better for long trajectories)
- High-quality preference pairs already exist → DPO/KTO
- Early exploration, no training budget → Best-of-N

### KL Divergence and Reward Hacking

All on-policy methods should include a KL penalty:

```
r_effective = r_RM - β · KL(π_θ ‖ π_ref)
```

The KL term (`kl_coef` in most frameworks) prevents two failure modes:
1. **Reward hacking**: the model learns to score highly on the reward proxy without actually improving at the task
2. **Distribution collapse**: outputs degenerate into repetition or gibberish

Without KL regularization, proxy reward (RM score) climbs monotonically while true quality peaks and then falls — the model learns to game the scorer, not to do the task.

**Safety-alignment callout**: safety behaviors are a learned capability that SFT/RL can overwrite. When fine-tuning a safety-aligned model, the KL reference policy should be the safety-aligned SFT checkpoint, not the raw base model. Reward functions that omit safety constraints cause RL to optimize them away — add safety violations as RLVP penalties if compliance is required.

-> Read `references/rl-training.md` for full PPO/GRPO mechanics, RLHF pipeline details, Bradley-Terry reward model training, and training stability practices.

---

## §3 Data, Environment, and Reward Design

**This section matters more than §2.** Algorithm choice is a marginal decision. Data quality and environment fidelity are load-bearing.

### The Priority Order

```
Strong base model → Polish environment + data → Tune algorithms
```

Chasing algorithm improvements before the environment and data are ready is the classic cart-before-horse mistake. Differences between PPO and GRPO only show up when everything else is already good.

### Simulation Environment Requirements

RL cannot train against real APIs (rate limits, account bans, side effects, irreversibility). You must build a shadow environment first.

Requirements for a trainable simulation environment:
- **Reset semantics**: must be able to reset to a clean starting state between episodes. Without this, state bleeds across trajectories and the reward signal becomes meaningless.
- **Throughput**: on-policy training requires generating many rollouts per step. The environment must support parallel execution (target: 100+ parallel workers for non-trivial tasks).
- **Fidelity**: the environment must resemble the real deployment scenario. Training on a simplified environment that differs from production is a form of distribution shift.
- **Reward computability**: the environment must be able to determine success/failure (or partial progress) deterministically. If the reward function returns NaN on 20%+ of trajectories, training will be unstable.

### Reward Signal Density

| Density | Form | When to Use |
|---|---|---|
| Binary (0/1) | Success or failure | Tasks with clear correct answers (math, SQL, unit tests) |
| Milestone | Partial credit at checkpoints | Multi-step tasks where intermediate progress is verifiable |
| Process (PRM) | Per-step feedback | Complex reasoning chains; reduces credit assignment difficulty |
| Vector | Multiple independent dimensions | Tasks with separable quality axes (accuracy, politeness, completeness) |
| Generative | LLM judge with reasoning | Open-ended tasks; provides diagnostic direction, not just a score |

**Default**: start with binary rewards. Add density only when training fails to converge or the all-fail/all-pass problem dominates.

### Multi-Turn Credit Assignment

Single-turn RL is straightforward: one prompt, one response, one reward. Multi-turn introduces credit assignment — which step in a 10-step trajectory earned the final reward?

**PPO approach**: uses GAE (Generalized Advantage Estimation) with a value network to estimate per-step advantage. More accurate but requires training the value network alongside the policy.

**GRPO approach**: treats the entire response as a single action. Advantage is within-group variance across N rollouts of the same prompt. Works well for short trajectories; degrades for long ones.

**RLVP pattern** (reward outcome, penalize path): when outcome rewards alone cannot express process constraints (e.g., "don't skip identity verification"), add a verified penalty for bad actions. Bad actions are cheap to detect deterministically; the penalty restores gradient signal in all-fail groups where GRPO would otherwise produce zero gradient.

Partial credit (progress rewards) accelerates convergence when progress is reachable — diagnose reachability by measuring within-group variance on a handful of base-model rollouts before committing to dense rewards.

### Tool-Calling RL Pipelines

Tool-calling RL adds a sandbox execution loop to the standard RL loop:

```
Prompt → Model generates action (think + tool call) → Sandbox executes → 
Feedback returned → Model continues → Final answer → Reward computed → Policy update
```

Two-stage training recipe (from ReTool):
1. **SFT warm-up** (~1 hour): convert pure-text reasoning data into tool-augmented trajectories. Establishes basic tool-call format.
2. **RL training** (PPO/GRPO on modified veRL): rollouts interleaved with real-time sandbox execution. Each step: model generates `<code>` tags → sandbox executes → result in `<interpreter>` tags → model continues.

Practical engineering for tool-calling RL:
- **Token-level policy gradient loss**: normalize across all tokens in the batch (not per-sample), so long responses receive gradient proportional to their length
- **Dynamic sampling**: reduce samples for easy prompts (already solved), increase for prompts in the 20–80% success-rate range (most informative)
- **Overlong reward shaping**: soft penalty for responses that grow long without improving accuracy

-> Read `references/training-data-environment.md` for simulation environment engineering, reward density paradigms, RLVP mechanics, and on-policy distillation.

---

## §4 Common Pitfalls

| Symptom | Root Cause | Fix |
|---|---|---|
| RL training fails immediately | Format not stable; reward returns NaN | Run SFT until parse failure < 10% (structured output), then start RL |
| Reward climbs but quality falls | Reward hacking | Add/increase KL penalty; add early stopping on held-out eval |
| GRPO produces no gradient | All-fail or all-pass groups dominate | Add RLVP penalty for bad actions; use dynamic sampling to filter zero-variance groups |
| Model collapses to repetitive output | KL penalty too low or absent | Increase `kl_coef`; check reference model is frozen |
| SFT performance degrades on OOD inputs | SFT memorized training distribution | Switch to RL for generalization; or expand SFT data coverage |
| RL training unstable, oscillating | Reward too sparse; learning rate too high | Add milestone rewards; reduce LR; check environment reset semantics |
| Post-training forgot general capabilities | Catastrophic forgetting | LoRA (not full fine-tuning); reduce training steps; mix in general-capability data |
| Post-training eroded safety behaviors | Reward omits safety constraints; KL ref is raw base | KL ref → safety-aligned checkpoint; add safety violations as RLVP penalty |

---

## Routing Map

These are companion skills in the ai-agents family.

| Concern | Companion Skill |
|---|---|
| Deciding whether/when to fine-tune | `agent-post-training` |
| Eval system design and metrics | `agent-evaluation` |
| Tool interface design for training environments | `agent-tool-design` |
| Agent architecture and orchestration | `agent-architecture` |
| Context and prompt design | `context-engineering` |

---

## NOT For

**Litmus**: Is the question about HOW to run training (mechanics, algorithms, implementation)? → here. Is it about WHETHER to train at all, or WHEN fine-tuning is the right call? → `agent-post-training`.

- Deciding whether/when to fine-tune → `agent-post-training`
- Pre-training from scratch → not covered here
- Model serving and inference infrastructure → ops skills
- Eval system design → `agent-evaluation`

---

## References

| Reference | When to read |
|---|---|
| `references/sft-methodology.md` | Loss masking mechanics, data preparation recipes, LoRA configuration details, format stabilization, prompt distillation |
| `references/rl-training.md` | RLHF pipeline, PPO/GRPO/DPO mechanics, KL divergence design, Bradley-Terry reward model training, training stability |
| `references/training-data-environment.md` | Simulation environment requirements, reward density engineering, multi-turn credit assignment, RLVP, on-policy distillation |
