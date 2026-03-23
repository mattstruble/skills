---
name: python-design
description: Python-specific design patterns and idioms for writing clean, well-structured Python code. Covers Protocols vs ABCs, frozen dataclasses, TypedDict, generators and itertools for composition, functools (partial, singledispatch, cache), structural pattern matching, context managers, async patterns, advanced typing (@overload, TypeGuard, generics, TYPE_CHECKING), validation boundaries (Pydantic at edges, dataclasses internally), type checker configuration, and error hierarchies. Use this skill whenever writing or reviewing Python code, designing Python APIs, choosing between Python-specific abstractions, or refactoring Python modules. Complements the language-agnostic software-design skill with concrete Python tooling.
---

# Python Design Patterns

Python-specific patterns for expressing clean software design. This skill
handles the "how in Python" -- for the underlying design philosophy (why
small interfaces, why composition, why immutability), see the
`software-design` skill.

---

## Quick Reference: Choosing the Right Abstraction

These decisions come up constantly. Use this table as a first pass, then
read the detailed sections below when context makes the choice less obvious.

**Data containers -- pick based on what the data *is*, not just its shape:**

| Situation | Reach for | Why |
|---|---|---|
| External input needing validation (API, config, files) | Pydantic `BaseModel` | Validates + coerces at the boundary |
| JSON/API input that stays dict-compatible (already trusted) | `TypedDict` | Zero overhead, serializable, type-safe |
| Domain object with a meaningful name (Order, UserSummary) | `@dataclass(frozen=True)` | Immutable, hashable, identity beyond "bag of keys" |
| Lightweight immutable record, supports unpacking | `NamedTuple` | Lighter than dataclass, tuple semantics |
| Fixed set of choices (statuses, modes, event types) | `Enum` / `StrEnum` | Prevents typos, exhaustive matching |
| Collection that shouldn't mutate after creation | `tuple` / `frozenset` | Signals intent, prevents accidental mutation |

**The TypedDict vs frozen dataclass boundary:** If the data has a name that
means something in your domain -- `OrderSummary`, `UserStats`,
`DeliveryResult` -- use a frozen dataclass. It represents something, not
just a structure. If the data is genuinely dict-shaped and needs to stay a
plain dict for serialization or library interop -- API responses, JSON
payloads, config dicts -- use TypedDict.

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
interfaces -- the caller declares what it needs, and any implementation that
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
focused on what the caller actually uses.

### ABCs for Implementor Convenience

Use `abc.ABC` when implementors benefit from shared logic -- argument
parsing, error wrapping, common setup. But callers never type against the
ABC. They type against the Protocol. This keeps the caller's contract
decoupled from the implementor's convenience layer.

```python
from abc import ABC, abstractmethod

class BaseParser(ABC):
    """Shared parsing logic -- implementors inherit from this."""
    def parse(self, raw: str) -> dict:
        cleaned = self._preprocess(raw)
        return self._do_parse(cleaned)

    def _preprocess(self, raw: str) -> str:
        return raw.strip()

    @abstractmethod
    def _do_parse(self, cleaned: str) -> dict: ...

class Parser(Protocol):
    """Callers type against this -- not BaseParser."""
    def parse(self, raw: str) -> dict: ...
```

### Mixins for Shared Behavior

When multiple classes need the same behavior but don't share an inheritance
chain, extract it into a mixin. Mixins carry implementation but no contract
-- keep the Protocol contract separate.

### Type Checker in CI

Run pyright or mypy in CI. Static analysis enforces Protocol conformance,
catches type mismatches, and validates that refactors don't break contracts.
This replaces runtime assertions and manual review as the enforcement
mechanism.

---

## Typing Patterns

Beyond Protocols, Python's type system has tools that make code safer and
more expressive without runtime overhead.

### `@overload` for Polymorphic Signatures

When a function's return type depends on its input, `@overload` tells the
type checker about each variant. Without it, the checker sees a union return
type and callers must narrow manually.

```python
from typing import Literal, overload

@overload
def parse_value(raw: str, as_int: Literal[True]) -> int: ...
@overload
def parse_value(raw: str, as_int: Literal[False] = ...) -> str: ...

def parse_value(raw: str, as_int: bool = False) -> int | str:
    return int(raw) if as_int else raw.strip()
```

