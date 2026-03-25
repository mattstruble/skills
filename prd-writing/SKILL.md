---
name: prd-writing
description: "Behavioral PRD writing — co-author a product requirements document through structured interview and codebase exploration, saved as a local Markdown file. Use when user wants to write a PRD, create a product requirements document, plan a new feature, define requirements, capture expected behaviors, or scope a project. Also trigger when the user mentions \"PRD\", \"product requirements\", \"requirements doc\", or wants to define what a system should do before implementation begins."
---

# Behavioral PRD Writing

Co-author a behavioral PRD for a repository through structured interview and codebase exploration. Output is `docs/prd.md` at the repo root.

The goal is a document that captures *what the system should do* — from the outside, in plain language — without prescribing how to build it. Downstream skills and processes generate stories, epics, and feature specs from this PRD.

## Scope Model

**PRD** (per-repo) → **Capability Groups** (independently shippable) → **Behaviors** (testable statements)

## Workflow

### Step 1: Explore the codebase

Before interviewing, explore the repo. Understand what exists — code structure, existing docs, patterns, naming conventions. This grounds the interview in reality and prevents asking questions the codebase already answers.

Look for:
- Existing documentation (`README.md`, `CONTRIBUTING.md`)
- Code structure and module organization
- Any prior PRDs, specs, or design docs in `docs/`

Do NOT read or surface the contents of secrets files (`.env`, `*.key`, `credentials.*`, `secrets/`).

### Step 2: Check for an existing PRD

Check if `docs/prd.md` exists. If found, read it, briefly summarize what it covers, and ask:

"I found an existing PRD at `docs/prd.md` — it covers [brief summary]. Should I use it as a starting point, or start fresh?"

If starting from the existing PRD: use it to pre-populate interview answers and skip phases already well-covered. If starting fresh: proceed as if no PRD exists.

### Step 3: Interview the user

Ask one question at a time. Provide a recommended answer with each question — this reduces friction and anchors the conversation. Fill in concrete details from the codebase before asking; never emit a literal `[X]` placeholder to the user.

Follow this sequence loosely; skip phases already answered by the codebase or the current conversation. If an answer is ambiguous or contradicts something found in the codebase, ask a follow-up before moving on. If the user gives two consecutive non-answers on the same question, move on and mark it as an Open Question.

Do not batch questions even if the user asks you to — batching produces shallow answers that miss the nuance needed for a good PRD. If the user pushes back, explain that one question at a time produces a better document.

**Phase 1 — Problem & actors**

Understand who has the problem and what's painful.

- "Who are the primary users of this system?" *(Recommended: [infer from codebase context])*
- "What problem does this solve that isn't solved today?"
- "What's the most painful part of the current workflow?"

**Phase 2 — Scenarios**

Walk through concrete usage end-to-end.

- "Walk me through what happens when a user [does the primary action] for the first time."
- "What does a typical session look like end to end?"
- "What's the most common thing a user will do with this?"

**Phase 3 — Edge cases & failure modes**

What breaks, what's weird, what happens at boundaries.

- "What should happen if the service is unavailable during [primary action]?"
- "Are there scenarios where two users would do [primary action] simultaneously?"
- "What happens when the input is empty, malformed, or extremely large?"

**Phase 4 — Scope boundaries**

What's explicitly out.

- "You mentioned [X] — is that something this PRD should cover, or is it a separate concern?"
- "Are there adjacent features we should explicitly exclude?"

### Step 4: Behavior coverage check

Before writing, present all captured behaviors grouped by capability area. Ask:

"Here are the capabilities and behaviors I've captured. What's missing?"

After each response, incorporate any new behaviors and ask again. If the user keeps adding new capability areas, note them as Open Questions or a future-phase section rather than expanding the current PRD indefinitely. Stop iterating when the user confirms completeness or provides no new behaviors after two consecutive rounds.

This is the primary quality gate — it catches missing use cases before they become implementation gaps.

### Step 5: Write `docs/prd.md`

Write the PRD in a single pass using the template below. Create the `docs/` directory if it doesn't exist. Write the file to `docs/prd.md` relative to the repository root. If overwriting an existing file, mention this to the user before writing.

Do NOT commit the file — not even if the user says "save it" or "finalize it". Writing the file to disk is the complete action. Tell the user the file is at `docs/prd.md` and that committing is their responsibility.

## PRD Template

```markdown
# PRD: [Product/Feature Name]

## Problem Statement
What problem exists, from the user's perspective.

## User Stories
Short list establishing actors and motivations.
- As a [actor], I want [feature], so that [benefit]

## Expected Behaviors

### [Capability Group 1]
- Behavioral statement
- Behavioral statement

### [Capability Group 2]
- Behavioral statement
- Behavioral statement

## Open Questions
- Unresolved design decisions go here, not buried as assumptions.

## Out of Scope
- What this PRD explicitly does not cover.
```

**Notes on the template:**

- **User Stories** — keep to 3–8 entries. Just enough to establish actors and motivations, not a full specification.
- **Expected Behaviors** — the heart of the document. Flat lists of plain behavioral statements, grouped by capability. Each group should be independently shippable; if a group bundles unrelated concerns, split it.
- **Table of Contents** — add only when there are 5 or more capability groups.
- **Open Questions** — captures uncertainty explicitly rather than burying it as assumptions.

## Writing Guidelines

Apply these when writing the PRD:

1. **Specify behavior, not structure.** Describe what the system does from the outside. Don't prescribe class names, file layout, or internal architecture.

2. **State intent, not mechanism.** Say *why* something matters so downstream implementors can find better approaches.

3. **Make uncertainty visible.** Unresolved decisions go in Open Questions. Don't bury assumptions in behavioral statements.

4. **Be terse.** Every unnecessary word is a potential error amplified downstream. Cut adjectives, qualifiers, and hedges that don't add meaning.

5. **Each capability group should be independently shippable.** If a group bundles unrelated concerns, split it.
