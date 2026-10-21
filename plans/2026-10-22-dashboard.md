# Plan: Streamlit dashboard, files only

Merged from the first draft and the user's review (2026-10-22). DECISIONS.md wins where they differ.

## Goal

The dashboard from ARCHITECTURE.md, reading the run folders under `out/` directly. No database,
Streamlit on localhost only, telemetry off, nothing hosted.

## Data (already on disk)

| File | Gives |
|---|---|
| `result.json` | status, abort reason, iterations, escalations, cost, seconds |
| `ledger.jsonl` | one row per LLM call: phase, model, tokens, latency, cost (written live) |
| `events.jsonl` (new) | one row per phase change plus an end row, written live by the agent |
| `issue.md`, `repro_test.py`, `red.log`, `patch.diff`, `green.log`, `summary.md` | run detail |
| `red2fix.<run-id>.json` (path unverified) | official SWE-bench resolved ids |

Run folders are `out/<n>/` (demo) and `out/bench/<run-id>/<instance>/`. Every run's `out` is a bind
mount, so the agent writes `events.jsonl` straight into it. No log tailing is needed: there are no
Serverless Jobs (see DECISIONS).

## Files

- `agent/main.py`: `Run.phase` appends a `phase` event and `run_agent` appends an `end` event.
- `bench/run.py`: `run_one` writes `result.json` itself when the image build fails or the agent
  leaves none, and clears a stale one first. Without this, crashed instances vanish from `report()`.
- `dashboard/data.py`: pure loaders: `find_runs`, `load_run`, `summarize`, `cost_by`, `total_spend`,
  `official`. Half-written JSONL lines are skipped.
- `dashboard/launch.py`: a single-run launcher for the demo.
- `dashboard/app.py`: the page.
- `.streamlit/config.toml`: localhost, no usage stats.
- `pyproject.toml`: a `ui` dependency group with `streamlit`. The agent image is unchanged.
- `tests/test_dashboard.py`: data, launcher, and an AppTest smoke test.

## Page

- **Sidebar:** pick a group (`demo` or a bench run-id). A "Refresh every 3 s" toggle. When
  `RED2FIX_ENABLE_LAUNCH=1`, a demo-issue picker and a Run button.
- **Live fragment** (`st.fragment(run_every=3)`, so the rest of the page doesn't flicker):
  - headline tiles: attempted; own repro red→green; official resolved or "not scored"; median $
    and time per issue; "spend in out/" against $50;
  - for each running run, a step bar (Triage → Localize → Reproduce → Fix → Confirm → Done) with
    elapsed time, fix iteration, cost so far, and the latest model call.
- **Static:**
  - cost by model (stacked per run) and cost by phase;
  - failure breakdown by abort reason;
  - comparison across bench run-ids;
  - instance table with row selection;
  - run detail: step bar, LLM-call timeline, issue, repro test, red log, patch, green log, PR body.
- **Loading:** `st.cache_data`, keyed on folder modification time.
- **Untrusted text:** model output and issue text render as code blocks, or as markdown with HTML
  off.

## Launcher (demo only)

- Off unless `RED2FIX_ENABLE_LAUNCH=1`.
- Takes only an issue number that exists in `demo/issues/`. It runs `scripts/run_local.sh <n>`
  detached, with arguments passed as a list.
- One run at a time: `out/.launch.lock` holds the process ID, and the button is disabled while
  that process is alive.
- Issue URLs come with the publisher slice, which brings the GitHub fetch and clone. No benchmark
  launches from the UI.

## Not doing

- Hosting or a snapshot deploy: the user asked for everything to stay local. Screenshots go in the
  README instead.
- A `mode` label per bench run: deferred to the Ultra-only slice, which is what creates a second
  mode. Until then the comparison is labelled by run-id.
- A live tail of test output: the step bar, cost and the latest model call carry the live view.

## Steps

1. Fix `run_one` so it always leaves a `result.json`.
2. Agent `events.jsonl`.
3. `data.py`, `launch.py` and tests.
4. `app.py` and the AppTest smoke test.
5. DECISIONS entry. The README line waits for the README slice; the run command is in the `dashboard/app.py` docstring.
6. After the pilot run and `score.sh`: verify the official report path and fix `score.sh`.

## Risks

- The SWE-bench report path is unverified; `official()` returns `None` until it is found.
- A run killed with `-9` never writes its end event or `result.json`, so it shows as running
  forever. Bench runs are covered by step 1; for a demo run, delete or rerun its folder.
