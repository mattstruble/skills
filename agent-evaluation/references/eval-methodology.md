# Eval Methodology

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## The Improvement Loop

Evaluation is not a one-time gate — it is a continuous iteration engine:

```
Observe (run benchmark)
  → Hypothesize (what's failing and why)
    → Experiment (change one thing)
      → Validate (re-run, check signal)
        → New Understanding
          → New Hypothesis → repeat
```

**Key principle**: when agent performance drops, check the evaluation system
first, then the agent. Eval environment bugs — stale test data, broken user
simulator, flawed rubric — are common sources of false regression signals.
A team with good eval infrastructure can identify a regression, hypothesize
root cause, run a targeted ablation, validate the fix, and deploy in hours
rather than weeks.

---

## Three-Layer Hypothesis Framework

Before implementing a fix, push to the deepest testable hypothesis:

| Layer | Example |
|---|---|
| **Surface** (symptom) | "The model gets confused on long contexts" |
| **Mid** (mechanism) | "The retrieval step returns irrelevant chunks that dilute the answer" |
| **Deep** (root cause) | "The chunking strategy severs key context from its source" |

A fix at the surface layer treats the symptom; a fix at the deep layer
eliminates the cause. Always push to the deepest testable hypothesis before
implementing. If you can't test the deep hypothesis directly, design an
experiment that isolates the mechanism first.

---

## Model Selection Framework

Model selection is a multi-dimensional comparison, not a single-score
ranking. Evaluate across four axes:

### 1. Throughput and Latency

- **TTFT** (time to first token): matters for interactive agents where the
  user waits for the first word
- **Thinking latency**: reasoning models add a planning phase before output
- **p95 tail latency**: the worst-case experience for users; often 3–5× the
  median

Multi-round agent latency compounds: a 20-round task that is 2s slower per
round adds 40s end-to-end. Output speed is a first-class requirement for
interactive agents.

### 2. Cost

Context accumulation makes agent tasks disproportionately expensive. A
3-round conversation costs more than 3× a single-round call because each
round re-sends the growing trajectory. Model cost must be evaluated on
realistic trajectory lengths, not single-call pricing.

**KV Cache savings**: shared prefixes (system prompt, tool definitions) can
be cached across calls, yielding 30–60% cost reduction on long shared
prefixes. Factor this into cost projections.

### 3. Performance

Match the metric to the deployment context:

| Metric | Use when |
|---|---|
| Pass@1 | Daily operations — typical single-attempt performance |
| Pass^k | Critical paths — must succeed reliably every time |
| Best@k | Exploratory / research — ceiling capability matters |

### 4. Rate Limits and Reliability

Production agents hit rate limits under load. Evaluate: requests-per-minute
ceiling, burst behavior, and the provider's reliability SLA. A model that
is 5% more capable but rate-limited at 10 RPM may be worse in production
than a slightly weaker model with higher throughput.

---

## Benchmark Report Reading

Aggregate scores hide structural weaknesses. Cross-analyze per-task results
with a capability tag matrix to find where a model actually breaks down.

A model at 80% overall might be 95% on simple single-hop tasks and 40% on
multi-hop reasoning — which tells a very different story than a uniform 80%.
The aggregate score is a starting point; the per-capability breakdown is the
diagnostic.

**Practical workflow:**

1. Tag each eval case with capability dimensions (e.g., multi-hop, tool
   selection, long context, arithmetic)
2. Compute per-tag success rates
3. Identify the capability dimensions where performance is lowest
4. Hypothesize whether the weakness is model-side or harness-side (run the
   model-swap experiment on the weak-tag subset)

**Cross-model comparison**: when comparing two models, don't just compare
overall scores. Compare per-tag profiles. A model that is weaker overall but
stronger on your specific task distribution may be the better choice.

---

## Evaluation-Driven Continuous Iteration

The eval system is the enabler of fast iteration, not just a quality gate.
Teams with strong eval infrastructure:

- Detect regressions within hours of a change, not days
- Run targeted ablations to isolate the cause of a regression
- Validate fixes before deploying, not after
- Build a growing library of regression tests from production failures

The improvement loop above is only as fast as the eval infrastructure
supports. Invest in eval infrastructure proportional to the iteration rate
you need.
