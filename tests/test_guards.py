from agent.guards import check_patch

REPRO = "tests/test_repro_issue_7.py"


def diff(path, *added):
    body = "\n".join("+" + a for a in added)
    return f"--- a/{path}\n+++ b/{path}\n@@ -1,1 +1,2 @@\n x = 1\n{body}\n"


def test_clean_fix_passes():
    assert check_patch(diff("pkg/core.py", "    if b == 0:", "        return None"), REPRO) == []


def test_repro_test_modified():
    assert check_patch(diff(REPRO, "    assert True"), REPRO) == [f"modifies the repro test: {REPRO}"]


def test_existing_test_files_caught():
    for path in ["tests/test_core.py", "pkg/core_test.py", "conftest.py", "test/helpers.py"]:
        assert check_patch(diff(path, "y = 2"), REPRO) == [f"modifies a test file: {path}"]


def test_new_file_from_dev_null():
    d = "--- /dev/null\n+++ b/pkg/new.py\n@@ -0,0 +1 @@\n+y = 2\n"
    assert check_patch(d, REPRO) == []


def test_cheat_constructs_caught():
    for line in ["    pytest.skip('nope')", "@pytest.mark.xfail", "    except: pass", "    except Exception:  pass"]:
        v = check_patch(diff("pkg/core.py", line), REPRO)
        assert len(v) == 1 and v[0].startswith("adds forbidden construct"), line


def test_removed_cheat_line_is_fine():
    d = "--- a/pkg/core.py\n+++ b/pkg/core.py\n@@ -1,2 +1,1 @@\n x = 1\n-    except: pass\n"
    assert check_patch(d, REPRO) == []
