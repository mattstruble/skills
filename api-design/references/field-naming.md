# Field Naming and Resource Paths

Detailed naming rules for when the summary in SKILL.md isn't specific enough for the task at hand.

---

## Resource Paths (AEP-122)

Resources are identified by their **path** — a URI-like string clients store and use as a stable reference.

```
publishers/acme/books/les-miserables
users/vhugo1802/events/birthday-dinner-226/guests/123
```

**Rules:**

- `path` is output-only (`readOnly: true`) — the server owns the resource hierarchy. Client-set paths create collision and security risks.
- Collection identifiers: plural, kebab-case, lowercase ASCII (`book-editions`, not `BookEditions`). Consistency makes paths predictable and guessable.
- Resource IDs follow RFC-1034 (lowercase, hyphens, starts with letter, max 63 chars). Avoid UUIDs/ULIDs as user-specified IDs — both can start with a digit, violating the RFC-1034 requirement that labels begin with a letter.
- Path parameter variable names in URI templates: `{resourceName_id}` — e.g., `{book_id}`, `{publisher_id}`. Bare `{book}` is ambiguous; camelCase `{bookId}` breaks consistency with snake_case fields.
- For nested List/Create, parent path is a prefix: `GET /v1/publishers/{publisher_id}/books`.
- Fields referencing other resources use that resource's full path, not just an ID. Field name: snake_case singular of the resource type (`shelf`, `publisher`). Full paths let clients navigate without constructing paths themselves.

---

## Field Naming (AEP-140)

- `lower_snake_case` in JSON and protobuf — mixing conventions causes client bugs.
- Arrays: plural (`books`). Singular fields: singular (`book`). Makes it immediately obvious whether a field is a list or scalar.
- Booleans: drop `is_` prefix — `disabled` not `is_disabled`. Must be nouns/adjectives, not verbs. The type already says it's boolean; `is_` creates inconsistency.
- Avoid prepositions (`error_reason` not `reason_for_error`). Adjectives before nouns (`collected_items`).
- URLs/URIs: use `_uri` suffix, not `_url`. AEP standardizes on `_uri`.
- `display_name`: human-readable, no uniqueness requirement. `title`: official/formal names.
- Don't embed the enclosing type name in field names (`display_name` not `task_name` inside `Task`). Redundant prefixes create awkward repetition like `task.task_name`.
- Times: RFC 3339 strings (`"2024-01-15T10:30:00Z"`). Durations: `Duration` type, not two fields. Quantities with units: embed the unit (`distance_km`, `price_usd`). Unitless numeric fields cause integration bugs.

---

## Standard Fields (AEP-148)

These fields appear on every resource. Standardizing them lets clients write generic code across all resources. Time fields follow AEP-142 conventions.

| Field | Type | Requirement | Notes |
|-------|------|-------------|-------|
| `path` | string | **Must** | Output-only, every resource |
| `display_name` | string | **Should** | Human-readable label |
| `create_time` | RFC 3339 | **Must** | Output-only (AEP-142) |
| `update_time` | RFC 3339 | **Must** | Output-only, any resource with Update (AEP-142) |
| `delete_time` | RFC 3339 | **Should** | If soft-delete is used (AEP-142) |
| `etag` | string | **Should** | Optimistic concurrency (AEP-154) |

Use `_time` suffix always — never `_at` or camelCase (`created_at`, `createdAt` are wrong).
