"""Red2Fix agent: issue in, red→green proven fix out. Runs inside the sandbox container.

Usage: python -m agent.main --repo DIR --issue FILE --out DIR [--number N] [--work DIR]
"""

import argparse
import json
import re
import shutil
import subprocess
import time
import traceback
from collections import Counter
from pathlib import Path

import config
from agent import guards, prompts, tools
from agent.llm import LLM, BudgetExceeded

READ = ["list_files", "read_file", "grep"]
EDIT = READ + ["edit_file", "write_file", "run_tests"]
MAX_REPRO_ATTEMPTS = 3
ESCALATE_EVERY = 3


class Abort(Exception):
    pass


def parse_json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def extract_code(text):
    blocks = re.findall(r"```(?:python)?\n(.*?)```", text or "", re.S)
    return blocks[-1] if blocks else (text or "")


def git(root, *args):
    return subprocess.run(
        ["git", "-c", "user.email=agent@red2fix", "-c", "user.name=red2fix", *args],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout


class Run:
    def __init__(self, root, issue, number, out, llm):
        self.root, self.issue, self.number, self.out, self.llm = root, issue, number, out, llm
        self.repro = f"tests/test_repro_issue_{number}.py"
        self.start = time.monotonic()
        self.result = {"status": "running", "phase": None, "abort_reason": None, "iterations": 0, "escalations": 0}

    def phase(self, name):
        self.result["phase"] = name
        print(f"PHASE {name}", flush=True)
        self.check_time()

    def check_time(self):
        if time.monotonic() - self.start > config.MAX_SECONDS:
            raise Abort("timeout")

    def ask(self, phase, system, user, **kw):
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        return self.llm.chat(phase, messages, **kw).choices[0].message.content or ""

    def save(self, name, text):
        (self.out / name).write_text(text)

    def tool_loop(self, phase, system, user, allow, max_steps, protect_tests=False):
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        specs = [tools.SPECS[n] for n in allow]
        for _ in range(max_steps):
            self.check_time()
            msg = self.llm.chat(phase, messages, tools=specs).choices[0].message
            if not msg.tool_calls:
                return msg.content or ""
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = None
                if isinstance(args, dict):
                    out = tools.call(self.root, tc.function.name, args, allow, protect_tests)
                else:
                    out = "error: tool arguments must be a JSON object"
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})
        messages.append({"role": "user", "content": "Step limit reached. Give your final answer now, without tools."})
        return self.llm.chat(phase, messages).choices[0].message.content or ""


def triage(run):
    run.phase("TRIAGE")
    t = parse_json(run.ask("triage", prompts.TRIAGE, run.issue)) or {}
    # Only an explicit "no" aborts; a garbled Nano reply should not end the run.
    if t.get("in_scope") is False:
        raise Abort(f"out_of_scope: {t.get('reason', '')}")


def localize(run):
    run.phase("LOCALIZE")
    user = f"Issue:\n{run.issue}\n\nRepository files:\n{tools.list_files(run.root)}"
    reply = run.tool_loop("localize", prompts.LOCALIZE, user, READ, max_steps=12)
    return parse_json(reply) or {"hypothesis": reply}


def reproduce(run, loc):
    feedback = ""
    for _ in range(MAX_REPRO_ATTEMPTS):
        run.phase("REPRODUCE")
        user = f"Issue:\n{run.issue}\n\nLocalization:\n{json.dumps(loc)}\n\nWrite the file {run.repro}.{feedback}"
        code = extract_code(run.tool_loop("reproduce", prompts.REPRODUCE, user, READ, max_steps=8))
        tools.write_file(run.root, run.repro, code)

        run.phase("VERIFY_RED")
        exit_code, out = tools.run_tests(run.root, run.repro)
        # Exit 1 = tests ran and failed; 0 = passed, 2/4/5 = collection or usage errors.
        if exit_code != 1:
            feedback = f"\n\nYour previous test did not fail as required (pytest exit {exit_code}):\n{code}\nOutput:\n{out}"
            continue
        verdict = parse_json(run.ask("verify_red", prompts.VERIFY_RED, f"Issue:\n{run.issue}\n\nTest:\n{code}\n\nOutput:\n{out}")) or {}
        if verdict.get("matches") is False:
            feedback = f"\n\nYour previous test failed for the wrong reason ({verdict.get('reason', '')}):\n{code}\nOutput:\n{out}"
            continue
        run.save("repro_test.py", code)
        run.save("red.log", out)
        return code, out
    raise Abort("no_repro")


def check(run, baseline):
    """None if the current change is acceptable, else feedback for the next fix iteration."""
    code, out = tools.run_tests(run.root, run.repro)
    if code != 0:
        return f"The reproduction test still fails:\n{out}"
    violations = guards.check_patch(tools.git_diff(run.root), run.repro)
    if violations:
        return "Your change was rejected:\n" + "\n".join(violations)
    broken = tools.failing_tests(run.root) - baseline
    if broken:
        return "The reproduction test passes, but your change broke existing tests:\n" + "\n".join(sorted(broken))
    return None


