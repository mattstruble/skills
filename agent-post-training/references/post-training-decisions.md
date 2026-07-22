# Post-Training Decisions

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## When Post-Training Outperforms Harness Optimization

Harness engineering (prompts, context, tools) is the right first lever. Post-training becomes the better investment when:

1. **The harness ceiling is demonstrably reached.** Adding more demonstrations or refining prompts no longer moves the eval metric on new scenarios. This is the clearest signal that the optimization objective itself — not the data volume — is the bottleneck.

2. **The capability gap is in generalization, not format.** If the model produces the right format but wrong answers on novel inputs, that is a generalization problem. Harness changes cannot fix a model that has memorized the wrong strategy.

3. **The task has verifiable correctness.** When success/failure can be determined programmatically (test pass/fail, answer matches key, SQL returns expected result), RL training becomes tractable. Verifiable tasks are the sweet spot for post-training investment.

4. **Protocol knowledge needs to be permanent.** If the agent must consistently use a specific API call format, terminology set, or output schema across all interactions, SFT bakes this in more reliably than a prompt that can be overridden or forgotten.

---

## SFT vs RL Decision Criteria

### Choose SFT when:

- **Output format needs stabilization.** The model must produce parseable JSON, correct tool call syntax, or a specific schema. SFT is the fastest and most reliable way to establish this.
- **Protocol knowledge is the gap.** Style, terminology, process habits ("how to say and do things") — SFT solidifies these efficiently with thousands of examples.
- **Training and deployment distributions are close.** If the scenarios the model will encounter in production closely resemble what you can demonstrate, SFT's memorization is a feature, not a bug.
- **Annotation cost is manageable.** You can produce high-quality demonstrations that cover the task distribution.
- **Speed and stability matter.** SFT converges quickly and predictably. RL is 10–100× more expensive and prone to oscillation.

### Choose RL when:

- **Deployment distribution drifts from training.** The classic SFT failure mode: the model memorizes training patterns and degrades when conditions change. RL learns a transferable strategy that re-solves rather than recites.
- **Expert demonstrations are suboptimal.** SFT's ceiling is the demonstrator's level. If the best available demonstrations are mediocre, RL can discover superior strategies that no demonstrator ever showed.
- **Annotation cost is prohibitive.** RL requires a reward function, not demonstrations. When demonstrating every path is too expensive, a verifiable reward signal is the practical alternative.
- **The task requires multi-step reasoning with unknown optimal paths.** RL's online exploration allows the model to discover strategies through trial and error, including strategies that would never appear in human demonstrations.

### The two-stage pipeline (most robust):

Phase 1 — SFT: Stabilize output format. Goal is parseable output, not maximum task performance. Stop when format is stable and basic capability is achieved. Overtraining here causes the model to collapse into the training distribution, making RL recovery harder.

Phase 2 — RL: Optimize task reward. Prerequisite is stable format so the reward function can compute. Goal is strategy generalization beyond the SFT demonstrations.

---

## Cost-Benefit Boundary

**SFT cost:** Low. Hours to days of compute. High sample efficiency — thousands of examples are effective. Stable, predictable convergence.

**RL cost:** High. Often 10–100× the compute of SFT. Low sample efficiency. Prone to oscillation, sensitive to hyperparameters. Requires a simulation environment that faithfully represents the deployment scenario — building this environment is often harder and more expensive than the training itself.

**The boundary rule:** If the task distribution is predictable and you can gather demonstrations that are diverse and high-quality enough, SFT often does the job. RL is truly irreplaceable only in three scenarios: systematic distribution drift, suboptimal expert demonstrations, or annotation cost too high to demonstrate every path.

**The Anthropic data point.** Before 2025, Anthropic's post-training recipe was SFT on massive high-quality data plus RLAIF, with little verifiable-reward RL. Its coding models were already excellent. The reason was data quality, not algorithm sophistication. This confirms: when SFT data is good enough, an unfancy recipe can train a top-tier model. RL then raises the ceiling further — but only on a foundation of good data. Data decides how far you can go; RL decides how much higher.

---

## Algorithm Selection (for Agent Builders)

Algorithm choice is the last lever, not the first. The sensible order: strong base model → good environment and data → then algorithm tuning. Differences between algorithms only show up when the environment is realistic and the data is good.

**Practical selection path:**
- Reliable reward signal + compute available → GRPO (simpler) or PPO (better credit assignment for long trajectories)
- High-quality preference data available → DPO/KTO (low cost, no online sampling)
- Early exploration stage → Best-of-N for a quick quality estimate without training

The key distinction between GRPO and PPO for agent builders: GRPO treats the entire response as a single action and distributes credit evenly across all tokens — this works well for short single-turn tasks but dilutes the learning signal in long multi-turn tasks. PPO with a value network provides finer-grained credit assignment and remains valuable for complex multi-turn agents.

---

## Common Pitfalls

**Reward hacking.** When the reward model or reward function is a proxy for the true objective, the model learns to maximize the proxy without improving on the actual task. Verbose, ingratiating responses that score well on a reward model but provide no real value are the canonical example. Mitigation: KL penalty to keep the model near the reference distribution; early stopping; human evaluation alongside proxy metrics.

**Overtraining SFT before RL.** SFT should establish format stability and basic capability, then stop. Overtraining causes the model to collapse into the training distribution so thoroughly that RL cannot recover out-of-distribution performance. The balance: "just enough SFT" to achieve stable format and basic capability, without overstaying.

**Distorted simulation environment.** A training environment that doesn't faithfully represent deployment trains a policy that works only in simulation. This is the most common way RL projects fail — not because the algorithm was bad, but because the practice field was not the exam room.

**Chasing algorithms before data is ready.** Teams that invest in algorithm tuning before their data quality and environment fidelity are solid are optimizing the wrong variable. The return on investment for data coverage, diversity, and annotation accuracy is usually far higher than switching to a fancier algorithm.
