---
name: python-design
description: Python-specific design patterns and idioms for writing clean, well-structured Python code. Covers Protocols vs ABCs, frozen dataclasses, TypedDict, generators and itertools for composition, functools (partial, singledispatch, cache), validation boundaries (Pydantic at edges, dataclasses internally), context managers, error hierarchies, and advanced typing patterns (TypeVar, generics, @overload, TypeGuard). Use this skill whenever writing or reviewing Python code, designing Python APIs, choosing between Python-specific abstractions (Protocol vs ABC, TypedDict vs dataclass, Enum vs string), or refactoring Python modules. Also trigger when the user asks how to structure a Python module, when to use Pydantic vs dataclasses, how to design a clean Python interface, how to organize domain objects, or when to use TypeVar and generics — even if they don't explicitly ask about "design patterns". Complements the language-agnostic software-design skill with concrete Python tooling. NOT for debugging Python errors, framework-specific setup (Django, Flask, FastAPI config), package management, or writing tests (see test-design).
---

# Python Design Patterns

Python-specific patterns for expressing clean software design. This skill
handles the "how in Python" — for the underlying design philosophy (why
small interfaces, why composition, why immutability), see the
`software-design` skill.

> **Advanced patterns** (TypeVar, @overload, TypeGuard, async, match/case,
> module organization): see [`references/advanced-patterns.md`](references/advanced-patterns.md).

---

## Quick Reference: Choosing the Right Abstraction

These decisions come up constantly. Use this table as a first pass, then
read the detailed sections below when context makes the choice less obvious.

**Data containers — pick based on what the data *is*, not just its shape:**

| Situation | Reach for | Why |
|---|---|---|
| External input needing validation (API, config, files) | Pydantic `BaseModel` | Validates + coerces at the boundary |
| JSON/API input that stays dict-compatible (already trusted) | `TypedDict` | Zero overhead, serializable, type-safe |
| Domain object with a meaningful name (Order, UserSummary) | `@dataclass(frozen=True)` | Immutable, hashable, identity beyond "bag of keys" |
| Lightweight immutable record, supports unpacking | `NamedTuple` | Lighter than dataclass, tuple semantics |
| Fixed set of choices (statuses, modes, event types) | `Enum` / `StrEnum` | Prevents typos, exhaustive matching |
| Collection that shouldn't mutate after creation | `tuple` / `frozenset` | Signals intent, prevents accidental mutation |

**The TypedDict vs frozen dataclass boundary:** If the data has a name that
means something in your domain — `OrderSummary`, `UserStats`,
`DeliveryResult` — use a frozen dataclass. It represents something, not
just a structure. If the data is genuinely dict-shaped and needs to stay a
plain dict for serialization or library interop — API responses, JSON
payloads, config dicts — use TypedDict.

**Interface contracts:**

| Need | Reach for | Why |
|---|---|---|
| Caller-facing contract | `Protocol` | Structural typing, no inheritance coupling |
| Shared implementation for authors | `ABC` | Callers type against Protocol, not the ABC |
| Shared behavior across unrelated classes | Mixin | Implementation without contract |

**Module hygiene:** Define `__all__` in every module that has a public API.
This is a one-line habit that makes the intended interface explicit and
prevents internal helpers from leaking. Place it right after imports.

```python
__all__ = ["process_orders", "Order", "OrderSummary", "OrderError"]
```

---

## Type Contracts

### Protocols for Caller Contracts

Define caller-facing interfaces as `typing.Protocol`. Protocols use
structural typing: any object with the right methods satisfies the contract
without inheriting from anything. This is Python's way of expressing focused
interfaces — the caller declares what it needs, and any implementation that
matches works.

```python
from typing import Protocol

class Renderable(Protocol):
    def render(self) -> str: ...

# Any class with a render() -> str method satisfies this.
# No inheritance required, no registration, no coupling.
def display(item: Renderable) -> None:
    print(item.render())
```

Protocols prevent interface pollution because they can't carry private
attributes, default implementations, or class variables. The contract stays
focused on what the caller actually uses. Use ABCs when implementors need
shared logic — but callers always type against the Protocol, not the ABC.

### ABCs for Implementor Convenience

Use `abc.ABC` when implementors benefit from shared logic — argument
parsing, error wrapping, common setup. Callers type against the Protocol;
the ABC is an implementor convenience layer, not the public contract.

