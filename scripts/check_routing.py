"""Lint skill routing metadata and run trigger evals. Stdlib only."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import routing  # noqa: E402

ROUTE_KEYS = ("route-prompt", "route-paths", "route-commands")
NON_SKILLS = {"lessons"}


def git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )


def find_skills(root):
    out = []
    for d in sorted(Path(root).iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name in NON_SKILLS:
            continue
        if d.name.endswith("-workspace") or d.name.endswith("-eval"):
            continue
        if (d / "SKILL.md").is_file():
            out.append(d.name)
    return out


def resolve_base(root, base):
    """Return (base_ref or None, warning or None)."""
    if base:
        return base, None
    if git(root, "rev-parse", "--git-dir").returncode != 0:
        return None, "not a git repository; linting all skills"
    r = git(root, "merge-base", "HEAD", "origin/main")
    if r.returncode != 0 or not r.stdout.strip():
        return None, "origin/main not found; linting all skills"
    return r.stdout.strip(), None


def changed_files(root, base):
    files = set()
    for args in (
        ("diff", "--relative", "--name-only", base),
        ("diff", "--relative", "--name-only", "--cached"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        r = git(root, *args)
        if r.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
        files.update(l for l in r.stdout.splitlines() if l)
    return files


def lint_skill(root, skill, base, errors):
    def err(msg):
        errors.append(f"{skill}: {msg}")

    text = (Path(root) / skill / "SKILL.md").read_text()
    fm = routing.parse_frontmatter(text)
    for e in fm.get("errors", []):
        err(f"frontmatter: {e}")
    meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
    if "route-prompt" not in meta and fm.get("disable-model-invocation") is not True:
        err("metadata.route-prompt is required unless disable-model-invocation is true")
    for key, comp in (
        ("route-prompt", routing.compile_keywords),
        ("route-commands", routing.compile_commands),
        ("route-paths", routing.compile_globs),
    ):
        if key in meta:
            try:
                comp(meta[key])
            except ValueError as e:
                err(f"metadata.{key}: {e}")

    has_route = any(k in meta for k in ROUTE_KEYS)
    need = False
    if base is None:
        need = has_route
    else:
        r = git(root, "show", f"{base}:./{skill}/SKILL.md")
        old = {}
        if r.returncode == 0:
            ofm = routing.parse_frontmatter(r.stdout)
            old = ofm.get("metadata") if isinstance(ofm.get("metadata"), dict) else {}
        need = any(k in meta and meta[k] != old.get(k) for k in ROUTE_KEYS)
    if need and not (Path(root) / "evals" / skill / "trigger_evals.json").is_file():
        err("route-* added or changed but evals/%s/trigger_evals.json is missing" % skill)


def name_matcher(skill):
    body = re.escape(skill).replace(r"\-", "[- ]")
    return re.compile(r"(?<![\w-])" + body + r"(?![\w-])", re.IGNORECASE)


def run_trigger_evals(root, skills, errors):
    for skill in skills:
        path = Path(root) / "evals" / skill / "trigger_evals.json"
        if not path.is_file():
            continue
        fm = routing.parse_frontmatter((Path(root) / skill / "SKILL.md").read_text())
        meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
        if "route-prompt" not in meta:
            continue
        try:
            matcher = routing.compile_keywords(meta["route-prompt"])
            cases = json.loads(path.read_text())
        except (ValueError, json.JSONDecodeError) as e:
            errors.append(f"{skill}: trigger eval setup failed: {e}")
            continue
        nm = name_matcher(skill)
        for c in cases:
            q = c.get("query", "")
            trig = routing.match_prompt(matcher, q[:2000]) or nm.search(q[:2000]) is not None
            want = bool(c.get("should_trigger"))
            if trig != want:
                verb = "did not trigger" if want else "triggered unexpectedly"
                errors.append(f"{skill}: trigger eval {verb}: {q[:80]!r}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--base")
    a = ap.parse_args(argv)
    root = a.root or os.environ.get("CHECK_ROOT") or str(Path(__file__).resolve().parent.parent)
    base_arg = a.base or os.environ.get("CHECK_BASE") or None
    lint_all = a.all or os.environ.get("ALL") == "1"

    skills = find_skills(root)
    base, warn = resolve_base(root, base_arg)
    if warn:
        print(f"warning: {warn}", file=sys.stderr)
        lint_all = True
    targets = skills
    if not lint_all:
        try:
            changed = changed_files(root, base)
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        targets = [s for s in skills if f"{s}/SKILL.md" in changed]

    errors = []
    for s in targets:
        lint_skill(root, s, base, errors)
    run_trigger_evals(root, skills, errors)
    for e in errors:
        print(e, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
