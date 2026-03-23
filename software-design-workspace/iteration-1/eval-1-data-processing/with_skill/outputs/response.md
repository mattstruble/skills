# Data Processing Module Design Recommendation

## The Core Problem with a Single `DataProcessor` Class

A single `DataProcessor` that reads from S3, validates, transforms, and writes to PostgreSQL violates nearly every principle in the skill document:

- **Focused Interfaces**: Four distinct responsibilities crammed into one class forces every caller (and every test) to deal with all four concerns.
- **Honesty**: A class named `DataProcessor` that secretly manages S3 connections and database transactions is hiding its true scope.
- **Composition**: A monolith cannot be partially reused. Need to validate records from a different source? You can't.
- **Pure Functions**: Business logic (validation, transformation) gets tangled with I/O (S3 reads, DB writes), making the core untestable without live infrastructure.

---

## Recommended Structure: Separate by Responsibility

Split the pipeline into four focused pieces — one per concern — then wire them together at the boundary.

### 1. Pure Core: Validation and Transformation

These functions contain no I/O. They take data in, return data out. They're trivially testable.

```python
# pipeline/validate.py

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ValidationError:
    record: dict
    reason: str

def validate_record(record: dict) -> tuple[dict, ValidationError | None]:
    """Returns (record, None) if valid, or (record, error) if not."""
    if "id" not in record:
        return record, ValidationError(record, "missing required field: id")
    if not isinstance(record.get("timestamp"), str):
        return record, ValidationError(record, "timestamp must be a string")
    return record, None

def validate_records(records: list[dict]) -> tuple[list[dict], list[ValidationError]]:
    valid, errors = [], []
    for record in records:
        r, err = validate_record(record)
        if err:
            errors.append(err)
        else:
            valid.append(r)
    return valid, errors
```

```python
# pipeline/transform.py

def transform_record(record: dict) -> dict:
    """Map raw S3 schema to the PostgreSQL target schema."""
    return {
        "id": record["id"],
        "created_at": record["timestamp"],
        "payload": record.get("data", {}),
    }

def transform_records(records: list[dict]) -> list[dict]:
    return [transform_record(r) for r in records]
```

### 2. I/O Adapters: Thin Wrappers Around Infrastructure

Keep all infrastructure coupling in narrow, swappable modules. Each depends only on an abstraction (via Protocol) so callers aren't locked to a specific library.

```python
# pipeline/sources.py

from typing import Protocol

class RecordSource(Protocol):
    def read_records(self, path: str) -> list[dict]: ...

class S3RecordSource:
    def __init__(self, s3_client):
        self._client = s3_client

    def read_records(self, path: str) -> list[dict]:
        bucket, key = _parse_s3_path(path)
        response = self._client.get_object(Bucket=bucket, Key=key)
        import json
        return json.loads(response["Body"].read())

def _parse_s3_path(path: str) -> tuple[str, str]:
    # s3://bucket/key/path
    without_scheme = path.removeprefix("s3://")
    bucket, _, key = without_scheme.partition("/")
    if not key:
        raise ValueError(f"Invalid S3 path: {path}")
    return bucket, key
```

```python
# pipeline/sinks.py

from typing import Protocol

class RecordSink(Protocol):
    def write_records(self, records: list[dict]) -> int: ...  # returns count written

class PostgresRecordSink:
    def __init__(self, conn):
        self._conn = conn

    def write_records(self, records: list[dict]) -> int:
        if not records:
            return 0
        with self._conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO records (id, created_at, payload) VALUES (%(id)s, %(created_at)s, %(payload)s)",
                records,
            )
        self._conn.commit()
        return len(records)
```

### 3. Pipeline Orchestration: Wire It Together at the Boundary

The pipeline function is the only place where I/O and pure logic meet. It's thin — it delegates, doesn't implement.

