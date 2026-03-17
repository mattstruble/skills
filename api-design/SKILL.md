---
name: api-design
description: AEP-compliant REST/gRPC API design — resource modeling, standard methods (Get/List/Create/Update/Delete), resource paths, field naming, pagination, error handling, and design patterns. Use this skill whenever designing or reviewing APIs, writing OpenAPI specs or protobuf definitions, deciding how to model resources and relationships, naming endpoints or fields, handling pagination or errors, or structuring CRUD operations. Also trigger when the user asks about API design best practices, wants to know how to version an API, is unsure whether to use a custom method vs. standard method, needs to design a collection endpoint, or wants to review an existing API for consistency problems — even if they don't explicitly mention AEP.
---

# AEP-Compliant API Design

Design APIs according to [AEP](https://aep.dev/) — an open standard from Google, Microsoft, Roblox, and IBM. The payoff: Terraform providers, CLIs, UIs, and MCP servers work automatically.

**Core principle: design resource hierarchies (nouns), not procedure collections (verbs).**

---

## 1. Resource-Oriented Design (AEP-121)

Start every design by asking:
1. What are the resources (things)?
2. What's the parent-child hierarchy?
3. What does each resource's schema look like?
4. Which standard methods does each resource need?

**Rules:**
- Model a resource hierarchy, not a database schema — the API is a contract, not a DB mirror.
- Every resource needs at minimum `Get` (so clients can verify state after mutations) and `List` (except singletons).
- Prefer standard methods. Reserve custom methods for operations that genuinely don't fit CRUDL.
- After a mutation completes (including after an LRO reaches `done=true`), a subsequent `Get` must reflect the final state.
- Resource relationships must form a DAG — no cycles (circular refs make creation/deletion very hard).

---

## 2. Resource Paths (AEP-122)

Resources are identified by their **path** — a URI-like string clients should store and use.

```
publishers/acme/books/les-miserables
users/vhugo1802/events/birthday-dinner-226/guests/123
```

**Rules:**
- `path` is output-only (`readOnly: true`). Never client-settable.
- Collection identifiers: plural, kebab-case, lowercase ASCII (`book-editions`, not `BookEditions`).
- Resource IDs follow RFC-1034 (lowercase, hyphens, starts with letter, max 63 chars). **No UUIDs or ULIDs as user-specified IDs** — AEP-122 prohibits them.
- Path parameter variable names in URI templates: `{resourceName_id}` — e.g., `{book_id}`, `{publisher_id}`. Never bare `{book}` or camelCase `{bookId}`.
- For nested List/Create, parent path is a prefix: `GET /v1/publishers/{publisher_id}/books`.
- Fields referencing other resources use that resource's path, not just an ID. Field name: snake_case singular of the resource type (`shelf`, `publisher`).

---

## 3. Standard Methods (AEP-130–137)

Use in this order: standard → batch → custom → streaming (last resort).

### Get (AEP-131)
- `GET /v1/{path}`; request has a single `path` field; response is the resource.

### List (AEP-132)
- `GET /v1/{parent}/subcollection`
- Request: `parent`, `max_page_size`, `page_token`; optional `filter`, `order_by`
- Response array **must** be named `results` (not the resource type name like `books`)
- Add `bool show_deleted` if the resource supports soft-delete
- **Paginate from day one** — adding pagination later is a breaking change

### Create (AEP-133)
- `POST /v1/{parent}/subcollection`; body is the resource itself (no wrapper)
- `id` is a **query parameter**, not a body field: `POST /v1/tasks?id=my-task`
- Support user-specified IDs — without them, every Create is non-idempotent and declarative clients (Terraform, CLI) can't reconcile state. Flag absence as a violation in reviews.
- Duplicate ID → `409 ALREADY_EXISTS`. But if caller lacks permission to see the duplicate → `403 PERMISSION_DENIED`.

### Update (AEP-134)
- `PATCH /v1/{path}` with `Content-Type: application/merge-patch+json` — omitted fields unchanged.
- In protobuf, include a `FieldMask update_mask`; support `update_mask: *` for full replacement.
- Never use `PUT` — it breaks when new fields are added.
- Don't make state fields writable via Update; use custom methods for state transitions.

### Delete (AEP-135)
- `DELETE /v1/{path}` → `204 No Content`; `202 Accepted` for LROs.
- If a resource has first-class child resources with independent lifecycle, require `force: bool`. Without `force=true` → `409 FAILED_PRECONDITION`. Junction/join records (no independent lifecycle) don't need `force`.

### Custom Methods (AEP-136)
- `POST /v1/{path}:actionName` — colon-prefixed verb in the URI.
- OpenAPI operationId: `:ArchiveBook`; gRPC: `ArchiveBook`.
- Use for state transitions and genuinely imperative actions.

### OperationId / RPC Naming (AEP-130)
- Standard: `{Verb}{Singular}` — `GetBook`, `CreateBook`, `UpdateBook`, `DeleteBook`
- List: `List{Plural}` — `ListBooks`

---

## 4. Field Naming (AEP-140)

- `lower_snake_case` in JSON and protobuf.
- Arrays: plural (`books`). Singular fields: singular (`book`).
- Booleans: drop `is_` prefix — `disabled` not `is_disabled`. Must be nouns/adjectives, not verbs.
- Avoid prepositions (`error_reason` not `reason_for_error`). Adjectives before nouns (`collected_items`).
- URLs/URIs: use `_uri` suffix, not `_url`.
- `display_name`: human-readable, no uniqueness requirement. `title`: official/formal names.
- Don't embed the enclosing type name in field names (`display_name` not `task_name` inside `Task`).
- Times: RFC 3339 strings (`"2024-01-15T10:30:00Z"`). Durations: `Duration` type, not two fields. Quantities with units: embed the unit (`distance_km`, `price_usd`).

---

## 5. Standard Fields (AEP-142, AEP-148)

| Field | Type | Requirement |
|-------|------|-------------|
| `path` | string | **Must** — output-only, every resource |
| `display_name` | string | **Should** |
| `create_time` | RFC 3339 timestamp | **Must** — output-only |
| `update_time` | RFC 3339 timestamp | **Must** — output-only, any resource with Update |
| `delete_time` | RFC 3339 timestamp | **Should** — if soft-delete used |
| `etag` | string | **Should** — optimistic concurrency |

Use `_time` suffix, never `_at` or camelCase (`created_at`, `createdAt` are wrong).

---

## 6. Pagination (AEP-158)

**Request:** `max_page_size` (int; 0 = server default; reject negatives with `INVALID_ARGUMENT`), `page_token` (opaque, not required), optional `skip`, `filter`, `order_by`.

**Response:** `results` (the array), `next_page_token` (empty string = end of collection), optional `total_size`.

Page tokens are opaque and URL-safe. They authorize continuation, not resource access — verify permissions on every paginated request.

---

## 7. Error Handling (AEP-193)

Use [RFC 9457 Problem Details](https://datatracker.ietf.org/doc/html/rfc9457). Error responses **must** use `Content-Type: application/problem+json`. Always show this header in response examples — it's part of the protocol contract, not just a note.

```
HTTP/1.1 429 Too Many Requests
Content-Type: application/problem+json

{
  "type": "RESOURCE_EXHAUSTED",
  "status": 429,
  "title": "Too Many Requests",
  "detail": "Zone 'us-east1-a' is out of capacity. Try us-west1-a or retry in 5 minutes.",
  "instance": "7934df3e-4b63-429b-b0f5-b8d350ec165e",
  "zone": "us-east1-a"
}
```

- `title`: non-sensitive, loggable. No PII.
- `detail`: may contain PII, request-specific, do not log. Must be actionable.
- Dynamic variables in `detail` must also appear as top-level fields for programmatic access.

**Permission check order (always enforce):**
1. Check permissions **first** — before any existence check.
2. Caller lacks permission → `403 PERMISSION_DENIED` (even if the resource doesn't exist — checking existence first leaks information).
3. Caller has permission but resource missing → `404 NOT_FOUND`.

---

## 8. Common Patterns

**Long-running Operations (AEP-151):** Use LROs whenever the work happens asynchronously — this includes video transcoding, bulk imports, image processing, indexing, and any other pipeline that runs in the background after the request returns. Return `202 Accepted` with an `Operation` resource (`path`, `done`, `metadata`, `response`, `error`). Expose `GET /v1/operations/{operation_id}` and `GET /v1/operations`. Resources created via LRO should appear in List/Get immediately with a `state` indicating they're not yet usable.

**Soft Delete (AEP-164):** Add `delete_time` field + `Undelete` custom method. List requests include `bool show_deleted`.

**Resource States (AEP-216):** Output-only `state` enum. States not directly writable via Update — use custom methods for transitions (`Activate`, `Deactivate`). Naming: `ACTIVE`, past participles for terminal (`SUCCEEDED`, `FAILED`), present participles for in-progress (`CREATING`). Always include `STATE_UNSPECIFIED` (value 0 in protobuf). Enum values use `UPPER_SNAKE_CASE` in both JSON and protobuf — `"status": "IN_PROGRESS"`, not `"in_progress"` (AEP-126).

**Idempotency (AEP-155):** Use `etag` on resources for safe concurrent updates. For custom methods, accept a structured `idempotency_key` field (with `key` and `first_sent`) — not an HTTP header.

**Validate-only / Dry Run (AEP-163):** Support `validate_only: bool` on Create/Update/Delete. Server validates and returns errors (or success) with no actual change.

**Singleton Resources (AEP-156):** Child resources that exist exactly once per parent have no ID segment: `publishers/acme/settings` (not `publishers/acme/settings/main`). No Create/Delete needed.

**Enumerations (AEP-126):** Always include `UNSPECIFIED` (value 0 in protobuf). Use strings for open-ended sets (language codes, etc.).

---

## Quick Checklist for Reviews

- [ ] Each resource has a Get endpoint (every resource requires at minimum Get + List)
- [ ] List response array is `results`, not the resource type name
- [ ] Path params use `{resource_id}` form, not `{resource}` or `{resourceId}`
- [ ] `id` for Create is a query param, not body field
- [ ] `update_time` present on every mutable resource
- [ ] Timestamps use `_time` suffix and RFC 3339 format
- [ ] Pagination in place on all List methods
- [ ] Permissions checked before existence on every request
- [ ] Error responses use `Content-Type: application/problem+json`
- [ ] No `PUT` for updates (use `PATCH` + merge-patch)
- [ ] LROs return `202 Accepted`, not `200`/`201`
- [ ] No cyclic resource references