```python
from abc import ABC, abstractmethod
from typing import Protocol

class BaseParser(ABC):
    """Shared parsing logic — implementors inherit from this."""
    def parse(self, raw: str) -> dict:
        return self._do_parse(raw.strip())

    @abstractmethod
    def _do_parse(self, cleaned: str) -> dict: ...

class Parser(Protocol):
    """Callers type against this — not BaseParser."""
    def parse(self, raw: str) -> dict: ...
```

### Mixins for Shared Behavior

When multiple classes need the same behavior but don't share an inheritance
chain, extract it into a mixin. Mixins carry implementation but no contract
— keep the Protocol contract separate.

### Type Checker in CI

Run pyright or mypy in CI. Static analysis enforces Protocol conformance,
catches type mismatches, and validates that refactors don't break contracts.
This replaces runtime assertions and manual review as the enforcement
mechanism.

---

## Data Representation

### Validation Boundaries

External data (API requests, config files, CLI input) needs validation
before entering domain logic. Use Pydantic `BaseModel` at these boundaries
for type validation and coercion. Once validated, convert to internal types
(frozen dataclasses, TypedDicts) — Pydantic models carry validation
overhead and mutability that internal logic doesn't need.

**Before (Pydantic model used throughout — mutable, carries validation overhead):**
```python
class Order(BaseModel):
    product_id: str
    quantity: int
    price: Decimal

def calculate_total(order: Order) -> Decimal:
    return order.price * order.quantity  # order is still mutable
```

**After (Pydantic at the boundary, frozen dataclass internally):**
```python
class CreateOrderRequest(BaseModel):  # validates external input
    product_id: str
    quantity: int
    price: Decimal

@dataclass(frozen=True)
class Order:  # immutable domain object
    product_id: str
    quantity: int
    price: Decimal

def create_order(request: CreateOrderRequest) -> Order:
    return Order(
        product_id=request.product_id,
        quantity=request.quantity,
        price=request.price,
    )

def calculate_total(order: Order) -> Decimal:
    return order.price * order.quantity  # order is immutable
```

### Frozen Dataclasses for Domain Objects

Use `@dataclass(frozen=True)` for any object that represents a concept in
your domain. Freezing prevents accidental mutation and makes them safe to
share across threads or use as dict keys.

```python
from dataclasses import dataclass, replace
from decimal import Decimal

@dataclass(frozen=True)
class OrderSummary:
    total_revenue: Decimal
    order_count: int
    average_value: Decimal

# Update frozen objects with replace() — returns a new instance:
updated = replace(summary, order_count=summary.order_count + 1)
```

Use `slots=True` (Python 3.10+) for memory efficiency when creating many
instances. Use `kw_only=True` when constructors have many fields to prevent
positional argument confusion.

### TypedDict for Dict-Shaped Data

TypedDict is for data that is naturally dictionary-shaped *and* needs to
remain a plain dict — JSON payloads coming in from an API, config dicts
passed to libraries, response bodies going out over the wire. It gives type
safety on structure with zero runtime overhead.

```python
from typing import TypedDict

class ActivityEvent(TypedDict):
    user_id: str
    event_type: str
    timestamp: str
```

The key distinction: if you'd naturally write `data["user_id"]` to access
it, TypedDict is right. If you'd naturally write `summary.total_revenue`,
a frozen dataclass is right.

### Enums Over Magic Strings

When a field or parameter accepts a fixed, known set of values — statuses,
event types, modes, roles, priorities — use `enum.Enum` or `enum.StrEnum`
(3.11+). Enums prevent typos that silently pass, enable exhaustive matching,
and make valid values discoverable via IDE autocomplete.

**Before (magic strings — typos silently pass, no autocomplete):**
```python
def process_order(order_id: str, status: str) -> None:
    if status == "pendin":  # typo — no error raised
        ...
```

**After (StrEnum — typos caught, exhaustive matching possible):**
```python
from enum import StrEnum

class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"

def process_order(order_id: str, status: OrderStatus) -> None:
    if status == OrderStatus.PENDING:  # typo would be a NameError
        ...
```

If the set of values is open-ended (user-provided tags, third-party plugin
names), strings are fine. The question is: "Do I know all valid values at
design time?" If yes, use an Enum.

### NamedTuple for Lightweight Immutable Records

