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
    assert "## Fixes #1: div crashes on zero" in (out / "summary.md").read_text()
    assert json.loads((out / "result.json").read_text())["status"] == "succeeded"
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
