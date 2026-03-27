---
name: python-design
description: Python-specific design patterns and idioms for writing clean, well-structured Python code. Use this skill whenever writing or reviewing Python code, designing Python APIs, choosing between Python-specific abstractions (Protocol vs ABC, TypedDict vs dataclass, Enum vs string), or refactoring Python modules. Also trigger when the user asks how to structure a Python module, when to use Pydantic vs dataclasses, how to design a clean Python interface, how to organize domain objects, or when to use TypeVar and generics — even if they don't explicitly ask about "design patterns". Trigger on mentions of functools (partial, singledispatch, cache), generator pipelines, validation boundaries (Pydantic at edges, dataclasses internally), context managers, error hierarchies, or advanced typing patterns (@overload, TypeGuard). Complements the language-agnostic software-design skill with concrete Python tooling. NOT for debugging Python errors, framework-specific setup (Django, Flask, FastAPI config), package management, or writing tests (see test-design).
---

# Python Design Patterns

Python-specific patterns for expressing clean software design. For the
underlying design philosophy (why small interfaces, why composition, why
immutability), see the `software-design` skill.

---

## Choosing the Right Abstraction

Use these tables as a first pass, then read the relevant reference for
implementation details and worked examples.

**Data containers — pick based on what the data *is*, not just its shape:**

| Situation | Reach for | Why |
|---|---|---|
| External input needing validation (API, config, files) | Pydantic `BaseModel` | Validates + coerces at the boundary |
| JSON/API input that stays dict-compatible (already trusted) | `TypedDict` | Zero overhead, serializable, type-safe |
| Domain object with a meaningful name (Order, UserSummary) | `@dataclass(frozen=True)` | Immutable, hashable, identity beyond "bag of keys" |
| Lightweight immutable record, supports unpacking | `NamedTuple` | Lighter than dataclass, tuple semantics |
| Fixed set of choices (statuses, modes, event types) | `Enum` / `StrEnum` | Prevents typos, exhaustive matching |
| Collection that shouldn't mutate after creation | `tuple` / `frozenset` | Signals intent, prevents accidental mutation |

**TypedDict vs frozen dataclass:** If the data has a domain name
(`OrderSummary`, `UserStats`) — use a frozen dataclass. If the data is
genuinely dict-shaped and must stay a plain dict for serialization or
library interop — use TypedDict. The access pattern tells you:
`data["user_id"]` → TypedDict; `summary.total_revenue` → dataclass.

**Interface contracts:**

| Need | Reach for | Why |
|---|---|---|
| Caller-facing contract | `Protocol` | Structural typing, no inheritance coupling |
| Shared implementation for authors | `ABC` | Callers type against Protocol, not the ABC |
| Shared behavior across unrelated classes | Mixin | Implementation without contract |

---

## Key Patterns

### Validation Boundaries

Pydantic `BaseModel` at the edges, frozen dataclasses inside. External data
(APIs, config, CLI) gets validated by Pydantic, then converted to immutable
domain types. This prevents Pydantic's validation overhead and mutability
from spreading through internal logic.

```python
class CreateOrderRequest(BaseModel):  # boundary — validates external input
    product_id: str
    quantity: int
    price: Decimal

@dataclass(frozen=True)
class Order:  # internal — immutable, no validation overhead
    product_id: str
    quantity: int
    price: Decimal

def create_order(request: CreateOrderRequest) -> Order:
    return Order(**request.model_dump())
```

### Protocols Over ABCs for Callers

Define caller-facing interfaces as `Protocol`. Any object with matching
methods satisfies the contract — no inheritance required. Use ABCs only when
implementors need shared logic; callers always type against the Protocol.

### Composition via Functions, Not Class Hierarchies

Python's composition strength comes from generators, `itertools`,
`functools`, and first-class functions. Prefer standalone functions over
methods for operations *on* objects (serialization, formatting,
orchestration). Generator pipelines compose streaming transforms without
materializing intermediate collections.

### Shallow Error Hierarchies

One base exception per domain, one level of specific errors beneath it.
Callers catch the base or the specific — nothing deeper. Use context
managers (`contextlib.contextmanager`) for resource cleanup.

### Module Hygiene

Define `__all__` in every module with a public API — place it after imports.
Structure modules so readers encounter the public interface first. Run
pyright or mypy in CI to enforce Protocol conformance and catch type
mismatches.

```python
__all__ = ["process_orders", "Order", "OrderSummary", "OrderError"]
```

---

## References

| Reference | When to read it |
|-----------|----------------|
| [`references/core-patterns.md`](references/core-patterns.md) | Full examples for type contracts (Protocols, ABCs, Mixins), data representation (frozen dataclasses, TypedDict, Enums, NamedTuple), error hierarchies, and context managers |
| [`references/composition.md`](references/composition.md) | Generator pipelines, itertools, functools (partial, singledispatch, cache, wraps), standalone functions vs methods |
| [`references/advanced-patterns.md`](references/advanced-patterns.md) | Advanced typing (@overload, TypeGuard, generics, TYPE_CHECKING), structural pattern matching, immutability toolkit, async patterns, module organization and docstring conventions |
