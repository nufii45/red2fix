import hashlib

from agent import policy
from test_main import FakeLLM
from test_review import GOOD, PASSING_REPRO, make_patch, run, script


def test_defaults_when_missing(tmp_path):
    p = policy.load(tmp_path)
    assert p["require_proof"] is True and p["budget_usd"] == 1.00 and p["sha"] == "default"
    assert ".red2fix.toml" in p["restricted_paths"]


def test_toml_overrides_defaults(tmp_path):
    raw = b'require_proof = false\nrubric = ["Only one rule"]\n'
    (tmp_path / ".red2fix.toml").write_bytes(raw)
    p = policy.load(tmp_path)
    assert p["require_proof"] is False and p["rubric"] == ["Only one rule"]
    assert p["restricted_paths"] == policy.DEFAULTS["restricted_paths"]
    assert p["sha"] == hashlib.sha256(raw).hexdigest()


def test_restricted_globs():
    paths = [".github/workflows/ci.yml", "setup.py", "pkg/setup.py", "src/a.py"]
    assert policy.restricted(paths, [".github/**", "setup.py"]) == [".github/workflows/ci.yml", "setup.py"]


def test_pr_cannot_loosen_its_own_rules(buggy_repo, tmp_path):
    # The PR turns off require_proof and the restricted list; the base policy (defaults) still applies.
    loosen = {".red2fix.toml": "require_proof = false\nrestricted_paths = []\n"}
    patch = make_patch(buggy_repo, GOOD, loosen)
    rv = run(buggy_repo, tmp_path, patch, FakeLLM(**script(reproduce=[PASSING_REPRO])))

    assert rv["verdict"] == "unproven", rv
    assert rv["policy_sha"] == "default"
    assert rv["restricted_paths_touched"] == [".red2fix.toml"]
