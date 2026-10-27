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


def test_review_one_runs_agent_review_without_the_test_patch(tmp_path, monkeypatch):
    calls = []

    def fake_run(args, **kw):
        calls.append(args)
        if args[:2] == ["docker", "run"]:
            (tmp_path / INST["instance_id"] / "gold" / "result.json").write_text('{"status": "succeeded", "verdict": "proven"}')
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run.subprocess, "run", fake_run)
    inst = {**INST, "test_patch": "SECRET HIDDEN TESTS"}
    _, kind, r = run.review_one(inst, "gold", "the gold diff", tmp_path, 900)

    out = tmp_path / INST["instance_id"] / "gold"
    assert (kind, r["verdict"]) == ("gold", "proven")
    assert (out / "pr.patch").read_text() == "the gold diff" and (out / "spec.md").read_text() == "p"
    args = calls[-1]
    assert args[args.index("--entrypoint") + 1] == "/opt/r2f/bin/python" and "agent.review" in args
    assert args[args.index("--spec-source") + 1] == "issue"
    assert args[args.index("--repro-steps") + 1] == "15"
    assert args[args.index("--suite") + 1:] == ["t.py"]
    assert args[args.index("--repo") + 1] == args[args.index("--work") + 1] == "/testbed"
    assert not any("SECRET" in a for a in args) and "SECRET" not in "".join(p.read_text() for p in out.iterdir())


def test_review_jobs_skips_missing_failed_patches():
    a, b = {**INST, "instance_id": "a__a-1", "patch": "ga"}, {**INST, "instance_id": "b__b-2", "patch": "gb"}
    jobs, missing = run.review_jobs([a, b], "both", {"a__a-1": {"system": "s", "patch": "fa"}})
    assert [(i["instance_id"], k, p) for i, k, p in jobs] == [("a__a-1", "gold", "ga"), ("a__a-1", "failed", "fa"), ("b__b-2", "gold", "gb")]
    assert missing == ["b__b-2/failed"]
