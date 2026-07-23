#!/usr/bin/env python3
"""Extract sanitized prompts from evals/<skill>/evals.json, stripping all grading data."""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <skill-name> <output-path>", file=sys.stderr)
        sys.exit(1)

    skill, output_path = sys.argv[1], Path(sys.argv[2])
    evals_file = REPO_ROOT / "evals" / skill / "evals.json"

    if not evals_file.exists():
        print(f"Error: {evals_file} not found", file=sys.stderr)
        sys.exit(1)

    data = json.loads(evals_file.read_text(encoding="utf-8"))
    evals = data.get("evals", data) if isinstance(data, dict) else data

    prompts = [
        {"id": e["id"], "prompt": e["prompt"]}
        for e in evals
        if e.get("should_trigger", True) is not False
    ]

    if not prompts:
        print(f"Error: no qualifying evals in {evals_file}", file=sys.stderr)
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(prompts, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
