---
name: git-commit
description: Git conventional commits — use this skill whenever authoring new git commits from working tree changes, writing commit messages, or planning how to organize changes into commits. Also trigger when grouping changes into logical commits, cleaning up a messy working tree, or when any agent needs to create commit messages as part of a workflow. NOT for non-authoring git operations (branching, merging, rebasing, cherry-picking, reverting, squashing, resolving conflicts, creating PRs, git configuration, or exploring git history).
---

# Git Conventional Commits

Analyze working tree changes, group by intent, write conventional commit messages that respect repo conventions.

**References** (read when needed):
- `references/commit-format.md` — read when composing messages or unsure about type/scope rules
- `references/worked-example.md` — read when grouping is ambiguous or changes span multiple intents

## Workflow

### Step 1: Detect repo conventions

**Do this before writing any messages.** Repo-specific rules override defaults here.

- Check `.commitlintrc*`, `commitlint.config.*`, `.czrc`, `CONTRIBUTING.md`
- **Always** run `git log --oneline -20` — even when config files exist. Config defines the rules; history shows what the team actually does. When they conflict, history wins.

> Repo history is the ground truth. A `feat:` in a repo that uses `feature:` looks wrong forever.

### Step 2: Assess the working tree

Run `git status`:

| State | Action |
|-------|--------|
| Staged files exist | Work only with staged → Step 3 → Step 5 → Step 6 |
| Unstaged/untracked only | Analyze all → Step 3 → Step 4 → Step 5 → Step 6 |
| Clean | Nothing to commit — tell the user |

If both staged and unstaged exist, work only with staged — the user staged those intentionally.

### Step 3: Analyze the changes

Read the actual diffs — filenames hint, but diff content tells you *what changed and why*.

```bash
git diff --cached          # staged
git diff                   # unstaged
git ls-files --others --exclude-standard  # untracked
```

For each change, identify: **intent** (feature? fix? cleanup?), **scope**, **logical connections** to other changes.

### Step 4: Group changes into commits

*Only applies when no staged files exist.*

**Group by shared intent, not shared type.** Two unrelated bug fixes = two `fix:` commits.

- Test files go **with the code they test** — not with all other tests
- Config/migrations that enable a feature go with that feature
- Standalone docs (README, docs/*.md) get their own `docs:` commit
- Pure refactors stay separate from feature/fix work
- Commit order: infrastructure → refactors → features/fixes → standalone docs

See `references/worked-example.md` for tricky grouping decisions.

### Step 5: Present the plan — STOP and wait

**Do not run any `git add` or `git commit` until the user confirms.** Show the proposed commits as a numbered list with the message and files for each:

```
1. feat(auth): add token revocation
   - src/auth/revoke.py (new)
   - tests/test_auth_revoke.py (new)

2. docs: update README with features section
   - README.md (modified)
```

Then ask: *"Does this look right, or do you want to change anything?"* and **stop**. Wait for the user's response before proceeding.

The user might adjust groupings, rename messages, or reorder commits — this is the whole point. Commits are permanent, so the plan must be reviewed first. This applies even for a single commit.

### Step 6: Execute the commits

For each group: `git add <files>` → compose message → `git commit -m "<message>"`

Format: `<type>(<scope>): <description>` — lowercase, imperative, under 72 chars. See `references/commit-format.md` for the full spec.

---

## Anti-rationalization

Stop if you catch yourself thinking any of these:

| Rationalization | Reality |
|----------------|---------|
| "Defaults are fine, I'll skip convention detection" | Repo history is the ground truth. Check it. |
| "It's all one logical change" | If part of it could be reverted independently, it's not one change. |
| "These are all from the same sprint/PR" | Sharing a sprint doesn't make changes logically related. Group by intent, not by timeframe. |
| "The user asked for one big commit" | Propose proper grouping and explain why. Respect their final call, but don't silently comply with a vague message. |
| "The message is clear enough" | If the subject doesn't convey *what and why* without the diff, it's not clear enough. |
| "I'll group all tests in a `test:` commit" | Tests go with the code they test. `test:` is for test-only changes. |
| "The lockfile/migration is a separate `chore:`" | Generated files go with the commit that caused them. |
| "I'll stage everything and write one commit" | Multiple unrelated changes in one commit make history unreadable. |
| "The plan is obvious, I'll just commit" | Commits are permanent. Present the plan and wait — even when the grouping seems clear. |
