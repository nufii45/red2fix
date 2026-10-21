# Friday P0 slice: spec, scaffold, hour-zero checks, llm/tools/guards

## Context
Red2Fix is an empty repo. The architecture and weekend plan (pasted 2026-10-20) is the spec. This slice builds the Friday-evening P0 pieces the agent loop will stand on: the LLM client with cost ledger, the sandbox tools, and the anti-cheat guards, plus a script to confirm the model IDs and tool-calling on Token Factory. It stops before the agent state machine (Saturday).

Environment found: system Python 3.9 (too old), `uv` and `python3.12` present, `nebius` CLI not installed, Docker installed (daemon state unknown).

## Steps

1. **Spec into the repo**
   - `docs/spec/ARCHITECTURE.md`: the pasted plan, verbatim.
   - `docs/spec/DECISIONS.md`: one line each, dated 2026-10-20/21: SWE-bench Lite (~20) + 3-5 seeded bugs; one Serverless Job per issue, tests run inside it; Super for fix loop, Nano only for triage/summary/failure-match; publisher on orchestrator, sandbox never holds a GitHub write token; plain Python, no agent framework; PRs only against own forks. Hour-zero results get appended here.

2. **Scaffold** (`uv init`, Python 3.11 pinned via `.python-version`)
   - `pyproject.toml` deps: `openai`; dev: `pytest`. Nothing else yet.
   - `.gitignore`: `.venv/`, `__pycache__/`, `*.jsonl`, `.env`.
   - Layout per §7, only the files this slice needs: `config.py`, `agent/{__init__,llm,tools,guards}.py`, `scripts/hour_zero.py`, `tests/`.

3. **`config.py`**: `BASE_URL`, `MODELS = {"ultra":…, "super":…, "nano":…}` (placeholder IDs from the doc, replaced with the live `/v1/models` strings after step 4), `PRICES` per 1M in/out tokens, `ROUTES` phase→model key (§3 table), budgets (`MAX_FIX_ITERS=8`, `MAX_ESCALATIONS=2`, `MAX_USD=1.00`, `MAX_SECONDS=600`), `TOOL_OUTPUT_LINES=200`.

4. **`scripts/hour_zero.py`** (run by hand with `NEBIUS_API_KEY`):
   - `GET /v1/models`, print every ID matching `nemotron`.
   - For each configured model: one plain chat call (prints latency + tokens) and one call with a single dummy tool, reporting whether `tool_calls` came back.
   - Results go into `DECISIONS.md` and `config.py` by hand.
   - Nebius Jobs check stays manual (CLI not installed): install CLI, `nebius ai job create --help`, run quickstart job, time cold start, note CPU presets / env/secret passing / max runtime in `DECISIONS.md`.

5. **`agent/llm.py`**: class `LLM(ledger_path, max_usd)` wrapping `openai.OpenAI(base_url=BASE_URL, api_key=NEBIUS_API_KEY)`.
   - `chat(phase, messages, **kw)`: picks model from `ROUTES[phase]`, calls, computes cost from `usage` × `PRICES`, appends one JSON line `{ts, phase, model, in_tokens, out_tokens, latency_ms, cost_usd}`, adds to `self.spent`, raises `BudgetExceeded` once `spent > max_usd`. Returns the raw response.
   - Client is injectable so tests use a fake.

6. **`agent/tools.py`**: plain functions taking `root` (the cloned repo):
   - `list_files` (`git ls-files`), `read_file(path, start, end)` with line numbers, `grep(pattern)` (`git grep -n`), `write_file`, `apply_patch(diff)` (`git apply`), `run_tests(selector)` → `(exit_code, tail)`, `git_diff()`.
   - All output truncated to `TOOL_OUTPUT_LINES`. Every path resolved and rejected if it escapes `root`. Subprocess calls get a timeout.
   - Tool JSON schemas for the model are deferred to the agent-loop slice.

7. **`agent/guards.py`**: `check_patch(diff, repro_path) -> list[str]` of violations: touches the repro test or any existing test file (`test_*.py`, `*_test.py`, `tests/`, `conftest.py`); adds lines with `pytest.skip`, `xfail`, or `except…: pass`. Parses `+++`/`---` headers and `+` lines only; no dependency.

8. **Tests** (`tests/`), against a tiny buggy package built in `tmp_path` and `git init`ed by a fixture:
   - `test_tools.py`: read/grep/write/apply_patch/run_tests (red then green after a patch), path escape rejected, truncation.
   - `test_guards.py`: clean patch passes; each violation type caught.
   - `test_llm.py`: fake client → ledger line written, cost math right, `BudgetExceeded` raised.

9. **Commit**: rename branch `master`→`main` (repo has no commits; `main` is the declared main branch), rename this plan to `plans/2026-10-21-friday-p0-slice.md`, one initial commit with spec + code + plan.

## Not in this slice
Agent state machine and tool schemas, Docker image, benchmark selection (SWE-bench download), launcher/orchestrator/publisher/dashboard, SQLite. Saturday.

## Verification
- `uv run pytest -q` green.
- `NEBIUS_API_KEY=… uv run scripts/hour_zero.py` lists live IDs and reports tool-calling per model; a `ledger.jsonl` appears with three-plus rows and plausible costs. Needs your key; I can't run it without one.
