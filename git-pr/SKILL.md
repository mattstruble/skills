---
name: git-pr
description: Git pull request creation — use this skill whenever creating a pull request from a feature branch, writing PR titles or descriptions, or when any agent needs to open a PR as part of a workflow. Also trigger when the user says "open a PR", "create a pull request", or asks to submit their work for review. NOT for reviewing PRs (see code-reviewer), writing commits (see git-commit), or merging/rebasing.
---

# Git Pull Request Creation

Create focused, minimal pull requests that respect repo conventions. The PR title is the permanent record — it becomes the squash-merge commit on the default branch.

**References** (read when needed):
- `references/worked-example.md` — read when composing multi-commit PR descriptions

## PR Size: Check Before You Compose

Before writing a single word of the description, assess whether the PR is the right size. A reviewer can hold a 200-line change in their head during a focused 30-60 minute session. A 2000-line change they cannot — they'll skim, miss things, and the review will be shallow.

**Signs a PR is too large:**
- More than ~400 lines changed (additions + deletions)
- More than ~8 files touched across unrelated concerns
- The title requires "and" to capture what it does
- You'd need more than a paragraph to explain what's in it

These are guidelines, not hard cutoffs — a 450-line change touching one well-understood module may be fine; a 300-line change spanning 12 unrelated concerns may not be.

**If the PR is too large, say so before proceeding.** Suggest one of these splitting strategies:

| Strategy | When to use |
|----------|-------------|
| **Stacked branches** | Layered changes — refactor first (no behavior change), feature second. Stack the PRs; merge in order. `git checkout -b feat/step-2 feat/step-1` |
| **Draft PR** | You need visibility while you keep splitting. Open a draft PR for the full change, then carve reviewable chunks off it. Only use this if the repo doesn't auto-assign reviewers on PR open — otherwise you'll trigger premature notifications on a PR you intend to close. |
| **Feature flag** | The code is ready but the feature shouldn't activate yet. Ship behind a flag; flag removal is a separate small PR. |
| **Interface first** | Define the types/contracts/interfaces in one PR, implement in the next. Reviewers can validate the design before the implementation lands. |

When a PR genuinely cannot be split (rare — a large atomic migration, a coordinated rename across the codebase), say so explicitly in the description and explain why. Don't silently proceed with a large PR.

**Example split recommendation:**

> This diff touches 1,847 lines across 23 files and covers both the database schema migration and the API layer changes. I'd recommend splitting this into two PRs:
> 1. `feat(db): add user_sessions table and migration` — schema only, no behavior change
> 2. `feat(auth): implement session-based token revocation` — API layer using the new table
>
> Want me to help structure the stacked branches, or do you want to proceed with the single PR?

---

## Workflow

### Step 1: Detect repo conventions

**Do this before composing anything.**

- Check for `.github/PULL_REQUEST_TEMPLATE.md` (or `docs/`, `.github/PULL_REQUEST_TEMPLATE/`)
- Run `gh pr list --state merged --limit 5 --json title,body` — see how the team titles PRs
- If a PR template exists, it takes priority over observed patterns

Priority order: template > merged PR history > skill defaults.

### Step 2: Determine what's being submitted

```bash
# What branch are we on?
git branch --show-current

# What's the base branch?
gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'

# What commits are we submitting? (substitute <base> with the branch name above)
git log --oneline $(git merge-base HEAD <base>)..HEAD

# How large is the diff?
git diff --stat $(git merge-base HEAD <base>)..HEAD
```

| State | Action |
|-------|--------|
| No commits ahead of base | Nothing to submit — tell the user |
| Diff too large | Flag it, suggest splitting (see PR Size section above). If the user confirms they want to proceed anyway, continue to Step 3 and note in the description why the PR is large. |
| One commit ahead | Single-commit PR → Step 3 |
| Multiple commits ahead | Multi-commit PR → Step 3 |

### Step 3: Compose the PR

#### Title

The PR title follows conventional commit format — identical rules to commit subjects:

```
<type>(<scope>): <description>
```

- Imperative mood, lowercase, no trailing period, under 72 characters
- Breaking changes: append `!` before colon
- **Single-commit PR:** title matches the commit subject exactly
- **Multi-commit PR:** title summarizes the overall intent at the same granularity as a commit subject

The title is the *what* — specific and self-contained. "fix bug" is not a title. "fix null deref in auth handler when session token is missing" is.

