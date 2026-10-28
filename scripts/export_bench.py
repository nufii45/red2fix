"""Freeze the data the public site reads: the only writer of web/public/data/.

Usage: uv run scripts/export_bench.py [RUN_DIR] [OUT_FILE]
Defaults: out/bench/rv-full → web/public/data/bench.json (recomputed verdicts, both label views, errors by
cause, cost by model from the ledgers), plus web/public/data/demos.json from the recorded demo PR runs in
web/fixtures/ (verdict, cost, time, searches, trace link).
"""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # run as a script, scripts/ is on the path but the repo root is not

from config import MODELS  # noqa: E402

DEMOS = ("good", "wrong", "breaks", "restricted", "inject", "inject2", "dep-advisory")
# shortcut: the two emulation reasons are rv-full's amd64-on-arm64 run (DECISIONS.md 2026-10-28); a native bench
# would need its own causes. Unknown reasons fall back to the reason itself.
ERROR_CAUSE = {"budget_usd": "budget cap", "patch_does_not_apply": "patch doesn't apply",
               "<suite timed out>": "amd64 emulation", "<pytest wrote no report>": "amd64 emulation"}


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def cost_by_model(run):
    name = {m: k for k, m in MODELS.items()}
    calls, usd = Counter(), Counter()
    for row in (r for p in sorted(run.glob("*/*/ledger.jsonl")) for r in rows(p)):
        if row.get("model") in name:  # tavily rows cost nothing
            calls[name[row["model"]]] += 1
            usd[name[row["model"]]] += row.get("cost_usd") or 0
    return {k: {"calls": calls[k], "usd": round(usd[k], 4)} for k in MODELS if calls[k]}


def bench(run):
    r = json.loads((run / "review_report.json").read_text())
    s = r["settings"]["blocker"]
    verdict = lambda v: v.get("recomputed", v["verdict"])  # noqa: E731
    errors = Counter(ERROR_CAUSE.get((v.get("reason") or "").split(":")[0], v.get("reason") or "unknown")
                     for row in r["instances"].values() for k, v in row.items()
                     if k in ("gold", "failed") and verdict(v) == "error")
    return {
        "run": run.name,
        "commit": "0c32486",
        "reviews": r["reviews"],
        "original": {"false_approvals": s["false_approvals"], "failed_total": s["failed_total"]},
        "cleaned": {"false_approvals": s["false_approvals_cleaned"], "failed_total": s["failed_total_cleaned"]},
        "gold": {"approvals": s["gold_approvals"], "total": s["gold_total"]},
        "verdicts": s["verdicts"],
        "settings_identical": r["settings"]["blocker"] == r["settings"]["warning"],
        "unproven": r["unproven"],
        "errors": r["errors"],
        "errors_by_cause": dict(errors.most_common()),
        "median_usd": round(r["median_usd"], 4),
        "median_s": r["median_s"],
        "total_usd": round(r["total_usd"], 2),
        "calls": r["calls"],
        "cost_by_model": cost_by_model(run),
        "instances": [
            {
                "id": iid,
                **{
                    kind: {"verdict": verdict(v), "cost_usd": round(v["cost_usd"] or 0, 4),
                           "seconds": v["seconds"], **({"truly_failed": v["truly_failed"]} if "truly_failed" in v else {})}
                    for kind, v in row.items() if kind in ("gold", "failed")
                },
            }
            for iid, row in sorted(r["instances"].items())
        ],
    }


def demos(fixtures):
    out = []
    for name in DEMOS:
        rv = json.loads((fixtures / name / "review.json").read_text())
        out.append({"name": name, "verdict": rv["verdict"], "cost_usd": round(rv["cost_usd"], 4),
                    "seconds": rv["seconds"], "searches": len(rv.get("web_searches") or []), "trace_url": rv.get("trace_url")})
    return out


def export(run, dest, fixtures=ROOT / "web" / "fixtures"):
    b, d = bench(run), demos(fixtures)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(b, indent=1) + "\n")
    (dest.parent / "demos.json").write_text(json.dumps(d, indent=1) + "\n")
    print(f"wrote {dest}: {len(b['instances'])} instances; {dest.parent / 'demos.json'}: {len(d)} demo PRs")
    return b, d


if __name__ == "__main__":
    export(Path(sys.argv[1] if len(sys.argv) > 1 else "out/bench/rv-full"),
           Path(sys.argv[2] if len(sys.argv) > 2 else "web/public/data/bench.json"))
