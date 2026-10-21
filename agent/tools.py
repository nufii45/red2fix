"""Repo tools for the agent. Every tool takes the repo root and returns truncated text."""

import subprocess
import sys
from pathlib import Path

import config

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


def git_diff(root):
    # Not truncated: guards and patch.diff need the whole diff.
    # Intent-to-add makes new files (like the repro test) show up in the diff.
    _run(root, ["git", "add", "-N", "."])
    return _run(root, ["git", "diff"]).stdout
