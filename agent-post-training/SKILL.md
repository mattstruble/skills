---
name: agent-post-training
description: You MUST consult this skill when deciding whether to fine-tune a model for an agent task, choosing between SFT and RL, designing reward signals, or evaluating whether post-training ROI justifies the cost. Also trigger when someone asks "should we fine-tune this?", when prompt engineering has hit a ceiling, or when choosing between harness optimization and model training. NOT for actually running training (→ ml-post-training), designing eval systems (→ agent-evaluation), or agent architecture unrelated to training decisions (→ agent-architecture).
---

# Agent Post-Training

**Most agent problems are harness problems. Post-training is the last resort, not the first.**

Before any training decision: exhaust prompt engineering, context management, and tool design. The majority of agent capability gaps are fixed in the harness without touching model weights.

---

## Symptom Table

| Symptom | Decision Point |
|---|---|
| Prompt iteration plateaued, new scenarios still fail | §YAGNI — run model-swap experiment |
| SFT model degrades on inputs outside training distribution | §1 — distribution shift → RL |
| Agent violates constraints despite correct outcomes | §4 — reward the outcome, constrain the process |
| RL training unstable or reward hacking | §3 — data/environment quality first |
| Multi-turn agent can't learn which step caused failure | §4 — credit assignment / process rewards |
| "Should we fine-tune this?" | §YAGNI → §2 decision framework |

---

## YAGNI Gate

Post-training is warranted only when the harness ceiling is genuinely reached.

**The model-swap experiment.** Fix the harness, swap to a stronger frontier model. If scores materially improve, the bottleneck is the model — continue harness iteration or consider SFT. If scores do not improve, the bottleneck is the harness itself (context quality, tool design, prompt structure) — fix that first. See `agent-evaluation` for the model-swap diagnostic.

**The distribution test.** Is the deployment environment stable and close to what you can demonstrate? If yes, SFT is likely sufficient. If the environment shifts systematically or optimal strategies are unknown, RL becomes relevant.

Post-training is 10–100× more expensive than harness iteration and harder to reverse. Most agent applications never need it.

---

## §1 SFT vs RL — The Core Decision

**The one-sentence rule: SFT memorizes, RL generalizes.**

SFT learns a fixed input→output mapping from demonstrations. It is fast, stable, and sample-efficient — but its ceiling is the quality of the demonstrations, and it degrades when deployment conditions differ from training. RL learns a transferable strategy by optimizing for outcomes. It can discover solutions no demonstrator ever showed, but costs 10–100× more compute and is harder to stabilize.

| Dimension | SFT | RL |
|---|---|---|
| What is learned | Fixed mapping (memorization) | Transferable strategy (generalization) |
| Training signal | Standard answer per token | Reward per episode |
| Under distribution shift | Performance drops — recites old answer | Stable — re-solves with same strategy |
| Sample efficiency | High (thousands of examples) | Low (tens to hundreds of times SFT cost) |
| Training stability | High, converges quickly | Low, prone to oscillation |
| Best for | Format/style/process solidification | Generalization, strategy discovery, costly annotation |

**Why RL has a higher ceiling:** SFT's ceiling is the demonstrator's level — you cannot train a 90-point student from a 60-point teacher's labels. RL's ceiling is the task itself: any behavior that earns a reward gets reinforced, even if no one ever demonstrated it. Verification is also easier than generation — math answers can be checked against a key, code can be run through tests — so RL can train a model stronger than any available demonstrator.

**The ordering constraint.** SFT must precede RL for smaller base models with structured output requirements. RL needs parseable output to compute rewards; a base model producing unstructured text gives the reward function nothing to work with. SFT establishes the "form" (format, structure); RL then pursues the "spirit" (strategy, generalization). Strong frontier models may skip SFT, but the cost is poor output readability — DeepSeek-R1-Zero demonstrated this and ultimately added SFT back.

---

## §2 The Decision Framework

Work through these in order. Stop at the first answer that resolves the question.

**Step 1: Is post-training needed at all?**

If the problem can be solved through harness engineering — prompt optimization, tool design, context management — no model training is needed. Most agent applications fall here. Post-training is expensive and irreversible; exhaust the harness first.

**Step 2: If training is needed, try SFT first.**

**Audit demonstration quality before committing to SFT.** SFT's ceiling is the demonstrator's level — mediocre demonstrations produce a mediocre model. Check: Are examples correct? Do they cover the deployment distribution, including edge cases? Are styles and solutions varied enough to avoid mode collapse? Fix the data before training; no algorithm compensates for bad demonstrations.

SFT is appropriate when:
- The output format needs to be stabilized (JSON schema, API call format, tool call syntax)
- Protocol knowledge needs to be baked in (terminology, style, process habits — "how to say and do things")
- Style or tone needs to be unified across outputs
- The training and deployment distributions are close

SFT is **not** appropriate for injecting large amounts of factual knowledge ("what to know") — that requires continued pre-training or RAG.

**Step 3: When SFT is insufficient, add RL.**

The signal that SFT has hit its ceiling: adding more demonstrations no longer improves performance on new scenarios. The root is not the number of examples but SFT's optimization objective — it cannot generalize beyond its training distribution.

RL is warranted when:
- Deployment distribution drifts systematically from training (rules change, environment changes)
- Expert demonstrations are themselves suboptimal and you need to discover better strategies
- Annotation cost is too high to demonstrate every path
- The task requires multi-step reasoning where the optimal path is unknown

**The practical test:** When "no matter how many demonstrations are added, new scenarios still perform poorly" — that is the tipping point to switch to RL.

---

## §3 Data and Environment — More Important Than Algorithms

**Algorithm choice is the last lever, not the first.**

