"""Red2Fix review: a pull request (unified diff) in, a verdict backed by executed tests out.

Usage: python -m agent.review --repo DIR --spec FILE --patch FILE --out DIR [--number N] [--work DIR]

The tree stays at base until APPLY_PR, so LOCALIZE and REPRODUCE only ever see the changed paths.
"""

import argparse
import json
import re
import shutil
import time
import traceback
from collections import Counter
from pathlib import Path

import config
from agent import guards, pr_context, prompts, tools
from agent import policy as policies
from agent.llm import LLM, BudgetExceeded
from agent.main import ARTIFACTS, Abort, Run, check, fix, git, localize, parse_json, prepare, reproduce

SEVERITIES = ("blocker", "warning", "info")
LABELS = {
    "proven": "✅ Proven", "needs_review": "🔶 Needs review", "unproven": "⚠️ Unproven",
    "doesnt_fix": "❌ Doesn't fix", "breaks_tests": "❌ Breaks tests", "error": "⛔ Error",
}
TEST_RULE = "No weakened, skipped, xfailed or deleted tests"
UNRELATED_RULE = "No changes unrelated to the spec"
SECTION = re.compile(r"^_+ (.*\S) _+$")  # "____ test_x ____"; long names get a single "_" each side
LOCATION = re.compile(r"^\S+?\.py:\d+:")  # "path:line: in func" per frame, "path:line: Exc" on the last
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def severity(finding, policy):
    """The finding's severity, raised to blocker for a quoted unrelated change to non-test code when
    policy unrelated_change = "blocker": the tests only prove the spec's claim, and the reviewer's own
    severity for such a change proved unreliable (inject2).
    """
    path = finding.get("diff_file") or ""
    changed = any(l.startswith(("+", "-")) for l in (finding.get("quote") or "").strip().splitlines())
    if (
        policy.get("unrelated_change", "blocker") != "warning"  # a typo fails closed
        and (finding.get("rule") or "").strip().lower() == UNRELATED_RULE.lower()
        and path.endswith(".py") and not guards.is_test_file(path) and changed
    ):
        return "blocker"
    return finding.get("severity")


def failure_signature(out):
    """(failed test ids, per failure section: its name, every traceback location and every executing source
    line, the ones pytest marks with ">") from pytest output."""
    failed, sections = set(), []
    for line in ANSI.sub("", out).splitlines():
        if line.startswith(("FAILED ", "ERROR ")):
            failed.add(line.split(" - ")[0])
        elif (m := SECTION.match(line)) and m.group(1).strip("_ "):
            sections.append([m.group(1)])
        elif sections and (LOCATION.match(line) or line.startswith(">")):
            sections[-1].append(line.rstrip())
    return failed, sections


def same_failure(base_out, head_out):
    """True when head fails the same tests through the same traceback frames, executing the same source
    lines, with the same exceptions as base. An edit to code the test runs through changes a frame's line
    number or its source line, so this only holds when the test never ran through changed code.
    """
    base = failure_signature(base_out)
    return bool(base[0]) and base == failure_signature(head_out)


def decide(proof, new_failures, findings, restricted_touched, policy, spec_source="spec_file"):
    """(verdict, reason). Proof and regression come from pytest; findings can only lower the verdict.

    proof: "proven" (red on base, green on head), "doesnt_fix", "unreached" (head failed exactly as base
    did), "unproven" or "error".
    """
    timeouts = sorted(f for f in new_failures if f.startswith("<"))
    if proof == "error" or timeouts:
        return "error", ", ".join(timeouts) or "proof could not be computed"
    if new_failures:
        return "breaks_tests", "new failing tests: " + ", ".join(sorted(new_failures))
    if proof == "doesnt_fix":
        return "doesnt_fix", "the repro test still fails with the PR applied"
    if proof == "unreached":
        return "unproven", "the repro test fails the same way on base and head: the test never reached the changed code"
    if proof == "unproven" and policy["require_proof"]:
        return "unproven", "no test showed the claimed behaviour failing on base"
    blockers = [f for f in findings if severity(f, policy) == "blocker"]
    if blockers or restricted_touched:
        why = [f"blocker: {f.get('rule')}" for f in blockers]
        why += [f"restricted path: {p}" for p in restricted_touched]
        return "needs_review", "; ".join(why)
    if proof == "unproven":
        return "unproven", "no failing test; require_proof is off"
    if spec_source == "pr_description":
        # The author wrote both the claim and the fix, so the proof only shows the PR does what it says.
        return "needs_review", "proven against the PR's own description; link an issue for a full ✅"
    return "proven", "red on base, green on head, no new failures, no blockers"


