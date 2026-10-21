"""Red2Fix dashboard: reads the run folders in out/, nothing else. Styled bryl-minimal (dashboard/style.css).

Run: uv run streamlit run dashboard/app.py   (RED2FIX_ENABLE_LAUNCH=1 adds the demo Run button)
"""

import os
import sys
import time
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # streamlit only puts dashboard/ on the path

import pandas as pd
import streamlit as st

from dashboard import data, launch

BUDGET_USD = 50.0
ROOT = data.ROOT
OUT = ROOT / "out"

st.set_page_config(page_title="red2fix", layout="wide")
st.markdown(f"<style>{(Path(__file__).parent / 'style.css').read_text()}</style>", unsafe_allow_html=True)


def html(markup):
    """Our own markup only; every run-derived value in it goes through escape()."""
    st.markdown(markup, unsafe_allow_html=True)


def section(n, name):
    html(f'<div class="r2f-section">{n:02d} — {name}</div>')


@st.cache_data(show_spinner=False)
def _load(run_dir, mtime):
    return data.load_run(Path(run_dir))


def load(group):
    return [_load(str(d), data.mtime(d)) for g, d in data.find_runs(OUT) if g == group]


def step_bar(run):
    r = run["result"]
    current = data.STEPS.get(r.get("phase"))
    idx = data.STEP_NAMES.index(current) if current else -1
    pills = []
    for i, name in enumerate(data.STEP_NAMES):
        if r["status"] == "succeeded" or i < idx:
            cls = "done"
        elif i == idx:
            cls = "fail" if r["status"] == "aborted" else "now"
        else:
            cls = ""
        mark = "✕ " if cls == "fail" else ""
        pills.append(f'<span class="r2f-step {cls}">{mark}{name}</span>')
    bar = f'<div class="r2f-steps">{"<span class=r2f-arrow>→</span>".join(pills)}</div>'
    if r["status"] == "aborted":
        bar += f'<div class="r2f-note">aborted · {escape(str(r.get("abort_reason")))}</div>'
    return bar


def live_card(run):
    events = run["events"]
    fix_iter = sum(e.get("name") == "FIX" for e in events)
    elapsed = time.time() - events[0]["t"] if events else 0
    last = run["ledger"][-1] if run["ledger"] else None
    call = f" · last call {escape(last['phase'])} on {escape(data.MODEL_NAMES.get(last['model'], last['model']))}" if last else ""
    return (
        f'<div class="r2f-card r2f-in"><div class="head"><span class="name">{escape(run["name"])}</span>'
        f'<span class="r2f-label">live</span></div>{step_bar(run)}'
        f'<div class="r2f-label">{elapsed:.0f}s elapsed · fix iteration {fix_iter} · '
        f'${run["result"]["cost_usd"]:.3f} so far{call}</div></div>'
    )


def stat(label, value, sub=""):
    return (f'<div class="r2f-stat"><div class="r2f-label">{label}</div><div class="v">{value}</div>'
            f'<div class="s">{sub}</div></div>')


# Sidebar
groups = sorted({g for g, _ in data.find_runs(OUT)}, key=lambda g: (g != "demo", g))
if os.environ.get("RED2FIX_ENABLE_LAUNCH") == "1":
    with st.sidebar:
        html('<div class="r2f-section" style="margin-top:0">start a demo run</div>')
        n = st.selectbox("Demo issue", launch.demo_issues(ROOT))
        pid = launch.running_pid(OUT / ".launch.lock")
        if st.button("Run ↗", disabled=bool(pid), type="primary"):
            try:
                launch.start(n, ROOT)
                st.rerun()
            except (ValueError, RuntimeError) as e:
                html(f'<div class="r2f-note">{escape(str(e))}</div>')
        if pid:
            st.caption(f"run in progress · pid {pid} · out/{n}/run.log")

html('<header class="r2f-hero r2f-in"><div class="r2f-label">nvidia × nebius · coding &amp; agentic engineering</div>'
     '<div class="r2f-title">red2fix</div><p class="r2f-lede">Issue in, failing repro test, proven fix out. '
     'Every number on this page is read from <code>out/</code>.</p></header>')

if not groups:
    html('<div class="r2f-note">No runs in out/ yet. Start one with scripts/run_local.sh 1 or uv run bench/run.py.</div>')
    st.stop()

with st.sidebar:
    html('<div class="r2f-section">view</div>')
    group = st.selectbox("Runs", groups, format_func=lambda g: "demo issues" if g == "demo" else f"bench · {g}")
    live = st.toggle("Refresh every 3 s")


