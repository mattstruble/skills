---
name: test-design
description: "Test Design Desiderata -- guides writing focused, resilient tests across all languages and test levels (unit, integration, e2e). Use this skill whenever writing tests, adding test coverage, reviewing test code, fixing failing tests, or delivering features where tests are expected as part of the work. Trigger on any task involving test creation, test refactoring, or test review -- even if the user didn't explicitly say 'write tests' but the task naturally calls for them."
---

# Test Design Desiderata

This skill applies Kent Beck's Test Desiderata framework to produce tests that are focused, resilient, and genuinely useful. The core idea: you cannot maximize every desirable property of a test simultaneously -- so make conscious tradeoffs instead of defaulting to "assert everything."

## Language-Specific Patterns

This skill works across all languages. The principles below are universal, but the concrete patterns differ by ecosystem. After reading this file, **also read the reference for the language you're working in**:

- **Python** (pytest, unittest): `references/python.md`
- **TypeScript/JavaScript** (Jest, Vitest, Mocha): `references/typescript.md`
- **Go** (testing, testify): `references/go.md`

If the language isn't listed, the principles and anti-patterns here still apply -- just translate the idioms to your language's testing conventions.

## The Tradeoff Mindset

A test that checks every field of every object is not thorough -- it's fragile. A test that mocks every dependency is not isolated -- it's coupled to implementation. More assertions do not mean more confidence; they mean more maintenance and more noise when something breaks.

Before writing any test, ask:
- **What behavior would break that a caller or user would actually notice?** Test that.
- **If I refactored the internals tomorrow, would this test still pass?** If not, you're testing structure, not behavior.
- **Does each assertion earn its keep?** Every assertion is a maintenance commitment. If it doesn't catch a meaningful regression, remove it.

The goal is tests that tell you something useful when they fail and stay out of your way when the code is correct.

## The 12 Properties

These properties come from Kent Beck's Test Desiderata (https://testdesiderata.com). They represent things that make tests valuable. No single test can maximize all of them -- the art is choosing the right tradeoffs for each situation.

### Isolated
Tests return the same results regardless of execution order. No shared mutable state between tests, no dependence on what ran before. If a test fails, it fails on its own terms.

### Composable
Test different dimensions of variability separately. Instead of one mega-test that checks input validation AND business logic AND error handling, write separate focused tests for each concern. The combination of passing tests gives you the full picture.

### Deterministic
Same code, same test result. Every time. No dependence on wall-clock time, random values, network state, or file system ordering without explicit control (seeded randomness, frozen clocks, etc.).

### Fast
Tests run quickly enough that developers actually run them. A slow test suite is a test suite that gets skipped. Prefer designs that keep the fast feedback loop intact.

### Writable
Tests should be cheap to write relative to the code they cover. If writing the test is harder than writing the code, the test design is probably wrong -- too much setup, too many mocks, too much ceremony.

### Readable
A reader should understand what a test checks and why it exists without tracing through layers of helpers, fixtures, or abstractions. The motivation for the test should be obvious from reading it. Favor clarity over DRY in test code -- a little repetition is fine if it makes each test self-explanatory.

### Behavioral
Tests should be sensitive to changes in observable behavior. If the behavior changes, the test should fail. The flip side: if behavior hasn't changed, the test should keep passing. This is the most important property for catching real regressions.

### Structure-insensitive
Tests should not break when you refactor internal structure without changing behavior. If renaming a private method, reordering function arguments internally, or extracting a helper class causes test failures, those tests are coupled to structure, not behavior.

### Automated
Tests run without human intervention. No manual verification steps, no "look at the output and check if it seems right." The test either passes or fails programmatically.

### Specific
When a test fails, the cause of failure should be obvious. A test that fails with "expected true, got false" is nearly useless. A test that fails with "expected user.status to be 'active' after calling activate(), but got 'pending'" tells you exactly what broke.

### Predictive
If all tests pass, the code should be suitable for production. Tests should cover the scenarios that actually matter in production, not just the easy cases. This is where integration and e2e tests earn their keep.

### Inspiring
Passing tests should inspire confidence that the code works. This emerges from getting the other properties right -- especially behavioral, predictive, and deterministic.

## Tradeoffs by Test Level

The desiderata priorities shift depending on what level of test you're writing. Read `references/test-levels.md` for deeper guidance on this, but here's the summary:

**Unit tests** -- Optimize for: isolated, fast, specific, structure-insensitive, composable. These form the bulk of your tests. Each one should test one behavioral concern, run in milliseconds, and survive refactors.

