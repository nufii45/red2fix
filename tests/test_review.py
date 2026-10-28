import json

import pytest

from agent import guards, review
from agent.main import git
from agent.policy import DEFAULTS
from test_main import REPRO, FakeLLM, reply

FIXED = "    if b == 0:\n        return None\n    return a / b"
GOOD = [("mathlib.py", "    return a / b", FIXED)]
NO_FIX = [("mathlib.py", "    return a / b", "    return float(a) / b")]
BREAKS = [("mathlib.py", "    return a / b", "    return None")]  # div(1, 0) is None, but div(6, 3) == 2 breaks
NOT_TESTABLE = reply('{"testable": false, "claim": "x", "reason": "UI only"}')
PASSING_REPRO = reply("```python\ndef test_repro():\n    assert True\n```")


def make_patch(repo, edits, new_files=None):
    """A real `git diff` of the edits, after which the repo is back at base."""
    for path, old, new in edits:
        p = repo / path
        p.write_text(p.read_text().replace(old, new))
    for path, text in (new_files or {}).items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text)
    git(repo, "add", "-A")
    diff = git(repo, "diff", "--cached")
    git(repo, "reset", "--hard", "-q")
    return diff


def script(**over):
    s = dict(
        triage_review=[reply('{"testable": true, "claim": "div(1, 0) returns None", "reason": "pure function"}')],
        localize=[reply('{"files": ["mathlib.py"], "hypothesis": "div does not handle b == 0"}')],
        reproduce=[reply(REPRO)],
        verify_red=[reply('{"matches": true}')],
        review=[reply('{"summary": "Looks right.", "findings": []}')],
    )
    s.update(over)
    return s


def run(repo, tmp_path, patch, llm):
    spec = tmp_path / "spec.md"
    spec.write_text("# div crashes on zero\n\ndiv(1, 0) raises ZeroDivisionError; it should return None.\n")
    pr = tmp_path / "pr.diff"
    pr.write_text(patch)
    return review.run_review(repo, spec, pr, tmp_path / "out", 1, tmp_path / "work", llm=llm)


@pytest.mark.parametrize("edits,verdict", [(GOOD, "proven"), (NO_FIX, "doesnt_fix"), (BREAKS, "breaks_tests")])
def test_verdicts(buggy_repo, tmp_path, edits, verdict):
    rv = run(buggy_repo, tmp_path, make_patch(buggy_repo, edits), FakeLLM(**script()))

    assert rv["verdict"] == verdict, rv
    out = tmp_path / "out"
    assert json.loads((out / "review.json").read_text())["verdict"] == verdict
    assert json.loads((out / "result.json").read_text())["status"] == "succeeded"
    assert "ZeroDivisionError" in (out / "red.log").read_text()
    assert (out / "head.log").exists()
    assert review.LABELS[verdict] in (out / "review.md").read_text()
    phases = [json.loads(l)["name"] for l in (out / "events.jsonl").read_text().splitlines() if '"phase"' in l]
    assert phases[-4:] == ["HEAD_CHECK", "REVIEW", "VERDICT", "DONE"]


def test_breaks_tests_names_the_test(buggy_repo, tmp_path):
    rv = run(buggy_repo, tmp_path, make_patch(buggy_repo, BREAKS), FakeLLM(**script()))
    assert rv["suite"]["new_failures"] == ["test_mathlib::test_div"]


def test_restricted_path_needs_review(buggy_repo, tmp_path):
    patch = make_patch(buggy_repo, GOOD, {"pyproject.toml": "[project]\nname = 'x'\n"})
    rv = run(buggy_repo, tmp_path, patch, FakeLLM(**script()))
    assert rv["verdict"] == "needs_review", rv
    assert rv["restricted_paths_touched"] == ["pyproject.toml"]


