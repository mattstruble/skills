# Python API Client Design

This guide applies Python-specific design patterns to structure a REST API client with user profiles and activity events.

---

## Design Decisions

| Layer | Pattern | Reason |
|---|---|---|
| External JSON response | `TypedDict` | Dict-shaped, serializable, no validation overhead |
| Validated input (request params) | Pydantic `BaseModel` | Validates + coerces at the external boundary |
| Domain objects (UserProfile, Event) | `@dataclass(frozen=True)` | Meaningful names, immutable after construction |
| Status/type enumerations | `StrEnum` | Prevents typos, enables exhaustive matching |
| Client contract | `Protocol` | Caller-facing, no inheritance coupling |
| Error hierarchy | Shallow `Exception` subclasses | Specific catch sites, no bare `except` |

---

## Module Structure

```
api_client/
├── __init__.py          # public API — re-exports only
├── client.py            # APIClient implementation
├── models.py            # domain dataclasses + enums
├── requests.py          # Pydantic models for request validation
├── responses.py         # TypedDicts for raw JSON shapes
├── errors.py            # error hierarchy
└── _protocols.py        # Protocol definitions (internal)
```

---

## Code

### `errors.py` — Shallow Error Hierarchy

```python
"""API client error types."""

from __future__ import annotations

__all__ = [
    "APIError",
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
]


class APIError(Exception):
    """Base for all API client errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(APIError):
    """Invalid or missing credentials."""


class NotFoundError(APIError):
    """Requested resource does not exist."""


class RateLimitError(APIError):
    """Request rate limit exceeded."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class ServerError(APIError):
    """Unexpected server-side error (5xx)."""
```

---

### `responses.py` — Raw JSON Shapes (TypedDict)

These represent the raw JSON the server returns — dict-shaped, no validation.

```python
"""TypedDicts matching the raw JSON response shapes from the API."""

from __future__ import annotations

from typing import TypedDict

__all__ = ["UserProfileResponse", "ActivityEventResponse", "PaginatedEventsResponse"]


class UserProfileResponse(TypedDict):
    id: str
    username: str
    email: str
    display_name: str
    created_at: str          # ISO-8601 string from JSON
    is_active: bool
    metadata: dict[str, str]


class ActivityEventResponse(TypedDict):
    id: str
    user_id: str
    event_type: str
    occurred_at: str         # ISO-8601 string from JSON
    payload: dict[str, object]


class PaginatedEventsResponse(TypedDict):
    items: list[ActivityEventResponse]
    total: int
    page: int
    page_size: int
    next_cursor: str | None
```

---

### `models.py` — Domain Objects (frozen dataclasses + StrEnum)

Immutable domain objects with meaningful names. Converted from raw responses.

```python
"""Immutable domain objects for the API client."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

__all__ = [
    "EventType",
    "UserProfile",
    "ActivityEvent",
    "EventPage",
]


class EventType(StrEnum):
    LOGIN = "login"
    LOGOUT = "logout"
    PROFILE_UPDATE = "profile_update"
    PASSWORD_CHANGE = "password_change"
    API_ACCESS = "api_access"


@dataclass(frozen=True)
class UserProfile:
    """A user profile as a domain object."""

    id: str
    username: str
    email: str
    display_name: str
    created_at: datetime
    is_active: bool
    metadata: dict[str, str]

    def deactivated(self) -> "UserProfile":
        """Return a copy with is_active=False."""
        return replace(self, is_active=False)


@dataclass(frozen=True)
class ActivityEvent:
    """A single user activity event."""

    id: str
    user_id: str
    event_type: EventType
    occurred_at: datetime
    payload: dict[str, object]


@dataclass(frozen=True)
class EventPage:
    """A page of activity events with pagination metadata."""

    items: tuple[ActivityEvent, ...]
    total: int
    page: int
    page_size: int
    next_cursor: str | None

    @property
    def has_next(self) -> bool:
        return self.next_cursor is not None
```

---

### `requests.py` — Request Validation (Pydantic at the boundary)

Pydantic validates and coerces caller-supplied inputs before they hit the wire.