### `TypeGuard` and `TypeIs` for Narrowing

When a function checks a type condition, annotating its return narrows the
type in the caller's scope. `TypeIs` (3.13+) narrows in both branches;
`TypeGuard` (3.10+) narrows only the truthy branch.

```python
from typing import TypeIs

def is_str_list(val: list[object]) -> TypeIs[list[str]]:
    return all(isinstance(v, str) for v in val)

def process(data: list[object]) -> None:
    if is_str_list(data):
        # type checker knows data is list[str] here
        print(data[0].upper())
```

### Generics with `TypeVar`

Use `TypeVar` to write functions and classes that work across types while
preserving type relationships.

```python
from typing import TypeVar
from collections.abc import Sequence

T = TypeVar("T")

def first(items: Sequence[T]) -> T | None:
    return items[0] if items else None
```

Python 3.12+ has built-in syntax for this:

```python
def first[T](items: Sequence[T]) -> T | None:
    return items[0] if items else None
```

### `TYPE_CHECKING` for Import Cycles

When two modules need each other's types but not at runtime, gate the
import behind `TYPE_CHECKING`. This breaks the cycle without losing type
safety.

```python
from __future__ import annotations  # only needed here for TYPE_CHECKING
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .order import Order

def process_payment(order: Order) -> None: ...
```

`from __future__ import annotations` makes all annotations strings at
runtime, so the unresolved `Order` reference doesn't cause an import error.

**This is the only scenario where `from __future__ import annotations` is
warranted.** Do not add it as a default import. Modern Python (3.10+)
supports `X | Y` union syntax natively, and PEP 649 (Python 3.14) reverses
PEP 563, making the future import a dead end. Use it strictly to support
`TYPE_CHECKING` guards for circular imports -- nowhere else.

---

## Data Representation

### Validation Boundaries

External data (API requests, config files, CLI input) needs validation
before entering domain logic. Use Pydantic `BaseModel` at these boundaries
for type validation and coercion. Once validated, convert to internal types
(frozen dataclasses, TypedDicts) -- Pydantic models carry validation
overhead and mutability that internal logic doesn't need.

```python
from pydantic import BaseModel

class CreateOrderRequest(BaseModel):
    product_id: str
    quantity: int
    price: Decimal

# After validation, convert to internal domain type:
order = Order(
    product_id=request.product_id,
    quantity=request.quantity,
    price=request.price,
)
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

# Update frozen objects with replace() -- returns a new instance:
updated = replace(summary, order_count=summary.order_count + 1)
```

Use `slots=True` (Python 3.10+) for memory efficiency when creating many
instances. Use `kw_only=True` when constructors have many fields to prevent
positional argument confusion.

### TypedDict for Dict-Shaped Data

TypedDict is for data that is naturally dictionary-shaped *and* needs to
remain a plain dict -- JSON payloads coming in from an API, config dicts
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

When a field or parameter accepts a fixed, known set of values -- statuses,
event types, modes, roles, priorities -- use `enum.Enum` or `enum.StrEnum`
(3.11+). Enums prevent typos that silently pass, enable exhaustive matching,
and make valid values discoverable via IDE autocomplete.

```python
from enum import StrEnum

class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"
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
functools, and first-class functions -- not class hierarchies.

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
def active_orders(orders):
    return (o for o in orders if o.status != OrderStatus.CANCELLED)

def with_tax(orders, rate):
    return (replace(o, total=o.subtotal * (1 + rate)) for o in orders)

pipeline = with_tax(active_orders(orders), rate=Decimal("0.08"))
```

### itertools and Comprehensions

Reach for `itertools` before manual loops for grouping, batching, chaining,
or filtering (`chain`, `groupby`, `islice`, `batched` 3.12+). Use
list/dict/set comprehensions for straightforward map/filter. When the logic
needs intermediate variables or nested conditions, switch to a generator
pipeline or explicit loop.

### `functools` for Reusable Composition

The `functools` module provides building blocks for composing behavior
without writing boilerplate classes or closures.