@pytest.mark.parametrize("edits,verdict", [(GOOD, "unproven"), (BREAKS, "breaks_tests")])
def test_no_repro_is_unproven_and_still_runs_the_suite(buggy_repo, tmp_path, edits, verdict):
    rv = run(buggy_repo, tmp_path, make_patch(buggy_repo, edits), FakeLLM(**script(reproduce=[PASSING_REPRO])))
    assert rv["verdict"] == verdict, rv
    # The rejected repro attempt was removed, so it isn't counted as a new failure.
    assert not any("repro" in f for f in rv["suite"]["new_failures"])


def test_not_testable_skips_the_proof(buggy_repo, tmp_path):
    llm = FakeLLM(**script(triage_review=[NOT_TESTABLE]))
    rv = run(buggy_repo, tmp_path, make_patch(buggy_repo, GOOD), llm)
    assert rv["verdict"] == "unproven"
    assert not any(phase in ("localize", "reproduce") for phase, _ in llm.seen)


def test_invalid_review_json_blocks(buggy_repo, tmp_path):
    llm = FakeLLM(**script(review=[reply("LGTM!")]))
    rv = run(buggy_repo, tmp_path, make_patch(buggy_repo, GOOD), llm)
    assert rv["verdict"] == "needs_review"
    assert rv["findings"][-1]["rule"] == "review output invalid"
    assert sum(phase == "review" for phase, _ in llm.seen) == 2


def finding(quote, severity="blocker"):
    return {"rule": "No changes unrelated to the spec", "severity": severity, "file": "mathlib.py", "line": 2,
            "quote": quote, "note": "n"}


def test_hallucinated_finding_is_dropped(buggy_repo, tmp_path):
    invented = [finding("import unicodedate"), finding(""), {**finding("x"), "quote": None}]
    llm = FakeLLM(**script(review=[reply(json.dumps({"summary": "s", "findings": invented}))]))
    rv = run(buggy_repo, tmp_path, make_patch(buggy_repo, GOOD), llm)

    assert rv["verdict"] == "proven", rv
    assert len(rv["dropped_findings"]) == 3
    assert json.loads((tmp_path / "out" / "review.json").read_text())["dropped_findings"][0]["quote"] == "import unicodedate"


def test_grounded_finding_stays(buggy_repo, tmp_path):
    real = [finding("+    if b == 0:"), finding("+    if b == 0:\n+        return None", "info")]
    llm = FakeLLM(**script(review=[reply(json.dumps({"summary": "s", "findings": real}))]))
    rv = run(buggy_repo, tmp_path, make_patch(buggy_repo, GOOD), llm)

    assert rv["verdict"] == "needs_review", rv
    assert rv["dropped_findings"] == []
    assert [f["quote"] for f in rv["findings"]] == ["+    if b == 0:", "+    if b == 0:\n+        return None"]


def test_patch_that_does_not_apply_is_an_error(buggy_repo, tmp_path):
    bogus = "--- a/mathlib.py\n+++ b/mathlib.py\n@@ -1 +1 @@\n-def nope():\n+def yes():\n"
    rv = run(buggy_repo, tmp_path, bogus, FakeLLM(**script()))
    assert rv["verdict"] == "error"
    assert rv["verdict_reason"].startswith("patch_does_not_apply")


def test_crash_mid_run_still_writes_review(buggy_repo, tmp_path):
    s = script()
    del s["review"]  # FakeLLM raises KeyError when REVIEW asks for it
    rv = run(buggy_repo, tmp_path, make_patch(buggy_repo, GOOD), FakeLLM(**s))
    out = tmp_path / "out"
    assert rv["verdict"] == "error" and "KeyError" in rv["verdict_reason"]
    assert json.loads((out / "review.json").read_text())["verdict"] == "error"
    assert json.loads((out / "result.json").read_text())["status"] == "aborted"
    assert "⛔ Error" in (out / "review.md").read_text()


