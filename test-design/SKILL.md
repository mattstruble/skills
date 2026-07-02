---
name: test-design
description: You MUST consult this skill when writing, reviewing, or fixing tests at any level (unit, integration, e2e). Also trigger when delivering features where tests are expected, when tests break on refactors, or when asking what makes a good test — even if 'write tests' wasn't explicitly requested. NOT for TDD workflow (see test-driven-development), test infrastructure setup (CI config, test runners), or diagnosing production code bugs.
---

# Test Design Desiderata

This skill applies Kent Beck's [Test Desiderata](https://testdesiderata.com) framework. The core idea: you cannot maximize every desirable property of a test simultaneously, so make conscious tradeoffs instead of defaulting to "assert everything."

## The Tradeoff Mindset

A test that checks every field is not thorough -- it's fragile. A test that mocks every dependency is not isolated -- it's coupled to implementation. More assertions do not mean more confidence; they mean more maintenance.

Before writing any test, ask:
- **What behavior would break that a caller would actually notice?** Test that.
- **If I refactored the internals tomorrow, would this test still pass?** If not, you're testing structure, not behavior.
- **Does each assertion earn its keep?** Every assertion is a maintenance commitment. If it doesn't catch a meaningful regression, remove it.

**Apply the same cost/benefit lens to the test suite itself.** Jonathan Blow argues that test infrastructure is maintenance debt in its own right: a faster or extra test mode isn't free -- it's one more thing to maintain for the life of the project. If a test runs rarely, its runtime usually isn't worth optimizing; you risk getting "drowned by one-more-things," each individually reasonable but collectively a burden. The skill's tradeoff mindset applies not just to individual assertions but to the suite as a whole: every piece of test infrastructure should justify its ongoing maintenance cost.

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

**Integration tests** -- Accept: slower, less isolated. Gain: more predictive. Use real or local equivalents -- that's the point. Stay focused on specific integration points.

**E2e tests** -- Accept: slowest, least specific. Gain: most predictive. Keep the count low, focused on critical user journeys.

## Where to Invest

For most codebases, **integration tests return the most value per test written**. Here's why:

- **Unit tests are coupled to internals.** A unit test that passes a mock repository to a service is really testing the service's call sequence, not its behavior. When you refactor -- extract a method, add a caching layer, change a collaborator -- unit tests break even when behavior is unchanged. This is the fragility trap.
- **E2e tests are hard to debug.** When an e2e test fails, the failure could be anywhere in the stack. The signal is real but the diagnosis is expensive.
- **Integration tests hit the middle ground.** High enough to test real correctness (real or local equivalents of databases, HTTP, message queues), low enough that a failure points to a specific component boundary. They survive refactors because they test outcomes, not call sequences.

**Where unit tests are the right choice:**
- Isolated algorithmic logic: parsers, calculators, validators, data transformations
- Pure functions with many input combinations (use parameterized tests)
- Parser combinators and state machines where each rule needs direct verification
- Anything where the "integration" would just be noise -- no real collaborator interaction

**The role of e2e tests:**
Keep a small, curated suite covering the most common user flows and a handful of critical edge cases. Run them religiously -- a failing e2e test is a production risk. Don't let the suite grow large; each addition should be justified by a flow that can't be adequately covered at the integration level.

**The practical bias:** When deciding where to add a new test, default to integration unless there's a clear reason to go lower (pure logic, speed requirements) or higher (critical user journey). This isn't a pyramid -- it's a judgment call, and integration is usually the right default.

**Aim tests where failures actually concentrate.** Jonathan Blow argues that developers often assume two code paths "do the same thing" without validating that assumption -- and that validation is the real testing work. In his experience, crashes concentrate in the most complex subsystems (in his game, the graphics code), not in the simple gameplay logic. Tests that don't exercise the genuinely failure-prone areas aren't really testing the system. The transferable kernel: before adding a test, ask where bugs have actually appeared or are most likely to appear. Spend your test budget on the components with real complexity and real failure history, not on the parts that feel easy to test.

## Deterministic Simulation Testing (DST)

