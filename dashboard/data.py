"""Load the run folders under out/ for the dashboard. No Streamlit here, so it stays testable.

Layout: out/<n>/ is a demo fix run, out/review-<name>/ a demo review, out/bench/<run-id>/<instance>/ a
benchmark fix run, and out/bench/<run-id>/<instance>/<gold|failed>/ a benchmark review.
"""

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import config

ROOT = Path(__file__).resolve().parent.parent
TEXT = ["issue.md", "repro_test.py", "red.log", "patch.diff", "green.log", "summary.md"]

# Agent phases folded into the steps the step bar shows.
STEPS = {
    "TRIAGE": "Triage", "BASELINE": "Triage", "LOCALIZE": "Localize",
    "REPRODUCE": "Reproduce", "VERIFY_RED": "Reproduce", "COMMIT_REPRO": "Reproduce",
    "FIX": "Fix", "CHECK": "Fix", "ESCALATE": "Fix",
    "CONFIRM": "Confirm", "SUMMARIZE": "Confirm", "DONE": "Done",
}
STEP_NAMES = list(dict.fromkeys(STEPS.values()))

# Review phases (agent/review.py) folded the same way.
REVIEW_STEPS = {
    "QUEUED": "Triage", "TRIAGE": "Triage", "BASELINE": "Triage", "LOCALIZE": "Localize",
    "REPRODUCE": "Reproduce", "VERIFY_RED": "Reproduce", "COMMIT_REPRO": "Reproduce",
    "APPLY_PR": "Head", "HEAD_CHECK": "Head", "REVIEW": "Review", "VERDICT": "Verdict", "DONE": "Verdict",
}
REVIEW_STEP_NAMES = list(dict.fromkeys(REVIEW_STEPS.values()))
REVIEW_KINDS = ("gold", "failed")
VERDICTS = ["proven", "needs_review", "unproven", "doesnt_fix", "breaks_tests", "error"]
LABELS = {
    "proven": "✅ Proven", "needs_review": "🔶 Needs review", "unproven": "⚠️ Unproven",
    "doesnt_fix": "❌ Doesn't fix", "breaks_tests": "❌ Breaks tests", "error": "⛔ Error",
}
REVIEW_TEXT = ["spec.md", "pr.patch", "repro_test.py", "red.log", "head.log", "review.md"]

FAILURES = {
    "out_of_scope": "out of scope", "no_repro": "couldn't reproduce", "max_iterations": "no fix within iteration limit",
    "budget_usd": "budget exceeded", "timeout": "timed out", "confirm_failed": "red→green not confirmed", "error": "error",
}
MODEL_NAMES = {v: k for k, v in config.MODELS.items()}


def read_jsonl(path):
    rows = []
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # a live run can be mid-write on its last line
    return rows


def is_review(run_dir):
    """A review run, finished or still live (no review.json yet)."""
    return (run_dir / "review.json").exists() or run_dir.name.startswith("review-") or run_dir.name in REVIEW_KINDS


def group_of(run_dir, out_root):
    parts = run_dir.relative_to(out_root).parts
    if len(parts) == 1:
        return "reviews" if is_review(run_dir) else "demo"
    if len(parts) == 3 and parts[0] == "bench":
        return parts[1]
    if len(parts) == 4 and parts[0] == "bench" and parts[3] in REVIEW_KINDS:
        return parts[1]
    return None


def find_runs(out_root):
    """[(group, run_dir)] for every folder with a result or live events."""
    dirs = {p.parent for name in ("result.json", "events.jsonl") for p in out_root.glob(f"**/{name}")}
    return sorted((g, d) for d in dirs if (g := group_of(d, out_root)))


def mtime(run_dir):
    return max((p.stat().st_mtime for p in run_dir.iterdir()), default=0)


def load_run(run_dir):
    try:
        result = json.loads((run_dir / "result.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        result = {"status": "running"}
    events = read_jsonl(run_dir / "events.jsonl")
    ledger = read_jsonl(run_dir / "ledger.jsonl")
    phases = [e for e in events if e.get("ev") == "phase"]
    if result["status"] == "running":
        result["phase"] = phases[-1]["name"] if phases else None
        result["cost_usd"] = round(sum(r["cost_usd"] for r in ledger), 6)
    return {
        "name": run_dir.name, "dir": run_dir, "result": result, "events": events, "ledger": ledger,
        "text": {n: (run_dir / n).read_text() for n in TEXT if (run_dir / n).exists()},
    }


def run_name(run_dir):
    """Bench reviews are named <instance>/<kind>; everything else by its folder."""
    return f"{run_dir.parent.name}/{run_dir.name}" if run_dir.name in REVIEW_KINDS else run_dir.name


def load_review(run_dir):
    """load_run() plus the parsed review.json (None while live) and the review's text files.

    Older review.json files lack dropped_findings, finding quotes and proof.result; callers use .get().
    """
    run = load_run(run_dir)
    try:
        review = json.loads((run_dir / "review.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        review = None
    text = {n: (run_dir / n).read_text() for n in REVIEW_TEXT if (run_dir / n).exists()}
    return {**run, "name": run_name(run_dir), "review": review, "text": {**run["text"], **text}}


def verdict_counts(runs):
    """{verdict: count} over finished reviews, in VERDICTS order."""
    found = Counter(r["review"]["verdict"] for r in runs if r.get("review"))
    return {v: found[v] for v in VERDICTS}


def bench_report(group_dir):
    """review_report.json written by bench/report_review.py, or None."""
    try:
        return json.loads((group_dir / "review_report.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def failure(result):
    reason = result.get("abort_reason") or ""
    return FAILURES.get(reason.split(":")[0], reason)


def summarize(runs):
    done = [r["result"] for r in runs if r["result"]["status"] != "running"]
    costs = [r.get("cost_usd", 0) for r in done]
    secs = [r.get("seconds", 0) for r in done]
    won = sum(r["status"] == "succeeded" for r in done)
    return {
        "attempted": len(done),
        "running": len(runs) - len(done),
        "won": won,
        "rate": won / len(done) if done else 0.0,
        "total_usd": sum(costs),
        "median_usd": statistics.median(costs) if done else 0.0,
        "median_s": statistics.median(secs) if done else 0.0,
        "failures": dict(Counter(failure(r) for r in done if r["status"] != "succeeded")),
    }


def cost_by(runs, key):
    """{run name: {model or phase: usd}} for a stacked bar."""
    out = defaultdict(lambda: defaultdict(float))
    for run in runs:
        for row in run["ledger"]:
            label = MODEL_NAMES.get(row[key], row[key]) if key == "model" else row[key]
            out[run["name"]][label] += row["cost_usd"]
    return {k: dict(v) for k, v in out.items()}


def total_spend(out_root):
    return sum(r["cost_usd"] for p in out_root.glob("**/ledger.jsonl") for r in read_jsonl(p))


def official(run_id, root=None):
    """Resolved instance ids from `swebench eval`, or None if the run has not been scored.

    shortcut: assumes the harness writes red2fix.<run-id>.json in the repo root; confirm after the first score.sh.
    """
    path = (root or ROOT) / f"red2fix.{run_id}.json"
    return set(json.loads(path.read_text()).get("resolved_ids", [])) if path.exists() else None
