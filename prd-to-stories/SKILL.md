---
name: prd-to-stories
description: "Decompose a behavioral PRD into deliverable stories with technically specific acceptance criteria, saved as Markdown files. Use when the user wants to generate stories from a PRD, break capability groups into work items, create acceptance criteria, or go from PRD to implementable stories. Also trigger when the user mentions \"stories from PRD\", \"decompose the PRD\", \"break down capabilities\", or wants to turn behavioral requirements into testable deliverables."
---

# PRD to Stories

Decompose a behavioral PRD into independently deliverable stories with technically specific acceptance criteria. Each story is a Markdown file in `docs/stories/`. This skill reads a PRD and produces the next level of granularity below capability groups.

## Scope Model

`prd-writing` produces: **PRD** → Capability Groups → Behaviors

This skill produces: Behaviors → **Stories** (`docs/stories/*.md`) → Acceptance Criteria

## Workflow

### Step 1: Explore the codebase

Before reading the PRD, explore the repo. The codebase provides technical context needed for specific acceptance criteria — what exists, what patterns are used, what constraints are real.

Look for:
- Code structure and module organization
- Existing tests and how they verify behavior
- Integration points, external dependencies, and API contracts
- Any prior stories, specs, or design docs in `docs/`

Do NOT read or surface the contents of secrets files (`.env`, `*.key`, `credentials.*`, `secrets/`). Do not reproduce literal hostnames, connection strings, or API keys in story files.

### Step 2: Find the PRD

Check if `docs/prd.md` exists. If found, read it, briefly summarize what it covers, and confirm with the user:

"I found a PRD at `docs/prd.md` covering [brief summary — fill in from the Problem Statement or first capability group]. Should I use this?"

If not found, ask the user where the PRD is or to paste it directly. If the user cannot locate a PRD, offer to run the `prd-writing` skill first.

### Step 3: Ask scope

Ask the user:

"Do you want to generate stories for the entire PRD, or for a specific capability group?"

If the PRD has more than 5 capability groups, recommend starting with one — generating all stories at once tends to produce lower-quality output. If the user selects the entire PRD and it has more than 5 groups, confirm once more before proceeding.

If the PRD has no capability groups (behaviors are in a flat list), treat the entire PRD as a single capability group and proceed.

### Step 4: Check for existing story files

Check if `docs/stories/` exists and contains any files. Determine overlap by checking whether existing files reference the same capability group in their Source section or have titles that correspond to the selected scope.

If overlapping story files exist, ask:

"I found existing stories in `docs/stories/` that cover [capability group name] — should I update them or start fresh?"

Clarify: "start fresh" means writing new files alongside existing ones, not deleting them. Warn the user before overwriting any existing file.

### Step 5: Propose stories

Read the selected capability group(s) from the PRD. Note any behaviors that depend on behaviors in other capability groups — flag these as Open Questions in the affected stories.

Propose a story decomposition. For each proposed story, show:

- **Title**: short descriptive name
- **Behaviors covered**: which PRD behaviors this story addresses
- **Draft acceptance criteria**: initial set of checkboxes

Then ask: "Does this decomposition look right? Should any stories be merged or split?"

Iterate until the user approves the structure. If the user has requested more than three rounds of restructuring without approving, ask: "Should we proceed with the current decomposition and record remaining concerns as Open Questions?"

### Step 6: Technical precision interview

For each proposed story, briefly interview the user about technical specifics. Ask one question at a time. Focus on:

- Boundary conditions ("What's the maximum number of results?")
- Error behavior ("What happens when the API returns a 500?")
- Performance expectations ("Is there a latency requirement for this?")
- Integration points ("Does this need to work with the existing auth system?")

Provide a recommended answer with each question, grounded in what you found during codebase exploration. Reference patterns and behaviors — not literal hostnames, IP addresses, or connection strings.

Keep this brief — the PRD interview already captured the high-level behaviors. This interview adds technical precision. If a story has no unresolved technical questions after codebase exploration, skip the interview for that story and proceed directly to writing.

If the user gives two consecutive non-answers on the same question, move on and record it as an Open Question in the story.

After completing interviews for all stories, scan for contradictory answers on shared technical concerns (e.g., latency, error behavior, auth). Surface contradictions as Open Questions in the affected stories.

### Step 7: Write story files

Write one file per story to `docs/stories/<story-name>.md` using kebab-case naming derived from the story title. Strip any path separators (`/`, `\`) and `..` sequences from the filename. Create `docs/stories/` (and `docs/` if needed) if it doesn't exist.

Do NOT commit the files — not even if the user says "save" or "finalize". Writing files to disk is the complete action. Tell the user what was created.

### Step 8: Report coverage

After writing stories, report which PRD behaviors from the selected scope are covered and which aren't. This is informational only — don't require 100% coverage.

Example: "5 of 7 behaviors in the Search capability group are covered. Not yet covered: bulk export, rate-limit behavior."

If fewer than half the behaviors in the selected scope are covered, ask whether the user wants to continue with the remaining behaviors now or in a future session.

## Story Template

```markdown
# Story: [Story Title]

## Source
PRD Capability Group: [name]
Behaviors covered:
- [PRD behavior 1]
- [PRD behavior 2]

## Summary
One paragraph describing what this story delivers.

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Open Questions
- None.

## Out of Scope
- What this story explicitly does not cover, even if it's in the PRD.
```

**Notes on the template:**

- **Source** ties back to specific PRD capability groups and behaviors — this is how coverage is tracked.
- **Acceptance Criteria** are the heart — technically specific, verifiable statements with checkboxes.
- **Open Questions** captures uncertainty surfaced during the technical interview. Write `- None.` if there are no open questions; do not omit the section.
- **Out of Scope** prevents scope creep at the story level.

## Writing Guidelines

Apply these when writing stories:

1. **Acceptance criteria must be verifiable.** Each criterion should be something an engineer can confirm as passing or failing. If you can't describe how to verify it, it's not specific enough.

2. **Be terse.** Say enough to be testable, no more.

3. **Reference PRD behaviors, don't restate them.** The Source section ties back to the PRD. Acceptance criteria add specificity — they don't repeat what the PRD already says.

4. **Technical specificity is welcome, implementation prescription is not.** "Search returns results within 200ms" is good. "Use Elasticsearch with a fuzzy query" is not.

5. **Make uncertainty visible.** Unresolved technical decisions go in Open Questions. Don't bury assumptions in acceptance criteria.