def still_failing(run, baseline):
    """(repro fails, new failing suite tests) at the current tree."""
    code, _ = tools.run_tests(run.root, run.repro)
    return code != 0, tools.failing_tests(run.root, *run.suite, f"--ignore={run.repro}") - baseline


def suggest_fix(run, policy, loc, repro_code, baseline):
    """{"status": "proven" | "failed", "reason"}: the FIX loop on top of the PR head, then CONFIRM from a clean
    head: something fails without the suggestion, and with it the repro passes and nothing new fails.
    Writes suggested_fix.diff when proven. Never raises: a failed suggestion must not change the review.
    """
    run.llm.max_usd = run.llm.spent + policy["suggest_fix_budget_usd"]  # its own cap on top of the review's spend
    run.max_seconds = time.monotonic() - run.start + config.SUGGEST_SECONDS
    try:
        fix(run, loc, repro_code, "", baseline, feedback=check(run, baseline))
        run.phase("CONFIRM")
        diff = tools.git_diff(run.root)
        git(run.root, "reset", "--hard", "-q")
        git(run.root, "clean", "-fdq")
        repro_red, broken = still_failing(run, baseline)
        if not (repro_red or broken):
            raise Abort("confirm_failed: nothing fails on the PR head without the suggestion")
        applied = tools.apply_patch(run.root, diff)
        if applied != "applied":
            raise Abort(f"confirm_failed: {applied}")
        repro_red, broken = still_failing(run, baseline)
        if repro_red or broken:
            raise Abort(f"confirm_failed: with the suggestion, repro {'fails' if repro_red else 'passes'}, "
                        f"new failures: {', '.join(sorted(broken)) or 'none'}")
        run.save("suggested_fix.diff", diff)
        return {"status": "proven", "reason": "repro passes and no new failures with the suggestion"}
    except BudgetExceeded:
        return {"status": "failed", "reason": "suggest_fix_budget_usd"}
    except Abort as e:
        return {"status": "failed", "reason": str(e)}
    except Exception as e:
        traceback.print_exc()
        return {"status": "failed", "reason": f"error:{type(e).__name__}: {e}"}


def changed_paths(diff):
    """Every path a diff touches, including created and deleted files."""
    return sorted({p for l in diff.splitlines() if l.startswith(("--- ", "+++ ")) and (p := guards._diff_path(l))})


def guard_findings(patch, repro):
    """Anti-cheat checks as findings: human PRs legitimately edit tests, so only deletions block."""
    findings = []
    for v in guards.check_patch(patch, repro):
        severity = "warning" if v.startswith("adds forbidden construct") else "info"
        findings.append({"rule": TEST_RULE, "severity": severity, "file": "", "line": 0, "note": v})
    for v in guards.deleted_tests(patch):
        findings.append({"rule": TEST_RULE, "severity": "blocker", "file": "", "line": 0, "note": v})
    return findings


def valid_review(data):
    return (
        isinstance(data, dict)
        and isinstance(data.get("findings"), list)
        and all(isinstance(f, dict) and f.get("severity") in SEVERITIES for f in data["findings"])
    )


def diff_sections(diff):
    """{path: that file's hunks}, so a quote can be traced to the file it really comes from."""
    sections, old, path = {}, None, None
    for line in diff.splitlines(keepends=True):
        if line.startswith("--- "):
            old = guards._diff_path(line)
        elif line.startswith("+++ "):
            path = guards._diff_path(line) or old
            sections.setdefault(path, "")
        elif path:
            sections[path] += line
    return sections


