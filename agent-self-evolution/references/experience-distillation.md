*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

# Experience Distillation

How agents extract reusable knowledge from what they've done — both successes and failures.

---

## Strategy Summaries (GAIA Pattern)

The core idea: after a successful trajectory, an LLM reflects on the process and produces a structured note capturing the method used, pitfalls encountered, and key steps. This note is vectorized and stored in a knowledge base. On future similar tasks, semantic search retrieves the most relevant historical notes and injects them as examples into the system prompt.

The GAIA experiment demonstrates this learning-application loop in practice. In learning mode, every successful task completion triggers automatic capture of the full action trajectory, followed by LLM reflection to generate a structured experience summary. The summary records not just the answer but the decision-making process — which tools were used in which order, where the approach diverged from the obvious path, what the key insight was. In apply-experience mode, the agent queries the experience knowledge base before starting a new task, retrieving the closest historical cases and using them to guide its approach.

The result is a positive feedback loop: the more tasks the agent solves, the richer its experience base, and the more efficiently it solves future tasks.

### Transferability Criteria

Not every trajectory deserves to become experience. The criterion is transferability: will the lesson from this task carry over to similar tasks in the future?

**Deserves to become experience:**
- A method that worked for a class of problems (not just one specific input)
- A pitfall that's likely to recur in similar contexts
- A tool sequence that's more efficient than the obvious approach
- A domain rule that applies across multiple tasks

**Does not deserve to become experience:**
- A fix valid only for one specific input with no generalizable lesson
- A workaround for a transient environment state (a server was down, a file was temporarily missing)
- A solution that depended on information that won't be available in future tasks

Applying the transferability gate before storage keeps the experience base signal-rich. Without it, the base fills with one-off fixes that add retrieval noise without improving future performance.

---

## Workflow Recording and Replay

Workflow recording solves a specific inefficiency: many repetitive tasks (sending a report email, querying a particular website, filling out a form) change their parameters each time but keep the same core flow. Making the agent rediscover that flow from scratch every time — burning an expensive multimodal LLM on "observe-think-act" for steps it's already solved — is wasteful.

### The Recording Phase

On first execution, the agent completes the task through full LLM reasoning. As it executes, the system records each action as a structured step: action type, target element identifier (e.g., XPath for browser automation), action parameters, and post-execution verification information (did the page URL change? did the expected element appear?). After success, the LLM generates a semantic label and description for the workflow, and the step sequence is stored as a parameterized template.

Parameterization is the key: instead of recording "enter test@example.com in the recipient field," the template records "enter `{{email}}` in the recipient field." On replay, a lightweight LLM call extracts the actual parameter values from the current task instructions without requiring full visual reasoning.

### The Replay Phase

When a new task arrives, the system checks for a matching workflow using semantic similarity and key element checks. If a match is found, it executes the steps directly — checking each verification predicate against the live environment before acting.

**State machine with verification predicates.** The robust implementation compiles a successful action sequence into a small state machine where each state carries a verification predicate — a condition that must hold on the current, real environment before the next action executes. During replay: check the predicate, then act. If a predicate fails or an action errors out, control returns to the full agent to redo the task, and the fresh trajectory is compiled into a new workflow.

Because replay requires zero model calls, repeat tasks that hit the workflow cache run significantly faster (measured at 8.5–13x in controlled experiments).

### The Pre-Storage Verification Gate

Before a compiled workflow enters the library, reset the environment and replay the workflow from scratch, using an evaluator to confirm the task was actually completed. This gate blocks workflows that execute all their steps but never accomplish the task — the whole flow runs, the save button gets clicked, but one field was empty throughout. Without this gate, faulty workflows accumulate and the library degrades.

The principle: procedural memory needs a verification gate, or the self-improvement loop decays.

### Fallback and Continuous Improvement

When a workflow fails during replay (element not found, predicate fails), the system marks it as potentially outdated and falls back to full agent reasoning. The fresh trajectory becomes the new workflow, replacing the old one. This handles environment changes — UI redesigns, API updates — without requiring manual intervention.

---

## Failure Reflection (Reflexion Pattern)

Strategy summaries and workflow recording mine successful trajectories. Failures carry different and often more information: a failure definitively rules out a path, while a success is merely one viable path among many.

### The Reflexion Mechanism

After a task fails, the agent reflects on the cause in natural language — not a scalar reward, but a full post-mortem: "at step three I should have verified identity first, not submitted the form directly." This reflection is stored in episodic memory. On the next attempt at a similar task, the reflections are read back as context, and the same mistake is not repeated.

No model parameters are updated. Reflexion is the canonical example of evolution without weight changes. A natural-language reflection carries far more information than a scalar reward — the same failure produces a rich, interpretable lesson rather than a single bit.

### Two Forms of Failure Experience

**Error pattern libraries**: record which method fails under which circumstances and what the failure signal looks like. "Attempting to cancel a subscription via the phone channel returns a 'no authority' error; the web portal is the correct channel." This pattern can be retrieved when a similar task is attempted.

**Negative rules**: explicit prohibitions derived from failure cases. "Never cancel subscriptions with this carrier by phone." These rules can be stored in the knowledge base for retrieval, or written directly into the system prompt as behavioral constraints (see `references/prompt-evolution.md`).

### What Makes a Good Failure Reflection

A useful reflection is specific enough to prevent the exact mistake but general enough to apply to similar situations. "I failed" is not a reflection. "I submitted the form before verifying the account number, which caused the transaction to fail — always verify account number before any financial transaction" is a reflection that generalizes.

---

## Transferability Criteria Summary

| Experience Type | Store? | Rationale |
|---|---|---|
| Method that worked for a class of problems | Yes | Generalizes to future similar tasks |
| Pitfall likely to recur in similar contexts | Yes | Prevents repeated failures |
| Efficient tool sequence | Yes | Saves future inference cost |
| Domain rule applicable across tasks | Yes | Factual knowledge entry |
| Fix valid only for one specific input | No | No generalization value |
| Workaround for transient environment state | No | Won't apply in future |
| Solution dependent on unavailable future information | No | Can't be retrieved usefully |
