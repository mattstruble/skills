# Python API Client Design

Applied guidance from the `python-design` skill to structure a REST API client with user profile and activity event models.

---

## Structure Overview

```
api_client/
├── __init__.py          # Public API surface
├── models.py            # Domain data models (frozen dataclasses, TypedDict, Enums)
├── schemas.py           # Pydantic validation models at the HTTP boundary
├── errors.py            # Shallow error hierarchy
├── client.py            # HTTP client — core request logic
└── _types.py            # Internal typing helpers (TYPE_CHECKING imports, TypeVars)
```

**Key boundaries:**
- `schemas.py` — Pydantic validates raw JSON at the HTTP boundary
- `models.py` — frozen dataclasses represent trusted domain objects after validation
- `errors.py` — shallow hierarchy, no bare `except`
- `client.py` — standalone functions / thin class, not a god-object

---

## `errors.py` — Shallow Error Hierarchy

```python
"""API client error types."""

__all__ = [
    "ApiClientError",
    "HttpError",
    "NotFoundError",
    "UnauthorizedError",
    "RateLimitError",
    "ParseError",
]


class ApiClientError(Exception):
    """Base for all API client errors."""


class HttpError(ApiClientError):
    """Non-2xx HTTP response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class NotFoundError(HttpError):
    """404 — resource does not exist."""


class UnauthorizedError(HttpError):
    """401/403 — authentication or permission failure."""


class RateLimitError(HttpError):
    """429 — rate limit exceeded."""


class ParseError(ApiClientError):
    """Response body could not be parsed into the expected model."""
```

---

## `models.py` — Domain Objects

These are trusted internal objects — immutable, hashable, domain-named.

```python
"""Internal domain models. Created after Pydantic validation at the boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TypedDict

__all__ = [
    "UserProfile",
    "ActivityEvent",
    "ActivityType",
    "PageInfo",
]


class ActivityType(StrEnum):
    LOGIN = "login"
    LOGOUT = "logout"
    PURCHASE = "purchase"
    VIEW = "view"
    SEARCH = "search"


@dataclass(frozen=True)
class UserProfile:
    """A resolved user profile from the API."""

    user_id: str
    username: str
    email: str
    display_name: str
    created_at: datetime
    is_active: bool


@dataclass(frozen=True)
class ActivityEvent:
    """A single recorded user activity event."""

    event_id: str
    user_id: str
    activity_type: ActivityType
    occurred_at: datetime
    metadata: frozenset[tuple[str, str]]  # immutable k/v extras

    @classmethod
    def from_dict(cls, data: ActivityEventDict) -> "ActivityEvent":
        return cls(
            event_id=data["event_id"],
            user_id=data["user_id"],
            activity_type=ActivityType(data["activity_type"]),
            occurred_at=datetime.fromisoformat(data["occurred_at"]),
            metadata=frozenset(data.get("metadata", {}).items()),
        )


class ActivityEventDict(TypedDict):
    """Dict-shaped wire representation of an activity event (stays dict-compatible)."""

    event_id: str
    user_id: str
    activity_type: str
    occurred_at: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class PageInfo:
    """Pagination cursor from a list response."""

    total: int
    page: int
    page_size: int
    has_next: bool
```

---

## `schemas.py` — Pydantic Validation at the HTTP Boundary

Raw JSON from the wire is validated here before entering the domain.