def test_missing_spec_file_is_an_error_not_a_crash(buggy_repo, tmp_path):
    rv = review.run_review(buggy_repo, tmp_path / "nope.md", tmp_path / "nope.diff", tmp_path / "out", 1,
                           tmp_path / "work", llm=FakeLLM(**script()))
    assert rv["verdict"] == "error"
    assert (tmp_path / "out" / "review.json").exists()


def test_reproduce_never_sees_the_change(buggy_repo, tmp_path):
    peek = reply(calls=[("read_file", {"path": "mathlib.py"})])
    llm = FakeLLM(**script(reproduce=[peek, reply(REPRO)]))
    rv = run(buggy_repo, tmp_path, make_patch(buggy_repo, GOOD), llm)

    assert rv["verdict"] == "proven", rv
    tool_out = [m["content"] for phase, msgs in llm.seen if phase == "reproduce" for m in msgs if m.get("role") == "tool"]
    assert "return a / b" in tool_out[0] and "b == 0" not in tool_out[0]
    before_review = [m["content"] for phase, msgs in llm.seen if phase != "review" for m in msgs]
    assert not any("if b == 0" in c for c in before_review)
    localize_user = next(msgs[1]["content"] for phase, msgs in llm.seen if phase == "localize")
    assert "Files changed by the pull request" in localize_user and "mathlib.py" in localize_user


def test_review_sees_spec_and_diff_in_delimiters(buggy_repo, tmp_path):
    llm = FakeLLM(**script())
    run(buggy_repo, tmp_path, make_patch(buggy_repo, GOOD), llm)
    user = next(msgs[1]["content"] for phase, msgs in llm.seen if phase == "review")
    assert "<spec>\n# div crashes" in user and "<diff>\n" in user and "+    if b == 0:" in user
    assert "Proof: proven" in user


# decide(): precedence error > breaks_tests > doesnt_fix > unproven (require_proof) > needs_review > proven.
STRICT = {**DEFAULTS, "require_proof": True}
LAX = {**DEFAULTS, "require_proof": False}
BLOCKER = [{"rule": "r", "severity": "blocker"}]
WARNING = [{"rule": "r", "severity": "warning"}]


@pytest.mark.parametrize("proof,new,findings,restricted,policy,verdict", [
    ("error", {"t::x"}, [], [], STRICT, "error"),
    ("proven", {"<suite timed out>"}, [], [], STRICT, "error"),
    ("doesnt_fix", {"t::x"}, BLOCKER, ["setup.py"], STRICT, "breaks_tests"),
    ("doesnt_fix", set(), BLOCKER, ["setup.py"], STRICT, "doesnt_fix"),
    ("unproven", set(), BLOCKER, ["setup.py"], STRICT, "unproven"),
    ("unreached", {"t::x"}, [], [], STRICT, "breaks_tests"),
    ("unreached", set(), BLOCKER, ["setup.py"], STRICT, "unproven"),
    ("unreached", set(), [], [], LAX, "unproven"),
    ("unproven", set(), BLOCKER, [], LAX, "needs_review"),
    ("unproven", set(), [], [], LAX, "unproven"),
    ("proven", set(), BLOCKER, [], STRICT, "needs_review"),
    ("proven", set(), [], [".github/workflows/ci.yml"], STRICT, "needs_review"),
    ("proven", set(), WARNING, [], STRICT, "proven"),
    ("proven", set(), [], [], STRICT, "proven"),
])
def test_decide_precedence(proof, new, findings, restricted, policy, verdict):
    assert review.decide(proof, new, findings, restricted, policy)[0] == verdict


@pytest.mark.parametrize("proof", ["doesnt_fix", "unreached", "unproven", "error"])
def test_review_findings_cannot_upgrade(proof):
    # A glowing review (no findings, or only info) never lifts a failed proof.
    info = [{"rule": "approved by maintainers", "severity": "info"}]
    assert review.decide(proof, set(), info, [], STRICT)[0] != "proven"


