# Refactoring a Bloated Class: From God Object to Focused Collaborators

## Diagnosis

A class with 12 methods, 8 constructor parameters, and four distinct responsibilities is a classic **God Object** — it knows too much and does too much. The tell is the responsibility list itself:

- User input validation
- JSON serialization
- Database access
- Email notification

These are four separate concerns. The Interface Segregation Principle is being violated: callers who only need serialization are forced to depend on a class that also manages database connections and email credentials. The 8-parameter constructor is a direct symptom — each group of parameters belongs to a different responsibility.

The fix is **decomposition by responsibility**: extract each concern into its own focused unit, then compose them at the boundary where they must work together.

---

## Step 1: Identify the Four Responsibilities

**Before** (the God Object):

```python
class UserManager:
    def __init__(self, db_host, db_port, db_name, db_user, db_password,
                 smtp_host, smtp_port, email_from):
        self.db = connect(db_host, db_port, db_name, db_user, db_password)
        self.smtp = SMTPClient(smtp_host, smtp_port, email_from)

    # Validation (2 methods)
    def validate_email(self, email): ...
    def validate_username(self, username): ...

    # Serialization (3 methods)
    def to_json(self, user): ...
    def from_json(self, data): ...
    def to_api_response(self, user): ...

    # Database access (4 methods)
    def get_user(self, user_id): ...
    def save_user(self, user): ...
    def delete_user(self, user_id): ...
    def find_by_email(self, email): ...

    # Email notifications (3 methods)
    def send_welcome_email(self, user): ...
    def send_password_reset(self, user, token): ...
    def send_deactivation_notice(self, user): ...
```

---

## Step 2: Extract Pure Logic First (Validation and Serialization)

Validation and serialization have no side effects — they're pure transformations. Extract them as standalone functions or stateless classes. No constructor parameters needed.

```python
# validation.py

class UserValidationError(ValueError):
    pass

def validate_email(email: str) -> str:
    """Returns normalized email or raises UserValidationError."""
    email = email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise UserValidationError(f"Invalid email: {email!r}")
    return email

def validate_username(username: str) -> str:
    """Returns normalized username or raises UserValidationError."""
    username = username.strip()
    if len(username) < 3:
        raise UserValidationError("Username must be at least 3 characters")
    if not username.isalnum():
        raise UserValidationError("Username must be alphanumeric")
    return username
```

```python
# serialization.py

from dataclasses import asdict
import json
from .models import User

def user_to_json(user: User) -> str:
    return json.dumps(asdict(user))

def user_from_json(data: str) -> User:
    try:
        return User(**json.loads(data))
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError(f"Cannot deserialize user: {e}") from e

def user_to_api_response(user: User) -> dict:
    return {"id": user.id, "username": user.username, "email": user.email}
```

These functions are now **trivially testable** — pass values in, assert on the output. No mocking, no setup.

---

## Step 3: Extract the Database Access Behind an Abstraction

Database access is a side-effectful concern. Wrap it behind a protocol so callers depend on an abstraction, not a specific implementation. This also makes the class swappable for tests.

```python
# repositories.py

from typing import Protocol
from .models import User

class UserRepository(Protocol):
    def get(self, user_id: int) -> User: ...
    def save(self, user: User) -> User: ...
    def delete(self, user_id: int) -> None: ...
    def find_by_email(self, email: str) -> User | None: ...

class PostgresUserRepository:
    def __init__(self, connection):
        self._conn = connection

    def get(self, user_id: int) -> User:
        row = self._conn.execute(
            "SELECT * FROM users WHERE id = %s", (user_id,)
        ).fetchone()
        if not row:
            raise UserNotFoundError(user_id)
        return User(**row)

    def save(self, user: User) -> User:
        # upsert logic...
        ...

    def delete(self, user_id: int) -> None:
        self._conn.execute("DELETE FROM users WHERE id = %s", (user_id,))

    def find_by_email(self, email: str) -> User | None:
        row = self._conn.execute(
            "SELECT * FROM users WHERE email = %s", (email,)
        ).fetchone()
        return User(**row) if row else None
```

The `PostgresUserRepository` now takes a **single** constructor parameter (a connection), not five. The connection configuration belongs at the application boundary, not inside this class.

---

