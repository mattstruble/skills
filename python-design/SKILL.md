---
name: python-design
description: You MUST consult this skill when writing, reviewing, or generating Python code. Also trigger on Python-specific design choices (Protocol vs ABC, TypedDict vs dataclass, Pydantic boundaries), code style anti-patterns (broad exceptions, sentinel defaults, redundant docstrings, unnecessary future imports), or advanced patterns (functools, generator pipelines, typing). NOT for debugging Python errors, framework-specific setup (Django, Flask, FastAPI config), package management, or writing tests (see test-design).
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

**Generics restraint:** `TypeVar` and generics shine in container and collection abstractions — type-safe wrappers, reusable data structures, utility functions like `first(items: Sequence[T]) -> T`. The trap is over-genericizing business logic that only ever has one concrete type: if `UserRepository` will never be anything other than a `UserRepository`, making it `Repository[T]` adds abstraction without value. Even when multiple concrete types exist, if every subclass adds domain-specific methods anyway, the generic base captures only the trivial skeleton — evaluate whether that skeleton justifies the abstraction overhead. A caller-facing `Protocol` often provides more value than a generic concrete base. Reach for generics when the type relationship is genuinely reusable across multiple concrete types; otherwise, name the type directly. See `references/advanced-patterns.md` for `TypeVar` syntax and examples.

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

Split a module when it exceeds ~300 lines or has 3+ distinct
responsibilities — whichever comes first. Prefer flat structure
(`src/formatters.py`) over deep nesting (`src/utils/helpers/formatters/date.py`).

---

## Code Hygiene

### No Unnecessary `from __future__ import annotations`

Only add it for genuine circular type references via `TYPE_CHECKING`. Modern
Python (3.10+) has `X | Y` and `list[int]` natively. See the `TYPE_CHECKING`
section in `references/advanced-patterns.md` for the legitimate use case.

### Specific Exception Types

Never bare `except:` or `except BaseException` — these catch `KeyboardInterrupt`
and `SystemExit`. Never `except Exception` without justification. Look up which
exceptions the called code actually raises and catch those. When genuinely
warranted, add an inline comment explaining why.

```python
# Bad
except Exception:
    log.error("failed")

# Good
except KeyError:
    ...

# Also fine
except (KeyError, TypeError):
    ...

# Acceptable when justified with a comment
# Plugin loader must never crash the host process.
except Exception:
    logger.exception("plugin failed to load")

# Also acceptable in rollback/teardown paths — must always re-raise
except Exception:  # must rollback on any application exception, then re-raise
    conn.rollback()
    raise
```

### Let `None` Propagate from Dict Access

Use `.get("key")` without a default. Providing `""` or `0` as a fallback
masks missing keys — `None` is the honest signal that data is absent.
Supply a default only when `None` is a valid value in the dict and you
need to distinguish "missing" from "explicitly None."

```python
# Bad — masks that "count" could be missing
count = data.get("count", 0)

# Good — let None propagate; handle it explicitly downstream
count = data.get("count")

# Acceptable — None is a valid value, so a default disambiguates
enabled = config.get("enabled", True)
```

### No Empty-String Defaults

`""` is not "no value." Use `None`, or better, require the argument. Same
applies to `[]` and `{}` as sentinels.

```python
# Bad — "" is not "no value"
def find_user(name: str = "") -> User: ...

# Good
def find_user(name: str | None = None) -> User: ...

# Best — require it
def find_user(name: str) -> User: ...
```

### Docstring Discipline

Google-style docstrings. Two sub-rules:

- **Never put type annotations in docstrings** — types belong in PEP 484
  annotations on the signature. Duplicating them creates noise and a second
  source of truth that drifts.
- **Omit sections that restate what the signature already says.** If `Args`
  names and types tell the whole story, or `Returns` type is self-explanatory,
  skip those sections.

```python
# Bad — redundant types and sections
def fetch_user(user_id: int, timeout: float = 5.0) -> User:
    """Fetch a user by ID.

    Args:
        user_id (int): The user's ID.
        timeout (float): Request timeout in seconds.

    Returns:
        User: The fetched user.
    """

# Good — only document what isn't obvious
def fetch_user(user_id: int, timeout: float = 5.0) -> User:
    """Fetch a user by ID.

    Raises:
        UserNotFoundError: If no user exists for the given ID.
    """
```

### Prefer Pathlib Methods Over String Manipulation

Use `with_suffix`, `with_stem`, `with_name` instead of string concatenation
or f-string path assembly. These methods handle edge cases (double
extensions, empty stems) that string manipulation silently gets wrong.

```python
# Bad
output = str(input_path) + ".json"
output = f"{input_path.parent}/{input_path.stem}.json"

# Good
output = input_path.with_suffix(".json")
output = input_path.with_name("output.json")
```

### Imports at Module Top

All imports belong at the top of the file — never inside functions. Lazy
imports hide dependencies and make it harder to see what a module depends
on at a glance. Sort: stdlib, third-party, local.

```python
# Bad
def process():
    from pathlib import Path
    ...

# Good
from pathlib import Path

def process():
    ...
```

### Be Concise

- No docstrings that restate the signature.
- No comments that restate the code.
- No single-use type aliases.
- No unnecessary helper functions that are only called once and don't simplify.

---

## References

| Reference | When to read it |
|-----------|----------------|
| [`references/core-patterns.md`](references/core-patterns.md) | Full examples for type contracts (Protocols, ABCs, Mixins), data representation (frozen dataclasses, TypedDict, Enums, NamedTuple), error hierarchies, and context managers |
| [`references/composition.md`](references/composition.md) | Generator pipelines, itertools, functools (partial, singledispatch, cache, wraps), standalone functions vs methods |
| [`references/advanced-patterns.md`](references/advanced-patterns.md) | Advanced typing (@overload, TypeGuard, generics, TYPE_CHECKING), structural pattern matching, immutability toolkit, async patterns, module organization and docstring conventions |
