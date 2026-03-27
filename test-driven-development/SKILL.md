---
name: test-driven-development
description: "Test-driven development workflow for implementing features, fixing bugs, and protecting behavior during refactors. Use whenever building new modules, APIs, services, handlers, or processing logic (payment systems, auth servers, caching layers, data pipelines, retry mechanisms); refactoring, rewriting, or migrating existing code; restructuring monoliths or tightly-coupled modules; fixing bugs (reproduce with a failing test first); or any task with multiple behaviors and non-trivial logic. Trigger on 'implement', 'build', 'add feature', 'refactor', 'migrate', 'rewrite', 'restructure', 'fix bug', 'reproduce', or mentions of TDD, red-green-refactor, or test-first development -- even if the user doesn't mention TDD, the workflow applies whenever the task involves substantial new functionality or reorganizing how existing code is structured. Complements test-design (test quality) and software-design (design principles). NOT for trivial one-liner fixes, config changes, renaming, documentation, or test quality in isolation (see test-design)."
---

# Test-Driven Development

This skill governs *how you work* -- the rhythm of writing tests and code
together. For *what makes a good test*, see `test-design`. For design
principles that inform refactoring, see `software-design`.

## Why Test-First

Tests written after implementation are biased by what you built. You
unconsciously test the paths you remember and skip the ones you forgot.
Tests written first force you to specify behavior before you know the
implementation -- catching a different class of bugs. A test that passes
immediately has never proven it catches anything.

## Three Modes

- **Feature Mode** -- building new functionality (red-green-refactor cycle)
- **Refactor Mode** -- protecting existing behavior before restructuring
- **Bug Fix Mode** -- reproducing a defect before fixing it

---

## Feature Mode

### Plan Behaviors

Before any code, identify the behaviors the feature needs. Think in what
a caller would observe, not implementation steps. Prioritize critical paths
and complex logic over trivial happy paths.

If there's genuine ambiguity, confirm with the user before starting. The
test: would a wrong guess waste significant work?

### Tracer Bullet

Start with one test for the simplest end-to-end behavior:

```
RED:   Write one test -> fails (verify: missing feature, not typo/import error)
GREEN: Minimal code to pass -> passes
```

This proves the interface works and the test infrastructure is set up.

### Incremental Loop

For each remaining behavior, one at a time:

```
RED:     Next test -> fails (verify: fails for the right reason)
GREEN:   Minimal code to pass -> passes
REFACTOR: Clean up while green (see software-design)
```

One test at a time. Only enough code to pass the current test. Each test
responds to what you learned from the previous cycle.

After each cycle, verify:

- The test describes caller-visible behavior
- It uses the public interface
- It would survive a refactor
- All previous tests still pass

See `test-design` for test quality criteria.

See `references/worked-example.md` for a complete 2-cycle walkthrough
(rate limiter).

---

## Refactor Mode

Start GREEN, stay GREEN throughout. Use when restructuring existing code.

1. **Assess** existing test coverage through public interfaces
2. **Characterize** uncovered behaviors with tests that pass against current code
3. **Refactor** in small steps, running tests after each change
4. **When tests break**: behavior changed = regression (fix it); test was
   coupled to internals = update the test to assert behavior instead

Unlike Feature Mode, writing multiple characterization tests before changing
code is correct here -- you're capturing a snapshot of existing behavior.

See `references/refactor-mode.md` for detailed guidance and examples.

---

## Bug Fix Mode

Before touching code, write a test that reproduces the bug. Watch it fail.
Fix the code. Watch the test pass. The test prevents regression permanently.

The key: watching the test fail proves the bug exists *and* that your test
catches it. A test written after the fix might pass for the wrong reason.

---

## Mode Transitions

Modes interleave. While building a feature, you may need to refactor
existing code first (switch to Refactor Mode). When a bug surfaces, pause
to reproduce it (Bug Fix Mode). The key is knowing which mode you're in:
red-green for new behavior, stay-green for restructuring, reproduce-then-fix
for defects.

---

## Discipline

TDD discipline is where agents fail most. The test-first constraint feels
unnecessary when you "already know" the implementation -- but that's exactly
when bias creeps in. The constraint is the point.

### Rationalization Table

If you catch yourself thinking any of these, stop:

| Rationalization | Reality |
|---|---|
| "I'll write code and tests together" | You lose the failing-test signal -- the proof it catches something. |
| "This is too simple for TDD" | Simple features are fast to TDD. The habit matters more than the test. |
| "I already know the implementation" | That's when you only test paths you remember. Test-first prevents this. |
| "Let me write all tests first" | Horizontal slicing. Bulk tests describe imagined behavior. One at a time. |
| "I'll get it working, then add tests" | Tests-after test what you built, not what you intended. |
| "The test would be trivial" | A test that never failed has never proven anything. Seconds to run. |

### Red Flags

You've left TDD if:

- You've written more than one failing test without making any pass
- You're writing implementation without a failing test driving it
- In Feature or Bug Fix Mode, a test passed immediately (behavior already existed, or the test is wrong -- does not apply to Refactor Mode, where characterization tests are expected to pass)
- You're refactoring while tests are failing

### When TDD Feels Hard

Test difficulty is a design signal, not a testing problem:

| Symptom | Response |
|---|---|
| Don't know what to test | Write the assertion first, work backward to setup |
| Test is hard to write | Simplify the interface -- decompose or reduce dependencies |
| Must mock everything | Use dependency injection -- code is too coupled |
| Setup is enormous | Extract factories, or simplify the design |

---

## References

| Reference | When to read |
|---|---|
| `references/worked-example.md` | Full RED-GREEN-REFACTOR walkthrough with a rate limiter |
| `references/refactor-mode.md` | Characterization tests, safe restructuring, and handling test breakage during refactors |
