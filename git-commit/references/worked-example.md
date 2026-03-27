# Worked Example: From Diff to Commits

This example walks through a realistic multi-file changeset and shows how to reason about grouping.

## The changeset

Unstaged changes:
- `backend/auth/utils.py` — new file, extracts `validate_token` helper from `auth.py`
- `backend/auth/auth.py` — modified, now calls `validate_token` from utils (behavior unchanged)
- `tests/test_auth_utils.py` — new file, tests for the extracted helper
- `backend/api/profile.py` — new file, user profile API endpoint
- `backend/models/profile.py` — new file, Profile data model
- `db/migrations/0042_add_profile_table.sql` — new file, schema migration for profiles
- `tests/test_profile_api.py` — new file, tests for the profile API
- `frontend/package.json` — modified, adds `react-avatar` dependency for profile UI
- `frontend/package-lock.json` — modified, lockfile updated by the above
- `backend/services/email.py` — modified, fixes null pointer when recipient is missing

## Reasoning through the grouping

**Auth utils group:** `auth.py`, `utils.py`, and `test_auth_utils.py` are a pure refactor — no new behavior, just restructuring. Keeping it separate from the profile feature means a reviewer can confirm "nothing changed" without wading through new code. The test belongs here because it validates the extracted helper.

**Profile feature group:** `profile.py` (API), `profile.py` (model), the migration, and `test_profile_api.py` all implement the same capability. The migration *enables* the model — it's part of the feature, not a standalone `chore:`. `package.json` and `package-lock.json` exist solely because the profile UI needs `react-avatar` — they're configuration that enables the feature, so they belong here too.

**Email fix group:** `email.py` is an unrelated bug fix. Someone reverting the profile feature shouldn't also lose this fix.

## Result

```
1. refactor(auth): extract validate_token into utils module
   - backend/auth/utils.py (new)
   - backend/auth/auth.py (modified)
   - tests/test_auth_utils.py (new)

2. feat(profile): add user profile API, data model, and database migration
   - backend/api/profile.py (new)
   - backend/models/profile.py (new)
   - db/migrations/0042_add_profile_table.sql (new)
   - tests/test_profile_api.py (new)
   - frontend/package.json (modified)
   - frontend/package-lock.json (modified)

3. fix(email): handle null pointer when recipient is missing
   - backend/services/email.py (modified)
```

## Key decisions

- Refactor lands before the feature (reviewers see the structure first)
- Migration and lockfile go *with* the feature that caused them (not as separate commits)
- Unrelated bug fix stays isolated so it can be reverted independently
- Standalone docs (if any) would get their own `docs:` commit
