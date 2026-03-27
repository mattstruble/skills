# Conventional Commit Format Reference

## Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

## Subject line rules
- `type` is required
- `scope` is optional — a short noun identifying the affected area (e.g., `auth`, `api`, `cli`)
- `description`: lowercase, imperative mood ("add" not "added"), no trailing period
- Under 72 characters total
- Breaking changes: append `!` before colon — `feat(api)!: change auth token format`
- Subject must be self-sufficient — reader understands full intent without needing a body

## Body
Default: no body. Add one **only** when the subject can't convey critical context — a non-obvious trade-off, a breaking change, or a design decision future readers will question.
- Separated from subject by a blank line
- Explains *what* and *why*, not *how* (the diff shows the how)
- 1-3 lines; wrap at 72 characters

## Footers
- `BREAKING CHANGE: <description>` for breaking changes
- `Refs: #123` for issue references
- `Co-authored-by: Name <email>` for co-authors

## Change types

| Type | When to use | Example |
|------|-------------|---------|
| `feat` | New capability that didn't exist before | `feat(search): add fuzzy matching` |
| `fix` | Corrects incorrect behavior | `fix(parser): handle empty input without crashing` |
| `docs` | Documentation only — READMEs, standalone guides, docs/ files | `docs: add deployment troubleshooting section` |
| `style` | Formatting, whitespace — no logic change | `style: fix indentation in auth module` |
| `refactor` | Restructuring without behavior change | `refactor(db): extract query builder into separate module` |
| `perf` | Primary purpose is improving performance | `perf(api): cache user lookup results` |
| `test` | Adding/updating tests with no production code change | `test(auth): add edge cases for token expiry` |
| `build` | Build system or external dependency changes | `build: upgrade webpack to v5` |
| `ci` | CI/CD configuration changes | `ci: add Node 20 to test matrix` |
| `chore` | Routine maintenance that doesn't fit elsewhere | `chore: clean up unused environment variables` |
| `revert` | Reverts a previous commit | `revert: undo migration changes from abc123` |

**When a change spans multiple types:** Use the type that describes the production change (`feat` or `fix`). Tests and config that enable a feature belong in that commit. Only use `test` for commits that are *purely* about tests.

## Scope inference

- Use the top-level directory or module name: changes in `src/auth/` → scope `auth`
- In monorepos, use the package name: changes in `packages/cli/` → scope `cli`
- For cross-cutting changes, omit scope rather than inventing a vague one
- Match existing conventions from `git log` — consistency beats precision
- Omit scope when: change spans whole codebase, repo doesn't use scopes, or no scope clearly fits

## Edge cases

**Very large changesets** — Group logically as best you can; acknowledge imperfection and invite adjustment.

**Binary files** — Mention them in the commit message ("add logo assets") but don't describe diff content.

**Generated files** — Lock files, build outputs go with the commit that caused them. Dependency update → `build:` commit. Dependency added for a feature → goes with that feature commit.

**Merge conflicts** — Don't commit. Tell the user to resolve conflicts first.
