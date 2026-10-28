# Prompt

Prepare the repo for submission. Read docs/spec/red2fix-prd.md, docs/spec/DECISIONS.md,
docs/bench-analysis.md, out/bench/rv-full/review_report.md, config.py and examples/github/README.md first.
Save this prompt as plans/2026-10-28-submission.md.

1. LICENSE: keep the existing MIT LICENSE (it came from the GitHub repo); don't overwrite it. Make sure it
   is at the repo root after merging with origin/main.
2. README.md, top to bottom:
   - One line: "Red2Fix doesn't give an opinion on your pull request. It proves it."
   - 30-second flow (PRD §6 diagram, simplified) and the verdict table (PRD §6.1).
   - Live demo: link github.com/nufii45/red2fix-minikit and its six PRs, one line each with its verdict
     (good merged, wrong, breaks, restricted, inject, inject2). Dashboard screenshots from docs/screenshots/.
   - "How we use NVIDIA Nemotron on Nebius Token Factory": routing table with the real model IDs from
     config.py, what each model does and why, median cost and time per review from the report, and the
     call counts by model.
   - "Results on SWE-bench Lite": method (20 instances, gold patch + one failed public patch each, ground
     truth from the dataset and official reports, no hidden tests seen). Then a table with BOTH views:
     original labels (false approvals 2/20) and cleaned labels (0/16 truly failed, of which 10 got a verdict,
     6 were infrastructure errors). Gold approvals 3/20. Unproven and error counts. State plainly that the
     cleaned-labels rule was defined after inspecting the results and then applied to all 20. Show original
     and recomputed verdicts if the same-failure→unproven rule changed any.
   - "Limitations", stated plainly: the proof is only as strong as the test Red2Fix writes (use the gold
     doesnt_fix causes from docs/bench-analysis.md, e.g. wrong expected values); interface visible,
     implementation hidden; same-repo PRs only and the runner holds the API key (pull_request_target, trusts
     collaborators); Python and pytest only; 9 reviews lost to amd64 emulation crashes on an arm64 Mac;
     no Nebius Serverless Jobs used (inference only, via Token Factory).
   - Quick start: local review of a demo PR with Docker (scripts/review_local.sh), the dashboard, and the
     GitHub Action setup (link examples/github/README.md). Every command must work as written; run the
     non-paid ones to check.
   - What existed before the submission period and what was built during it, using git log dates (the
     issue-to-fix agent vs review mode, GitHub gate, bench evaluation, dashboard review view, suggest-fix).
   - Next steps: sandbox without secrets, native amd64 bench, GitHub App, more languages, desktop companion.
3. "Feedback on Token Factory and Nemotron" section from DECISIONS.md: the lowercase Nano ID that 404s,
   native tool_calls on all three models, Ultra exploring until the step limit under tool use, median
   latency per model from the ledgers.
