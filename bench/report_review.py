"""Score a review-mode bench run: does Red2Fix's verdict agree with the ground truth?

Usage: uv run bench/report_review.py <run-id>
Gold patches are resolved by definition; failed patches are unresolved per their submission's official results.
Verdicts are recomputed from the stored review.json and red.log/head.log under both unrelated_change settings
(no model calls), with the current decide() and HEAD_CHECK rules. Cleaned labels come from bench/failed_labels.json.
Writes out/bench/<run-id>/review_report.md and .json. Counts only, no percentages.
"""

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # run as a script, bench/ is on the path but the repo root is not

from agent.policy import DEFAULTS  # noqa: E402
from agent.review import decide, same_failure  # noqa: E402

KINDS = ("gold", "failed")
SETTINGS = ("blocker", "warning")
LABELS = ROOT / "bench" / "failed_labels.json"
CLEANED_RULE = ("Cleaned labels: a failed patch counts as truly failed only if at least one of its FAIL_TO_PASS tests "
                "failed in its official SWE-bench report (bench/failed_labels.json). "
                "This rule was defined after inspecting these results.")


def recompute(rv, unrelated_change):
    """The verdict this review would get under the given setting; errors and incomplete runs stay as they are."""
    if rv is None:
        return "missing"
    proof = rv.get("proof", {}).get("result")
    if rv["verdict"] == "error" or proof is None:
        return rv["verdict"]
    policy = {**DEFAULTS, "require_proof": rv.get("require_proof", True), "unrelated_change": unrelated_change}
    return decide(proof, set(rv["suite"]["new_failures"]), rv["findings"], rv["restricted_paths_touched"],
                  policy, rv.get("spec_source", "issue"))[0]


def load(out_root):
    """{instance: {kind: review.json or None}} for every kind that was attempted (has a folder)."""
    runs = {}
    for d in sorted(p for p in out_root.glob("*/*") if p.is_dir() and p.name in KINDS):
        f = d / "review.json"
        rv = json.loads(f.read_text()) if f.exists() else None
        # HEAD_CHECK's same-failure rule, applied to the stored logs of reviews that ran before it existed.
        logs = [d / "red.log", d / "head.log"]
        if rv and rv.get("proof", {}).get("result") == "doesnt_fix" and all(l.exists() for l in logs):
            if same_failure(*(l.read_text() for l in logs)):
                rv["proof"]["result"] = "unreached"
        runs.setdefault(d.parent.name, {})[d.name] = rv
    return runs


def summarize(runs, labels=None):
    """labels: {instance: failed FAIL_TO_PASS tests} for the failed patches, or None for no cleaned counts."""
    truly = {i for i, failed in (labels or {}).items() if failed}
    reviews = [rv for kinds in runs.values() for rv in kinds.values()]
    done = [rv for rv in reviews if rv]
    by_setting = {}
    for s in SETTINGS:
        failed = {i: recompute(k["failed"], s) for i, k in runs.items() if "failed" in k}
        gold = {i: recompute(k["gold"], s) for i, k in runs.items() if "gold" in k}
        by_setting[s] = {
            "false_approvals": sorted(i for i, v in failed.items() if v == "proven"), "failed_total": len(failed),
            "false_approvals_cleaned": sorted(i for i, v in failed.items() if v == "proven" and i in truly),
            "failed_total_cleaned": len(failed.keys() & truly),
            "gold_approvals": sum(v == "proven" for v in gold.values()), "gold_total": len(gold),
            "verdicts": {"gold": dict(Counter(gold.values())), "failed": dict(Counter(failed.values()))},
        }
    stored = {i: k["failed"]["verdict"] if k["failed"] else "missing" for i, k in runs.items() if "failed" in k}
    stored_fa = sorted(i for i, v in stored.items() if v == "proven")
    calls = Counter()
    for rv in done:
        calls.update(rv.get("calls", {}))
    return {
        "reviews": len(reviews),
        "unproven": sum(rv["verdict"] == "unproven" for rv in done),
        "errors": sum(rv is None or rv["verdict"] == "error" for rv in reviews),
        "median_usd": statistics.median(rv["cost_usd"] for rv in done) if done else 0.0,
        "median_s": statistics.median(rv["seconds"] for rv in done) if done else 0.0,
        "total_usd": sum(rv["cost_usd"] for rv in done),
        "calls": dict(calls),
        "settings": by_setting,
        "labels": labels is not None,
        "stored": {"false_approvals": stored_fa, "false_approvals_cleaned": [i for i in stored_fa if i in truly]},
        "instances": {
            i: {k: {"verdict": rv["verdict"] if rv else "missing", "recomputed": recompute(rv, "blocker"),
                    "reason": rv.get("verdict_reason") if rv else None,
                    "cost_usd": rv["cost_usd"] if rv else None, "seconds": rv["seconds"] if rv else None,
                    **({"truly_failed": i in truly} if k == "failed" and labels is not None else {})}
                for k, rv in kinds.items()}
            for i, kinds in runs.items()
        },
    }


