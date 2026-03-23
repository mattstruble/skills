# Advanced Python Patterns

Supplementary reference for less-frequently-needed Python patterns. Read
when the core SKILL.md guidance isn't enough for your specific situation.

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
from __future__ import annotations  # defers annotation evaluation so "Order" isn't resolved at import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .order import Order

def process_payment(order: Order) -> None: ...
```

`from __future__ import annotations` makes all annotations strings at
runtime, so the unresolved `Order` reference doesn't cause a `NameError`
at import time.

**This is the only scenario where `from __future__ import annotations` is
warranted.** Modern Python (3.10+) supports `X | Y` union syntax natively,
and PEP 649 (Python 3.14) makes lazy annotation evaluation the default,
deprecating PEP 563. Avoid it in new code except for this `TYPE_CHECKING`
pattern.

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
        case _:
            raise ValueError(f"Unhandled status: {status}")
```

Match also destructures dataclasses (binding fields to variables in each
`case` arm), which makes it useful for command/event dispatch over union
types. Use match/case when dispatching on type or shape of data. Stick with
if/elif for simple boolean conditions — match doesn't add clarity there.

**Before (if/elif chain):**
```python
def handle_event(event: Event) -> None:
    if isinstance(event, OrderPlaced):
        send_confirmation(event.order_id)
    elif isinstance(event, PaymentReceived):
        fulfill_order(event.order_id, event.amount)
    elif isinstance(event, OrderCancelled):
        refund(event.order_id)
    else:
        log_unknown(event)
```

**After (match/case with dataclass destructuring):**
```python
def handle_event(event: Event) -> None:
    match event:
        case OrderPlaced(order_id=oid):
            send_confirmation(oid)
        case PaymentReceived(order_id=oid, amount=amt):
            fulfill_order(oid, amt)
        case OrderCancelled(order_id=oid):
            refund(oid)
        case _:
            log_unknown(event)
```

---

## Immutability Toolkit

Python doesn't enforce immutability, so reach for these tools intentionally:

- `@dataclass(frozen=True)` for data objects; update with `replace()`
- `tuple` over `list` when the collection shouldn't change after creation
- `frozenset` over `set` for hashable, immutable sets
- `types.MappingProxyType` to expose a read-only view of a dict
- Avoid module-level mutable state — accept configuration as function
  arguments rather than reading from module globals

---

## Async Patterns

### Async-Only APIs

When all consumers are async, provide only the async variant. Maintaining
parallel sync/async implementations doubles the surface area for bugs and
confusion. Name the method directly — `run`, not `arun`. `async def` is
sufficient signal.

**Before (unnecessary sync/async duplication):**
```python
class DataFetcher:
    def fetch(self, url: str) -> bytes:
        return requests.get(url).content

    async def afetch(self, url: str) -> bytes:
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                return await r.read()
```

**After (async-only, shared session with proper lifecycle):**
```python
class DataFetcher:
    async def __aenter__(self) -> "DataFetcher":
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._session.aclose()

    async def fetch(self, url: str) -> bytes:
        # If url is user-supplied, validate scheme and host against an
        # allowlist before calling get() to prevent SSRF.
        async with self._session.get(url) as r:
            r.raise_for_status()
            return await r.read()

# Usage:
async with DataFetcher() as fetcher:
    data = await fetcher.fetch("https://api.example.com/data")
```

### Structured Concurrency

Prefer `asyncio.TaskGroup` (3.11+) over bare `create_task` calls.
TaskGroups ensure all tasks are awaited and exceptions propagate cleanly.
Dangling tasks are the async equivalent of unclosed file handles.

**Before (bare create_task — tasks can be lost on exception):**
```python
async def fetch_all(urls: list[str]) -> list[bytes]:
    tasks = [asyncio.create_task(fetch(url)) for url in urls]
    return await asyncio.gather(*tasks)
```

**After (TaskGroup — exceptions cancel siblings, nothing leaks):**
```python
async def fetch_all(urls: list[str]) -> list[bytes]:
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch(url)) for url in urls]
    return [t.result() for t in tasks]
```

---

## Module Organization

### Public API at the Top

Structure modules so the reader encounters the public interface first:
`__all__`, imports, public types, public functions. Implementation details
(private helpers, constants) go below. This mirrors the caller-driven
principle — the most important audience sees what they need first.

**Before (public API buried under helpers):**
```python
def _normalize_price(price: Decimal) -> Decimal:
    return price.quantize(Decimal("0.01"))

def _validate_quantity(qty: int) -> None:
    if qty <= 0:
        raise ValueError(f"Quantity must be positive, got {qty}")

def calculate_total(price: Decimal, quantity: int) -> Decimal:
    _validate_quantity(quantity)
    return _normalize_price(price) * quantity
```

**After (public API first, helpers below):**
```python
__all__ = ["calculate_total"]

def calculate_total(price: Decimal, quantity: int) -> Decimal:
    _validate_quantity(quantity)
    return _normalize_price(price) * quantity

# --- private helpers ---

def _normalize_price(price: Decimal) -> Decimal:
    return price.quantize(Decimal("0.01"))

def _validate_quantity(qty: int) -> None:
    if qty <= 0:
        raise ValueError(f"Quantity must be positive, got {qty}")
```

### Docstring Style

Use Google-style docstrings. They read naturally as plain text, which is
how most developers encounter them — in source code, IDE hovers, and
`help()` output, not rendered Sphinx pages.

```python
from collections.abc import Callable
from typing import Any

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

Avoid Sphinx/RST markup in docstrings — directives like `.. note::`,
`.. warning::`, `.. code-block::`, and field-list syntax like `:param:`,
`:type:`, `:rtype:` are meant for documentation build systems, not for
code that humans read directly. They add visual noise without benefit in
the contexts where docstrings are actually consumed.
