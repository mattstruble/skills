# RL Generalization Literature — Source Attribution

Provenance for skill content synthesized from ~71 public research papers on
reinforcement learning generalization, environment design, curriculum learning,
and reward engineering. This file is **not registered in any skill's References
table** — it is read by humans and by skill-building sessions, and is **never
auto-loaded at skill runtime**. It exists for human traceability and to lock
citation conventions across the rl-generalization skill and related bolsters.

Source: Public research papers (arXiv, conference proceedings). No single
primary source — this is a multi-paper literature synthesis originally curated
from a survey document (August 2026) that collected findings from these papers
into design rules.

## For skill-builders (read before extending this material)

**Official citation line.** Paste this verbatim into the intro of each new
`references/*.md` file you create from this body of work:

```
*Synthesized from public RL generalization research — full paper list and provenance in [docs/sources/rl-generalization-literature.md](../../docs/sources/rl-generalization-literature.md).*
```

**Citation rules:**

1. **Reference files** carry the official citation line in their intro. Prose
   is paraphrased — no verbatim quotes from papers. Cite specific papers
   inline as "(Author et al. Year)" when a finding is from one paper.
2. **Body weaves** — material woven into an existing skill's `SKILL.md` —
   carry **no citation line**. Record them only as a row in the content map
   below. Attribute genuinely contestable stances inline.
3. **Quantitative claims** must cite their source paper. Do not present a
   number without attribution.

**Other rules:**

- **Conceptual filenames.** Name reference files by concept (e.g.
  `environment-diversity.md`, `curriculum-calibration.md`), never by author.
- **Paraphrase only.** No verbatim quotes from papers.
- **No Lila-specific content.** This synthesis draws from public research
  only. Do not include pod terminology, internal pipeline decisions, or
  proprietary training architecture details.


## Paper corpus by theme cluster

### Cluster 1: Procedural Generation & Generalization

| Paper | Venue | Key Finding | Feeds |
|---|---|---|---|
| Cobbe et al. "Quantifying Generalization in RL" | ICML 2019 | Generalization gap closes logarithmically with training level count; ~10K levels needed to close a 33-point gap on CoinRun | rl-generalization |
| Cobbe et al. "Leveraging Procedural Generation to Benchmark RL (ProcGen)" | ICML 2020 | 16-game benchmark confirms diversity threshold; 200 levels = 40-60% test performance, unlimited levels closes gap | rl-generalization, agent-evaluation |