def markdown(s):
    lines = ["# Red2Fix review bench", ""]
    for name in SETTINGS:
        t = s["settings"][name]
        fa = ", ".join(t["false_approvals"]) or "none"
        lines += [
            f"**unrelated_change = \"{name}\"** (recomputed)",
            f"- False approvals (failed patches marked proven): {len(t['false_approvals'])} / {t['failed_total']} ({fa})",
        ]
        if s["labels"]:
            fc = ", ".join(t["false_approvals_cleaned"]) or "none"
            lines.append(f"- False approvals, cleaned labels: {len(t['false_approvals_cleaned'])} / {t['failed_total_cleaned']} ({fc})")
        lines += [f"- Correct approvals (gold patches marked proven): {t['gold_approvals']} / {t['gold_total']}", ""]
    st = s["stored"]
    lines.append(f"**Stored verdicts (as run)**: false approvals {len(st['false_approvals'])} / "
                 f"{s['settings']['blocker']['failed_total']} ({', '.join(st['false_approvals']) or 'none'})"
                 + (f"; cleaned labels {len(st['false_approvals_cleaned'])} / {s['settings']['blocker']['failed_total_cleaned']}"
                    if s["labels"] else ""))
    lines += ["", "Recomputed = the stored review re-decided by the current rules, including \"same failure on base "
              "and head → unproven\" applied to the stored red.log/head.log. No model calls."]
    if s["labels"]:
        lines += ["", CLEANED_RULE]
    lines.append("")
    mix = ", ".join(f"{k} {n}" for k, n in sorted(s["calls"].items()) if n)
    lines += [
        f"Reviews: {s['reviews']} · unproven: {s['unproven']} · errors: {s['errors']} · "
        f"median ${s['median_usd']:.3f} and {s['median_s']:.0f} s per review · total ${s['total_usd']:.2f} · calls: {mix}",
        "",
        "Verdicts, stored → recomputed (unrelated_change = \"blocker\"):",
        "",
        "| Instance | Gold | Failed | Truly failed | $ | s |",
        "|---|---|---|---|---|---|",
    ]
    for i, kinds in sorted(s["instances"].items()):
        cell = {k: (lambda v: v["verdict"] if v["verdict"] == v["recomputed"] else f"{v['verdict']} → **{v['recomputed']}**")(kinds[k])
                if k in kinds else "—" for k in KINDS}
        truly = {True: "yes", False: "no"}.get(kinds.get("failed", {}).get("truly_failed"), "—")
        usd = sum(v["cost_usd"] or 0 for v in kinds.values())
        secs = sum(v["seconds"] or 0 for v in kinds.values())
        lines.append(f"| {i} | {cell['gold']} | {cell['failed']} | {truly} | {usd:.3f} | {secs:.0f} |")
    return "\n".join(lines) + "\n"


def report(out_root, labels_path=LABELS):
    s = summarize(load(out_root), json.loads(labels_path.read_text()) if labels_path.exists() else None)
    (out_root / "review_report.json").write_text(json.dumps(s, indent=2))
    text = markdown(s)
    (out_root / "review_report.md").write_text(text)
    print(text)
    return s


if __name__ == "__main__":
    report(ROOT / "out" / "bench" / sys.argv[1])
