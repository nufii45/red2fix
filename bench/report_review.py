"""Score a review-mode bench run: does Red2Fix's verdict agree with the ground truth?

Usage: uv run bench/report_review.py <run-id>
Gold patches are resolved by definition; failed patches are unresolved per their submission's official results.
Verdicts are recomputed from the stored review.json under both unrelated_change settings (no model calls).
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
from agent.review import decide  # noqa: E402

KINDS = ("gold", "failed")
SETTINGS = ("blocker", "warning")


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
        runs.setdefault(d.parent.name, {})[d.name] = json.loads(f.read_text()) if f.exists() else None
    return runs


def summarize(runs):
    reviews = [rv for kinds in runs.values() for rv in kinds.values()]
    done = [rv for rv in reviews if rv]
    by_setting = {}
    for s in SETTINGS:
        failed = {i: recompute(k["failed"], s) for i, k in runs.items() if "failed" in k}
        gold = {i: recompute(k["gold"], s) for i, k in runs.items() if "gold" in k}
        by_setting[s] = {
            "false_approvals": sorted(i for i, v in failed.items() if v == "proven"), "failed_total": len(failed),
            "gold_approvals": sum(v == "proven" for v in gold.values()), "gold_total": len(gold),
            "verdicts": {"gold": dict(Counter(gold.values())), "failed": dict(Counter(failed.values()))},
        }
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
        "instances": {
            i: {k: {"verdict": rv["verdict"] if rv else "missing", "reason": rv.get("verdict_reason") if rv else None,
                    "cost_usd": rv["cost_usd"] if rv else None, "seconds": rv["seconds"] if rv else None}
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
            f"**unrelated_change = \"{name}\"**",
            f"- False approvals (failed patches marked proven): {len(t['false_approvals'])} / {t['failed_total']} ({fa})",
            f"- Correct approvals (gold patches marked proven): {t['gold_approvals']} / {t['gold_total']}",
            "",
        ]
    mix = ", ".join(f"{k} {n}" for k, n in sorted(s["calls"].items()) if n)
    lines += [
        f"Reviews: {s['reviews']} · unproven: {s['unproven']} · errors: {s['errors']} · "
        f"median ${s['median_usd']:.3f} and {s['median_s']:.0f} s per review · total ${s['total_usd']:.2f} · calls: {mix}",
        "",
        "Stored verdicts (policy as run, unrelated_change = \"blocker\"):",
        "",
        "| Instance | Gold | Failed | $ | s |",
        "|---|---|---|---|---|",
    ]
    for i, kinds in sorted(s["instances"].items()):
        cell = {k: kinds[k]["verdict"] if k in kinds else "—" for k in KINDS}
        usd = sum(v["cost_usd"] or 0 for v in kinds.values())
        secs = sum(v["seconds"] or 0 for v in kinds.values())
        lines.append(f"| {i} | {cell['gold']} | {cell['failed']} | {usd:.3f} | {secs:.0f} |")
    return "\n".join(lines) + "\n"


def report(out_root):
    s = summarize(load(out_root))
    (out_root / "review_report.json").write_text(json.dumps(s, indent=2))
    text = markdown(s)
    (out_root / "review_report.md").write_text(text)
    print(text)
    return s


if __name__ == "__main__":
    report(ROOT / "out" / "bench" / sys.argv[1])
