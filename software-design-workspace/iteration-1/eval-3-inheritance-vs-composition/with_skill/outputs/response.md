# Inheritance vs Composition for UserService and AdminService

**Recommendation: Use composition.**

---

## Why Not Inheritance

The inheritance approach looks appealing — both services share logging, audit trail, and permission checking, so a `BaseService` seems natural. But inheritance couples them tightly:

- `AdminService` extending `UserService` inherits everything `UserService` has, including methods that only make sense for users. AdminService only needs `log`, `audit`, and `check_permission` — not user management operations.
- When shared behavior changes (e.g., audit trail format), the base class changes, and every subclass is silently affected.
- Testing `AdminService` in isolation becomes harder because it drags in `UserService`'s behavior.

The guideline here: **build behavior by combining small pieces, not by extending large ones.** Deep hierarchies are brittle; composition is explicit about what each service actually uses.

---

## Concrete Example

### Before: Inheritance (avoid)

```python
class BaseService:
    def log(self, message): ...
    def record_audit(self, action): ...
    def check_permission(self, user, action): ...

class UserService(BaseService):
    def get_user(self, user_id): ...
    def update_user(self, user_id, data): ...

class AdminService(UserService):  # inherits everything, including user methods
    def bulk_delete(self, user_ids): ...
    def bulk_update(self, updates): ...
```

`AdminService` now silently inherits `get_user` and `update_user` even though it shouldn't expose those directly. It's also tightly coupled to `UserService`'s internals.

---

### After: Composition (prefer)

Extract each shared behavior into a small, focused collaborator:

```python
class Logger:
    def log(self, message: str) -> None: ...

class AuditRecorder:
    def record(self, actor: str, action: str, target: str) -> None: ...

class PermissionChecker:
    def check(self, user: User, action: str) -> None:
        """Raises PermissionDeniedError if user lacks permission."""
        ...

class UserService:
    def __init__(
        self,
        logger: Logger,
        auditor: AuditRecorder,
        permissions: PermissionChecker,
    ):
        self._logger = logger
        self._auditor = auditor
        self._permissions = permissions

    def update_user(self, actor: User, user_id: str, data: dict) -> User:
        self._permissions.check(actor, "user:update")
        user = self._fetch(user_id)
        updated = self._apply(user, data)
        self._auditor.record(actor.id, "user:update", user_id)
        self._logger.log(f"User {user_id} updated by {actor.id}")
        return updated

class AdminService:
    def __init__(
        self,
        logger: Logger,
        auditor: AuditRecorder,
        permissions: PermissionChecker,
    ):
        self._logger = logger
        self._auditor = auditor
        self._permissions = permissions

    def bulk_delete(self, actor: User, user_ids: list[str]) -> None:
        self._permissions.check(actor, "admin:bulk_delete")
        for uid in user_ids:
            self._delete(uid)
        self._auditor.record(actor.id, "admin:bulk_delete", f"{len(user_ids)} users")
        self._logger.log(f"Bulk delete of {len(user_ids)} users by {actor.id}")

    def bulk_update(self, actor: User, updates: dict[str, dict]) -> None:
        self._permissions.check(actor, "admin:bulk_update")
        for uid, data in updates.items():
            self._apply(uid, data)
        self._auditor.record(actor.id, "admin:bulk_update", f"{len(updates)} users")
```

---

## Key Benefits

**Each service declares exactly what it needs.** `AdminService` doesn't accidentally inherit `UserService` methods. The constructor signature is the complete dependency list — readable, testable, and honest.

**Testing is straightforward.** Each collaborator can be replaced with a stub:

```python
def test_bulk_delete_checks_permission():
    permissions = StubPermissionChecker(raises=PermissionDeniedError)
    service = AdminService(logger=NullLogger(), auditor=NullAuditor(), permissions=permissions)

    with pytest.raises(PermissionDeniedError):
        service.bulk_delete(actor=unprivileged_user, user_ids=["u1", "u2"])
```

No base class setup, no inherited state to worry about.

**Adding new shared behavior is additive, not invasive.** If you later need rate limiting, inject a `RateLimiter` into the services that need it. No base class changes, no risk of breaking unrelated services.

**The interfaces stay focused.** `Logger`, `AuditRecorder`, and `PermissionChecker` each do one thing. Any service (not just these two) can compose them freely without being forced to take the whole bundle.

---

## Summary

| | Inheritance | Composition |
|---|---|---|
| Coupling | High — parent/child tightly linked | Low — each dependency is explicit |
| Testability | Harder — base class drags along | Easy — swap any collaborator |
| What AdminService gets | Everything UserService has | Only what it declares |
| Adding new behavior | Modify base (risky) | Inject new collaborator (safe) |

Compose `Logger`, `AuditRecorder`, and `PermissionChecker` as explicit constructor dependencies. Both services get exactly what they need, nothing more.
