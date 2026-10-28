# Recreate the demo repo as nufii45/red2fix-minikit under the personal identity

## Context
The public demo repo nufii45/red2fix-demo has 8 commits authored as rarceo@alazzamgroup.com (work email).
The demo is rebuilt in a new repo, nufii45/red2fix-minikit, with fresh history authored only as
Imman Bufi <bufiimman45@gmail.com>. The old repo is then deleted. The content is unchanged: demo/repo
at the root, the gate workflow, .red2fix.toml, issues #1-#3 and the six demo PRs (#4-#9, same order as before).

User decisions (2026-10-28): name `red2fix-minikit`; push Red2Fix main and pin e6ccef4; delete
nufii45/red2fix-demo; keep the old DECISIONS.md entries as history and add a new entry.

Known state:
- Old clone: `/private/tmp/claude-501/-Users-imman-dev-Red2Fix/a07ecfae-…/scratchpad/red2fix-demo`
  (OLD below). Its minikit/ and tests/ are identical to `demo/repo`. Its workflow differs from
  `examples/github/red2fix.yml` only in the pinned SHA.
- Global git config is already bufiimman45@gmail.com / "nufii45". No local config is set anywhere.
- nufii45/red2fix-minikit doesn't exist yet. **Stop and ask if it's still missing or not empty.**
- The gh token has `repo` but not `delete_repo`.
- Red2Fix local main (e6ccef4) is 2 commits ahead of origin (6e0dde4). All of its commits are
  bufiimman45@gmail.com. Secret scan: only `NEBIUS_API_KEY=...` placeholders.

## Steps
0. **Preconditions (the user does these):** create the empty public repo, then run
   `! gh secret set NEBIUS_API_KEY -R nufii45/red2fix-minikit`. Without the secret every review ends `error`.
1. **Identity:** run `git config user.email bufiimman45@gmail.com` and `git config user.name "Imman Bufi"`
   in OLD, in ~/dev/Red2Fix and in the new clone NEW (`<scratchpad>/red2fix-minikit`). Print
   `git config user.email` for each.
2. **Save the old PR text before deleting anything:** `gh pr view N -R nufii45/red2fix-demo --json title,body`
   for N = 4..9 into `<scratchpad>/bodies/`, keyed by branch. Get commit messages from
   `git -C OLD log -1 --format=%B origin/pr/<name>`.
3. **Pin the reviewer:** `git push origin main` in ~/dev/Red2Fix, then pin the full SHA of e6ccef4.
4. **Build NEW:** `git init -b main`. Copy `demo/repo/{minikit,tests}` without `__pycache__`.
   Copy `README.md`, `.gitignore` and `.red2fix.toml` from OLD. Copy the workflow to
   `.github/workflows/red2fix.yml` from `examples/github/red2fix.yml` with `REPLACE_WITH_A_COMMIT_SHA`
   replaced by the full SHA. Make one commit: "minikit with seeded bugs, Red2Fix gate (reviewer pinned at e6ccef4)".
5. **PR branches:** for each of good, wrong, breaks, restricted, inject and inject2:
   `git checkout -b pr/<name> main`, `git apply ~/dev/Red2Fix/demo/prs/<name>/patch.diff`, then commit
   with the old message.
6. **Identity gate:** `git log --all --format='%ae %ce' | sort -u` must print only bufiimman45@gmail.com.
   Stop if it doesn't.
7. **Publish:**
   - Push main.
   - Create issues #1-#3 from `demo/issues/{1,2,3}.md` (the title is the `# ` line, the body is the rest).
   - `gh repo edit nufii45/red2fix-minikit --enable-auto-merge`.
   - Set branch protection with `gh api -X PUT repos/nufii45/red2fix-minikit/branches/main/protection`:
     required status check `red2fix/verdict`, `strict: true`, `enforce_admins: false`, no required
     reviews, no restrictions. This matches the old repo.
   - Push the six branches and open PRs in the same order with the saved titles and bodies, so they become
     #4-#9. inject and inject2 keep "Related to #N".
   - Don't enable auto-merge on any PR. Only the repo setting was asked for.
8. **Watch the verdicts** with `gh pr checks` until each PR has a final `red2fix/verdict`.
   Expected: #4 success; #5, #6 and #8 failure; #7 and #9 needs-review (failure).
9. **Delete the old repo:** the user runs `! gh auth refresh -h github.com -s delete_repo`. I confirm once
   more, then run `gh repo delete nufii45/red2fix-demo --yes`. The deletion is permanent and the old PR links
   in DECISIONS.md go dead.
10. **Red2Fix repo:**
   - In `tests/test_dashboard.py`, change the `red2fix-demo/pull/4` fixture URL to `red2fix-minikit`.
   - In `docs/spec/DECISIONS.md`, add a dated entry: the demo was moved to nufii45/red2fix-minikit with
     fresh history under the personal identity, the reviewer is pinned at e6ccef4, record each verdict with
     its PR link, and note that red2fix-demo was deleted. Keep lines 31-33 as they are.
   - `examples/github/` and the PRD only name `nufii45/red2fix` (the reviewer), so they stay unchanged.
     There is no root README.
   - Rename this plan to `plans/2026-10-28-minikit-repo.md`. Commit it with the two files above.
     Don't commit `plans/red2fix-v2-build-prompts.md` and don't push this commit.

## Verification
- Step 1 prints bufiimman45@gmail.com three times. Step 6 prints only that email.
- `gh api repos/nufii45/red2fix-minikit/commits?sha=main --jq '.[].commit.author.email'` returns only that email.
- Branch protection lists `red2fix/verdict` with strict mode, and `allow_auto_merge` is true
  (`gh api repos/nufii45/red2fix-minikit --jq .allow_auto_merge`).
- Each of PRs #4-#9 has a review comment and the expected status.
- `uv run pytest tests/test_dashboard.py` passes.
