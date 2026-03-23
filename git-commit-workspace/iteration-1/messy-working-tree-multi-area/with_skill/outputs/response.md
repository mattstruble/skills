# Simulated Git Commit Grouping

## Step 1: Detect repo conventions

**Simulated commands:**
```
ls .commitlintrc* commitlint.config.* .czrc package.json CONTRIBUTING.md 2>/dev/null
git log --oneline -20
```

**Expected output:** No commitlint or commitizen config files found. Git log shows standard conventional commits style (e.g., `feat(auth): ...`, `fix: ...`). No special overrides — proceed with conventional commit defaults.

---

## Step 2: Assess the working tree

**Simulated command:**
```
git status
```

**Expected output:**
```
On branch main
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)

        modified:   src/auth/token.py
        modified:   src/auth/middleware.py
        modified:   tests/auth/test_token.py
        modified:   tests/payment/test_payment.py
        modified:   README.md

no changes added to commit (use "git add" to track)
```

No staged files — analyze all unstaged changes and group into logical commits.

---

## Step 3: Analyze the changes

**Simulated commands:**
```
git diff
git ls-files --others --exclude-standard
```

**Expected diff summary:**

- `src/auth/token.py` — new token refresh logic (new capability: generates and validates refresh tokens)
- `src/auth/middleware.py` — wires the refresh logic into the request pipeline (supports the same feature)
- `tests/auth/test_token.py` — tests for the new token refresh logic (validates the above feature)
- `tests/payment/test_payment.py` — fixes to existing payment tests (corrects incorrect test assertions / flaky behavior, no production code change)
- `README.md` — updated setup instructions (standalone documentation update)

---

## Step 4: Grouping plan

**Reasoning:**

- `src/auth/token.py`, `src/auth/middleware.py`, and `tests/auth/test_token.py` all serve the same intent: implementing the token refresh feature. The tests belong with the production code they validate — not in a separate `test:` commit.
- `tests/payment/test_payment.py` is a pure test fix — no production code changed. It's unrelated to the auth feature, so it gets its own `test:` commit.
- `README.md` is standalone documentation. Keeping it separate from the auth feature commit makes the feature commit easier to review and revert independently.

**Commit order:**
1. Feature work first (auth token refresh)
2. Standalone test fix (payment tests)
3. Documentation last (README)

---

Here's how I'd group these changes:

1. feat(auth): add token refresh logic
   - src/auth/token.py (modified)
   - src/auth/middleware.py (modified)
   - tests/auth/test_token.py (modified)

2. test(payment): fix failing payment module tests
   - tests/payment/test_payment.py (modified)

3. docs: update README with new setup instructions
   - README.md (modified)

Does this look right?

---

## Step 5: Execution plan (pending user confirmation)

Once confirmed, the commands would be:

```bash
# Commit 1
git add src/auth/token.py src/auth/middleware.py tests/auth/test_token.py
git commit -m "feat(auth): add token refresh logic"

# Commit 2
git add tests/payment/test_payment.py
git commit -m "test(payment): fix failing payment module tests"

# Commit 3
git add README.md
git commit -m "docs: update README with new setup instructions"
```
