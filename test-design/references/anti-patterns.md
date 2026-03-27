# Anti-Patterns and Patterns: Detailed Examples

Language-agnostic pseudocode examples. See `python.md`, `typescript.md`, and `go.md` in this directory for idiomatic implementations in each language.

## Anti-Patterns

### Asserting default values and echo-back values

Testing that a newly constructed object has its default values is testing the language's construction machinery, not your behavior. These assertions never catch a real bug -- they only break when you intentionally change a default.

**Echo-back assertions** are a subtler variant: verifying that a create/build method returns the same values you passed in. Prefer asserting on *derived* or *consequential* state -- things the system computed or decided.

**Violates: behavioral, structure-insensitive.**

**Before:**
```
test "user creation":
    user = createUser("alice", "alice@example.com")
    assert user.name == "alice"           // echo-back -- just parroting inputs
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

Mocking every collaborator and asserting that specific methods were called with specific arguments makes the test a mirror of the implementation. Rename an internal method? Test breaks. Add a caching layer? Test breaks. But introduce a bug in the actual logic? Test still passes.

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

Private methods are implementation details. Test the public interface that uses them. If a private method is complex enough that you feel it needs direct testing, that's a signal it should be extracted into its own unit.

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

When a test has 30 lines of object construction and only 2 lines of actual testing, the reader has to wade through noise. Use factory functions or builders that set sensible defaults and only specify the values that matter.

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

Snapshots capture *everything* about an output, so they break on any change -- including cosmetic ones (whitespace, key ordering). The error is "the output changed" with a diff of the entire blob, which tells you nothing about *what* actually broke.

Use snapshots only for outputs where the exact format is the contract (API response schemas, serialization formats).

**Violates: specific, behavioral.**

**Before:**
```
test "user profile response":
    response = api.getProfile("alice")
    assertMatchesSnapshot(response)    // breaks on any change
```

**After:**
```
test "user profile response includes required fields":
    response = api.getProfile("alice")
    assert response.username == "alice"
    assert response.email != null
    assert response.memberSince != null
```

---

### Flaky tests

A test that sometimes passes and sometimes fails teaches developers to ignore test failures. Common causes: reliance on the real clock, uncontrolled concurrency, shared database state, floating-point comparison without tolerance, ordering assumptions on unordered collections.

Fix the source of nondeterminism rather than adding retries.

**Violates: deterministic, isolated, inspiring.**

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

If five tests all set up the same scenario and each checks one slightly different field, you likely need one test with a focused assertion and a separate test for each genuinely different behavior.

**Violates: composable, writable.**

**Before:**
```
test "order response has user_id":    assert response.user_id == "u1"
test "order response has status":     assert response.status == "pending"
test "order response has items":      assert response.items != null
test "order response has total":      assert response.total == 29.99
test "order response has created_at": assert response.created_at != null
```

**After:**
```
test "new order starts in pending status":
    order = service.create(user_id="u1", items=[...])
    assert order.status == "pending"   // the decision the system made

test "order total is calculated from items":
    order = service.create(user_id="u1", items=[Item(price=10), Item(price=19.99)])
    assert order.total == 29.99        // derived computation
```

---

## Patterns

### Factory functions over raw constructors

Create helpers that build test objects with sensible defaults. Tests only specify the fields relevant to their scenario.

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

Each test should verify one aspect of behavior. Not one assertion (sometimes you need a few to verify a single behavior), but one *concern*.

**Before:**
```
test "place order":
    order = placeOrder(cart, user)
    assert order.status == CONFIRMED
    assert inventory.quantity == originalQuantity - cart.quantity
    assert emailer.sentConfirmationTo(user.email)
    assert order.total == cart.subtotal + TAX
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

Organize each test into three clear phases with blank lines between them:

```
test "expired subscription blocks access":
    sub = makeSubscription(expiresAt=YESTERDAY)   // Arrange

    result = sub.checkAccess()                    // Act

    assert result == ACCESS_DENIED                // Assert
```

### Test boundary behavior

The happy path is the easiest test to write and the least likely to catch bugs. Focus on edge cases, error conditions, and boundary values: empty input, null/nil, concurrent access, boundary of valid ranges.

### Fakes and test doubles

- **Simple stateless interfaces** (tax calculator): a stub returning canned responses is fine.
- **Stateful collaborators** (repository): fakes with real in-memory state give more predictive tests.
- **External boundaries** (network, payment processors): always mock or stub at the unit level -- slow, non-deterministic, outside your control. At the integration level, prefer real or local equivalents.

Verify outcomes (data persisted, state changed), not interactions (method called with args).
