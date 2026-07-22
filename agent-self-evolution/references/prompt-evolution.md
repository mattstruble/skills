*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

# Prompt Evolution

How agents improve their own behavioral rules through experience — without changing model weights.

---

## Karpathy's "System Prompt Learning"

Andrej Karpathy argues that current LLM training is missing an entire learning paradigm. Pre-training acquires knowledge; fine-tuning instills habitual behavior; both change model parameters. Yet much of human learning looks more like updating a system prompt — when we puzzle something out, we write it down for ourselves in explicit language: "next time I hit this kind of problem, try this method first."

LLMs, Karpathy observes, are like the protagonist of Memento — waking each time with no memory of what came before, and we haven't even given them a notebook. Reading Claude's system prompt (roughly 17,000 words), he found it packed with general problem-solving strategies distilled from edge cases: rules that exist because a specific failure revealed a gap.

Knowledge of this kind shouldn't be hand-crafted by humans — it should come from system prompt learning: the agent's own failures generating the rules that prevent future failures.

### Why System Prompt Learning Is Data-Efficient

System prompt learning and reinforcement learning both use failures to improve future behavior, but the learning algorithms differ fundamentally. RL adjusts parameters by gradient descent using a scalar reward signal. System prompt learning edits the prompt text directly using a full natural-language post-mortem.

The information bandwidth difference is significant: a scalar reward ("correct/incorrect") carries far less information than a full natural-language reflection ("you should have verified the ID before starting the refund process"). From the very same failure, system prompt learning absorbs far more than one bit. Where RL must grind through massive trial and error to move the weights, system prompt learning can learn from one or a handful of edge cases.

The learning is also fully interpretable: every rule is written out in plain text, and can be audited, amended, or deleted. As edge cases accumulate, the system prompt evolves into a detailed problem-solving handbook.

---

## Edge-Case Sharpening

Bojie Li argues the essence of system prompt learning is sharpening rule boundaries through edge cases. Most rules work fine in typical scenarios; the real challenge is the gray zone.

"Transfer to a human agent when the request exceeds your capabilities" sounds clear enough — but does a user unhappy with policy count as exceeding capabilities? What about a user demanding an exception? It is these edge cases that define what a rule actually means.

### The Gray Zone Problem

Rules are written for the typical case. Edge cases reveal where the rule's boundary is ambiguous. Each edge case failure is an opportunity to sharpen the rule: add a clarifying condition, add a negative example, or split the rule into two more precise rules.

**Example**: an agent over-transfers to human agents when encountering policy disputes, because the transfer rule ("transfer when the request exceeds your capabilities") doesn't distinguish between capability limits and policy disagreements. The fix: clarify the transfer boundary as "user explicitly requests a human agent + emergency safety situations," and add a negative rule "never transfer due to a policy dispute." The new rule is precise enough to handle the edge case without breaking the typical case.

### One-Shot vs. Batch Learning

System prompt learning can operate in two modes:

**One-shot (online)**: a single failure case generates a single rule update. Hit a failure, add a clear rule to the prompt immediately — no need to collect thousands of similar samples. This is the case-by-case mode, suited to production systems where edge cases arrive continuously.

**Batch**: collect a set of failures, analyze patterns, and generate multiple rule updates at once. More efficient for initial prompt construction, but requires a curated failure set.

---

## Coding Agent as Prompt Editor

Automating system prompt learning requires treating the system prompt as a document to be edited, not a fixed artifact. System prompts and tool descriptions are themselves files — scattered across a codebase, with structure and cross-references.

When an edge case surfaces, a coding agent can:

1. **Read and understand the existing prompt**: analyze the rule structure, identify the section relevant to the failure, understand how the existing rules interact
2. **Generate a precise diff**: identify which file, which location, what change — not a wholesale rewrite, but a targeted edit that addresses the specific failure
3. **Maintain consistency**: ensure the new rule introduces no contradiction or redundancy with existing rules

Final say stays with human experts, who review each diff and judge whether it is sound. This keeps every rule interpretable and accountable — a better fit for high-stakes settings than end-to-end automated rewriting.

The coding agent approach is online and case-by-case: it evolves the prompt as edge cases arrive in production, one failure at a time.

---

## Automated Frameworks

Three research frameworks automate prompt optimization at larger scale, each with different trade-offs.

### DSPy

Treats prompts as optimizable parameters of a program. Developers declare what goes in and what comes out for each module; the framework automatically searches for example combinations and instruction phrasing on an evaluation set. Transforms prompt engineering from manual debugging to systematic optimization.

**Trade-off**: requires a scored evaluation set to drive the search. Efficient for initial prompt construction; less suited to continuous production evolution.

### OPRO

Lets the LLM itself act as the optimizer. Using historical prompts and their scores as context, the model iteratively proposes better rewrites. Outperforms human-designed prompts on tasks like mathematical reasoning.

**Trade-off**: also requires scored task sets; the model's rewrites can produce odd phrasing that overfits the evaluation set.

### GEPA

Performs natural-language reflection on failure trajectories, evolves prompts accordingly, and maintains a Pareto frontier among multiple candidates — preserving complementary optimization directions rather than converging to a single "optimal" prompt. Outperforms GRPO fine-tuning on multiple tasks while requiring one to two orders of magnitude fewer samples.

GEPA is precisely what Karpathy's "system prompt learning" describes, and its empirical results support the information-bandwidth argument: natural-language reflection from failures produces better prompt updates than scalar-reward RL.

**Trade-off**: still requires scored task sets; end-to-end rewriting without human review.

### Choosing Between Approaches

| Dimension | Automated frameworks (DSPy/OPRO/GEPA) | Coding agent + human review |
|---|---|---|
| Mode | Offline batch against evaluation set | Online case-by-case as failures arrive |
| Human oversight | End-to-end rewriting, minimal oversight | Human reviews every diff |
| Evaluation set | Required (scored task set) | One failure case + human feedback |
| Risk of overfitting | Higher (optimizes against fixed set) | Lower (each rule tied to a real failure) |
| Best for | Initial prompt construction | Continuous production evolution |

In practice, the two approaches complement each other: batch-optimize the initial prompt with an automated framework, then let the coding-agent diff approach carry continuous evolution after launch.
