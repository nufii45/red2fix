import json

import pytest

from scripts import tryit_fetch as tf

ID = "5e1a07k2m4p6q7"


@pytest.mark.parametrize("url,expected", [
    ("https://github.com/nufii45/red2fix-minikit/pull/4", ("nufii45/red2fix-minikit", 4)),
    ("  https://github.com/a/b.c_d-e/pull/123  ", ("a/b.c_d-e", 123)),
])
def test_pr_url_accepted(url, expected):
    assert tf.parse_pr_url(url) == expected


@pytest.mark.parametrize("url", [
    "", "github.com/a/b/pull/1", "http://github.com/a/b/pull/1", "https://www.github.com/a/b/pull/1",
    "https://github.com/a/b/pull/1/files", "https://github.com/a/b/pull/1?x=1", "https://github.com/a/b/pull/1#c",
    "https://github.com/a/b/pull/0", "https://github.com/a/b/pull/01", "https://github.com/a/b/pull/abc",
    "https://github.com/a/b/issues/1", "https://github.com/a/b", "https://gitlab.com/a/b/pull/1",
    "https://github.com/a/../pull/1", "https://github.com/a b/c/pull/1", "https://github.com/a/b/pull/1\nhttps://github.com/c/d/pull/2",
    "https://github.com.evil.com/a/b/pull/1", "https://github.com/a/b/pull/12345678",
])
def test_pr_url_refused(url):
    with pytest.raises(tf.Refused):
        tf.parse_pr_url(url)


@pytest.mark.parametrize("value,repo,ok", [
    (None, "nufii45/red2fix-minikit", True),
    ("", "nufii45/red2fix-minikit", True),
    ("  ,  ", "nufii45/red2fix-minikit", True),
    (None, "NuFii45/Red2Fix-Minikit", True),
    (None, "psf/requests", False),
    ("nufii45/red2fix-minikit, psf/requests", "psf/requests", True),
    ("psf/requests", "nufii45/red2fix-minikit", False),  # an explicit list replaces the default
    ("psf/requests", "psf/requests-extra", False),
])
def test_allowlist(value, repo, ok):
    assert tf.allowed(repo, value) is ok


def runs(n, start=100):
    return [{"id": start + i, "display_title": f"try-it {ID}"} for i in range(n)]


@pytest.mark.parametrize("value,cap", [(None, 25), ("", 25), ("3", 3), ("x", 25), ("-1", 25), ("0", 0)])
def test_daily_cap_value(value, cap):
    assert tf.daily_cap(value) == cap


def test_cap_counts_this_run_and_earlier_ones_only():
    today = runs(5)  # ids 100..104
    assert not tf.over_cap(today, 102, cap=3)  # 100, 101, 102
    assert tf.over_cap(today, 103, cap=3)
    assert not tf.over_cap(today, 104, cap=5)
    assert tf.over_cap(today, 100, cap=0)


def test_cap_ignores_runs_that_are_not_try_it():
    other = [{"id": 1, "display_title": "red2fix"}, {"id": 2, "display_title": "try-it nonsense"}]
    assert not tf.over_cap(other + runs(1, start=10), 10, cap=1)


PR = {"title": "Fix minutes", "body": "Fixes #1", "base": {"sha": "b" * 40, "repo": {"private": False}},
      "head": {"sha": "h" * 40}}


def fake_api(pr=PR, diff="diff --git a/x b/x\n+1\n", runs_today=()):
    def api(path, accept="application/vnd.github+json"):
        if "/actions/workflows/" in path:
            return {"workflow_runs": list(runs_today)}
        if path.endswith("/issues/1"):
            return {"title": "Minutes are wrong", "body": "1h30m gives 3630"}
        return diff if accept.endswith("diff") else pr
    return api


def run_main(tmp_path, monkeypatch, url="https://github.com/nufii45/red2fix-minikit/pull/4", run_id=7, **kw):
    monkeypatch.setattr(tf, "api", fake_api(**kw))
    out_file = tmp_path / "gh_output"
    for k, v in {"GITHUB_WORKSPACE": str(tmp_path), "GITHUB_OUTPUT": str(out_file), "PR_URL": url,
                 "REQUEST_ID": ID, "GITHUB_RUN_ID": str(run_id), "GITHUB_REPOSITORY": "nufii45/red2fix",
                 "GITHUB_SHA": "r" * 40, "GH_TOKEN": "t"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("TRYIT_REPOS", raising=False)
    monkeypatch.delenv("TRYIT_DAILY_CAP", raising=False)
    tf.main([])
    outputs = dict(l.split("=", 1) for l in out_file.read_text().splitlines())
    return outputs, tmp_path / "out"


def test_fetch_writes_inputs_and_meta(tmp_path, monkeypatch):
    outputs, out = run_main(tmp_path, monkeypatch)
    assert outputs == {"refused": "false", "repo": "nufii45/red2fix-minikit", "number": "4",
                       "base_sha": "b" * 40, "head_sha": "h" * 40, "spec_source": "issue#1"}
    assert (tmp_path / "pr.patch").read_text().startswith("diff --git")
    assert "1h30m gives 3630" in (tmp_path / "spec.md").read_text()
    meta = json.loads((out / "meta.json").read_text())
    assert meta["title"] == "Fix minutes" and meta["reviewer_sha"] == "r" * 40 and meta["request_id"] == ID
    assert not (out / "review.json").exists()


@pytest.mark.parametrize("kw,reason", [
    ({"url": "https://github.com/psf/requests/pull/1"}, "allowlist"),
    ({"url": "https://github.com/a/b/issues/1"}, "not a GitHub pull request URL"),
    ({"runs_today": runs(26, start=1), "run_id": 26}, "used up"),
    ({"pr": {**PR, "base": {**PR["base"], "repo": {"private": True}}}}, "private"),
    ({"diff": ""}, "empty diff"),
    ({"diff": "x" * (tf.MAX_PATCH_BYTES + 1)}, "too large"),
])
def test_refusals_write_an_error_review(tmp_path, monkeypatch, kw, reason):
    outputs, out = run_main(tmp_path, monkeypatch, **kw)
    assert outputs == {"refused": "true"}
    review = json.loads((out / "review.json").read_text())
    assert review["verdict"] == "error" and reason in review["verdict_reason"]
    assert json.loads((out / "meta.json").read_text())["request_id"] == ID
    assert not (tmp_path / "pr.patch").exists()


def test_error_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_WORKSPACE", str(tmp_path))
    tf.main(["--error", "couldn't install the repo"])
    review = json.loads((tmp_path / "out" / "review.json").read_text())
    assert review["verdict"] == "error" and review["verdict_reason"] == "couldn't install the repo"
    assert "couldn't install the repo" in (tmp_path / "out" / "review.md").read_text()
