# Saturday P0 slice: agent loop, local Docker, 3 seeded bugs

## Context
The Friday slice gave us `agent/llm.py` (routed calls + ledger + $ cap), `agent/tools.py` (repo tools), and `agent/guards.py` (patch checks). This slice wires them into the state machine from ARCHITECTURE §3 and runs it end-to-end in a local Docker sandbox on 3 seeded bugs. Per DECISIONS (2026-10-22): no Serverless Jobs; local Docker is the sandbox; the whole project has a $50 model budget.

Outcome: `docker run … red2fix-agent` on a seeded issue produces a failing repro test, a fix that makes it pass without new suite failures, and artifacts in `out/`.

## State machine (`agent/main.py`)
```
TRIAGE → BASELINE → LOCALIZE → REPRODUCE ⇄ VERIFY_RED → COMMIT_REPRO → FIX ⇄ CHECK → CONFIRM → SUMMARIZE → DONE
any phase → ABORT(reason)   reasons: out_of_scope | no_repro | max_iterations | budget_usd | timeout | error:<Exc>
```
| Phase | Model | What happens |
|---|---|---|
| TRIAGE | nano | Issue text → JSON `{in_scope, bug_type, reason}`. Not in scope → abort. |
| BASELINE | — | `tools.failing_tests(root)` on the untouched repo: set of already-failing tests. |
| LOCALIZE | ultra | Tool loop with read-only tools (`list_files`, `read_file`, `grep`), ends with JSON `{files, functions, hypothesis}`. Max 12 tool steps. |
| REPRODUCE | ultra | Returns the content of `tests/test_repro_issue_<n>.py`; harness writes it. |
| VERIFY_RED | — + nano | Run repro test. Must exit **1** (exit 2/4/5 = collection/usage error → retry). Then nano: "does this failure match the issue?" No → back to REPRODUCE with the log. Max 3 attempts → abort `no_repro`. Saves `red.log`. |
| COMMIT_REPRO | — | `git commit` the repro test inside the sandbox copy, so later diffs are fix-only (the guard baseline requirement noted in `guards.py`). |
| FIX | super | One iteration = a tool-calling episode with read tools + `edit_file` + `write_file` + `run_tests`, ended by the model replying without tool calls. Writes to test files are refused at the tool layer (`guards.is_test_file`). Each iteration starts from fresh messages (issue, hypothesis, repro test, last failure output, current diff) to keep context bounded. |
| CHECK | — | In order: repro passes? → `guards.check_patch(diff)` clean? → `failing_tests` now ⊆ baseline? Any failure becomes the feedback for the next FIX iteration. |
| ESCALATE | ultra | After every 3 failed iterations (max 2 escalations): history in, new hypothesis out, back to FIX. |
| CONFIRM | — | `git stash` the fix, repro must fail again, `git stash pop`, repro must pass. The red→green proof, re-checked in the same container. Saves `green.log`. |
| SUMMARIZE | nano | PR-style markdown (ARCHITECTURE §5 template) → `summary.md`. |

Caps from `config.py` (`MAX_FIX_ITERS=8`, `MAX_ESCALATIONS=2`, `MAX_USD`, `MAX_SECONDS`) checked at every phase/iteration boundary; `BudgetExceeded` from `LLM.chat` → `budget_usd`. Every phase change printed as `PHASE <name>` (the orchestrator will tail this later). `result.json` is always written (`try/finally`).

## Changes

1. **`agent/tools.py`**
   - `edit_file(root, path, old, new)`: replace exactly one occurrence, else return an error string (search/replace is far more reliable from models than unified diffs; `apply_patch` stays harness-only).
   - `failing_tests(root, selector="")`: run pytest with `--junitxml` to a temp file, parse with `xml.etree`, return the set of failed/errored test ids. Not truncated, so baseline comparison is exact.
   - `SPECS`: OpenAI tool JSON schemas, and `call(root, name, args, allow)` dispatch that returns errors as strings (a bad tool call must not crash the run).
2. **`agent/guards.py`**: rename `_is_test_file` → `is_test_file` (used by the fix-phase write refusal).
3. **`agent/main.py`** (new): CLI `python -m agent.main --repo DIR --issue FILE --out DIR [--number N]`, the state machine above, a `tool_loop(llm, phase, messages, allow, max_steps)` helper, and a lenient `parse_json` (first `{…}` in the reply). Copies `--repo` to `/work/repo` and `git init`s it if needed, so the input is never modified. Phases live here, not in `phases/`, until the file gets unwieldy.
4. **`agent/prompts.py`** (new): one system prompt per phase, as plain strings.
5. **`Dockerfile`** (new): `python:3.11-slim` + `git`; `pip install openai pytest`; copy `agent/`, `config.py`; `ENTRYPOINT ["python", "-m", "agent.main"]`. Non-root user.
6. **`demo/`** (new): small package `demo/shop/` with a passing test suite and 3 seeded bugs not covered by it, plus `demo/issues/{1,2,3}.md` written like real GitHub issues (symptom + repro steps, no fix hint). Candidates: duration parser drops minutes in `"1h30m"`; paginator loses the last page when the item count divides the page size; `slugify` crashes / double-dashes on accented input.
7. **`scripts/run_local.sh`** (new): `docker build` once, then `docker run --rm --env-file .env -v demo:/src:ro -v out/<issue>:/out red2fix-agent --repo /src --issue /src/issues/<n>.md --out /out`.
8. **Tests** (`tests/test_main.py`): a scripted fake LLM (same `SimpleNamespace` pattern as `tests/test_llm.py`) on the `buggy_repo` fixture:
   - happy path reaches DONE with red then green and a clean diff;
   - repro that passes immediately is rejected → `no_repro`;
   - fix that tries to edit a test file is refused and ends `max_iterations`;
   - new suite failure after the fix is fed back, not accepted.
   Plus unit tests for `edit_file`, `failing_tests`, `parse_json`.
9. **Docs**: add a line to `DECISIONS.md` for search/replace edits and the CONFIRM stash check. Rename this plan to `plans/2026-10-22-agent-loop.md` and commit with the work.

## Not in this slice
Cloning from a GitHub URL / SWE-bench environments, orchestrator, SQLite, publisher, dashboard, Ultra-only mode.

## Verification
- `uv run pytest -q` green (no credits spent; fake LLM).
- Docker Desktop must be running (daemon was down when checked).
- `scripts/run_local.sh 1` (then 2, 3): each ends `DONE` or a clear abort reason; `out/<n>/` has `result.json`, `red.log`, `green.log`, `patch.diff`, `repro_test.py`, `ledger.jsonl`, `summary.md`.
- Sum `cost_usd` across the 3 ledgers and record $/run in `DECISIONS.md`; that number sizes the benchmark against the $50 budget. Expected spend for this slice: a few dollars.
