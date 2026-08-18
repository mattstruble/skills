*Synthesized from public RL generalization research — full paper list and provenance in [docs/sources/rl-generalization-literature.md](../../docs/sources/rl-generalization-literature.md).*

# Environment Diversity

The strongest single lever for transfer is variety across training environments.
This reference collects the quantitative evidence and implementation patterns.

---

## The Scaling Law

Environment count and generalization gap follow a log-linear relationship:
each order-of-magnitude increase in distinct environments buys a roughly
constant reduction in the train-test gap.

| Study | Environments | Result |
|---|---|---|
| CoinRun (Cobbe 2019) | 100 levels | 33-point train-test gap |
| CoinRun (Cobbe 2019) | 10,000 levels | Gap effectively closed |
| ProcGen (Cobbe 2020) | 200 levels | 40-60% of train performance on test |
| ProcGen (Cobbe 2020) | Unlimited | Gap mostly closed |
| SWE-smith (Yang 2025) | 4 repos, 700 traces | 13.6% on SWE-bench |
| SWE-smith (Yang 2025) | 100 repos, 700 traces | 19.0% on SWE-bench |
| InternBootcamp (2025) | 8 task types | Training collapsed |
| InternBootcamp (2025) | 512 task types | Stable, transfer improved continuously |
| RACES (Xiang 2026) | 50 composed environments | Same transfer as 300 standalone |
| Endless Terminals (2026) | 3,255 procedural tasks | Qwen2.5-7B: 10.7% → 53.3% on own eval |

**Calibration**: hundreds = narrow regime; tens of thousands = genuine invariance.
The curve is sublinear but not saturating at current scales.

---

## Environment Diversity vs Trace Volume

These are independent axes. A dataset with 50,000 traces from 5 environments is
a narrow dataset. A dataset with 700 traces from 100 environments produces broader
capability (SWE-smith). Budget both separately.

The Super-NaturalInstructions finding generalizes: adding more examples of the
same task stops helping after ~64 examples; adding more distinct tasks keeps
helping indefinitely.

---

## Domain Randomization

When training in simulation, randomize hidden environment settings to force
adaptive rather than memorized behavior.

**Mechanism**: if a setting the model cannot observe changes every episode, the
model cannot hard-code a response. It must infer the current setting from
observations and adapt mid-episode.

**Evidence of environment probing** (OpenAI ADR 2019): the trained policy
exhibited deliberate exploratory motions at episode start. Its memory could
predict unobserved block size ~80% of the time after a few seconds — it had
learned to probe and identify its own environment.

**Compute cost**: domain randomization makes optimization harder (wider
distributions = more variance in returns). Budget for:
- ~2-3× baseline compute for moderate randomization (Dactyl 2018)
- ~10× for aggressive automatic randomization (ADR 2019)
- ~33× total training experience in the robotics case

**ADR mechanism** (Automatic Domain Randomization):
1. Each parameter has uniform distribution [a, b]
2. When policy performance exceeds threshold τ → expand boundaries by Δ
3. When performance drops below lower threshold → contract boundaries
4. This creates an automatic difficulty curriculum over randomization breadth

---

## Procedural Generation Patterns

Procedural generators must produce *valid and meaningfully diverse*
configurations, not just surface-level noise.

**What matters in the generator:**
- Distributional breadth (covers edge cases in dynamics, layout, reward)
- Validity (generated environments are solvable and well-formed)
- Orthogonality (variations are independent, not correlated)

**What doesn't matter as much:**
- Total task space size alone (XLand had ~10^37 possible games; removing the
  adaptive picker still cost ~50-65% of performance)
- Fancy curriculum algorithms over random — Kinetix showed random generation
  at 1M levels > curated 10K levels; minimax found curriculum methods barely
  beat plain randomization in some task spaces

**Priority**: fix what the generator can produce and across what difficulty
range FIRST. Only then optimize the sampling algorithm.

---

## Open-Ended Learning Architecture

The XLand/AdA line of work shows that combining massive task diversity with
population-based training produces agents that generalize zero-shot to unseen
tasks. Key architectural elements:

1. **Procedurally generated task space** (vast, parameterized)
2. **Dynamic task selection** (concentrate training at capability frontier)
3. **Population-based training** (co-adapt population and curriculum)
4. **Memory architecture** (episodic + working memory to exploit diversity)

Performance scales log-linearly with both model size and task-space diversity
(AdA 2023). In-context learning is the mechanism by which environment diversity
converts to generalization at test time.

---

## Compositional Environment Building

RACES (2026) demonstrates that composable environments achieve more transfer
per environment than standalone ones:
- 50 composed environments = same transfer as 300 standalone
- Composition operators: SEQUENTIAL, PARALLEL, SORT, SELECT
- Key insight: when output type of one env matches input type of another, they
  can be automatically fused into a new verifiable environment

This enables recursive scaling: building new tasks from verified primitives.
The caveat: deep composition chains need intermediate signal (reward shaping
or adaptive difficulty) to produce learning before the final outcome.

---

## Cross-Domain Transfer from Diversity

Training on diverse environments produces transfer even to structurally
different domains:
- 363 office-work tasks (zero SWE content) → +5.8pp on SWE-Bench Pro
  (Ritchie et al. 2026). The transferred capability was "goal-directed
  execution" — selecting goals, constructing state, maintaining fidelity,
  verifying completion.
- Logic puzzle CoT warmup → MATH 55.6→77.4 (Shrestha 2026). What transfers
  is reasoning *behavior*, not topic knowledge.

This means a training environment in a distant domain can build skills your
target needs, if it forces the same control structure (decomposition,
constraint tracking, verification).
