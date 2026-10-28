"""Freeze the review bench report for the try-it site.

Usage: python scripts/export_bench.py [RUN_DIR] [OUT_FILE]
Defaults: out/bench/rv-full → web/public/data/bench.json. Recomputed verdicts, both label views.
"""

import json
import sys
from pathlib import Path

run = Path(sys.argv[1] if len(sys.argv) > 1 else "out/bench/rv-full")
dest = Path(sys.argv[2] if len(sys.argv) > 2 else "web/public/data/bench.json")
r = json.loads((run / "review_report.json").read_text())
s = r["settings"]["blocker"]

out = {
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
    "median_usd": round(r["median_usd"], 4),
    "median_s": r["median_s"],
    "total_usd": round(r["total_usd"], 2),
    "calls": r["calls"],
    "instances": [
        {
            "id": iid,
            **{
                kind: {"verdict": v.get("recomputed", v["verdict"]), "cost_usd": round(v["cost_usd"], 4),
                       "seconds": v["seconds"], **({"truly_failed": v["truly_failed"]} if "truly_failed" in v else {})}
                for kind, v in row.items() if kind in ("gold", "failed")
            },
        }
        for iid, row in sorted(r["instances"].items())
    ],
}
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(out, indent=1) + "\n")
print(f"wrote {dest}: {len(out['instances'])} instances")
