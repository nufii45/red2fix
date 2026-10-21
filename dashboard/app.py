"""Red2Fix dashboard: reads the run folders in out/, nothing else.

Run: uv run streamlit run dashboard/app.py   (RED2FIX_ENABLE_LAUNCH=1 adds the demo Run button)
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # streamlit only puts dashboard/ on the path

import pandas as pd
import streamlit as st

from dashboard import data, launch

BUDGET_USD = 50.0
ROOT = data.ROOT
OUT = ROOT / "out"

st.set_page_config(page_title="Red2Fix", layout="wide")


@st.cache_data(show_spinner=False)
def _load(run_dir, mtime):
    return data.load_run(Path(run_dir))


def load(group):
    return [_load(str(d), data.mtime(d)) for g, d in data.find_runs(OUT) if g == group]


def step_bar(run):
    r = run["result"]
    current = data.STEPS.get(r.get("phase"), None)
    idx = data.STEP_NAMES.index(current) if current else -1
    cells = []
    for i, name in enumerate(data.STEP_NAMES):
        if r["status"] == "succeeded" or i < idx:
            cells.append(f"✅ {name}")
        elif i == idx and r["status"] == "aborted":
            cells.append(f"❌ **{name}**")
        elif i == idx:
            cells.append(f"🔵 **{name}**")
        else:
            cells.append(f"⚪ {name}")
    st.markdown(" → ".join(cells))
    if r["status"] == "aborted":
        st.error(f"Aborted: {r.get('abort_reason')}")


def live_details(run):
    events = run["events"]
    fix_iter = sum(e.get("name") == "FIX" for e in events)
    elapsed = time.time() - events[0]["t"] if events else 0
    last = run["ledger"][-1] if run["ledger"] else None
    call = f" · last call: {last['phase']} on {data.MODEL_NAMES.get(last['model'], last['model'])}" if last else ""
    st.caption(f"{elapsed:.0f}s elapsed · fix iteration {fix_iter} · ${run['result']['cost_usd']:.3f} so far{call}")


# Sidebar
runs_index = data.find_runs(OUT)
groups = sorted({g for g, _ in runs_index}, key=lambda g: (g != "demo", g))
if os.environ.get("RED2FIX_ENABLE_LAUNCH") == "1":
    with st.sidebar:
        st.subheader("Start a demo run")
        issues = launch.demo_issues(ROOT)
        n = st.selectbox("Demo issue", issues)
        pid = launch.running_pid(OUT / ".launch.lock")
        if st.button("Run", disabled=bool(pid), type="primary"):
            try:
                launch.start(n, ROOT)
                st.rerun()
            except (ValueError, RuntimeError) as e:
                st.error(str(e))
        if pid:
            st.caption(f"Run in progress (pid {pid}). Log: out/{n}/run.log")
        st.divider()

if not groups:
    st.title("Red2Fix")
    st.info("No runs in out/ yet. Start one with `scripts/run_local.sh 1` or `uv run bench/run.py`.")
    st.stop()

group = st.sidebar.selectbox("Runs", groups, format_func=lambda g: "demo issues" if g == "demo" else f"bench: {g}")
live = st.sidebar.toggle("Refresh every 3 s")

st.title("Red2Fix")
st.caption("Issue in, failing repro test, proven fix out. Every number below is read from out/.")


@st.fragment(run_every=3 if live else None)
def overview():
    runs = load(group)
    s = data.summarize(runs)
    resolved = data.official(group) if group != "demo" else None
    cols = st.columns(6)
    cols[0].metric("Attempted", s["attempted"], help=f"{s['running']} running" if s["running"] else None)
    cols[1].metric("Own repro red→green", f"{s['won']}/{s['attempted']}", help=f"{s['rate']:.0%}")
    cols[2].metric("Official SWE-bench", "not scored" if resolved is None else f"{len(resolved & {r['name'] for r in runs})}/{s['attempted']}")
    cols[3].metric("Median $/issue", f"${s['median_usd']:.3f}")
    cols[4].metric("Median time/issue", f"{s['median_s']:.0f}s")
    cols[5].metric("Spend in out/", f"${data.total_spend(OUT):.2f}", help=f"of the ${BUDGET_USD:.0f} credit")

    for run in [r for r in runs if r["result"]["status"] == "running"]:
        with st.container(border=True):
            st.markdown(f"**Live: {run['name']}**")
            step_bar(run)
            live_details(run)


overview()
runs = load(group)

left, right = st.columns(2)
with left:
    st.subheader("Cost by model")
    by_model = data.cost_by(runs, "model")
    if by_model:
        st.bar_chart(pd.DataFrame(by_model).T.fillna(0), y_label="USD")
with right:
    st.subheader("Cost by phase")
    by_phase = data.cost_by(runs, "phase")
    if by_phase:
        st.bar_chart(pd.DataFrame(by_phase).T.fillna(0), y_label="USD")

failures = data.summarize(runs)["failures"]
st.subheader("Failures")
if failures:
    st.bar_chart(pd.Series(failures, name="runs"), horizontal=True)
else:
    st.caption("No failed runs in this group.")

bench_groups = [g for g in groups if g != "demo"]
if len(bench_groups) > 1:
    st.subheader("Compare benchmark runs")
    picked = st.multiselect("Runs", bench_groups, default=bench_groups[-2:])
    rows = {}
    for g in picked:
        s = data.summarize(load(g))
        rows[g] = {"red→green rate": s["rate"], "median $/issue": s["median_usd"], "total $": s["total_usd"], "attempted": s["attempted"]}
    if rows:
        cmp = pd.DataFrame(rows).T
        st.dataframe(cmp)
        a, b = st.columns(2)
        a.bar_chart(cmp["red→green rate"])
        b.bar_chart(cmp["median $/issue"])

st.subheader("Runs")
resolved = data.official(group) if group != "demo" else None
table = pd.DataFrame([{
    "run": r["name"],
    "outcome": r["result"]["status"] if r["result"]["status"] != "aborted" else data.failure(r["result"]),
    "official": None if resolved is None else r["name"] in resolved,
    "iterations": r["result"].get("iterations", 0),
    "escalations": r["result"].get("escalations", 0),
    "$": r["result"].get("cost_usd", 0),
    "seconds": r["result"].get("seconds"),
} for r in runs])
if resolved is None:
    table = table.drop(columns="official")
picked_rows = st.dataframe(table, on_select="rerun", selection_mode="single-row", hide_index=True, key=f"table-{group}")
selected = picked_rows.selection.rows[0] if picked_rows.selection.rows else 0
run = runs[selected]

st.subheader(f"Run detail: {run['name']}")
step_bar(run)
issue = run["text"].get("issue.md")
if issue is None and group == "demo" and (ROOT / "demo" / "issues" / f"{run['name']}.md").exists():
    issue = (ROOT / "demo" / "issues" / f"{run['name']}.md").read_text()

tabs = st.tabs(["PR body", "Issue", "Repro test", "Red log", "Patch", "Green log", "Model calls"])
text = {**run["text"], "issue.md": issue}
for tab, (name, lang) in zip(tabs, [("summary.md", None), ("issue.md", "markdown"), ("repro_test.py", "python"),
                                    ("red.log", "text"), ("patch.diff", "diff"), ("green.log", "text")]):
    with tab:
        if not text.get(name):
            st.caption("Not produced by this run.")
        elif lang is None:
            st.markdown(text[name])  # model-written; Streamlit markdown keeps HTML off
        else:
            st.code(text[name], language=lang, wrap_lines=True)
with tabs[6]:
    if run["ledger"]:
        calls = pd.DataFrame(run["ledger"])
        calls["model"] = calls["model"].map(lambda m: data.MODEL_NAMES.get(m, m))
        calls["t"] = (calls["ts"] - calls["ts"].iloc[0]).round(1)
        st.dataframe(calls[["t", "phase", "model", "in_tokens", "out_tokens", "latency_ms", "cost_usd"]], hide_index=True)
    else:
        st.caption("Not produced by this run.")
