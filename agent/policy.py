"""Team policy for reviews: .red2fix.toml, read from the base checkout so a PR can't loosen its own rules."""

import hashlib
import tomllib
from fnmatch import fnmatch
from pathlib import Path

FILE = ".red2fix.toml"
DEFAULTS = {
    "rubric": [
        "Fixes the root cause described in the spec, not just the symptom",
        "No changes unrelated to the spec",
        "No weakened, skipped, xfailed or deleted tests",
        "Handles the edge cases the spec mentions",
    ],
    "restricted_paths": [".github/**", FILE, "setup.py", "pyproject.toml", "setup.cfg"],
    "require_proof": True,
    # "blocker": a quoted unrelated change to non-test code blocks, whatever severity the reviewer gave it.
    "unrelated_change": "blocker",
    "budget_usd": 1.00,
}


def load(root):
    """Policy dict plus "sha": sha256 of the file bytes, or "default" when the file is missing."""
    path = Path(root) / FILE
    if not path.exists():
        return {**DEFAULTS, "sha": "default"}
    raw = path.read_bytes()
    return {**DEFAULTS, **tomllib.loads(raw.decode()), "sha": hashlib.sha256(raw).hexdigest()}


def restricted(paths, patterns):
    # fnmatch's * also matches "/", so ".github/**" covers every file under .github/.
    return sorted(p for p in paths if any(fnmatch(p, pat) for pat in patterns))
