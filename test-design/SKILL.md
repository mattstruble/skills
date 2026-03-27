---
name: test-design
description: "Test Design Desiderata -- guides writing focused, resilient tests across all languages and test levels (unit, integration, e2e). Use this skill whenever writing tests, adding test coverage, reviewing test code, fixing failing tests, or delivering features where tests are expected as part of the work. Trigger on any task involving test creation, test refactoring, or test review -- even if the user didn't explicitly say 'write tests' but the task naturally calls for them. Also trigger for fragile-test questions (tests breaking on refactors, what makes a good test, why tests are brittle). NOT for TDD workflow (use test-driven-development skill instead). NOT for test infrastructure setup like CI configuration or test runner configuration. NOT for diagnosing why production code is broken."
---

# Test Design Desiderata

This skill applies Kent Beck's [Test Desiderata](https://testdesiderata.com) framework. The core idea: you cannot maximize every desirable property of a test simultaneously, so make conscious tradeoffs instead of defaulting to "assert everything."

## The Tradeoff Mindset

A test that checks every field is not thorough -- it's fragile. A test that mocks every dependency is not isolated -- it's coupled to implementation. More assertions do not mean more confidence; they mean more maintenance.

Before writing any test, ask:
- **What behavior would break that a caller would actually notice?** Test that.
- **If I refactored the internals tomorrow, would this test still pass?** If not, you're testing structure, not behavior.
- **Does each assertion earn its keep?** Every assertion is a maintenance commitment. If it doesn't catch a meaningful regression, remove it.

## The 12 Properties

No single test can maximize all of them -- the art is choosing the right tradeoffs.

| Property | What it means |
|---|---|
| **Isolated** | Same results regardless of execution order. No shared mutable state. |
| **Composable** | Test different dimensions separately. Combine passing tests to reason about the whole. |
| **Deterministic** | Same code, same result. No wall-clock time, random values, or network state without explicit control. |
| **Fast** | Quick enough that developers actually run them. A slow suite is a skipped suite. |
| **Writable** | Cheap to write relative to the code they cover. |
| **Readable** | A reader understands what a test checks and why without tracing through helpers. |
| **Behavioral** | Sensitive to changes in observable behavior. Insensitive to internal restructuring. |
| **Structure-insensitive** | Renaming a private method or extracting a helper should not break tests. |
| **Automated** | Run without human intervention. Pass or fail programmatically. |
| **Specific** | Failure cause is obvious. "expected 'active', got 'pending'" beats "expected true, got false". |
| **Predictive** | If all tests pass, the code is suitable for production. |
| **Inspiring** | Passing tests inspire confidence. Emerges from getting the other properties right. |

## Tradeoffs by Test Level

Read `references/test-levels.md` for deeper guidance. Summary:

**Unit tests** -- Optimize for: isolated, fast, specific, structure-insensitive, composable. Each tests one behavioral concern, runs in milliseconds, survives refactors.

**Integration tests** -- Accept: slower, less isolated. Gain: more predictive. Mock less (that's the point), but stay focused on specific integration points.

**E2e tests** -- Accept: slowest, least specific. Gain: most predictive. Keep the count low, focused on critical user journeys.

## Checklist

When writing or reviewing a test:

1. **Clear reason to exist?** It protects against a specific regression. If you can't say what bug it would catch, it probably shouldn't exist.
2. **Named for the behavior it verifies?** `test_expired_subscription_blocks_access` tells you what broke without opening the file.
3. **Minimum setup needed?** Only create objects that affect the behavior under test. Use factory functions with sensible defaults.
4. **Assertions focused on observable behavior?** Assert on return values, visible side effects, and meaningful state changes. Not internal method calls or private state.
5. **Would survive a refactor?** Extracting a helper or renaming an internal method shouldn't break it.
6. **Each assertion earning its keep?** 15 assertions usually means testing too many things at once.
7. **Useful failure message?** When it fails, will the developer know what went wrong?

## Anti-Patterns and Patterns

Read `references/anti-patterns.md` for detailed examples. The key anti-patterns to watch for:

- **Echo-back assertions**: Asserting the function returns the same values you passed in. Test derived/consequential state instead.
- **Over-mocking**: Mocking every collaborator and verifying calls makes tests mirror the implementation. Use fakes for stateful collaborators; verify outcomes, not interactions.
- **Testing private methods**: Test through the public API. If a private method needs direct testing, it should be its own unit.
- **Excessive setup**: 30 lines of construction for 2 lines of testing. Use factory functions with sensible defaults.
- **Snapshot overuse**: Snapshots break on any change, including cosmetic ones. Assert on specific properties you care about.
- **Flaky tests**: Fix the nondeterminism source (real clock, shared state, uncontrolled concurrency) rather than adding retries.
- **Redundant tests**: Five tests with the same setup checking one field each. Compose tests to cover different behavioral dimensions.

The key patterns to follow:

- **Factory functions over raw constructors**: Helpers that build test objects with sensible defaults, so tests only specify what matters for their scenario.
- **One behavioral concern per test**: Not one assertion, but one *concern*. "inventory decreases and email is sent" is two concerns -- split them.
- **Arrange-Act-Assert**: Three clear phases with blank lines between them.
- **Boundary behavior**: Happy paths are the least likely to catch bugs. Focus on edge cases, error conditions, and boundary values.
- **Fakes over mock-call verification**: At the unit level, verify outcomes (data persisted, state changed) rather than interactions (method called with args). At the integration level, prefer real or local equivalents over mocks.

## References

| Reference | When to read it |
|-----------|----------------|
| `references/anti-patterns.md` | Detailed before/after examples of anti-patterns and patterns |
| `references/test-levels.md` | Deeper guidance on tradeoffs by test level (unit, integration, e2e) |
