import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_lessons.py"


def entry(n=1, cue="c", lesson="l", evidence="pass 0.8 vs 0.6", head=None):
    head = head or f"## 2025-01-0{n % 9 + 1} skill iteration-{n}"
    out = [head]
    for k, v in (("cue", cue), ("lesson", lesson), ("evidence", evidence)):
        if v is not None:
            out.append(f"- {k}: {v}")
    return "\n".join(out) + "\n"


def run(tmp_path, text=None):
    if text is not None:
        d = tmp_path / "evals" / "lessons"
        d.mkdir(parents=True)
        (d / "process.md").write_text(text)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True, text=True,
    )


def test_missing_dir_passes(tmp_path):
    assert run(tmp_path).returncode == 0


def test_empty_dir_passes(tmp_path):
    (tmp_path / "evals" / "lessons").mkdir(parents=True)
    assert run(tmp_path).returncode == 0


def test_valid_and_keep_base_pass(tmp_path):
    t = entry(1) + "\n" + entry(2, head="## 2025-01-02 skill iteration-2: KEEP_BASE")
    assert run(tmp_path, t).returncode == 0


def test_missing_field_rejected(tmp_path):
    r = run(tmp_path, entry(lesson=None))
    assert r.returncode == 1
    assert "process.md:1:" in r.stderr and "lesson" in r.stderr


def test_evidence_without_number_rejected(tmp_path):
    r = run(tmp_path, entry(evidence="it got better"))
    assert r.returncode == 1 and "number" in r.stderr


def test_bad_heading_rejected(tmp_path):
    assert run(tmp_path, entry(head="## skill iteration-1")).returncode == 1


def test_21_entries_rejected(tmp_path):
    r = run(tmp_path, "\n".join(entry(i) for i in range(21)))
    assert r.returncode == 1 and "21" in r.stderr


def test_20_entries_pass(tmp_path):
    assert run(tmp_path, "\n".join(entry(i) for i in range(20))).returncode == 0


def test_check_root_env_used_when_no_root_flag(tmp_path):
    d = tmp_path / "evals" / "lessons"
    d.mkdir(parents=True)
    (d / "process.md").write_text("## bad heading\n")
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True,
        env={**os.environ, "CHECK_ROOT": str(tmp_path)},
    )
    assert r.returncode == 1
