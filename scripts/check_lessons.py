"""Validate evals/lessons/*.md entries. Stdlib only."""

import argparse
import os
import re
import sys
from pathlib import Path

HEADING_RE = re.compile(r"^## \d{4}-\d{2}-\d{2} \S+ iteration-\d+(: KEEP_BASE)?$")
FIELDS = ("cue", "lesson", "evidence")
MAX_ENTRIES = 20


def check_file(path, rel):
    errors = []
    entries = []  # (line, {field: text})
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("## "):
            if not HEADING_RE.match(line.rstrip()):
                errors.append(
                    f"{rel}:{n}: heading must match "
                    "'## YYYY-MM-DD <skill> iteration-<n>[: KEEP_BASE]'"
                )
            entries.append((n, {}))
            continue
        m = re.match(r"^- (cue|lesson|evidence):(.*)$", line)
        if m and entries:
            entries[-1][1].setdefault(m.group(1), m.group(2).strip())
    for n, fields in entries:
        for f in FIELDS:
            if not fields.get(f):
                errors.append(f"{rel}:{n}: missing or empty '{f}' bullet")
        if fields.get("evidence") and not re.search(r"\d", fields["evidence"]):
            errors.append(f"{rel}:{n}: evidence must contain a number")
    if len(entries) > MAX_ENTRIES:
        errors.append(f"{rel}:1: {len(entries)} entries exceeds maximum {MAX_ENTRIES}")
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=os.environ.get("CHECK_ROOT") or str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args(argv)
    d = Path(args.root) / "evals" / "lessons"
    errors = []
    if d.is_dir():
        for f in sorted(d.glob("*.md")):
            errors += check_file(f, f"evals/lessons/{f.name}")
    for e in errors:
        print(e, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
