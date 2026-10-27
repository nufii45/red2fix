import pytest

import config
from agent import tools

FIX = """\
--- a/mathlib.py
+++ b/mathlib.py
@@ -1,2 +1,4 @@
 def div(a, b):
+    if b == 0:
+        return None
     return a / b
"""


def test_list_read_grep(buggy_repo):
    assert "mathlib.py" in tools.list_files(buggy_repo)
    assert tools.read_file(buggy_repo, "mathlib.py", 2, 2) == "2:     return a / b"
    assert "mathlib.py:2:" in tools.grep(buggy_repo, "a / b")
    assert tools.grep(buggy_repo, "nothing_here") == "(no matches)"


def test_red_then_green(buggy_repo):
    code, out = tools.run_tests(buggy_repo, "test_mathlib.py::test_div_zero")
    assert code == 1 and "ZeroDivisionError" in out

    assert tools.apply_patch(buggy_repo, FIX) == "applied"
    code, out = tools.run_tests(buggy_repo)
    assert code == 0 and "2 passed" in out
    assert "+    if b == 0:" in tools.git_diff(buggy_repo)


def test_bad_patch_reports_failure(buggy_repo):
    assert tools.apply_patch(buggy_repo, "garbage").startswith("patch failed")


def test_write_file_shows_in_diff(buggy_repo):
    tools.write_file(buggy_repo, "tests/test_repro.py", "def test_x(): pass\n")
    assert "tests/test_repro.py" in tools.git_diff(buggy_repo)


@pytest.mark.parametrize("path", ["../outside.py", "/etc/passwd"])
def test_path_escape_rejected(buggy_repo, path):
    with pytest.raises(ValueError):
        tools.write_file(buggy_repo, path, "x")
    with pytest.raises(ValueError):
        tools.read_file(buggy_repo, path)


def test_truncation(buggy_repo, monkeypatch):
    monkeypatch.setattr(config, "TOOL_OUTPUT_LINES", 5)
    tools.write_file(buggy_repo, "big.py", "\n".join(f"x{i} = {i}" for i in range(50)))
    out = tools.read_file(buggy_repo, "big.py")
    assert out.splitlines()[0] == "1: x0 = 0"
    assert out.splitlines()[-1] == "... [45 lines truncated] ..."


def test_git_dir_is_off_limits(buggy_repo):
    with pytest.raises(ValueError, match="inside .git"):
        tools.read_file(buggy_repo, ".git/HEAD")
    assert "inside .git" in tools.call(buggy_repo, "read_file", {"path": ".git/config"}, ["read_file"])


def test_list_files_under_a_directory(buggy_repo):
    assert tools.list_files(buggy_repo, "mathlib.py").strip() == "mathlib.py"
    assert tools.list_files(buggy_repo, "nope") == "(no files)"
    assert "test_mathlib.py" in tools.call(buggy_repo, "list_files", {}, ["list_files"])
