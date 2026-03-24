---
name: test-driven-development
description: "Test-driven development workflow for implementing features, fixing bugs, and protecting behavior during refactors. Use whenever building new modules, APIs, services, handlers, or processing logic (payment systems, auth servers, caching layers, data pipelines, retry mechanisms); refactoring, rewriting, or migrating existing code; restructuring monoliths or tightly-coupled modules; fixing bugs (reproduce with a failing test first); or any task with multiple behaviors and non-trivial logic. Trigger on 'implement', 'build', 'add feature', 'refactor', 'migrate', 'rewrite', 'restructure', 'fix bug', 'reproduce', or mentions of TDD, red-green-refactor, or test-first development -- even if the user doesn't mention TDD, the workflow applies whenever the task involves substantial new functionality or reorganizing how existing code is structured. Complements test-design (test quality) and software-design (design principles). NOT for trivial one-liner fixes, config changes, renaming, documentation, or test quality in isolation (see test-design)."
---

# Test-Driven Development

This skill governs *how you work* -- the rhythm of writing tests and code
together. For guidance on *what makes a good test* (desiderata, anti-patterns,
language-specific patterns), see the `test-design` skill. For design principles
that inform refactoring decisions, see the `software-design` skill.

## Philosophy

Tests verify behavior through public interfaces, not implementation details.
Code can change entirely; tests should not need to. A good test reads like a
specification -- it describes *what* the system does, and a reader who has
never seen the code can understand the capability it protects.

The corollary: if a test breaks when you refactor internals but behavior hasn't
changed, that test was testing structure, not behavior. It's working against you
rather than for you.

Writing tests *before* implementation matters for a specific reason: tests
written after you've built something are biased by what you built. You
unconsciously test the code paths you remember and skip the ones you forgot.
Tests written first force you to specify behavior before you know the
implementation, which catches a different class of bugs. A test that passes
immediately when you first run it has never proven it catches anything. You
don't know whether it would fail if the feature were broken.

This skill has two modes depending on the task:

- **Feature Mode** -- building something new using the red-green-refactor cycle
- **Refactor Mode** -- protecting existing behavior with characterization tests
  before restructuring code
- **Bug Fix Mode** -- reproducing a defect with a test before fixing it

## Feature Mode

Use when building new functionality. The goal is to let tests drive the design
forward incrementally: write a failing test that describes what you want, then
write the minimum code to make it pass. Repeat.

### Planning

Before writing any code, identify the behaviors the new feature needs to
exhibit. Think in terms of what a caller or user would observe, not
implementation steps.

If the feature is straightforward (clear inputs, outputs, and behaviors), lay
out the behavior list and proceed. If there's genuine ambiguity about what
the feature should do, what its interface should look like, or which behaviors
matter most, confirm with the user before starting. The judgment call is:
would a wrong guess waste significant work?

Prioritize behaviors. You can't test everything, and not every behavior is
equally important. Focus testing effort on critical paths and complex logic
over trivial happy paths.

### Tracer Bullet

Start with a single test that proves the path works end-to-end:

```
RED:   Write one test for the simplest end-to-end behavior -> test fails
       Verify it fails for the right reason: the feature is missing,
       not a typo or import error. An error during setup means the test
       infrastructure isn't working yet — fix that first.
       A test that passes immediately is testing existing behavior — rewrite it.
GREEN: Write minimal code to make it pass -> test passes
```

This is the tracer bullet -- it confirms the interface works, the test
infrastructure is set up correctly, and you have a foundation to build on.

### Incremental Loop

For each remaining behavior:

```
RED:   Write the next test -> fails
       Verify it fails for the right reason: the behavior is absent,
       not a typo or import error.
GREEN: Minimal code to pass -> passes
```

One test at a time. Only enough code to pass the current test. Each test
responds to what you learned from the previous cycle -- because you just
wrote the code, you know exactly what behavior matters and how to verify it.

The reason this matters: tests written one-at-a-time in response to real code
describe *actual* behavior. Tests written in bulk before implementation
describe *imagined* behavior -- they tend to test the shape of data structures
and function signatures rather than what the system actually does.

### Anti-Pattern: Horizontal Slices

Writing all tests first, then all implementation, is "horizontal slicing":

```
WRONG (horizontal):
  RED:   test1, test2, test3, test4, test5
  GREEN: impl1, impl2, impl3, impl4, impl5

RIGHT (vertical):
  RED->GREEN: test1 -> impl1
  RED->GREEN: test2 -> impl2
  RED->GREEN: test3 -> impl3
  ...
```

Horizontal slicing produces brittle tests because they're written before
understanding the implementation. You outrun your headlights, committing to
test structure before learning what actually matters. Vertical slices keep
tests grounded in reality.

