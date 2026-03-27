# API Design Patterns

Detailed pattern guidance for AEP-compliant APIs. Read when implementing specific patterns that need more detail than the SKILL.md summary provides.

---

## Pagination (AEP-158)

Add pagination from day one — retrofitting is a breaking change (existing clients silently get only the first page).

**Request fields:** `max_page_size` (int; 0 = server default; reject negatives with `INVALID_ARGUMENT`), `page_token` (opaque, not required), optional `skip`, `filter`, `order_by`.

**Response fields:** `results` (the array), `next_page_token` (empty string = end of collection), optional `total_size`.

Page tokens are opaque and URL-safe. They authorize continuation, not resource access — verify permissions on every paginated request. A user whose access is revoked mid-pagination should get `403` on the next page.

**Example:**
```
GET /v1/books?max_page_size=100
-> {
    "results": [...100 books...],
    "next_page_token": "eyJvZmZzZXQiOjEwMH0",
    "total_size": 50000
  }
```

---

## Error Handling (AEP-193)

Use [RFC 9457 Problem Details](https://datatracker.ietf.org/doc/html/rfc9457). Error responses must use `Content-Type: application/problem+json`.

**Before (ad-hoc — unparseable):**
```
HTTP/1.1 429 Too Many Requests
Content-Type: application/json

{ "error": "Rate limit exceeded. Try again later." }
```

**After (RFC 9457 — structured, actionable):**
```
HTTP/1.1 429 Too Many Requests
Content-Type: application/problem+json

{
  "type": "https://aep.dev/errors/resource-exhausted",
  "status": 429,
  "title": "Too Many Requests",
  "detail": "Zone 'us-east1-a' is out of capacity. Try us-west1-a or retry in 5 minutes.",
  "instance": "7934df3e-4b63-429b-b0f5-b8d350ec165e",
  "zone": "us-east1-a"
}
```

**Field guidance:**
- `type`: URI identifying the error category. Use a stable URL your docs explain.
- `title`: non-sensitive, loggable. No PII. Goes in monitoring dashboards.
- `detail`: may contain PII, request-specific, do not log. Must be actionable — tell the user what to do.
- Dynamic variables in `detail` must also appear as top-level fields for programmatic access (e.g., `"zone": "us-east1-a"`).

**Permission check order:**
1. Check permissions first — before any existence check.
2. Caller lacks permission -> `403 PERMISSION_DENIED` (even if resource doesn't exist — checking existence first leaks information).
3. Caller has permission but resource missing -> `404 NOT_FOUND`.

---

## Long-running Operations (AEP-151)

Use LROs when work happens asynchronously — video transcoding, bulk imports, image processing, indexing.

Return `202 Accepted` with an `Operation` resource:
- Fields: `path`, `done`, `metadata`, `response`, `error`
- `response` and `error` are mutually exclusive — exactly one is populated when `done: true`
- Expose `GET /v1/operations/{operation_id}` and `GET /v1/operations`

Resources created via LRO should appear in List/Get immediately with a `state` field indicating they're not yet usable. This lets clients poll for readiness without a separate "does it exist yet?" check.

---

## Soft Delete (AEP-164)

Add `delete_time` field + `Undelete` custom method (`:undelete`). List requests include `bool show_deleted`. Prefer soft delete when resources have audit trails or users might need recovery.

---

## Resource States (AEP-216)

Output-only `state` enum. States not directly writable via Update — use custom methods for transitions (`Activate`, `Deactivate`). This enforces valid state machine transitions server-side.

**Naming conventions:**
- `ACTIVE` for active states
- Past participles for terminal states: `SUCCEEDED`, `FAILED`
- Present participles for in-progress states: `CREATING`, `DELETING`
- Always include `STATE_UNSPECIFIED` (value 0 in protobuf)
- Values use `UPPER_SNAKE_CASE` in both JSON and protobuf — `"status": "IN_PROGRESS"`, not `"in_progress"` (AEP-126)

---

## Idempotency (AEP-155)

Use `etag` on resources for safe concurrent updates. For custom methods, accept a structured `idempotency_key` field (with `key` and `first_sent`) in the request body — not an HTTP header. Headers are often stripped by proxies and load balancers; body fields are more reliable.

---

## Validate-only / Dry Run

Support `validate_only: bool` on Create/Update/Delete. Server validates and returns errors (or success) with no actual change. Valuable for complex resources where validation failures are expensive to discover after the fact.

---

## Singleton Resources (AEP-156)

Child resources that exist exactly once per parent have no ID segment: `publishers/acme/settings` (not `publishers/acme/settings/main`). No Create/Delete needed — the singleton exists implicitly when the parent exists.

---

## Enumerations (AEP-126)

Always include `UNSPECIFIED` (value 0 in protobuf) — prevents uninitialized messages from defaulting to a meaningful state. Use `UPPER_SNAKE_CASE` values. Use strings for open-ended sets (language codes, etc.).