```python
"""Pydantic models for validating API request parameters."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from .models import EventType

__all__ = ["GetEventsRequest", "UpdateProfileRequest"]


class GetEventsRequest(BaseModel):
    """Parameters for paginating a user's activity events."""

    user_id: str
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    event_types: list[EventType] | None = None
    cursor: str | None = None

    @field_validator("user_id")
    @classmethod
    def user_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("user_id must not be blank")
        return v


class UpdateProfileRequest(BaseModel):
    """Fields that can be updated on a user profile."""

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    metadata: dict[str, str] | None = None
```

---

### `_protocols.py` — Caller-Facing Contracts

Protocols define what callers depend on. Implementations are free to vary.

```python
"""Protocol definitions — these are the contracts callers type against."""

from __future__ import annotations

from typing import Protocol

from .models import ActivityEvent, EventPage, UserProfile
from .requests import GetEventsRequest, UpdateProfileRequest

__all__ = ["UserProfileAPI", "ActivityAPI"]


class UserProfileAPI(Protocol):
    def get_user(self, user_id: str) -> UserProfile: ...
    def update_user(self, user_id: str, request: UpdateProfileRequest) -> UserProfile: ...


class ActivityAPI(Protocol):
    def get_events(self, request: GetEventsRequest) -> EventPage: ...
    def get_event(self, event_id: str) -> ActivityEvent: ...
```

---

### `client.py` — Implementation

The client implements both protocols. Conversion from raw TypedDicts to domain objects happens here.

```python
"""APIClient — implements UserProfileAPI and ActivityAPI."""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
from typing import Any

import httpx

from .errors import APIError, AuthenticationError, NotFoundError, RateLimitError, ServerError
from .models import ActivityEvent, EventPage, EventType, UserProfile
from .requests import GetEventsRequest, UpdateProfileRequest
from .responses import ActivityEventResponse, PaginatedEventsResponse, UserProfileResponse

__all__ = ["APIClient"]

_BASE_URL = "https://api.example.com/v1"


class APIClient:
    """HTTP client for the user profile and activity API."""

    def __init__(self, api_key: str, base_url: str = _BASE_URL) -> None:
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )

    # -- UserProfileAPI --

    def get_user(self, user_id: str) -> UserProfile:
        raw: UserProfileResponse = self._get(f"/users/{user_id}")
        return _parse_user_profile(raw)

    def update_user(self, user_id: str, request: UpdateProfileRequest) -> UserProfile:
        payload = request.model_dump(exclude_none=True)
        raw: UserProfileResponse = self._patch(f"/users/{user_id}", json=payload)
        return _parse_user_profile(raw)

    # -- ActivityAPI --

    def get_events(self, request: GetEventsRequest) -> EventPage:
        params: dict[str, Any] = {
            "page": request.page,
            "page_size": request.page_size,
        }
        if request.event_types:
            params["event_types"] = [et.value for et in request.event_types]
        if request.cursor:
            params["cursor"] = request.cursor

        raw: PaginatedEventsResponse = self._get(
            f"/users/{request.user_id}/events", params=params
        )
        return _parse_event_page(raw)

    def get_event(self, event_id: str) -> ActivityEvent:
        raw: ActivityEventResponse = self._get(f"/events/{event_id}")
        return _parse_activity_event(raw)

    # -- HTTP helpers --

    def _get(self, path: str, **kwargs: Any) -> Any:
        return self._request("GET", path, **kwargs)

    def _patch(self, path: str, **kwargs: Any) -> Any:
        return self._request("PATCH", path, **kwargs)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._http.request(method, path, **kwargs)
        _raise_for_status(response)
        return response.json()

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "APIClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


# -- Standalone conversion functions --

def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _parse_user_profile(raw: UserProfileResponse) -> UserProfile:
    return UserProfile(
        id=raw["id"],
        username=raw["username"],
        email=raw["email"],
        display_name=raw["display_name"],
        created_at=_parse_timestamp(raw["created_at"]),
        is_active=raw["is_active"],
        metadata=raw["metadata"],
    )


def _parse_activity_event(raw: ActivityEventResponse) -> ActivityEvent:
    return ActivityEvent(
        id=raw["id"],
        user_id=raw["user_id"],
        event_type=EventType(raw["event_type"]),
        occurred_at=_parse_timestamp(raw["occurred_at"]),
        payload=raw["payload"],
    )


def _parse_event_page(raw: PaginatedEventsResponse) -> EventPage:
    return EventPage(
        items=tuple(_parse_activity_event(e) for e in raw["items"]),
        total=raw["total"],
        page=raw["page"],
        page_size=raw["page_size"],
        next_cursor=raw.get("next_cursor"),
    )


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    message = _extract_message(response)
    match response.status_code:
        case 401 | 403:
            raise AuthenticationError(message, status_code=response.status_code)
        case 404:
            raise NotFoundError(message, status_code=404)
        case 429:
            retry_after = _parse_retry_after(response)
            raise RateLimitError(message, retry_after=retry_after)
        case code if 500 <= code < 600:
            raise ServerError(message, status_code=code)
        case _:
            raise APIError(message, status_code=response.status_code)


def _extract_message(response: httpx.Response) -> str:
    with contextlib.suppress(Exception):
        return response.json().get("message", response.text)
    return response.text


def _parse_retry_after(response: httpx.Response) -> int | None:
    value = response.headers.get("Retry-After")
    if value and value.isdigit():
        return int(value)
    return None
```

