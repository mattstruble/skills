import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_routing.py"
G = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def sh(cwd, *args):
    subprocess.run([*G, *args], cwd=cwd, check=True, capture_output=True)


def skill(root, name, route="foo", extra=""):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    meta = f"metadata:\n  route-prompt: {route}\n" if route else ""
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: d\n{meta}{extra}---\nbody\n")


def evals(root, name, cases):
    d = root / "evals" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "trigger_evals.json").write_text(json.dumps(cases))


def run(root, *args, env=None):
    e = {k: v for k, v in os.environ.items() if k not in ("ALL", "CHECK_ROOT", "CHECK_BASE")}
    e.update(env or {})
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=e, cwd=str(root.parent)
    )


def make_repo(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    sh(root, "init", "-b", "main")
    skill(root, "alpha")
    skill(root, "beta")
    evals(root, "alpha", [{"query": "use foo", "should_trigger": True}])
    evals(root, "beta", [{"query": "use foo", "should_trigger": True}])
    sh(root, "add", ".")
    sh(root, "commit", "-m", "base")
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(root), str(bare)], check=True, capture_output=True)
    sh(root, "remote", "add", "origin", str(bare))
    sh(root, "fetch", "origin")
    return root


def test_clean_repo_passes(tmp_path):
    r = run(make_repo(tmp_path), "--root", str(tmp_path / "work"))
    assert r.returncode == 0, r.stderr


def test_changed_linted_unchanged_not(tmp_path):
    root = make_repo(tmp_path)
    skill(root, "alpha", route="")  # missing route-prompt
    (root / "beta" / "SKILL.md").write_text("---\nname: beta\n---\n")  # also broken
    sh(root, "checkout", "--", "beta")  # revert: beta unchanged
    skill(root, "alpha", route="")
    r = run(root, "--root", str(root))
    assert r.returncode == 1
    assert "alpha: " in r.stderr and "beta: " not in r.stderr


def test_route_added_without_trigger_evals_fails(tmp_path):
    root = make_repo(tmp_path)
    skill(root, "gamma")
    r = run(root, "--root", str(root))
    assert r.returncode == 1
    assert "gamma: " in r.stderr and "trigger_evals.json" in r.stderr
    evals(root, "gamma", [{"query": "foo", "should_trigger": True}])
    assert run(root, "--root", str(root)).returncode == 0


def test_route_value_change_requires_evals(tmp_path):
    root = make_repo(tmp_path)
    (root / "evals" / "alpha" / "trigger_evals.json").unlink()
    sh(root, "add", "-A")
    sh(root, "commit", "-m", "rm evals")
    sh(root, "push", "origin", "main")
    skill(root, "alpha", route="foo bar")
    r = run(root, "--root", str(root))
    assert r.returncode == 1 and "alpha: " in r.stderr


def test_invalid_route_reported(tmp_path):
    root = make_repo(tmp_path)
    skill(root, "alpha", route="'*'")
    r = run(root, "--root", str(root))
    assert r.returncode == 1 and "alpha: metadata.route-prompt" in r.stderr


def test_disable_model_invocation_exempts_route_prompt(tmp_path):
    root = make_repo(tmp_path)
    skill(root, "delta", route="", extra="disable-model-invocation: true\n")
    assert run(root, "--root", str(root)).returncode == 0


def test_all_flag_and_env(tmp_path):
    root = make_repo(tmp_path)
    (root / "beta" / "SKILL.md").write_text("---\nname: beta\ndescription: d\n---\n")
    sh(root, "add", "-A")
    sh(root, "commit", "-m", "break beta")
    sh(root, "push", "origin", "main")  # base now includes the break; changed set empty
    assert run(root, "--root", str(root)).returncode == 0
    r = run(root, "--root", str(root), "--all")
    assert r.returncode == 1 and "beta: " in r.stderr
    r = run(root, env={"CHECK_ROOT": str(root), "ALL": "1"})
    assert r.returncode == 1 and "beta: " in r.stderr


def test_missing_origin_falls_back_to_all(tmp_path):
    root = tmp_path / "solo"
    root.mkdir()
    sh(root, "init", "-b", "main")
    skill(root, "alpha", route="")
    sh(root, "add", ".")
    sh(root, "commit", "-m", "x")
    r = run(root, "--root", str(root))
    assert "warning" in r.stderr and "alpha: " in r.stderr and r.returncode == 1


def test_not_a_git_repo_warns(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    skill(root, "alpha")
    evals(root, "alpha", [{"query": "foo", "should_trigger": True}])
    r = run(root, "--root", str(root))
    assert r.returncode == 0 and "warning" in r.stderr


def test_runner_false_positive_and_false_negative(tmp_path):
    root = make_repo(tmp_path)
    evals(root, "alpha", [
        {"query": "nothing here", "should_trigger": True},
        {"query": "has foo inside", "should_trigger": False},
    ])
    r = run(root, "--root", str(root))
    assert r.returncode == 1
    assert "did not trigger" in r.stderr and "triggered unexpectedly" in r.stderr


def test_runner_name_rule(tmp_path):
    root = make_repo(tmp_path)
    skill(root, "my-skill")
    evals(root, "my-skill", [
        {"query": "please use my skill", "should_trigger": True},
        {"query": "my-skills plural", "should_trigger": False},
    ])
    assert run(root, "--root", str(root)).returncode == 0


def test_runner_skips_skill_without_route_prompt_and_runs_unchanged(tmp_path):
    root = make_repo(tmp_path)
    skill(root, "plain", route="")
    evals(root, "plain", [{"query": "zzz", "should_trigger": True}])
    sh(root, "add", "-A")
    sh(root, "commit", "-m", "plain")
    sh(root, "push", "origin", "main")
    assert run(root, "--root", str(root)).returncode == 0
    evals(root, "alpha", [{"query": "nope", "should_trigger": True}])  # unchanged skill still run
    assert run(root, "--root", str(root)).returncode == 1


def test_lessons_not_a_skill(tmp_path):
    root = make_repo(tmp_path)
    skill(root, "lessons", route="")
    r = run(root, "--root", str(root), "--all")
    assert r.returncode == 0, r.stderr


def test_invalid_base_errors(tmp_path):
    root = make_repo(tmp_path)
    r = run(root, "--root", str(root), "--base", "no-such-ref")
    assert r.returncode == 1 and "error" in r.stderr
    r = run(root, "--root", str(root), env={"CHECK_BASE": "no-such-ref"})
    assert r.returncode == 1
