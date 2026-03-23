# Pydantic vs Dataclasses: When to Use Each

## The Core Principle: Validation Boundaries

The key insight is **where** in your flow you are, not how convenient Pydantic is throughout. Pydantic is excellent at the **boundary** — where external, untrusted data enters your system. Once that data is validated and trusted, carrying Pydantic models through your internal logic adds overhead and mutability you don't need.

Your class probably looks something like this right now:

```python
from pydantic import BaseModel
from decimal import Decimal

class UserInput(BaseModel):
    username: str
    email: str
    age: int

class UserService:
    def process(self, raw_data: dict) -> None:
        user = UserInput(**raw_data)         # validate
        transformed = self._transform(user)  # transform (still a Pydantic model)
        self._save(transformed)              # save (still a Pydantic model)

    def _transform(self, user: UserInput) -> UserInput:
        # Pydantic model passed around internally — mutable, carries validator overhead
        return user.model_copy(update={"username": user.username.strip().lower()})

    def _save(self, user: UserInput) -> None:
        db.insert(user.model_dump())
```

**The problem:** Pydantic models are mutable by default, carry validation overhead on every field access, and signal to readers "this data might still be untrusted" — even when it's already been validated.

---

## The Recommended Split

### 1. Pydantic at the boundary (external input)

Use `BaseModel` for anything coming from outside: HTTP request bodies, CLI args, config files, environment variables, message queues. This is where coercion and validation belong.

```python
from pydantic import BaseModel, EmailStr, field_validator

class CreateUserRequest(BaseModel):
    """Validates and coerces external input. Lives at the API/service boundary."""
    username: str
    email: EmailStr
    age: int

    @field_validator("age")
    @classmethod
    def age_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("age must be positive")
        return v
```

### 2. Frozen dataclasses internally

Once validated, convert to an immutable domain object. This signals to readers (and the type checker) that the data is trusted and won't change.

```python
from dataclasses import dataclass, replace

@dataclass(frozen=True)
class User:
    """Immutable domain object. Used throughout internal logic."""
    username: str
    email: str
    age: int
```

### 3. The service wiring them together

```python
from dataclasses import replace

class UserService:
    def process(self, raw_data: dict) -> None:
        # Boundary: validate external input
        request = CreateUserRequest(**raw_data)

        # Convert to internal domain object
        user = User(
            username=request.username,
            email=request.email,
            age=request.age,
        )

        # Internal logic uses the immutable domain object
        transformed = self._transform(user)
        self._save(transformed)

    def _transform(self, user: User) -> User:
        # replace() creates a new instance — frozen dataclass stays immutable
        return replace(user, username=user.username.strip().lower())

    def _save(self, user: User) -> None:
        db.insert({
            "username": user.username,
            "email": user.email,
            "age": user.age,
        })
```

---

## Decision Table

| Situation | Use |
|---|---|
| HTTP request body, form data, JSON from API client | `Pydantic BaseModel` |
| Config loaded from file or environment | `Pydantic BaseModel` |
| Domain concept passed through internal functions | `@dataclass(frozen=True)` |
| Return value from a pure function | `@dataclass(frozen=True)` |
| Dict-shaped payload that stays a plain dict | `TypedDict` |
| Fixed set of statuses/modes | `StrEnum` / `Enum` |

---

## Why Not Pydantic All the Way Through?

1. **Mutability by default.** Pydantic models are mutable unless you set `model_config = ConfigDict(frozen=True)`. Frozen dataclasses are immutable by construction.

2. **Validation on construction.** Pydantic re-runs validators when you call `model_copy()` or construct a new model. Dataclass `replace()` is a simple field copy — no overhead.

3. **Semantics.** A `BaseModel` subclass says "I came from outside and was validated." A `@dataclass(frozen=True)` says "I am a trusted domain concept." Mixing them confuses intent.

4. **Hashability.** Frozen dataclasses are hashable by default (usable in sets, dict keys). Pydantic models are not unless you implement `__hash__` manually.

---

## When Pydantic *Is* the Right Internal Type

There are cases where keeping Pydantic inside makes sense:

- **You need serialization back out.** If the domain object gets serialized to JSON frequently (e.g., for caching or event publishing), Pydantic's `model_dump()` / `model_dump_json()` is convenient and well-tested.
- **You need validation on mutation.** If the object is genuinely mutable during processing (e.g., a builder pattern where fields are filled in incrementally), `model_copy(update=...)` with validation is useful.
- **The whole codebase is Pydantic-first.** If you're in a FastAPI codebase where everything flows through Pydantic, the consistency benefit may outweigh the conceptual purity of splitting.

In those cases, use `model_config = ConfigDict(frozen=True)` on your internal models at minimum.

---

## Practical Refactoring Steps

If you want to migrate your existing class:

1. Rename your current Pydantic model to `<Name>Request` or `<Name>Input` — it stays at the boundary.
2. Create a `@dataclass(frozen=True)` with the same fields for internal use.
3. Add a conversion at the point where external data enters internal logic.
4. Replace `model_copy(update=...)` with `replace(...)` from `dataclasses`.
5. Replace `obj.model_dump()` for DB/serialization with an explicit dict literal or a helper function.

This is a small, incremental change — no need to rewrite everything at once.
