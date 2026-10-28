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


REVIEW = {
    "verdict": "proven", "verdict_reason": "red on base, green on head", "claim": "5m means five minutes",
    "spec_source": "issue#1", "proof": {"base": "failed: 1 failed", "head": "passed: 1 passed"},
    "suite": {"new_failures": []}, "restricted_paths_touched": [],
    "findings": [{"rule": "No changes unrelated to the spec", "severity": "warning", "file": "minikit/duration.py",
                  "line": 10, "note": "a <b>note</b>"}],
    "cost_usd": 0.03, "seconds": 23, "calls": {"ultra": 13, "super": 0, "nano": 2},
    "pr_url": "https://github.com/nufii45/red2fix-minikit/pull/4",
}
REPORT = {
    "reviews": 2, "unproven": 1, "errors": 0, "median_usd": 0.3, "median_s": 150, "total_usd": 0.6, "calls": {},
    "settings": {s: {"false_approvals": ["a__b-1"], "failed_total": 1, "gold_approvals": 0, "gold_total": 1}
                 for s in ("blocker", "warning")},
    "instances": {"a__b-1": {"gold": {"verdict": "unproven", "cost_usd": 0.3, "seconds": 100},
                             "failed": {"verdict": "proven", "cost_usd": 0.3, "seconds": 200}}},
}


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
    # A finished demo review (old-style review.json: no quotes, no dropped_findings) and a bench review run.
    review = out / "review-good"
    write(review / "review.json", json.dumps(REVIEW))
    write(review / "result.json", json.dumps({"status": "succeeded", "phase": "DONE", "verdict": "proven", "cost_usd": 0.03, "seconds": 23}))
    write(review / "events.jsonl", '{"t": 1.0, "ev": "phase", "name": "TRIAGE"}\n{"t": 2.0, "ev": "phase", "name": "DONE"}\n')
    write(review / "ledger.jsonl", ledger({"phase": "review", "model": ULTRA, "cost_usd": 0.03}))
    write(review / "repro_test.py", "def test_minutes():\n    assert parse_duration('5m') == 300\n")
    rv = out / "bench" / "rv" / "a__b-1"
    write(rv / "gold" / "review.json", json.dumps({**REVIEW, "verdict": "unproven", "claim": "gold claim"}))
    write(rv / "gold" / "result.json", json.dumps({"status": "succeeded", "verdict": "unproven"}))
    write(rv / "failed" / "review.json", json.dumps({**REVIEW, "verdict": "proven", "claim": "failed claim"}))
    write(rv / "failed" / "result.json", json.dumps({"status": "succeeded", "verdict": "proven"}))
    write(out / "bench" / "rv" / "review_report.json", json.dumps(REPORT))
    write(tmp_path / "demo" / "prs" / "good" / "patch.diff", "+x\n")
    write(tmp_path / "scripts" / "review_local.sh", "#!/bin/sh\nsleep 1\n")
    (tmp_path / "scripts" / "review_local.sh").chmod(0o755)
    return tmp_path


def test_find_and_load_runs(root):
    found = data.find_runs(root / "out")
    assert [(g, data.run_name(d)) for g, d in found] == [
        ("demo", "1"), ("pilot", "a__b-1"), ("pilot", "c__d-2"), ("reviews", "review-good"),
        ("rv", "a__b-1/failed"), ("rv", "a__b-1/gold"),
    ]

    live = data.load_run(root / "out" / "bench" / "pilot" / "c__d-2")
    # Half-written last lines are skipped, and a run without result.json is live.
    assert live["result"] == {"status": "running", "phase": "TRIAGE", "cost_usd": 0.02}