#### Body

**Single-commit PR:** No body. The title says it all.

**Multi-commit PR:** A short paragraph (2-4 sentences) explaining the *why* — what problem this solves, what context a reviewer needs before looking at the diff. Not what was done (the diff shows that), not a list of commits (the Commits tab shows that).

A good body answers: *Why does this change exist? What was broken or missing?*

**Breaking changes (any PR):** Include a `BREAKING CHANGE:` footer explaining the impact, separated by a blank line — same format as git-commit footers.

**Issue linking:** If the branch name or commit messages reference an issue number (e.g., branch `fix/423-token-expiry`, commit footer `Refs: #423`), append `Closes #423` at the bottom. If no issue is detectable, omit.

**User-facing changes:** If the PR changes visible behavior, UI, or public API, add one sentence describing the impact. Keep it brief — this is for the reviewer's context, not a changelog entry.

#### Description quality: weak vs. strong

**Weak description** — vague, no context, reviewer still doesn't know what to look for:
```
Title: fix auth bug

Body:
Fixed a bug in the auth module. Also updated some tests.
```

**Strong description** — specific title, body explains the problem and why this fix (multi-commit PR: fix commit + test commit):
```
Title: fix(auth): prevent null deref when session token missing from request

Body:
The auth middleware assumed `request.session.token` was always present,
but unauthenticated requests from mobile clients omit it entirely. This
caused a NullPointerException that surfaced as a 500 rather than a 401.
The fix adds an explicit nil check before token validation; the existing
test suite didn't cover unauthenticated mobile paths so two cases were added.

Closes #512
```

The strong version lets a reviewer understand the intent before reading a single line of diff. That's the goal.

#### When a PR template exists

- Use the template as the skeleton
- Fill sections minimally — one or two sentences max per section
- Remove sections with nothing to say entirely (don't write "N/A" or filler)
- The motivation paragraph goes in the "Description" or "Summary" section
- Single-commit PRs still remove unnecessary sections

#### When motivation is unclear

If you cannot determine a clear "why" from the commits, diff, branch name, or linked issues, present an empty body at the confirmation step. Let the user fill it in rather than inventing a vague paragraph.

### Step 4: Present the plan — STOP and wait

**Do not run any `gh` or `git push` commands until the user confirms.** Show the proposed PR:

```
Title: feat(auth): add token revocation endpoint

Body:
The existing logout flow invalidated sessions but left tokens active
until expiry. This adds an explicit revocation endpoint so clients can
immediately invalidate compromised tokens.

Closes #423
```

For single-commit PRs with no body:

```
Title: fix(parser): handle empty input without panic

Body: (none)
```

Then ask: *"Does this look right, or do you want to change anything?"* and **stop**.

### Step 5: Create the PR

After confirmation:

```bash
# Push the branch if needed
git push -u origin HEAD

# Create the PR
gh pr create --base <base> --title "<title>" --body "<body>"
```

Output the PR URL. Nothing else.

---

## Anti-rationalization

Stop if you catch yourself thinking any of these:

| Rationalization | Reality |
|----------------|---------|
| "I should list what each commit does in the body" | No. The Commits tab exists. Don't re-narrate. |
| "The body should explain the implementation approach" | No. That's what the diff is for. The body explains *why*, not *how*. |
| "I'll add a summary section with bullet points" | Bullet-point summaries of changes are the #1 verbosity problem. The title captures the what. |
| "This template section is required so I'll write something" | If there's nothing genuine to say, remove the section. Filler wastes reviewer attention. |
| "I should add a body even though it's one commit" | Single-commit PRs don't need bodies. The title is the message. |
| "The title needs more detail than a commit subject" | Same format, same rules. Under 72 chars, imperative, lowercase. |
| "I'll explain what tests were added" | Only if the template has a Testing section and you have something non-obvious to say. "Added tests" is noise. |
| "I should mention the files that changed" | Never. The diff shows exactly what changed. |
| "The plan is obvious, I'll just create it" | PRs are public artifacts sent to reviewers. Present the plan and wait — always. |
| "I'll create it as a draft since I'm not sure" | Default is ready-for-review. The user confirmed the content — they intend it to be reviewed. |
| "The PR is large but it's all one feature" | Size is about reviewer cognitive load, not logical cohesion. Split it anyway. |
| "I can't split this PR" | You almost certainly can. Refactor first, feature second. Interface first, implementation second. |
