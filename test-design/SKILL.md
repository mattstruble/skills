---
name: test-design
description: "Test Design Desiderata -- guides writing focused, resilient tests across all languages and test levels (unit, integration, e2e). Use this skill whenever writing tests, adding test coverage, reviewing test code, fixing failing tests, or delivering features where tests are expected as part of the work. Trigger on any task involving test creation, test refactoring, or test review -- even if the user didn't explicitly say 'write tests' but the task naturally calls for them. Also trigger for fragile-test questions (tests breaking on refactors, what makes a good test, why tests are brittle). NOT for TDD workflow (use test-driven-development skill instead). NOT for test infrastructure setup like CI configuration or test runner configuration. NOT for diagnosing why production code is broken."
---

# Test Design Desiderata

This skill applies Kent Beck's Test Desiderata framework to produce tests that are focused, resilient, and genuinely useful. The core idea: you cannot maximize every desirable property of a test simultaneously -- so make conscious tradeoffs instead of defaulting to "assert everything."

## Language-Specific Patterns

This skill works across all languages. The principles below are universal, but the concrete patterns differ by ecosystem. After reading this file, **also read the reference for the language you're working in**:

- **Python** (pytest, unittest): `references/python.md` — fakes, factory functions, pytest idioms
- **TypeScript/JavaScript** (Jest, Vitest, Mocha): `references/typescript.md` — fakes, jest.fn() patterns, async gotchas
- **Go** (testing, testify): `references/go.md` — fakes, factory functions, table-driven tests, subtests

If the language isn't listed, the principles and anti-patterns here still apply -- just translate the idioms to your language's testing conventions.

## The Tradeoff Mindset

A test that checks every field of every object is not thorough -- it's fragile. A test that mocks every dependency is not isolated -- it's coupled to implementation. More assertions do not mean more confidence; they mean more maintenance and more noise when something breaks.

Before writing any test, ask:
- **What behavior would break that a caller or user would actually notice?** Test that.
- **If I refactored the internals tomorrow, would this test still pass?** If not, you're testing structure, not behavior.
- **Does each assertion earn its keep?** Every assertion is a maintenance commitment. If it doesn't catch a meaningful regression, remove it.

The goal is tests that tell you something useful when they fail and stay out of your way when the code is correct.

## The 12 Properties

These properties come from Kent Beck's Test Desiderata (https://testdesiderata.com). No single test can maximize all of them -- the art is choosing the right tradeoffs for each situation.

| Property | What it means |
|---|---|
| **Isolated** | Tests return the same results regardless of execution order. No shared mutable state. |
| **Composable** | Test different dimensions of variability separately. Combine passing tests to reason about the whole. |
| **Deterministic** | Same code, same result every time. No wall-clock time, random values, or network state without explicit control. |
| **Fast** | Tests run quickly enough that developers actually run them. A slow suite is a skipped suite. |
| **Writable** | Tests should be cheap to write relative to the code they cover. |
| **Readable** | A reader understands what a test checks and why it exists without tracing through layers of helpers. |
| **Behavioral** | Sensitive to changes in observable behavior. Insensitive to internal restructuring. |
| **Structure-insensitive** | Renaming a private method, extracting a helper, or reordering internals should not break tests. |
| **Automated** | Tests run without human intervention. Pass or fail programmatically. |
| **Specific** | When a test fails, the cause is obvious. "expected status 'active', got 'pending'" beats "expected true, got false". |
| **Predictive** | If all tests pass, the code is suitable for production. Tests cover scenarios that actually matter. |
| **Inspiring** | Passing tests inspire confidence. Emerges from getting the other properties right. |

## Tradeoffs by Test Level

The desiderata priorities shift depending on what level of test you're writing. Read `references/test-levels.md` — tradeoff priorities per level, what to test at each level — for deeper guidance, but here's the summary:

**Unit tests** -- Optimize for: isolated, fast, specific, structure-insensitive, composable. These form the bulk of your tests. Each one should test one behavioral concern, run in milliseconds, and survive refactors.

