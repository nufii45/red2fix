"""Run the agent on the frozen SWE-bench list, one Docker container per instance.

Usage: uv run bench/run.py --run-id pilot [--ids id1,id2] [-j 2] [--max-seconds 1200]
       uv run bench/run.py --run-id rv-pilot --mode review --patches both [--ids ...]
Fix mode: results land in out/bench/<run-id>/<instance>/, plus preds.jsonl for bench/score.sh.
Review mode: each patch kind (gold, failed) is reviewed in out/bench/<run-id>/<instance>/<kind>/;
bench/report_review.py scores them. The image never gets the SWE-bench test_patch.
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


def aborted(out, reason):
    """Record a run that never produced its own result, so report() and the dashboard still count it."""
    r = {"status": "aborted", "abort_reason": reason}
    (out / "result.json").write_text(json.dumps(r, indent=2))
    return r


def build(inst, log):
    """Image tag for the instance, or None if the build failed."""
    tag = "r2f-" + inst["instance_id"].lower().replace("__", "-")
    r = subprocess.run(
        ["docker", "build", "--platform", "linux/amd64", "-q", "-f", "bench/Dockerfile.swebench",
         "--build-arg", f"BASE={inst['image']}", "-t", tag, "."],
        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
    )
    return None if r.returncode else tag


def number_of(iid):
    return re.search(r"(\d+)$", iid).group(1)


def run_one(inst, out_root, max_seconds):
    iid = inst["instance_id"]
    out = out_root / iid
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").unlink(missing_ok=True)  # a stale result would hide a crash in this run
    (out / "issue.md").write_text(inst["problem_statement"])
    number = number_of(iid)
    with open(out / "run.log", "w") as log:
        tag = build(inst, log)
        if not tag:
            return iid, aborted(out, "error: image build failed (see run.log)")
        subprocess.run(
            ["docker", "run", "--rm", "--platform", "linux/amd64", "--env-file", str(ROOT / ".env"), "-e", f"RED2FIX_INSTANCE={iid}",
             "-v", f"{out}:/out", tag, "--issue", "/out/issue.md", "--out", "/out", "--number", number,
             "--max-seconds", str(max_seconds), "--suite", *inst["test_files"]],
            stdout=log, stderr=subprocess.STDOUT,
        )
    result = out / "result.json"
    if not result.exists():
        return iid, aborted(out, "error: no result.json (see run.log)")
    return iid, json.loads(result.read_text())


def review_one(inst, kind, patch, out_root, max_seconds):
    """Review one patch (gold or failed) against the instance's base commit, in place in /testbed."""
    iid = inst["instance_id"]
    out = out_root / iid / kind
    out.mkdir(parents=True, exist_ok=True)
    for stale in ("result.json", "review.json"):
        (out / stale).unlink(missing_ok=True)
    (out / "spec.md").write_text(inst["problem_statement"])
    (out / "pr.patch").write_text(patch)
    with open(out / "run.log", "w") as log:
        tag = build(inst, log)
        if not tag:
            return iid, kind, aborted(out, "error: image build failed (see run.log)")
        subprocess.run(
            ["docker", "run", "--rm", "--platform", "linux/amd64", "--env-file", str(ROOT / ".env"), "-e", f"RED2FIX_INSTANCE={iid}",
             "-v", f"{out}:/out", "--entrypoint", "/opt/r2f/bin/python", tag,
             "-m", "agent.review", "--repo", "/testbed", "--work", "/testbed",
             "--spec", "/out/spec.md", "--patch", "/out/pr.patch", "--out", "/out", "--number", number_of(iid),
             # The problem statement is the issue, so the PR-description cap never applies on the bench.
             "--spec-source", "issue", "--max-seconds", str(max_seconds), "--repro-steps", "15",
             # Off whatever the policy says: SWE-bench fixes are public, so a search could find the answer.
             "--no-web-search",
             "--suite", *inst["test_files"]],
            stdout=log, stderr=subprocess.STDOUT,
        )
    if not (out / "result.json").exists():
        return iid, kind, aborted(out, "error: no result.json (see run.log)")
    return iid, kind, json.loads((out / "result.json").read_text())


def review_jobs(chosen, patches, failed):
    """[(inst, kind, patch)] for the requested kinds, plus the ids that have no usable failed patch."""
    kinds = ["gold", "failed"] if patches == "both" else [patches]
    jobs, missing = [], []
    for inst in chosen:
        for kind in kinds:
            patch = inst["patch"] if kind == "gold" else (failed.get(inst["instance_id"]) or {}).get("patch")
            if patch:
                jobs.append((inst, kind, patch))
            else:
                missing.append(f"{inst['instance_id']}/{kind}")
    return jobs, missing


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
    ap.add_argument("--mode", choices=["fix", "review"], default="fix")
    ap.add_argument("--patches", choices=["gold", "failed", "both"], default="both", help="review mode only")
    a = ap.parse_args()

    known = {i["instance_id"] for i in INSTANCES}
    wanted = set(a.ids.split(",")) if a.ids else known
    if wanted - known:
        raise SystemExit(f"unknown ids: {sorted(wanted - known)}")
    out_root = ROOT / "out" / "bench" / a.run_id
    chosen = [i for i in INSTANCES if i["instance_id"] in wanted]

    if a.mode == "review":
        import report_review  # bench/ is on sys.path when this file runs as a script

        failed_file = ROOT / "bench" / "failed_patches.json"
        failed = json.loads(failed_file.read_text()) if failed_file.exists() else {}
        jobs, missing = review_jobs(chosen, a.patches, failed)
        if missing:
            print(f"no patch, skipped: {', '.join(missing)}", flush=True)
        with ThreadPoolExecutor(a.j) as ex:
            futures = [ex.submit(review_one, inst, kind, patch, out_root, a.max_seconds) for inst, kind, patch in jobs]
            for f in as_completed(futures):
                iid, kind, r = f.result()
                print(f"done {iid}/{kind}: {r.get('verdict') or r['status']} {r.get('abort_reason') or ''}", flush=True)
        report_review.report(out_root)
        return

    with ThreadPoolExecutor(a.j) as ex:
        futures = [ex.submit(run_one, inst, out_root, a.max_seconds) for inst in chosen]
        for f in as_completed(futures):
            iid, r = f.result()
            print(f"done {iid}: {r['status']} {r.get('abort_reason') or ''}", flush=True)
    report(out_root)


if __name__ == "__main__":
    main()
