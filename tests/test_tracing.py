import json
import os
import re
import subprocess
import sys
from pathlib import Path

from agent import tools, tracing

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://smith.langchain.com/o/org-1/projects/p/proj-1"

# Runs one FakeLLM review; argv: repo, tmp dir, and "off" (no key: no langsmith, no network),
# "url" or "no_base" (key set, LANGSMITH_TRACE_URL_BASE set or not).
REVIEW = """
import json, socket, sys
from pathlib import Path
sys.path[:0] = [".", "tests"]
if sys.argv[3] == "off":
    def no_network(*a, **kw):
        raise AssertionError("network call without LANGSMITH_API_KEY")
    socket.socket.connect = no_network
else:
    from langsmith.run_trees import RunTree
    def lookup(self):
        raise AssertionError("trace_url must not be looked up: the key is write-only")
    RunTree.get_url = lookup
from test_main import FakeLLM
from test_review import GOOD, make_patch, run, script
repo, tmp = Path(sys.argv[1]), Path(sys.argv[2])
rv = run(repo, tmp, make_patch(repo, GOOD), FakeLLM(**script()))
result = json.loads((tmp / "out" / "result.json").read_text())
print("RV", json.dumps({"rv": rv, "result": result, "langsmith": "langsmith" in sys.modules}))
"""


def review(repo, tmp_path, mode):
    env = {k: v for k, v in os.environ.items() if not k.startswith("LANGSMITH_")}
    if mode != "off":
        # Every upload goes to a closed local port, so all of them fail.
        env.update(LANGSMITH_API_KEY="lsv2-test-key", LANGSMITH_ENDPOINT="http://127.0.0.1:9")
    if mode == "url":
        env["LANGSMITH_TRACE_URL_BASE"] = BASE + "?timeModel=%7B%7D"  # as copied from the UI
    p = subprocess.run([sys.executable, "-c", REVIEW, str(repo), str(tmp_path), mode],
                       cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stderr
    line = next(l for l in p.stdout.splitlines() if l.startswith("RV "))
    return json.loads(line[3:])


def test_no_key_means_no_langsmith_and_no_network(buggy_repo, tmp_path):
    out = review(buggy_repo, tmp_path, "off")
    assert out["rv"]["verdict"] == "proven"
    assert not out["langsmith"] and "trace_url" not in out["rv"]


def test_trace_url_is_recorded_even_when_uploads_fail(buggy_repo, tmp_path):
    out = review(buggy_repo, tmp_path, "url")
    assert out["rv"]["verdict"] == "proven"
    url = out["rv"]["trace_url"]
    assert url == out["result"]["trace_url"]
    assert re.fullmatch(re.escape(BASE) + r"/r/[0-9a-f-]{36}\?poll=true", url), url


def test_no_url_base_means_no_trace_url(buggy_repo, tmp_path):
    out = review(buggy_repo, tmp_path, "no_base")
    assert out["rv"]["verdict"] == "proven"
    assert "trace_url" not in out["rv"] and "trace_url" not in out["result"]


def test_redact_hides_secret_env_values(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "sk-very-secret-value")
    monkeypatch.setenv("HOME_DIR_NAME", "sk-very-secret-value-not-a-secret-name")
    got = tracing.redact({"messages": [{"content": "key=sk-very-secret-value"}], "n": 3})
    assert got == {"messages": [{"content": "key=[redacted]"}], "n": 3}


def test_env_files_are_off_limits(buggy_repo):
    (buggy_repo / ".env").write_text("NEBIUS_API_KEY=x\n")
    assert tools.call(buggy_repo, "read_file", {"path": ".env"}, {"read_file"}).startswith("error: ValueError")
