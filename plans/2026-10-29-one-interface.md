# One public interface: the Next.js site (2026-10-29)

## Prompt

Make the Next.js site Red2Fix's only public interface, and demote the Streamlit dashboard to a local dev
tool. Don't delete dashboard/. Save this prompt as plans/2026-10-29-one-interface.md.

1. Gap check first, then show me: list what the Streamlit dashboard shows (overview tiles, cost by model and
   phase, failure breakdown, run comparison, bench page, verdict card, live phase bar, launcher) and, for
   each, whether the site already covers it. Port ONLY what a judge needs and the site lacks. Likely
   candidates: the cost-by-model chart and the failure/verdict breakdown on /results. Skip the launcher,
   the old fix-mode pages and the run comparison.
2. Data: the site reads static JSON from web/public/data/. Make scripts/export_bench.py the single
   exporter (bench results with both label views, the demo PR runs with cost, searches and trace links),
   and make sure every number on /results matches out/bench/rv-full/review_report.md. Add a test that
   compares them.
3. Streamlit becomes dev-only: retitle it "Red2Fix local run viewer", add a one-line banner "Internal tool;
   the public site is <URL>", and keep RED2FIX_ENABLE_LAUNCH off by default. Its tests must still pass.
4. Docs: the README's main flow, screenshots and quick start point only to the site. Add a short
   "Development" section: dashboard/ is a local viewer for bench and demo runs, with the command to start
   it. Remove Streamlit from the README's "Built with" list. Add a DECISIONS.md entry:
   "2026-10-29: the Next.js site is the only public interface; Streamlit is a local dev viewer."
5. Run the full Python suite plus the web typecheck, lint and tests. Commit on the try-it branch. Don't push.

## Gap check

| Dashboard section | Site before | Action |
|---|---|---|
| Overview tiles, review mode (verdict counts, median $/time, spend) | /results tiles and verdict table; /recent | Covered; bench.json was stale (no needs_review), re-exported |
| Overview tiles, fix mode (red→green rate, official score) | None | Skipped (old fix mode) |
| Cost by model | One run only (verdict card); bench showed call counts | Ported: /results "cost by model" table with share bars |
| Cost by phase | None | Skipped (not needed by a judge) |
| Failure breakdown | Hardcoded 4/2/3 text | Ported: `errors_by_cause` from review_report.json |
| Verdict breakdown | /results "every verdict" table | Covered |
| Run comparison | None | Skipped (as asked) |
| Bench report (approvals, label views, per-instance) | /results | Covered |
| Verdict card | verdict-card.tsx on /r/[id] | Covered |
| Live phase bar | StepBar in run-view.tsx | Covered |
| Launcher | Try-it form | Skipped (as asked) |
| Fix-mode detail tabs | None | Skipped (as asked) |
| Demo PR runs side by side | Per run only; demo cost hardcoded | Ported: /results "demo pull requests" table |

## Approach (approved)

- `scripts/export_bench.py` writes bench.json (recomputed verdicts, both label views, `errors_by_cause`,
  `cost_by_model` from the run's ledgers) and demos.json (from the recorded runs in web/fixtures/, which the
  site replays). It is the only writer of web/public/data/.
- /results: hardcoded copy replaced by data; new cost-by-model and demo PR sections; CSS bars, no chart library.
- `tests/test_export_bench.py`: parses review_report.md and compares every number with the export, on a
  fixture run (always) and on out/bench/rv-full vs the committed bench.json (skipped without out/).
- Streamlit: title, hero and banner; launcher stays behind RED2FIX_ENABLE_LAUNCH=1; a test for the default.
- README: Live demo and screenshots point to the site, Quick start runs the site and the exporter, new
  Development section for dashboard/. There was no "Built with" list to edit.
- The site URL isn't known yet: `https://TODO-site-url` in dashboard/app.py (SITE_URL) and README.md.