```python
"""Pydantic schemas for validating raw API JSON responses."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from .models import ActivityEvent, ActivityType, PageInfo, UserProfile

__all__ = [
    "UserProfileResponse",
    "ActivityEventResponse",
    "ActivityFeedResponse",
]


class UserProfileResponse(BaseModel):
    """Raw API response for a single user profile."""

    user_id: str
    username: str
    email: str
    display_name: str
    created_at: datetime
    is_active: bool = True

    def to_domain(self) -> UserProfile:
        return UserProfile(
            user_id=self.user_id,
            username=self.username,
            email=self.email,
            display_name=self.display_name,
            created_at=self.created_at,
            is_active=self.is_active,
        )


class ActivityEventResponse(BaseModel):
    """Raw API response for a single activity event."""

    event_id: str
    user_id: str
    activity_type: str
    occurred_at: datetime
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("activity_type")
    @classmethod
    def validate_activity_type(cls, v: str) -> str:
        try:
            ActivityType(v)
        except ValueError:
            raise ValueError(f"Unknown activity_type: {v!r}")
        return v

    def to_domain(self) -> ActivityEvent:
        return ActivityEvent(
            event_id=self.event_id,
            user_id=self.user_id,
            activity_type=ActivityType(self.activity_type),
            occurred_at=self.occurred_at,
            metadata=frozenset(self.metadata.items()),
        )


class ActivityFeedResponse(BaseModel):
    """Paginated list of activity events."""

    events: list[ActivityEventResponse]
    total: int
    page: int
    page_size: int
    has_next: bool

    def to_domain(self) -> tuple[list[ActivityEvent], PageInfo]:
        domain_events = [e.to_domain() for e in self.events]
        page_info = PageInfo(
            total=self.total,
            page=self.page,
            page_size=self.page_size,
            has_next=self.has_next,
        )
        return domain_events, page_info
```

---

## `client.py` — HTTP Client

Thin class wrapping HTTP calls. Standalone helper functions for response parsing live outside the class so they're independently testable.

```python
"""REST API client — HTTP transport and response parsing."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, TypeVar

import httpx
from pydantic import ValidationError

from .errors import (
    ApiClientError,
    HttpError,
    NotFoundError,
    ParseError,
    RateLimitError,
    UnauthorizedError,
)
from .models import ActivityEvent, PageInfo, UserProfile
from .schemas import ActivityFeedResponse, UserProfileResponse

__all__ = ["ApiClient"]

T = TypeVar("T")

_STATUS_ERRORS: dict[int, type[HttpError]] = {
    401: UnauthorizedError,
    403: UnauthorizedError,
    404: NotFoundError,
    429: RateLimitError,
}


def _raise_for_status(response: httpx.Response) -> None:
    """Raise the appropriate HttpError subclass for non-2xx responses."""
    if response.is_success:
        return
    error_cls = _STATUS_ERRORS.get(response.status_code, HttpError)
    raise error_cls(response.status_code, response.text)


def _parse_response(response: httpx.Response, schema_cls: type[T]) -> T:
    """Parse a validated response using a Pydantic schema.

    Args:
        response: The raw httpx response.
        schema_cls: A Pydantic BaseModel subclass to validate against.

    Returns:
        A validated schema instance.

    Raises:
        ParseError: If the response body does not match the schema.
    """
    try:
        return schema_cls.model_validate(response.json())  # type: ignore[attr-defined]
    except (ValidationError, ValueError) as exc:
        raise ParseError(f"Failed to parse response as {schema_cls.__name__}: {exc}") from exc


class ApiClient:
    """Client for the user profiles and activity events API.

    Args:
        base_url: Root URL of the REST service.
        api_key: Bearer token for authentication.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 10.0,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    def get_user(self, user_id: str) -> UserProfile:
        """Fetch a single user profile by ID.

        Args:
            user_id: The unique identifier of the user.

        Returns:
            A validated, immutable UserProfile.

        Raises:
            NotFoundError: If the user does not exist.
            UnauthorizedError: If the API key is invalid or lacks permission.
            HttpError: For other non-2xx responses.
            ParseError: If the response cannot be parsed.
        """
        response = self._http.get(f"/users/{user_id}")
        _raise_for_status(response)
        schema = _parse_response(response, UserProfileResponse)
        return schema.to_domain()

    def get_activity_feed(
        self,
        user_id: str,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ActivityEvent], PageInfo]:
        """Fetch a paginated activity feed for a user.

        Args:
            user_id: The unique identifier of the user.
            page: 1-based page number.
            page_size: Number of events per page.

        Returns:
            A tuple of (events list, pagination info).

        Raises:
            NotFoundError: If the user does not exist.
            UnauthorizedError: If the API key is invalid.
            HttpError: For other non-2xx responses.
            ParseError: If the response cannot be parsed.
        """
        response = self._http.get(
            f"/users/{user_id}/activity",
            params={"page": page, "page_size": page_size},
        )
        _raise_for_status(response)
        schema = _parse_response(response, ActivityFeedResponse)
        return schema.to_domain()

    def iter_all_activity(
        self,
        user_id: str,
        *,
        page_size: int = 100,
    ) -> Generator[ActivityEvent, None, None]:
        """Lazily iterate over all activity events for a user across pages.

        Args:
            user_id: The unique identifier of the user.
            page_size: Events to fetch per page request.

        Yields:
            ActivityEvent objects in chronological order.
        """
        page = 1
        while True:
            events, page_info = self.get_activity_feed(
                user_id, page=page, page_size=page_size
            )
            yield from events
            if not page_info.has_next:
                break
            page += 1

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
```

