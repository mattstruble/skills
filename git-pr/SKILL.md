---
name: git-pr
description: Git pull request creation — use this skill whenever creating a pull request from a feature branch, writing PR titles or descriptions, or when any agent needs to open a PR as part of a workflow. Also trigger when the user says "open a PR", "create a pull request", or asks to submit their work for review. NOT for reviewing PRs (see code-reviewer), writing commits (see git-commit), or merging/rebasing.
---

# Git Pull Request Creation

Create focused, minimal pull requests that respect repo conventions. The PR title is the permanent record — it becomes the squash-merge commit on the default branch.

**References** (read when needed):
- `references/worked-example.md` — read when composing multi-commit PR descriptions

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

# What commits are we submitting?
git log --oneline $(git merge-base HEAD <base>)..HEAD
```

| State | Action |
|-------|--------|
| No commits ahead of base | Nothing to submit — tell the user |
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

#### Body

**Single-commit PR:** No body. The title says it all.

**Multi-commit PR:** A short paragraph (2-4 sentences) explaining the *motivation* — why this change exists, what problem it solves, what context a reviewer needs before looking at the diff. Not what was done (the diff shows that), not a list of commits (the Commits tab shows that).

**Breaking changes (any PR):** Include a `BREAKING CHANGE:` footer explaining the impact, separated by a blank line — same format as git-commit footers.

**Issue linking:** If the branch name or commit messages reference an issue number (e.g., branch `fix/423-token-expiry`, commit footer `Refs: #423`), append `Closes #423` at the bottom. If no issue is detectable, omit.

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
