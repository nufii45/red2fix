Read dashboard/app.py, dashboard/data.py, tests/test_dashboard.py and plans/2026-10-27-review-core.md.
Save this prompt as plans/2026-10-29-dashboard-review.md and implement it.

## Goal
The dashboard shows review runs as well as fix runs, with no new data sources.
1. data.py: find review runs (any out dir with review.json, including out/review-*/ and the bench layout
   out/bench/<run>/<instance>/<kind>/). Add load_review(), cached on mtime like the existing loaders.
2. Live panel: the phase bar learns the review phases (TRIAGE … APPLY_PR, HEAD_CHECK, REVIEW, VERDICT).
3. Verdict card for a selected review: large verdict with emoji, claim, red line and green line, new
   failures, findings table, restricted paths, cost and model mix, the repro test in a code block, and
   links to the PR or workflow run when review.json has them.
4. Bench page: if review_report.json exists, show the headline counts as tiles (false approvals first),
   the per-instance table, and a bar of cost per review by model.
5. Keep the existing monochrome theme and the RED2FIX_ENABLE_LAUNCH rules. If the launcher is enabled,
   add a select of demo/prs/* that starts scripts/review_local.sh with the same one-run lock.

## Done when
AppTest smoke test passes for a fixture review run and a fixture bench report; `uv run pytest -q` green;
screenshots of the verdict card for the five demo PRs saved to docs/screenshots/ for the README.

---

## Implementation notes (Claude)

**Context.** Review mode, the GitHub gate and the review bench all write `review.json`, but the dashboard
only understands fix runs: `out/review-*` dirs land in the "demo" group mixed with fix runs, and the bench
review layout (4 levels deep) isn't found at all. The full bench run `rv-full` is in progress.

**Freeze guard.** `bench/run.py` builds each instance's image from the working tree when that instance
starts, copying `agent/` and `config.py`. Until `rv-full` finishes, this slice touches only `dashboard/`,
`tests/test_dashboard.py`, `docs/screenshots/` and the plan. No change to `agent/`, `config.py`, `bench/`
or `scripts/` (`review_local.sh` already exists and is reused as is).

**data.py** (no Streamlit, testable)
- `is_review(run_dir)`: `review.json` exists, or the name starts with `review-`, or it's a bench kind dir
  (`gold`/`failed`), so live reviews without `review.json` yet are recognised.
- `group_of`: `out/review-*` → group `"reviews"`; `out/bench/<run>/<inst>/<kind>` → `<run>` (4 parts);
  existing 1- and 3-part rules unchanged. Run names in a bench review group are `<instance>/<kind>`.
- `REVIEW_STEPS` / `REVIEW_STEP_NAMES` next to `STEPS`: Triage (TRIAGE, BASELINE), Localize, Reproduce
  (REPRODUCE, VERIFY_RED, COMMIT_REPRO), Head (APPLY_PR, HEAD_CHECK), Review (REVIEW), Verdict (VERDICT, DONE).
- `load_review(run_dir)`: `load_run()`'s dict plus `"review"` (parsed review.json or None) and text of
  spec.md, pr.patch, repro_test.py, red.log, head.log, review.md. Tolerates the older review.json files
  (no `dropped_findings`, no `quote`, no `proof.result`).
- `verdict_counts(reviews)` for the overview; `bench_report(group_dir)` reads `review_report.json` if present.

**app.py**
- `load(group)` dispatches to a cached `_load_review(run_dir, mtime)` for review runs (same pattern as `_load`).
- `step_bar(run)` picks the step map by kind; live cards work for reviews (the "fix iteration" text only for fix runs).
- Review groups: overview tiles are verdict counts (proven, needs review, unproven, doesn't fix, breaks
  tests, error) plus median $ and time and spend; then the runs table (run, verdict, reason, $, s); then the
  **verdict card** for the selected row: big `LABEL` line, claim, base (must fail) and head (must pass)
  lines, new failures, restricted paths, findings table (severity, rule, where, note; dropped findings in
  a caption count), cost and model mix from `calls`, repro test in `st.code`, and links when review.json
  has `pr_url` / `run_url` (nothing writes those yet; adding `--pr-url/--run-url` to agent.review and the
  workflow is a follow-up after `rv-full`, because it touches `agent/`). Tabs keep spec, patch, red/head logs, model calls.
- Bench review group with `review_report.json`: tiles in this order: false approvals (blocker),
  false approvals (warning), gold approvals (blocker), gold approvals (warning), unproven, errors,
  median $/review; the per-instance table; a stacked bar of cost per review by model via `data.cost_by`.
- Monochrome: reuse `.r2f-card`, `.r2f-stat`, `.r2f-label`, `escape()` for every review-derived value; add
  only a `.r2f-verdict` size rule to `style.css`. Emoji stay grayscale (existing filter).
- Deep link: `?run=<path under out/>` preselects the group and row (needed for screenshots; harmless otherwise).
- Launcher (only with `RED2FIX_ENABLE_LAUNCH=1`): a second select of `demo/prs/*` and a "Review ↗" button
  calling new `launch.start_review(name, root)`: same `out/.launch.lock`, QUEUED event in
  `out/review-<name>/`, runs `scripts/review_local.sh <name>` detached. Both buttons disabled while a run holds the lock.

**Tests** (`tests/test_dashboard.py`, no model calls)
- Fixture adds `out/review-good/` (review.json, events, ledger, repro) and a bench review run
  `out/bench/rv/a__b-1/{gold,failed}/` plus `out/bench/rv/review_report.json`.
- `find_runs` groups (`reviews`, `rv`, names `a__b-1/gold`), `load_review` on an old-style review.json,
  review step bar for a live review.
- AppTest: reviews group renders the verdict card (label, claim, a finding); rv group renders the
  false-approval tile first and the instance table; existing two cases still pass.
- `launch.start_review` respects the lock and rejects unknown names.

**Screenshots.** `uv run streamlit run dashboard/app.py --server.headless true --server.port 8599`, then
headless Chrome `--screenshot --window-size=1280,2600 --virtual-time-budget=20000` on
`http://localhost:8599/?run=review-<name>` for good, wrong, breaks, restricted, inject →
`docs/screenshots/review-<name>.png`. Check each PNG by eye (Read) before committing. Uses the existing
`out/review-*` results; no new model calls.

**Done when:** `uv run pytest -q` green, five PNGs look right, commit (dashboard, tests, screenshots, plan
renamed to `plans/2026-10-29-dashboard-review.md`). `rv-full` keeps running untouched.
