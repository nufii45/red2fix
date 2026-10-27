# Red2Fix as a GitHub merge gate

Every pull request from a branch in your repo gets a Red2Fix review comment and a `red2fix/verdict` commit
status on its head SHA. Branch protection requires that status; GitHub's own auto-merge does the merging.
Red2Fix never calls the merge API.

## Trust model: read this first

- **This trusts the repo's own collaborators.** The workflow runs the PR's code (its tests, and the repro test
  against its changes) on the runner, in the same job that holds `NEBIUS_API_KEY` and, in later steps, a
  GitHub token with `statuses: write`. Malicious test code could read the key, rewrite the files those later
  steps run or read (including `review.json`), and so set its own status. Same-repo PR authors already have
  write access and could set a status through the API anyway. The gate protects against mistaken PRs, not
  malicious collaborators.
- **Fork PRs never run.** The job's `if:` skips any PR whose head repo is not this repo.
- **The workflow can't be edited by the PR it judges.** `pull_request_target` always runs the workflow file
  from the base branch. With `pull_request`, a PR that edits `.github/workflows/red2fix.yml` would run its
  own edited copy.
- **The reviewer can't be edited by a PR either.** Red2Fix's code is checked out from `nufii45/red2fix` at a
  pinned commit SHA (`RED2FIX_SHA`), never a branch.
- **The policy comes from base.** The tree is moved to the base SHA before the review starts, so
  `.red2fix.toml` is read from base and a PR can't loosen its own rules. `.red2fix.toml` and `.github/**`
  are restricted paths by default: touching them caps the verdict at 🔶 Needs review.
- **Secrets per step.** `NEBIUS_API_KEY` is only on the review step, which has no GitHub token. The token is
  only on the steps that call the GitHub API. Checkouts use `persist-credentials: false`.
- **Fail closed.** A missing or unreadable `review.json` sets `error`, and so does any failed or cancelled
  step. A new push gets a fresh `pending` status, so an old ✅ can't merge new code.
- Use a project-scoped Nebius key with a low spend cap.

## Setup

1. Copy `red2fix.yml` to `.github/workflows/red2fix.yml` on the default branch, and set `RED2FIX_SHA` to a
   commit of `nufii45/red2fix`.
2. Add a repo secret `NEBIUS_API_KEY`.
3. Optional: add `.red2fix.toml` at the repo root (defaults below).

```toml
rubric = [
  "Fixes the root cause described in the spec, not just the symptom",
  "No changes unrelated to the spec",
  "No weakened, skipped, xfailed or deleted tests",
  "Handles the edge cases the spec mentions",
]
restricted_paths = [".github/**", ".red2fix.toml", "setup.py", "pyproject.toml", "setup.cfg"]
require_proof = true   # ⚠️ Unproven blocks the merge
budget_usd = 1.00
```

## Branch protection and auto-merge checklist

Settings → Branches → add a rule (or ruleset) for the default branch:

- [ ] Require status checks to pass before merging
- [ ] Required check: `red2fix/verdict`
- [ ] Require branches to be up to date before merging
- [ ] Do not allow bypassing the above settings (optional; admins can otherwise merge blocked PRs by hand)

Settings → General → Pull Requests:

- [ ] Allow auto-merge

Then, on a PR, choose "Enable auto-merge". GitHub merges it once `red2fix/verdict` is `success`.

## Verdicts

| Verdict | Status |
|---|---|
| ✅ Proven | `success` |
| 🔶 Needs review | `failure` |
| ⚠️ Unproven | `failure` (or `success` if `require_proof = false`) |
| ❌ Doesn't fix / ❌ Breaks tests | `failure` |
| Error | `error` |

## Spec

If the PR body says `Fixes #N`, `Closes #N` or `Resolves #N`, the spec is issue #N's title and body.
Otherwise it is the PR's title and body (`spec_source: pr_description`), which the PR author controls.

## Limits

- Python repos tested with plain pytest. The runner installs only `pytest`; repos with dependencies need an
  install step added before the review.
- The patch is `git diff base...head`. If the base branch has moved and the patch no longer applies, the
  verdict is `error`. "Require branches to be up to date" avoids this.
