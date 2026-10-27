"""Pick the frozen benchmark list from SWE-bench Lite and write bench/instances.json.

Usage: uv run bench/pick.py
"""

import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

API = "https://datasets-server.huggingface.co/rows?dataset=SWE-bench/SWE-bench_Lite&config=default&split=test"
# Repos whose official test command is plain pytest; django, sympy and sphinx use their own runners.
REPOS = {
    "psf/requests", "pallets/flask", "pytest-dev/pytest", "pylint-dev/pylint",
    "astropy/astropy", "pydata/xarray", "mwaskom/seaborn",
}
DIFFICULTY = {"<15 min fix": 0, "15 min - 1 hour": 1, "1-4 hours": 2, ">4 hours": 3}
OUT = Path(__file__).with_name("instances.json")


def fetch_rows():
    rows, offset = [], 0
    while True:
        with urllib.request.urlopen(f"{API}&offset={offset}&length=100", timeout=60) as r:
            page = json.load(r)
        rows += [x["row"] for x in page["rows"]]
        offset += 100
        if offset >= page["num_rows_total"]:
            return rows


def patch_test_files(patch):
    return sorted({p for p in re.findall(r"^\+\+\+ b/(\S+)", patch, re.M) if p.endswith(".py")})


def pick(rows, n=20, per_repo=5):
    rows = sorted(
        (r for r in rows if r["repo"] in REPOS),
        key=lambda r: (DIFFICULTY.get(r.get("difficulty"), 9), r["instance_id"]),
    )
    taken, per = [], Counter()
    for r in rows:
        if len(taken) == n:
            break
        if per[r["repo"]] < per_repo:
            per[r["repo"]] += 1
            taken.append({
                "instance_id": r["instance_id"],
                "repo": r["repo"],
                "image": r["image"],
                "base_commit": r["base_commit"],
                "difficulty": r.get("difficulty"),
                "problem_statement": r["problem_statement"],
                "test_files": patch_test_files(r["test_patch"]),
                "patch": r["patch"],  # gold patch, reviewed in bench review mode; never the test_patch
            })
    return taken


if __name__ == "__main__":
    chosen = pick(fetch_rows())
    if OUT.exists():
        frozen = [i["instance_id"] for i in json.loads(OUT.read_text())]
        assert [c["instance_id"] for c in chosen] == frozen, "the frozen benchmark list changed"
    OUT.write_text(json.dumps(chosen, indent=2) + "\n")
    for c in chosen:
        print(f"{c['instance_id']:40} {c['difficulty']:18} {' '.join(c['test_files'])}")
    print(f"{len(chosen)} instances -> {OUT}")
