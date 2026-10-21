"""Repo tools for the agent. Every tool takes the repo root and returns truncated text."""

import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import config
from agent import guards

CMD_TIMEOUT = 30
TEST_TIMEOUT = 300


def _truncate(text, keep="tail"):
    lines = text.splitlines()
    n = config.TOOL_OUTPUT_LINES
    if len(lines) <= n:
        return text
    dropped = f"... [{len(lines) - n} lines truncated] ..."
    kept = lines[-n:] if keep == "tail" else lines[:n]
    return "\n".join([dropped, *kept] if keep == "tail" else [*kept, dropped])


def _resolve(root, path):
    root = Path(root).resolve()
    p = (root / path).resolve()
    if not p.is_relative_to(root):
        raise ValueError(f"path escapes repo: {path}")
    return p


def _run(root, args, timeout=CMD_TIMEOUT, input=None):
    return subprocess.run(
        args, cwd=root, capture_output=True, text=True, timeout=timeout, input=input
    )


def list_files(root):
    return _truncate(_run(root, ["git", "ls-files"]).stdout, keep="head")


def read_file(root, path, start=1, end=None):
    lines = _resolve(root, path).read_text().splitlines()
    start = max(1, start)
    end = end or len(lines)
    numbered = [f"{i}: {line}" for i, line in enumerate(lines[start - 1 : end], start)]
    return _truncate("\n".join(numbered), keep="head")


def grep(root, pattern):
    # "--" so a pattern starting with "-" is not read as a flag.
    out = _run(root, ["git", "grep", "-n", "-E", "--", pattern]).stdout
    return _truncate(out, keep="head") or "(no matches)"


def write_file(root, path, content):
    p = _resolve(root, path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"wrote {path}"


def edit_file(root, path, old, new):
    p = _resolve(root, path)
    text = p.read_text()
    n = text.count(old) if old else 0
    if n != 1:
        return f"error: `old` matched {n} times in {path}; it must match exactly once"
    p.write_text(text.replace(old, new))
    return f"edited {path}"


def apply_patch(root, diff):
    r = _run(root, ["git", "apply", "--whitespace=nowarn", "-"], input=diff)
    return "applied" if r.returncode == 0 else f"patch failed:\n{_truncate(r.stderr)}"


def run_tests(root, selector=""):
    args = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    if selector:
        args.append(selector)
    try:
        r = _run(root, args, timeout=TEST_TIMEOUT)
    except subprocess.TimeoutExpired:
        return -1, f"pytest timed out after {TEST_TIMEOUT}s"
    return r.returncode, _truncate(r.stdout + r.stderr)


def failing_tests(root, selector=""):
    """Set of failed/errored test ids, from a junit report so nothing is lost to truncation."""
    with tempfile.TemporaryDirectory() as d:
        report = Path(d) / "junit.xml"
        args = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={report}"]
        if selector:
            args.append(selector)
        try:
            _run(root, args, timeout=TEST_TIMEOUT)
        except subprocess.TimeoutExpired:
            return {"<suite timed out>"}
        if not report.exists():
            return {"<pytest wrote no report>"}
        cases = ET.parse(report).iter("testcase")
        return {
            f"{c.get('classname')}::{c.get('name')}"
            for c in cases
            if c.find("failure") is not None or c.find("error") is not None
        }


def git_diff(root):
    # Not truncated: guards and patch.diff need the whole diff.
    # Intent-to-add makes new files (like the repro test) show up in the diff.
    _run(root, ["git", "add", "-N", "."])
    return _run(root, ["git", "diff"]).stdout


def _spec(name, description, props, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {k: {"type": t} for k, t in props.items()},
                "required": required,
            },
        },
    }


SPECS = {
    "list_files": _spec("list_files", "List the files tracked in the repository.", {}, []),
    "read_file": _spec(
        "read_file",
        "Read a file with line numbers. Optional 1-based start and end lines.",
        {"path": "string", "start": "integer", "end": "integer"},
        ["path"],
    ),
    "grep": _spec(
        "grep", "Search tracked files with an extended regex. Returns path:line: text.", {"pattern": "string"}, ["pattern"]
    ),
    "edit_file": _spec(
        "edit_file",
        "Replace one exact occurrence of `old` with `new` in a file. `old` must match exactly once, including indentation.",
        {"path": "string", "old": "string", "new": "string"},
        ["path", "old", "new"],
    ),
    "write_file": _spec(
        "write_file", "Create or overwrite a file with the given content.", {"path": "string", "content": "string"}, ["path", "content"]
    ),
    "run_tests": _spec(
        "run_tests",
        "Run pytest, optionally on a selector like tests/test_x.py::test_y. Returns the exit code and the output tail.",
        {"selector": "string"},
        [],
    ),
}


def call(root, name, args, allow, protect_tests=False):
    """Run a model-requested tool. Errors come back as text so a bad call never crashes the run."""
    if name not in allow:
        return f"error: tool {name} is not available in this phase"
    if protect_tests and name in ("edit_file", "write_file") and guards.is_test_file(str(args.get("path", ""))):
        return "error: editing test files is not allowed; fix the source code instead"
    try:
        if name == "run_tests":
            code, out = run_tests(root, args.get("selector", ""))
            return f"exit code {code}\n{out}"
        return globals()[name](root, **args)
    except Exception as e:
        return f"error: {type(e).__name__}: {e}"
