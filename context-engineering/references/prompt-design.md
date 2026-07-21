# Prompt Design

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## Process-Driven vs Rule-Stacking

*Why this is non-obvious and agent-specific: Human-written documentation
tolerates contradiction because a human reader resolves ambiguity with
judgment. An agent has no such judgment — it executes rules literally and
in parallel, so two rules that conflict produce undefined behavior. The
failure mode is invisible: the agent appears to follow instructions while
silently skipping or misapplying the ones that conflict.*

Rules accumulate over time. Each new edge case produces a new rule. After
dozens of iterations, the rule list contains contradictions the author
never intended — rule 7 says "always confirm before deletion," rule 12
says "skip confirmation for temporary files," and the agent must decide
what "temporary" means in a context the author didn't anticipate.

A process-driven prompt replaces the rule list with a sequence: "First
verify the file type. If temporary, proceed. If not, request
confirmation." The sequence makes the contradiction impossible because
each step's preconditions are explicit. The agent cannot reach step 3
without completing step 2.

**Restructuring heuristic.** When a rule list exceeds five to seven
items, look for the underlying process. Most rule lists are implicit
processes with the sequencing stripped out. Restore the sequencing and
the contradictions often resolve themselves.

**Ablation as the test.** Remove one section of the process prompt and
run the agent on a representative task set. If success rate drops, the
section is load-bearing. If it doesn't, the section is dead weight. This
is the only reliable way to know whether a prompt section is doing work.

---

## Structured Prompts

*Why this is non-obvious and agent-specific: In a chat interface, a human
reader uses visual layout to parse sections. The model has no visual
rendering — it processes a flat token sequence. Structure works because
the model has learned, from training data, that certain delimiter patterns
(XML tags, markdown headers, fenced blocks) signal semantic boundaries.
This learned association makes structure a genuine semantic tool, not just
cosmetic organization.*

Section headers and delimiter patterns tell the model where one concern
ends and another begins. In a tool-calling agent, the system prompt must
simultaneously define persona, behavioral constraints, tool usage policy,
and output format requirements. Without structure, these concerns bleed
into each other and the model applies them inconsistently.

**XML-style delimiters** (e.g., `<constraints>...</constraints>`) create
hard boundaries that the model treats as scope markers. Content inside a
`<constraints>` block is processed as a constraint, not as a suggestion.
The same sentence outside the block may be treated differently.

**Markdown headers** create softer boundaries — useful for organizing
long prompts into readable sections, but less reliable as semantic scope
markers than explicit delimiters. For behavioral constraints and tool
policies, prefer explicit delimiters.

**Consistent formatting across turns.** If the system prompt uses XML
delimiters, tool results should also use XML delimiters. Mixing delimiter
styles within a single context creates ambiguity about which conventions
apply where.

**The density trade-off.** Structured prompts are longer than flat ones.
Each delimiter is tokens. For short prompts, structure adds overhead
without benefit. The threshold is roughly when the prompt contains more
than two distinct concerns — at that point, structure pays for itself in
reliability.

---

## Few-Shot Economics

*Why this is non-obvious and agent-specific: In a single-turn chat
context, few-shot examples are a straightforward cost — more tokens, more
money. In an agent, the cost compounds: examples live in the prefix, they
consume cache capacity, and if they change (because you're tuning them),
they bust the cache for everything that follows. The decision to add
few-shot examples is an architectural commitment, not a prompt tweak.*

Few-shot examples are most valuable when:

- The output format is complex and hard to describe declaratively (nested
  JSON with conditional fields, structured reasoning traces)
- The target behavior is a style or pattern that resists verbal
  description ("write in the tone of a terse technical report")
- The model consistently misapplies a rule in zero-shot conditions, and
  an example of correct application fixes it

Few-shot examples are wasteful when:

- The behavior can be described clearly in a declarative rule
- The examples are generic (showing the model how to respond politely,
  how to format a list) — the model already knows these
- The examples change frequently — each change busts the prefix cache

**Cache-cost accounting.** If examples are static (same examples every
run), they sit in the prefix and cache well. If examples are dynamic
(selected per-task from a pool), they change the prefix on every call and
eliminate cache reuse for everything after them. Dynamic few-shot
selection is expensive; measure before committing.

**Placement.** Examples should come after the behavioral constraints and
before the task description. Placing them before constraints risks the
model treating the example's behavior as the constraint.

---

## Business-Rule Refinement

*Why this is non-obvious and agent-specific: Business rules in human
documentation are written for human readers who apply judgment. An agent
applies rules literally and exhaustively — it will find the edge case the
rule author didn't consider and either fail silently or produce an
incorrect result. The discipline of deriving rules from observed failures
(rather than anticipating failures speculatively) is the only reliable
way to build a rule set that matches the agent's actual execution
environment.*

**From failures to rules.** Each rule in the prompt should correspond to
a specific observed failure. The workflow: run the agent on a
representative task set, collect failures, identify the root cause of
each failure, write a rule that prevents that specific failure. Rules
written this way are precise and testable.

**Speculative rules are debt.** A rule added to prevent a failure that
hasn't occurred yet is a hypothesis. It consumes tokens, adds to the
entropy load, and may contradict a future rule written to handle the
actual failure when it occurs. Defer speculative rules until the failure
they're meant to prevent is observed.

**Testing rules via ablation.** Remove a rule and run the agent on the
task set that motivated it. If the failure rate on those tasks increases,
the rule is doing work. If it doesn't, the rule is either redundant
(another rule covers the case) or the failure it was meant to prevent
doesn't occur in practice.

**Rule precision.** Vague rules ("be careful with financial data") are
unenforceable — the model cannot operationalize "be careful." Precise
rules ("never return a balance figure without also returning the
as-of-date") are testable and enforceable.

---

## Entropy Control

*Why this is non-obvious and agent-specific: Software code has compilers
and linters that catch contradictions. Prompts have neither. A prompt
maintained by a team over months accumulates contradictions silently —
each contributor adds what they need, nobody removes what's no longer
needed, and the agent's behavior becomes increasingly unpredictable as the
contradictions multiply. The engineering practices that prevent this are
borrowed from software maintenance, not from writing.*

**Version control.** Treat the system prompt as source code. Store it in
version control with the same discipline as application code. Every change
should have a commit message explaining why the change was made and what
failure it addresses.

**Ownership.** Assign a named owner to the prompt. The owner is
responsible for reviewing proposed additions, running ablation tests, and
removing sections that no longer improve outcomes. Without ownership,
prompts accumulate indefinitely.

**Periodic ablation.** Schedule regular reviews where each section of the
prompt is tested for continued effectiveness. Sections that no longer
improve outcomes should be removed. The goal is a prompt where every
section is load-bearing.

**Multi-maintainer decay.** When multiple people can add to a prompt
without a review process, the prompt will drift. Common patterns: two
people add rules that contradict each other without realizing it; someone
adds a rule to fix a failure that a different rule already handles; a rule
that was added for a deprecated feature remains after the feature is
removed. The review process is the only defense.

---

## Cross-References

- Prompt injection (attacker embeds malicious instructions in data the
  agent reads) → `agent-architecture` guardrails
- Tool-definition design (how to write tool names, parameter descriptions,
  and side-effect documentation) → `agent-tool-design`