4. Secrets and identity check: git ls-files | grep -iE 'env|secret|key'; grep tracked files for "sk-" and
   key-like strings; git log --format='%ae' | sort -u must show only bufiimman45@gmail.com (report any
   other email, don't rewrite history without asking me).
5. uv run pytest -q must be green.
6. Show me the README rendered as text and the list of files that would be pushed. Don't push until I say so.

# Submission prep (README, feedback, secrets check)

## Context
Hackathon deadline is 2026-10-30. There's no root README yet. The repo must be ready to push publicly: README, license, a feedback section and a clean secrets/identity check. Nothing is pushed until the user says so. On execution, this file becomes `plans/2026-10-28-submission.md`, containing the user's prompt text plus notes, and is committed with the work.

## Facts already checked (read-only)
- **origin/main** has no commits that local main lacks. Local is 3 ahead (77c1029, dd3146a, bc14ffb). LICENSE (MIT, merged in 084c10a) is tracked at the root, so nothing changes there.
- **`git log --format='%ae'`** shows only `bufiimman45@gmail.com`. Committer emails also include `noreply@github.com`, from GitHub's web-created LICENSE commit 918482a. I'll report that without rewriting anything.
- **`git ls-files | grep -iE 'env|secret|key'`** returns nothing. A grep for `sk-…` and `api_key = "…"` in tracked files returns nothing. `.env`, `*.jsonl` and `out/` are gitignored.
- **Median latency per model** (all ledgers, `latency_ms`):

  | Model | Median | Calls |
  |---|---|---|
  | Ultra | 2.4 s | 2345 |
  | Super | 1.8 s | 66 |
  | Nano | 3.1 s | 86 |

  In rv-full: Ultra 2.6 s / 1565 calls, Nano 3.2 s / 40 calls, Super 0 (suggest-fix was off).
- **rv-full:**
  - Median $0.464 and 198 s per review; $19.49 total.
  - Gold approvals 3/20.
  - False approvals 2/20 under original labels and 0/16 under cleaned labels.
  - Recomputed changes: gold pytest-7432 and 7490, and failed astropy-14995, go from doesnt_fix to unproven.
  - Unproven goes from 12 stored to 15 recomputed (I'll recount with a script). Errors: 9.
  - Recomputed verdicts, gold: proven 3, doesnt_fix 5, unproven 8, breaks 1, error 3.
  - Recomputed verdicts, failed: proven 2, doesnt_fix 3, breaks 2, unproven 7, error 6.
- **Git dates:**
  - 2026-10-21/22: the issue-to-fix agent, SWE-bench picker/runner/scorer, Streamlit dashboard and seeded demo bugs.
  - 2026-10-27/28: review mode, the GitHub gate, bench review mode and failed patches, rv-full, the dashboard review view, same-failure→unproven, suggest-fix and the minikit move.

## Corrections to the prompt (README will state the accurate version)
1. **"9 reviews lost to amd64 emulation crashes" is not accurate** (DECISIONS 2026-10-28). The 9 errors split as follows:
   - 4 emulation: xarray-4094 ×2 segfault, seaborn-3407 ×2 suite timeout.
   - 2 bench input: the failed patches for 12907 and 3190 don't apply with `git apply`.
   - 3 budget cap: 6938 failed, pylint-7080 gold and failed.
2. **"6 were infrastructure errors"** among the 16 truly failed: those 6 are 2 emulation (3407, 4094), 2 patch-apply (12907, 3190) and 2 budget cap (6938, 7080). The README says "6 ended in error" with that split.
3. **DECISIONS line 41 says "gold doesnt_fix 8"**, but the stored table has 7. I'll add a one-line correction entry and leave the old line as it is.
4. **The PRD §6 diagram is stale.** It shows `pull_request` and VERIFY_RED on Nano. The README diagram will use the current facts: `pull_request_target`, VERIFY_RED on Ultra, and suggest-fix off by default and never pushed.

## Changes
1. **`README.md` (new, root), sections in the order the prompt gives:**
   - **Tagline.**
   - **Flow and verdicts:** a simplified flow diagram, then the §6.1 verdict table.
   - **Live demo:**
     - Links to the minikit repo and PRs #4–#9, with the verdicts from DECISIONS 2026-10-28. #4 is ✅ but not merged yet, since auto-merge wasn't enabled, so it won't be described as "merged" unless the user merges it first.
     - The 5 screenshots in `docs/screenshots/`. Look at each one first for emails or keys.
   - **Nemotron on Token Factory:**
     - Routing table from `config.py` `MODELS`/`ROUTES`, with the exact IDs.
     - Why each model is used.
     - Median cost and time, call counts by model, and median latency.
     - A note that Super's price is unverified (`config.py` comment).
   - **SWE-bench Lite results:**
     - Method.
     - One table with original labels and cleaned labels, for both stored and recomputed verdicts.
     - Gold approvals, unproven and error counts.
     - The cleaned-labels rule, stated as defined after inspecting the results and then applied to all 20.
     - A table of the 3 changed verdicts.
     - Links to `docs/bench-analysis.md`.
   - **Limitations:**
     - The proof is only as strong as the test. Use the analysis counts: 5 wrong expected values, 1 different code path, 1 broken test.
     - The interface is visible but the implementation is hidden.
     - Same-repo PRs only, and the runner holds the key (`pull_request_target`, trusts collaborators).
     - Python and pytest only.
     - The accurate 9-error split from the corrections above.
     - Inference only via Token Factory, with no Serverless Jobs.
   - **Quick start:**
     - `.env` with `NEBIUS_API_KEY`, then `scripts/review_local.sh good`.
     - Dashboard: `uv run streamlit run dashboard/app.py`.
     - Link to `examples/github/README.md`.
     - `uv run pytest -q` and `uv run bench/report_review.py rv-full`.
   - **Before and during the submission period:** a table built from git dates.
   - **Next steps.**
   - **Feedback on Token Factory and Nemotron:**
     - The lowercase Nano ID that 404s.
     - Native `tool_calls` on all three models.
     - Ultra exploring until the step limit (pilots 1–3: all 13/15 steps on grep/read, never submitting until forced).
     - The latency table.
   - **License line.**
2. **`scripts/review_local.sh`:** add `inject2` to the usage comment if `demo/prs/inject2` exists.
3. **`docs/spec/DECISIONS.md`:** add the gold doesnt_fix 7-not-8 correction, plus one line recording the README and submission prep.
4. **`plans/2026-10-28-submission.md`:** the prompt text and notes. Then delete this plan-mode file.

## Verification (no paid calls)
- **Dashboard:**
  - `uv run streamlit run dashboard/app.py --server.headless true` in the background.
  - `curl -s localhost:8501` returns 200, then stop it.
- **Docker and the review script:**
  - `docker build -q -t red2fix-agent .` succeeds.
  - `scripts/review_local.sh` with no argument prints usage. The paid run isn't repeated, because the output already exists.
- **Bench report:** `uv run bench/report_review.py rv-full` regenerates the report, and its numbers match the README.
- **Demo links:** `gh pr list -R nufii45/red2fix-minikit --state all` (read-only) confirms the PR links and states.
- **README links:** every relative link points to a tracked file.
- **Secrets and identity:** rerun the secret greps and `git log --format='%ae' | sort -u`.
- **Tests:** `uv run pytest -q` is green.
- **Commit** locally with the personal identity and the Co-Authored-By trailer. Don't commit `plans/red2fix-v2-build-prompts.md`.
- **Show the user** the README as plain text and `git ls-files` (the files that would be pushed), plus `git log origin/main..main`. Don't push.

Skipped: video, desktop companion, merging #4 and enabling auto-merge on it (outward actions, not asked).