```python
# pipeline/run.py

from dataclasses import dataclass
from pipeline.sources import RecordSource
from pipeline.sinks import RecordSink
from pipeline.validate import validate_records, ValidationError
from pipeline.transform import transform_records

@dataclass(frozen=True)
class PipelineResult:
    written: int
    validation_errors: list[ValidationError]

def run_pipeline(
    path: str,
    source: RecordSource,
    sink: RecordSink,
) -> PipelineResult:
    raw = source.read_records(path)
    valid, errors = validate_records(raw)
    transformed = transform_records(valid)
    written = sink.write_records(transformed)
    return PipelineResult(written=written, validation_errors=errors)
```

### 4. Entry Point: Assemble and Call

Infrastructure wiring lives at the outermost layer, separate from logic.

```python
# main.py

import boto3
import psycopg2
from pipeline.sources import S3RecordSource
from pipeline.sinks import PostgresRecordSink
from pipeline.run import run_pipeline

def main():
    s3 = boto3.client("s3")
    conn = psycopg2.connect(dsn="postgresql://user:pass@host/db")

    source = S3RecordSource(s3)
    sink = PostgresRecordSink(conn)

    result = run_pipeline("s3://my-bucket/records.json", source, sink)

    print(f"Written: {result.written}")
    if result.validation_errors:
        print(f"Validation errors: {len(result.validation_errors)}")
        for err in result.validation_errors:
            print(f"  - {err.reason}: {err.record}")
```

---

## Why This Structure Works

### Testability without infrastructure

The pure core can be tested with zero mocking:

```python
def test_validate_record_missing_id():
    record, err = validate_record({"timestamp": "2024-01-01"})
    assert err is not None
    assert "id" in err.reason

def test_transform_maps_timestamp_to_created_at():
    result = transform_record({"id": "x", "timestamp": "2024-01-01", "data": {}})
    assert result["created_at"] == "2024-01-01"
```

The pipeline can be tested with fakes, not mocks:

```python
class FakeSource:
    def __init__(self, records): self._records = records
    def read_records(self, path): return self._records

class FakeSink:
    def __init__(self): self.written = []
    def write_records(self, records):
        self.written.extend(records)
        return len(records)

def test_pipeline_skips_invalid_records():
    source = FakeSource([{"id": "1", "timestamp": "t"}, {"no_id": True}])
    sink = FakeSink()
    result = run_pipeline("s3://x/y", source, sink)
    assert result.written == 1
    assert len(result.validation_errors) == 1
```

### Each piece earns its place

| Module | Responsibility | Depends on |
|---|---|---|
| `validate.py` | Business rules for record validity | Nothing |
| `transform.py` | Schema mapping | Nothing |
| `sources.py` | S3 I/O | `boto3` (contained) |
| `sinks.py` | PostgreSQL I/O | `psycopg2` (contained) |
| `run.py` | Orchestration | All of the above via protocols |
| `main.py` | Wiring | Concrete implementations |

### Swappability

Need to read from a local file instead of S3? Implement `RecordSource` — the pipeline doesn't change. Need to write to a different database? Implement `RecordSink`. The core logic is untouched.

---

## What to Avoid

**Don't do this:**

```python
class DataProcessor:
    def __init__(self, s3_bucket, db_dsn, schema_version, validate=True,
                 dry_run=False, error_threshold=0.05):
        self.s3 = boto3.client("s3")
        self.conn = psycopg2.connect(db_dsn)
        # ... 6 more fields

    def process(self, path):
        # reads S3, validates, transforms, writes DB — 80 lines
        # impossible to test without live infrastructure
        # impossible to reuse validation alone
        # impossible to swap the sink
```

This class is doing four jobs, has hidden infrastructure dependencies, and cannot be partially reused or tested in isolation.

---

## Summary

The key insight is **separate I/O from logic**. Validation and transformation are pure data functions — they're the heart of the problem and should have no dependencies. The S3 reader and PostgreSQL writer are thin I/O wrappers that hide infrastructure details behind protocols. The pipeline function wires them together at the boundary. This gives you a module where the most important code (the business rules) is also the easiest to test and understand.
