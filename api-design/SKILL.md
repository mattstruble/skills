---
name: api-design
description: AEP-compliant REST/gRPC API design — resource modeling, standard methods (Get/List/Create/Update/Delete), resource paths, field naming, pagination, error handling, and design patterns. Use this skill whenever designing or reviewing APIs, writing OpenAPI specs or protobuf definitions, deciding how to model resources and relationships, naming endpoints or fields, handling pagination or errors, or structuring CRUD operations. Also trigger when the user asks about API design best practices, wants to know how to version an API, is unsure whether to use a custom method vs. standard method, needs to design a collection endpoint, or wants to review an existing API for consistency problems — even if they don't explicitly mention AEP. Trigger when someone asks "what's wrong with this API design", wants to add search/filter to a collection, or is choosing between HTTP verbs and resource paths.
---

# AEP-Compliant API Design

Design APIs according to [AEP](https://aep.dev/) — an open standard from Google, Microsoft, Roblox, and IBM. The payoff: Terraform providers, CLIs, UIs, and MCP servers work automatically because they can predict the shape of your API from its resource hierarchy.

**Core principle: design resource hierarchies (nouns), not procedure collections (verbs).** This is the single most important decision — it determines whether tooling can auto-generate clients, whether your API is learnable, and whether it scales gracefully.

---

## 1. Resource-Oriented Design (AEP-121)

Start every design by asking:
1. What are the resources (things)?
2. What's the parent-child hierarchy?
3. What does each resource's schema look like?
4. Which standard methods does each resource need?

**Before (verb-oriented — hard to learn, impossible to auto-generate clients for):**
```
POST /v1/createProject
POST /v1/archiveProject
POST /v1/getProjectTasks
POST /v1/assignTaskToUser
```

**After (resource-oriented — predictable, tooling-friendly):**
```
POST   /v1/projects                          # Create
GET    /v1/projects/{project_id}             # Get
GET    /v1/projects                          # List
PATCH  /v1/projects/{project_id}             # Update
DELETE /v1/projects/{project_id}             # Delete
POST   /v1/projects/{project_id}:archive     # Custom method (state transition)
GET    /v1/projects/{project_id}/tasks       # Nested collection
POST   /v1/projects/{project_id}/tasks/{task_id}/assignments  # Sub-resource
```

**Design guidance:**

- Model a resource hierarchy, not a database schema — the API is a contract, not a DB mirror. Clients shouldn't need to understand your storage layer.
- Every resource needs at minimum `Get` (so clients can verify state after mutations) and `List` (except singletons). Without `Get`, clients can't confirm their writes took effect.
- Prefer standard methods. Reserve custom methods for operations that genuinely don't fit CRUDL — the more standard your API, the more tooling works for free.
- After a mutation completes (including after an LRO reaches `done=true`), a subsequent `Get` must reflect the final state. Violating this breaks optimistic UI patterns and declarative reconciliation loops.
- Resource relationships must form a DAG — no cycles. Circular references make creation and deletion ordering impossible to determine.

---

## 2. Resource Paths (AEP-122)

Resources are identified by their **path** — a URI-like string clients should store and use as a stable reference.

```
publishers/acme/books/les-miserables
users/vhugo1802/events/birthday-dinner-226/guests/123
```

**Design guidance:**

- `path` is output-only (`readOnly: true`) — clients should never set paths because the server owns the resource hierarchy, and client-set paths create collision and security risks.
- Collection identifiers: plural, kebab-case, lowercase ASCII (`book-editions`, not `BookEditions`). Consistency here is what makes paths predictable and guessable.
- Resource IDs follow RFC-1034 (lowercase, hyphens, starts with letter, max 63 chars). Avoid UUIDs or ULIDs as user-specified IDs — they violate RFC-1034 format (UUIDs can start with a digit; ULIDs use base32 characters outside `[a-z0-9-]`), making them non-conformant and awkward in nested paths.
- Path parameter variable names in URI templates: `{resourceName_id}` — e.g., `{book_id}`, `{publisher_id}`. Bare `{book}` is ambiguous (is it a path or an ID?), and camelCase `{bookId}` breaks consistency with snake_case field names.
- For nested List/Create, parent path is a prefix: `GET /v1/publishers/{publisher_id}/books`. This makes the hierarchy explicit in the URL.
- Fields referencing other resources use that resource's path, not just an ID. Field name: snake_case singular of the resource type (`shelf`, `publisher`). Using full paths instead of bare IDs lets clients navigate the API without needing to know how to construct paths themselves.

---

## 3. Standard Methods (AEP-130–137)

Use in this order of preference: standard → batch → custom → streaming (last resort). Each step down this ladder costs you tooling compatibility.

### Get (AEP-131)
- `GET /v1/{path}`; request has a single `path` field; response is the resource.

### List (AEP-132)
- `GET /v1/{parent}/subcollection`
- Request: `parent`, `max_page_size`, `page_token`; optional `filter`, `order_by`
- Response array must be named `results` (not the resource type name like `books`) — using a consistent name means clients don't need to know the resource type to parse the response
- Add `bool show_deleted` if the resource supports soft-delete
- Paginate from day one — adding pagination later is a breaking change because existing clients that don't send `page_token` will silently get only the first page

**Before (no pagination — breaks when data grows):**
```
GET /v1/books
→ { "books": [...all 50,000 books...] }
```

**After (paginated from day one):**
```
GET /v1/books?max_page_size=100
→ {
    "results": [...100 books...],
    "next_page_token": "eyJvZmZzZXQiOjEwMH0",
    "total_size": 50000
  }
```

### Create (AEP-133)
- `POST /v1/{parent}/subcollection`; body is the resource itself (no wrapper)
- `id` is a **query parameter**, not a body field: `POST /v1/tasks?id=my-task`. This keeps the body a clean resource representation.
- Support user-specified IDs — without them, Create is not safely retryable (a crash between send and receive leaves the client unable to know if the resource was created) and declarative clients (Terraform, CLI) can't reconcile state. Flag absence as a violation in reviews.
- Duplicate ID → `409 ALREADY_EXISTS`. But if caller lacks permission to see the duplicate → `403 PERMISSION_DENIED`. Returning 409 when the caller can't see the resource leaks information about what exists.

### Update (AEP-134)
- `PATCH /v1/{path}` with `Content-Type: application/merge-patch+json` — omitted fields are unchanged.
- In protobuf, include a `FieldMask update_mask`; support `update_mask: *` for full replacement.
- Use `PATCH` with merge-patch semantics, not `PUT` — PUT requires sending the full resource, so adding a new field to the schema silently becomes a breaking change (clients that don't know about the new field send requests that reset it to its zero value).
- Don't make state fields writable via Update; use custom methods for state transitions. State machines need validation logic that Update can't express.

**Before (PUT — breaks on schema evolution):**
```
PUT /v1/books/les-miserables
Content-Type: application/json
{ "title": "Les Misérables", "author": "Victor Hugo" }
// Adding a new "isbn" field? Old clients now silently clear it on every update.
```

**After (PATCH merge-patch — additive and safe):**
```
PATCH /v1/books/les-miserables
Content-Type: application/merge-patch+json
{ "title": "Les Misérables — Updated Edition" }
// Only title changes. isbn, author, and any future fields are untouched.
```

### Delete (AEP-135)
- `DELETE /v1/{path}` → `204 No Content`; `202 Accepted` for LROs.
- If a resource has first-class child resources with independent lifecycle, require `force: bool`. Without `force=true` → `409 FAILED_PRECONDITION`. This prevents accidental cascading deletes. Junction/join records (no independent lifecycle) don't need `force`.

### Custom Methods (AEP-136)
- `POST /v1/{path}:actionName` — colon-prefixed verb in the URI.
- OpenAPI operationId: `:ArchiveBook`; gRPC: `ArchiveBook`.
- Use for state transitions and genuinely imperative actions that can't be expressed as a field update — e.g., `:archive`, `:publish`, `:cancel`. The colon syntax signals "this is a verb, not a resource" to both humans and tooling.

### OperationId / RPC Naming (AEP-130)
- Standard: `{Verb}{Singular}` — `GetBook`, `CreateBook`, `UpdateBook`, `DeleteBook`
- List: `List{Plural}` — `ListBooks`

---

## 4. Field Naming (AEP-140)

Consistent naming is what makes an API feel coherent and learnable. These rules eliminate the "which convention did they use here?" friction.

- `lower_snake_case` in JSON and protobuf — mixing conventions within an API is a common source of client bugs.
- Arrays: plural (`books`). Singular fields: singular (`book`). This makes it immediately obvious whether a field is a list or a scalar.
- Booleans: drop `is_` prefix — `disabled` not `is_disabled`. Must be nouns/adjectives, not verbs. `is_` prefixes are redundant (the type already tells you it's boolean) and create inconsistency when some booleans have it and others don't.
- Avoid prepositions (`error_reason` not `reason_for_error`). Adjectives before nouns (`collected_items`). Prepositions make names longer without adding clarity.
- URLs/URIs: use `_uri` suffix, not `_url`. AEP standardizes on `_uri` to avoid the URL/URI ambiguity.
- `display_name`: human-readable, no uniqueness requirement. `title`: official/formal names. Using the right one signals to clients whether they can rely on uniqueness.
- Don't embed the enclosing type name in field names (`display_name` not `task_name` inside `Task`). Redundant type prefixes make field names longer and create awkward repetition like `task.task_name`.
- Times: RFC 3339 strings (`"2024-01-15T10:30:00Z"`). Durations: `Duration` type, not two fields. Quantities with units: embed the unit (`distance_km`, `price_usd`). Unitless numeric fields are a perennial source of integration bugs.

---

## 5. Standard Fields (AEP-142, AEP-148)

These fields appear on every resource. Standardizing them means clients can write generic code that works across all your resources.

| Field | Type | Requirement |
|-------|------|-------------|
| `path` | string | **Must** — output-only, every resource |
| `display_name` | string | **Should** |
| `create_time` | RFC 3339 timestamp | **Must** — output-only |
| `update_time` | RFC 3339 timestamp | **Must** — output-only, any resource with Update |
| `delete_time` | RFC 3339 timestamp | **Should** — if soft-delete used |
| `etag` | string | **Should** — optimistic concurrency |

Use `_time` suffix, never `_at` or camelCase (`created_at`, `createdAt` are wrong). The `_time` suffix is what makes these fields recognizable as timestamps across all AEP-compliant APIs.

---

## 6. Pagination (AEP-158)

**Request:** `max_page_size` (int; 0 = server default; reject negatives with `INVALID_ARGUMENT`), `page_token` (opaque, not required), optional `skip`, `filter`, `order_by`.

**Response:** `results` (the array), `next_page_token` (empty string = end of collection), optional `total_size`.

Page tokens are opaque and URL-safe. They authorize continuation, not resource access — verify permissions on every paginated request, not just the first one. A user whose access is revoked mid-pagination should get `403` on the next page, not continue seeing data.

---

## 7. Error Handling (AEP-193)

Use [RFC 9457 Problem Details](https://datatracker.ietf.org/doc/html/rfc9457). Structured errors are what allow clients to handle errors programmatically rather than parsing human-readable strings. Error responses must use `Content-Type: application/problem+json` — always show this header in response examples, it's part of the protocol contract.

**Before (ad-hoc error — unstructured, unparseable):**
```
HTTP/1.1 429 Too Many Requests
Content-Type: application/json

{ "error": "Rate limit exceeded. Try again later." }
```

**After (RFC 9457 Problem Details — structured, actionable, programmatically parseable):**
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

- `type`: a URI identifying the error category — not a bare string. Use a stable URL your docs explain.
- `title`: non-sensitive, loggable. No PII. This is what goes in your monitoring dashboard.
- `detail`: may contain PII, request-specific, do not log. Must be actionable — tell the user what to do, not just what went wrong.
- Dynamic variables in `detail` must also appear as top-level fields for programmatic access. If you mention "zone 'us-east1-a'" in `detail`, also include `"zone": "us-east1-a"` so clients can act on it without parsing strings.

**Permission check order — always enforce this sequence:**
1. Check permissions first — before any existence check.
2. Caller lacks permission → `403 PERMISSION_DENIED` (even if the resource doesn't exist — checking existence first leaks information about what resources exist to unauthorized callers).
3. Caller has permission but resource missing → `404 NOT_FOUND`.

---

## 8. Common Patterns

**Long-running Operations (AEP-151):** Use LROs whenever the work happens asynchronously — video transcoding, bulk imports, image processing, indexing, any pipeline that runs in the background. Return `202 Accepted` with an `Operation` resource (`path`, `done`, `metadata`, `response`, `error`). Expose `GET /v1/operations/{operation_id}` and `GET /v1/operations`. Resources created via LRO should appear in List/Get immediately with a `state` indicating they're not yet usable — this lets clients poll for readiness without a separate "does it exist yet?" check.

**Soft Delete (AEP-164):** Add `delete_time` field + `Undelete` custom method. List requests include `bool show_deleted`. Soft delete is preferable to hard delete when resources have audit trails or when users might need to recover them.

**Resource States (AEP-216):** Output-only `state` enum. States not directly writable via Update — use custom methods for transitions (`Activate`, `Deactivate`). This enforces valid state machine transitions server-side rather than trusting clients to send valid states. Naming: `ACTIVE`, past participles for terminal (`SUCCEEDED`, `FAILED`), present participles for in-progress (`CREATING`). Always include `STATE_UNSPECIFIED` (value 0 in protobuf). Enum values use `UPPER_SNAKE_CASE` in both JSON and protobuf — `"status": "IN_PROGRESS"`, not `"in_progress"` (AEP-126).

**Idempotency (AEP-155):** Use `etag` on resources for safe concurrent updates. For custom methods, accept a structured `idempotency_key` field (with `key` and `first_sent`) — not an HTTP header. HTTP headers are often stripped by proxies and load balancers; body fields are more reliable.

**Validate-only / Dry Run (AEP-163):** Support `validate_only: bool` on Create/Update/Delete. Server validates and returns errors (or success) with no actual change. This is especially valuable for complex resources where validation failures are expensive to discover after the fact.

**Singleton Resources (AEP-156):** Child resources that exist exactly once per parent have no ID segment: `publishers/acme/settings` (not `publishers/acme/settings/main`). No Create/Delete needed — the singleton exists implicitly when the parent exists.

**Enumerations (AEP-126):** Always include `UNSPECIFIED` (value 0 in protobuf). Use strings for open-ended sets (language codes, etc.). `UNSPECIFIED` as value 0 means uninitialized proto messages don't accidentally default to a meaningful state.

---

## Quick Checklist for Reviews

- [ ] Each resource has a Get endpoint (singletons exempt from List; all others need both Get + List)
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
- [ ] User-specified IDs supported on Create
- [ ] State transitions use custom methods, not Update
- [ ] Delete with child resources uses `force: bool`
- [ ] Mutable resources include `etag` for optimistic concurrency
