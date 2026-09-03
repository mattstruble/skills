---
name: "brainstorm"
summary: "Interview-driven design through relentless questioning before implementation"
type: "process"
description: "You MUST use this before any creative work — creating features, building components, adding functionality, or modifying behavior. Also trigger when the user mentions brainstorming, wants to think through a design, stress-test a plan, or says 'grill me'. NOT for debugging, code review, writing tests, committing, or mechanical refactors (renaming, version bumps, config changes)."
---

# Brainstorm

Turn ideas into fully formed designs through relentless, opinionated questioning.
Interview the user about every aspect of their idea, walking down each branch of
the decision tree and resolving dependencies one by one. For each question, lead
with your recommended answer.

Ask questions one at a time.

If a question can be answered by exploring the codebase, explore the codebase
instead of asking.

<HARD-GATE>
Do NOT invoke any implementation skill, write any code, scaffold any project, or
take any implementation action until the user says the brainstorming session is
done. This applies regardless of perceived simplicity — jumping to code before
understanding the problem leads to wrong assumptions and wasted work.
</HARD-GATE>

## No Topic Is Too Simple

Every topic gets questioned. A todo list, a single-function utility, a config
change — all of them. "Simple" topics are where unexamined assumptions cause the
most damage, because nobody thinks to question them. The questioning can be brief
for truly simple topics, but you still question before acting.

## How You Work

- **Always recommend first.** State your recommendation and reasoning, then ask
  the question. This ordering matters — the user reads your position, then responds
  to it. "I'd recommend X because Y. What's your situation with Z?" is the pattern.
  This is faster than neutral "what do you think?" and produces better results
  because you bring your own informed perspective.
- **One question at a time.** Each message contains exactly one question. Don't
  ask multiple questions, bullet lists of follow-ups, or restate the same question
  in different words at the end.
- **Walk every branch.** Follow each line of the decision tree to resolution before
  moving on. Don't leave decisions half-explored.
- **Surface alternatives organically.** When multiple valid approaches exist, present
  them as part of the natural conversation flow rather than a formal checkpoint.
  Compare trade-offs and recommend one.
- **YAGNI ruthlessly.** Challenge features that aren't clearly needed. Remove
  unnecessary complexity from all designs.
- **80/20 when YAGNI fails.** Sometimes you can't say no — a stakeholder has
  already committed, a business requirement is non-negotiable, or the team has
  decided. That's okay. When a feature survives the YAGNI challenge, the next
  question becomes: what's the version that delivers 80% of the value with 20%
  of the complexity? Strip it to the core need. The goal shifts from elimination
  to simplification.
- **Flag scope early.** If the request covers multiple independent subsystems, flag
  it immediately rather than refining details of something that needs decomposition
  first. Help break it into pieces, then brainstorm the first piece.

## Phases

These are a loose guide, not a rigid checklist. The conversation naturally loops
between them as new information surfaces.

### 1. Quick Context Scan

Before asking questions, orient yourself from two sources:

**Wiki traversal** — If a knowledge base is configured (check `AGENTS.md` for
`Knowledge base: <path>`), traverse it using the reading protocol from the
`knowledge-base` skill: `INDEX.md` → relevant MOC → 1–5 atomic notes most
relevant to the domain being discussed. Also check `plans/` for any active map
if the work looks like part of an ongoing effort. Don't narrate the read — absorb
it and ask questions as if you already knew the context.

**Codebase scan** — Do a light read of the project structure, docs, and recent
commits. Enough to avoid asking questions the codebase already answers. Heavier
exploration happens on-demand as the conversation surfaces specific areas worth
investigating.

### 2. Question and Discuss

Grill the user. Understand purpose, constraints, success criteria. Prefer
multiple-choice questions when possible, but open-ended is fine. Keep going until
you've walked every relevant branch of the decision tree and reached shared
understanding.

**Scratch glossary** — As the conversation resolves domain terms, entity
definitions, and design decisions, accumulate them as a running mental model:
`term: definition`. No wiki formatting, no file writes — just a lightweight list
you hold in working memory. This prevents re-explanation as terms compound
within the session and gives you the material for the stress-test and handoff.

**In existing codebases:**
- Explore current structure before proposing changes. Follow existing patterns.
- Where existing code has problems that affect the work, include targeted
  improvements in the discussion — don't propose unrelated refactoring.

**For new components:**
- Break the system into units with one clear purpose each, communicating through
  well-defined interfaces.
- For each unit: what does it do, how do you use it, what does it depend on?
- Favor small, well-bounded units — they're easier to reason about, test, and
  implement correctly.

### 3. Stress-Test Before Converging

Before wrapping up, actively challenge your own conclusions:
- What assumptions did we make that we didn't examine?
- What alternative approaches didn't we explore?
- Are there trade-offs we accepted implicitly?
- Are there terms we resolved in the scratch glossary whose definitions we
  assumed but never fully pressure-tested?

Be honest about your own ideas — call your own bluff, audit the beliefs you started
with, and check that novelty isn't masquerading as depth. See `references/idea-judgment.md`.

Present these to the user as a genuine attempt to find blind spots. They either
dig deeper (extending the session) or confirm satisfaction (moving to summary).

### 4. Summarize and Hand Off

Present a concise summary of the decisions made. If the scratch glossary is
non-empty, include it as a **Shared language** section — a flat list of
`term: definition` pairs. This gives follow-on agents and future sessions the
vocabulary established here without requiring re-explanation.

**Glossary flush** — After presenting the shared language list, classify each
term into one of two buckets and present the proposed split to the user for
confirmation before writing anything:

- **Project-local** — terms that only matter inside this repo (implementation
  specifics, local naming conventions, project-scoped entities): persist with
  `bd remember "term: definition"`, surfaced next session by `bd prime`.
- **Cross-project** — decisions, domain concepts, patterns, and entities that
  future sessions in other repos would benefit from knowing: persist as wiki
  writes following the knowledge-base skill's write protocol.

Present the split like this:

> **Glossary flush — proposed split:**
>
> `bd remember` (project-local):
> - `term: definition`
>
> Wiki (cross-project):
> - `term: definition` → suggested note path/type
>
> Does this split look right?

Wait for confirmation. After the user confirms (or adjusts), execute the
writes. For wiki writes, load and follow the `knowledge-base` skill's write
protocol — don't duplicate it here. The boundary rule from that skill applies:
if the insight only matters inside this repo, `bd remember`; if a future session
in a different repo would benefit, write to the wiki.

If the glossary is empty or contains only ephemeral session chatter, skip the
flush entirely.

**Ticket-type tagging** — When recommending beads tasks at handoff (or handing
off to the planner skill to create them), prefix each ticket title with a
session-type tag. This tells the next session *how* to work the ticket, not
just what to work on:

| Tag | When to use |
|---|---|
| `[research]` | Unknown facts must be established before the work can proceed. AFK-capable. |
| `[brainstorming]` | A design decision requires a live grilling session. HITL. |
| `[prototype]` | A question is best answered by building something cheap and throwaway. HITL. |
| `[human-task]` | Only a human can do this: provisioning, credentials, external approvals. HITL. |
| *(no tag)* | Standard implementation ticket — scope is clear and the agent can execute. |

Then let the user know they can invoke follow-up skills to turn the brainstorming
output into whatever artifact they need next — infer relevant options from the
conversation context rather than suggesting a hardcoded list.
