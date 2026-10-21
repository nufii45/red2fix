import json
import os
import subprocess
import sys

import pytest
from streamlit.testing.v1 import AppTest

import config
from dashboard import data, launch

ULTRA, NANO = config.MODELS["ultra"], config.MODELS["nano"]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def ledger(*rows):
    return "".join(json.dumps({"ts": 1.0, "in_tokens": 1, "out_tokens": 1, "latency_ms": 1, **r}) + "\n" for r in rows)


@pytest.fixture
def root(tmp_path):
    """A repo root with one demo run and a bench run holding one failure and one live run."""
    out = tmp_path / "out"
    write(out / "1" / "result.json", json.dumps({"status": "succeeded", "phase": "DONE", "iterations": 1, "cost_usd": 0.05, "seconds": 40}))
    write(out / "1" / "ledger.jsonl", ledger({"phase": "triage", "model": NANO, "cost_usd": 0.01}, {"phase": "localize", "model": ULTRA, "cost_usd": 0.04}))
    write(out / "1" / "summary.md", "## Fixes #1: div\n")
    write(out / "1" / "patch.diff", "+fix\n")
    bench = out / "bench" / "pilot"
    write(bench / "a__b-1" / "result.json", json.dumps({"status": "aborted", "abort_reason": "out_of_scope: UI bug", "cost_usd": 0.01, "seconds": 5}))
    write(bench / "a__b-1" / "issue.md", "the issue")
    write(bench / "c__d-2" / "events.jsonl", '{"t": 1.0, "ev": "phase", "name": "TRIAGE"}\n{"t": 2.0, "ev": "phase", "name": "FI')
    write(bench / "c__d-2" / "ledger.jsonl", ledger({"phase": "triage", "model": NANO, "cost_usd": 0.02}) + '{"half')
    write(out / "bench" / "pilot" / "preds.jsonl", "")  # not a run folder
    write(tmp_path / "demo" / "issues" / "1.md", "# div crashes\n")
    write(tmp_path / "scripts" / "run_local.sh", "#!/bin/sh\nsleep 1\n")
    (tmp_path / "scripts" / "run_local.sh").chmod(0o755)
    return tmp_path


def test_find_and_load_runs(root):
    found = data.find_runs(root / "out")
    assert [(g, d.name) for g, d in found] == [("demo", "1"), ("pilot", "a__b-1"), ("pilot", "c__d-2")]

    live = data.load_run(root / "out" / "bench" / "pilot" / "c__d-2")
    # Half-written last lines are skipped, and a run without result.json is live.
    assert live["result"] == {"status": "running", "phase": "TRIAGE", "cost_usd": 0.02}


def test_summarize_and_costs(root):
    runs = [data.load_run(d) for _, d in data.find_runs(root / "out")]
    s = data.summarize(runs)
    assert (s["attempted"], s["running"], s["won"]) == (2, 1, 1)
    assert s["failures"] == {"out of scope": 1}
    assert data.cost_by(runs[:1], "model") == {"1": {"nano": 0.01, "ultra": 0.04}}
    assert data.total_spend(root / "out") == pytest.approx(0.07)


def test_official_scores(root):
    assert data.official("pilot", root) is None
    write(root / "red2fix.pilot.json", json.dumps({"resolved_ids": ["a__b-1"]}))
    assert data.official("pilot", root) == {"a__b-1"}


def test_launcher_runs_one_at_a_time(root):
    with pytest.raises(ValueError):
        launch.start(7, root)
    pid = launch.start(1, root)
    assert launch.running_pid(root / "out" / ".launch.lock") == pid
    assert data.load_run(root / "out" / "1")["result"]["phase"] == "QUEUED"
    with pytest.raises(RuntimeError):
        launch.start(1, root)
    os.waitpid(pid, 0)
    assert launch.running_pid(root / "out" / ".launch.lock") is None


def test_running_pid_of_a_dead_stranger(tmp_path):
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    (tmp_path / "lock").write_text(str(p.pid))
    assert launch.running_pid(tmp_path / "lock") is None


@pytest.mark.parametrize("group,red_green,shown", [
    ("demo", "1/1", "detail · 1<"),
    ("pilot", "0/1", '<span class="name">c__d-2</span>'),
])
def test_app_renders(root, monkeypatch, group, red_green, shown):
    monkeypatch.setattr(data, "ROOT", root)
    monkeypatch.setenv("RED2FIX_ENABLE_LAUNCH", "1")
    at = AppTest.from_file("../dashboard/app.py", default_timeout=30).run()
    at.sidebar.selectbox[1].set_value(group).run()
    assert not at.exception, at.exception
    page = "".join(m.value for m in at.markdown)
    assert f'<div class="v">{red_green}</div>' in page
    assert shown in page
