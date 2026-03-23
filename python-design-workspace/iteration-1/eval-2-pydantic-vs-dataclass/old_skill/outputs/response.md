# Pydantic vs Dataclasses: When to Use Each

## The Core Principle: Validation at the Boundary

Using Pydantic throughout your entire flow (input → transform → save) is a common pattern, but it's not ideal. Pydantic's validation overhead and coercion machinery is most valuable at **external boundaries** — where you can't trust the data. Once the data is validated, you're paying that cost unnecessarily on every internal transformation.

The recommended approach: **validate once at the edge with Pydantic, then convert to frozen dataclasses for internal flow.**

---

## When to Use Each

| Situation | Use |
|---|---|
| External input (API request, config file, user form) | `Pydantic BaseModel` |
| Data flowing through internal business logic | `@dataclass(frozen=True)` |
| Dict-shaped data that doesn't have a meaningful domain name | `TypedDict` |

---

## Concrete Refactoring Example

### Before: Pydantic Throughout

```python
from pydantic import BaseModel
from decimal import Decimal

class CreateUserRequest(BaseModel):
    username: str
    email: str
    age: int

class UserRecord(BaseModel):
    username: str
    email: str
    age: int
    normalized_email: str   # derived field

class UserService:
    def handle(self, raw: dict) -> None:
        # Pydantic validating at every step
        request = CreateUserRequest(**raw)
        record = self._transform(request)
        self._save(record)

    def _transform(self, request: CreateUserRequest) -> UserRecord:
        return UserRecord(
            username=request.username,
            email=request.email,
            age=request.age,
            normalized_email=request.email.lower().strip(),
        )

    def _save(self, record: UserRecord) -> None:
        db.insert(record.model_dump())
```

Problems here:
- `UserRecord` is a Pydantic model but it's an internal domain object — it has a name (`UserRecord`) that means something, it's not just a bag of validated input.
- Pydantic re-validates every field assignment and `model_dump()` on every `_save()` call.
- Internal transformations carry validation overhead they don't need.

---

### After: Pydantic at the Boundary, Dataclasses Internally

```python
from pydantic import BaseModel, field_validator
from dataclasses import dataclass, replace
from decimal import Decimal

# --- Boundary: validate external input ---

class CreateUserRequest(BaseModel):
    username: str
    email: str
    age: int

    @field_validator("age")
    @classmethod
    def age_must_be_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("age must be non-negative")
        return v

# --- Internal domain object: immutable, hashable, fast ---

@dataclass(frozen=True)
class UserRecord:
    username: str
    email: str
    age: int
    normalized_email: str

# --- Service uses validated request, works with dataclass internally ---

class UserService:
    def handle(self, raw: dict) -> None:
        request = CreateUserRequest(**raw)   # validate once here
        record = self._transform(request)    # dataclass from here on
        self._save(record)

    def _transform(self, request: CreateUserRequest) -> UserRecord:
        return UserRecord(
            username=request.username,
            email=request.email,
            age=request.age,
            normalized_email=request.email.lower().strip(),
        )

    def _save(self, record: UserRecord) -> None:
        # Convert to dict only at the persistence boundary
        db.insert({
            "username": record.username,
            "email": record.email,
            "age": record.age,
            "normalized_email": record.normalized_email,
        })
```

Now Pydantic runs exactly once — at the edge where it earns its cost.

---

## Updating Domain Objects

Frozen dataclasses are immutable. Use `dataclasses.replace()` to produce modified copies cleanly:

```python
from dataclasses import replace

# Don't mutate — create a new record
updated_record = replace(record, normalized_email="new@example.com")
```

This is intentional: immutability makes transformations explicit and prevents accidental mutation inside long call chains.

---

## The TypedDict Option

If the data doesn't have a meaningful domain identity (e.g., you're just passing around event metadata), `TypedDict` is lighter than either:

```python
from typing import TypedDict

class UserEventPayload(TypedDict):
    user_id: str
    action: str
    timestamp: str
```

Use TypedDict when the structure is genuinely dict-shaped and won't outlive the immediate call context.

---

## Decision Rule

Ask yourself: **"Does this data have a name that means something in my domain?"**

- `UserRecord`, `OrderSummary`, `PaymentResult` → frozen dataclass. It has identity.
- `{"user_id": ..., "action": ...}` passed to a log function → TypedDict. It's a bag of keys.
- Incoming API JSON you haven't yet validated → Pydantic. Validate it once, then move on.
