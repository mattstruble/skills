# Worked Example: Rate Limiter

Two TDD cycles for a rate limiter that allows N requests per time window
per client. The snippets are pseudo-code -- method signatures omit
language-specific boilerplate for clarity.

## Behavior List (first two cycles shown)

1. Requests within the limit are allowed
2. Requests that exceed the limit are denied
3. The window resets after the time period *(future cycle)*
4. Different clients have independent limits *(future cycle)*

## Cycle 1 -- Tracer Bullet

The simplest behavior that proves the interface works: the happy path.

```
// RED: write the test first, watch it fail
test "first request is allowed":
    limiter = RateLimiter(limit=3)
    result = limiter.check("client-A")
    assert result == ALLOWED

// GREEN: write the minimum code to pass
class RateLimiter:
    init(limit):
        self.limit = limit

    check(client_id):
        return ALLOWED   // hardcoded -- just enough to pass
```

The implementation is obviously incomplete, but the tracer bullet proved
the interface compiles and the test harness works.

## Cycle 2 -- Enforce the Limit

```
// RED: write the next test, watch it fail
test "request beyond limit is denied":
    limiter = RateLimiter(limit=2)
    limiter.check("client-A")   // request 1
    limiter.check("client-A")   // request 2
    result = limiter.check("client-A")   // request 3 -- over limit
    assert result == DENIED

// GREEN: extend the implementation to make both tests pass
class RateLimiter:
    init(limit):
        self.limit = limit
        self.counts = {}   // maps client_id -> request count

    check(client_id):
        count = self.counts[client_id] ?? 0
        if count >= self.limit:
            return DENIED
        self.counts[client_id] = count + 1
        return ALLOWED
```

Behaviors 1 and 2 are covered. Behaviors 3 (window reset) and 4 (client
isolation) remain -- each gets its own cycle.

## Cycle 2 -- Refactor Step

Before adding window-reset logic, extract the count lookup to avoid
duplicating the access pattern:

```
// Extract a helper -- all tests still pass after this change
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

The pattern continues: each remaining behavior (window reset, client
isolation) gets its own RED-GREEN cycle. Each cycle adds one behavior,
keeps all previous tests green.
