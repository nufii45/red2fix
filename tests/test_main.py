import json
from types import SimpleNamespace

import pytest

from agent import main, tools

REPRO = "```python\nfrom mathlib import div\n\n\ndef test_repro():\n    assert div(1, 0) is None\n```"
GOOD_FIX = ("mathlib.py", "    return a / b", "    if b == 0:\n        return None\n    return a / b")


def reply(content="", calls=()):
    tool_calls = [
        SimpleNamespace(id=f"c{i}", function=SimpleNamespace(name=name, arguments=json.dumps(args)))
        for i, (name, args) in enumerate(calls)
    ]
    msg = SimpleNamespace(content=content, tool_calls=tool_calls or None)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def edit(path, old, new):
    return reply(calls=[("edit_file", {"path": path, "old": old, "new": new})])


class FakeLLM:
    """Scripted replies per phase; the last reply of a phase repeats once the script runs out."""

    def __init__(self, **script):
        self.script = {k: list(v) for k, v in script.items()}
        self.seen = []
        self.spent = 0.0

    def chat(self, phase, messages, model_key=None, **kw):
        self.seen.append((phase, messages))
        queue = self.script[phase]
        return queue.pop(0) if len(queue) > 1 else queue[0]


def base_script(**over):
    s = dict(
        triage=[reply('{"in_scope": true}')],
        localize=[reply('{"files": ["mathlib.py"], "hypothesis": "div does not handle b == 0"}')],
        reproduce=[reply(REPRO)],
        verify_red=[reply('{"matches": true}')],
        fix=[edit(*GOOD_FIX), reply("guarded zero division")],
        escalate=[reply("new plan")],
        summarize=[reply("div now returns None for a zero divisor.")],
    )
    s.update(over)
    return s


def run(buggy_repo, tmp_path, llm):
    return main.run_agent(buggy_repo, write_issue(tmp_path), tmp_path / "out", 1, tmp_path / "work", llm=llm)


def write_issue(tmp_path):
    p = tmp_path / "issue.md"
    p.write_text("# div crashes on zero\n\ndiv(1, 0) raises ZeroDivisionError; it should return None.\n")
    return p


def test_happy_path(buggy_repo, tmp_path):
    result = run(buggy_repo, tmp_path, FakeLLM(**base_script()))

    assert result["status"] == "succeeded", result
    assert result["iterations"] == 1
    out = tmp_path / "out"
    assert "ZeroDivisionError" in (out / "red.log").read_text()
    assert "1 passed" in (out / "green.log").read_text()
    assert "+    if b == 0:" in (out / "patch.diff").read_text()
    assert "test_repro" not in (out / "patch.diff").read_text()
    summary = (out / "summary.md").read_text()
    assert "## Fixes #1: div crashes on zero" in summary
    assert "- Before fix: ❌ ZeroDivisionError" in summary
    assert "- After fix:  ✅ 1 passed" in summary
    assert json.loads((out / "result.json").read_text())["status"] == "succeeded"
    events = [json.loads(l) for l in (out / "events.jsonl").read_text().splitlines()]
    assert [e["name"] for e in events if e["ev"] == "phase"][:3] == ["TRIAGE", "BASELINE", "LOCALIZE"]
    assert events[-1] == {**events[-1], "ev": "end", "status": "succeeded"}
    # The input repo is never modified.
    assert "return a / b" in (buggy_repo / "mathlib.py").read_text()
    assert "if b == 0" not in (buggy_repo / "mathlib.py").read_text()


def test_repro_that_passes_is_rejected(buggy_repo, tmp_path):
    passing = reply("```python\ndef test_repro():\n    assert True\n```")
    llm = FakeLLM(**base_script(reproduce=[passing]))

    result = run(buggy_repo, tmp_path, llm)

    assert result["abort_reason"] == "no_repro"
    assert not any(phase == "verify_red" for phase, _ in llm.seen)


def test_out_of_scope_aborts(buggy_repo, tmp_path):
    llm = FakeLLM(**base_script(triage=[reply('{"in_scope": false, "reason": "UI bug"}')]))
    assert run(buggy_repo, tmp_path, llm)["abort_reason"] == "out_of_scope: UI bug"


def test_editing_tests_is_refused(buggy_repo, tmp_path, monkeypatch):
    monkeypatch.setattr(main.config, "MAX_FIX_ITERS", 4)
    cheat = edit("tests/test_repro_issue_1.py", "assert div(1, 0) is None", "assert True")
    llm = FakeLLM(**base_script(fix=[cheat, reply("done")]))

    result = run(buggy_repo, tmp_path, llm)

    assert result["abort_reason"] == "max_iterations"
    assert result["escalations"] == 1
    tool_msgs = [m for phase, msgs in llm.seen if phase == "fix" for m in msgs if m.get("role") == "tool"]
    assert "editing test files is not allowed" in tool_msgs[0]["content"]