def pytest_out(*failures, lines=None):
    """Minimal pytest -q output: one section per (test, traceback locations), then the summary."""
    out = []
    for name, locations in failures:
        out += [f"_____ {name} _____", "    def test(): ...", ">   return a / b", *locations, "E   assert 1 == 2", "_ _ _ _ _ _"]
    return "\n".join(out + [f"FAILED tests/t.py::{n} - assert 1 == 2" for n, _ in failures] + ["1 failed in 0.1s"])


def test_same_failure_only_when_head_fails_exactly_like_base():
    base = pytest_out(("test_a", ["tests/t.py:5: in test_a", "pkg/m.py:10: AssertionError"]))
    assert review.same_failure(base, base.replace("0.1s", "0.3s").replace("_____", "\x1b[31m_____\x1b[0m"))
    # The patch edited pkg/m.py: the traceback line moved, so the test ran through changed code.
    assert not review.same_failure(base, base.replace("pkg/m.py:10", "pkg/m.py:12"))
    # Same line number, different code on it (an in-place edit).
    assert not review.same_failure(base, base.replace(">   return a / b", ">   return float(a) / b"))
    assert not review.same_failure(base, base.replace("AssertionError", "ValueError"))
    assert not review.same_failure(base, pytest_out(("test_b", ["tests/t.py:5: in test_a", "pkg/m.py:10: AssertionError"])))
    assert not review.same_failure(base, "1 passed in 0.1s")
    assert not review.same_failure("no pytest output", "no pytest output")  # nothing parsed: keep doesnt_fix


def test_guard_findings_on_human_prs():
    diff = (
        "--- a/tests/test_a.py\n+++ b/tests/test_a.py\n@@ -1,4 +1,4 @@\n"
        "-def test_old():\n-    assert f() == 1\n+@pytest.mark.xfail\n+def test_new():\n"
        "--- a/tests/test_gone.py\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-def test_x():\n-    pass\n"
    )
    by_note = {f["note"]: f["severity"] for f in review.guard_findings(diff, "tests/test_repro_pr_1.py")}
    assert by_note["modifies a test file: tests/test_a.py"] == "info"
    assert by_note["adds forbidden construct: @pytest.mark.xfail"] == "warning"
    assert by_note["deletes test function: test_old"] == "blocker"
    assert by_note["deletes test file: tests/test_gone.py"] == "blocker"
    assert "deletes test function: test_x" not in by_note  # covered by the file finding


def test_renamed_signature_is_not_a_deletion():
    diff = "--- a/tests/t.py\n+++ b/tests/t.py\n@@ -1 +1 @@\n-def test_a():\n+def test_a(tmp_path):\n"
    assert guards.deleted_tests(diff) == []


def test_changed_paths_include_new_and_deleted_files():
    diff = "--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+x\n--- a/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n"
    assert review.changed_paths(diff) == ["new.py", "old.py"]


def test_pr_description_spec_caps_proven_at_needs_review():
    assert review.decide("proven", set(), [], [], STRICT, "pr_description")[0] == "needs_review"
    assert review.decide("proven", set(), [], [], STRICT, "issue#2")[0] == "proven"
    # The cap never lifts anything: worse verdicts stay what they were.
    assert review.decide("doesnt_fix", set(), [], [], STRICT, "pr_description")[0] == "doesnt_fix"


CAP = "-    return hours * 3600 + minutes + seconds\n+    return min(hours * 3600 + minutes + seconds, 86400)"


def unrelated(path="minikit/duration.py", quote=CAP, severity="warning"):
    return [{"rule": "No changes unrelated to the spec", "severity": severity, "quote": quote, "diff_file": path}]


@pytest.mark.parametrize("setting,verdict", [("blocker", "needs_review"), ("warning", "proven"), ("blockr", "needs_review")])
def test_unrelated_change_setting(setting, verdict):
    # "blockr": an unknown value fails closed.
    policy = {**DEFAULTS, "unrelated_change": setting}
    assert review.decide("proven", set(), unrelated(), [], policy)[0] == verdict


