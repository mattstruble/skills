# Eval Infrastructure

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## Environment Components

A complete eval environment has five parts:

| Component | What it is | Key design concern |
|---|---|---|
| **Dataset** | The tasks to evaluate on | Static or dynamically generated; contamination-resistant |
| **Environment State** | The world the agent operates in (DB, filesystem, APIs) | Reproducible reset; isolated per-run |
| **Tools** | The tools available during evaluation | Must match production exactly — eval tool drift invalidates results |
| **Rubric** | How to judge success (assertions, rubric items, verifier functions) | Deterministic where possible; calibrated when LLM-based |
| **Interaction Protocol** | How the agent communicates with the environment | Single-turn, multi-turn, or async — must match production interaction model |

Tools in the eval environment must match production. A tool that behaves
differently in eval than in production (different error handling, different
return format, different latency) produces eval scores that don't transfer.

---

## Observability

Build on distributed tracing (OpenTelemetry / OpenInference):

- One task = one trace
- Each LLM call = a span
- Each tool call = a span

This gives you: problem diagnosis at the span level, continuous cost tracking
per-task, and latency profiling across the full execution path.

**Failed-trace → test-case pipeline:**

Production failures become eval coverage automatically:

1. Filter failed production traces
2. Anonymize (strip PII, customer identifiers)
3. Distill into new eval cases and regression tests

This pipeline closes the authenticity gap: the hardest cases in production
become the hardest cases in eval, without manual curation.

**Challenges:**
- Data volume vs privacy: high-volume production tracing generates large
  datasets with sensitive data; anonymization pipelines add latency and
  complexity
- Causal attribution in multi-step tasks: which span caused the failure?
  Span-level error signals are necessary but not always sufficient
- Multi-agent trace correlation: when multiple agents collaborate, traces
  must be correlated across agent boundaries to reconstruct the full causal
  chain

---

## Internal Eval Infrastructure

### Ablation Infrastructure

Every major feature should be independently disableable. Regularly verify
that each feature contributes to the score. If disabling a feature doesn't
change the score, it is dead weight — remove it.

Ablation discipline prevents feature accumulation: teams add features that
improve scores at the time, but never verify they still contribute after
subsequent changes. Regular ablation sweeps keep the system lean.

### A/B Testing

Use multi-armed comparisons, not binary A/B:

- **Mechanism metrics**: tool call accuracy, retrieval precision — measure
  whether the change does what you think it does
- **Target metrics**: task success rate — measure whether the change
  achieves the goal
- **Guardrail metrics**: safety violation rate, cost ceiling — measure
  whether the change breaks constraints

Distinguish mechanism from target metrics. A change that improves tool call
accuracy but doesn't improve task success rate is fixing the wrong thing.
A change that improves task success but violates a guardrail metric is not
deployable.

### Feature Flag System

Two layers:

- **Compile-time flags**: remove code entirely; used for ablation studies
  where you want to measure the true cost of a feature
- **Runtime flags**: server configuration; used for gradual rollouts and
  canary deployments

Compile-time flags give cleaner ablation signals because they eliminate dead
code paths. Runtime flags are necessary for production rollouts where you
can't redeploy for every experiment.

### Prompt Sensitivity

Prompts are code. Treat them accordingly:

- Deterministically renderable: given the same inputs, the prompt renders
  identically every time
- Versioned snapshots: every prompt change is tracked
- Regression tested: every prompt change triggers a benchmark run

A "minor wording tweak" can shift agent behavior unpredictably. The only
way to know is to test it. Teams that don't regression-test prompt changes
discover the impact in production.

---

## Simulation Environments

**Fidelity spectrum:**

| Level | Environment | Use when |
|---|---|---|
| 1 | Mock API | Fast iteration, unit-level eval |
| 2 | MCP sandbox | Integration-level eval with controlled state |
| 3 | Full simulator | System-level eval with realistic complexity |
| 4 | Real environment | Production validation; expensive and slow |

Start at the lowest fidelity that catches the failure mode you care about.
Move up the spectrum when lower-fidelity environments stop catching real
failures.

**Eval → training environment reuse:**

A well-designed eval environment can become a training environment with
minimal adaptation — validators become reward functions. However, training
demands differ from eval demands:

- **Reset semantics**: training requires millions of reliable resets; eval
  requires hundreds
- **Throughput**: training requires orders-of-magnitude higher throughput
  than eval
- **Isolation**: the eval task set must be strictly isolated from training
  data to prevent contamination

**Domain randomization:**

Moderate randomization (varying task parameters, surface forms, context)
improves generalization. Excessive randomization makes tasks unsolvable and
produces noisy training signals. Tune randomization to the task's realism
needs — the goal is coverage of the real distribution, not maximum entropy.

**Scope note**: using eval environments for RL post-training is out of scope
for this skill. That territory belongs to agent post-training (Ch7).