def test_broken_suite_is_fed_back(buggy_repo, tmp_path):
    breaks_test_div = edit("mathlib.py", "    return a / b", "    return None")
    proper = edit("mathlib.py", "    return None", "    if b == 0:\n        return None\n    return a / b")
    llm = FakeLLM(**base_script(fix=[breaks_test_div, reply("done"), proper, reply("done")]))

    result = run(buggy_repo, tmp_path, llm)

    assert result["status"] == "succeeded", result
    assert result["iterations"] == 2
    second_fix_prompt = [msgs[1]["content"] for phase, msgs in llm.seen if phase == "fix"][2]
    assert "broke existing tests" in second_fix_prompt and "test_div" in second_fix_prompt


def test_edit_file(buggy_repo):
    assert tools.edit_file(buggy_repo, "mathlib.py", "a / b", "a // b") == "edited mathlib.py"
    assert "matched 0 times" in tools.edit_file(buggy_repo, "mathlib.py", "nope", "x")


def test_failing_tests(buggy_repo):
    assert tools.failing_tests(buggy_repo) == {"test_mathlib::test_div_zero"}


@pytest.mark.parametrize("text,expected", [
    ('sure: {"a": 1} done', {"a": 1}),
    ("```json\n{\"a\": [1, 2]}\n```", {"a": [1, 2]}),
    ("no json here", None),
    ("{broken", None),
])
def test_parse_json(text, expected):
    assert main.parse_json(text) == expected


def test_repro_with_a_passing_test_is_rejected(buggy_repo, tmp_path):
    mixed = reply(
        "```python\nfrom mathlib import div\n\n\n"
        "def test_buggy_behaviour():\n    assert div(6, 3) == 2\n\n\n"
        "def test_repro():\n    assert div(1, 0) is None\n```"
    )
    llm = FakeLLM(**base_script(reproduce=[mixed, reply(REPRO)]))

    result = run(buggy_repo, tmp_path, llm)

    assert result["status"] == "succeeded", result
    second_prompt = [msgs[1]["content"] for phase, msgs in llm.seen if phase == "reproduce"][1]
    assert "1 of its tests already pass" in second_prompt


def test_rerun_clears_old_artifacts(buggy_repo, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "ledger.jsonl").write_text('{"stale": true}\n')
    (out / "patch.diff").write_text("stale")
    (out / "events.jsonl").write_text('{"stale": true}\n')
    llm = FakeLLM(**base_script(triage=[reply('{"in_scope": false, "reason": "x"}')]))

    run(buggy_repo, tmp_path, llm)

    assert not (out / "ledger.jsonl").exists() and not (out / "patch.diff").exists()
    assert "stale" not in (out / "events.jsonl").read_text()


def test_in_place_run_edits_the_repo(buggy_repo, tmp_path_factory):
    # Output must live outside the repo: CONFIRM's `git clean` would delete it.
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    result = main.run_agent(buggy_repo, write_issue(elsewhere), elsewhere / "out", 1, buggy_repo, llm=FakeLLM(**base_script()))

    assert result["status"] == "succeeded", result
    assert "if b == 0" in (buggy_repo / "mathlib.py").read_text()


def test_suite_scopes_the_regression_check(buggy_repo, tmp_path):
    # test_div is outside the suite, so breaking it goes unnoticed: the scope is honoured.
    breaks_test_div = edit("mathlib.py", "    return a / b", "    return None")
    llm = FakeLLM(**base_script(fix=[breaks_test_div, reply("done")]))

    result = main.run_agent(
        buggy_repo, write_issue(tmp_path), tmp_path / "out", 1, tmp_path / "work", llm=llm,
        suite=["test_mathlib.py::test_div_zero", "tests/added_by_hidden_patch.py"],
    )

    assert result["status"] == "succeeded", result
    assert result["iterations"] == 1


def test_step_limit_asks_for_submit_and_falls_back_to_text(buggy_repo, tmp_path, monkeypatch):
    explore = reply(calls=[("list_files", {})])
    llm = FakeLLM(**base_script(reproduce=[explore] * 2 + [reply(REPRO)]))
    run_ = main.Run(buggy_repo, "issue", 1, tmp_path, llm)
    run_.repro_steps = 2
    out = run_.tool_loop("reproduce", "s", "u", main.READ + ["submit_test"], 2, submit="submit_test")
    assert out == REPRO
    last_phase, last_msgs = llm.seen[-1]
    assert "call submit_test now" in last_msgs[-1]["content"]


