# Core Python Patterns

Read this when the SKILL.md decision tables point you to a pattern and you
need implementation details and worked examples.

## Contents

- [Type Contracts](#type-contracts)
- [Data Representation](#data-representation)
- [Error Handling](#error-handling)

---

## Type Contracts

### Protocols for Caller Contracts

Define caller-facing interfaces as `typing.Protocol`. Protocols use
structural typing: any object with the right methods satisfies the contract
without inheriting from anything. The caller declares what it needs, and
any implementation that matches works.

```python
from typing import Protocol

class Renderable(Protocol):
    def render(self) -> str: ...

# Any class with a render() -> str method satisfies this.
# No inheritance required, no registration, no coupling.
def display(item: Renderable) -> None:
    print(item.render())
```

Protocols use structural typing — any object with matching methods satisfies
the contract without inheriting from anything. Callers don't couple to the
implementor's class hierarchy, which keeps the interface focused on what the
caller actually needs.

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

```python
class TimestampMixin:
    """Adds created_at tracking to any class."""
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def mark_created(self) -> None:
        from datetime import datetime, UTC
        self.created_at = datetime.now(UTC)
```

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
your domain. Freezing blocks attribute reassignment and makes instances
hashable when all fields are themselves hashable. Note: fields that hold
mutable objects (lists, dicts) remain mutable — use `tuple` instead of
`list` for true deep immutability.

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

```python
from typing import NamedTuple

class Point(NamedTuple):
    x: float
    y: float

x, y = Point(1.0, 2.0)  # unpacking works naturally
```

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