def grounded(findings, patch):
    """(kept, dropped): a finding must quote text that is really in the diff, so invented problems fall out.

    Kept findings get "diff_file", the file the quote was found in (not the file the model named).
    """
    kept, dropped = [], []
    sections = diff_sections(patch)
    for f in findings:
        quote = f.get("quote")
        ok = isinstance(quote, str) and quote.strip() and quote.strip() in patch
        if ok:
            f["diff_file"] = next((p for p, text in sections.items() if quote.strip() in text), "")
        (kept if ok else dropped).append(f)
    return kept, dropped


def review_diff(run, policy, patch, evidence):
    run.phase("REVIEW")
    rubric = "\n".join(f"- {r}" for r in policy["rubric"])
    user = (
        f"Rubric:\n{rubric}\n\nEvidence (computed by running tests):\n{evidence}\n\n"
        f"<spec>\n{run.issue}\n</spec>\n\n<diff>\n{patch}\n</diff>"
    )
    messages = [{"role": "system", "content": prompts.REVIEW}, {"role": "user", "content": user}]
    for _ in range(2):
        text = run.llm.chat("review", messages).choices[0].message.content or ""
        data = parse_json(text)
        if valid_review(data):
            data["findings"], data["dropped"] = grounded(data["findings"], patch)
            return data
        messages += [
            {"role": "assistant", "content": text},
            {"role": "user", "content": "That was not valid JSON in the required schema. Reply with only the JSON object."},
        ]
    # Fail closed: a review we can't read blocks the merge.
    return {"summary": "", "findings": [{"rule": "review output invalid", "severity": "blocker", "file": "", "line": 0,
                                         "note": "the review model returned invalid JSON twice"}]}


def last_line(text):
    return text.strip().splitlines()[-1] if text.strip() else ""


def model_calls(out):
    path = out / "ledger.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []
    names = {v: k for k, v in config.MODELS.items()}
    calls = Counter(names.get(r["model"], r["model"]) for r in rows)
    return {k: calls[k] for k in ("ultra", "super", "nano")}


def cell(text):
    return str(text or "").replace("|", "\\|").replace("\n", " ")


def render_md(rv, out):
    """The PR comment."""
    p = rv["proof"]
    lines = [f"## Red2Fix: {LABELS[rv['verdict']]}", "", f"**Why:** {rv['verdict_reason']}", ""]
    if rv["claim"]:
        lines += [f"**Claim:** {rv['claim']}", ""]
    lines += [
        "**Evidence**",
        f"- Base (must fail): {p['base'] or '—'}",
        f"- Head (must pass): {p['head'] or '—'}",
        f"- New failing tests: {', '.join(rv['suite']['new_failures']) or 'none'}",
    ]
    if rv["restricted_paths_touched"]:
        lines.append(f"- Restricted paths touched: {', '.join(rv['restricted_paths_touched'])}")
    if rv["summary"]:
        lines += ["", f"**Review:** {rv['summary']}"]
    if rv["findings"]:
        lines += ["", "| Severity | Rule | Where | Note |", "|---|---|---|---|"]
        for f in rv["findings"]:
            where = f"{f.get('file')}:{f.get('line')}" if f.get("file") else ""
            lines.append(f"| {cell(f.get('severity'))} | {cell(f.get('rule'))} | {cell(where)} | {cell(f.get('note'))} |")
    mix = " / ".join(f"{k.title()} {n}" for k, n in rv["calls"].items() if n) or "no model calls"
    lines += ["", f"**Cost:** ${rv['cost_usd']:.2f} · {int(rv['seconds'])}s · {mix}"]
    suggestion = out / "suggested_fix.diff"
    if (rv.get("suggested_fix") or {}).get("status") == "proven" and suggestion.exists():
        lines += ["", "**Suggested fix (proven)**: the repro test passes and no existing test breaks with this on top of "
                  "the PR. It does not change the verdict and was not pushed.", "",
                  "```diff", suggestion.read_text().rstrip(), "```"]
    repro = out / "repro_test.py"
    if repro.exists():
        lines += ["", "<details><summary>Repro test</summary>", "", "```python", repro.read_text().rstrip(), "```", "", "</details>"]
    return "\n".join(lines) + "\n"


