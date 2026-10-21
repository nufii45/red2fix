# Red2Fix: architecture and weekend build plan

*Red2Fix: from failing test to proven fix.*

**Track:** Coding and Agentic Engineering (NVIDIA × Nebius hackathon)
**One-liner:** Give it a GitHub issue. It writes a failing test that reproduces the bug, fixes the code until that test passes without breaking the suite, and opens a PR with the red→green evidence.
**Stack default:** Python 3.11, OpenAI-compatible client against Nebius Token Factory, Docker image run as Nebius Serverless AI Jobs.

---

## 0. Verified facts (as of 2026-10-20) and what still needs checking

| Item | What I found | Confidence |
|---|---|---|
| Token Factory API | OpenAI-compatible. Base URL `https://api.tokenfactory.nebius.com/v1/`; Nebius's own cookbook also uses the regional host `https://api.tokenfactory.us-central1.nebius.com/v1/`. Auth via `NEBIUS_API_KEY`. | High |
| Nemotron 3 Ultra | Listed as `Nemotron-3-Ultra-550b-a55b` (550B MoE, 55B active, ~1M context), ~$1.00 / $3.00 per 1M in/out tokens. ID seen in projects: `nvidia/Nemotron-3-Ultra-550b-a55b`. | Medium on exact ID string |
| Nemotron 3 Super | `nvidia/nemotron-3-super-120b-a12b` (120B MoE, 12B active, ~256K context). | Medium |
| Nemotron 3 Nano | Nebius cookbook uses `nvidia/nvidia-nemotron-3-nano-30b-a3b` (30B MoE, 3B active, 262K context, function calling + structured output), ~$0.06 / $0.24 per 1M tokens. Other projects use different casing. | High for cookbook ID |
| Serverless AI Jobs | Containerized finite workloads (start, run, complete), billed per second, managed via the `nebius ai` CLI group (create job, list, get, logs). Not available in every region. | High on concept, **low on exact flags** |

**Hour-zero tasks (do these before writing any agent code):**
1. `GET /v1/models` with your key and hardcode the three IDs from the live list into `config.py`. Casing differs across sources; don't guess.
2. Run `nebius ai job create --help` and launch the quickstart job. Confirm CPU-only presets exist in your region, how env vars/secrets are passed, max runtime, and how long cold start takes. That number decides the sandbox design in §4.
3. Check whether each model supports tool calling on Token Factory today. If Ultra doesn't, the plan still works: Ultra returns JSON plans, Super/Nano do the tool-calling loop.

