#!/usr/bin/env python3
"""Generate root README.md and evals/README.md from skill SKILL.md frontmatter and benchmark data."""

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent


def parse_frontmatter(skill_md: Path) -> dict[str, str] | None:
    """Extract name and description from YAML frontmatter delimited by ---."""
    text = skill_md.read_text(encoding="utf-8")
    parts = text.split("---")
    if len(parts) < 3:
        return None
    block = parts[1]
    result = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"')
        if key in ("name", "description"):
            result[key] = val
    return result if "name" in result and "description" in result else None


def load_skills() -> list[dict]:
    """Return sorted list of {name, description} for every dir with a SKILL.md."""
    skills = []
    for entry in sorted(REPO_ROOT.iterdir()):
        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.exists():
            continue
        fm = parse_frontmatter(skill_md)
        if fm:
            skills.append(fm)
    return sorted(skills, key=lambda s: s["name"])


def load_benchmarks() -> dict[str, dict]:
    """Return {skill_name: benchmark_data} for skills with a benchmark.json that has run_summary."""
    benchmarks = {}
    evals_dir = REPO_ROOT / "evals"
    if not evals_dir.exists():
        return benchmarks
    for entry in sorted(evals_dir.iterdir()):
        bm_path = entry / "benchmarks" / "benchmark.json"
        if not bm_path.exists():
            continue
        try:
            data = json.loads(bm_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"warning: skipping {bm_path}: {e}", file=sys.stderr)
            continue
        if "run_summary" in data:
            benchmarks[entry.name] = data
    return benchmarks


def fmt_pct(val: float) -> str:
    return f"{round(val * 100)}%"


def generate_root_readme(skills: list[dict], benchmarks: dict[str, dict]) -> str:
    lines = [
        "# mattstruble-skills",
        "",
        "Claude/OpenCode skills with eval-driven development.",
        "",
        "## Skills",
        "",
        "| Skill | Description |",
        "|-------|-------------|",
    ]
    for s in skills:
        desc = s["description"].replace("|", "\\|")
        lines.append(f"| {s['name']} | {desc} |")

    lines += [
        "",
        "## Eval Scoreboard",
        "",
        "| Skill | With Skill | Baseline | Delta | Last Run |",
        "|-------|-----------|----------|-------|----------|",
    ]
    for s in skills:
        bm = benchmarks.get(s["name"])
        if not bm:
            continue
        try:
            rs = bm["run_summary"]
            with_pct = fmt_pct(rs["with_skill"]["pass_rate"]["mean"])
            base_pct = fmt_pct(rs["without_skill"]["pass_rate"]["mean"])
            delta_raw = rs["delta"]["pass_rate"]
            # Convert decimal string/number like "+0.33" or 0.33 to "+33%"
            try:
                delta_val = float(delta_raw)
                sign = "+" if delta_val >= 0 else ""
                delta = f"{sign}{round(delta_val * 100)}%"
            except (ValueError, TypeError, AttributeError):
                delta = str(delta_raw)
            date = bm["metadata"]["timestamp"]
        except KeyError:
            continue
        lines.append(f"| {s['name']} | {with_pct} | {base_pct} | {delta} | {date} |")

    lines += [
        "",
        "[Detailed per-eval results →](evals/README.md)",
        "",
        "## Structure",
        "",
        "```",
        "<skill>/SKILL.md       — skill definition + references",
        "evals/<skill>/         — eval definitions + benchmarks",
        "scripts/               — tooling (generate_readme.py)",
        "```",
        "",
    ]
    return "\n".join(lines)


def generate_evals_readme(skills: list[dict], benchmarks: dict[str, dict]) -> str:
    skill_names = {s["name"] for s in skills}
    lines = ["# Eval Results (Detailed)", ""]

    for skill_name in sorted(benchmarks.keys()):
        if skill_name not in skill_names:
            continue
        bm = benchmarks[skill_name]
        runs = bm.get("runs", [])
        if not runs:
            continue
        lines += [
            f"## {skill_name}",
            "",
            "| Eval | Config | Pass Rate | Passed | Failed | Total |",
            "|------|--------|-----------|--------|--------|-------|",
        ]
        for run in runs:
            try:
                eval_name = run["eval_name"]
                config = run["configuration"]
                r = run["result"]
                pass_rate = fmt_pct(r["pass_rate"])
                lines.append(
                    f"| {eval_name} | {config} | {pass_rate} | {r['passed']} | {r['failed']} | {r['total']} |"
                )
            except KeyError:
                continue
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    skills = load_skills()
    benchmarks = load_benchmarks()

    root_readme = REPO_ROOT / "README.md"
    root_readme.write_text(generate_root_readme(skills, benchmarks), encoding="utf-8")

    evals_dir = REPO_ROOT / "evals"
    evals_dir.mkdir(exist_ok=True)
    evals_readme = evals_dir / "README.md"
    evals_readme.write_text(generate_evals_readme(skills, benchmarks), encoding="utf-8")

    print(f"Generated README.md ({len(skills)} skills, {len(benchmarks)} benchmarks)")
    print(f"Generated evals/README.md")


if __name__ == "__main__":
    main()