The sensible order of effort: choose a strong base model → polish the environment and data → only then tune algorithms and hyperparameters. Teams that chase algorithm selection before their environment and data are solid are optimizing the wrong variable.

**On data quality:** Three dimensions that matter more than algorithm choice:
- **Coverage** — does the data cover the situations encountered during deployment, especially long-tail and edge cases?
- **Diversity** — are speakers, styles, and solutions varied enough? A narrow dataset collapses the model into a single mode.
- **Annotation accuracy** — are the demonstration answers themselves correct? Erroneous thought processes get imitated.

**The Anthropic example.** Before 2025, Anthropic's post-training recipe was SFT on massive high-quality data plus RLAIF — leaning little on verifiable-reward RL. Its coding models were already excellent. The reason was data quality, not algorithm sophistication. When SFT data is good enough, an unfancy recipe can train a top-tier model. RL then raises the ceiling further — but only on a foundation of good data.

**On simulation environment:** RL requires a training environment that resembles the real deployment scenario. A distorted environment trains a policy that works only in simulation. Building a high-fidelity environment is often harder and more expensive than the training itself.

---

## §4 Reward Design Principles (for Agent Builders)

When you reach the point of designing RL training, reward design is where agent builders have the most leverage.

**The density spectrum.** Rewards range from sparse binary (success/failure at the end) to dense process rewards (feedback at every step). The right choice depends on the task:

- **Binary outcome rewards** are sufficient when the answer is verifiable (math, SQL, code tests). Simple and reliable.
- **Process rewards** provide step-by-step feedback, reducing credit assignment difficulty in long multi-turn tasks. Cost: higher annotation burden and risk of over-constraining exploration.
- **Outcome rewards** give maximum exploration freedom — RL can discover strategies no demonstrator ever showed. Cost: harder to train, requires more samples.

**The practical tradeoff:** Process rewards accelerate convergence but may prevent the model from discovering better strategies. Outcome rewards allow discovery (like the "pushcut" action in robot manipulation — a more efficient strategy never seen in human demonstrations) but require more training. When the correctness of intermediate steps is easy to define, process rewards are more efficient. When the optimal path is unknown, outcome rewards have more potential.

**Reward the outcome, constrain the process.** For deployable agents, pure outcome rewards are insufficient — they actively incentivize constraint violations (cutting corners raises apparent success rate). The pattern: outcome reward as the primary signal, plus verifiable path penalties for machine-detectable bad actions (destructive commands, skipping identity verification, editing test files). The penalty target must be a specific detectable action, never "lack of progress" — that teaches the agent to do nothing.

**Multi-turn credit assignment.** In a 10-step task, which step caused the final success or failure? This is the core challenge of multi-turn RL. Practical options: turn-level credit assignment (cheaper than token-level, more precise than trajectory-level) is the common compromise in current multi-turn agent RL frameworks.

-> Read `references/agent-reward-design.md` for the full reward density spectrum, process vs outcome tradeoffs, and tool-calling reward framing.

---

## Worked Examples

**"Should we fine-tune our customer service agent?"**

The agent handles returns, answers policy questions, and escalates to humans. It's using GPT-4 with a detailed system prompt. After a dozen prompt iterations it's stuck at ~78% on the eval set.

*Decision path:* A dozen prompt iterations at 78% signals the harness ceiling may be near — but run the model-swap experiment first. Swap to a stronger frontier model with the same harness. If scores jump materially (say, to 88%), the bottleneck is the model, not the harness — SFT on high-quality demonstration transcripts is the right next step. If scores don't improve, the bottleneck is still the harness: investigate context quality (are policy documents actually in context?), tool design (is the return eligibility check returning ambiguous results?), and prompt structure before touching model weights. RL is not warranted unless the deployment environment shifts (new policies, new product lines) or demonstrations are provably suboptimal.

**"Our coding agent keeps failing on novel repository structures it hasn't seen before."**

*Decision path:* This is a distribution shift problem — the classic SFT failure mode. SFT memorized patterns from training repos; novel structures are out-of-distribution. If the task has verifiable correctness (tests pass/fail), RL is the right tool. The reward signal is clear (test pass rate), the environment is buildable (code sandbox), and the goal is generalization beyond demonstrations. Before committing to RL: verify the base model is strong enough to produce structured output without SFT warm-up, or plan a short SFT phase to stabilize output format first.

**"We want to teach our agent to use a new internal API correctly."**

*Decision path:* This is a protocol knowledge problem — exactly what SFT is designed for. A few hundred high-quality demonstration trajectories showing correct API call sequences will bake the protocol into the model efficiently. RL is not warranted unless the API usage patterns are highly variable and optimal call sequences need to be discovered.

---

## Routing Map

| Decision | Companion Skill | Source |
|---|---|---|
| Actually running SFT or RL training | `ml-post-training` | Ch7 implementation |
| Designing the eval system that feeds training | `agent-evaluation` | Ch6 |
| Agent architecture unrelated to training | `agent-architecture` | Ch1 |
| Tool interface design | `agent-tool-design` | Ch4 |
| Model-swap diagnostic | `agent-evaluation` | Ch6 |

---

## NOT For

- **Running training** (LoRA config, PPO/GRPO mechanics, training infra) → `ml-post-training`
- **Eval system design** (metrics, harness construction, benchmark selection) → `agent-evaluation`
- **Agent architecture** unrelated to training decisions → `agent-architecture`
- **Tool interface depth** (ACI design, tool taxonomy) → `agent-tool-design`

---

## References

| Reference | When to read |
|---|---|
| `references/post-training-decisions.md` | Full SFT vs RL criteria, cost-benefit boundary, algorithm selection guide, common pitfalls |
| `references/agent-reward-design.md` | Reward density spectrum, process vs outcome tradeoffs, multi-turn credit assignment, tool-calling reward framing |
