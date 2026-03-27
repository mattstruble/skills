---
name: api-design
description: AEP-compliant REST/gRPC API design — resource modeling, standard methods (Get/List/Create/Update/Delete), resource paths, field naming, pagination, error handling, and design patterns. Use this skill whenever designing or reviewing APIs, writing OpenAPI specs or protobuf definitions, deciding how to model resources and relationships, naming endpoints or fields, handling pagination or errors, or structuring CRUD operations. Also trigger when the user asks about API design best practices, wants to know how to version an API, is unsure whether to use a custom method vs. standard method, needs to design a collection endpoint, or wants to review an existing API for consistency problems — even if they don't explicitly mention AEP. Trigger when someone asks "what's wrong with this API design", wants to add search/filter to a collection, or is choosing between HTTP verbs and resource paths.
---

# AEP-Compliant API Design

Design APIs following [AEP](https://aep.dev/) (Google, Microsoft, Roblox, IBM). The payoff: Terraform providers, CLIs, UIs, and MCP servers auto-generate because they can predict the API shape from resource hierarchies.

**Core principle: design resource hierarchies (nouns), not procedure collections (verbs).**

---

## Design Process

For every API, answer these four questions in order:
1. What are the resources (things)?
2. What's the parent-child hierarchy?
3. What does each resource's schema look like?
4. Which standard methods does each resource need?

**Before (verb-oriented — hard to auto-generate clients):**
```
POST /v1/createProject
POST /v1/archiveProject
POST /v1/getProjectTasks
```

**After (resource-oriented — predictable, tooling-friendly):**
```
POST   /v1/projects                       # Create
GET    /v1/projects/{project_id}          # Get
GET    /v1/projects                       # List
PATCH  /v1/projects/{project_id}          # Update
DELETE /v1/projects/{project_id}          # Delete
POST   /v1/projects/{project_id}:archive  # Custom method (state transition)
GET    /v1/projects/{project_id}/tasks    # Nested collection
```

Model a resource hierarchy, not a database schema — the API is a contract, not a DB mirror. Resource relationships must form a DAG (no cycles).

---

## Standard Methods (AEP-130–135)

Prefer standard > batch > custom > streaming. Each step down costs tooling compatibility.

| Method | Verb + Path | Key Rules |
|--------|------------|-----------|
| **Get** | `GET /v1/{path}` | Every resource needs Get so clients can verify mutations |
| **List** | `GET /v1/{parent}/collection` | Response array is **`results`**, not the type name. Paginate from day one |
| **Create** | `POST /v1/{parent}/collection?id=X` | ID is a **query param**, not body. Support user-specified IDs by default |
| **Update** | `PATCH /v1/{path}` | Merge-patch semantics (`application/merge-patch+json`). Never `PUT` |
| **Delete** | `DELETE /v1/{path}` | Require `force: bool` when first-class children exist |
| **Custom** | `POST /v1/{path}:verb` | State transitions that can't be expressed as field updates |

OperationId naming: `{Verb}{Singular}` for standard (`GetBook`, `CreateBook`), `List{Plural}` for List (`ListBooks`).

---

## Conventions That Diverge From Common Practice

These AEP rules are the ones most likely to be missed. Each exists for a specific reason:

- **`results` array in List responses** — not `books` or `users`. A consistent name lets generic clients parse any collection without knowing the resource type.
- **`id` as query param on Create** — `POST /v1/tasks?id=my-task`. Keeps the body a clean resource representation. Without user-specified IDs, Create isn't safely retryable and declarative clients (Terraform) can't reconcile state.
- **`PATCH` + merge-patch, never `PUT`** — PUT requires the full resource, so adding a new schema field silently becomes breaking (old clients reset it to zero value on every update).
- **`_time` suffix on timestamps** — `create_time`, `update_time`. Never `_at`, never camelCase. This makes timestamps recognizable across all AEP APIs.
- **Permissions before existence** — always check auth first (-> `403`), then existence (-> `404`). Reversing this leaks which resources exist to unauthorized callers.
- **RFC 9457 errors** — `Content-Type: application/problem+json` with `type`, `status`, `title`, `detail`. Dynamic variables in `detail` must also appear as top-level fields for programmatic access.
- **State transitions via custom methods** — `:archive`, `:publish`, not PATCH on a `state` field. State machines need server-side validation that Update can't express.
- **Duplicate Create ID** -> `409 ALREADY_EXISTS`, unless caller can't see the duplicate -> `403` (avoids leaking existence info).

---

## Review Checklist

- [ ] Resources use nouns, not verbs; hierarchy forms a DAG
- [ ] List response array is `results`
- [ ] Create supports user-specified `id` as query param
- [ ] Update uses `PATCH` + merge-patch, not `PUT`
- [ ] Timestamps use `_time` suffix, RFC 3339 format
- [ ] Pagination on all List methods from day one
- [ ] Permissions checked before existence
- [ ] Errors use `application/problem+json` (RFC 9457)
- [ ] State transitions use custom methods, not Update
- [ ] Delete with children requires `force: bool`
- [ ] `create_time`, `update_time`, `etag` on mutable resources
- [ ] `path` field is output-only on every resource
- [ ] Long-running operations (LROs) return `202 Accepted` with Operation resource

---

## References

| Reference | When to read it |
|-----------|----------------|
| `references/field-naming.md` | Designing paths, naming fields, or reviewing naming consistency |
| `references/patterns.md` | Implementing pagination, error responses, LROs, soft delete, state machines, idempotency, validate-only, singletons, or enumerations |
