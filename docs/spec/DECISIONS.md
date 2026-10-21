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

## Hour-zero results

- Live model IDs (2026-10-22): `nvidia/Nemotron-3-Ultra-550b-a55b`, `nvidia/nemotron-3-super-120b-a12b`, `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (cookbook's lowercase ID 404s). Also listed, unused: `nvidia/Nemotron-3.5-Super-VL`, `nvidia/Nemotron-3_5-Lightning`.
- Tool calling (2026-10-22): Ultra, Super and Nano all return native `tool_calls`; no JSON-mode fallback needed.
- Serverless Jobs: not used (no AI Cloud access).
