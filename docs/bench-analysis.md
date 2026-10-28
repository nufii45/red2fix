# rv-full: gold doesnt_fix analysis and cleaned failed labels

## Context
Analysis of the full review bench `out/bench/rv-full` (commit 0c32486, 2026-10-28), done from stored logs
with no model calls. FAIL_TO_PASS lists and test_patch contents come from SWE-bench Lite. The failed
patches' official report.json files are summarised in `bench/failed_labels.json`
(`uv run bench/failed_patches.py --labels`).

There are **7** gold doesnt_fix reviews (the analysis was asked for 8). No other gold review has that verdict.

## 1–3. Per instance
| Instance | Repro's key assertion → head.log | Official FAIL_TO_PASS | Cause |
|---|---|---|---|
| astropy-12907 | Test 1 (the spec's nested example) passed. Test 2 expects 3×3 for `Linear1D & (Linear1D & cm1)`, which has 4 outputs → `shapes (4, 4), (3, 3) mismatch` | `test_separable[cm6/cm9]`: 4×4 matrices for `rot & sh1 & sh2` | Wrong expected value: the test's own arithmetic, in a case it derived beyond the issue |
| astropy-14365 | Expects `col1_perr`/`col1_nerr` after `read serr 1 2` → `'col1_perr' in ['col1','col1_err',…]`. Test 2 → `ValueError: Inconsistent number of input colnames` | `test_roundtrip[True]`: lowercases the header and round-trips the file | Wrong expected value: SERR is symmetric (`_err`), and two-sided columns come from TERR. Test 2 passes the wrong `names` |
| seaborn-2848 | `pytest.raises(KeyError)` on `_hue_map("virginica")` → `DID NOT RAISE` | `test_hue_order`: points of the unused level have facecolor 0; the legend shows the order | Wrong expected value guessed from the issue. The issue never says what happens to an excluded level, and the gold patch makes it transparent rather than raising |
| flask-4045 | `raises(ValueError, match="Blueprint name.*dot")` → regex doesn't match `'name' may not contain a dot '.' character.` | `test_dotted_name_not_allowed`: bare `pytest.raises(ValueError)` | Wrong expected value: a guessed error message |
| requests-2674 | Mocks `adapter.send` raising urllib3 `TimeoutError`/`DecodeError` and checks `__cause__` → `TimeoutError: Proxy timeout`, `isinstance(None, …)`. **Identical failure on base and head** | 12 httpbin network tests. test_patch adds `test_urllib3_pool_connection_closed`, which isn't in F2P | Tests a different code path. The gold patch handles `ClosedPoolError` in adapters and `DecodeError`/`ReadTimeoutError` in `models.iter_content`. The official F2P signal is network tests, so it's noisy too |
| pytest-7432 | `fnmatch_lines(["*test_skip.py:3*", …])` → `nomatch '*test_skip.py:3*'`. Head printed `test_skip.py:2` (fixed), base printed `skipping.py` | `test_xfail_run_with_skip_mark[-rs --runxfail]`: same idea, with the location pytest actually prints | Wrong expected value copied from the issue: line 3 from the issue's file layout, off by one for the repro's layout |
| pytest-7490 | `reports[2].outcome == "skipped"` → `Expected skipped, got passed`. **Identical on base and head** | `test_dynamic_xfail_set_during_runtest_*`: `runpytest` + `assert_outcomes(xfailed=1)` | Other, a broken test: `runtestprotocol` returns [setup, call, teardown], so `reports[2]` is the teardown report, which always passes |

## 4. Counts and one-change verdict
- **Wrong expected value: 5** (12907, 14365, 2848, 4045, 7432)
- **Tests a different code path: 1** (2674)
- **Other, broken test: 1** (7490)
- **Environment: 0.** **Gold patch incomplete: 0**

**No.** No single change to REPRODUCE or VERIFY_RED would plausibly flip 3 of these to proven without
making false approvals easier.
- The 5 wrong-value cases need the test to match the true behaviour. A model can only learn that by seeing
  the head's behaviour, which means repairing the test after a head failure. That fits the test to the
  patch, so a wrong patch's behaviour would be fitted the same way.
- The other option is narrowing the test to the issue's literal example (no message regexes, no derived
  cases). There's a concrete counterexample: the failed flask-4045 patch passes the official
  `test_dotted_name_not_allowed` and fails only `test_route_decorator_custom_endpoint_with_dots`. A bare
  `raises(ValueError)` test would approve it.

