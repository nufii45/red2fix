import json
from types import SimpleNamespace

from bench import run

INST = {"instance_id": "o__r-1", "problem_statement": "p", "image": "img", "test_files": ["t.py"]}


def test_crashed_run_still_leaves_a_result(tmp_path, monkeypatch):
    out = tmp_path / INST["instance_id"]
    out.mkdir()
    (out / "result.json").write_text('{"status": "succeeded"}')  # stale, from an earlier run
    monkeypatch.setattr(run.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))

    _, r = run.run_one(INST, tmp_path, 60)

    assert r["abort_reason"].startswith("error: no result.json")
    assert json.loads((out / "result.json").read_text()) == r
