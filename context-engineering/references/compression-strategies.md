# Compression Strategies

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## Why Compression Is Needed

Context growth is not just a length problem. Two distinct degradation
mechanisms make an unmanaged trajectory harmful even before it hits the
window limit:

**Retrieval degradation.** The model's ability to locate and use
information from earlier in the context degrades as the context grows.
Information near the beginning of a long trajectory is attended to less
reliably than information near the end. A decision made in step 3 of a
50-step trajectory may be effectively invisible to the model at step 47.

**Attention diffusion.** Irrelevant content in the trajectory consumes
attention capacity. A tool result that returned 200 lines of raw file
content to answer a yes/no question leaves 199 lines of noise that the
model must attend through on every subsequent turn. The noise doesn't
disappear — it persists in the trajectory and dilutes the signal of
everything that follows.

Bojie Li argues in-context learning is essentially retrieval, not
reasoning: the model is pattern-matching against examples and prior
context rather than performing novel inference. If this premise holds,
the quality of what's in context is as important as the model's
capability — a well-curated trajectory outperforms a larger model with
a noisy one.

---

## Hierarchical Compression Mechanisms

Compression is not a single operation. A multi-level approach applies
different strategies at different granularities:

**Turn-level summarization.** After each ReAct step, replace the raw
tool result with a summary that preserves the conclusion and discards
the intermediate content. The raw result is never stored in the
trajectory; only the summary enters. This is the least lossy form of
compression because it happens before the raw content is committed.

**Segment summarization.** When a block of trajectory (several turns
covering a sub-task) is complete, replace the block with a summary of
what was accomplished, what was decided, and what remains. The individual
steps are discarded; the summary is retained.

**Rolling window with summary header.** Maintain a fixed-length window
of recent turns. When the window fills, compress the oldest turns into
a summary block prepended to the window. The model always sees recent
turns in full and older context in summarized form.

**Hierarchical summary.** For very long trajectories, summaries of
summaries. The oldest content is summarized at the highest level of
abstraction; more recent content is summarized at finer granularity.
The model sees a pyramid: abstract history at the top, detailed recent
context at the bottom.

---

## Retention-Priority Design

Compression is lossy. The retention-priority list determines what
survives compression and what is discarded. In order of preservation
priority:

1. **Architectural decisions and constraints.** Decisions that constrain
   all subsequent steps — "we are using approach X, not Y," "the output
   must be in format Z." These must never be summarized away; losing them
   causes the agent to contradict its own prior decisions.

2. **Modified files and change records.** A complete record of what was
   changed, where, and why. Partial records produce agents that re-do
   work or produce conflicting changes.

3. **Verification status.** Pass/fail results for each completed step.
   Losing verification status causes the agent to re-verify work already
   verified, or worse, to proceed past a failed verification it no longer
   remembers.

4. **Unresolved TODOs.** Items explicitly deferred for later handling.
   If these are lost in compression, they are silently dropped — the
   agent has no way to know they existed.

5. **Tool output.** Raw tool results are the most compressible content.
   The conclusion is retained; the intermediate content is discarded.
   Exception: tool output that contains identifiers (see below).

**Identifier preservation.** UUIDs, hashes, URLs, filenames, and other
exact-match identifiers must be preserved verbatim. A summarized
identifier is a broken reference — the agent will attempt to use it and
fail. When compressing tool output, extract and preserve all identifiers
before discarding the surrounding content.

---

## Task-Type-Coupled Strategies

The optimal compression strategy depends on the task type:

**Retrieval tasks** (find information, answer questions from a corpus).
Preserve breadth: retain references to all sources consulted, even if
their content is summarized. The agent may need to return to a source
it previously visited. Losing the reference loses the ability to
retrieve.

**Analysis tasks** (synthesize findings, identify patterns, produce a
report). Preserve depth: retain the reasoning chain that produced each
conclusion. Conclusions without their supporting reasoning are
unverifiable and may be wrong in ways the agent cannot detect.

**Creative tasks** (generate content, write code, design solutions).
Preserve triggers: retain the constraints, examples, and feedback that
shaped the direction. Creative work is highly sensitive to its initial
conditions; losing the triggers produces drift toward generic output.

**Multi-step execution tasks** (implement a feature, run a deployment).
Apply the full retention-priority list. These tasks produce the most
diverse content — decisions, file changes, verification results, deferred
items — and benefit most from explicit prioritization.

---

## Isolation Mechanics

Isolation is the alternative to compression: prevent bulky content from
entering the main context in the first place, rather than compressing it
after the fact.

**Sub-agent delegation.** The main agent delegates a bounded sub-task to
a sub-agent. The sub-agent executes the task, accumulates whatever
intermediate context it needs, and returns only the conclusion to the
main agent. The intermediate context is discarded with the sub-agent's
session.

**Trade-off: task self-containment.** The sub-agent does not see the main
agent's context. The task description passed to the sub-agent must be
fully self-contained — it cannot rely on context the main agent has but
didn't include. This requires the main agent to be explicit about what
the sub-agent needs to know, which is itself a useful discipline.

**When isolation beats compression.** Isolation is preferable when the
intermediate content is large relative to the conclusion, when the
sub-task is well-bounded (clear inputs and outputs), and when the
conclusion can be expressed concisely. Compression is preferable when
the intermediate content is needed for later steps — isolation discards
it permanently.

**Isolation failure modes.** The most common failure: the main agent
delegates a task with an underspecified description, the sub-agent
produces a result that doesn't match the main agent's implicit
expectations, and the main agent must re-delegate with a more complete
description. The cost of this failure is two sub-agent calls instead of
one. Invest in task description quality upfront.

---

## Status-Bar Composition Patterns

The agent status bar converts implicit state into explicit structured
information appended to the trajectory. Without it, the agent must
infer its own progress from the trajectory — an unreliable process that
degrades as the trajectory grows.

**What to include:**

- **Step count and budget.** Current step number and maximum steps
  remaining. Prevents the agent from running indefinitely and gives it
  a sense of urgency as the budget shrinks.
- **Task progress.** A structured representation of completed sub-tasks
  and remaining sub-tasks. Not a narrative — a list or table that the
  model can parse reliably.
- **Tool budget.** If certain tools have usage limits (API rate limits,
  cost caps), the remaining budget for each. The agent cannot manage
  what it cannot see.
- **Current state.** The agent's current position in the task — what
  phase it's in, what it's working on, what it's waiting for.

**Update frequency.** Update the status bar at the end of each turn,
not mid-turn. Mid-turn updates create multiple versions of the status
bar in the trajectory, which confuses the model about which is current.

**Placement for cache friendliness.** The status bar changes every turn
— it is volatile data. Apply §2's volatile-data-last principle: append
the status bar at the end of each turn's content, after the tool results
and before the next turn begins. This minimizes the cache invalidation
impact to the tail of the trajectory.

**Format.** Structured over narrative. A table or key-value block that
the model can parse without ambiguity is more reliable than a sentence
describing the same information. The model should be able to extract
"steps remaining: 7" from the status bar without interpreting prose.