**`partial`** -- fix some arguments to create a specialized callable. Useful
for callbacks, pipeline stages, and configuring generic functions for a
specific context:

```python
from functools import partial

def retry(fn, *, max_attempts: int = 3, delay: float = 1.0): ...

# Create a pre-configured variant:
retry_api_call = partial(retry, max_attempts=5, delay=2.0)
```

**`singledispatch`** -- dispatch on the type of the first argument. Python's
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

**`cache` / `lru_cache`** -- memoize pure functions. `cache` (3.9+) is
unbounded; `lru_cache` evicts least-recently-used entries. Only use on
functions with hashable arguments and no side effects.

**`wraps`** -- preserve the original function's metadata when writing
decorators. Without it, decorated functions lose their name, docstring, and
type hints.

---

## Structural Pattern Matching

Python 3.10+ `match`/`case` is particularly powerful with enums and
dataclasses. It expresses exhaustive dispatch more clearly than if/elif
chains, and the type checker can verify all cases are handled.

```python
def describe_status(status: OrderStatus) -> str:
    match status:
        case OrderStatus.PENDING:
            return "Awaiting confirmation"
        case OrderStatus.CONFIRMED:
            return "Processing order"
        case OrderStatus.SHIPPED:
            return "In transit"
        case OrderStatus.CANCELLED:
            return "Order cancelled"
```

Match also destructures dataclasses (binding fields to variables in each
`case` arm), which makes it useful for command/event dispatch over union
types. Use match/case when dispatching on type or shape of data. Stick with
if/elif for simple boolean conditions -- match doesn't add clarity there.

---

## Immutability Toolkit

Python doesn't enforce immutability, so reach for these tools intentionally:

- `@dataclass(frozen=True)` for data objects; update with `replace()`
- `tuple` over `list` when the collection shouldn't change after creation
- `frozenset` over `set` for hashable, immutable sets
- `types.MappingProxyType` to expose a read-only view of a dict
- Avoid module-level mutable state -- accept configuration as function
  arguments rather than reading from module globals

---

## Async

### Async-Only APIs

When all consumers are async, provide only the async variant. Maintaining
parallel sync/async implementations doubles the surface area for bugs and
confusion. Name the method directly -- `run`, not `arun`. `async def` is
sufficient signal.

### Structured Concurrency

Prefer `asyncio.TaskGroup` (3.11+) over bare `create_task` calls.
TaskGroups ensure all tasks are awaited and exceptions propagate cleanly.
Dangling tasks are the async equivalent of unclosed file handles.

---

## Error Handling

### Shallow Hierarchies

Define a base exception for the domain, then one level of specific errors
beneath it. Callers catch the base or the specific -- nothing deeper.

```python
class PaymentError(Exception):
    """Base for all payment domain errors."""

class InsufficientFunds(PaymentError): ...
class CardDeclined(PaymentError): ...
class PaymentTimeout(PaymentError): ...
```

### Never Bare Except

Catch specific exceptions. `except Exception` is the broadest acceptable
catch -- and even that should be rare, typically at system boundaries where
you need to convert exceptions to error responses.

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

## Module Organization

### Public API at the Top

Structure modules so the reader encounters the public interface first:
`__all__`, imports, public types, public functions. Implementation details
(private helpers, constants) go below. This mirrors the caller-driven
principle -- the most important audience sees what they need first.

### Docstring Style

Use Google-style docstrings. They read naturally as plain text, which is
how most developers encounter them -- in source code, IDE hovers, and
`help()` output, not rendered Sphinx pages.

```python
def retry(fn: Callable, *, max_attempts: int = 3) -> Any:
    """Call fn up to max_attempts times, re-raising on final failure.

    Args:
        fn: Callable to invoke.
        max_attempts: Number of tries before giving up.

    Returns:
        The return value of fn on success.

    Raises:
        RuntimeError: If all attempts fail.
    """
```

Avoid Sphinx/RST markup in docstrings -- directives like `.. note::`,
`.. warning::`, `.. code-block::`, and field-list syntax like `:param:`,
`:type:`, `:rtype:` are meant for documentation build systems, not for
code that humans read directly. They add visual noise without benefit in
the contexts where docstrings are actually consumed.
