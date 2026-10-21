"""Run the agent on the frozen SWE-bench list, one Docker container per instance.

Usage: uv run bench/run.py --run-id pilot [--ids id1,id2] [-j 2] [--max-seconds 1200]
Results land in out/bench/<run-id>/<instance>/, plus preds.jsonl for bench/score.sh.
"""

import argparse
import json
import re
import statistics
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTANCES = json.loads((ROOT / "bench" / "instances.json").read_text())


def run_one(inst, out_root, max_seconds):
    iid = inst["instance_id"]
    out = out_root / iid
    out.mkdir(parents=True, exist_ok=True)
    (out / "issue.md").write_text(inst["problem_statement"])
    tag = "r2f-" + iid.lower().replace("__", "-")
    number = re.search(r"(\d+)$", iid).group(1)
    with open(out / "run.log", "w") as log:
        build = subprocess.run(
            ["docker", "build", "--platform", "linux/amd64", "-q", "-f", "bench/Dockerfile.swebench",
             "--build-arg", f"BASE={inst['image']}", "-t", tag, "."],
            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
        )
        if build.returncode:
            return iid, {"status": "aborted", "abort_reason": "error: image build failed (see run.log)"}
        subprocess.run(
            ["docker", "run", "--rm", "--platform", "linux/amd64", "--env-file", str(ROOT / ".env"),
             "-v", f"{out}:/out", tag, "--issue", "/out/issue.md", "--out", "/out", "--number", number,
             "--max-seconds", str(max_seconds), "--suite", *inst["test_files"]],
            stdout=log, stderr=subprocess.STDOUT,
        )
    result = out / "result.json"
    if not result.exists():
        return iid, {"status": "aborted", "abort_reason": "error: no result.json (see run.log)"}
    return iid, json.loads(result.read_text())


def report(out_root):
    """Write preds.jsonl and print a table for every instance this run has a result for."""
    rows, preds = [], []
    for inst in INSTANCES:
        d = out_root / inst["instance_id"]
        if not (d / "result.json").exists():
            continue
        r = json.loads((d / "result.json").read_text())
        ok = r["status"] == "succeeded"
        patch = (d / "patch.diff").read_text() if ok and (d / "patch.diff").exists() else ""
        preds.append({"instance_id": inst["instance_id"], "model_name_or_path": "red2fix", "model_patch": patch})
        rows.append((inst["instance_id"], r))
    (out_root / "preds.jsonl").write_text("".join(json.dumps(p) + "\n" for p in preds))

    print(f"\n{'instance':40} {'outcome':34} {'iters':>5} {'$':>7} {'secs':>6}")
    for iid, r in rows:
        outcome = r["status"] if r["status"] == "succeeded" else (r.get("abort_reason") or "")[:34]
        print(f"{iid:40} {outcome:34} {r.get('iterations', 0):>5} {r.get('cost_usd', 0):>7.3f} {r.get('seconds', 0):>6.0f}")
    if rows:
        costs = [r.get("cost_usd", 0) for _, r in rows]
        secs = [r.get("seconds", 0) for _, r in rows]
        won = sum(r["status"] == "succeeded" for _, r in rows)
        print(f"\nown repro red→green: {won}/{len(rows)} · total ${sum(costs):.2f} · "
              f"median ${statistics.median(costs):.3f}/issue · median {statistics.median(secs):.0f}s/issue")
    print(f"predictions: {out_root / 'preds.jsonl'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--ids", help="comma-separated instance ids (default: all in bench/instances.json)")
    ap.add_argument("-j", type=int, default=2, help="parallel containers")
    ap.add_argument("--max-seconds", type=int, default=1200, help="per-run cap; emulation is slow")
    a = ap.parse_args()

    known = {i["instance_id"] for i in INSTANCES}
    wanted = set(a.ids.split(",")) if a.ids else known
    if wanted - known:
        raise SystemExit(f"unknown ids: {sorted(wanted - known)}")
    out_root = ROOT / "out" / "bench" / a.run_id
    chosen = [i for i in INSTANCES if i["instance_id"] in wanted]

    with ThreadPoolExecutor(a.j) as ex:
        futures = [ex.submit(run_one, inst, out_root, a.max_seconds) for inst in chosen]
        for f in as_completed(futures):
            iid, r = f.result()
            print(f"done {iid}: {r['status']} {r.get('abort_reason') or ''}", flush=True)
    report(out_root)


if __name__ == "__main__":
    main()
