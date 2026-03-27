# Composition Patterns

Read this when the SKILL.md summary isn't enough detail for your specific
composition pattern.

## Contents

- [Standalone Functions Over Methods](#standalone-functions-over-methods)
- [Generator Pipelines](#generator-pipelines)
- [itertools and Comprehensions](#itertools-and-comprehensions)
- [functools for Reusable Composition](#functools-for-reusable-composition)

---

## Standalone Functions Over Methods

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

## Generator Pipelines

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

## itertools and Comprehensions

Reach for `itertools` before manual loops for grouping, batching, chaining,
or filtering (`chain`, `groupby`, `islice`, `batched` 3.12+). Use
comprehensions for straightforward map/filter; switch to a generator
pipeline or explicit loop when logic needs intermediate variables.

## functools for Reusable Composition

The `functools` module provides building blocks for composing behavior
without writing boilerplate classes or closures.

### partial — Fix Arguments to Create Specialized Callables

Useful for callbacks, pipeline stages, and configuring generic functions for
a specific context:

```python
from functools import partial

def retry(fn, *, max_attempts: int = 3, delay: float = 1.0): ...

# Create a pre-configured variant:
retry_api_call = partial(retry, max_attempts=5, delay=2.0)
```

### singledispatch — Dispatch on First Argument Type

Python's idiomatic alternative to visitor patterns or isinstance chains:

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

### cache / lru_cache — Memoize Pure Functions

`cache` (3.9+) is unbounded; `lru_cache` evicts least-recently-used
entries. Only use on functions with hashable arguments and no side effects.

```python
from functools import cache

@cache
def fibonacci(n: int) -> int:
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
```

### wraps — Preserve Metadata in Decorators

Without `wraps`, decorated functions lose their name and type hints.
Always use it when writing decorators.

```python
from functools import wraps
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

def log_calls(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)  # preserves fn.__name__, __doc__, __annotations__
    def wrapper(*args, **kwargs) -> T:
        print(f"Calling {fn.__name__}")
        return fn(*args, **kwargs)
    return wrapper
```