def fix(run, loc, repro_code, red_out, baseline):
    hypothesis = loc.get("hypothesis", "")
    feedback = f"The reproduction test currently fails:\n{red_out}"
    history = []
    for i in range(1, config.MAX_FIX_ITERS + 1):
        run.result["iterations"] = i
        run.phase("FIX")
        user = (
            f"Issue:\n{run.issue}\n\nRoot-cause hypothesis:\n{hypothesis}\n\n"
            f"Reproduction test ({run.repro}):\n{repro_code}\n\n"
            f"Current diff:\n{tools.git_diff(run.root) or '(none)'}\n\n{feedback}"
        )
        run.tool_loop("fix", prompts.FIX, user, EDIT, max_steps=15, protect_tests=True)

        run.phase("CHECK")
        feedback = check(run, baseline)
        if feedback is None:
            return
        history.append(f"Attempt {i}:\n{tools.git_diff(run.root)}\nResult: {feedback[:2000]}")

        if i % ESCALATE_EVERY == 0 and run.result["escalations"] < config.MAX_ESCALATIONS and i < config.MAX_FIX_ITERS:
            run.phase("ESCALATE")
            hypothesis = run.ask(
                "escalate", prompts.ESCALATE,
                f"Issue:\n{run.issue}\n\nOld hypothesis:\n{hypothesis}\n\nHistory:\n" + "\n\n".join(history[-ESCALATE_EVERY:]),
            )
            run.result["escalations"] += 1
            # The old approach was wrong: start the next attempt from the clean repro commit.
            git(run.root, "reset", "--hard", "-q")
            git(run.root, "clean", "-fdq")
    raise Abort("max_iterations")


def confirm(run):
    """Re-prove red→green: the repro fails without the patch and passes with it."""
    run.phase("CONFIRM")
    diff = tools.git_diff(run.root)
    git(run.root, "reset", "--hard", "-q")
    git(run.root, "clean", "-fdq")
    code, out = tools.run_tests(run.root, run.repro)
    if code != 1:
        raise Abort(f"confirm_failed: repro exit {code} without the fix")
    applied = tools.apply_patch(run.root, diff)
    if applied != "applied":
        raise Abort(f"confirm_failed: {applied}")
    code, green = tools.run_tests(run.root, run.repro)
    if code != 0:
        raise Abort(f"confirm_failed: repro exit {code} with the fix")
    _, suite = tools.run_tests(run.root)
    run.save("patch.diff", diff)
    run.save("green.log", f"{green}\n\n--- full suite ---\n{suite}")
    return diff, green, suite


def summarize(run, loc, red_out, diff, suite):
    run.phase("SUMMARIZE")
    title = run.issue.strip().splitlines()[0].lstrip("# ").strip()
    try:
        root_cause = run.ask("summarize", prompts.ROOT_CAUSE, f"Issue:\n{run.issue}\n\nHypothesis:\n{loc.get('hypothesis', '')}\n\nDiff:\n{diff}")
    except Exception as e:  # the fix is already proven; a failed summary (even over budget) should not fail the run
        root_cause = f"(summary unavailable: {e})"
    red_line = next((l for l in red_out.splitlines() if l.startswith("E ")), red_out.strip().splitlines()[-1])
    suite_line = suite.strip().splitlines()[-1] if suite.strip() else ""
    rows = [json.loads(l) for l in (run.out / "ledger.jsonl").read_text().splitlines()] if (run.out / "ledger.jsonl").exists() else []
    names = {v: k for k, v in config.MODELS.items()}
    calls = Counter(names.get(r["model"], r["model"]) for r in rows)
    mix = " / ".join(f"{k.title()} {calls[k]} calls" for k in ("ultra", "super", "nano") if calls[k])
    secs = int(time.monotonic() - run.start)
    run.save("summary.md", (
        f"## Fixes #{run.number}: {title}\n\n**Root cause:** {root_cause.strip()}\n\n"
        f"**Reproduction:** `{run.repro}`\n- Before fix: ❌ {red_line.strip()}\n- After fix:  ✅ 1 passed\n"
        f"- Existing suite: {suite_line}\n\n"
        f"**Cost:** ${run.llm.spent:.2f} · {secs // 60}m{secs % 60:02d}s · {mix}\n"
    ))


def prepare(repo, work):
    """Copy the input repo so it is never modified, and make sure it is a git repo with a commit."""
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(repo, work, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".venv"))
    if not (work / ".git").exists():
        git(work, "init", "-q")
        git(work, "add", "-A")
        git(work, "commit", "-qm", "original")
    with open(work / ".git" / "info" / "exclude", "a") as f:
        f.write("\n__pycache__/\n*.pyc\n.pytest_cache/\n")


def run_agent(repo, issue_path, out, number, work, llm=None):
    out.mkdir(parents=True, exist_ok=True)
    prepare(Path(repo), work)
    llm = llm or LLM(ledger_path=out / "ledger.jsonl")
    run = Run(work, Path(issue_path).read_text(), number, out, llm)
    try:
        triage(run)
        run.phase("BASELINE")
        baseline = tools.failing_tests(work)
        loc = localize(run)
        repro_code, red_out = reproduce(run, loc)
        run.phase("COMMIT_REPRO")
        git(work, "add", run.repro)
        git(work, "commit", "-qm", "repro test")
        fix(run, loc, repro_code, red_out, baseline)
        diff, _, suite = confirm(run)
        summarize(run, loc, red_out, diff, suite)
        run.result["status"] = "succeeded"
        run.phase("DONE")
    except Abort as e:
        run.result.update(status="aborted", abort_reason=str(e))
    except BudgetExceeded:
        run.result.update(status="aborted", abort_reason="budget_usd")
    except Exception as e:
        traceback.print_exc()
        run.result.update(status="aborted", abort_reason=f"error:{type(e).__name__}: {e}")
    finally:
        run.result.update(cost_usd=round(llm.spent, 6), seconds=round(time.monotonic() - run.start, 1))
        run.save("result.json", json.dumps(run.result, indent=2))
        print("RESULT", json.dumps(run.result), flush=True)
    return run.result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--issue", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--number", type=int, default=0)
    ap.add_argument("--work", default="/work/repo")
    a = ap.parse_args()
    result = run_agent(a.repo, a.issue, Path(a.out), a.number, Path(a.work))
    raise SystemExit(0 if result["status"] == "succeeded" else 1)


if __name__ == "__main__":
    main()