def test_bad_submit_args_get_a_clear_error(buggy_repo, tmp_path):
    bad = reply(calls=[("submit_test", {"code": "x"})])
    llm = FakeLLM(reproduce=[bad, reply("done")])
    run_ = main.Run(buggy_repo, "issue", 1, tmp_path, llm)
    run_.tool_loop("reproduce", "s", "u", main.READ + ["submit_test"], 3, submit="submit_test")
    tool_msg = [m for m in llm.seen[-1][1] if m.get("role") == "tool"][0]["content"]
    assert 'call submit_test with {"content"' in tool_msg


def red(buggy_repo, body):
    """Real pytest output for a repro file with this body (imports div from the fixture's mathlib)."""
    path = "tests/test_repro_issue_1.py"
    tools.write_file(buggy_repo, path, "import json, io, pytest\nfrom mathlib import div\n\n" + body)
    code, out = tools.run_tests(buggy_repo, path)
    assert code == 1, out
    return out, path


@pytest.mark.parametrize("body", [
    "def test_r():\n    assert div(6, 3) == 3\n",                                    # assertion: fine
    "def test_r():\n    with pytest.raises(ValueError):\n        div(6, 3)\n",          # DID NOT RAISE: fine
    "def test_r():\n    div(1, 0)\n",                                                  # raised in the code: fine
])
def test_red_from_the_code_is_not_broken(buggy_repo, body):
    out, path = red(buggy_repo, body)
    assert main.broken_test(out, path) is None


def test_exception_inside_the_test_is_broken(buggy_repo):
    out, path = red(buggy_repo, "def test_r():\n    json.dump({'a': 1}, io.BytesIO())\n    assert div(1, 0) is None\n")
    reason = main.broken_test(out, path)
    assert reason.startswith("the test is broken, not the code: TypeError raised in the test itself")


def test_missing_new_api_on_base_is_the_expected_red(buggy_repo):
    out, path = red(buggy_repo, "def test_r():\n    assert div(1, 0, default=None) is None\n")
    assert main.broken_test(out, path, {"default"}) is None       # the PR adds `default`
    assert main.broken_test(out, path, {"other"}) is not None     # not something the PR adds


def test_broken_test_is_rejected_before_verify_red(buggy_repo, tmp_path):
    broken = reply("```python\nimport io, json\nfrom mathlib import div\n\n\ndef test_repro():\n"
                   "    json.dump({'a': 1}, io.BytesIO())\n    assert div(1, 0) is None\n```")
    llm = FakeLLM(**base_script(reproduce=[broken, reply(REPRO)]))
    result = run(buggy_repo, tmp_path, llm)
    assert result["status"] == "succeeded", result
    assert sum(phase == "verify_red" for phase, _ in llm.seen) == 1  # only the good attempt reached the model
    assert "the test is broken" in (tmp_path / "out" / "repro_attempts" / "1.log").read_text()


def test_verify_red_judges_each_test(buggy_repo, tmp_path):
    one_wrong = reply('{"tests": [{"name": "test_repro", "matches": true}, {"name": "test_x", "matches": false, '
                      '"reason": "wrong setup"}], "matches": true}')
    llm = FakeLLM(**base_script(verify_red=[one_wrong, reply('{"matches": true}')]))
    result = run(buggy_repo, tmp_path, llm)
    assert result["status"] == "succeeded"
    assert "test_x: wrong setup" in (tmp_path / "out" / "repro_attempts" / "1.log").read_text()


def test_step_budget_is_shown_and_only_submit_is_offered_at_the_end(buggy_repo, tmp_path):
    explore = reply(calls=[("list_files", {})])
    seen_tools = []
    llm = FakeLLM(reproduce=[explore] * 5 + [reply(REPRO)])
    chat = llm.chat
    llm.chat = lambda phase, messages, **kw: seen_tools.append([t["function"]["name"] for t in kw.get("tools", [])]) or chat(phase, messages, **kw)
    run_ = main.Run(buggy_repo, "issue", 1, tmp_path, llm)
    run_.tool_loop("reproduce", "s", "u", main.READ + ["submit_test"], 5, submit="submit_test")
    assert seen_tools[0] == main.READ + ["submit_test"] and seen_tools[3] == seen_tools[4] == ["submit_test"]
    tool_msgs = [m["content"] for m in llm.seen[-1][1] if m.get("role") == "tool"]
    assert "[4 tool steps left." in tool_msgs[0] and "call submit_test now" in tool_msgs[-1]
