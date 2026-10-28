"""Red2Fix local run viewer: a dev tool that reads the run folders in out/, nothing else. The public interface is
the Next.js site in web/. Styled bryl-minimal (dashboard/style.css).

Run: uv run streamlit run dashboard/app.py   (RED2FIX_ENABLE_LAUNCH=1 adds the demo Run and Review buttons)
Deep link: ?run=<path under out/>, e.g. ?run=review-good or ?run=bench/rv-full/psf__requests-2317/gold
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
SITE_URL = "https://TODO-site-url"  # TODO: the deployed site (web/), also in README.md

st.set_page_config(page_title="Red2Fix local run viewer", layout="wide")
st.markdown(f"<style>{(Path(__file__).parent / 'style.css').read_text()}</style>", unsafe_allow_html=True)


def html(markup):
    """Our own markup only; every run-derived value in it goes through escape()."""
    st.markdown(markup, unsafe_allow_html=True)


def section(n, name):
    html(f'<div class="r2f-section">{n:02d} — {name}</div>')


@st.cache_data(show_spinner=False)
def _load(run_dir, mtime):
    return data.load_run(Path(run_dir))


@st.cache_data(show_spinner=False)
def _load_review(run_dir, mtime):
    return data.load_review(Path(run_dir))


def load(group):
    return [(_load_review if data.is_review(d) else _load)(str(d), data.mtime(d))
            for g, d in data.find_runs(OUT) if g == group]


def step_bar(run):
    r = run["result"]
    steps, names = (data.REVIEW_STEPS, data.REVIEW_STEP_NAMES) if "review" in run else (data.STEPS, data.STEP_NAMES)
    current = steps.get(r.get("phase"))
    idx = names.index(current) if current else -1
    pills = []
    for i, name in enumerate(names):
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
    elapsed = time.time() - events[0]["t"] if events else 0
    last = run["ledger"][-1] if run["ledger"] else None
    call = f" · last call {escape(last['phase'])} on {escape(data.MODEL_NAMES.get(last['model'], last['model']))}" if last else ""
    iteration = "" if "review" in run else f" · fix iteration {sum(e.get('name') == 'FIX' for e in events)}"
    return (
        f'<div class="r2f-card r2f-in"><div class="head"><span class="name">{escape(run["name"])}</span>'
        f'<span class="r2f-label">live</span></div>{step_bar(run)}'
        f'<div class="r2f-label">{elapsed:.0f}s elapsed{iteration} · '
        f'${run["result"].get("cost_usd", 0):.3f} so far{call}</div></div>'
    )


def stat(label, value, sub=""):
    return (f'<div class="r2f-stat"><div class="r2f-label">{label}</div><div class="v">{value}</div>'
            f'<div class="s">{sub}</div></div>')


def verdict_card(run):
    rv = run["review"]
    if rv is None:
        return f'<div class="r2f-card">{step_bar(run)}<div class="r2f-label">review in progress</div></div>'
    p = rv.get("proof") or {}
    rows = [
        ("claim", rv.get("claim") or "—"),
        ("base · must fail", p.get("base") or "—"),
        ("head · must pass", p.get("head") or "not run"),
        ("new failing tests", ", ".join(rv.get("suite", {}).get("new_failures", [])) or "none"),
        ("restricted paths", ", ".join(rv.get("restricted_paths_touched", [])) or "none"),
    ]
    searches = "".join(
        f'<div class="r2f-kv"><span class="r2f-label">search · {escape(str(s.get("phase") or "").lower())}</span><span>'
        f'{escape(str(s.get("query") or ""))} → '
        + (" · ".join(f'<a href="{escape(u)}" target="_blank">{escape(u)}</a>' for u in s.get("urls") or []
                      if str(u).startswith("https://")) or escape(str(s.get("status") or "")))
        + "</span></div>"
        for s in rv.get("web_searches") or []
    )
    calls = rv.get("calls") or {}
    mix = " / ".join(f"{k} {n}" for k, n in calls.items() if n) or "no model calls"
    links = [(label, rv[key]) for key, label in (("pr_url", "pull request ↗"), ("run_url", "workflow run ↗"),
                                                      ("trace_url", "View trace in LangSmith ↗"))
             if str(rv.get(key) or "").startswith("https://")]
    return (
        '<div class="r2f-card r2f-in"><div class="head"><span class="name">'
        f'{escape(run["name"])}</span><span class="r2f-label">{escape(rv.get("spec_source") or "")}</span></div>'
        f'<div class="r2f-verdict">{escape(data.LABELS.get(rv["verdict"], rv["verdict"]))}</div>'
        f'<div class="r2f-note">{escape(rv.get("verdict_reason") or "")}</div>'
        + "".join(f'<div class="r2f-kv"><span class="r2f-label">{k}</span><span>{escape(str(v))}</span></div>' for k, v in rows)
        + searches
        + f'<div class="r2f-kv"><span class="r2f-label">cost</span><span>${rv.get("cost_usd", 0):.3f} · '
          f'{rv.get("seconds", 0):.0f}s · {escape(mix)}</span></div>'
        + (f'<div class="r2f-kv"><span class="r2f-label">links</span><span>'
           + " · ".join(f'<a href="{escape(url)}" target="_blank">{label}</a>' for label, url in links)
           + "</span></div>" if links else "")
        + "</div>"
    )


query_run = st.query_params.get("run")
query_dir = (OUT / query_run).resolve() if query_run else None  # resolved, so ?run=../.. can't leave out/

# Sidebar
groups = sorted({g for g, _ in data.find_runs(OUT)}, key=lambda g: (g != "demo", g != "reviews", g))
if os.environ.get("RED2FIX_ENABLE_LAUNCH") == "1":
    with st.sidebar:
        pid = launch.running_pid(OUT / ".launch.lock")
        html('<div class="r2f-section" style="margin-top:0">start a demo run</div>')
        n = st.selectbox("Demo issue", launch.demo_issues(ROOT))
        if st.button("Run ↗", disabled=bool(pid), type="primary"):
            try:
                launch.start(n, ROOT)
                st.rerun()
            except (ValueError, RuntimeError) as e:
                html(f'<div class="r2f-note">{escape(str(e))}</div>')
        prs = launch.demo_prs(ROOT)
        if prs:
            pr = st.selectbox("Demo PR", prs)
            if st.button("Review ↗", disabled=bool(pid)):
                try:
                    launch.start_review(pr, ROOT)
                    st.rerun()
                except (ValueError, RuntimeError) as e:
                    html(f'<div class="r2f-note">{escape(str(e))}</div>')
        if pid:
            st.caption(f"run in progress · pid {pid} · see out/*/run.log")

html('<header class="r2f-hero r2f-in"><div class="r2f-label">nvidia × nebius · coding &amp; agentic engineering</div>'
     '<div class="r2f-title">Red2Fix local run viewer</div><p class="r2f-lede">Pull request in, a test written from the issue, '
     'red on base and green on the PR, then a verdict. Every number on this page is read from <code>out/</code>.</p></header>')
html(f'<div class="r2f-note">Internal tool; the public site is <a href="{SITE_URL}">{SITE_URL}</a></div>')

if not groups:
    html('<div class="r2f-note">No runs in out/ yet. Start one with scripts/run_local.sh 1, scripts/review_local.sh good '
         'or uv run bench/run.py.</div>')
    st.stop()

query_group = data.group_of(query_dir, OUT) if query_dir and query_dir.is_relative_to(OUT) and query_dir.is_dir() else None
with st.sidebar:
    html('<div class="r2f-section">view</div>')
    group = st.selectbox(
        "Runs", groups, index=groups.index(query_group) if query_group in groups else 0,
        format_func=lambda g: {"demo": "demo issues", "reviews": "demo reviews"}.get(g, f"bench · {g}"),
    )
    live = st.toggle("Refresh every 3 s")

reviewing = any("review" in r for r in load(group))


@st.fragment(run_every=3 if live else None)
def overview():
    runs = load(group)
    section(1, "overview")
    if reviewing:
        counts = data.verdict_counts(runs)
        done = [r["review"] for r in runs if r.get("review")]
        med = lambda key: pd.Series([rv.get(key, 0) for rv in done]).median() if done else 0  # noqa: E731
        html('<div class="r2f-stats r2f-in" style="animation-delay:120ms">'
             + "".join(stat(escape(data.LABELS[v].split(" ", 1)[1].lower()), counts[v]) for v in data.VERDICTS)
             + stat("median $/review", f"${med('cost_usd'):.3f}")
             + stat("median time/review", f"{med('seconds'):.0f}s")
             + stat("spend in out/", f"${data.total_spend(OUT):.2f}", f"of ${BUDGET_USD:.0f} credit")
             + "</div>")
    else:
        s = data.summarize(runs)
        resolved = data.official(group) if group != "demo" else None
        official = "—" if resolved is None else f"{len(resolved & {r['name'] for r in runs})}/{s['attempted']}"
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
n_section = 2

report = data.bench_report(OUT / "bench" / group) if group not in ("demo", "reviews") else None
if report:
    section(n_section, "bench · does the verdict match the ground truth?")
    n_section += 1
    st_ = report["settings"]
    tiles = [
        ("false approvals · blocker", f"{len(st_['blocker']['false_approvals'])}/{st_['blocker']['failed_total']}",
         ", ".join(st_["blocker"]["false_approvals"]) or "failed patches marked proven"),
        ("false approvals · warning", f"{len(st_['warning']['false_approvals'])}/{st_['warning']['failed_total']}",
         ", ".join(st_["warning"]["false_approvals"]) or "unrelated_change = warning"),
        ("gold approvals · blocker", f"{st_['blocker']['gold_approvals']}/{st_['blocker']['gold_total']}", "correct patches marked proven"),
        ("gold approvals · warning", f"{st_['warning']['gold_approvals']}/{st_['warning']['gold_total']}", ""),
        ("unproven", report["unproven"], f"of {report['reviews']} reviews"),
        ("errors", report["errors"], ""),
        ("median $/review", f"${report['median_usd']:.3f}", f"total ${report['total_usd']:.2f}"),
        ("median time/review", f"{report['median_s']:.0f}s", ""),
    ]
    html('<div class="r2f-stats r2f-in">' + "".join(stat(escape(a), escape(str(b)), escape(c)) for a, b, c in tiles) + "</div>")
    per = pd.DataFrame([
        {"instance": i, "gold": k.get("gold", {}).get("verdict", "—"), "failed": k.get("failed", {}).get("verdict", "—"),
         "$": sum(v.get("cost_usd") or 0 for v in k.values()), "seconds": sum(v.get("seconds") or 0 for v in k.values())}
        for i, k in sorted(report["instances"].items())
    ])
    st.dataframe(per, hide_index=True, column_config={"$": st.column_config.NumberColumn(format="$%.3f"),
                                                       "seconds": st.column_config.NumberColumn(format="%.0fs")})

section(n_section, "cost")
n_section += 1
left, right = st.columns(2, gap="large")
with left:
    html(f'<div class="r2f-label">by model, per {"review" if reviewing else "run"}</div>')
    by_model = pd.DataFrame(data.cost_by(runs, "model")).T.fillna(0)
    if not by_model.empty:
        st.bar_chart(by_model, y_label="usd", height=260)
with right:
    html('<div class="r2f-label">by phase</div>')
    by_phase = pd.DataFrame(data.cost_by(runs, "phase")).T.fillna(0)
    if not by_phase.empty:
        st.bar_chart(by_phase, y_label="usd", height=260)

if not reviewing:
    section(n_section, "failures")
    n_section += 1
    failures = data.summarize(runs)["failures"]
    if failures:
        st.bar_chart(pd.Series(failures, name="runs"), horizontal=True, height=40 + 36 * len(failures))
    else:
        st.caption("no failed runs in this group")

bench_groups = [g for g in groups if g not in ("demo", "reviews")]
if len(bench_groups) > 1 and not reviewing:
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
if reviewing:
    table = pd.DataFrame([{
        "run": r["name"],
        "verdict": data.LABELS.get(r["review"]["verdict"], r["review"]["verdict"]) if r.get("review") else r["result"]["status"],
        "reason": (r.get("review") or {}).get("verdict_reason") or "",
        "$": (r.get("review") or r["result"]).get("cost_usd", 0),
        "seconds": (r.get("review") or r["result"]).get("seconds"),
    } for r in runs])
else:
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
query_name = data.run_name(query_dir) if query_group == group else None
default = next((i for i, r in enumerate(runs) if r["name"] == query_name), 0)
selected = picked_rows.selection.rows[0] if picked_rows.selection.rows else default
run = runs[selected]

section(n_section + 1, f"detail · {escape(run['name'])}")
if "review" in run:
    html(step_bar(run))
    html(verdict_card(run))
    rv = run["review"] or {}
    findings = rv.get("findings") or []
    if findings:
        # An HTML table, not st.dataframe: notes are the point and a dataframe cuts them off. Every value is escaped.
        cells = "".join(
            f"<tr><td>{escape(str(f.get('severity') or ''))}</td><td>{escape(str(f.get('rule') or ''))}</td>"
            f"<td>{escape((str(f.get('diff_file') or f.get('file') or '') + ':' + str(f.get('line') or '')).strip(':'))}</td>"
            f"<td>{escape(str(f.get('note') or ''))}"
            + (f' <a href="{escape(f["source"])}" target="_blank">source ↗</a>' if str(f.get("source") or "").startswith("https://") else "")
            + "</td></tr>"
            for f in findings
        )
        html('<div class="r2f-label" style="margin-top:1rem">findings</div><table class="r2f-table"><tr><th>severity</th>'
             f'<th>rule</th><th>where</th><th>note</th></tr>{cells}</table>')
    if rv.get("dropped_findings"):
        st.caption(f"{len(rv['dropped_findings'])} finding(s) dropped: their quote was not in the diff")
    if run["text"].get("repro_test.py"):
        html('<div class="r2f-label" style="margin-top:1rem">repro test, written from the spec without seeing the diff</div>')
        st.code(run["text"]["repro_test.py"], language="python", wrap_lines=True)
    tabs = st.tabs(["PR comment", "Spec", "Patch", "Red log", "Head log", "Model calls"])
    for tab, (name, lang) in zip(tabs, [("review.md", None), ("spec.md", "markdown"), ("pr.patch", "diff"),
                                        ("red.log", "text"), ("head.log", "text")]):
        with tab:
            if not run["text"].get(name):
                st.caption("not produced by this run")
            elif lang is None:
                st.markdown(run["text"][name])  # plain st.markdown keeps HTML off
            else:
                st.code(run["text"][name], language=lang, wrap_lines=True)
    calls_tab = tabs[5]
else:
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
    calls_tab = tabs[6]
with calls_tab:
    if run["ledger"]:
        calls = pd.DataFrame(run["ledger"])
        calls["model"] = calls["model"].map(lambda m: data.MODEL_NAMES.get(m, m))
        calls["t"] = (calls["ts"] - calls["ts"].iloc[0]).round(1)
        st.dataframe(calls[["t", "phase", "model", "in_tokens", "out_tokens", "latency_ms", "cost_usd"]], hide_index=True)
    else:
        st.caption("not produced by this run")