def test_summarize_and_costs(root):
    runs = [data.load_run(d) for g, d in data.find_runs(root / "out") if g in ("demo", "pilot")]  # fix runs only
    s = data.summarize(runs)
    assert (s["attempted"], s["running"], s["won"]) == (2, 1, 1)
    assert s["failures"] == {"out of scope": 1}
    assert data.cost_by(runs[:1], "model") == {"1": {"nano": 0.01, "ultra": 0.04}}
    assert data.total_spend(root / "out") == pytest.approx(0.10)  # fix runs $0.07 + the demo review $0.03


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


def test_load_review_and_live_review_steps(root):
    r = data.load_review(root / "out" / "review-good")
    assert r["review"]["verdict"] == "proven" and r["text"]["repro_test.py"].startswith("def test_minutes")
    assert data.verdict_counts([r])["proven"] == 1
    live = root / "out" / "review-live"
    write(live / "events.jsonl", '{"t": 1.0, "ev": "phase", "name": "HEAD_CHECK"}\n')
    r = data.load_review(live)
    assert r["review"] is None and r["result"] == {"status": "running", "phase": "HEAD_CHECK", "cost_usd": 0}
    assert data.REVIEW_STEPS["HEAD_CHECK"] == "Head" and data.group_of(live, root / "out") == "reviews"
    assert data.bench_report(root / "out" / "bench" / "rv")["reviews"] == 2
    assert data.bench_report(root / "out" / "bench" / "pilot") is None


def test_review_launcher_shares_the_lock(root):
    with pytest.raises(ValueError):
        launch.start_review("nope", root)
    pid = launch.start_review("good", root)
    assert data.load_review(root / "out" / "review-good")["result"]["phase"] == "QUEUED"
    with pytest.raises(RuntimeError):
        launch.start(1, root)  # one run at a time, fix or review
    os.waitpid(pid, 0)


def app(root, monkeypatch, query=None):
    monkeypatch.setattr(data, "ROOT", root)
    monkeypatch.setenv("RED2FIX_ENABLE_LAUNCH", "1")
    at = AppTest.from_file("../dashboard/app.py", default_timeout=30)
    if query:
        at.query_params["run"] = query
    return at.run()


def test_app_renders_a_review_verdict_card(root, monkeypatch):
    at = app(root, monkeypatch, "review-good")
    assert not at.exception, at.exception
    page = "".join(m.value for m in at.markdown)
    assert '<div class="r2f-verdict">✅ Proven</div>' in page
    assert "5m means five minutes" in page and "passed: 1 passed" in page
    assert 'href="https://github.com/nufii45/red2fix-minikit/pull/4"' in page
    assert "<b>note</b>" not in page and "a &lt;b&gt;note&lt;/b&gt;" in page  # model-written notes are escaped
    assert any("parse_duration('5m')" in c.value for c in at.code)


def test_app_renders_the_bench_report(root, monkeypatch):
    at = app(root, monkeypatch, "bench/rv/a__b-1/failed")
    assert not at.exception, at.exception
    page = "".join(m.value for m in at.markdown)
    first = page.index("false approvals · blocker")
    assert first < page.index("gold approvals · blocker")
    assert '<div class="v">1/1</div>' in page and "failed claim" in page


def test_query_param_cannot_leave_out(root, monkeypatch):
    at = app(root, monkeypatch, "../../etc")
    assert not at.exception, at.exception


@pytest.mark.parametrize("group,red_green,shown", [
    ("demo", "1/1", "detail · 1<"),
    ("pilot", "0/1", '<span class="name">c__d-2</span>'),
])
def test_app_renders(root, monkeypatch, group, red_green, shown):
    monkeypatch.setattr(data, "ROOT", root)
    monkeypatch.setenv("RED2FIX_ENABLE_LAUNCH", "1")
    at = AppTest.from_file("../dashboard/app.py", default_timeout=30).run()
    next(b for b in at.sidebar.selectbox if b.label == "Runs").set_value(group).run()
    assert not at.exception, at.exception
    page = "".join(m.value for m in at.markdown)
    assert f'<div class="v">{red_green}</div>' in page
    assert shown in page
