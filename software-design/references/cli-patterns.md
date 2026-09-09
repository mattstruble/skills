# CLI Patterns

---

## Progressive Disclosure in Commands

Common paths should be obvious; power should be discoverable.

| Layer | Example | Who uses it |
|---|---|---|
| **Layer 0** | `mytool deploy` | Most users, most of the time |
| **Layer 1** | `mytool deploy --env staging --dry-run` | ~20% of invocations |
| **Layer 2** | `mytool deploy rollback --to v1.2.3` | Subcommands for complex operations |
| **Layer 3** | `mytool deploy --strategy blue-green --timeout 600` | Advanced flags, visible in `--help` |

**Rule:** Don't penalize the common case to support the edge case. If 80%
of users just run `deploy`, that invocation should require zero flags and
do the right thing.

---

## Feedback Contract

Every long-running operation maintains a feedback contract with the user:

| Duration | Expected feedback |
|---|---|
| < 100ms | No feedback needed |
| 100ms–1s | Should feel instant; spinner optional |
| 1–10s | Progress indicator |
| > 10s | Progress + estimated time remaining |
| > 30s | Progress + ability to cancel (Ctrl-C handled gracefully) |

**Before — silent for 2 minutes, then done:**

```
$ mytool build
Done.
```

**After — continuous feedback:**

```
$ mytool build
Building 47 modules...
  [████████████████░░░░░░░░] 32/47 modules  (68%)  elapsed: 1m12s  ~30s remaining
```

### Failure Feedback

Failure output must tell: (1) what failed, (2) why, and (3) how to fix it.

**Before:**

```
Error: exit code 1
```

**After:**

```
Error: Build failed — module 'payments' has a circular import.

  payments/service.py:3  →  from payments.api import router
  payments/api.py:5      →  from payments.service import charge

Fix: Break the cycle by moving the shared type to payments/types.py
     and importing from there in both files.

Docs: https://mytool.dev/errors/circular-import
```

The user knows exactly what happened, can see the cycle, and has a
concrete fix to try.

---

## Constraint Defaults for Dangerous Operations

Mutating and destructive commands should be constrained by default.

### `--dry-run` as Universal Constraint

Show what would happen without doing it:

```
$ mytool migrate --dry-run
Would apply 3 migrations:
  0042_add_payment_status.py
  0043_backfill_payment_status.py
  0044_drop_legacy_status_column.py

No changes applied. Remove --dry-run to execute.
```

### `--force` for Deliberate Overrides

Skip safety checks when the caller knows what they're doing:

```
$ mytool deploy --env production
Error: Health check failed — 2 instances unhealthy. Use --force to deploy anyway.

$ mytool deploy --env production --force
Deploying despite unhealthy instances...
```

### Confirmation Prompts for Irreversible Operations

Require the user to type a confirming value:

```
$ mytool db drop --env production
This will permanently delete the 'orders_prod' database (142GB, 3.2M rows).
Type the database name to confirm: orders_prod
Dropping database...
```

**Rule:** The default behavior of a dangerous command should be to do
nothing dangerous. Safety is opt-out, not opt-in.