For simple immutable records without methods, `typing.NamedTuple` is lighter
than a frozen dataclass and naturally supports unpacking.

---

## Functions and Composition

Python's strength for composition comes from generators, itertools,
functools, and first-class functions — not class hierarchies.

### Standalone Functions Over Methods

Operations *on* objects (serialization, orchestration, formatting) belong as
standalone functions, not methods on the class. This keeps them testable in
isolation and extensible without modifying the core type.

```python
# Prefer this:
def serialize_order(order: Order) -> dict: ...

# Over this:
class Order:
    def serialize(self) -> dict: ...
```

### Generator Pipelines

When processing stages are streaming transforms, generators compose
naturally without materializing intermediate collections:

```python
# Assume Order has: status, subtotal, total fields
def active_orders(orders):
    return (o for o in orders if o.status != OrderStatus.CANCELLED)

def with_tax(orders, rate):
    return (replace(o, total=o.subtotal * (1 + rate)) for o in orders)

pipeline = with_tax(active_orders(orders), rate=Decimal("0.08"))
```

### itertools and Comprehensions

Reach for `itertools` before manual loops for grouping, batching, chaining,
or filtering (`chain`, `groupby`, `islice`, `batched` 3.12+). Use
comprehensions for straightforward map/filter; switch to a generator
pipeline or explicit loop when logic needs intermediate variables.

### `functools` for Reusable Composition

The `functools` module provides building blocks for composing behavior
without writing boilerplate classes or closures.

**`partial`** — fix some arguments to create a specialized callable. Useful
for callbacks, pipeline stages, and configuring generic functions for a
specific context:

```python
from functools import partial

def retry(fn, *, max_attempts: int = 3, delay: float = 1.0): ...

# Create a pre-configured variant:
retry_api_call = partial(retry, max_attempts=5, delay=2.0)
```

**`singledispatch`** — dispatch on the type of the first argument. Python's
idiomatic alternative to visitor patterns or isinstance chains:

```python
from functools import singledispatch

@singledispatch
def serialize(obj) -> dict:
    raise TypeError(f"Cannot serialize {type(obj)}")

@serialize.register
def _(obj: Order) -> dict:
    return {"id": obj.id, "total": str(obj.total)}

@serialize.register
def _(obj: User) -> dict:
    return {"name": obj.name, "email": obj.email}
```

**`cache` / `lru_cache`** — memoize pure functions. `cache` (3.9+) is
unbounded; `lru_cache` evicts least-recently-used entries. Only use on
functions with hashable arguments and no side effects.

**`wraps`** — preserve the original function's metadata when writing
decorators. Without it, decorated functions lose their name and type hints.

---

## Error Handling

### Shallow Hierarchies

Define a base exception for the domain, then one level of specific errors
beneath it. Callers catch the base or the specific — nothing deeper.

```python
class PaymentError(Exception):
    """Base for all payment domain errors."""

class InsufficientFunds(PaymentError): ...
class CardDeclined(PaymentError): ...
class PaymentTimeout(PaymentError): ...
```

### Never Bare Except

Catch specific exceptions. `except Exception` is the broadest acceptable
catch — and even that should be rare, typically at system boundaries where
you need to convert exceptions to error responses.

**Before (bare except swallows everything including KeyboardInterrupt):**
```python
try:
    result = process_payment(order)
except:
    log.error("Something went wrong")
    return None
```

**After (specific exception, meaningful error handling):**
```python
try:
    result = process_payment(order)
except PaymentTimeout as e:
    log.warning("Payment timed out, retrying: %s", e)
    raise
except PaymentError as e:
    log.error("Payment failed: %s", e)
    return PaymentResult.failed(str(e))
    # Note: don't apply catch-and-convert to security exceptions
    # (PermissionError, auth failures) — those must propagate.
```

### Context Managers for Resource Cleanup

Use `with` statements for anything that acquires and releases a resource:
files, database connections, locks, temporary directories. Write custom
context managers with `contextlib.contextmanager` when the stdlib doesn't
cover your case.

```python
from contextlib import contextmanager

@contextmanager
def db_transaction(conn):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
```

---

## References

| Reference | When to read it |
|-----------|----------------|
| `references/advanced-patterns.md` | Advanced typing (@overload, TypeGuard, generics, TYPE_CHECKING), structural pattern matching, immutability toolkit, async patterns, module organization and docstring conventions |
