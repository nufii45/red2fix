# LangSmith tracing (optional, never load-bearing)

## Prompt
```
Add LangSmith tracing so every review can be inspected call by call, without making a run depend on it.
Read agent/llm.py, agent/review.py, agent/main.py and agent/tools.py first. Save this prompt as
plans/2026-10-28-langsmith.md.

1. In agent/llm.py, wrap the OpenAI client with langsmith.wrappers.wrap_openai only when
   LANGSMITH_API_KEY is set. Without the key, behave exactly as today: no import, no network.
2. @traceable on run_review, run_agent and every phase (TRIAGE ... VERDICT, FIX, CONFIRM), named by phase,
   and on tools.call, named "tool:<name>" with the arguments and a truncated result.
3. Metadata and tags on the root trace: mode (review/fix/try-it), repo, PR URL or instance id,
   head_sha, policy_sha, final verdict, total cost. Project from LANGSMITH_PROJECT, default "red2fix".
4. Write the root trace URL into review.json and result.json as "trace_url". The dashboard's verdict card
   shows "View trace in LangSmith" when it exists. The local ledger stays the source of truth for cost.
5. Add langsmith to the agent's dependencies: pyproject, Dockerfile, bench/Dockerfile.swebench and the
   GitHub workflow's install step. Pass LANGSMITH_API_KEY through scripts/review_local.sh and the
   workflows only when it's set.
6. Tests: no key means no langsmith import and no network; with a mocked client, trace_url is recorded and
   a failed trace upload never fails the review.
7. One paid run: scripts/review_local.sh good with the key set. Show me the trace URL and a one-line
   description of what the trace tree looks like. Record it in DECISIONS.md. Commit, don't push.
Never send .env contents or secrets in trace inputs.
```

## Context
Every review should be inspectable call by call in LangSmith, but a run must never depend on it: with no
`LANGSMITH_API_KEY` nothing changes (no import, no network), and with the key a failed upload never changes a
verdict. The local ledger stays the source of truth for cost. On approval this file is renamed to
`plans/2026-10-28-langsmith.md` with the user's prompt verbatim at the top, and committed with the work.

Work happens in worktree `.claude/worktrees/langsmith`, branch `langsmith-tracing` (from local main, which is 3
commits ahead of origin). `.env` is symlinked in (gitignored) so `review_local.sh` runs there.

## Design: one small module, `agent/tracing.py` (~40 lines)
Everything LangSmith goes through it; nothing else imports `langsmith`.
- `ENABLED = bool(os.environ.get("LANGSMITH_API_KEY"))` (empty string = unset, which is what GitHub passes for a
  missing secret). Only if enabled: `import langsmith`, `setdefault LANGSMITH_TRACING=true`,
  `setdefault LANGSMITH_PROJECT=red2fix`, and one `Client(hide_inputs=redact, hide_outputs=redact)`.
- `traceable(**kw)`: `langsmith.traceable(client=CLIENT, **kw)` when enabled, else the identity decorator.
- `span(name, run_type, inputs)`: context manager over `langsmith.trace`, yields `record(out)` that ends the span
  with `{"output": str(out)[:2000]}`; a no-op yielding `lambda out: None` when disabled.
- `phase(name)`: closes the previous phase span and opens a new one (module-level `ExitStack`).
- `finish(**meta) -> url | None`: closes the open phase, adds metadata + tags (mode, verdict) to the current root
  run tree, returns `run_tree.get_url()`. Whole body in `try/except Exception: return None`.
  **Changed after review:** the key is write-only, so `get_url()` can't work; the URL is
  `$LANGSMITH_TRACE_URL_BASE` (project URL from the UI, query string dropped) + `/r/<root run id>?poll=true`,
  and no `trace_url` when it's unset.
- `redact(obj)`: walks dicts/lists/strings and replaces the value of every env var whose name contains
  KEY/TOKEN/SECRET/PASSWORD (values ≥ 8 chars) with `[redacted]`. Pure, testable without langsmith.