def run_review(repo, spec_path, patch_path, out, number, work, llm=None, max_seconds=config.MAX_SECONDS,
               spec_source="spec_file", head_sha=None, suite=(), repro_steps=12):
    out.mkdir(parents=True, exist_ok=True)
    for name in ARTIFACTS:
        (out / name).unlink(missing_ok=True)
    shutil.rmtree(out / "repro_attempts", ignore_errors=True)
    run = Run(work, "", number, out, llm, max_seconds=max_seconds)
    repro_code = loc = None
    run.repro = f"tests/test_repro_pr_{number}.py"
    run.repro_steps = repro_steps
    rv = {
        "verdict": "error", "verdict_reason": None, "claim": "", "summary": "",
        # head_sha comes from the caller (the PR event); a local diff has none.
        "base_sha": None, "head_sha": head_sha, "policy_sha": None, "require_proof": None, "spec_source": spec_source,
        "proof": {"repro_test": None, "base": None, "head": None},
        "suite": {"new_failures": []}, "findings": [], "dropped_findings": [], "restricted_paths_touched": [],
    }
    # Everything that can fail sits inside the try, so review.json and result.json are always written.
    try:
        prepare(Path(repo), work)
        policy = policies.load(work)
        rv["policy_sha"], rv["require_proof"] = policy["sha"], policy["require_proof"]
        run.llm = run.llm or LLM(ledger_path=out / "ledger.jsonl", max_usd=policy["budget_usd"])
        run.issue = Path(spec_path).read_text()
        patch = Path(patch_path).read_text()
        paths = changed_paths(patch)
        rv["restricted_paths_touched"] = policies.restricted(paths, policy["restricted_paths"])
        rv["base_sha"] = git(work, "rev-parse", "HEAD").strip()
        # Regression scope, as in main.run_agent; paths that don't exist on base are dropped.
        suite = run.suite = [s for s in suite if (work / s.split("::")[0]).exists()]

        run.phase("TRIAGE")
        triage = parse_json(run.ask("triage_review", prompts.TRIAGE_REVIEW, f"<spec>\n{run.issue}\n</spec>")) or {}
        rv["claim"] = triage.get("claim", "")
        run.phase("BASELINE")
        baseline = tools.failing_tests(work, *suite)

        proof = "unproven"
        # Only an explicit "no" skips the proof; a garbled Nano reply should not.
        if triage.get("testable") is False:
            rv["proof"]["base"] = f"not testable: {triage.get('reason', '')}"
        else:
            listing = "\n".join(paths)
            # Interface visible, implementation hidden: paths, signatures and changed-function names only.
            shape, run.new_names = pr_context.interface(work, patch, paths)
            loc = localize(run, f"\n\nFiles changed by the pull request (paths only; the change itself is hidden):\n{listing}{shape}")
            try:
                repro_code, red = reproduce(run, loc, shape + pr_context.related_test_block(work, paths, run.repro))
            except Abort as e:
                if str(e) != "no_repro":
                    raise
                # The last rejected attempt is still on disk; left there it would count as a new failure on head.
                (work / run.repro).unlink(missing_ok=True)
                rv["proof"]["base"] = "no test could be made to fail for the claimed reason"
            else:
                proof = "red"
                rv["proof"].update(repro_test=run.repro, base=f"failed: {last_line(red)}")
                run.phase("COMMIT_REPRO")
                git(work, "add", run.repro)
                git(work, "commit", "-qm", "repro test")

        run.phase("APPLY_PR")
        applied = tools.apply_patch(work, patch)
        if applied != "applied":
            raise Abort(f"patch_does_not_apply: {applied}")
        git(work, "add", "-A")
        git(work, "commit", "-qm", "pr")

        run.phase("HEAD_CHECK")
        if proof == "red":
            code, head_out = tools.run_tests(work, run.repro)
            run.save("head.log", head_out)
            proof = "proven" if code == 0 else "unreached" if same_failure(red, head_out) else "doesnt_fix"
            rv["proof"]["head"] = f"{'passed' if code == 0 else f'failed (exit {code})'}: {last_line(head_out)}"
        # The repro is judged above; inside the suite a wrong fix would show up as breaks_tests instead.
        head = tools.failing_tests(work, *suite, f"--ignore={run.repro}")
        # Sentinels (suite timed out, no report) are kept even if base had them too: they must not cancel out.
        new_failures = (head - baseline) | {f for f in head if f.startswith("<")}
        rv["suite"]["new_failures"] = sorted(new_failures)

        rv["findings"] = guard_findings(patch, run.repro)
        evidence = (
            f"Proof: {proof} (base: {rv['proof']['base']}; head: {rv['proof']['head'] or 'not run'})\n"
            f"New failing tests: {', '.join(rv['suite']['new_failures']) or 'none'}\n"
            f"Restricted paths touched: {', '.join(rv['restricted_paths_touched']) or 'none'}"
        )
        review = review_diff(run, policy, patch, evidence)
        rv["summary"] = review.get("summary", "")
        rv["findings"] += review["findings"]
        rv["dropped_findings"] = review.get("dropped", [])

        run.phase("VERDICT")
        rv["proof"]["result"] = proof  # lets bench/report_review.py recompute verdicts under other policies
        rv["verdict"], rv["verdict_reason"] = decide(
            proof, new_failures, rv["findings"], rv["restricted_paths_touched"], policy, spec_source)
        # Only with a repro to fix against (unproven has none). The verdict is final before this runs.
        if policy["suggest_fix"] and rv["verdict"] in ("doesnt_fix", "breaks_tests") and repro_code:
            rv["suggested_fix"] = suggest_fix(run, policy, loc, repro_code, baseline)
        run.phase("DONE")
    except Abort as e:
        rv.update(verdict="error", verdict_reason=str(e))
    except BudgetExceeded:
        rv.update(verdict="error", verdict_reason="budget_usd")
    except Exception as e:
        traceback.print_exc()
        rv.update(verdict="error", verdict_reason=f"error:{type(e).__name__}: {e}")
    finally:
        spent = run.llm.spent if run.llm else 0.0
        rv.update(cost_usd=round(spent, 6), seconds=round(time.monotonic() - run.start, 1), calls=model_calls(out))
        ok = rv["verdict"] != "error"
        run.result.update(
            status="succeeded" if ok else "aborted", abort_reason=None if ok else rv["verdict_reason"],
            verdict=rv["verdict"], cost_usd=rv["cost_usd"], seconds=rv["seconds"],
        )
        run.save("review.json", json.dumps(rv, indent=2))
        run.save("result.json", json.dumps(run.result, indent=2))
        run.save("review.md", render_md(rv, out))
        run.event(ev="end", status=run.result["status"], abort_reason=run.result["abort_reason"], verdict=rv["verdict"])
        print("VERDICT", rv["verdict"], "-", rv["verdict_reason"], flush=True)
    return rv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="base checkout")
    ap.add_argument("--spec", required=True, help="linked issue or PR description")
    ap.add_argument("--patch", required=True, help="the PR as a unified diff against --repo")
    ap.add_argument("--out", required=True)
    ap.add_argument("--number", type=int, default=0)
    ap.add_argument("--work", default="/work/repo")
    ap.add_argument("--max-seconds", type=int, default=config.MAX_SECONDS)
    ap.add_argument("--spec-source", default="spec_file", help='e.g. "issue#12" or "pr_description"')
    ap.add_argument("--head-sha", help="the PR head commit being reviewed")
    ap.add_argument("--suite", nargs="*", default=[], help="test files for the regression check (default: whole suite)")
    ap.add_argument("--repro-steps", type=int, default=12, help="tool steps per REPRODUCE attempt")
    a = ap.parse_args()
    rv = run_review(a.repo, a.spec, a.patch, Path(a.out), a.number, Path(a.work), max_seconds=a.max_seconds,
                    spec_source=a.spec_source, head_sha=a.head_sha, suite=a.suite, repro_steps=a.repro_steps)
    raise SystemExit(1 if rv["verdict"] == "error" else 0)


if __name__ == "__main__":
    main()
