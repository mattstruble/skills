# Test Levels: Tradeoff Guide

The Test Desiderata properties don't carry equal weight at every test level. This reference provides deeper guidance on how to balance them when writing unit, integration, and end-to-end tests.

## Unit Tests

Unit tests are the foundation. They should be the majority of your test suite and they should be cheap to write, fast to run, and easy to understand.

**Prioritize these properties:**
- **Isolated**: Absolutely. Each unit test runs independently -- no shared state, no ordering dependence, no implicit setup from other tests.
- **Fast**: Milliseconds per test. If a unit test touches the network, a real database, or the file system, reconsider. Use in-memory fakes or simple stubs.
- **Specific**: When a unit test fails, the developer should immediately know what broke. Keep the scope narrow enough that the failure message tells the story.
- **Structure-insensitive**: This is where most AI-generated tests go wrong. A unit test should test the *interface*, not the *implementation*. Assert on what the function returns or what observable side effect it produces, not on which internal methods were called in which order.
- **Composable**: Each unit test covers one behavioral dimension. Combine passing tests to reason about the whole -- don't cram multiple concerns into one test.

**Acceptable tradeoffs:**
- **Predictive**: Unit tests don't prove the system works end-to-end. That's fine. They prove individual units behave correctly in isolation. Predictiveness comes from higher-level tests.
- **Behavioral**: Sometimes you need to test a specific code path (error handling, edge cases) that isn't directly visible to the external caller. That's OK, but prefer testing through the public interface when possible.

**What to test at this level:**
- Pure logic: computations, transformations, validations
- State transitions: given this starting state and this input, what's the new state?
- Error handling: what happens with invalid input, missing data, boundary conditions?
- Edge cases: empty collections, nil/null values, maximum sizes, concurrent scenarios

**What NOT to test at this level:**
- That your ORM correctly maps to a database (that's the ORM's job)
- That two classes interact correctly (that's integration)
- Default values of data structures (that's testing the language)
- That a mock was called with specific arguments (that's testing your implementation)

## Integration Tests

Integration tests verify that components work together correctly. They are intentionally less isolated and slower than unit tests, and that's the point.

**Prioritize these properties:**
- **Predictive**: The whole purpose of integration tests. They answer: "do these pieces actually work together?" Use real databases (even if in-memory like SQLite), real message queues (even if local), real HTTP calls (even if to a test server).
- **Behavioral**: Test behaviors that emerge from component interaction. "When a user submits a form, a record appears in the database and an email job is enqueued."
- **Deterministic**: Even though you're using more real infrastructure, control for nondeterminism. Use fixed seeds, frozen clocks, and reset state between tests.
- **Readable**: Integration tests tend to be longer. Combat complexity with clear naming, helper functions that express intent, and comments that explain *why* a particular integration point is being tested.

**Acceptable tradeoffs:**
- **Fast**: Integration tests are inherently slower. Aim for seconds, not milliseconds. If they take minutes each, look for opportunities to reduce scope.
- **Isolated**: Integration tests may share infrastructure (a test database, a message broker). Manage this with per-test transactions, cleanup hooks, or unique identifiers -- but don't obsess over perfect isolation if the cost is excessive mocking that defeats the purpose.
- **Specific**: When an integration test fails, it might take more investigation to find the cause. That's an inherent tradeoff. Mitigate by keeping each integration test focused on one integration point.

**What to test at this level:**
- Database queries return expected data for given inputs
- API endpoints accept requests and return correct responses
- Message producers and consumers communicate correctly
- File processing pipelines produce expected outputs
- Authentication and authorization flows work end-to-end

**What NOT to test at this level:**
- Every edge case of individual functions (that's unit test territory)
- UI layout and styling (that's e2e or visual testing)
- Performance characteristics (that's load/performance testing)

## End-to-End Tests

E2e tests verify that the system works as a user would experience it. They are the most expensive to write and maintain, and the slowest to run, but they provide the most confidence.

**Prioritize these properties:**
- **Predictive**: Maximum predictiveness. If the e2e tests pass, the system is likely to work in production. This is the only test level that can make that claim.
- **Behavioral**: Test real user journeys, not implementation details. "A user can sign up, create a project, invite a collaborator, and the collaborator can see the project."
- **Inspiring**: When the e2e suite passes, the team should feel confident shipping.

**Acceptable tradeoffs:**
- **Fast**: E2e tests are slow. Accept it. Run them less frequently (pre-merge, nightly) if needed.
- **Specific**: When an e2e test fails, it might point to a broad area rather than a specific line. That's OK -- the unit and integration tests should handle specificity.
- **Writable**: E2e tests are expensive to write and maintain. That's why you write few of them, focused on critical paths.
- **Isolated**: E2e tests may depend on external services, test environments, or ordered setup. Minimize this where possible, but don't sacrifice predictiveness for isolation.

**What to test at this level:**
- Critical user journeys (sign up, purchase, core workflow)
- Cross-service communication in distributed systems
- Deployment verification (smoke tests)

**What NOT to test at this level:**
- Edge cases (too many e2e tests make the suite slow and flaky)
- Internal error handling (test at the unit level)
- Every permutation of input (that's what unit tests with composability are for)

## The Testing Pyramid in Practice

The traditional testing pyramid -- many unit tests, fewer integration tests, very few e2e tests -- exists because of these tradeoffs:

```
         /  E2E  \        Few, slow, highly predictive
        /----------\
       / Integration \    Moderate count, moderate speed
      /----------------\
     /    Unit Tests     \  Many, fast, highly specific
    /____________________\
```

This isn't dogma -- some systems benefit from a different shape (more integration tests for a CRUD app, more e2e tests for a critical workflow). But the reasoning behind the pyramid is sound: invest most in the tests that give you the fastest feedback loop (unit), and use higher-level tests strategically for confidence that can't come from unit tests alone.

Follow this distribution naturally: generate thorough unit tests for logic, targeted integration tests for component boundaries, and suggest (but not necessarily generate) e2e tests for critical paths.
