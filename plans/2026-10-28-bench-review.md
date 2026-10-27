Read docs/spec/red2fix-prd.md §11, bench/run.py, bench/pick.py, bench/Dockerfile.swebench and
plans/2026-10-27-review-core.md. Save this prompt as plans/2026-10-28-bench-review.md and implement it.

## Goal
Review 2 patches per frozen instance (20 instances): the gold patch (ground truth: resolved) and one failed
patch from a public SWE-bench Lite submission (ground truth: not resolved, from that submission's official
results). Report how often Red2Fix's verdict agrees with the ground truth, false approvals first.
The official harness is NOT needed here: ground truth comes from the dataset and the published results.

## Build
1. bench/pick.py: also store each instance's gold `patch` in instances.json (same HF rows API). Don't
   change which 20 instances are picked; assert the ids are unchanged.
2. bench/failed_patches.py: fetch per-system predictions and results for SWE-bench Lite from the
   SWE-bench/experiments GitHub repo (evaluation/lite/<system>/all_preds.jsonl and results/results.json).
   For each of our 20 instances, pick one patch that the official results mark as NOT resolved, preferring
   a strong recent system, and a non-empty patch that applies to the base commit. Write
   bench/failed_patches.json {instance_id: {system, patch}}. First check that the repo layout really is
   like this; if it isn't, stop and tell me what you found instead of guessing.
   Instances with no usable failed patch: record them and continue with gold only.
3. bench/run.py: `--mode fix|review` (default fix, unchanged behaviour) and `--patches gold|failed|both`.
   In review mode, for each instance and patch kind, out dir out/bench/<run-id>/<instance>/<kind>/, write
   spec.md (problem_statement) and pr.patch, and run the review entry point in the instance image with
   --repo /testbed --work /testbed. The image must not get the SWE-bench test_patch.
   The regression scope stays `--suite <test_files>` as in fix mode (pass it through to review).
4. bench/report_review.py: table per instance (gold verdict, failed verdict, cost, time) and the headline:
   - False approvals: failed patches marked proven (n / N), listed by instance.
   - Correct approvals: gold patches marked proven (n / N).
   - Unproven rate, error rate, median $ and seconds per review, model mix.
   Counts only, no percentages. Write out/bench/<run-id>/review_report.md and .json for the dashboard.

## Run order (stop between steps and show me the numbers)
1. Pilot: 3 instances × both patches (`--ids` with 3 fast ones, e.g. the flask and requests ones). Report
   cost per review and wall time.
2. Estimate total = median cost × 40 and time with -j 2. If cost is over $25 or time over 8 hours, propose
   a smaller set before running. Otherwise run all 40 and let it go overnight.

## Tests
pick keeps the ids; failed-patch selection logic on a fixture; run_one review mode writes the right
args (mock subprocess); report math on fixture review.json files.

## Done when
Pilot numbers are in DECISIONS.md, and the full run is either finished or launched with an ETA.

## Addendum (2026-10-27)
1. Add policy key unrelated_change = "blocker" | "warning" (default "blocker"). In decide(), a quoted
   "No changes unrelated to the spec" finding on a non-test .py line becomes a blocker when set to "blocker".
   Tests for both settings.
2. Bench reviews pass spec_source = "issue" (the problem statement is the issue), so the
   PR-description cap never applies. Add a test that asserts it.
3. report_review.py recomputes verdicts from the stored review.json under both unrelated_change settings
   and reports false approvals and gold approvals for each. No extra model calls.

## Implementation notes (Claude)
- STOPPED at step 2 (failed_patches.py), as instructed: SWE-bench/experiments does not have
  evaluation/lite/<system>/all_preds.jsonl. All 84 Lite systems have only README.md, metadata.yaml and
  results/results.json (resolved ids only). Its README: "This repository holds entries, not artifacts";
  predictions live in the repo named by metadata.yaml's `assets` block, or s3://swe-bench-submissions/ for
  entries before mid-2026. Waiting for the user's call.
- "On a non-test .py line" is decided by the file the quote is found in (grounded() records diff_file from
  the diff itself, not the file the model named), and the quote must contain a +/- line. Any value other than
  "warning" counts as "blocker", so a typo fails closed.
- review.json now stores proof.result, so report_review.py can call decide() again without model calls.
- agent.review gains --suite (same rule as main: paths missing on base are dropped).
- Review mode overrides the bench image's entrypoint (/opt/r2f/bin/python -m agent.review) and never
  passes the test_patch; restricted_paths stay at the defaults on the bench.
- After the user chose to probe S3: 81 of 84 Lite systems keep artifacts at
  s3://swe-bench-submissions/lite/<system>/logs/<instance>/{patch.diff,report.json}, public over HTTPS.
  failed_patches.py takes report.json's official `patch_successfully_applied` and `resolved: false`,
  strongest system first. All 20 instances got one (9 systems; ExpeRepair + Claude 4 Sonnet gave 10).
- Caveat: 5 failed patches carry extras that are easy to reject (pytest-7432 a root test file, astropy-12907
  pyproject.toml, pylint-7080 reproduce_issue.py, seaborn-3010 a test edit, seaborn-3190 .gitignore).
  Kept as the officially evaluated patches; report false approvals with and without them.
- No gold patch touches a default restricted path.