**Integration tests** -- Accept: slower, less isolated. Gain: more predictive. These verify that components work together correctly. Mock less (that's the point), but still keep tests focused on specific integration points.

**E2e tests** -- Accept: slowest, least specific, hardest to write. Gain: most predictive, most behavioral. Keep the count low and focused on critical user journeys.

## Anti-Patterns and Why They Fail

Understanding *why* these patterns fail matters more than the rule -- it lets you recognize novel variants. The examples below are language-agnostic pseudocode. See the language-specific reference files for idiomatic implementations in your language.

### Asserting default values and echo-back values

Testing that a newly constructed object has the default values you just defined is testing the language's construction machinery, not your application's behavior. These assertions never catch a real bug -- they only break when you intentionally change a default, at which point the test is just paperwork.

A subtler variant is **echo-back assertions** -- verifying that a create/build method returns the same values you passed in. If you call `createUser("alice", "alice@example.com")` and then assert that `user.name == "alice"`, you're checking that the function echoes inputs back. Prefer asserting on *derived* or *consequential* state -- things the system computed or decided based on the inputs.

**Violates: behavioral, structure-insensitive.**

**Before:**
```
test "user creation":
    user = createUser("alice", "alice@example.com")
    assert user.name == "alice"           // echo-back — just parroting inputs
    assert user.email == "alice@example.com"
    assert user.createdAt != null         // default value check
```

**After:**
```
test "new user starts with pending verification":
    user = createUser("alice", "alice@example.com")
    assert user.status == PENDING         // tests consequential state
    assert verificationEmailSentTo("alice@example.com")
```

---

### Over-mocking and mock-call verification

Mocking every collaborator and then asserting that specific methods were called with specific arguments makes the test a mirror of the implementation. It asserts *how* the code does its work rather than *what* it accomplishes. Rename an internal method? Test breaks. Add a caching layer? Test breaks. But introduce a bug in the actual logic? Test still passes because the mock doesn't care about outcomes.

Using mocks to *provide* dependencies is fine. Using mocks to *verify* internal interactions is where tests become brittle.

**Violates: structure-insensitive, predictive, behavioral.**

**Before:**
```
test "process order":
    mockDb = mock()
    mockEmailer = mock()
    service = OrderService(mockDb, mockEmailer)
    service.process(order)
    assert mockDb.save.calledOnceWith(order)   // verifying HOW, not WHAT
    assert mockEmailer.send.calledOnce()
```

**After:**
```
test "processed order is persisted and confirmation sent":
    db = FakeDatabase()
    emailer = FakeEmailer()
    service = OrderService(db, emailer)
    service.process(order)
    assert db.findOrder(order.id).status == CONFIRMED   // verify outcome
    assert emailer.sentTo(order.customerEmail)
```

---

### Testing private/internal methods directly

Private methods are implementation details. Test the public interface that uses them. If a private method is complex enough that you feel it needs direct testing, that's a signal it should be extracted into its own unit with its own public interface.

**Violates: structure-insensitive.**

**Before:**
```
test "password hashing":
    result = service._hashPassword("secret")   // reaching into internals
    assert result.contains(":")
```

**After:**
```
test "login succeeds with correct password":
    service.register("alice", "secret")
    session = service.login("alice", "secret")
    assert session != null                      // test through the public API
```

---

### Excessive test setup

When a test has 30 lines of object construction and only 2 lines of actual testing, the reader has to wade through noise to find what's being tested. Use factory functions or builders that set sensible defaults and only specify the values that matter for *this particular test*.

**Violates: readable, writable.**

**Before:**
```
test "low inventory triggers reorder":
    product = Product(
        id="p1", name="Widget", sku="WGT-001",
        price=9.99, weight=0.5, category="tools",
        supplier="Acme", leadDays=7, reorderPoint=10,
        quantity=5                                  // only this matters
    )
    warehouse = Warehouse(id="w1", name="Main", location="NY")
    ...
```

**After:**
```
test "low inventory triggers reorder":
    product = makeProduct(quantity=5, reorderPoint=10)  // only relevant fields
    assert product.needsReorder() == true
```

---

### Snapshot/golden-file overuse

Snapshots capture *everything* about an output, so they break on any change -- including cosmetic ones that don't affect behavior (whitespace, key ordering, timestamp formatting). When a snapshot test fails, the error is "the output changed" with a diff of the entire blob, which tells you nothing about *what* actually broke.

Use snapshots sparingly and only for outputs where the exact format is the contract (e.g., API response schemas, serialization formats). For everything else, assert on the specific properties you care about.

**Violates: specific, behavioral.**

**Before:**
```
test "user profile response":
    response = api.getProfile("alice")
    assertMatchesSnapshot(response)    // breaks on any change, even unrelated ones
```

**After:**
```
test "user profile response includes required fields":
    response = api.getProfile("alice")
    assert response.username == "alice"
    assert response.email != null
    assert response.memberSince != null
    // don't assert on formatting, ordering, or fields you don't care about
```

---

### Flaky tests

**Violates: deterministic, isolated, inspiring.**

A test that sometimes passes and sometimes fails teaches developers to ignore test failures. Common causes: reliance on the real clock, uncontrolled concurrency, shared database state between tests, floating-point comparison without tolerance, or ordering assumptions on unordered collections.

Fix the source of nondeterminism rather than adding retries. Retries hide flakiness; they don't fix it.

**Before:**
```
test "subscription expires after 30 days":
    sub = createSubscription()
    assert sub.expiresAt == now() + 30days   // fails depending on when test runs
```

**After:**
```
test "subscription expires 30 days after creation":
    sub = createSubscription(createdAt=FIXED_DATE)
    assert sub.expiresAt == FIXED_DATE + 30days  // deterministic
```

---

### Redundant and duplicated tests

**Violates: composable, writable.**

If five tests all set up the same scenario and each checks one slightly different field of the response, you likely need one test with a focused assertion and a separate test for each genuinely different behavior. Tests should compose -- different tests cover different dimensions of variability, not the same scenario with minor variations.

**Before:**
```
test "order response has user_id":    assert response.user_id == "u1"
test "order response has status":     assert response.status == "pending"
test "order response has items":      assert response.items != null
test "order response has total":      assert response.total == 29.99
test "order response has created_at": assert response.created_at != null
// five tests, same setup, each checking one field
```

**After:**
```
test "new order starts in pending status":
    order = service.create(user_id="u1", items=[...])
    assert order.status == "pending"   // the decision the system made

test "order total is calculated from items":
    order = service.create(user_id="u1", items=[Item(price=10), Item(price=19.99)])
    assert order.total == 29.99        // derived computation

// user_id and items: echo-backs (see "asserting echo-back values" above)
// created_at != null: non-null check adds no behavioral value
```

---

## Writing Good Tests: A Checklist

When writing or reviewing a test, run through these questions:

1. **Does this test have a clear reason to exist?** It should protect against a specific category of regression. If you can't articulate what bug this test would catch, it probably shouldn't exist.

2. **Is the test named for the behavior it verifies?** `test_expired_subscription_blocks_access` is better than `test_subscription_3` or `test_is_active_returns_false`. The name should tell you what broke without opening the file.

3. **Does the test use the minimum setup needed?** Only create the objects and state that directly affect the behavior under test. Everything else is noise. Use factory functions with sensible defaults.

4. **Are assertions focused on observable behavior?** Assert on return values, side effects visible to callers (records created, events emitted, HTTP responses), and state changes that matter. Do not assert on internal method calls, private state, or structural details.

5. **Would this test survive a refactor?** If you extracted a helper, renamed an internal method, or changed the data structure used internally, would this test still pass? If not, it's coupled to structure.

6. **Is each assertion earning its keep?** A test with 15 assertions is usually testing too many things at once. Prefer fewer tests with focused assertions over one test that checks everything.

7. **Is the failure message useful?** When this test fails, will the developer know what went wrong?

## Language-Agnostic Patterns

### Factory functions over raw constructors

Create helpers that build test objects with sensible defaults. Tests only specify the fields relevant to their scenario. This keeps setup minimal and makes it obvious what each test cares about.

For services, a factory that wires up fakes automatically is especially valuable:

**Before:**
```
test "registration sends welcome email":
    repo = FakeUserRepository()
    emailer = FakeEmailer()
    audit = FakeAuditLogger()
    cache = FakeCache()
    service = UserService(repo, emailer, audit, cache)  // 4 deps, test cares about 1
    service.register("alice", "alice@example.com", "s3cr3t")
    assert emailer.sentTo("alice@example.com")
```

**After:**
```
test "registration sends welcome email":
    service, _, emailer = makeService()   // fakes wired up automatically
    service.register("alice", "alice@example.com", "s3cr3t")
    assert emailer.sentTo("alice@example.com")
```

### One behavioral concern per test

Each test should verify one aspect of behavior. Not one assertion (sometimes you need a few assertions to verify a single behavior), but one *concern*. "After placing an order, the inventory decreases and a confirmation email is sent" is two concerns -- split them.

**Before:**
```
test "place order":
    order = placeOrder(cart, user)
    assert order.status == CONFIRMED                                   // concern 1
    assert inventory.quantity == originalQuantity - cart.quantity      // concern 2
    assert emailer.sentConfirmationTo(user.email)                      // concern 3
    assert order.total == cart.subtotal + TAX                          // concern 4
```

**After:**
```
test "placed order has confirmed status":
    order = placeOrder(cart, user)
    assert order.status == CONFIRMED

test "placing order decreases inventory":
    placeOrder(cart, user)
    assert inventory.quantity == originalQuantity - cart.quantity

test "placing order sends confirmation email":
    placeOrder(cart, user)
    assert emailer.sentConfirmationTo(user.email)

test "order total includes tax":
    order = placeOrder(cart, user)
    assert order.total == cart.subtotal + TAX
```

### Arrange-Act-Assert structure

Organize each test into three clear phases: set up the preconditions, perform the action, check the result. A blank line between each phase helps readability.

```
test "expired subscription blocks access":
    sub = makeSubscription(expiresAt=YESTERDAY)   // Arrange

    result = sub.checkAccess()                    // Act

    assert result == ACCESS_DENIED                // Assert
```

### Test boundary behavior, not happy paths alone

The happy path is the easiest test to write and the least likely to catch bugs. Focus energy on edge cases, error conditions, and boundary values. What happens with empty input? Null/nil values? Concurrent access? Inputs at the boundary of valid ranges?

### Mocks, fakes, and test doubles

Not all test doubles are equal:

- **Simple stateless interfaces** (e.g., a tax calculator): a stub returning canned responses is fine.
- **Stateful collaborators** (e.g., a repository): fakes that maintain real in-memory state give you more predictive tests. The fake actually exercises your code's interaction with the storage contract.
- **External boundaries** (network services, payment processors, third-party APIs): always mock or stub these. They're slow, non-deterministic, and outside your control.

The key principle: **verify outcomes, not interactions.** Assert on return values, persisted state, and observable side effects rather than asserting that specific internal methods were called with specific arguments. A test that checks "the order is in the database with status=confirmed" is more valuable than one that checks "db.save was called once with these exact args."
