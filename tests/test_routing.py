import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import routing  # noqa: E402

VECTORS = json.loads((ROOT / "skill-creator/references/routing-vectors.json").read_text())


@pytest.mark.parametrize("v", VECTORS["frontmatter"], ids=lambda v: v["text"][:40])
def test_frontmatter(v):
    got = routing.parse_frontmatter(v["text"])
    if not v["expect"]:
        assert got == {}
    for k, val in v["expect"].items():
        assert got[k] == val


@pytest.mark.parametrize("v", VECTORS["keywords"], ids=lambda v: f"{v['spec']!r}-{v.get('text')}")
def test_keywords(v):
    if v.get("invalid"):
        with pytest.raises(ValueError):
            routing.compile_keywords(v["spec"])
        return
    m = routing.compile_keywords(v["spec"])
    assert routing.match_prompt(m, v["text"]) is v["match"]


@pytest.mark.parametrize("v", VECTORS["commands"], ids=lambda v: f"{v['spec']}-{v['command']}")
def test_commands(v):
    m = routing.compile_commands(v["spec"])
    assert routing.match_command(m, v["command"]) is v["match"]


@pytest.mark.parametrize("v", VECTORS["git_commit"], ids=lambda v: v["command"][:50])
def test_git_commit(v):
    assert routing.is_real_git_commit(v["command"]) is v["match"]


@pytest.mark.parametrize("v", VECTORS["globs"], ids=lambda v: f"{v['spec']}-{v['path']}")
def test_globs(v):
    m = routing.compile_globs(v["spec"])
    assert routing.match_path(m, v["path"], v.get("root")) is v["match"]


def test_empty_globs_invalid():
    with pytest.raises(ValueError):
        routing.compile_globs("  ")


def test_stdlib_only():
    tree = ast.parse((ROOT / "scripts/routing.py").read_text())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert mods <= set(sys.stdlib_module_names)
