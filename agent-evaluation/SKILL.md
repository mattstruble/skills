---
name: agent-evaluation
summary: Designing evaluation systems, rubrics, and metrics for autonomous agents
type: design
description: You MUST consult this skill when building evaluation systems for autonomous agents, designing rubrics for LLM-as-Judge, choosing evaluation paradigms (tool-calling verification vs user-simulator vs LLM-as-Judge), selecting metrics (Pass@k vs Pass^k), building eval datasets, or determining statistical significance of results. Also trigger when agent scores fluctuate between runs, a stronger model doesn't improve scores, or evaluation results don't match production behavior. NOT for testing code correctness (see test-design), evaluating skill effectiveness specifically (see skill-creator), or deciding whether/when to post-train based on eval results (→ agent-post-training; Ch6 §6.11 establishes that evaluation environments become training environments — the decision to cross that bridge lives in agent-post-training).
---

# Agent Evaluation

**The object of evaluation is model + harness combined, not the model alone.**

Every eval score is a joint measurement of model capability AND harness
quality. Improving either changes the score.

---

## Framing — Evaluate the System, Not Just the Model

Bojie Li argues the **model-swap experiment** is the primary diagnostic: fix
the harness, swap to a stronger model. If the score doesn't rise, the
bottleneck is the harness (prompts, tools, context strategy), not the model.
This reframe prevents the most common mistake — blaming the model when the
harness is broken.

Corollary: before spending on a better model, run the model-swap experiment.
A broken harness will waste the upgrade.

---

## Symptom Table

| Symptom | Section |
|---|---|
| Agent passes tests but fails in production | §2 — Dataset (authenticity gap) |
| Scores fluctuate wildly between runs | §5 — Statistical rigor |
| Stronger model doesn't improve scores | Framing — model-swap diagnostic |
| Agent games the metric without solving the task | §4 — Rubric design (reward hacking) |
| Can't tell if improvement is real or noise | §5 — Statistical rigor |
| Open-ended output can't be scored automatically | §4 — LLM-as-Judge |

---

## YAGNI Gate

Does this agent need formal evaluation? Formal eval pays off when:

- Tasks are diverse (>10 distinct types)
- Failures are costly (financial, safety, user trust)
- You're iterating on harness or prompt
- You need to compare models or configurations

Otherwise: start with manual review + lightweight assertions. Don't build
infrastructure you won't run regularly.

---

## §1 Evaluation Paradigm

Choose by output type. Many tasks need a combination.

**Tool-calling verification** (rule-based):
- Agent calls tools; verification checks observable state change (DB row
  inserted, file modified, API called with correct params)
- Verdict: deterministic pass/fail from code assertions
- When: tasks with verifiable outcomes — CRUD operations, workflow
  completion, state transitions
- Environment hierarchy: `SingleTurnEnv → ToolEnv → StatefulToolEnv → SandboxEnv`

**User simulator** (LLM plays the user):
- Simulated user with progressive information disclosure — reveals info
  gradually, not all at once
- Dual verification: DB state checks + dialogue content analysis + process
  compliance
- When: conversational agents, customer service, advisory roles
- Key design: the user-simulator LLM must follow a persona script and reveal
  information only when the agent prompts correctly

**LLM-as-Judge** (scores open-ended output):
- Judge LLM evaluates agent output against a rubric
- When: creative output, open-ended tasks, subjective quality assessment
- Requires calibration against human annotations before trusting at scale (see §4)

**Selection heuristic:**

| Output type | Paradigm |
|---|---|
| Deterministic verifiable outcome | Tool-calling verification |
| Dialogue quality matters | User simulator |
| Open-ended / creative | LLM-as-Judge |

---

## §2 Dataset Design

Five challenges, each requiring a deliberate choice:

1. **Clarity vs openness** — tasks must be clear enough for reproducibility
   but open enough for creative solutions. Ensure answer uniqueness: if
   multiple valid approaches exist, the verifier must accept all of them.

2. **Authenticity vs controllability** — real tasks have noise and ambiguity;
   controlled tasks are reproducible. Bridge: parametric generation from real
   task templates (vary names, numbers, context while keeping structure).

3. **Diversity vs systematization** — cover typical scenarios AND edge cases,
   organized by capability dimension so results diagnose specific weaknesses,
   not just an aggregate score.

4. **Cost vs coverage** — complex agent tasks take minutes or hours each.
   Hierarchical complexity levels:
   - Level 1 (smoke tests): run on every change
   - Level 2 (standard tasks): run on every PR
   - Level 3 (complex multi-step): run weekly

