import json

import pytest

from agent import review, search


@pytest.fixture
def tavily(monkeypatch):
    """Every payload sent to Tavily; each answers with 4 results whose content is longer than the cut."""
    sent = []

    def post(payload):
        sent.append(payload)
        return {"results": [{"title": f"t{i}", "url": f"https://docs.example/{i}", "content": "x" * 3000}
                            for i in range(4)]}

    monkeypatch.setattr(search, "post", post)
    return sent


def test_excluded_domains_are_always_sent(tavily, tmp_path):
    (tmp_path / "setup.py").write_text('setup(url="https://flask.palletsprojects.com/", project_urls={"Code": "https://github.com/x"})')
    s = search.Search(tmp_path / "ledger.jsonl", search.project_hosts(tmp_path))
    text, results = s.query("REPRODUCE", "werkzeug Blueprint name")
    urls = [r["url"] for r in results]

    assert tavily[0]["exclude_domains"] == search.EXCLUDE + ["flask.palletsprojects.com"]
    assert "include_domains" not in tavily[0]
    assert tavily[0]["max_results"] == 3 and urls == [f"https://docs.example/{i}" for i in range(3)]
    assert "x" * 1500 in text and "x" * 1501 not in text and "untrusted" in text
    row = json.loads((tmp_path / "ledger.jsonl").read_text())
    assert (row["model"], row["phase"], row["query"], row["cost_usd"]) == ("tavily", "REPRODUCE", "werkzeug Blueprint name", 0.0)
    assert s.log == [{"phase": "REPRODUCE", "query": "werkzeug Blueprint name", "urls": urls, "status": "ok"}]


def test_budget_is_three_per_review(tavily, tmp_path):
    s = search.Search(tmp_path / "ledger.jsonl")
    assert [s.query("LOCALIZE", f"q{i}")[0].startswith("<search_results>") for i in range(3)] == [True] * 3
    assert s.query("REVIEW", "q4", model=False) == (search.BUDGET_USED, [])
    assert len(tavily) == 3 and s.log[-1]["status"] == search.BUDGET_USED


def test_reserve_keeps_searches_for_dependencies(tavily, tmp_path):
    s = search.Search(tmp_path / "ledger.jsonl")
    s.reserved = 2
    assert s.query("REPRODUCE", "a")[0] != search.BUDGET_USED
    assert s.query("REPRODUCE", "b")[0] == search.BUDGET_USED
    assert s.query("REVIEW", "c", model=False)[0] != search.BUDGET_USED
    assert s.query("REVIEW", "d", model=False)[0] != search.BUDGET_USED
    assert len(tavily) == 3


def test_failed_search_is_text_not_a_crash(monkeypatch, tmp_path):
    monkeypatch.setattr(search, "post", lambda payload: (_ for _ in ()).throw(OSError("down")))
    s = search.Search(tmp_path / "ledger.jsonl")
    assert s.query("REPRODUCE", "q") == ("error: OSError: down", []) and s.used == 1


DEPS = """\
diff --git a/requirements-dev.txt b/requirements-dev.txt
--- a/requirements-dev.txt
+++ b/requirements-dev.txt
@@ -1,2 +1,3 @@
-requests==2.18.0
+requests==2.19.1  # pinned
+-r base.txt
+click
 pytest
diff --git a/pyproject.toml b/pyproject.toml
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -1,3 +1,6 @@
+name = "minikit"
+version = "0.1.1"
+requires-python = ">=3.8"
 dependencies = [
+    "PyYAML>=5.3.1",
+    "jinja2[i18n]==2.10",
 ]
diff --git a/setup.py b/setup.py
--- a/setup.py
+++ b/setup.py
@@ -1 +1 @@
+setup(name="x", version="1.0", install_requires=["urllib3==1.24.1", "six"])
diff --git a/setup.cfg b/setup.cfg
--- a/setup.cfg
+++ b/setup.cfg
@@ -1,3 +1,5 @@
+python_requires = >=3.8
 install_requires =
+    Django ~= 2.2.0
diff --git a/minikit/pins.py b/minikit/pins.py
--- a/minikit/pins.py
+++ b/minikit/pins.py
@@ -0,0 +1 @@
+VERSION = "requests==1.0"
"""


def test_dependencies_in_every_file_format():
    assert search.dependencies(review.diff_sections(DEPS)) == [
        ("requests", "2.19.1"), ("PyYAML", "5.3.1"), ("jinja2", "2.10"), ("urllib3", "1.24.1"), ("Django", "2.2.0"),
    ]


def test_include_domains_replace_the_exclude_list(tavily, tmp_path):
    s = search.Search(tmp_path / "ledger.jsonl")
    s.query("REVIEW", "requests 2.19.1 security advisory", model=False, include=search.ADVISORY_DOMAINS)
    assert tavily[0]["include_domains"] == search.ADVISORY_DOMAINS and "exclude_domains" not in tavily[0]


@pytest.mark.parametrize("title,content,ok", [
    ("CVE-2018-18074 Detail", "Requests before 2.20.0 sends an HTTP Authorization header", True),  # name + CVE id
    ("requests", "Version 2.19.1 is affected", True),                                              # name + exact version
    ("requests 2.16.0", "leaks the Authorization header on redirect", False),                     # another version, no id
    ("urllib3 advisory", "CVE-2019-11324 in 2.19.1", False),                                        # another package
    ("requests", "fixed in 2.19.10", False),                                                        # not the exact version
    ("requests-oauthlib", "GHSA-x84v-xcm2-53pg", False),                                            # another package's name
    ("requests", "see ghsa-x84v-xcm2-53pg", True),                                                  # GHSA id, any case
])
def test_corroborates(title, content, ok):
    assert search.corroborates({"title": title, "content": content}, "requests", "2.19.1") is ok
