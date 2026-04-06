---
name: brainstorm
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

Before asking questions, do a light read of the project — structure, docs, recent
commits. Enough to avoid asking questions the codebase already answers. Heavier
exploration happens on-demand as the conversation surfaces specific areas worth
investigating.

### 2. Question and Discuss

Grill the user. Understand purpose, constraints, success criteria. Prefer
multiple-choice questions when possible, but open-ended is fine. Keep going until
you've walked every relevant branch of the decision tree and reached shared
understanding.

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

Present these to the user as a genuine attempt to find blind spots. They either
dig deeper (extending the session) or confirm satisfaction (moving to summary).

### 4. Summarize and Hand Off

Present a concise summary of the decisions made. Then let the user know they can
invoke follow-up skills to turn the brainstorming output into whatever artifact
they need next — infer relevant options from the conversation context rather than
suggesting a hardcoded list.
