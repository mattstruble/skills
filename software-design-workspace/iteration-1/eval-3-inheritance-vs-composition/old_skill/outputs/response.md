# Inheritance vs Composition for UserService and AdminService

## Recommendation: Composition

Use composition. Avoid inheritance here.

Both services share three distinct behaviors — logging, audit trail recording, and permission checking. These are independent concerns. Inheritance would force you to bundle them into a base class that every subclass drags along, coupling `AdminService` to the full surface of `UserService` even for parts it doesn't share conceptually.

---

## Why Not Inheritance

The "Compose, Don't Inherit" principle is direct: inheritance couples parent and child tightly. Here, there's no genuine "is-a" relationship — `AdminService` isn't a specialized `UserService`, it's a different service that happens to share some cross-cutting concerns. Modelling that with inheritance misrepresents the domain.

Additionally, if you later need to test `AdminService` in isolation, a base class with side effects (logging, audit recording) makes setup harder. Pure, injectable collaborators are straightforward to swap in tests.

---

## Concrete Design

Extract each shared behavior into a focused, standalone collaborator:

```python
# Each collaborator does exactly one thing

class Logger:
    def log(self, message: str, level: str = "info") -> None:
        ...

class AuditRecorder:
    def record(self, actor: str, action: str, resource: str) -> None:
        ...

class PermissionChecker:
    def require(self, actor: str, permission: str) -> None:
        # raises PermissionDenied if not allowed
        ...
```

Inject them into each service:

```python
class UserService:
    def __init__(
        self,
        logger: Logger,
        audit: AuditRecorder,
        permissions: PermissionChecker,
    ) -> None:
        self._logger = logger
        self._audit = audit
        self._permissions = permissions

    def get_user(self, actor: str, user_id: str) -> User:
        self._permissions.require(actor, "users:read")
        user = self._fetch(user_id)
        self._audit.record(actor, "get_user", user_id)
        self._logger.log(f"user {user_id} fetched by {actor}")
        return user


class AdminService:
    def __init__(
        self,
        logger: Logger,
        audit: AuditRecorder,
        permissions: PermissionChecker,
    ) -> None:
        self._logger = logger
        self._audit = audit
        self._permissions = permissions

    def bulk_delete(self, actor: str, user_ids: list[str]) -> None:
        self._permissions.require(actor, "admin:bulk_delete")
        for uid in user_ids:
            self._delete(uid)
            self._audit.record(actor, "bulk_delete", uid)
        self._logger.log(f"{len(user_ids)} users deleted by {actor}")
```

`AdminService.bulk_delete` and any other admin-only methods live naturally on `AdminService` without polluting a shared base class or forcing `UserService` to know about them.

---

## If the Constructor Repetition Bothers You

If injecting the same three collaborators into every service becomes mechanical, extract a small container — not a base class:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ServiceDeps:
    logger: Logger
    audit: AuditRecorder
    permissions: PermissionChecker


class UserService:
    def __init__(self, deps: ServiceDeps) -> None:
        self._deps = deps

    def get_user(self, actor: str, user_id: str) -> User:
        self._deps.permissions.require(actor, "users:read")
        ...
```

This keeps the interface focused (`ServiceDeps` is a value, not a base class), avoids re-listing three parameters everywhere, and is still trivially testable — pass a `ServiceDeps` with mocked collaborators.

---

## Summary

| Approach | Verdict |
|---|---|
| `AdminService(UserService)` inheritance | No — wrong relationship, tight coupling |
| Shared `BaseService` with logging/audit/permissions | No — hides three responsibilities in one class |
| Standalone `Logger`, `AuditRecorder`, `PermissionChecker` injected into each service | Yes |

Shared behavior that crosses conceptual boundaries belongs in collaborators, not base classes. Inject the pieces each service needs; let each service own its own interface.
