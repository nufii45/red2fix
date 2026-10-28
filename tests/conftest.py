import os
import subprocess

import pytest

# Tests never trace for real; agent.tracing reads this at import, after conftest.
for _k in [k for k in os.environ if k.startswith("LANGSMITH_")]:
    del os.environ[_k]


@pytest.fixture
def buggy_repo(tmp_path):
    """Tiny git repo: mathlib.div crashes on zero instead of returning None."""
    (tmp_path / "mathlib.py").write_text("def div(a, b):\n    return a / b\n")
    (tmp_path / "test_mathlib.py").write_text(
        "from mathlib import div\n\n"
        "def test_div():\n    assert div(6, 3) == 2\n\n"
        "def test_div_zero():\n    assert div(1, 0) is None\n"
    )
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run([*git, "add", "."], cwd=tmp_path, check=True)
    subprocess.run([*git, "commit", "-qm", "init"], cwd=tmp_path, check=True)
    return tmp_path