---

## `__init__.py` — Public API Surface

Only expose what callers need. Internal schemas and helpers stay private.

```python
"""API client for the user profiles and activity service.

Public interface:
    ApiClient       — main entry point
    UserProfile     — immutable user profile domain object
    ActivityEvent   — immutable activity event domain object
    ActivityType    — enum of valid activity type values
    PageInfo        — pagination metadata
    ApiClientError  — base exception (catch-all for this library)
    HttpError       — non-2xx response
    NotFoundError   — 404
    UnauthorizedError — 401/403
    RateLimitError  — 429
    ParseError      — response body parse failure
"""

from .client import ApiClient
from .errors import (
    ApiClientError,
    HttpError,
    NotFoundError,
    ParseError,
    RateLimitError,
    UnauthorizedError,
)
from .models import ActivityEvent, ActivityType, PageInfo, UserProfile

__all__ = [
    "ApiClient",
    "UserProfile",
    "ActivityEvent",
    "ActivityType",
    "PageInfo",
    "ApiClientError",
    "HttpError",
    "NotFoundError",
    "UnauthorizedError",
    "RateLimitError",
    "ParseError",
]
```

---

## Usage Example

```python
from api_client import ApiClient, NotFoundError, RateLimitError, ActivityType

with ApiClient(base_url="https://api.example.com", api_key="secret") as client:
    # Fetch a single user
    try:
        user = client.get_user("user-123")
        print(f"Hello, {user.display_name}")
    except NotFoundError:
        print("User not found")

    # Paginated fetch
    events, page_info = client.get_activity_feed("user-123", page=1, page_size=50)
    purchases = [e for e in events if e.activity_type == ActivityType.PURCHASE]

    # Lazy iteration across all pages — generator pipeline
    all_logins = (
        e for e in client.iter_all_activity("user-123")
        if e.activity_type == ActivityType.LOGIN
    )
    for event in all_logins:
        print(event.event_id, event.occurred_at)
```

---

## Design Decisions Summary

| Concern | Decision | Rationale |
|---|---|---|
| Raw JSON validation | Pydantic `BaseModel` in `schemas.py` | Validates + coerces at the HTTP boundary before domain code sees data |
| Domain objects | `@dataclass(frozen=True)` | Named, immutable, hashable — `UserProfile` and `ActivityEvent` are more than "bags of keys" |
| Wire dict shape | `TypedDict` (`ActivityEventDict`) | Dict-compatible for interop, still type-checked |
| Activity types | `StrEnum` | Prevents typos, enables exhaustive matching, serializes cleanly |
| Error types | Shallow hierarchy under `ApiClientError` | Callers catch specifically; `NotFoundError` is not a `ParseError` |
| Pagination iteration | Generator (`iter_all_activity`) | Lazy, composable — callers filter with generator expressions |
| HTTP status mapping | Dict dispatch (`_STATUS_ERRORS`) | Avoids a chain of `if/elif`; extend by adding entries |
| Public API | `__all__` in `__init__.py` | Explicit surface; internals (`schemas`, `_types`) stay hidden |
| Resource cleanup | `__enter__`/`__exit__` + `close()` | Supports both `with` and explicit close patterns |
