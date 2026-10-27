import subprocess

from agent import pr_context
from agent.main import git

BASE = '''class Config(dict):
    def from_file(
        self,
        filename,
        silent=False,
    ):
        """Load a file."""
        with open(filename) as f:
            return f.read()

    def other(self):
        return 1


def helper(x):
    return x + 1
'''


def repo(tmp_path, files):
    for path, text in files.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def diff_of(root, changes):
    for path, (old, new) in changes.items():
        p = root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(p.read_text().replace(old, new) if old else new)
    git(root, "add", "-A")
    d = git(root, "diff", "--cached")
    git(root, "reset", "--hard", "-q")
    git(root, "clean", "-fdq")
    return d


def test_multiline_signature_change_shows_the_full_head_signature(tmp_path):
    r = repo(tmp_path, {"pkg/config.py": BASE})
    d = diff_of(r, {"pkg/config.py": ("        silent=False,\n", "        silent=False,\n        text=True,\n")})
    shape, names = pr_context.interface(r, d, ["pkg/config.py"])
    assert "changed signature: def Config.from_file(self, filename, silent=False, text=True)" in shape
    assert "with open" not in shape and "Load a file" not in shape  # never body or docstring
    assert names == {"text"}  # only what the PR adds


def test_body_only_change_shows_the_name_only(tmp_path):
    r = repo(tmp_path, {"pkg/config.py": BASE})
    d = diff_of(r, {"pkg/config.py": ("    return x + 1", "    return x + 2")})
    shape, names = pr_context.interface(r, d, ["pkg/config.py"])
    assert shape.strip().endswith("pkg/config.py: body changed: helper")
    assert "x + 2" not in shape and "changed signature" not in shape
    assert names == set()


def test_added_function_and_deleted_lines(tmp_path):
    r = repo(tmp_path, {"pkg/config.py": BASE})
    d = diff_of(r, {"pkg/config.py": ("    def other(self):\n        return 1\n", "    def other(self):\n        pass\n\n    def fresh(self, n: int = 3) -> int:\n        return n * 7\n")})
    shape, names = pr_context.interface(r, d, ["pkg/config.py"])
    assert "changed signature: def Config.fresh(self, n: int=3) -> int" in shape
    assert "body changed: Config.other" in shape
    assert "n * 7" not in shape
    assert names == {"fresh", "n"}


def test_test_files_and_unparsable_code_are_skipped(tmp_path):
    r = repo(tmp_path, {"tests/test_x.py": "def test_a():\n    pass\n", "old.py": "print 'py2'\n"})
    d = diff_of(r, {"tests/test_x.py": (None, "def test_a():\n    pass\n\ndef test_b():\n    pass\n"),
                    "old.py": ("print 'py2'\n", "print 'py2'\nprint 'more'\n")})
    assert pr_context.interface(r, d, ["tests/test_x.py", "old.py"]) == ("", set())


def test_related_test_prefers_the_module_test(tmp_path):
    r = repo(tmp_path, {
        "src/pkg/config.py": BASE, "src/pkg/cli.py": "def run():\n    pass\n",
        "tests/test_config.py": "from pkg.config import Config\n\ndef test_c():\n    Config()\n",
        "tests/test_cli.py": "from pkg.cli import run\n",
    })
    assert pr_context.related_test(r, ["src/pkg/config.py"])[0] == "tests/test_config.py"
    assert pr_context.related_test(r, ["README.md"]) is None
    block = pr_context.related_test_block(r, ["src/pkg/config.py"])
    assert "tests/test_config.py" in block and "1: from pkg.config import Config" in block


def test_module_names():
    assert pr_context.module_names("src/flask/config.py") == ("flask.config", "config")
    assert pr_context.module_names("requests/__init__.py") == ("requests", "requests")
