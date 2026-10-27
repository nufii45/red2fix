"""Anti-cheat checks on a candidate patch (unified diff text)."""

import re
from pathlib import PurePosixPath

CHEAT_LINE = re.compile(r"pytest\.skip|xfail|except\b[^:]*:\s*pass\b")


def is_test_file(path):
    p = PurePosixPath(path)
    return (
        p.name.startswith("test_")
        or p.name.endswith("_test.py")
        or p.name == "conftest.py"
        or "tests" in p.parts
        or "test" in p.parts
    )


def _diff_path(line):
    # "--- a/x.py" / "+++ b/x.py"; /dev/null marks a created or deleted file.
    path = line[4:].split("\t")[0].strip()
    if path == "/dev/null":
        return None
    return path[2:] if path[:2] in ("a/", "b/") else path


def check_patch(diff, repro_path):
    """Return a list of violations; empty means the patch is allowed.

    `diff` must be the fix only, taken against a state where the repro test is already
    committed, otherwise creating the repro test itself counts as modifying it.
    """
    violations = []
    touched = set()
    for line in diff.splitlines():
        if line.startswith(("--- ", "+++ ")):
            path = _diff_path(line)
            if path:
                touched.add(path)
        elif line.startswith("+") and CHEAT_LINE.search(line):
            violations.append(f"adds forbidden construct: {line[1:].strip()}")

    for path in sorted(touched):
        if path == repro_path:
            violations.append(f"modifies the repro test: {path}")
        elif is_test_file(path):
            violations.append(f"modifies a test file: {path}")
    return violations


TEST_DEF = re.compile(r"^([+-])\s*(?:async\s+)?def (test_\w+)")


def deleted_tests(diff):
    """Test files the diff deletes and test functions it removes without re-adding.

    A removed test can't fail on head, so the regression check alone would never notice it.
    """
    files, removed, added = [], set(), set()
    old, in_deleted_file = None, False
    for line in diff.splitlines():
        if line.startswith("--- "):
            old = _diff_path(line)
        elif line.startswith("+++ "):
            in_deleted_file = _diff_path(line) is None
            if in_deleted_file and old and is_test_file(old):
                files.append(old)
        elif not in_deleted_file and (m := TEST_DEF.match(line)):
            (removed if m.group(1) == "-" else added).add(m.group(2))
    return [f"deletes test file: {p}" for p in files] + [f"deletes test function: {n}" for n in sorted(removed - added)]