---

### `__init__.py` — Public API

Define `__all__` to make the public surface explicit.

```python
"""api_client — Python client for the user profile and activity API."""

from .client import APIClient
from .errors import APIError, AuthenticationError, NotFoundError, RateLimitError, ServerError
from .models import ActivityEvent, EventPage, EventType, UserProfile
from .requests import GetEventsRequest, UpdateProfileRequest
from ._protocols import ActivityAPI, UserProfileAPI

__all__ = [
    # Client
    "APIClient",
    # Protocols (for type annotations in caller code)
    "UserProfileAPI",
    "ActivityAPI",
    # Domain models
    "UserProfile",
    "ActivityEvent",
    "EventPage",
    "EventType",
    # Request models
    "GetEventsRequest",
    "UpdateProfileRequest",
    # Errors
    "APIError",
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
]
```

---

## Usage Example

```python
from api_client import APIClient, GetEventsRequest, EventType, UpdateProfileRequest

# Context manager ensures connection cleanup
with APIClient(api_key="secret") as client:
    # Fetch a user profile
    user = client.get_user("usr_123")
    print(user.display_name)  # immutable frozen dataclass

    # Paginate events — Pydantic validates page_size before the request goes out
    request = GetEventsRequest(
        user_id="usr_123",
        page_size=50,
        event_types=[EventType.LOGIN, EventType.LOGOUT],
    )
    page = client.get_events(request)
    for event in page.items:
        print(event.event_type, event.occurred_at)

    if page.has_next:
        next_request = GetEventsRequest(
            user_id="usr_123",
            page_size=50,
            cursor=page.next_cursor,
        )
        next_page = client.get_events(next_request)
```

---

## Key Design Rules Applied

1. **Pydantic at the boundary** — `GetEventsRequest` and `UpdateProfileRequest` validate caller-supplied inputs before anything reaches the network.

2. **TypedDict for raw JSON** — `UserProfileResponse`, `ActivityEventResponse`, and `PaginatedEventsResponse` model the raw wire format with zero runtime overhead. They do not validate; they document shape.

3. **Frozen dataclasses for domain objects** — `UserProfile`, `ActivityEvent`, `EventPage`, and `EventType` are meaningful names with meaning in the domain. They are immutable after construction; `replace()` creates updated copies.

4. **StrEnum for fixed sets** — `EventType` prevents typo bugs like `"logi"` passing silently. Structural pattern matching works naturally with `StrEnum`.

5. **Protocols for the public contract** — `UserProfileAPI` and `ActivityAPI` are what callers type against in their own code. The concrete `APIClient` is an implementation detail — swappable with a mock or a test double.

6. **Standalone conversion functions** — `_parse_user_profile`, `_parse_activity_event`, and `_parse_event_page` are module-level functions, not methods. They are pure, testable in isolation, and don't couple the parsing logic to the HTTP client.

7. **Shallow error hierarchy** — Four concrete error types under `APIError`. Callers catch the specific type they care about. No bare `except`.

8. **Context manager for cleanup** — `APIClient` implements `__enter__`/`__exit__` so `with APIClient(...) as client:` closes the underlying HTTP connection without caller ceremony.

9. **`__all__` in every module** — The public surface is explicit and grep-able. Internal helpers like `_raise_for_status` and `_parse_timestamp` are underscore-prefixed and excluded.