**arXiv**: [1812.02341](https://arxiv.org/abs/1812.02341), [1912.01588](https://arxiv.org/abs/1912.01588)

### Cluster 2: Domain Randomization

| Paper | Venue | Key Finding | Feeds |
|---|---|---|---|
| Tobin et al. "Domain Randomization for Sim-to-Real Transfer" | IROS 2017 | Training with randomized sim (textures, lighting, positions) enables zero-shot real transfer; 1.5cm mean error | rl-generalization, ml-post-training |
| OpenAI "Learning Dexterous In-Hand Manipulation (Dactyl)" | 2018 | 50+ randomized physics params; 0% real success without → ~50 consecutive rotations with; ~2-3× compute multiplier | rl-generalization, ml-post-training |
| OpenAI "Solving Rubik's Cube with a Robot Hand (ADR)" | 2019 | Automatic Domain Randomization across 380 params; 60% real Rubik's solve vs 0% fixed; policy learns to probe environment; ~10× Dactyl compute | rl-generalization, ml-post-training |

**arXiv**: [1703.06907](https://arxiv.org/abs/1703.06907), [1808.00177](https://arxiv.org/abs/1808.00177), [1910.07113](https://arxiv.org/abs/1910.07113)

### Cluster 3: Open-Ended Learning

| Paper | Venue | Key Finding | Feeds |
|---|---|---|---|
| Team et al. "Open-Ended Learning Leads to Generally Capable Agents (XLand)" | DeepMind 2021 | ~10^37 task space with dynamic task selection; removing adaptive picker costs ~50-65% of held-out performance | rl-generalization, ml-post-training |
| Adaptive Agent Team "Human-Timescale Adaptation (AdA / XLand 2.0)" | 2023 | In-context adaptation in ~30 episodes; performance scales log-linearly with task-space diversity | rl-generalization |
| Matthews et al. "Kinetix" | ICLR 2025 | Random procedural 2D physics envs; random variation reaches ~70-80% of curriculum-trained performance; 1M random > 10K curated | rl-generalization |
| Matthews et al. "Craftax" | ICML 2024 | JAX-accelerated Crafter with achievement dependency depth up to 8; exposes deep compositional structure requirements | rl-generalization |

**arXiv**: [2107.12808](https://arxiv.org/abs/2107.12808), [2301.07608](https://arxiv.org/abs/2301.07608), [2410.23208](https://arxiv.org/abs/2410.23208), [2402.16801](https://arxiv.org/abs/2402.16801)

### Cluster 4: Unsupervised Environment Design (UED)

| Paper | Venue | Key Finding | Feeds |
|---|---|---|---|
| Dennis et al. "PAIRED" | NeurIPS 2020 | Protagonist-antagonist regret signal produces emergent curricula; zero-shot transfer where DR fails | rl-generalization |
| Jiang et al. "Prioritized Level Replay (PLR)" | ICML 2021 | Score levels by learning potential (TD error); replay high-scoring ones; ~70% vs 55% for uniform | rl-generalization, ml-post-training |
| Jiang et al. "Robust PLR" | NeurIPS 2021 | PLR + regret-gated generator admission; 3-50× more sample-efficient than PAIRED | rl-generalization, ml-post-training |
| Parker-Holder et al. "ACCEL" | ICML 2022 | Evolve existing high-regret levels via mutation; solves 12/12 vs PLR's 10/12 | rl-generalization |
| Rutherford et al. "No Regrets" (SFL) | NeurIPS 2024 | Standard regret approximations are unreliable; "solved sometimes but not always" selection beats regret-based on hard tail | rl-generalization, agent-evaluation |
| Li et al. "DIPLR" | IJCAI 2023 | Diversity-only level selection recovers most benefit of regret-based methods | rl-generalization |
| Jiang et al. "minimax" | 2023 | Efficient JAX baselines; random variation is stronger baseline than curriculum papers suggest | rl-generalization |

**arXiv**: [2012.02096](https://arxiv.org/abs/2012.02096), [2010.03934](https://arxiv.org/abs/2010.03934), [2110.02439](https://arxiv.org/abs/2110.02439), [2203.01302](https://arxiv.org/abs/2203.01302), [2408.15099](https://arxiv.org/abs/2408.15099), [2301.08025](https://arxiv.org/abs/2301.08025), [2311.12716](https://arxiv.org/abs/2311.12716)


### Cluster 5: RLVR Cross-Domain Transfer

| Paper | Venue | Key Finding | Feeds |
|---|---|---|---|
| Chu et al. "SFT Memorizes, RL Generalizes" | ICML 2025 | RL on outcomes generalizes to shifted versions (+3 to +61 pts); SFT on same trajectories degrades (-6 to -80 pts) | rl-generalization, ml-post-training |
| Yue et al. "Does RL Really Incentivize Reasoning Beyond Base?" | NeurIPS 2025 Oral | RLVR improves pass@1 but base model achieves higher pass@k at large k; current RL sharpens more than expands | rl-generalization, agent-evaluation |
| Liu et al. "ProRL" (NVIDIA) | 2025 | Prolonged RL with KL control + reference resetting expands reasoning boundaries; solves tasks base model cannot at any k | rl-generalization |
| Wu et al. "The Invisible Leash" | 2025 | RLVR improves precision but narrows support; token entropy may rise while answer-level entropy falls | rl-generalization, agent-evaluation |
| Shao et al. "Spurious Rewards" | 2025 | Random rewards capture 21.4pp of 29.1pp gain on Qwen (GRPO clipping bias); fails on Llama/OLMo — model-dependent | agent-evaluation |
| Wang et al. "1-shot RLVR" | 2025 | Single training example: 36.0% → 73.6% on MATH500 (Qwen); post-saturation generalization phenomenon | rl-generalization, agent-evaluation |
| Zhao et al. "Absolute Zero" | 2025 | Self-play task proposal + code executor reward; zero external data; SOTA on code+math among zero-setting models | rl-generalization |
| Cheng et al. "GURU" | 2025 | 92K examples across 6 domains; domains saturated in pretraining (math/code) transfer easily; thin domains (logic/sim/tabular) need in-domain training | rl-generalization |
| Li et al. "Can One Domain Help Others?" | 2025 | Multi-domain GRPO: mutual enhancement between math/code/logic but also conflicts; base vs instruct models differ significantly under RL | rl-generalization |
| Huan et al. "Does Math Improve General Capabilities?" | 2025 | Math RL training can hurt other domains; single-domain training drops code 22-38 pts | rl-generalization, agent-evaluation |
| Hu et al. "Breaking Barriers" | ICLR 2026 | RPT gains do transfer to unseen domains under certain conditions | rl-generalization |
| Liu et al. "SPIRAL" | 2025 | Self-play on zero-sum games incentivizes reasoning via multi-agent multi-turn RL | rl-generalization |
| Cui et al. "Entropy Mechanism" | 2025 | R = -a·e^H + b: performance trades from entropy; ceiling predictable from H=0; entropy collapse is the scaling bottleneck | rl-generalization, ml-post-training, agent-evaluation |
| Cheng et al. "IsoCompute Playbook" | 2026 | Compute-optimal rollout allocation: optimal parallel rollouts increase with budget then saturate; more rollouts mitigate cross-problem interference; problem count affects stability | ml-post-training |

**arXiv**: [2501.17161](https://arxiv.org/abs/2501.17161), [2504.13837](https://arxiv.org/abs/2504.13837), [2505.24864](https://arxiv.org/abs/2505.24864), [2507.14843](https://arxiv.org/abs/2507.14843), [2506.10947](https://arxiv.org/abs/2506.10947), [2504.20571](https://arxiv.org/abs/2504.20571), [2505.03335](https://arxiv.org/abs/2505.03335), [2506.14965](https://arxiv.org/abs/2506.14965), [2507.17512](https://arxiv.org/abs/2507.17512), [2507.00432](https://arxiv.org/abs/2507.00432), [2506.19733](https://arxiv.org/abs/2506.19733), [2506.24119](https://arxiv.org/abs/2506.24119), [2505.22617](https://arxiv.org/abs/2505.22617), [2603.12151](https://arxiv.org/abs/2603.12151)

### Cluster 6: Curriculum & Difficulty

| Paper | Venue | Key Finding | Feeds |
|---|---|---|---|
| Bae et al. "Online Difficulty Filtering" | EACL 2026 | Optimal signal at 50% success rate; 30-70% band beats unfiltered by ~4 pts; one-sided filtering worse than none | rl-generalization, ml-post-training |
| Yang et al. "DARS" | 2026 | Depth (adaptive rollouts for hard problems) + Breadth (large diverse batches) are orthogonal and complementary; training to convergence destroys breadth | rl-generalization, ml-post-training, agent-evaluation |
| Chen et al. "SEC" | 2025 | Bandit-based curriculum using advantage as learning-gain proxy; +13-33% relative OOD improvement vs flat ID gains | rl-generalization, ml-post-training |
| Portelas et al. "ALP-GMM" | CoRL 2019 | Teacher algorithm tracks absolute learning progress via Gaussian mixture; selects tasks at learning frontier | rl-generalization |
| ByteDance "DAPO" | 2025 | Open-source large-scale GRPO; dynamic sampling, clip-higher removal, token-level loss normalization | ml-post-training |
| Shrestha et al. "Warm Up Before You Train" | EMNLP 2025 | Warmup on long CoT from logic puzzles (K&K) → MATH 55.6→77.4; short CoT same puzzles → MATH 11%; reasoning BEHAVIOR transfers, not topic | rl-generalization |

**arXiv**: [aclanthology](https://aclanthology.org/2026.eacl-long.30.pdf), [2508.13755](https://arxiv.org/abs/2508.13755), [2505.14970](https://arxiv.org/abs/2505.14970), [1910.07224](https://arxiv.org/abs/1910.07224), [2503.14476](https://arxiv.org/abs/2503.14476), [2505.13718](https://arxiv.org/abs/2505.13718)


### Cluster 7: Reward Design & Hacking

| Paper | Venue | Key Finding | Feeds |
|---|---|---|---|
| Gao et al. "Scaling Laws for Reward Model Overoptimization" | 2022 | True reward = d·√KL - c·KL; peaks then degrades; larger RM shifts peak rightward but never eliminates overoptimization | rl-generalization, ml-post-training |
| Skalse et al. "Defining and Characterizing Reward Hacking" | NeurIPS 2022 | Formal proof: unhackable reward functions have measure zero; hacking is default with imperfect proxies | rl-generalization |
| Ng, Harada, Russell "Policy Invariance Under Reward Transformations" | ICML 1999 | Potential-based shaping F=γΦ(s')-Φ(s) is the ONLY form guaranteed to preserve optimal policy | rl-generalization, ml-post-training |
| Lightman et al. "Let's Verify Step by Step" | 2023 | PRM solves 78.2% vs ORM 72.4% (MATH best-of-1860); human step labels consistently dominate outcome-only | ml-post-training |
| Setlur et al. "Rewarding Progress" | ICLR 2025 | Automated process verifiers without human step labels; Monte Carlo estimation of step correctness | ml-post-training |
| Zheng et al. "ProcessBench" | ACL 2025 | Benchmark for process reward models; auto-generated step rewards degrade on new distributions | ml-post-training, agent-evaluation |
| Singhal et al. "Length Correlations in RLHF" | 2023 | Rewarding length alone reproduces most apparent benefit of RLHF; length is a confound in all reward-based training | rl-generalization, agent-evaluation |
| Kirk et al. "Effects of RLHF on Generalisation and Diversity" | ICLR 2024 | RLHF reduces output diversity; models converge to narrow high-reward modes | rl-generalization, agent-evaluation |
| MacDiarmid et al. (Anthropic) "Natural Emergent Misalignment" | 2025 | Reward hacking in code RL generalizes into sabotage/deception on unrelated tasks; framing affects transfer direction | rl-generalization |
| Rajan "Auditing Reward Hackability" | 2026 | 28.5% of SWE-bench tasks accept wrong patches; +14pp score inflation on hackable tasks; 62% of auto-generated tests are broken | ml-post-training, agent-evaluation |
| "Reward Hacking in Rubric-Based RL" | 2026 | Rubric rewards checking "mentions X" produce longer, denser, less accurate answers | rl-generalization, agent-evaluation |
| "Limits of Generalization in RLVR" | 2025 | Two case studies showing RL gains don't generalize to structurally different problems within same domain | rl-generalization, agent-evaluation |

**arXiv**: [2210.10760](https://arxiv.org/abs/2210.10760), [2209.13085](https://arxiv.org/abs/2209.13085), [ICML99](https://people.eecs.berkeley.edu/~russell/papers/icml99-shaping.pdf), [2305.20050](https://arxiv.org/abs/2305.20050), [2410.08146](https://arxiv.org/abs/2410.08146), [2412.06559](https://arxiv.org/abs/2412.06559), [2310.03716](https://arxiv.org/abs/2310.03716), [2310.06452](https://arxiv.org/abs/2310.06452), [2511.18397](https://arxiv.org/abs/2511.18397), [2606.16062](https://arxiv.org/abs/2606.16062), [2605.12474](https://arxiv.org/abs/2605.12474), [2510.27044](https://arxiv.org/abs/2510.27044)

### Cluster 8: Compositionality & Skills

| Paper | Venue | Key Finding | Feeds |
|---|---|---|---|
| Redhardt et al. "Scaling Can Lead to Compositional Generalization" | NeurIPS 2025 Spotlight | Compositional generalization requires: (1) compositional support (every factor value present), (2) connected support (no value locked to single partner); linear decodability of factors = generalization | rl-generalization |
| Ruis et al. "gSCAN" | NeurIPS 2020 | Benchmark with splits breaking connected support; models drop to near 0% on violated conditions | rl-generalization |
| Mendez et al. "CompoSuite" | CoLLAs 2022 | Multi-task robotics benchmark with combinatorial task structure; measures compositional transfer | rl-generalization |
| Eysenbach et al. "DIAYN" | ICLR 2019 | Discovers diverse skills via mutual information maximization without extrinsic reward | rl-generalization |
| Laskin et al. "URLB" | NeurIPS 2021 | Methods optimizing for skill diversity transfer WORSE downstream; distinguishability ≠ usefulness | rl-generalization |
| Ghosh et al. "Epistemic POMDPs" | NeurIPS 2021 | Training across many envs makes the current env unobservable → optimal behavior is to gather info first, not react reflexively | rl-generalization |
| Yu et al. "Meta-World" | CoRL 2019 | Multi-task agent at ~88% on 10 tasks drops to ~35-38% on 50; negative transfer from capacity saturation | rl-generalization, agent-evaluation |
| Shenfeld et al. "RL's Razor" | 2025 | RL forgets less because it's KL-minimal: divergence 0.019 (RL) vs 0.283 (SFT) on same task | rl-generalization, ml-post-training |
| Mukherjee et al. "RL Finetunes Small Subnetworks" | NeurIPS 2025 | RL modifies only small subsets of parameters; explains why it preserves prior capabilities better than SFT | rl-generalization |

**arXiv**: [2507.07207](https://arxiv.org/abs/2507.07207), [2003.05161](https://arxiv.org/abs/2003.05161), [2207.04136](https://arxiv.org/abs/2207.04136), [1802.06070](https://arxiv.org/abs/1802.06070), [2110.15191](https://arxiv.org/abs/2110.15191), [2107.06277](https://arxiv.org/abs/2107.06277), [1910.10897](https://arxiv.org/abs/1910.10897), [2509.04259](https://arxiv.org/abs/2509.04259), [2505.11711](https://arxiv.org/abs/2505.11711)

### Cluster 9: Agentic Environment Scaling

| Paper | Venue | Key Finding | Feeds |
|---|---|---|---|
| Pan et al. "SWE-Gym" | ICML 2025 | First open SWE training environment; 2,438 tasks from 11 repos; establishes real-reward baseline | ml-post-training |
| Yang et al. "SWE-smith" | 2025 | Fixed 700 traces, 4→100 repos: 13.6%→19%; pipeline generates 50K instances from 128 repos | rl-generalization, ml-post-training |
| Jain et al. "R2E-Gym" | 2025 | Procedural coding envs with dense reward (partial test credit); supports difficulty stratification | ml-post-training |
| Fang et al. "AgentScaler" | ACL Findings 2026 | Framework for efficiently scaling training environment count while managing compute costs | rl-generalization, ml-post-training |
| Li/Ye et al. "InternBootcamp" | 2025 | 8→512 verifiable task types; 8-task run collapsed, 512 stayed stable; transfer improved continuously | rl-generalization |
| Gandhi et al. "Endless Terminals" | 2026 | Procedural terminal tasks; own-eval ~10× higher than human benchmark; command diversity ratio 0.49 (success) vs 0.18 (failure) | rl-generalization, agent-evaluation |
| Wang et al. "Agent World Model" | ICML 2026 | Synthetic environments from world model for agentic RL; infinite generation | rl-generalization |
| Xiang et al. "RACES" | 2026 | Recursive composition of verifiable envs; 50 composed = 300 standalone; operators: SEQUENTIAL, PARALLEL, SORT, SELECT | rl-generalization |
| Ritchie et al. "Office Work → SWE" | 2026 | 363 office tasks, zero SWE content → +5.8pp on SWE-Bench Pro; goal-directed execution transfers cross-domain | rl-generalization |
| Zhou et al. (Meta) "Self-Challenging" | NeurIPS 2025 | Agent generates its own increasingly difficult challenges | rl-generalization |
| Ariadne "RLVR extends VLM reasoning" | 2025 | Synthetic maze training → real navigation transfer; RLVR expands boundary where base has 0% pass@k | rl-generalization |
| ScaleRL | 2025 | Analysis of scaling RL compute for LLMs; practical allocation rules | ml-post-training |

**arXiv**: [2412.21139](https://arxiv.org/abs/2412.21139), [2504.21798](https://arxiv.org/abs/2504.21798), [2504.07164](https://arxiv.org/abs/2504.07164), [2509.13311](https://arxiv.org/abs/2509.13311), [2508.08636](https://arxiv.org/abs/2508.08636), [2601.16443](https://arxiv.org/abs/2601.16443), [2602.10090](https://arxiv.org/abs/2602.10090), [2606.12373](https://arxiv.org/abs/2606.12373), [2608.01604](https://arxiv.org/abs/2608.01604), [2506.01716](https://arxiv.org/abs/2506.01716), [2511.00710](https://arxiv.org/abs/2511.00710), [2510.13786](https://arxiv.org/abs/2510.13786)


## Content map

| Cluster | Skill | Reference file(s) |
|---|---|---|
| Clusters 1, 2, 3, 4 (environment diversity) | rl-generalization | environment-diversity.md |
| Cluster 5 (RLVR transfer) | rl-generalization | transfer-dynamics.md |
| Cluster 6 (curriculum) | rl-generalization | curriculum-calibration.md |
| Cluster 6 (curriculum) | ml-post-training | training-data-environment.md (bolster) |
| Cluster 7 (reward design) | rl-generalization | reward-generalization.md |
| Cluster 7 (reward design) | ml-post-training | training-data-environment.md (bolster) |
| Cluster 8 (compositionality) | rl-generalization | compositional-coverage.md |
| Cluster 9 (agentic scaling) | rl-generalization | environment-diversity.md |
| Clusters 5, 6, 7 (measurement) | agent-evaluation | breadth-measurement.md (new reference) |

## Accessibility notes

All papers were accessed via arXiv abstract pages. Full-text PDFs were not
fetched in bulk; abstracts plus the original survey document provided
sufficient detail for all quantitative claims. Papers marked as 2026 (DARS,
Rajan, RACES, Endless Terminals, Ritchie, Rubric-RL, IsoCompute) are recent
preprints — treat individual numbers as indicative pending replication.

## Caveats inherited from the literature

- Much 2025 RLVR evidence is on one model family (Qwen); effects often do
  not reproduce on Llama or OLMo (Spurious Rewards 2025).
- ~25-33% of realistic code RL environments are cheatable (Rajan 2026).
- The 1-shot RLVR result (Wang et al.) is the null hypothesis any "scaling
  environments helped" claim must beat on that model family.
- Diversity-causes-transfer currently rests on correlations across studies,
  not one clean controlled experiment.
