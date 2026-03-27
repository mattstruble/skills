# Design Patterns: Before/After Catalog

Complete before/after examples for each design principle. Read the relevant
section when you need a concrete refactoring model for a specific pattern.

## Contents

1. [Purpose and Usefulness](#purpose-and-usefulness) -- earning your place
2. [Minimalism](#minimalism) -- smallest sufficient interface
3. [Focused Interfaces](#focused-interfaces) -- splitting by consumer
4. [Pure Functions](#pure-functions) -- isolating side effects
5. [Immutability](#immutability) -- values over containers
6. [Composition Over Inheritance](#composition-over-inheritance) -- delegation over hierarchies
7. [Declarative Over Imperative](#declarative-over-imperative) -- intent over mechanism
8. [Self-Explanatory Design](#self-explanatory-design) -- names that reveal intent
9. [Honesty](#honesty) -- no hidden behavior
10. [Thoroughness](#thoroughness) -- edge cases and resource cleanup
11. [Longevity Over Trend](#longevity-over-trend) -- abstractions over implementations

---

## Purpose and Usefulness

Every piece of code exists to serve someone -- a caller, a user, a future
maintainer. Before writing anything, be clear about who it serves and what
problem it solves.

- Write code that earns its place. If a function, class, or module doesn't
  serve a clear need, it shouldn't exist yet. Resist speculative abstractions.
- Emphasize usefulness over cleverness. A straightforward solution that's easy
  to call and easy to understand beats an elegant one that requires a tutorial.
- Design from the caller's perspective. What does the consumer actually need?
  Start there, then build inward. Don't expose internal complexity through the
  interface.

**Before:** (speculative abstraction nobody asked for)
```
class DataPipelineOrchestrator:
    def __init__(self, source_adapter, sink_adapter, transformer_chain,
                 retry_policy, metrics_collector, feature_flags):
        ...

    def execute_with_hooks(self, pre_hooks=None, post_hooks=None): ...
    def execute_async(self): ...
    def execute_dry_run(self): ...
```

**After:** (solve the actual problem first)
```
def process_records(records):
    """Filter and transform records. Extend when the need is real."""
    return [transform(r) for r in records if is_valid(r)]
```

---

## Minimalism

"Less, but better." Every line, parameter, abstraction, and dependency should
earn its keep.

- Prefer the smallest interface that serves the caller. Extra methods,
  parameters, and options create surface area for confusion and bugs. You can
  always add later; removing is painful.
- Strip non-essential features, options, and configuration. When in doubt,
  leave it out. The cost of an unused abstraction is paid by every reader who
  has to understand it.
- Avoid premature generalization. Solve the concrete problem first. Extract
  patterns only when repetition proves they're real, not when you imagine they
  might be.

**Before:** (every option imaginable, most never used)
```
def send_email(to, subject, body,
               cc=None, bcc=None, reply_to=None,
               html_body=None, attachments=None,
               priority="normal", read_receipt=False,
               track_opens=False, retry_count=3,
               timeout=30, encoding="utf-8"):
    ...
```

**After:** (start with what callers actually need)
```
def send_email(to, subject, body):
    ...

# When a caller genuinely needs cc/attachments, add them then:
# def send_email(to, subject, body, cc=None, attachments=None): ...
```

---

## Focused Interfaces

Clients should never be forced to depend on things they don't use. This is the
Interface Segregation Principle, and it applies far beyond class hierarchies --
it's a way of thinking about every boundary in your code.

- Split broad interfaces into focused ones. A function that takes 8 parameters
  is probably doing too many things. A module that exports 30 symbols probably
  has multiple responsibilities hiding inside it.
- When an interface feels bloated, ask: "Which callers use which parts?" If
  different callers use different subsets, that's a signal to split.
- Apply this to function signatures, module exports, API endpoints, config
  objects, and data structures -- not just class interfaces.

**Before:** (one config object forces every consumer to know about everything)
```
def process(config):  # config has 12 fields, this function uses 3
    input_path = config.input_path
    output_format = config.output_format
    verbose = config.verbose
    ...  # ignores config.db_url, config.cache_ttl, config.retry_policy, ...
# Every caller must construct a full config even to call this one function
```

**After:** (accept only what you need)
```
def process(input_path, output_format, verbose=False):
    ...
```

---

## Pure Functions

A pure function takes inputs, returns outputs, and does nothing else. No
hidden state, no surprise side effects, no reading from global variables.

- Pure functions are inherently testable -- pass in values, assert on the
  result. No mocking, no setup, no teardown.
- Pure functions are composable -- the output of one feeds directly into
  another.
- When a function needs to do IO or mutate state, isolate that at the
  boundary. Keep the core logic pure and push side effects to the edges.

**Before:** (logic tangled with side effects -- hard to test, hard to reuse)
```
def calculate_discount(user_id):
    user = db.get_user(user_id)          # side effect: DB read
    discount = user.loyalty_years * 0.05
    logger.info(f"Discount for {user_id}: {discount}")  # side effect: logging
    analytics.track("discount_calculated", user_id)     # side effect: network
    return discount
```

**After:** (pure core, side effects pushed to the caller)
```
def calculate_discount(loyalty_years):
    return min(loyalty_years * 0.05, 0.30)

# Caller handles IO:
user = db.get_user(user_id)
discount = calculate_discount(user.loyalty_years)
logger.info(f"Discount for {user_id}: {discount}")
analytics.track("discount_calculated", user_id)
```

---

## Immutability

Mutable state is the primary source of bugs that are hard to reproduce and
hard to reason about. Treat data as values that flow through transformations
rather than containers that get modified in place.

- Default to immutable data structures. Use mutation only when performance
  requires it, and contain it to a small scope.
- Avoid long-lived mutable state. When state is necessary, make ownership and
  lifecycle explicit.
- Prefer returning new values over modifying existing ones. `sorted(items)`
  over `items.sort()` when the caller doesn't expect mutation.

**Before:** (mutates in place -- caller's list is silently changed)
```
def process_items(items):
    items.sort()    # mutates the caller's list
    return items
```

**After:** (return new values; caller's data is untouched)
```
def process_items(items):
    return sorted(items)  # caller's list unchanged
```

---

## Composition Over Inheritance

Build behavior by combining small pieces rather than layering through
inheritance hierarchies.

- Favor function composition and delegation over class inheritance. Inheritance
  couples parent and child tightly and makes the codebase brittle to change.
- When you need shared behavior, extract it into standalone functions or small
  composable units (mixins, decorators, higher-order functions) rather than
  building deep hierarchies.
- Pipelines of transformations are often clearer than inheritance chains.
  `result = persist(transform(validate(data)))` tells you exactly what
  happens. Sequential calls make the order explicit.

**Before:** (deep inheritance to share behavior)
```
class BaseService:
    def log(self): ...
    def validate(self): ...

class UserService(BaseService):
    def notify(self): ...

class AdminService(UserService):  # inherits log, validate, notify — but only needs log + audit
    def audit(self): ...
```

**After:** (compose only what each class actually needs)
```
class UserService:
    def __init__(self, logger, validator, notifier):
        self.logger = logger
        self.validator = validator
        self.notifier = notifier

class AdminService:
    def __init__(self, logger, auditor):
        self.logger = logger
        self.auditor = auditor

# In tests, swap any collaborator: AdminService(logger=FakeLogger(), auditor=FakeAuditor())
```

---

## Declarative Over Imperative

Express *what* should happen rather than *how* it should happen, when the
language and context support it.

- Prefer `map`, `filter`, `reduce` and comprehensions over manual loops when
  the intent is a data transformation.
- Declarative code communicates intent; imperative code communicates mechanism.
  Both have their place, but default to intent.

**Before:** (imperative -- describes the mechanism)
```
result = []
for user in users:
    if user.active:
        result.append(user.email)
```

**After:** (declarative -- describes the intent)
```
result = [user.email for user in users if user.active]
```

When comprehensions become hard to read (nested conditions, side effects), a
named loop is clearer -- don't force it.

---

## Self-Explanatory Design

Code should communicate its purpose without requiring external explanation.

- Choose names that reveal intent. A reader should understand what a function
  does, what a variable holds, and why a module exists from the names alone.
- Structure code so the reader discovers information in the order they need it.
  Public API at the top, implementation details below. High-level flow before
  low-level mechanics.
- Use types as documentation. A well-typed function signature often makes
  docstrings about parameter types redundant.
- When something *isn't* obvious -- a non-obvious performance optimization, a
  workaround for a library bug, a subtle invariant -- that's when comments
  earn their keep. Don't comment the "what" (the code says that); comment the
  "why."

**Before:** (names that hide intent)
```
def proc(d, f=True):
    tmp = []
    for x in d:
        if x[2] > 0:
            tmp.append(x)
    if f:
        tmp = sorted(tmp, key=lambda x: x[1])
    return tmp
```

**After:** (names that reveal intent)
```
def active_users(users, sort_by_name=True):
    active = [u for u in users if u.is_active]
    return sorted(active, key=lambda u: u.name) if sort_by_name else active
```

---

## Honesty

Code should not promise more than it delivers.

- APIs should do what their names suggest -- no hidden side effects, no
  surprising behaviors, no silent failures. A function called `get_user`
  should get a user, not also update a cache and log an analytics event.
- Error handling should be explicit. Make failure modes visible in the type
  system or API contract. Don't swallow errors or return ambiguous sentinels.
- Complexity should be visible, not hidden. If an operation is expensive, the
  API should make that clear, not disguise an O(n^2) operation behind a
  property accessor.

**Before:** (function does more than its name says)
```
def get_user(user_id):
    user = db.query(user_id)
    cache.set(user_id, user)         # hidden side effect — also caches None if user not found
    analytics.track("user_fetched")  # hidden side effect
    if not user:
        return None                  # silent failure
    return user
```

**After:** (name matches behavior; failure is explicit; caller owns the side effects)
```
def get_user(user_id) -> User:
    user = db.query(user_id)
    if not user:
        raise UserNotFoundError(user_id)
    return user

# Caller decides what to do with the result:
user = get_user(user_id)
cache.set(user_id, user)
analytics.track("user_fetched", user_id)
```

---

## Thoroughness

Care about the details. Sloppy handling of edge cases, error paths, and
boundary conditions is a form of disrespect toward users and future
maintainers.

- Handle edge cases explicitly. An empty list, a missing key, a network
  timeout -- these aren't exceptional, they're expected. Design for them.
- Validate at boundaries. Trust nothing that crosses a system boundary (user
  input, API responses, file contents). Validate early, fail clearly.
- Resource cleanup matters. Open files, connections, locks -- make sure they're
  released. Use language-appropriate patterns (context managers, defer, RAII,
  try-with-resources).

**Before:** (assumes the happy path; silent failures on bad input)
```
def parse_config(path):
    data = open(path).read()       # file never closed
    return json.loads(data)        # crashes on malformed JSON with no context
                                   # raises FileNotFoundError with no useful context
```

**After:** (validates input, cleans up resources, fails clearly)
```
def parse_config(path) -> dict:
    if not os.path.exists(path):
        raise ConfigNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigParseError(f"Invalid JSON in {path}: {e}") from e
```

---

## Longevity Over Trend

Favor stable, well-understood approaches over fashionable ones.

- Choose boring technology for core infrastructure. The newest framework is
  exciting; the proven one ships products.
- Depend on abstractions, not implementations. When you must depend on
  something external, wrap it so you can swap it out. The wrapper is a form of
  honesty about what you actually need.
- Write code for the reader who comes after you. Optimize for understanding,
  not for impressing. The most maintainable code is the code that doesn't
  require the original author to explain it.

**Before:** (tightly coupled to a specific library)
```
import redis

class SessionStore:
    def __init__(self):
        self._client = redis.StrictRedis()   # hard-coded to Redis

    def get(self, key):
        return self._client.get(key)

    def set(self, key, value):
        self._client.set(key, value)
```

**After:** (depend on an abstraction; swap the backend without changing callers)
```
from typing import Protocol

class SessionStore(Protocol):
    def get(self, key: str) -> bytes | None: ...
    def set(self, key: str, value: bytes) -> None: ...

class RedisSessionStore:
    def __init__(self, client):   # inject the client
        self._client = client

    def get(self, key):
        return self._client.get(key)

    def set(self, key, value):
        self._client.set(key, value)

# Caller depends on the Protocol, not the implementation:
def save_session(store: SessionStore, session_id: str, data: bytes) -> None:
    store.set(session_id, data)
```
