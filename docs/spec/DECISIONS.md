# Decisions

Newest last. One line each; the reasoning lives in [ARCHITECTURE.md](ARCHITECTURE.md).

- 2026-10-20: Benchmark is ~20 SWE-bench Lite issues for measured numbers, plus 3-5 seeded bugs in a small demo repo for the live run.
- 2026-10-20: One Serverless Job per issue; tests run inside that container, never one job per test run.
- 2026-10-20: Routing: Ultra for localize/reproduce/escalate, Super for the fix loop, Nano only for triage, failure-match and summary.
- 2026-10-20: Publisher runs on the orchestrator; the sandbox never holds a GitHub write token.
- 2026-10-20: Plain Python agent, no agent framework.
- 2026-10-20: PRs only against our own forks, never upstream.
- 2026-10-21: Python 3.11 managed by `uv`; deps limited to `openai` (+ `pytest` dev) until a slice needs more.

## Hour-zero results

- Live model IDs (2026-10-22): `nvidia/Nemotron-3-Ultra-550b-a55b`, `nvidia/nemotron-3-super-120b-a12b`, `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (cookbook's lowercase ID 404s). Also listed, unused: `nvidia/Nemotron-3.5-Super-VL`, `nvidia/Nemotron-3_5-Lightning`.
- Tool calling (2026-10-22): Ultra, Super and Nano all return native `tool_calls`; no JSON-mode fallback needed.
- Serverless Jobs: CPU presets in region, env/secret passing, max runtime, measured cold start:
