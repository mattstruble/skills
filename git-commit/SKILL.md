---
name: git-commit
description: "Git conventional commits -- analyzes working tree changes, groups them logically by change type (feat/fix/docs/refactor/test/chore/etc.), detects and respects repo-level commit conventions (commitlint, commitizen, CONTRIBUTING.md), infers scopes, and creates subject-first conventional commit messages with minimal bodies. Use this skill whenever committing code, writing or planning commit messages, or any task that involves creating git commits -- 'commit my stuff', 'commit this', 'commit my changes', 'make a commit', 'git commit', 'help me commit', 'draft commit messages', or just 'commit' as an action. Also trigger when grouping changes into logical commits, cleaning up a messy working tree into organized commits, or when any agent needs to create or plan commit messages as part of a workflow. NOT for non-commit git operations (branching, merging, rebasing, history exploration)."
---

# Git Conventional Commits

Analyze working tree changes, group them by intent, and write clear conventional commit messages that respect any existing repo conventions.

## Workflow

Follow these steps in order. The goal is to produce commits that are atomic (one logical change per commit), well-typed, and useful to someone reading `git log` six months from now.

### Step 1: Detect repo conventions

Before writing any commit messages, check whether the repo already has commit conventions. Repo-specific rules take priority over the defaults in this skill.

Look for these (in rough priority order):
- `.commitlintrc`, `.commitlintrc.json`, `.commitlintrc.yml`, `.commitlintrc.js`, `commitlint.config.js`, `commitlint.config.ts` -- these define allowed types, scopes, and formatting rules
- `.czrc`, `.cz.json`, or a `config.commitizen` section in `package.json` -- commitizen configuration
- `CONTRIBUTING.md` or `.github/CONTRIBUTING.md` -- often contains written commit message guidelines
- `package.json` -- may have a `commitlint` config section

Also run `git log --oneline -20` to observe the actual commit style in use. The recent history tells you how the team actually writes commits -- what types they use, whether they use scopes, how long their descriptions are, whether they capitalize the first word, etc. Match what you see.

If the repo has conventions that differ from the conventional commit defaults below, follow the repo conventions. For instance, if the team uses `improvement:` instead of `feat:`, or if they always capitalize the description, do what the repo does.

### Step 2: Assess the working tree

Run `git status` to understand what you're working with. There are three possible states:

**Staged files exist** -- The user has already decided what to commit. Work only with the staged changes. Do not touch unstaged or untracked files. Proceed to Step 3 to analyze just the staged diff, then write a single commit.

**No staged files, but unstaged/untracked changes exist** -- Analyze everything (modified, deleted, and untracked files). Proceed to Step 3 to analyze, then Step 4 to group them into logical commits.

**Clean working tree** -- Nothing to commit. Tell the user.

If there are both staged AND unstaged changes, work only with the staged files. The user staged those intentionally -- respect that decision.

### Step 3: Analyze the changes

Read the actual diffs, not just the filenames. Filenames give you hints (a `.md` file is probably docs, a `test_*.py` file is probably tests), but the diff content tells you what actually changed and why.

For staged changes:
```
git diff --cached
```

For unstaged/untracked changes:
```
git diff
git ls-files --others --exclude-standard   # untracked files
```

For untracked files, read their contents to understand what they introduce.

As you read each change, think about:
- What is the *intent* of this change? (new feature, bug fix, cleanup, etc.)
- What part of the codebase does it touch? (this becomes the scope)
- Which other changes is it logically connected to?

### Step 4: Group changes (multi-commit path)

This step only applies when there are no staged files and you're organizing all unstaged/untracked changes into commits.

**Group by shared intent, not just shared type.** Two unrelated bug fixes should be two separate `fix:` commits. A new feature file and its corresponding test file should be one `feat:` commit, not split across `feat:` and `test:`.

Guiding principles:
- Files that implement the same logical change belong together, even if they span directories. A controller change + its migration + its test = one commit.
- Test files go with the code they test. Don't group all test files together -- group each test with the production code it validates.
- Configuration changes that enable a feature go with that feature, not in a separate `chore:` commit.
- Standalone documentation files (README, docs/*.md, guides) should be separate `docs` commits, even when they describe a feature in the same changeset. Keeping feature commits focused on code makes them easier to review and revert. Inline documentation like docstrings and code comments stays with the code it documents -- that's different from a standalone doc file.
- Pure refactors (restructuring without behavior change) should be separate from feature or fix work, because mixing them makes the feature commit harder to review.
- When in doubt, fewer cohesive commits are better than many tiny ones. A commit should be a meaningful unit of work that someone could understand, review, or revert on its own.

**Present the plan to the user before committing.** Format it clearly so they can approve, adjust, or reject it:

```
Here's how I'd group these changes:

1. feat(auth): add JWT token refresh endpoint
   - src/auth/refresh.ts (new)
   - src/auth/middleware.ts (modified)
   - tests/auth/refresh.test.ts (new)

2. fix(api): handle null response from external service
   - src/services/external.ts (modified)

3. docs: update API authentication guide
   - README.md (modified)
   - docs/authentication.md (modified)

Does this look right?
```

Wait for the user to confirm before executing any commits.

### Step 5: Execute the commits

For each group (or for the single staged commit):

1. Stage the relevant files: `git add <files>`
2. Compose the commit message following the format below
3. Commit: `git commit -m "<message>"` (or with `-m` for subject and body separately if needed)

**Commit order matters** when there are multiple groups. A sensible order:
1. Infrastructure, build, CI changes (foundational work)
2. Refactors (structural changes others build on)
3. Features and fixes (the substantive work)
4. Documentation (describes the above)

This isn't rigid -- use judgment. If a doc change is part of a feature, it goes with the feature commit, not at the end.

## Conventional commit format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Subject line rules:**
- `type` is required -- see the type guide below
- `scope` is optional -- a short noun identifying the affected area (e.g., `auth`, `api`, `cli`)
- `description` starts lowercase, uses imperative mood ("add" not "added" or "adds"), and does not end with a period
- The whole subject line should be under 72 characters
- Breaking changes append `!` before the colon: `feat(api)!: change auth token format`
- The subject line must be self-sufficient -- a reader should understand the full intent of the commit from the subject alone, without needing a body

**Body** -- the default is no body. Add one **only** when the subject cannot convey critical context on its own -- a non-obvious trade-off, a breaking change, or a design decision future readers will question.
- Separated from the subject by a blank line
- Explains *what* and *why*, not *how* (the diff shows the how)
- Keep to 1-3 lines; if you need more, the commit is probably doing too much
- Wrap at 72 characters

**Footers:**
- `BREAKING CHANGE: <description>` for breaking changes (can also use the `!` shorthand in the subject)
- `Refs: #123` for issue references
- `Co-authored-by: Name <email>` for co-authors

## Change type guide

Choose the type based on the *intent* of the change, not just what files were touched.

| Type | When to use | Example |
|------|------------|---------|
| `feat` | A new capability that didn't exist before | `feat(search): add fuzzy matching` |
| `fix` | Corrects incorrect behavior | `fix(parser): handle empty input without crashing` |
| `docs` | Documentation only -- READMEs, docstrings, comments, guides | `docs: add deployment troubleshooting section` |
| `style` | Formatting, whitespace, semicolons -- no logic change | `style: fix indentation in auth module` |
| `refactor` | Restructuring code without changing behavior | `refactor(db): extract query builder into separate module` |
| `perf` | A change whose primary purpose is improving performance | `perf(api): cache user lookup results` |
| `test` | Adding or updating tests, with no production code change | `test(auth): add edge cases for token expiry` |
| `build` | Build system or external dependency changes | `build: upgrade webpack to v5` |
| `ci` | CI/CD configuration changes | `ci: add Node 20 to test matrix` |
| `chore` | Routine maintenance that doesn't fit elsewhere | `chore: clean up unused environment variables` |
| `revert` | Reverts a previous commit | `revert: undo migration changes from abc123` |

**When a change spans multiple types:** If a single logical change touches production code and its tests, use the type that describes the production change (usually `feat` or `fix`). The test is *part of* the feature, not a separate thing. Only use `test` when the commit is *purely* about tests -- adding missing coverage, fixing a flaky test, etc. Standalone documentation files (README, guides) get their own `docs` commit even if they describe a feature introduced in the same changeset -- keep code commits focused on code.

## Scope inference

Scopes help readers quickly identify what part of the codebase a commit affects. They're optional, but valuable when they're clear and consistent.

**How to infer a good scope:**
- Use the top-level directory or module name: changes in `src/auth/` suggest scope `auth`
- In monorepos, use the package name: changes in `packages/cli/` suggest scope `cli`
- For cross-cutting changes, omit the scope rather than inventing a vague one

**Match existing conventions.** Look at `git log` and reuse scopes the team already uses. If the repo uses `auth` as a scope, don't introduce `authentication`. Consistency matters more than precision.

**When to omit scope:**
- The change spans the whole codebase
- The repo doesn't use scopes in its existing commits
- No scope value clearly fits -- a forced scope is worse than no scope

## Edge cases

**Very large changesets** -- If there are dozens of changed files across many unrelated areas, suggest that the user might want to commit in smaller working sessions going forward. Still do your best to group them logically, but acknowledge that the grouping might not be perfect and invite the user to adjust.

**Binary files** -- Mention them in the commit message ("add logo assets") but don't try to describe their diff content.

**Generated files** -- Lock files (`package-lock.json`, `poetry.lock`), build outputs, and similar generated files should generally go with the commit that caused them to change (e.g., a dependency update in `package.json` + the resulting `package-lock.json` change = one `build:` commit).

**Merge conflicts** -- If the working tree has unresolved merge conflicts, don't try to commit. Let the user know they need to resolve conflicts first.
