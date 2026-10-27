Read docs/spec/red2fix-prd.md §7 FR-2, §10 and plans/2026-10-27-review-core.md first. Save this prompt as
plans/2026-10-28-github-gate.md and implement it.

## Prerequisite (the human does this; stop and ask if missing)
A public GitHub repo, e.g. nufii45/red2fix-demo, containing demo/repo's contents at the root, a
.red2fix.toml, and a repo secret NEBIUS_API_KEY (a project-scoped key with a low spend cap). Ask me for the
repo name before writing anything that hardcodes it.

## Goal
Every PR from a branch in that repo gets a Red2Fix review comment and a `red2fix/verdict` commit status on
its head SHA. Branch protection requires that status, and GitHub auto-merge merges proven PRs. Red2Fix
never calls the merge API.

## Build
1. `.github/workflows/red2fix.yml` (written into red2fix's repo under `examples/github/` and copied into the
   demo repo):
   - on: pull_request [opened, synchronize, reopened]; skip forks
     (`if: github.event.pull_request.head.repo.full_name == github.repository`).
   - permissions: contents: read, pull-requests: write, statuses: write, issues: read. Nothing else.
   - concurrency: group per PR number, cancel-in-progress true (a new push cancels the stale review).
   - Steps: checkout with fetch-depth 0 → set status `pending` → compute
     `git diff <base_sha>...<head_sha> > pr.patch` → `git checkout <base_sha>` (the tree must be at base) →
     build the spec (below) → run the agent → post or update ONE comment (find it by a hidden marker
     `<!-- red2fix -->`) with review.md → set the final status from review.json → upload out/ as an artifact.
   - A final step with `if: failure() || cancelled()` that sets status `error` ("Red2Fix could not complete
     the review"), so a crash never leaves `pending` or `success`.
2. How the agent runs in CI: pip install the agent from the red2fix repo at a pinned ref (or check it out
   alongside) and run `python -m agent.review` directly on the runner. No Docker in CI. Note in the README
   that the runner is the sandbox and holds the key (PRD §10.4).
3. `scripts/gh_spec.py`: if the PR body contains `Fixes #N` / `Closes #N` / `Resolves #N`, the spec is that
   issue's title and body (via the GitHub API with GITHUB_TOKEN) and spec_source = "issue#N"; otherwise the
   PR title and body, spec_source = "pr_description".
4. `scripts/gh_status.py`: maps verdicts to statuses as in PRD §6.1, with a description under 140 chars,
   and `target_url` pointing to the workflow run. The status must be set on the head SHA that was reviewed,
   taken from the event payload, never from HEAD at the end of the job.
5. Write the exact branch-protection and auto-merge settings as a checklist in `examples/github/README.md`
   (required status check `red2fix/verdict`, "require branches to be up to date", allow auto-merge).

## Done when
- In the demo repo, open the five demo PRs from slice 1 as real branches. Each gets the expected verdict
  as a comment and status. The good one auto-merges after you enable auto-merge on it.
- Push a commit to an already-✅ PR: the status goes back to pending, then a fresh verdict.
- Temporarily set a bad NEBIUS_API_KEY on one PR run: the status ends `error`, not success. Restore it.
- Record what happened, with the PR links, in DECISIONS.md. Commit in red2fix. Don't push red2fix itself.

## Addendum (2026-10-27)
1. The workflow needs Red2Fix's code, and nufii45/red2fix is still empty. First scan this repo for secrets
   (git ls-files | grep -iE 'env|secret|key', grep -rn "sk-" on tracked files), show me the result, and after
   I approve push main to nufii45/red2fix. The workflow checks out nufii45/red2fix at a PINNED commit SHA,
   never a branch, so nothing in a demo PR can change the reviewer.
2. Use `pull_request_target`, not `pull_request`. With `pull_request`, a PR that edits
   .github/workflows/red2fix.yml runs its own edited workflow and can set its own status to success.
   `pull_request_target` always runs the workflow from the base branch. Keep the same-repo-only `if:`
   (fork PRs never run), keep the minimal permissions, and check out the PR head SHA explicitly to build
   the patch. State in examples/github/README.md that this trusts the repo's own collaborators, because
   their code runs next to the key.

## Implementation notes (Claude)
- Scan was clean (placeholders only). nufii45/red2fix had a LICENSE-only initial commit; merged with
  --allow-unrelated-histories (user's choice), then pushed once, after the gate code, so the pinned SHA has it.
- Secrets per step: NEBIUS_API_KEY only on the review step; GH_TOKEN only on the steps that call the GitHub
  API; checkouts use persist-credentials: false. The PR's code still runs in the same job as later
  token-holding steps and can rewrite their files, so the gate trusts collaborators (README says so).
- agent/tools.py refuses paths under .git/, so REPRODUCE can't read head commits fetched by fetch-depth 0.
- agent.review gains --spec-source and --head-sha; review.json records require_proof for the status mapping.
- The review step never fails the job on a verdict; gh_status.py maps a missing or unreadable review.json to
  `error`. An `if: failure() || cancelled()` step covers crashes in any other step.
- The demo repo gets issues #1–#3 from demo/issues so "Fixes #N" resolves. inject and inject2 say
  "Related to #N" (not a closing keyword), so their spec is the PR description and the injection reaches the model.
- The example workflow in red2fix carries a placeholder SHA; the demo repo's copy pins the real one.
- Bad-key test: I can't restore a repo secret I can't read, so I give the user the commands.
