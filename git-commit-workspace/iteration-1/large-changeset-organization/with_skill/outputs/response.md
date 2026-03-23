# Commit Grouping Plan

You have 15 changed files across 6 directories. Here's how I'd group them into logical commits:

---

## Step 1: Repo conventions

No `.commitlintrc`, `.czrc`, or `CONTRIBUTING.md` detected in this simulated repo. Using conventional commit defaults.

---

## Step 2: Working tree assessment

No staged files. All 15 files are unstaged/untracked — analyzing all of them for grouping.

---

## Step 3: Analysis

| File | Intent | Notes |
|------|--------|-------|
| `frontend/src/pages/Profile.tsx` | New user profile feature | Frontend page |
| `frontend/src/components/ProfileCard.tsx` | New user profile feature | Frontend component |
| `frontend/src/styles/profile.css` | New user profile feature | Styles for profile UI |
| `backend/api/profile.py` | New user profile feature | API endpoint |
| `backend/models/profile.py` | New user profile feature | Data model |
| `db/migrations/0042_add_profile_table.sql` | New user profile feature | Schema migration enabling the feature |
| `tests/test_profile_api.py` | New user profile feature | Tests go with the code they validate |
| `tests/test_profile_model.py` | New user profile feature | Tests go with the code they validate |
| `frontend/package.json` | New user profile feature | Adds react-avatar dependency for profile UI |
| `frontend/package-lock.json` | New user profile feature | Generated lockfile update caused by package.json change |
| `backend/services/email.py` | Bug fix — null pointer on missing recipient | Unrelated to other changes |
| `.github/workflows/ci.yml` | CI config — add Python 3.12 to test matrix | Infrastructure change |
| `backend/auth/utils.py` | Refactor — extract validate_token helper | New file, but no new behavior |
| `backend/auth/auth.py` | Refactor — use validate_token from utils.py | Behavior unchanged, code restructured |
| `tests/test_auth_utils.py` | Refactor — tests for extracted helper | Belongs with the refactor, not with profile tests |

---

## Step 4: Proposed commits

Ordered per convention: CI first, then refactors, then features, then fixes.

```
1. ci: add Python 3.12 to test matrix
   - .github/workflows/ci.yml (modified)

2. refactor(auth): extract validate_token into utils module
   - backend/auth/utils.py (new)
   - backend/auth/auth.py (modified)
   - tests/test_auth_utils.py (new)

3. feat(profile): add user profile page with API, model, and migration
   - frontend/src/pages/Profile.tsx (new)
   - frontend/src/components/ProfileCard.tsx (new)
   - frontend/src/styles/profile.css (new)
   - frontend/package.json (modified)
   - frontend/package-lock.json (modified)
   - backend/api/profile.py (new)
   - backend/models/profile.py (new)
   - db/migrations/0042_add_profile_table.sql (new)
   - tests/test_profile_api.py (new)
   - tests/test_profile_model.py (new)

4. fix(email): handle null pointer when recipient is missing
   - backend/services/email.py (modified)
```

---

## Reasoning

**Commit 1 — `ci`:** The CI config change is independent of everything else and foundational — it defines the environment that validates all other commits. Goes first.

**Commit 2 — `refactor(auth)`:** Extracting `validate_token` is a pure structural change — no new behavior, just reorganization. Refactors belong before feature work so reviewers can see the structure before the substantive changes land. `test_auth_utils.py` goes here because it tests the *extracted helper*, not a new feature — and the refactor commit would be incomplete without confirming the extracted function behaves correctly.

**Commit 3 — `feat(profile)`:** All profile work belongs together: the migration enables the model, the model enables the API, the API enables the frontend. The tests validate the feature. `package.json` and `package-lock.json` are included because they exist *solely* to support the profile UI (adding react-avatar) — per the skill guideline, "configuration changes that enable a feature go with that feature." Lock files follow the dependency change that caused them.

**Commit 4 — `fix(email)`:** An unrelated, self-contained bug fix. Keeping it separate means someone can revert the email fix without touching the profile feature, and vice versa.

---

## Note on changeset size

15 files across 6 directories is manageable, but it suggests a few parallel tracks of work landed at once. Going forward, consider committing CI changes and refactors as you finish them rather than accumulating them alongside feature work — it makes history easier to bisect.

Does this grouping look right? Let me know if you'd like to adjust any group before I execute the commits.
