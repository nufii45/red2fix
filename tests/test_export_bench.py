"""Every number /results shows (web/public/data/bench.json) must match the bench's review_report.md."""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from bench import report_review
from scripts import export_bench
from tests.test_bench_report import rv, write

ROOT = Path(__file__).resolve().parent.parent


def ids(s):
    return [] if s == "none" else s.split(", ")


def assert_matches(md, b):
    fa = re.search(r"False approvals \(failed patches marked proven\): (\d+) / (\d+) \((.*)\)", md)  # first: blocker
    fc = re.search(r"False approvals, cleaned labels: (\d+) / (\d+) \((.*)\)", md)
    ca = re.search(r"Correct approvals \(gold patches marked proven\): (\d+) / (\d+)", md)
    assert (b["original"]["false_approvals"], b["original"]["failed_total"]) == (ids(fa[3]), int(fa[2]))
    assert len(b["original"]["false_approvals"]) == int(fa[1])
    assert (b["cleaned"]["false_approvals"], b["cleaned"]["failed_total"]) == (ids(fc[3]), int(fc[2]))
    assert (b["gold"]["approvals"], b["gold"]["total"]) == (int(ca[1]), int(ca[2]))

    m = re.search(r"Reviews: (\d+) · unproven: (\d+) · errors: (\d+) · median \$([\d.]+) and (\d+) s per review"
                  r" · total \$([\d.]+) · calls: (.*)", md)
    assert (b["reviews"], b["unproven"], b["errors"]) == (int(m[1]), int(m[2]), int(m[3]))
    assert abs(b["median_usd"] - float(m[4])) <= 0.0005 and round(b["median_s"]) == int(m[5])
    assert f"{b['total_usd']:.2f}" == m[6]
    calls = dict((k, int(n)) for k, n in (c.split() for c in m[7].split(", ")))
    assert {k: n for k, n in b["calls"].items() if n} == calls
    assert {k: v["calls"] for k, v in b["cost_by_model"].items()} == calls
    assert sum(b["errors_by_cause"].values()) == b["errors"]

    table = {}
    for line in md.splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == 6 and "__" in cells[0]:
            table[cells[0]] = cells
    after = lambda c: c.split("→")[-1].strip(" *")  # noqa: E731  stored → **recomputed**
    assert [i["id"] for i in b["instances"]] == sorted(table)
    for i in b["instances"]:
        _, gold, failed, truly, usd, _ = table[i["id"]]
        assert i.get("gold", {}).get("verdict", "—") == after(gold)
        assert i.get("failed", {}).get("verdict", "—") == after(failed)
        assert {True: "yes", False: "no"}.get(i.get("failed", {}).get("truly_failed"), "—") == truly
        assert abs(sum(i[k]["cost_usd"] for k in ("gold", "failed") if k in i) - float(usd)) <= 0.001
    for kind in ("gold", "failed"):
        counts = Counter(i[kind]["verdict"] for i in b["instances"] if kind in i)
        assert b["verdicts"][kind] == dict(counts)


def test_export_matches_the_report(tmp_path):
    run = tmp_path / "rv-x"
    write(run, "a__a-1", "gold", rv("proven", cost=0.2, secs=90, calls={"ultra": 1}))
    write(run, "a__a-1", "failed", rv("proven", calls={}))  # passes its FAIL_TO_PASS tests: label noise
    write(run, "b__b-2", "gold", rv("doesnt_fix", proof="doesnt_fix", cost=0.3, calls={}))
    write(run, "b__b-2", "failed", rv("error", proof=None, calls={}))
    (run / "a__a-1" / "gold" / "ledger.jsonl").write_text(
        '{"model": "nvidia/Nemotron-3-Ultra-550b-a55b", "cost_usd": 0.2}\n'
        '{"model": "tavily", "cost_usd": 0}\n')
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"a__a-1": [], "b__b-2": ["t::x"]}))
    report_review.report(run, labels)

    b, demos = export_bench.export(run, tmp_path / "data" / "bench.json")

    assert_matches((run / "review_report.md").read_text(), b)
    assert b["cost_by_model"] == {"ultra": {"calls": 1, "usd": 0.2}}
    assert json.loads((tmp_path / "data" / "demos.json").read_text()) == demos
    assert [d["name"] for d in demos] == list(export_bench.DEMOS)


def test_committed_results_match_rv_full():
    md = ROOT / "out" / "bench" / "rv-full" / "review_report.md"
    if not md.exists():
        pytest.skip("out/bench/rv-full isn't in the repo; run the bench first")
    assert_matches(md.read_text(), json.loads((ROOT / "web" / "public" / "data" / "bench.json").read_text()))
