import type { Metadata } from "next";

export const metadata: Metadata = { title: "Use it on your own repo" };

const TOML = `rubric = [
  "Fixes the root cause described in the spec, not just the symptom",
  "No changes unrelated to the spec",
  "No weakened, skipped, xfailed or deleted tests",
  "Handles the edge cases the spec mentions",
]
restricted_paths = [".github/**", ".red2fix.toml", "setup.py", "pyproject.toml", "setup.cfg"]
require_proof = true          # Unproven blocks the merge
unrelated_change = "blocker"  # or "warning"
budget_usd = 1.00`;

const WF = "https://github.com/nufii45/red2fix/blob/main/examples/github/red2fix.yml";
const README = "https://github.com/nufii45/red2fix/blob/main/examples/github/README.md";

export default function Install() {
  return (
    <div className="col prose">
      <h1 className="title">your repo</h1>
      <p className="lede">
        Run Red2Fix on every pull request as a GitHub Action. It posts one review comment and sets a{" "}
        <code>red2fix/verdict</code> status on the head commit. Branch protection requires that status, and
        GitHub&apos;s own auto-merge does the merging.
      </p>

      <h2>Setup</h2>
      <ol>
        <li>
          Copy <a href={WF} target="_blank" rel="noreferrer">red2fix.yml ↗</a> to <code>.github/workflows/red2fix.yml</code> on
          your default branch, and set <code>RED2FIX_SHA</code> to a commit of nufii45/red2fix. Use a pinned commit, never a branch.
        </li>
        <li>Add a repository secret <code>NEBIUS_API_KEY</code>. Use a project-scoped key with a low spend cap.</li>
        <li>Optional: add <code>.red2fix.toml</code> at the repo root. These are the defaults:</li>
      </ol>
      <pre className="code">{TOML}</pre>

      <h2>Make it a merge gate</h2>
      <p>In Settings → Branches, add a rule for the default branch:</p>
      <ul>
        <li>Require status checks to pass before merging, with <code>red2fix/verdict</code> as a required check.</li>
        <li>Require branches to be up to date before merging.</li>
      </ul>
      <p>
        In Settings → General → Pull Requests, allow auto-merge. Then choose &ldquo;Enable auto-merge&rdquo; on a
        pull request, and GitHub merges it once the verdict is Proven.
      </p>

      <h2>Private repos</h2>
      <p>
        The review runs inside your own GitHub Actions, on your runner, with your own Nebius key. Your code and
        test output never leave your repo, except for the model calls to Nebius Token Factory. Nothing is sent
        to this site.
      </p>

      <h2>What it trusts</h2>
      <ul>
        <li>It runs the pull request&apos;s code next to the Nebius key, so it trusts your collaborators. Pull requests from forks never run.</li>
        <li>The workflow and the <code>.red2fix.toml</code> policy are read from the base branch, so a pull request can&apos;t loosen its own rules.</li>
        <li>It fails closed: a crash, timeout or unreadable result sets <code>error</code>, never success.</li>
        <li>Python repos tested with pytest. Repos with dependencies need an install step before the review.</li>
      </ul>
      <p style={{ marginTop: "1.5rem" }}>
        <a href={README} target="_blank" rel="noreferrer">Full setup and trust model ↗</a>
      </p>
    </div>
  );
}
