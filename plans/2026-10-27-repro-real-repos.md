# Fix REPRODUCE on real repos (bench pilot follow-up)

## Context
Bench pilot 2 (3 instances × gold/failed) gave 0/3 gold approvals. On 5 of 6 reviews REPRODUCE used every
step and then wrote a file with no tests (pytest exit 5). On flask-4992 it guessed the issue's suggested
API (`mode="b"`) while the gold patch added `text=`, so a correct fix got ❌ doesnt_fix. The rejected
attempts weren't saved, so we can't see what the model wrote. Goal: make the proof step work on real repos
before the ~$15 full run, without showing REPRODUCE any implementation from the diff.

User's request (verbatim intent): save rejected attempts; a `submit_test(content)` tool that ends the loop,
15 steps for bench runs only; include the most relevant existing test file; "interface visible,
implementation hidden" signatures for LOCALIZE and REPRODUCE plus a leak test; rerun pilot 2's 6 reviews
one instance at a time; record in DECISIONS.md.

Decisions taken with the user (item 4): show the **full head signature** parsed with `ast` (flask-4992's
change is the continuation line `text: bool = True,` of a multi-line signature, so "def line only" would
show nothing for all 6 pilot patches), and also the **names** of functions whose bodies changed.

## Changes

**1. Saved attempts.** `agent/main.py` `reproduce()`: on every rejection write
`out/repro_attempts/<k>.py` (the code) and `<k>.log` (first line `rejected: <reason>`, then pytest output).
`run_agent` and `review.run_review` remove `out/repro_attempts/` at start alongside `ARTIFACTS`.

**2. submit_test.** `agent/tools.py`: add `SPECS["submit_test"]` (`content: string`).
`Run.tool_loop(..., submit=None)`: when the model calls the `submit` tool with valid JSON, return its
`content` at once (bad args → error tool message, loop continues). At the step limit with `submit` set,
offer only that tool and ask "Call submit_test now with the complete file"; fall back to the reply text.
`reproduce()` allows `READ + ["submit_test"]`, keeps `extract_code()` on the result (handles fenced or
plain content), and uses `run.repro_steps` (new `Run` attribute, default 12). `agent/review.py` gets
`--repro-steps` (default 12); `bench/run.py` review mode passes `--repro-steps 15`. `prompts.REPRODUCE`:
"When the file is ready, call submit_test with its complete content" (```python block stays as fallback).
The fix agent shares `reproduce()` and simply gains the tool.

**3. Related test file.** New `agent/pr_context.py` `related_test(root, paths, exclude)`: deterministic, no
model. For each changed non-test `.py` path: dotted module (strip `.py`, `/`→`.`, drop a leading `src.`/
`lib.`) and stem (`__init__` → package name). Score each tracked test file (`guards.is_test_file`):
+10 if the filename contains `test_<stem>`, +5 if the dotted module appears in its text, +1 per
word-boundary stem hit (capped at 5). Highest score > 0 wins, ties → shorter path. Included via
`tools.read_file(root, path, 1, 150)` with a heading saying it is base code to copy imports and style from.

**4. Interface visible, implementation hidden.** `pr_context.interface(root, patch, paths)`:
- Copy the base versions of the changed non-test `.py` files into a temp dir and
  `git apply --include=<each path>` the PR patch there (base tree untouched, nothing written to `root`).
- `ast`-parse base and head; for every function/method/class build its signature from the AST only
  (`def Q.name(<ast.unparse(args)>) -> <returns>`, `class Name(<bases>)`): never body, docstring or
  decorator text.
- **Signature added/changed:** qualified name absent in base or signature text differs.
- **Body changed (names only):** innermost def containing a changed line: head `+` line numbers from hunk
  headers mapped into head ranges, base `-` line numbers into base ranges; minus the ones already listed.
- `SyntaxError` / apply failure for a file → skipped (bench repos include old code).
- Output block, e.g.
  `src/flask/config.py: changed signature: def Config.from_file(self, filename: str, load: ..., silent: bool=False, text: bool=True) -> bool`
  `src/flask/cli.py: body changed: routes_command`
- `agent/main.py`: `reproduce(run, loc, extra="")` appends `extra` to its user message (like `localize`).
  `review.py` passes paths + interface to LOCALIZE and interface + related test to REPRODUCE.

## Tests (no paid calls)
- `tests/test_pr_context.py`: multi-line signature change shows the full head signature; added function;
  body-only change → name only; deleted lines map to base function; test files excluded; unparsable file
  skipped; `related_test` picks `test_mathlib.py` for `mathlib.py` and returns None when nothing matches.
- `tests/test_review.py` leak test: a PR adding `def clamp_div(a, b, limit)` with distinctive body lines
  → the signature appears in LOCALIZE/REPRODUCE messages, no `+` body line of the diff appears in any
  REPRODUCE (or LOCALIZE) message; the existing `if b == 0` leak test stays.
- `tests/test_main.py`: `submit_test` call ends the loop and its content is the repro; a rejected attempt
  leaves `repro_attempts/1.py` and `1.log`; step limit with submit falls back to text.
- `tests/test_bench_run.py`: review args include `--repro-steps 15`.

## Run (paid, ~$2.50), one instance at a time
`bench/run.py --run-id rv-pilot3 --mode review --patches both --ids <one> -j 2` for flask-4992, then
flask-5063, then requests-2317. After each instance, check that submit_test was used and attempts were
saved; fix any mechanical bug before the next instance. Then `bench/report_review.py rv-pilot3`: gold
approvals and false approvals under both `unrelated_change` settings, plus what the saved attempts show for
every remaining failure. Stop and report; no full run.

## Record
DECISIONS.md: the change (submit_test, 15 bench steps, related test, ast interface) and the pilot-3
numbers next to pilot 2's. Rename this plan to `plans/2026-10-27-repro-real-repos.md`, commit with the work.

## Verification
`uv run pytest -q` green; pilot-3 run dirs contain `repro_attempts/` for every rejection; `run.log` shows
`tool submit_test`; report numbers in `out/bench/rv-pilot3/review_report.md`.
