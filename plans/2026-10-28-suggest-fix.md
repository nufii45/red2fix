Read agent/main.py (fix, check, confirm) and agent/review.py. Save as plans/2026-10-29-suggest-fix.md.

## Goal
When the verdict is doesnt_fix or breaks_tests and policy suggest_fix = true, run the existing FIX loop
starting from the PR head (repro committed, PR committed), with the baseline from BASE. On success, CONFIRM
proves the repro fails on head and passes with the suggestion; save suggested_fix.diff and add a
"Suggested fix (proven)" section to review.md. The suggestion never changes the verdict and is never pushed.
Separate budget cap: policy suggest_fix_budget_usd (default 0.75), and stop at MAX_FIX_ITERS as today.
Not for unproven (there's no failing test to fix against).

## Done when
Tests with FakeLLM: suggestion found → section present and verdict unchanged; suggestion fails → review
still written. One paid run on demo/prs/wrong gives a proven suggestion. In the GitHub workflow, the comment
shows the suggestion as a ```diff block.

## Implementation notes (Claude, 2026-10-28)
- `suggest_fix` defaults to false: it spends up to `suggest_fix_budget_usd` more on every failing PR, and bench runs
  use the defaults. The demo repo opts in through its `.red2fix.toml`.
- It runs after `decide()`, so the verdict is final first, and only for doesnt_fix and breaks_tests with a repro.
  unproven (including the new "same failure on base and head" case) never triggers it.
- The FIX loop runs on the PR head commit. Its first feedback is `check()` against the BASE baseline, so a breaks_tests
  PR is told which tests it broke. `fix()` gains an optional `feedback`.
- CONFIRM, from a clean PR head: something fails without the suggestion (the repro, or a test that's new against
  base), and with it the repro passes and nothing new fails. This covers breaks_tests PRs whose repro already passes.
- The budget is enforced by raising the LLM cap to spent + `suggest_fix_budget_usd`. Time: a fresh
  `config.SUGGEST_SECONDS` = 300 window, so review + suggestion stay under the workflow's 20-minute job.
- Paid run on demo/prs/wrong: doesnt_fix, with a proven suggestion that replaces `if not hours: minutes *= 60` with
  `minutes *= 60`. $0.019, 29 s.