5. **Preventing contamination** — models train on public benchmarks. Defenses:
   unique answers, dynamic parameter generation, canary GUIDs in test cases,
   temporal freshness (tasks requiring current information).

---

## §3 Metrics

**Outcome metrics:**

| Metric | Measures | Use when |
|---|---|---|
| **Pass@k** | At least one of k attempts succeeds | Capability ceiling — "can it do this at all?" |
| **Pass^k** | ALL k attempts succeed | Reliability — "will it work every time?" |
| **Best@k** | Score of best of k attempts | Open-ended tasks where quality varies |

**Process metrics:**
- Tool call correctness rate
- Path efficiency (steps taken vs optimal)
- Retrieval coverage
- Cost and latency per task

**Safety — zero-tolerance principle.** A single serious violation (data leak,
unauthorized action) vetoes the entire evaluation regardless of other scores.

**Dual coverage:** Evaluate BOTH the execution trajectory AND the final
outcome. Two failure modes that single-signal evaluation misses:
- "Said it but didn't do it" — claims success, state unchanged
- "Did it but broke something else" — state changed, but collateral damage

---

## §4 Rubric Design & LLM-as-Judge

**Four Rubric Principles** (industry practice from Scale AI):

1. **Expert Guidance** — domain expert defines what good looks like
2. **Comprehensive Coverage** — including pitfalls and failure modes, not
   just the happy path
3. **Standard Importance Weights** — Essential / Important / Optional /
   Pitfall (veto). A Pitfall item at any severity vetoes the entire score.
4. **Self-Contained** — each rubric item is independently actionable; the
   scorer needs no external context

**LLM-as-Judge design:**
- Define objectively verifiable scoring levels with concrete examples and
  edge cases
- Guard against reward hacking: if the metric can be gamed by
  length/verbosity/formatting without substance, the rubric is broken
- **Length bias defense**: penalize verbosity in rubric; bring candidates to
  similar lengths in pairwise comparisons; audit length-score correlation
- **Same-family model problem**: a model judges its own family's output
  favorably. Use heterogeneous judges (different model families)
- **Calibration**: build a human-annotated gold standard (100–200 cases).
  Measure judge agreement with humans before deploying at scale. If agreement
  is below threshold, fix the rubric before trusting results.

**Pairwise comparison** (for relative ranking): Elo/Bradley-Terry from
matchups. Mitigate position bias by evaluating each pair twice with swapped
order.

---

## §5 Statistical Rigor

**Standard error** of binomial success rate: `√(p(1-p)/n)`. At 100 cases
with 70% success → ±9 percentage points. That is your confidence interval.

**Practical principle**: when the score difference between two configurations
is smaller than the noise bandwidth, do NOT make a switching decision.

**Paired analysis** (McNemar's test): more sensitive than comparing
independent success rates because it uses per-case matches — which specific
cases flipped?

**Multiple comparisons trap**: testing 6 hypotheses at 95% confidence each
→ 26% chance of at least one false positive. Correct with Bonferroni or
control false discovery rate.

**Run multiple times** (3–5 per configuration), report mean and spread. A
single run is an anecdote, not evidence.

**Mental math sieve**: if you need > √2× improvement to clear the noise
floor, the eval set is too small.

---

## Routing Map

These are companion skills in the ai-agents family. Load the relevant one
when building that layer.

| Concern | Companion Skill |
|---|---|
| Agent architecture & orchestration | agent-architecture |
| Coding agent patterns (uses "tests pass" as completion criterion) | coding-agent-design |
| Multi-agent verification loops | multi-agent-collaboration (Loop Engineering) |
| Skill effectiveness evaluation (applies these principles to skill quality) | skill-creator |
| Code testing (unit/integration/e2e for code, not agent behavior) | test-design |
| Context strategy (affects eval scores) | context-engineering |

---

## NOT For

**Litmus**: Is the question about evaluating an autonomous agent's behavior
on tasks? → here.

- Writing unit tests or integration tests for code → `test-design`
- Evaluating whether a specific skill improves agent output → `skill-creator`'s
  eval loop (which implements these general principles for that specific case)

**Co-triggering note**: both this skill and `test-design` should fire when
someone asks "how do I evaluate whether my coding agent writes good tests?"
— `test-design` covers what good tests look like; this skill covers how to
score the agent's test-writing behavior.

---

## References

| Reference | When to read |
|---|---|
| `references/eval-methodology.md` | Improvement loop, three-layer hypothesis framework, model selection framework, cost analysis, benchmark report reading |
| `references/eval-infrastructure.md` | Environment component taxonomy, observability and tracing, ablation/A/B/feature-flag infrastructure, simulation environments and fidelity spectrum |
