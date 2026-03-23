# Refactoring a Bloated Class

## Diagnosis

This class has at least four distinct responsibilities: validation, serialization, database access, and email notification. That's four separate reasons to change it, which means it violates single-responsibility and has a bloated interface. The 8 constructor parameters are a symptom -- callers must know about database config, email settings, validation rules, and serialization options all at once, even if they only care about one concern.

The fix is to split along responsibility lines, then compose the pieces.

---

## Step 1: Identify the Responsibilities

Before touching code, name the four concerns explicitly:

1. **Validation** -- rules about what constitutes valid user input
2. **Serialization** -- converting a user object to/from JSON
3. **Repository** -- reading and writing users to the database
4. **Notifications** -- sending email when user-relevant events occur

Each becomes its own focused unit.

---

## Step 2: Extract Pure Validation

Validation is almost always stateless -- it takes data, applies rules, returns a result. Make it a pure function or a stateless class.

```python
# Before: buried in the big class
class UserService:
    def __init__(self, db_host, db_port, db_name, db_user, db_pass,
                 smtp_host, smtp_port, email_from):
        ...
    def validate(self, data): ...  # one of 12 methods

# After: isolated, pure, testable
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class ValidationError:
    field: str
    message: str

def validate_user_input(data: dict) -> List[ValidationError]:
    errors = []
    if not data.get("email"):
        errors.append(ValidationError("email", "Email is required"))
    if not data.get("name") or len(data["name"]) < 2:
        errors.append(ValidationError("name", "Name must be at least 2 characters"))
    return errors
```

No setup. No mocking. Pass a dict, get a list back.

---

## Step 3: Extract Serialization

Serialization is also pure -- it's a transformation between representations.

```python
from typing import Any

def user_to_json(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "created_at": user.created_at.isoformat(),
    }

def user_from_json(data: dict[str, Any]) -> User:
    return User(
        id=data["id"],
        name=data["name"],
        email=data["email"],
        created_at=datetime.fromisoformat(data["created_at"]),
    )
```

These are standalone functions. No class needed. The caller imports exactly what they need.

---

## Step 4: Extract the Repository

Database access is a side effect -- isolate it. Define a focused interface that expresses only what callers need.

```python
from typing import Optional, Protocol

class UserRepository(Protocol):
    def get(self, user_id: str) -> Optional[User]: ...
    def save(self, user: User) -> None: ...
    def delete(self, user_id: str) -> None: ...

class PostgresUserRepository:
    def __init__(self, connection_string: str):
        self._conn_str = connection_string

    def get(self, user_id: str) -> Optional[User]:
        # actual DB logic
        ...

    def save(self, user: User) -> None:
        # actual DB logic
        ...

    def delete(self, user_id: str) -> None:
        # actual DB logic
        ...
```

The `Protocol` type lets callers depend on the abstraction, not the Postgres implementation. Tests can inject a fake without a real database.

---

## Step 5: Extract Notifications

Email sending is another side effect. Same pattern -- protocol plus concrete implementation.

```python
class UserNotifier(Protocol):
    def send_welcome(self, user: User) -> None: ...
    def send_password_reset(self, user: User, token: str) -> None: ...

class SmtpUserNotifier:
    def __init__(self, smtp_host: str, smtp_port: int, from_address: str):
        self._host = smtp_host
        self._port = smtp_port
        self._from = from_address

    def send_welcome(self, user: User) -> None:
        # SMTP logic
        ...

    def send_password_reset(self, user: User, token: str) -> None:
        # SMTP logic
        ...
```

---

## Step 6: Compose in a Slim Coordinator

If you need a single entry point that orchestrates these (e.g., "register a user"), write a thin coordinator that takes only what it needs.

```python
# Before: 8 constructor params, caller must configure everything
service = UserService(
    db_host="localhost", db_port=5432, db_name="app",
    db_user="admin", db_pass="secret",
    smtp_host="mail.example.com", smtp_port=587,
    email_from="noreply@example.com"
)

# After: inject focused collaborators, each already configured
from dataclasses import dataclass

@dataclass
class RegisterUserCommand:
    name: str
    email: str

class UserRegistrationHandler:
    def __init__(self, repo: UserRepository, notifier: UserNotifier):
        self._repo = repo
        self._notifier = notifier

    def handle(self, cmd: RegisterUserCommand) -> User | list[ValidationError]:
        errors = validate_user_input({"name": cmd.name, "email": cmd.email})
        if errors:
            return errors

        user = User.create(name=cmd.name, email=cmd.email)
        self._repo.save(user)
        self._notifier.send_welcome(user)
        return user
```

The coordinator has **2 constructor parameters** (down from 8). Each collaborator is independently configurable, testable, and replaceable.

---

## Step 7: Wire It Up at the Boundary

Configuration concerns belong at the composition root -- the application entry point. Nowhere else.

```python
# In your app startup / dependency injection setup
repo = PostgresUserRepository("postgresql://admin:secret@localhost/app")
notifier = SmtpUserNotifier("mail.example.com", 587, "noreply@example.com")
handler = UserRegistrationHandler(repo, notifier)
```

The business logic never sees connection strings. The infrastructure never sees validation rules.

---

## Summary: Before vs. After

| Concern | Before | After |
|---|---|---|
| Validation | Method on `UserService` | Pure function, no dependencies |
| Serialization | Method on `UserService` | Pure functions, no dependencies |
| DB access | Methods on `UserService`, 5 DB params in constructor | `PostgresUserRepository`, 1 param |
| Email | Methods on `UserService`, 3 SMTP params in constructor | `SmtpUserNotifier`, 3 params |
| Orchestration | All 12 methods on one class | `UserRegistrationHandler`, 2 params |
| Testing | Need to mock DB + SMTP just to test validation | Test validation with a plain dict |

The 12-method class becomes five small pieces, each testable in isolation, each changeable without touching the others.

---

## Key Checks

1. **Does this earn its place?** Each piece now has a single reason to exist.
2. **Is each piece focused on one thing?** Yes -- validation never touches a socket; the repository never sends email.
3. **Can I understand this without running it in my head?** Each unit is small enough to read in under a minute.
4. **Does it do what it says?** `validate_user_input` validates. `UserRepository.save` saves. No surprises.
5. **What happens when things go wrong?** Validation returns explicit errors. DB and SMTP failures surface at the boundary, not swallowed internally.
6. **Will this still make sense in a year?** Yes -- each file has a clear name and scope. A new engineer can find email logic without reading database code.
