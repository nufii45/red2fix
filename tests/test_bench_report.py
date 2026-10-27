import json

from bench import report_review

CAP_QUOTE = "+    return min(total, 86400)"


def rv(verdict, proof="proven", findings=(), cost=0.1, secs=60, **kw):
    return {"verdict": verdict, "verdict_reason": "r", "proof": {"result": proof}, "suite": {"new_failures": []},
            "findings": list(findings), "restricted_paths_touched": [], "require_proof": True, "spec_source": "issue",
            "cost_usd": cost, "seconds": secs, "calls": {"ultra": 3, "nano": 2}, **kw}


SNEAKY = {"rule": "No changes unrelated to the spec", "severity": "warning", "quote": CAP_QUOTE, "diff_file": "pkg/util.py"}


def write(root, iid, kind, review):
    d = root / iid / kind
    d.mkdir(parents=True)
    if review is not None:
        (d / "review.json").write_text(json.dumps(review))


def test_report_counts_under_both_settings(tmp_path):
    write(tmp_path, "a__a-1", "gold", rv("proven"))
    write(tmp_path, "a__a-1", "failed", rv("doesnt_fix", proof="doesnt_fix"))
    # Stored as needs_review (run with "blocker"); under "warning" the same review would approve it.
    write(tmp_path, "b__b-2", "gold", rv("unproven", proof="unproven", cost=0.3, secs=100))
    write(tmp_path, "b__b-2", "failed", rv("needs_review", findings=[SNEAKY]))
    write(tmp_path, "c__c-3", "gold", None)  # crashed: no review.json

    s = report_review.report(tmp_path)

    blocker, warning = s["settings"]["blocker"], s["settings"]["warning"]
    assert (blocker["false_approvals"], blocker["failed_total"]) == ([], 2)
    assert (warning["false_approvals"], warning["failed_total"]) == (["b__b-2"], 2)
    assert (blocker["gold_approvals"], blocker["gold_total"]) == (1, 3)
    assert (s["reviews"], s["unproven"], s["errors"]) == (5, 1, 1)
    assert s["median_usd"] == 0.1 and s["calls"] == {"ultra": 12, "nano": 8}
    md = (tmp_path / "review_report.md").read_text()
    assert "False approvals (failed patches marked proven): 1 / 2 (b__b-2)" in md
    assert "%" not in md
    assert json.loads((tmp_path / "review_report.json").read_text())["instances"]["c__c-3"]["gold"]["verdict"] == "missing"


def test_errors_are_not_recomputed():
    assert report_review.recompute(rv("error", proof=None), "warning") == "error"
    assert report_review.recompute(None, "blocker") == "missing"