@st.fragment(run_every=3 if live else None)
def overview():
    runs = load(group)
    s = data.summarize(runs)
    resolved = data.official(group) if group != "demo" else None
    official = "—" if resolved is None else f"{len(resolved & {r['name'] for r in runs})}/{s['attempted']}"
    section(1, "overview")
    html('<div class="r2f-stats r2f-in" style="animation-delay:120ms">'
         + stat("attempted", s["attempted"], f"{s['running']} running" if s["running"] else "")
         + stat("own repro red→green", f"{s['won']}/{s['attempted']}", f"{s['rate']:.0%}")
         + stat("official swe-bench", official, "not scored" if resolved is None else "hidden tests")
         + stat("median $/issue", f"${s['median_usd']:.3f}")
         + stat("median time/issue", f"{s['median_s']:.0f}s")
         + stat("spend in out/", f"${data.total_spend(OUT):.2f}", f"of ${BUDGET_USD:.0f} credit")
         + "</div>")
    for run in [r for r in runs if r["result"]["status"] == "running"]:
        html(live_card(run))


overview()
runs = load(group)

section(2, "cost")
left, right = st.columns(2, gap="large")
with left:
    html('<div class="r2f-label">by model</div>')
    by_model = pd.DataFrame(data.cost_by(runs, "model")).T.fillna(0)
    if not by_model.empty:
        st.bar_chart(by_model, y_label="usd", height=260)
with right:
    html('<div class="r2f-label">by phase</div>')
    by_phase = pd.DataFrame(data.cost_by(runs, "phase")).T.fillna(0)
    if not by_phase.empty:
        st.bar_chart(by_phase, y_label="usd", height=260)

section(3, "failures")
failures = data.summarize(runs)["failures"]
if failures:
    st.bar_chart(pd.Series(failures, name="runs"), horizontal=True, height=40 + 36 * len(failures))
else:
    st.caption("no failed runs in this group")

n_section = 4
bench_groups = [g for g in groups if g != "demo"]
if len(bench_groups) > 1:
    section(n_section, "compare")
    n_section += 1
    picked = st.multiselect("Benchmark runs", bench_groups, default=bench_groups[-2:])
    rows = {}
    for g in picked:
        s = data.summarize(load(g))
        rows[g] = {"red→green rate": s["rate"], "median $/issue": s["median_usd"], "total $": s["total_usd"], "attempted": s["attempted"]}
    if rows:
        cmp = pd.DataFrame(rows).T
        st.dataframe(cmp)
        a, b = st.columns(2, gap="large")
        a.bar_chart(cmp["red→green rate"], height=220)
        b.bar_chart(cmp["median $/issue"], height=220)

section(n_section, "runs")
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
picked_rows = st.dataframe(
    table, on_select="rerun", selection_mode="single-row", hide_index=True, key=f"table-{group}",
    column_config={"$": st.column_config.NumberColumn(format="$%.3f"), "seconds": st.column_config.NumberColumn(format="%.0fs")},
)
selected = picked_rows.selection.rows[0] if picked_rows.selection.rows else 0
run = runs[selected]

section(n_section + 1, f"detail · {escape(run['name'])}")
html(step_bar(run))
issue = run["text"].get("issue.md")
if issue is None and group == "demo" and (ROOT / "demo" / "issues" / f"{run['name']}.md").exists():
    issue = (ROOT / "demo" / "issues" / f"{run['name']}.md").read_text()

tabs = st.tabs(["PR body", "Issue", "Repro test", "Red log", "Patch", "Green log", "Model calls"])
text = {**run["text"], "issue.md": issue}
for tab, (name, lang) in zip(tabs, [("summary.md", None), ("issue.md", "markdown"), ("repro_test.py", "python"),
                                    ("red.log", "text"), ("patch.diff", "diff"), ("green.log", "text")]):
    with tab:
        if not text.get(name):
            st.caption("not produced by this run")
        elif lang is None:
            st.markdown(text[name])  # model-written; plain st.markdown keeps HTML off
        else:
            st.code(text[name], language=lang, wrap_lines=True)
with tabs[6]:
    if run["ledger"]:
        calls = pd.DataFrame(run["ledger"])
        calls["model"] = calls["model"].map(lambda m: data.MODEL_NAMES.get(m, m))
        calls["t"] = (calls["ts"] - calls["ts"].iloc[0]).round(1)
        st.dataframe(calls[["t", "phase", "model", "in_tokens", "out_tokens", "latency_ms", "cost_usd"]], hide_index=True)
    else:
        st.caption("not produced by this run")