Sources: [Nebius Nemotron on Token Factory](https://nebius.com/services/token-factory/nemotron), [Nemotron model inference page](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference), [Token Factory cookbook: Nano](https://github.com/nebius/token-factory-cookbook/blob/main/models/nemotron/nemotron3-nano-30b.md), [Nebius Serverless docs](https://docs.nebius.com/serverless), [`nebius ai` CLI reference](https://docs.nebius.com/cli/reference/ai.md).

---

## 1. Scope: what it does and refuses to do

**In scope:** Python repos with a working `pytest` suite. Bugs that show up as a crash, wrong return value, or unhandled edge case and can be expressed as a unit test.

**Out of scope (the agent declines with a reason):** UI bugs, performance issues, flaky/concurrency bugs, anything needing network or external services, issues without enough information to reproduce.

The refusal path matters. A clean "I couldn't reproduce this, here's what I tried" is a feature on the dashboard, not a failure to hide.

> **Push-back on the original pitch:** "run it on 3 real issues from popular repos" live on stage is the riskiest possible demo. Popular repos have heavy install steps and the issues worth fixing are hard. Use a pre-measured benchmark for the numbers (§6) and do **one** live run on an issue you've already watched it solve at least 3 times.

---

## 2. Architecture

```
            ┌──────────────────────────── Orchestrator (your laptop or a small Nebius VM) ───────────────────────────┐
 GitHub     │  FastAPI + SQLite                                                                                       │
 issue URL ─┼─► intake ─► enqueue run ─► launch Serverless Job ─► stream logs ─► collect result.json ─► open PR ─►  │─► GitHub PR
            │                                                                                                    │     │
            │  Dashboard (Streamlit) reads SQLite: runs, pass/fail, tokens, $, wall time, model mix               │     │
            └────────────────────────────────────────────┬───────────────────────────────────────────────────────┘     │
                                                         │ one job per issue                                           │
                                     ┌───────────────────▼────────────────── Nebius Serverless AI Job (CPU) ───────────┐
                                     │  container: red2fix-agent image                                                 │
                                     │  1. clone repo @ commit, install deps                                           │
                                     │  2. agent loop  ── HTTPS ──► Token Factory (Ultra / Super / Nano)               │
                                     │  3. runs pytest locally inside the container (fast, no extra job per run)       │
                                     │  4. writes result.json + patch.diff + logs to object storage                    │
                                     └─────────────────────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Responsibility | Notes |
|---|---|---|
| `intake` | Fetch issue title/body/comments via GitHub API, resolve repo + default branch commit. | `PyGithub` or plain REST. |
| `launcher` | Create one Serverless Job per issue with env: repo URL, commit SHA, issue text, model IDs, `NEBIUS_API_KEY`, budget caps. | Wrap the `nebius ai` CLI with `subprocess` first; move to the SDK only if time allows. |
| `agent` (runs in the job) | The state machine in §3. | Plain Python, no agent framework. Frameworks cost debugging time you don't have. |
| `tools` | `list_files`, `read_file(path, range)`, `grep(pattern)`, `write_file`, `apply_patch`, `run_tests(selector)`, `git_diff`. | Every tool returns truncated output (e.g. last 200 lines of pytest) to keep context small. |
| `ledger` | Record every LLM call: model, phase, input/output tokens, latency, $ cost. | This is your dashboard data. Build it on day 1, not day 2. |
| `publisher` | Fork-or-branch, push `fix/issue-<n>`, open PR with template (§5). | Runs on the orchestrator, **not** in the sandbox, so the sandbox never holds a GitHub write token. |
| `dashboard` | Streamlit page: success rate, $/fix, time/fix, per-phase model mix, failure reasons, run detail with red→green logs. | |

---

## 3. Agent state machine and model routing

```
LOCALIZE ──► REPRODUCE ──► VERIFY_RED ──► FIX ⇄ TEST ──► REGRESSION ──► DONE
   │             │              │           │               │
   └──────── ABORT(reason) ◄────┴───────────┴───────────────┘   (budget, no repro, max iterations)
```

| Phase | Model | Why | Output |
|---|---|---|---|
| **Triage** (is this in scope?) | Nano | Cheap classification over the issue text. | `{in_scope, bug_type, reason}` |
| **Localize** | Ultra | Needs to reason over issue + repo map + grep hits to pick the 1-3 files and the root-cause hypothesis. | `{files, functions, hypothesis}` |
| **Reproduce** | Ultra | Writing a test that fails *for the right reason* is the hardest step and the whole thesis. | `tests/test_repro_issue_<n>.py` |
| **Verify red** | none (deterministic) + Nano | Run test; Nano checks the failure message matches the issue (not an ImportError or typo). | pass/retry |
| **Fix loop** | Super | Edit, run, read traceback, edit. Many short calls; needs to be competent at code, not brilliant. | patch |
| **Escalate** | Ultra | After 3 failed Super iterations, hand Ultra the history and ask for a new hypothesis. Then back to Super. | revised plan |
| **Regression** | none | Run the full existing suite (or the subset that was green at baseline). | pass/fail |
| **Summarize** | Nano | PR description from the logs. | markdown |

> **Push-back on "Nano/Super for the fix loop":** Nano (3B active) will likely write broken patches and burn iterations, which costs more than one Super call. Use **Super for edits** and **Nano only for classification and summarization**. Then *measure* it: run the benchmark once all-Ultra and once with routing, and show both bars on the dashboard. "Routing cut cost 4× with a 1-point drop in success rate" is the claim judges asked for, and it only counts if you measured it.

**Budgets (hard caps, enforced in code):** max 8 fix iterations, max 2 Ultra escalations, max $1.00 and 10 minutes per run. Abort with a reason when hit.

**Guardrails that prevent fake wins:**
- The repro test must fail on the original commit and pass on the patched commit. Check both in the same container.
- Reject patches that modify the repro test after VERIFY_RED, or that touch existing test files. Without this the model will "fix" the bug by weakening the test.
- Reject patches containing `pytest.skip`, `xfail`, or bare `except: pass` added near the fix.

---

## 4. Sandbox and execution

**Decision: one Serverless Job per issue, with tests run inside that container.**

The tempting design is a new job for every test run. Don't. Each job pays container pull + scheduling time, and the fix loop runs tests 5-15 times. Measure the cold start in hour zero; if it's 30-60 s, per-test jobs turn a 3-minute fix into a 15-minute one.

- **Image:** `python:3.11-slim` + git + build-essential + the agent code. Pre-bake dependencies for benchmark repos into image layers so install is seconds, not minutes.
- **Isolation:** the job only gets the Token Factory key and a scoped, write-only object storage credential. No GitHub write token. Disable outbound network after dependency install if the platform allows it; if not, say so honestly in the README.
- **Outputs:** `result.json` (status, phase reached, abort reason, iterations), `patch.diff`, `repro_test.py`, `red.log`, `green.log`, `ledger.jsonl`. Upload to Nebius Object Storage; the orchestrator polls job status and downloads.
- **Fallback:** the same image runs under local `docker run`. Keep a `--local` flag in the launcher. If Nebius jobs misbehave on Saturday night, you still have a demo, and you switch back once fixed. Report honestly which runs used which.
- **Parallelism:** the benchmark launches N jobs at once. That's the visual for "Serverless": 20 issues, 20 sandboxes, results in the time of one.

---

## 5. Data flow and PR format

1. User pastes issue URL into the dashboard (or `cli.py run <url>`).
2. Orchestrator writes a `runs` row (status `queued`), launches the job.
3. Job streams phase changes to logs; orchestrator tails them and updates `runs.phase`.
4. Job uploads artifacts; orchestrator marks `succeeded` / `aborted:<reason>`.
5. On success, publisher opens a PR:

```markdown
## Fixes #<n>: <issue title>

**Root cause:** <one paragraph from Localize>

**Reproduction:** `tests/test_repro_issue_<n>.py`
- Before fix: ❌ <failure line from red.log>
- After fix:  ✅ 1 passed
- Existing suite: ✅ <k> passed, 0 new failures

**Cost:** $0.31 · 2m48s · Ultra 2 calls / Super 6 calls / Nano 3 calls
<details><summary>Full logs</summary>…</details>
```

For the hackathon, open PRs against **your own forks**, not upstream. Opening agent PRs on real maintainers' repos without asking is spam, and judges who maintain OSS will notice.

### SQLite schema (minimal)

```sql
runs(id, issue_url, repo, commit, status, phase, abort_reason, iterations,
     started_at, finished_at, cost_usd, pr_url, mode)        -- mode: routed | ultra_only | local
calls(id, run_id, phase, model, in_tokens, out_tokens, latency_ms, cost_usd)
```

---

## 6. Demo plan and metrics

**Benchmark set:** 15-25 issues from **SWE-bench Lite / Verified** (Python, real issues, known-good tests, pre-specified commits). This gives you credibility you can't get from hand-picked issues, and the harness defines the environments. Filter to repos with fast installs (e.g. `requests`, `flask`, `astropy` subsets; avoid `django` and `sympy` if installs or suites are slow). Add 3-5 issues you seed yourself in a small demo repo for the live run.

> Be precise on stage: SWE-bench scoring uses hidden tests. Your agent's own repro test passing is *not* the official metric. Report both: "own repro passed" and "official SWE-bench tests passed". If those numbers differ, that gap is an honest, interesting finding.

**Dashboard (Streamlit), top to bottom:**
1. Headline tiles: success rate (official tests), median $/fix, median time/fix, issues attempted.
2. Bar chart: routed vs Ultra-only on success rate and $/fix. This is the routing proof.
3. Stacked bar per run: tokens/cost by model.
4. Failure breakdown: couldn't reproduce / reproduced but no fix / fix broke suite / budget exceeded.
5. Run detail: issue, repro test, red log, diff, green log, PR link.

**3-minute pitch script:**
1. (20 s) Problem: coding agents claim fixes they can't prove.
2. (60 s) Live run on a pre-tested issue: show phases ticking, red test, green test, PR opening. Have a recording of the same run queued in case Wi-Fi dies.
3. (60 s) Dashboard: "We ran 20 real SWE-bench issues in parallel on Nebius Serverless Jobs. 9 fixed, median $0.28, 3 minutes. Routing cut cost 4× versus all-Ultra." (Use your real numbers, whatever they are.)
4. (30 s) Show a failure honestly and what the agent reported.
5. (10 s) Close.

---

## 7. Repo layout

```
red2fix/
  agent/            # runs inside the job
    main.py         # state machine
    phases/         # localize.py, reproduce.py, fix.py, regress.py
    tools.py        # file/grep/patch/pytest tools with truncation
    llm.py          # Token Factory client, routing table, ledger
    guards.py       # anti-cheat patch checks
  orchestrator/
    api.py          # FastAPI: POST /runs, GET /runs
    launcher.py     # nebius ai job create | docker run
    publisher.py    # GitHub PRs
    db.py
  dashboard/app.py  # Streamlit
  bench/            # issue list, runner, scorer
  Dockerfile
  config.py         # model IDs from /v1/models, budgets
```

---

## 8. Weekend schedule (prioritized)

Priority tags: **P0** = no demo without it, **P1** = makes it win, **P2** = only if ahead.

### Friday evening (3-4 h)
- **P0** Hour-zero checks from §0: model IDs, a test call to each model, the quickstart job, measured cold start.
- **P0** Pick and freeze the benchmark list. Build the Docker image with deps pre-installed for those repos.
- **P0** `llm.py` with ledger, and `tools.py`. Unit-test the tools on one repo by hand.

### Saturday (10-12 h)
- **P0** (morning) Agent state machine end-to-end **locally in Docker** on 3 easy seeded bugs. All-Super is fine for now; get it working before optimizing.
- **P0** (morning) Guards: red-then-green check, no test tampering.
- **P0** (afternoon) Routing table (Ultra for localize/reproduce/escalate, Super for fix, Nano for triage/summary).
- **P0** (afternoon) Launcher on Nebius Serverless Jobs; artifacts to object storage; orchestrator collects results.
- **P1** (evening) Run the full benchmark once, routed. Read every failure and fix the top 2 causes (usually: bad repro tests and context overflow from long tracebacks).
- **P1** (evening) Publisher opening PRs on your forks.

### Sunday (6-8 h before submission)
- **P1** (morning) Benchmark run #2 routed + one Ultra-only run for the comparison. Freeze numbers by midday. No agent changes after this point except crash fixes.
- **P1** Streamlit dashboard from SQLite.
- **P0** Pick the live-demo issue, run it 3+ times, record a backup video.
- **P1** README: architecture diagram, how to run, honest limitations, the numbers.
- **P2** Parallel benchmark launch visual, failure-reason auto-classification, PR comment with dashboard link.
- **P0** Rehearse the pitch twice with a timer.

**Cut order if behind:** P2 items → Ultra-only comparison (keep only if one run is affordable in time) → publisher (show the diff and logs in the dashboard instead of a real PR) → Serverless Jobs (fall back to local Docker, and say so). Never cut the red→green guard; it's the whole idea.

---

## 9. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Model ID / tool-calling mismatch on Token Factory | Medium | Hour-zero check; JSON-mode fallback instead of native tools. |
| Job cold start too slow for live demo | Medium | One job per issue; pre-warm by launching the demo job before you go on stage; local fallback. |
| Repro tests that fail for the wrong reason (import error, typo) | High | Nano failure-match check + require assertion/exception type related to the issue. |
| Model weakens the test to pass | High | Guards in §3; diff check on test files. |
| Context blowup from big repos / tracebacks | High | Repo map (file tree + top-level symbols) instead of full files; truncate tool output. |
| Low success rate (<30%) | Medium | It's fine. Report it honestly with the failure breakdown. A measured 35% with clear reasons beats an unverified "it works". |
| Running out of credits during benchmark | Low-Medium | Per-run $ cap; estimate total cost from 3 runs before launching 20. |

---

## 10. Open decisions for you

1. ~~Benchmark source~~ **Decided (2026-10-20):** ~20 issues from SWE-bench Lite for the measured numbers, plus 3-5 seeded bugs in a small demo repo for the live run.
2. **Team split**, if more than one person: one person on agent + guards, one on Nebius jobs + orchestrator + dashboard is the natural cut.
3. **Where the orchestrator runs:** laptop (simplest) or a small Nebius VM (stronger "runs on Nebius" story). Default: laptop for development, VM on Sunday if time allows.