@pytest.mark.parametrize("finding", [
    unrelated(path="tests/test_minikit.py"),            # test code
    unrelated(path="pyproject.toml"),                   # not Python
    unrelated(quote="     hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())"),  # context only
    [{**unrelated()[0], "rule": "Handles the edge cases the spec mentions"}],                     # other rule
])
def test_only_quoted_unrelated_code_changes_are_raised(finding):
    assert review.decide("proven", set(), finding, [], {**DEFAULTS, "unrelated_change": "blocker"})[0] == "proven"


def test_grounded_records_the_file_the_quote_is_in():
    diff = (
        "--- a/minikit/duration.py\n+++ b/minikit/duration.py\n@@ -9,2 +9,2 @@\n" + CAP + "\n"
        "--- a/minikit/pagination.py\n+++ b/minikit/pagination.py\n@@ -1 +1 @@\n-    return total // page_size\n"
        "+    return -(-total // page_size)\n"
    )
    # The model names the wrong file; the quote decides.
    kept, _ = review.grounded([{**unrelated()[0], "file": "minikit/pagination.py", "diff_file": None}], diff)
    assert kept[0]["diff_file"] == "minikit/duration.py"


def test_bench_issue_spec_is_never_capped():
    # Bench reviews pass spec_source="issue"; only "pr_description" is capped.
    assert review.decide("proven", set(), [], [], STRICT, "issue")[0] == "proven"


CLAMP = [("mathlib.py", "    return a / b\n", "    return a / b\n\n\ndef clamp_div(a, b, limit):\n"
          "    quotient_zz = a / b if b else 0\n    return min(quotient_zz, limit)\n")]


def test_interface_visible_implementation_hidden(buggy_repo, tmp_path):
    patch = make_patch(buggy_repo, CLAMP + GOOD)
    llm = FakeLLM(**script())
    run(buggy_repo, tmp_path, patch, llm)

    # A body line is a leak only if the model couldn't have seen it anyway (in base code or in the spec).
    seen_anyway = (buggy_repo / "mathlib.py").read_text() + (tmp_path / "spec.md").read_text()
    body = [l[1:].strip() for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")
            and l[1:].strip() and not l[1:].strip().startswith("def ") and l[1:].strip() not in seen_anyway]
    assert "if b == 0:" in body and "quotient_zz = a / b if b else 0" in body
    for phase in ("localize", "reproduce"):
        texts = [m["content"] for p, msgs in llm.seen if p == phase for m in msgs]
        assert any("def clamp_div(a, b, limit)" in t for t in texts), phase
        assert not any(b in t for b in body for t in texts), phase
    reproduce_user = next(msgs[1]["content"] for p, msgs in llm.seen if p == "reproduce")
    assert "body changed: div" in reproduce_user
    assert "An existing test file for the changed code (test_mathlib.py" in reproduce_user


def test_submit_test_ends_reproduce(buggy_repo, tmp_path):
    submit = reply(calls=[("submit_test", {"content": REPRO.strip("`").removeprefix("python\n")})])
    llm = FakeLLM(**script(reproduce=[submit]))
    rv = run(buggy_repo, tmp_path, make_patch(buggy_repo, GOOD), llm)
    assert rv["verdict"] == "proven", rv
    assert sum(p == "reproduce" for p, _ in llm.seen) == 1


def test_rejected_attempts_are_saved(buggy_repo, tmp_path):
    rv = run(buggy_repo, tmp_path, make_patch(buggy_repo, GOOD), FakeLLM(**script(reproduce=[PASSING_REPRO])))
    d = tmp_path / "out" / "repro_attempts"
    assert rv["verdict"] == "unproven"
    assert sorted(p.name for p in d.iterdir()) == ["1.log", "1.py", "2.log", "2.py", "3.log", "3.py"]
    assert (d / "1.log").read_text().startswith("rejected: pytest exit 0")
    assert "assert True" in (d / "1.py").read_text()