A safe change exists, but it doesn't approve anything. When the repro fails on head at the same test and
assertion as on base, the test never reached the changed behaviour, so call it `unproven` (inconclusive)
instead of `doesnt_fix`. It blocks the same PRs.

**As implemented** (`agent/review.py` `same_failure`): "same" means the same failed tests, the same
traceback frames (path:line), the same executing source lines (pytest's `>` lines) and the same exception.
- An edit to code the test runs through changes a frame's line or its `>` line. So 2674 doesn't match: its
  traceback goes through `adapters.send`, which the gold patch edits, shifting it from line 361 to 362.
  The test did reach the changed file. This analysis originally listed 2674 as relabelled, which was wrong.
- In rv-full the rule relabels gold 7432 and 7490, and failed astropy-14995. The failed 14995 patch edits
  only `nddata.py`, and its traceback stays in `ndarithmetic.py`.

## 5. requests-1963 and cleaned labels
**requests-1963 isn't a real false approval.** All 7 of its official FAIL_TO_PASS tests pass, including
`TestRedirects::test_requests_are_updated_each_time`. It's labelled unresolved only because one
PASS_TO_PASS test failed: `test_BASICAUTH_TUPLE_HTTP_200_OK_GET`, an httpbin network test. That same test
is a FAIL_TO_PASS test in requests-2674, which shows that httpbin tests flip with the environment.

Red2Fix's repro used a mock adapter to replay the issue's POST → 303 → 307 chain. On base the third request
was POST, so it failed (`'POST' != 'GET'`). With the patch it was GET, so it passed. The patch carries the
rewritten request through the loop, which is the gold fix's idea. No suite test regressed.

**Cleaned labels:** a patch is truly failed only if a FAIL_TO_PASS test failed in its official report.
- **Truly failed: 16 of 20.** Red2Fix's verdicts on them: 0 proven, 4 doesnt_fix (14182, 14995,
  flask-4045, flask-4992), 1 breaks_tests (flask-5063), 5 unproven (14365, seaborn-2848, seaborn-3010,
  requests-2148, pytest-7490), and 6 error (12907, 6938, seaborn-3190, seaborn-3407, xarray-4094,
  pylint-7080). **False approvals: 0 of 16.**
- **Not truly failed: 4.** All their FAIL_TO_PASS tests pass and only PASS_TO_PASS tests fail:
  - requests-1963: Red2Fix proven
  - requests-2317: Red2Fix proven
  - requests-2674: Red2Fix unproven
  - pytest-7432: Red2Fix breaks_tests. Red2Fix flagged `test_skipped_reasons_functional`, the same
    PASS_TO_PASS test the official report failed.

  Both earlier "false approvals" are in this group.

## Recomputed report
Generated with `uv run bench/report_review.py rv-full` (offline, from the stored review.json, red.log and
head.log; no model calls). The full table is in `out/bench/rv-full/review_report.md`.

- **Verdicts changed by the same-failure rule:** gold pytest-7432 and pytest-7490, doesnt_fix → unproven;
  failed astropy-14995, doesnt_fix → unproven. Everything else is unchanged.
- **False approvals, original labels:** 2 / 20 for both the stored and the recomputed verdicts
  (requests-1963, requests-2317), under both unrelated_change settings.
- **False approvals, cleaned labels:** 0 / 16 for both the stored and the recomputed verdicts.
- **Correct approvals (gold proven):** 3 / 20, unchanged.

The cleaned-label rule (a failed patch is truly failed only if at least one of its FAIL_TO_PASS tests
failed in its official report) was **defined after inspecting these results**. The report states this next
to the numbers.
