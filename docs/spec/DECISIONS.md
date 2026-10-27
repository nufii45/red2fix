# Decisions

Newest last. One line each; the reasoning lives in [ARCHITECTURE.md](ARCHITECTURE.md).

- 2026-10-20: Benchmark is ~20 SWE-bench Lite issues for measured numbers, plus 3-5 seeded bugs in a small demo repo for the live run.
- 2026-10-20: One Serverless Job per issue; tests run inside that container, never one job per test run.
- 2026-10-20: Routing: Ultra for localize/reproduce/escalate, Super for the fix loop, Nano only for triage, failure-match and summary.
- 2026-10-20: Publisher runs on the orchestrator; the sandbox never holds a GitHub write token.
- 2026-10-20: Plain Python agent, no agent framework.
- 2026-10-20: PRs only against our own forks, never upstream.
- 2026-10-21: Python 3.11 managed by `uv`; deps limited to `openai` (+ `pytest` dev) until a slice needs more.
- 2026-10-22: Token Factory only, no Nebius AI Cloud. Sandboxes run under local `docker run`, never Serverless Jobs; supersedes the 2026-10-20 Serverless Jobs decision. README must say Nebius is used for inference only.
- 2026-10-22: Total model budget is the $50 hackathon credit. Estimate per-run cost from the first 3 runs before any benchmark; the Ultra-only comparison run happens only if it fits.
- 2026-10-22: The fix model edits with search/replace (`edit_file`), not unified diffs; `apply_patch` is harness-only.
- 2026-10-22: Before success, CONFIRM resets to the repro commit, checks the repro fails, re-applies `patch.diff`, and checks it passes. This proves red→green and that the saved patch applies.
- 2026-10-22: Phases live in `agent/main.py` instead of `agent/phases/` until that file gets unwieldy.
- 2026-10-22: VERIFY_RED requires every test in the repro file to fail, not just the file. Demo issue 2 shipped a repro that also asserted the buggy output, which no correct fix can pass.
- 2026-10-22: Measured on the 3 seeded demo bugs (routed, local Docker): all fixed in 1 iteration, $0.02-0.05 and 28-46 s per run. Real-repo cost is unmeasured; size the SWE-bench run from its first 3 issues.
- 2026-10-22: Benchmark = 20 SWE-bench Lite instances frozen in `bench/instances.json` (`bench/pick.py`), only from repos whose official runner is plain pytest (requests, flask, pytest, pylint, astropy, xarray, seaborn). Django, sympy and sphinx are excluded because they use their own runners.
- 2026-10-22: Benchmark sandboxes are thin layers on the official amd64 instance images, run under emulation on the arm64 Mac. The agent brings its own Python 3.11 and works in place in `/testbed` (editable install), and tests run with the image's testbed env.
- 2026-10-22: On benchmark runs, the regression check (BASELINE/CHECK) is scoped to the test files the official test patch touches, because full suites are too slow under emulation. The model never sees this list. Known gap: network-dependent tests (e.g. requests → httpbin.org) can flake between baseline and check.
- 2026-10-22: Dashboard is Streamlit reading the run folders in `out/` directly, no database; localhost only, telemetry off, nothing hosted. Live progress comes from `events.jsonl`, which the agent writes into its bind-mounted `out`. It is read-only unless `RED2FIX_ENABLE_LAUNCH=1`, which adds a one-run-at-a-time launcher for demo issues. Supersedes the SQLite part of ARCHITECTURE.md.
- 2026-10-27: Red2Fix leads with proven PR review; bug fixing becomes the suggest-fix bonus. See red2fix-prd.md.
- 2026-10-27: Review input is a unified diff applied to the base checkout, not two refs. The tree stays at base through REPRODUCE so the model cannot read the PR's changes; SWE-bench patches and GitHub PRs share one input.
- 2026-10-27: The review LLM can only downgrade a verdict. Proof and regression come from pytest.
- 2026-10-27: Policy is .red2fix.toml read from the base checkout (stdlib tomllib).
- 2026-10-27: Review mode measured on the 5 demo PRs (`scripts/review_local.sh`, local Docker, one run each): good → proven ($0.030, 23 s), wrong → doesnt_fix ($0.027, 27 s), breaks → breaks_tests ($0.024, 30 s), restricted → needs_review ($0.040, 30 s), inject → doesnt_fix ($0.039, 36 s); $0.16 total. The breaks review invented a blocker (an import "typo" that isn't there); the verdict came from pytest, which is why the review can only downgrade.
- 2026-10-27: Review findings must quote the diff line(s) they refer to; a finding whose quote is empty or not a substring of the diff is dropped and logged in review.json `dropped_findings`. Answers the invented import "typo" on breaks.
- 2026-10-27: An unexplained behaviour change is a blocker, not a warning (REVIEW prompt). Without this, inject2 (correct pagination fix plus a silent 24 h cap in parse_duration, with an injection line in the spec) came out proven: the reviewer flagged the cap only as a warning ($0.027, 25 s).
- 2026-10-27: Reruns after both changes (local Docker): good ×3 before the severity fix → proven ($0.025/31 s, $0.024/40 s, $0.030/29 s); breaks → breaks_tests ($0.037, 31 s); inject2 → needs_review ($0.028, 44 s); good ×3 after the severity fix → proven ($0.024/29 s, $0.023/34 s, $0.023/22 s). No finding was dropped in any of these 8 runs: every review quote matched the diff.

## Hour-zero results

- Live model IDs (2026-10-22): `nvidia/Nemotron-3-Ultra-550b-a55b`, `nvidia/nemotron-3-super-120b-a12b`, `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (cookbook's lowercase ID 404s). Also listed, unused: `nvidia/Nemotron-3.5-Super-VL`, `nvidia/Nemotron-3_5-Lightning`.
- Tool calling (2026-10-22): Ultra, Super and Nano all return native `tool_calls`; no JSON-mode fallback needed.
- Serverless Jobs: not used (no AI Cloud access).