DST is a methodology for testing concurrent, distributed, or fault-tolerant systems where traditional mocking of concurrency is fragile or impossible. The system runs inside a simulation engine that controls every source of nondeterminism — scheduling, I/O, timing, faults — seeded by a single integer. If a bug occurs, replaying the same seed reproduces the exact failure. No flaky tests, no "works on my machine."

### When to use DST

**Good fit:**
- Concurrent systems with complex scheduling (actors, state machines, cooperative schedulers)
- Systems with recovery/supervision logic (crash → restart paths)
- Networked systems where you need to test partial failures, dropped messages, or message reordering
- Any system where the interesting bugs only surface under specific interleavings

**Poor fit:** Sequential logic, pure functions, systems with no meaningful failure modes. For those, unit and integration tests are cheaper and sufficient.

### How it works

The system under test runs in simulation mode on a single thread. The simulation engine controls:
- Which actor or coroutine runs next (scheduling)
- When timeouts and timers fire
- Whether I/O operations succeed, fail, or are delayed
- Message ordering and delivery (drop, reorder, duplicate)

Tests define **invariants** that must hold after every scheduling step, not just at the end. The engine explores many interleavings per run by varying the seed.

### Writing effective simulation tests

**Define structural invariants, not just outcome assertions:**
```
# Instead of: assert final_state == expected
# Write: after every step, no two actors hold the same lock
#        message count_in + count_out == count_produced
```

**Check invariants at recovery boundaries:** After a crash-and-restart, verify the system reaches a consistent state before continuing. Don't only check the happy path end state.

**Use random seeds + many iterations over hand-crafted scenarios:** A single seed that exercises one interleaving is weaker than 10,000 random seeds that collectively explore the space. Hand-crafted scenarios miss the interleavings you didn't think of.

**Inject faults deliberately:** Crash actors mid-operation, drop messages, inject network partitions, delay responses. The recovery path is where bugs hide.

**Seed management:** On failure, print the seed. Plug it back in to reproduce the exact failure deterministically:
```
# Run: seed=42 → FAIL: invariant violated at step 1337
# Reproduce: seed=42 → same failure, every time
```

**Track fault coverage:** Know which fault patterns (crash-before-commit, message-drop-during-handshake, etc.) have been exercised. Gaps in fault coverage are gaps in confidence.

### Production examples

- **TigerBeetle VOPR**: Continuous simulation testing of a distributed database. Runs millions of simulated operations per night, catching bugs that would take months to surface in production. The entire storage engine is designed to run inside the simulator.
- **Tina**: Deterministic scheduling + injectable I/O + seed replay for testing actor recovery. Demonstrates DST applied to a smaller-scale actor system.
- **FoundationDB**: Pioneered simulation testing at scale for distributed systems; the approach is credited with FoundationDB's reliability.

### Architectural prerequisite

DST only works if the system is designed for it: deterministic scheduling, an abstracted I/O layer, and injectable faults. This section covers how to write and run simulation tests. For how to design a system that enables DST — fault isolation, topology, I/O abstraction boundaries — see the `concurrency-design` skill.

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
- **Over-mocking**: Mocking every collaborator and verifying calls makes tests mirror the implementation. Mocks should be rare -- approaching never for stateful collaborators. When you do mock, do it only at coarse-grain system boundaries: external HTTP services, payment processors, third-party APIs. Use fakes with in-memory state for everything else; verify outcomes, not interactions.
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
- **Fakes over mock-call verification**: Verify outcomes (data persisted, state changed) rather than interactions (method called with args). At the integration level, use real or local equivalents. At the unit level, use fakes with in-memory state for stateful collaborators. Reserve mocks for true external boundaries (third-party APIs, payment processors) where a real or fake equivalent isn't practical.

## References

| Reference | When to read it |
|-----------|----------------|
| `references/anti-patterns.md` | Detailed before/after examples of anti-patterns and patterns |
| `references/test-levels.md` | Deeper guidance on tradeoffs by test level (unit, integration, e2e) |
| `concurrency-design` skill | Architectural prerequisites for DST: deterministic scheduling, I/O abstraction, fault isolation |
