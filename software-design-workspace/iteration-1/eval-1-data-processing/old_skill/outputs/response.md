# Data Processing Module Design Recommendation

## The Problem with a Single DataProcessor Class

A monolithic `DataProcessor` class that reads from S3, validates, transforms, and writes to PostgreSQL violates several core design principles:

1. **Focused Interfaces** — Different callers need different subsets. A test that validates schema logic shouldn't need S3 credentials. A retry wrapper around DB writes shouldn't know about S3.
2. **Pure Functions** — Bundling IO with transformation logic makes the transformation untestable without live infrastructure.
3. **Honesty** — A class called `DataProcessor` that secretly owns database connections, S3 clients, and validation rules hides its true complexity.
4. **Composition** — When requirements change (swap S3 for GCS, swap Postgres for Redshift), a monolith forces you to rewrite rather than swap a piece.

## Recommended Structure: Four Focused Layers

Split the pipeline into four independent, composable units:

```
S3Reader → validate() → transform() → DBWriter
```

Each piece does one thing, depends only on what it needs, and can be tested in isolation.

---

### 1. Reader — S3 Record Fetching

```python
from dataclasses import dataclass
from typing import Iterator
import boto3

@dataclass(frozen=True)
class S3Location:
    bucket: str
    key: str

def read_records(location: S3Location, client=None) -> Iterator[dict]:
    """Yield raw records from an S3 object (JSONL assumed)."""
    s3 = client or boto3.client("s3")
    response = s3.get_object(Bucket=location.bucket, Key=location.key)
    for line in response["Body"].iter_lines():
        yield json.loads(line)
```

- Takes only what it needs: a location and an optional client (for testing).
- Returns an iterator — lazy, composable, memory-efficient.
- No knowledge of validation or transformation.

---

### 2. Validation — Pure Function

```python
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ValidationError:
    field: str
    reason: str

def validate_record(record: dict) -> list[ValidationError]:
    """Return a list of validation errors, empty if valid."""
    errors = []
    if "id" not in record:
        errors.append(ValidationError("id", "required field missing"))
    if not isinstance(record.get("timestamp"), str):
        errors.append(ValidationError("timestamp", "must be a string"))
    # ... additional rules
    return errors
```

- Pure function: takes a dict, returns errors. No IO, no state.
- Testable with a single `assert validate_record({...}) == []`.
- Returns explicit errors rather than raising or returning `None`.

---

### 3. Transformation — Pure Function

```python
from datetime import datetime

def transform_record(record: dict) -> dict:
    """Map raw record schema to the target DB schema."""
    return {
        "record_id": record["id"],
        "created_at": datetime.fromisoformat(record["timestamp"]),
        "payload": record.get("data", {}),
    }
```

- Pure: input dict in, output dict out.
- No coupling to S3 or PostgreSQL schemas in the same function.
- Easy to unit-test with literal values.

---

### 4. Writer — DB Persistence

```python
from contextlib import contextmanager
import psycopg2

@contextmanager
def db_connection(dsn: str):
    conn = psycopg2.connect(dsn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def write_records(records: Iterator[dict], conn) -> int:
    """Insert transformed records; returns count of rows written."""
    cursor = conn.cursor()
    count = 0
    for record in records:
        cursor.execute(
            "INSERT INTO records (record_id, created_at, payload) VALUES (%s, %s, %s)",
            (record["record_id"], record["created_at"], record["payload"]),
        )
        count += 1
    return count
```

- `db_connection` uses a context manager — resource cleanup is explicit and guaranteed.
- `write_records` accepts an injected connection, making it testable with a mock or test DB.
- Returns a count so the caller has an honest signal about what happened.

---

### 5. Pipeline Orchestration — Compose at the Top

```python
import logging
from typing import NamedTuple

logger = logging.getLogger(__name__)

class PipelineResult(NamedTuple):
    records_read: int
    records_skipped: int
    records_written: int

def run_pipeline(location: S3Location, db_dsn: str) -> PipelineResult:
    """Orchestrate the full read → validate → transform → write pipeline."""
    records_read = 0
    records_skipped = 0
    valid_records = []

    for raw in read_records(location):
        records_read += 1
        errors = validate_record(raw)
        if errors:
            logger.warning("Skipping record %s: %s", raw.get("id"), errors)
            records_skipped += 1
            continue
        valid_records.append(transform_record(raw))

    with db_connection(db_dsn) as conn:
        records_written = write_records(iter(valid_records), conn)

    return PipelineResult(records_read, records_skipped, records_written)
```

- The orchestrator is the only place that wires the pieces together.
- Each step is called by name — the flow is readable without running it in your head.
- Returns a typed result — no ambiguous return values, no silent failures.

---

## What You Get from This Structure

| Concern | Before (monolith) | After (composed) |
|---|---|---|
| Test validation logic | Need S3 + DB mocked | `assert validate_record({...})` |
| Test transformation | Need full setup | Pure function, literal inputs |
| Swap S3 for GCS | Rewrite class | Replace `read_records` only |
| Retry failed writes | Complex to isolate | Wrap `write_records` alone |
| Understand the flow | Read the whole class | Read `run_pipeline` |

---

## When to Reach for a Class

A class is appropriate when you need to manage **long-lived state** — e.g., a connection pool that persists across many pipeline runs. In that case, the class should own exactly that state and nothing more:

```python
class RecordWriter:
    """Manages a persistent DB connection pool for high-throughput writes."""
    def __init__(self, dsn: str):
        self._pool = create_connection_pool(dsn)

    def write(self, records: Iterator[dict]) -> int:
        with self._pool.acquire() as conn:
            return write_records(records, conn)
```

The class wraps state management; the logic stays in the standalone function.

---

## Summary

- **Split by concern**: reader, validator, transformer, writer.
- **Keep transformation pure**: no IO in the functions that reshape data.
- **Push side effects to the edges**: IO happens in `read_records` and `write_records`, not in the middle.
- **Compose at the top**: `run_pipeline` wires everything together and is the only function that needs to know about all four pieces.
- **Make failures visible**: return typed results, log skipped records explicitly, use context managers for cleanup.
