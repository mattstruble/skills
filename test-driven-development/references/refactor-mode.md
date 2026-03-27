# Refactor Mode: Characterization Tests and Safe Restructuring

## Assess Existing Coverage

Before writing new tests, check what's already covered:

- What behaviors do existing tests exercise?
- Do they test through public interfaces or are they coupled to internals?
- Are there gaps for the code paths you'll be modifying?

Tests that are green and test through public interfaces are valuable --
keep them. Tests coupled to implementation details will likely break during
the refactor regardless; note them but don't count them as coverage.

## Identify Behaviors to Preserve

Look at the public interface contracts of the code being refactored:

- Function and method signatures -- what goes in, what comes out
- Side effects visible to callers (records created, events emitted, errors raised)
- Edge cases and error handling that callers depend on

Focus on what external consumers observe, not internal mechanics.

## Write Characterization Tests

For each uncovered behavior, write a test that passes against the current
code. These document what the system *actually does* right now, whether or
not that was the original intent.

```
// Capture current behavior before touching the code.
// These tests don't judge whether the behavior is ideal -- they pin it.

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
```

Run the full suite after writing characterization tests. Everything should
be green -- this is your baseline. If anything is already failing,
investigate before proceeding.

## Make Changes Incrementally

Now change the code. The tests are your safety net:

- Make a change
- Run tests
- If green, continue
- If red, the change broke behavior -- fix before moving on

Keep changes small and incremental. A refactor touching 15 files with 8
failing tests is much harder to debug than a series of small changes
verified individually.

## When Tests Break

A failing test after a refactor step means one of two things:

1. **The refactor changed behavior** -- this is a regression. Undo or fix
   so the test passes again.
2. **The test was coupled to implementation** -- if behavior is preserved but
   the test asserted on internal structure (method call order, private state,
   specific SQL queries), update the test to assert on behavior instead.

Distinguishing requires judgment: check whether the test's *intent* still
holds. If "users can log in with valid credentials" fails because you
renamed an internal method, that's case 2. If it fails because the login
flow returns a different response, that's case 1.

## When Characterization Tests Reveal Bugs

If a characterization test reveals behavior that is clearly a defect (not
just undocumented), pin the current behavior anyway. Fix the bug in a
separate Bug Fix Mode cycle after the refactor is complete -- mixing bug
fixes into a refactor makes failures harder to attribute.