## Changes
1. **agent/llm.py**: in the `client is None` branch only, `if tracing.ENABLED: client = wrap_openai(client)`
   (import inside the branch). Injected clients (tests) stay untouched.
2. **Phases**: `Run.phase()` in agent/main.py calls `tracing.phase(name)`, so every phase (TRIAGE, BASELINE,
   LOCALIZE, REPRODUCE, …, HEAD_CHECK, VERDICT, FIX, CHECK, CONFIRM, SUMMARIZE) is a span named by its phase,
   with that phase's LLM and tool calls nested under it. Deviation from "@traceable on every phase": review.py's
   phases are inline blocks, not functions, so `Run.phase` is the one place that covers them all.
   `@tracing.traceable(name="review"|"fix", process_inputs=<drop llm, str() paths>)` on `run_review` and `run_agent`.
3. **agent/tools.py**: body of `call` moves to `_call`; `call` wraps it in
   `tracing.span(f"tool:{name}", "tool", args)` and records the result truncated to 2000 chars.
4. **Root metadata**: in both `finally` blocks, before saving, `url = tracing.finish(mode=..., repo=..., target=...,
   head_sha=..., policy_sha=..., verdict=..., cost_usd=...)`; if url, set `trace_url` in review.json and result.json.
   - repo: `GITHUB_REPOSITORY` else `Path(repo).name`.
   - target: PR URL `$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/pull/<number>` in Actions; `RED2FIX_INSTANCE` on the
     bench (bench/run.py adds `-e RED2FIX_INSTANCE=<iid>` to both docker runs); else `#<number>`.
   - mode: `review` / `fix`. **Assumption:** no try-it entry point exists in the code today, so no `try-it` mode yet.
5. **Secrets**: `redact` on every traced input/output (incl. wrap_openai messages via the shared client), and
   `tools._resolve` refuses `.env*` files the way it refuses `.git` (grep excludes `**/.env*`), so a repo's
   .env never reaches the model or the trace. Root inputs drop the `llm` object.
6. **Dashboard**: `verdict_card`'s links tuple gets `("trace_url", "View trace in LangSmith ↗")`; the existing
   `https://` check and rendering already handle it.
7. **Dependencies**: `uv add langsmith` (pyproject + uv.lock); same pinned version in Dockerfile,
   bench/Dockerfile.swebench and examples/github/red2fix.yml's install step. Workflow Review step env gets
   `LANGSMITH_API_KEY: ${{ secrets.LANGSMITH_API_KEY }}` (empty when unset → disabled).
   scripts/review_local.sh and run_local.sh add `${LANGSMITH_API_KEY:+-e LANGSMITH_API_KEY}` (a key in .env
   already passes via `--env-file`).
8. **tests/conftest.py** pops `LANGSMITH_*` before agent modules import, so tests never trace for real.

## Tests (tests/test_tracing.py)
- No key: monkeypatch `socket.socket.connect` to raise, run a review with `FakeLLM` (reuse `test_review.run`,
  `make_patch`, `script`); verdict proven, no `trace_url`, `"langsmith" not in sys.modules`.
- With key, mocked: subprocess with `LANGSMITH_API_KEY=test`, `LANGSMITH_ENDPOINT=http://127.0.0.1:9`
  (refused, so every upload fails) running the same FakeLLM review: (a) with `RunTree.get_url` patched to a fixed
  URL → `trace_url` in review.json and result.json, verdict proven; (b) unpatched → verdict still proven, no
  `trace_url`, exit 0.
- `redact` replaces a secret env value inside nested inputs; `read_file(root, ".env")` returns an error.

## Verification
1. `uv run pytest`: all green.
2. Paid run: `scripts/review_local.sh good` with the key set. **Needs the user's `LANGSMITH_API_KEY` in .env
   (none there now).** Check verdict proven, `trace_url` in out/review-good/review.json, and the tree in the UI:
   root `review` (metadata present) → phase spans → ChatOpenAI calls and `tool:<name>` spans. Report the URL and a
   one-line tree description; record it in docs/spec/DECISIONS.md (plus a line superseding "deps limited to openai").
3. Commit on `langsmith-tracing` with the plan; no push.