### Worked Example: Rate Limiter

Here's what 2 TDD cycles look like in practice. The domain is a rate limiter
that allows N requests per time window per client.

The snippets below are pseudo-code — method signatures omit language-specific
boilerplate (`self`/`this`, type annotations) for clarity. `self.` in method
bodies is a stand-in for the instance reference; use `this.` or equivalent in
your language.

**Behavior list (planned upfront):**
1. Requests within the limit are allowed
2. Requests that exceed the limit are denied
3. The window resets after the time period
4. Different clients have independent limits

**Cycle 1 — Tracer bullet (simplest end-to-end path):**

The tracer bullet is the simplest behavior that proves the interface works and
the test harness is set up correctly. For a rate limiter, that's the happy path.

```
// RED: write the test first, watch it fail
test "first request is allowed":
    limiter = RateLimiter(limit=3, window=60)
    result = limiter.check("client-A")
    assert result == ALLOWED

// GREEN: write the minimum code to pass
class RateLimiter:
    check(client_id):
        return ALLOWED   // hardcoded — just enough to pass
```

The test passes. The implementation is obviously incomplete, but that's fine.
The tracer bullet proved the interface compiles and the test harness works.

**Cycle 2 — Enforce the limit:**

```
// RED: write the next test, watch it fail
test "request beyond limit is denied":
    limiter = RateLimiter(limit=2, window=60)
    limiter.check("client-A")   // request 1
    limiter.check("client-A")   // request 2
    result = limiter.check("client-A")   // request 3 — over limit
    assert result == DENIED

// GREEN: extend the implementation to make both tests pass
class RateLimiter:
    init(limit, window):
        self.limit = limit
        self.counts = {}   // maps client_id -> request count

    check(client_id):
        count = self.counts[client_id] ?? 0   // 0 if client not seen yet
        if count >= self.limit:
            return DENIED
        self.counts[client_id] = count + 1
        return ALLOWED
```

Both tests pass. The implementation is still incomplete (no window reset, no
client isolation test), but it's grounded in real behavior.

**After cycle 2 — Refactor opportunity:**

Before adding window-reset logic (which will also need to read the count),
extract the count lookup to avoid duplicating the access pattern:

```
// Extract a helper — all tests still pass after this change
class RateLimiter:
    count_for(client_id):
        return self.counts[client_id] ?? 0

    check(client_id):
        count = self.count_for(client_id)
        if count >= self.limit:
            return DENIED
        self.counts[client_id] = count + 1
        return ALLOWED
```

The pattern continues: each remaining behavior (window reset, client isolation)
gets its own RED→GREEN cycle. Each cycle adds one behavior, keeps all previous
tests green.

### Refactor Phase

After the tests are green, look for opportunities to improve the code.
Refactoring happens *only* when all tests pass -- never while red. The tests
give you confidence that your improvements preserve behavior.

Run tests after each refactor step, not just at the end. Small, verified
steps are safer than a large restructuring followed by a prayer.

See the `software-design` skill for guidance on what to look for: duplication,
shallow modules that should be deepened, feature envy, primitive obsession.

### Test Cleanup and Isolation

Tests often need to reset state between runs. Resist the urge to add private
`_reset()` or `_clear_state()` methods to production code for test convenience
-- these are test hooks disguised as implementation, and they couple tests to
internals.

Prefer approaches that work through the public interface or the test framework:
use fresh instances per test, use the test framework's setup/teardown to
reconstruct objects, or use dependency injection to supply test-specific
implementations. If the only way to reset state is through a private function,
that's a signal the module's interface may need a rethink -- perhaps the state
should be scoped to an object lifecycle rather than living in module globals.

### Checklist Per Cycle

After each red-green cycle, verify:

- The test describes behavior a caller would care about, not implementation
- The test uses only the public interface
- The test would survive an internal refactor
- The production code is minimal for this test -- no speculative features
- Test cleanup uses public interfaces or framework mechanisms, not private hooks
- All previous tests still pass

## Refactor Mode

Use when restructuring, migrating, or reorganizing existing code. The goal
is the opposite of Feature Mode: you start GREEN and stay GREEN throughout.
Tests come first not to drive new design, but to lock down existing behavior
so you can change the code with confidence.

### Assess Existing Coverage

Before writing new tests, check what's already covered. Look at existing
tests for the code you're about to change:

- What behaviors do they exercise?
- Do they test through public interfaces or are they coupled to internals?
- Are there gaps in coverage for the code paths you'll be modifying?

Tests that are already green and test through public interfaces are valuable
-- keep them. Tests coupled to implementation details will likely break during
the refactor regardless of whether behavior changes; note these but don't
count them as coverage.