**Integration tests** -- Accept: slower, less isolated. Gain: more predictive. These verify that components work together correctly. Mock less (that's the point), but still keep tests focused on specific integration points rather than testing everything end-to-end.

**E2e tests** -- Accept: slowest, least specific, hardest to write. Gain: most predictive, most behavioral. Keep the count low and focused on critical user journeys. These are your "does the whole thing actually work" safety net.

## Anti-Patterns and Why They Fail

Each of these patterns produces tests that score poorly on the desiderata. The explanation of *why* matters more than the rule -- understanding the underlying principle lets you recognize novel variants of these problems. See the language-specific reference files for concrete code examples in your language.

### Asserting default values and echo-back values
Testing that a newly constructed object has the default values you just defined for it is testing the language's construction machinery, not your application's behavior. These assertions never catch a real bug -- they only break when you intentionally change a default, at which point the test is just paperwork. Instead, test the behavior that *depends* on those defaults.

**Violates: behavioral, structure-insensitive.**

A subtler variant is **echo-back assertions** -- verifying that a create/build method returns the same values you passed in. If you call `createUser("alice", "alice@example.com")` and then assert that `user.name == "alice"`, you're checking that the function echoes inputs back, which rarely catches real bugs. Prefer asserting on *derived* or *consequential* state -- things the system computed or decided based on the inputs (status transitions, computed expiry dates, side effects like notifications sent, records persisted and retrievable).

### Over-mocking and mock-call verification
Mocking every collaborator and then asserting that specific methods were called with specific arguments makes the test a mirror of the implementation. It asserts *how* the code does its work rather than *what* it accomplishes. Rename an internal method? Test breaks. Add a caching layer? Test breaks. But introduce a bug in the actual logic? Test still passes because the mock doesn't care about outcomes.

**Violates: structure-insensitive, predictive, behavioral.**

Using mocks to *provide* dependencies is fine. Using mocks to *verify* internal interactions is where tests become brittle. The distinction matters: a mock that returns a canned response is a test double; a mock that asserts it was called with specific args is structural coupling. Every language has its own mock verification syntax -- the principle is the same across all of them.

### Testing private/internal methods directly
**Violates: structure-insensitive.** Private methods are implementation details. Test the public interface that uses them. If a private method is complex enough that you feel it needs direct testing, that's a signal it should be extracted into its own unit with its own public interface.

### Excessive test setup
When a test has 30 lines of object construction and only 2 lines of actual testing, the reader has to wade through noise to find what's being tested. Use factory functions or builders that set sensible defaults and only specify the values that matter for *this particular test*. If the test only cares about inventory quantity, the setup should only mention inventory quantity.

**Violates: readable, writable.**

### Redundant and duplicated tests
**Violates: composable, writable.** If five tests all set up the same scenario and each checks one slightly different field of the response, you likely need one test with a focused assertion and a separate test for each genuinely different behavior. Tests should compose -- different tests cover different dimensions of variability.

### Flaky tests
**Violates: deterministic, isolated, inspiring.** A test that sometimes passes and sometimes fails teaches developers to ignore test failures. Common causes: reliance on the real clock, uncontrolled concurrency, shared database state between tests, floating-point comparison without tolerance, or ordering assumptions on unordered collections. Fix the source of nondeterminism rather than adding retries.

### Snapshot/golden-file overuse
**Violates: specific, behavioral.** Snapshots capture *everything* about an output, so they break on any change -- including cosmetic ones that don't affect behavior (whitespace, key ordering, timestamp formatting). When a snapshot test fails, the error message is "the output changed" with a diff of the entire blob, which tells you nothing about *what* actually broke. Use snapshots sparingly and only for outputs where the exact format is the contract (e.g., API response schemas). For everything else, assert on the specific properties you care about.

## Writing Good Tests: A Checklist

When writing or reviewing a test, run through these questions:

1. **Does this test have a clear reason to exist?** It should protect against a specific category of regression. If you can't articulate what bug this test would catch, it probably shouldn't exist.

2. **Is the test named for the behavior it verifies?** `test_expired_subscription_blocks_access` is better than `test_subscription_3` or `test_is_active_returns_false`. The name should tell you what broke without opening the file.

3. **Does the test use the minimum setup needed?** Only create the objects and state that directly affect the behavior under test. Everything else is noise. Use factory functions with sensible defaults.

4. **Are assertions focused on observable behavior?** Assert on return values, side effects visible to callers (records created, events emitted, HTTP responses), and state changes that matter. Do not assert on internal method calls, private state, or structural details.

5. **Would this test survive a refactor?** If you extracted a helper, renamed an internal method, or changed the data structure used internally, would this test still pass? If not, it's coupled to structure.

6. **Is each assertion earning its keep?** A test with 15 assertions is usually testing too many things at once. If one fails, you have to debug which of the 15 concerns actually broke. Prefer fewer tests with focused assertions over one test that checks everything.

7. **Is the failure message useful?** When this test fails, will the developer know what went wrong? Use assertion messages or structure tests so that the failure naturally describes the problem.

## Language-Agnostic Patterns

### Factory functions over raw constructors
Create helpers that build test objects with sensible defaults. Tests only specify the fields relevant to their scenario. This keeps setup minimal and makes it obvious what each test cares about.

### Arrange-Act-Assert structure
Organize each test into three clear phases: set up the preconditions, perform the action, check the result. This makes tests scannable. A blank line between each phase helps readability.

### One behavioral concern per test
Each test should verify one aspect of behavior. Not one assertion (sometimes you need a few assertions to verify a single behavior), but one *concern*. "After placing an order, the inventory decreases and a confirmation email is sent" is two concerns -- split them.

### Test boundary behavior, not happy paths alone
The happy path is the easiest test to write and the least likely to catch bugs. Focus energy on edge cases, error conditions, and boundary values. What happens with empty input? Null/nil values? Concurrent access? Inputs at the boundary of valid ranges?

### Mocks, fakes, and test doubles
Not all test doubles are equal, and the right choice depends on the collaborator's complexity:

- **Simple stateless interfaces** (e.g., a tax calculator that takes inputs and returns a value): a mock or stub that returns canned responses is fine. Writing a full fake class adds ceremony without payoff.
- **Stateful collaborators** (e.g., a repository that needs to store and retrieve data): fakes that maintain real in-memory state give you more predictive tests than mocks that just record calls. The fake actually exercises your code's interaction with the storage contract.
- **External boundaries** (network services, payment processors, third-party APIs): always mock or stub these. They're slow, non-deterministic, and outside your control.

The key principle: **verify outcomes, not interactions.** Assert on return values, persisted state, and observable side effects rather than asserting that specific internal methods were called with specific arguments. A test that checks "the order is in the database with status=confirmed" is more valuable than one that checks "db.save was called once with these exact args."