## Step 4: Extract Email Notifications

Email is another side-effectful concern, but orthogonal to database access.

```python
# notifications.py

from typing import Protocol
from .models import User

class UserNotifier(Protocol):
    def welcome(self, user: User) -> None: ...
    def password_reset(self, user: User, token: str) -> None: ...
    def deactivation_notice(self, user: User) -> None: ...

class EmailUserNotifier:
    def __init__(self, smtp_client, from_address: str):
        self._smtp = smtp_client
        self._from = from_address

    def welcome(self, user: User) -> None:
        self._smtp.send(
            to=user.email,
            from_=self._from,
            subject="Welcome!",
            body=f"Hi {user.username}, welcome aboard."
        )

    def password_reset(self, user: User, token: str) -> None:
        self._smtp.send(
            to=user.email,
            from_=self._from,
            subject="Reset your password",
            body=f"Use this token: {token}"
        )

    def deactivation_notice(self, user: User) -> None:
        self._smtp.send(
            to=user.email,
            from_=self._from,
            subject="Account deactivated",
            body="Your account has been deactivated."
        )
```

Again: `EmailUserNotifier` takes only what it needs (smtp client, from address) — 2 parameters instead of being bundled with 5 database parameters.

---

## Step 5: Compose at the Service Layer (Only When Needed)

If you have a workflow that genuinely needs multiple concerns together — say, "register a user: validate, save, send welcome email" — compose them at the service layer. But the service class only takes what it needs:

```python
# user_service.py

from .validation import validate_email, validate_username
from .repositories import UserRepository
from .notifications import UserNotifier
from .models import User

class UserRegistrationService:
    """Orchestrates user registration: validate → save → notify."""

    def __init__(self, repository: UserRepository, notifier: UserNotifier):
        self._repo = repository
        self._notifier = notifier

    def register(self, username: str, email: str) -> User:
        # Validate (pure — no dependencies needed)
        clean_username = validate_username(username)
        clean_email = validate_email(email)

        # Persist
        user = self._repo.save(User(username=clean_username, email=clean_email))

        # Notify
        self._notifier.welcome(user)

        return user
```

This service has **2 constructor parameters** (down from 8) and **1 method**. Each dependency does one thing. The validation logic is pure and doesn't need to be injected at all.

---

## Step 6: Wire It Together at the Application Boundary

Configuration and construction happen once, at startup:

```python
# app.py (or dependency injection container)

import psycopg2
from smtplib import SMTP

from .repositories import PostgresUserRepository
from .notifications import EmailUserNotifier
from .user_service import UserRegistrationService

def build_registration_service(config) -> UserRegistrationService:
    conn = psycopg2.connect(
        host=config.db_host, port=config.db_port,
        dbname=config.db_name, user=config.db_user,
        password=config.db_password
    )
    smtp = SMTP(config.smtp_host, config.smtp_port)
    
    repo = PostgresUserRepository(conn)
    notifier = EmailUserNotifier(smtp, config.email_from)
    
    return UserRegistrationService(repo, notifier)
```

The 8 original parameters still exist — but they're now handled at the **composition root**, not scattered through a single bloated class.

---

## Summary: Before vs. After

| | Before | After |
|---|---|---|
| Classes | 1 God Object | 4 focused units + 1 thin service |
| Constructor params | 8 | 0–2 per class |
| Methods per class | 12 | 2–4 per class |
| Testability | Requires mocking DB + SMTP for every test | Pure functions test with no mocks; each class tested in isolation |
| Caller coupling | Every caller depends on all 4 concerns | Each caller depends only on what it uses |

## Key Principles Applied

1. **Focused Interfaces**: Split the one broad interface into four narrow ones — callers that only serialize don't see the SMTP configuration.
2. **Compose, Don't Inherit**: The service layer *owns* a repository and notifier; it doesn't inherit from them.
3. **Pure Functions First**: Validation and serialization have no side effects — extracted as standalone functions with no constructor at all.
4. **Depend on Abstractions**: `UserRepository` and `UserNotifier` are protocols; the service doesn't know (or care) whether it's talking to Postgres or a test double.
5. **Honesty**: Each unit does exactly what its name says. `validate_email` validates an email. `PostgresUserRepository.get` fetches a user or raises — it doesn't silently return `None`.
