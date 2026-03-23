# Git Commit Grouping Plan

> **Note:** This is a large changeset with 15 files across 6 directories. Going forward, it's worth committing more frequently as you complete each logical unit of work — it makes grouping straightforward and keeps individual commits easier to review or revert.

Since there are no staged files, I've analyzed the full set of unstaged/untracked changes and grouped them by shared intent. Here's how I'd organize these into commits:

---

Here's how I'd group these changes:

**1. `ci: add Python 3.12 to test matrix`**
- `.github/workflows/ci.yml` (modified)

**2. `refactor(auth): extract validate_token into utils module`**
- `backend/auth/utils.py` (new)
- `backend/auth/auth.py` (modified)
- `tests/test_auth_utils.py` (new)

**3. `fix(email): handle missing recipient without null pointer`**
- `backend/services/email.py` (modified)

**4. `feat(profile): add user profile page with backend API and database migration`**
- `frontend/src/pages/Profile.tsx` (new)
- `frontend/src/components/ProfileCard.tsx` (new)
- `frontend/src/styles/profile.css` (new)
- `backend/api/profile.py` (new)
- `backend/models/profile.py` (new)
- `tests/test_profile_api.py` (new)
- `tests/test_profile_model.py` (new)
- `db/migrations/0042_add_profile_table.sql` (new)

**5. `build(frontend): add react-avatar dependency`**
- `frontend/package.json` (modified)
- `frontend/package-lock.json` (modified)

---

**Rationale for grouping decisions:**

- **CI first** — foundational tooling change, no dependencies on the other work.
- **Auth refactor second** — pure restructuring (`refactor:`), kept separate from feature work. The extracted `validate_token` helper and its tests are included because the test is part of validating the refactor, not a standalone test addition.
- **Email fix third** — isolated bug fix, unrelated to the profile feature.
- **Profile feature fourth** — all files that implement the same logical capability (the user profile page) are grouped together: frontend components, backend API, data model, and the database migration that enables it. The migration is part of this feature, not a standalone `chore:` commit.
- **Frontend dependency last** — the `react-avatar` package addition and its resulting lock file change is a `build:` commit, separate from the feature commit itself since it's a dependency management concern that's independently reviewable.

---

Does this look right? Happy to adjust any groupings or commit messages before I execute.
