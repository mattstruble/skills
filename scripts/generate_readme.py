#!/usr/bin/env python3
"""Generate root README.md and evals/README.md from skill SKILL.md frontmatter and benchmark data."""

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent


def parse_frontmatter(skill_md: Path) -> dict[str, str] | None:
    """Extract name, description, summary, and type from YAML frontmatter delimited by ---."""
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
        if key in ("name", "description", "summary", "type"):
            result[key] = val
    return result if "name" in result and "description" in result else None


def load_skills() -> list[dict]:
    """Return sorted list of skill frontmatter dicts for every dir with a SKILL.md."""
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


_SECTION_META = {
    "process": (
        "Process Skills",
        "Skills that enforce a specific way of working — a multi-step procedure or discipline the model follows once the skill loads.",
    ),
    "design": (
        "Design Skills",
        "Skills that supply frameworks and judgment for architectural or creative decisions.",
    ),
    "reference": (
        "Reference Skills",
        "Skills that provide domain facts and syntax the model already knows; they exist for consistent routing and conventions.",
    ),
    # Legacy alias: treat behavioral as process until frontmatter is relabeled
    "behavioral": (
        "Process Skills",
        "Skills that enforce a specific way of working — a multi-step procedure or discipline the model follows once the skill loads.",
    ),
}

_SECTION_ORDER = ["process", "design", "reference"]


def _unified_table_row(skill: dict, benchmarks: dict[str, dict]) -> str:
    name = skill["name"]
    summary = (skill.get("summary") or name).replace("|", "\\|")
    bm = benchmarks.get(name)
    if bm and "run_summary" in bm:
        try:
            rs = bm["run_summary"]
            with_mean = rs["with_skill"]["pass_rate"]["mean"]
            base_mean = rs["without_skill"]["pass_rate"]["mean"]
            delta_val = with_mean - base_mean
            sign = "+" if delta_val >= 0 else ""
            date = bm["metadata"]["timestamp"]
            return (
                f"| {name} | {summary} | {fmt_pct(with_mean)} | {fmt_pct(base_mean)}"
                f" | {sign}{round(delta_val * 100)}% | {date} |"
            )
        except KeyError:
            pass
    return f"| {name} | {summary} | — | — | — | — |"


def generate_root_readme(skills: list[dict], benchmarks: dict[str, dict]) -> str:
    # Bucket skills by canonical section key; behavioral maps to "process"
    _alias = {"behavioral": "process"}
    sections: dict[str, list[dict]] = {k: [] for k in _SECTION_ORDER}
    other: list[dict] = []
    for s in skills:
        raw_type = s.get("type", "")
        key = _alias.get(raw_type, raw_type)
        if key in sections:
            sections[key].append(s)
        else:
            other.append(s)

    table_header = [
        "| Skill | Summary | With Skill | Baseline | Δ | Last Run |",
        "|-------|---------|-----------|----------|---|----------|",
    ]

    lines = [
        "# mattstruble-skills",
        "",
        "Claude/OpenCode skills with eval-driven development.",
        "",
        "## Skills",
        "",
    ]

    for key in _SECTION_ORDER:
        section_skills = sections[key]
        if not section_skills:
            continue
        heading, description = _SECTION_META[key]
        lines += [f"### {heading}", "", description, ""]
        lines.extend(table_header)
        for s in section_skills:
            lines.append(_unified_table_row(s, benchmarks))
        lines.append("")

    if other:
        lines += [
            "### Other Skills",
            "",
            "Skills not yet assigned to a section.",
            "",
        ]
        lines.extend(table_header)
        for s in other:
            lines.append(_unified_table_row(s, benchmarks))
        lines.append("")

    lines += [
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

        # Group runs by eval_name, collecting with_skill and without_skill results
        eval_order: list[str] = []
        eval_runs: dict[str, dict] = {}
        for run in runs:
            try:
                eval_name = run["eval_name"]
                config = run["configuration"]
                r = run["result"]
            except KeyError:
                continue
            if eval_name not in eval_runs:
                eval_order.append(eval_name)
                eval_runs[eval_name] = {}
            eval_runs[eval_name][config] = r

        lines += [
            f"## {skill_name}",
            "",
            "| Eval | Baseline | With Skill | Δ |",
            "|------|----------|-----------|---|",
        ]

        total_base_passed = total_base_total = 0
        total_with_passed = total_with_total = 0

        for eval_name in eval_order:
            configs = eval_runs[eval_name]
            base = configs.get("without_skill", {})
            with_s = configs.get("with_skill", {})

            base_passed = base.get("passed", 0)
            base_total = base.get("total", 0)
            with_passed = with_s.get("passed", 0)
            with_total = with_s.get("total", 0)

            delta = with_passed - base_passed
            delta_str = f"+{delta}" if delta >= 0 else str(delta)

            lines.append(
                f"| {eval_name} | {base_passed}/{base_total} | {with_passed}/{with_total} | {delta_str} |"
            )

            total_base_passed += base_passed
            total_base_total += base_total
            total_with_passed += with_passed
            total_with_total += with_total

        # Bold total row
        total_delta_pct = (
            round(
                (
                    total_with_passed / total_with_total
                    - total_base_passed / total_base_total
                )
                * 100
            )
            if total_with_total and total_base_total
            else 0
        )
        total_delta_str = (
            f"+{total_delta_pct}%" if total_delta_pct >= 0 else f"{total_delta_pct}%"
        )
        base_pct = (
            round(total_base_passed / total_base_total * 100) if total_base_total else 0
        )
        with_pct = (
            round(total_with_passed / total_with_total * 100) if total_with_total else 0
        )
        lines.append(
            f"| **Total** | **{total_base_passed}/{total_base_total} ({base_pct}%)** "
            f"| **{total_with_passed}/{total_with_total} ({with_pct}%)** | **{total_delta_str}** |"
        )
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
