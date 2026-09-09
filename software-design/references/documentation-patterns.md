# Documentation Patterns

---

## Diátaxis Framework

Documentation serves four distinct purposes. Mixing them produces documents
that serve none well.

| Quadrant | Purpose | Form | Reader state |
|---|---|---|---|
| **Tutorial** | Learning | Guided narrative | "I'm new, teach me" |
| **How-To Guide** | Task completion | Steps | "I know what I want, show me how" |
| **Reference** | Lookup | Comprehensive catalog | "I need a specific fact" |
| **Explanation** | Understanding | Conceptual discussion | "I want to understand why" |

**Common failure:** Mixing explanation into reference docs. Reference must be
complete and scannable — explanation interrupts the scan. When you catch
yourself writing "the reason this works is..." in a reference table, move
that paragraph to an explanation doc and link to it.

---

## Bottom Line Up Front (BLUF)

Readers scan. They decide in the first sentence whether to keep reading.

**Bad — buries the point:**

> The migration system was originally designed in 2021 to handle schema
> changes across multiple database backends. Over time, we've added support
> for data migrations, reversible operations, and dry-run mode. When running
> migrations in production, it's important to understand the locking behavior
> of your database engine, because some DDL operations acquire exclusive
> locks. To avoid downtime, you should run migrations during low-traffic
> periods.

**Good — leads with the actionable instruction:**

> **Run migrations during low-traffic periods** — some DDL operations acquire
> exclusive locks that block reads. Use `migrate --dry-run` first to see
> which migrations require locks, then schedule accordingly.
>
> *Background:* The migration system handles schema and data changes across
> multiple backends, with support for reversible operations...

**Rule:** Every heading should be informative on its own. A reader scanning
only headings should find what they need without reading body text.

---

## Code Examples as First-Class Content

Standards for code examples in documentation:

- Syntactically correct and runnable as-is
- Uses real-looking values, not `YOUR_VALUE_HERE` or `string`
- Shows the complete happy path in the simplest case
- Shows error handling in the next example
- Includes output where output is meaningful

**Before — reader must fill gaps:**

```python
from mylib import Client

client = Client(YOUR_API_KEY)
result = client.send(data)  # data should be a dict
print(result)
```

**After — complete, real-looking, with output:**

```python
from mylib import Client

client = Client("sk_test_example_key_here")
result = client.send({
    "to": "user@example.com",
    "subject": "Invoice #1042",
    "body": "Your invoice is attached.",
})
print(result.status)    # "delivered"
print(result.message_id)  # "msg_abc123"
```

The second example tells the reader what the API key looks like, what the
input structure is, what method to call, and what the response contains.
The reader can start using the library without reading anything else.