### Identify Behaviors to Preserve

Look at the public interface contracts of the code being refactored:

- Function and method signatures -- what goes in, what comes out
- Side effects visible to callers (records created, events emitted, errors raised)
- Edge cases and error handling that callers depend on

The focus is on what external consumers of this code observe, not on internal
mechanics. If an internal helper reorganizes its work but the public interface
still returns the same results for the same inputs, that's a successful
refactor.

### Write Characterization Tests

For each uncovered behavior, write a test that passes against the current
code. These are characterization tests -- they document what the system
*actually does* right now, whether or not that's what was originally intended.

Unlike Feature Mode, writing multiple characterization tests before changing
any code is expected and correct here. You're capturing a snapshot of existing
behavior, not driving new design.

**Example — before refactoring a payment module:**

```
// Capture what the current code does before touching it.
// These tests don't judge whether the behavior is ideal — they just pin it.

test "processing a valid card returns success":
    result = process_payment(valid_card, amount: 50.00)
    assert result.status == SUCCESS
    assert result.charge_id != null

test "processing a declined card returns failure with reason":
    result = process_payment(declined_card, amount: 50.00)
    assert result.status == DECLINED
    assert result.reason != null

test "processing with zero amount raises an error":
    expect_error(InvalidAmountError):
        process_payment(valid_card, amount: 0)
    // syntax for expect_error varies by language (pytest.raises, assertThrows, etc.)
```

After writing these characterization tests, run the full test suite. Everything
should be green. This is your baseline -- if anything is already failing,
investigate before proceeding.

### Refactor

Now change the code. The tests act as a safety net:

- Make a change
- Run tests
- If green, continue
- If red, the change broke existing behavior -- fix it before moving on

Keep changes small and incremental. A refactor that touches 15 files at once
and then has 8 failing tests is much harder to debug than a series of small
changes, each verified individually.

### When Tests Break

A failing test after a refactor step means one of two things:

1. **The refactor changed behavior** -- this is a regression. Undo or fix the
   change so the test passes again.
2. **The test was coupled to implementation** -- if the behavior is preserved
   but the test was asserting on internal structure (method call order, private
   state, specific SQL queries), update the test to assert on behavior instead.

Distinguishing between these requires judgment: check whether the test's
*intent* still holds. If the test was "users can log in with valid
credentials" and it's failing because you renamed an internal method, that's
case 2. If it's failing because the login flow now returns a different
response, that's case 1.

## Bug Fix Mode

Use when a defect has been reported. Before touching the code, write a test
that reproduces the bug. Watch it fail — this proves the bug exists and that
your test actually catches it. Then fix the code and verify the test passes.
The test now prevents the regression permanently.

```
test "empty email is rejected":           // reproduces the reported bug
    result = submit_form(email: "")
    assert result.error == "Email required"  // FAILS — bug confirmed

// fix: add validation to submit_form
// test passes — regression prevented permanently
```

The key step is watching the test fail before you fix anything. A test you
write after the fix might pass for the wrong reason — maybe it's testing the
wrong thing, or the bug was never there to begin with. The failure is the
proof.

Bug Fix Mode is the simplest form of TDD and a natural entry point for teams
adopting it. It requires no upfront planning — just reproduce, verify, fix.

## Mode Transitions

Feature Mode and Refactor Mode often interleave in practice. While building a
new feature, you may discover that existing code needs restructuring to support
it. When that happens, pause the feature work, apply Refactor Mode to the
existing code (characterize, refactor, verify), then resume Feature Mode for
the new functionality. Bug Fix Mode can interrupt either: when a defect
surfaces during feature work or a refactor, pause, reproduce the bug with a
failing test, fix it, then resume the original mode. The key is recognizing
which mode you're in so you apply the right workflow: red-green for new
behavior, stay-green for existing, reproduce-then-fix for defects.

## When TDD Feels Hard

If writing a test feels painful, that's usually a signal about the design, not
the testing. Tests are the first client of your code — if they're hard to
write, the interface is probably hard to use.

| Problem | Signal | Response |
|---------|--------|----------|
| Don't know what to test | Staring at a blank test file | Write the assertion first (what should be true?), then work backward to the setup |
| Test is hard to write | Excessive setup or mocking needed | Simplify the interface — decompose the function or reduce its dependencies |
| Must mock everything | Every collaborator needs a fake | Use dependency injection — code is too coupled |
| Test setup is enormous | Can't write the test without building a world first | Extract factory helpers, or simplify the design |

The pattern: test hard to write = design unclear. When TDD feels painful,
treat it as a diagnostic. The test is telling you something about the code.
Listen to it before reaching for workarounds.
