# SWE-bench Lite benchmark slice

## Context
The agent loop works on 3 seeded bugs ($0.02-0.05, ~30-45 s each). The pitch needs numbers from real issues: about 20 SWE-bench Lite instances, scored by the official harness's hidden tests, plus our own repro pass rate. This slice also measures real cost per issue against the $50 budget. Live demo and PR stay on the user's own public repo (minikit), a later slice.

Facts that shape the design (researched 2026-10-22, swebench v5.0.2):
- Dataset `SWE-bench/SWE-bench_Lite`, split `test`. Each row has `image` (e.g. `swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest`), `base_commit`, `problem_statement`, `test_patch`, `FAIL_TO_PASS`/`PASS_TO_PASS` (lists).
- Images are **amd64 only**; repo at `/testbed`, conda env `testbed` (python probably `/opt/miniconda3/envs/testbed/bin/python`, verify). On this arm64 Mac they run under emulation, ~4-7× slower.
- Official scoring: `swebench eval SWE-bench/SWE-bench_Lite -p preds.jsonl --run-id <id> -j <n> [-i <id>…]`, predictions `{instance_id, model_name_or_path, model_patch}`, results in `logs/evaluation/<run_id>/`. Needs Python ≥3.10. Old guides' `--namespace`/`--cache_level` flags no longer exist.
- Plain-pytest repos in Lite: requests 6, flask 3, pytest 17, pylint 6, astropy 6, xarray 5, seaborn 4 (47). Django, sympy and sphinx use other runners and are excluded.
- Machine: arm64, 32 GB RAM, Docker has 8 GB / 10 CPU, 658 GB disk free.

## Design
The agent runs **inside a thin image derived from each instance's official image**, working directly in `/testbed`. That repo is pip-installed in editable mode, so a copy would test the wrong code. The agent brings its own Python 3.11 + `openai`. Tests run with the testbed env's Python, so the repo's pinned deps apply. The model never sees the harness's test lists. The harness only uses the official test files to scope our BASELINE/CHECK regression run; the full suites of pytest or astropy would take too long under emulation.

## Changes
1. **`agent/tools.py`**: test commands use `os.environ.get("RED2FIX_TEST_PYTHON", sys.executable)` (one helper shared by `run_tests` and `failing_tests`).
2. **`agent/main.py`**:
   - `prepare`: when `work == repo`, skip the copy and only add the `.git/info/exclude` lines.
   - New `--suite SELECTOR` (default: whole suite) passed to `failing_tests` in BASELINE and CHECK.
   - New `--max-seconds` (default `config.MAX_SECONDS`), since emulation is slower.
3. **`bench/select.py`**: fetch Lite `test` rows from the HF datasets-server JSON API (stdlib `urllib`, no new deps). Keep the 7 plain-pytest repos, at most 5 per repo for variety, sorted by `difficulty` (if present) then id. Take 20 and write `bench/instances.json`: id, repo, image, base_commit, problem_statement, and the test-file paths from `test_patch` (for `--suite`). The committed file is the frozen benchmark list.
4. **`bench/Dockerfile.swebench`**: `ARG BASE` → `FROM $BASE`; copy `uv` from `ghcr.io/astral-sh/uv`; `uv venv -p 3.11 /opt/r2f && uv pip install -p /opt/r2f openai==3.35.1`; copy `agent/`, `config.py` to `/opt/r2f/app`. Env `RED2FIX_TEST_PYTHON=/opt/miniconda3/envs/testbed/bin/python`, `PYTHONDONTWRITEBYTECODE=1`. Entrypoint: agent with `--repo /testbed --work /testbed`.
5. **`bench/run.py`**: `uv run bench/run.py --run-id R [--ids a,b] [-j 2]`.
   - Per instance:
     - `docker build --platform linux/amd64 --build-arg BASE=<image>`.
     - Write `issue.md`.
     - `docker run --platform linux/amd64 --env-file .env` with `out/bench/R/<id>` mounted, `--number` set to the numeric suffix, and `--suite` set to the test files.
   - Runs instances in parallel with a `ThreadPoolExecutor`.
   - Then writes `out/bench/R/preds.jsonl`: `patch.diff` for succeeded runs, empty patch otherwise.
   - Then a table: id, status/abort reason, iterations, $, seconds; plus totals and own-repro pass rate.
6. **`bench/score.sh`**: `uvx --python 3.11 swebench eval SWE-bench/SWE-bench_Lite -p out/bench/R/preds.jsonl --run-id R -j 2`, then print resolved count from `logs/evaluation/R/results.json`.
7. **Tests**: the in-place `prepare` path and `--suite` scoping on the `buggy_repo` fixture; a `bench/select.py` unit test on a canned 3-row response (repo filter, per-repo cap, test-file extraction from a patch).
8. **Docs**: in `DECISIONS.md`, record:
   - in-image agent with in-place `/testbed`;
   - regression scoped to the official test files (and why);
   - the excluded repos;
   - amd64 emulation.

   Rename this plan to `plans/2026-10-22-swebench-bench.md` and commit with the work. `out/` and `logs/` are gitignored.

## Run order (credits spent only in steps 3-4)
1. **Docker Desktop** (user): turn on "Use Rosetta for x86_64/amd64 emulation" and raise the virtual disk to ≥120 GB.
2. **Gold check, no credits:** `swebench eval … --gold -i <the 20 ids>`. This proves the images run under emulation and the harness scores on this Mac, and it pre-pulls the images. Drop any instance where gold fails.
3. **Pilot:** `bench/run.py` on 3 instances. Read every log. Estimate $/issue and minutes/issue and record them in `DECISIONS.md`.
4. **Full run on all 20** only if the estimate fits the budget, then `bench/score.sh`.

## Not in this slice
Ultra-only comparison mode, SQLite/dashboard, publisher, minikit on GitHub.

## Verification
- `uv run pytest -q` green.
- Gold check resolves (nearly) all 20.
- Pilot: 3 result folders with `result.json`; any succeeded patch scores in `swebench eval`.
- `DECISIONS.md` has the measured $/issue.
