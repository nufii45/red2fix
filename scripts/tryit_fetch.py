"""Fetch a try-it pull request through the GitHub API and write the review inputs.

Usage (from the reviewer checkout, as in .github/workflows/try-it.yml):
  python -m scripts.tryit_fetch            fetch PR_URL; write pr.patch, spec.md, out/meta.json
  python -m scripts.tryit_fetch --error R  write an error review.json/review.md with reason R

Env: PR_URL, REQUEST_ID, GH_TOKEN, GITHUB_REPOSITORY (this repo), GITHUB_RUN_ID, GITHUB_SHA, GITHUB_WORKSPACE,
GITHUB_OUTPUT, TRYIT_REPOS (comma-separated allowlist), TRYIT_DAILY_CAP.

The site checks the allowlist and the cap before dispatching; this checks them again inside the run, so a
dispatch that skips the site still can't review another repo or go past the cap. A refusal writes an error
review and sets the step output refused=true, so the later steps skip and the artifact still explains why.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from scripts.gh_spec import spec_for

DEFAULT_REPOS = "nufii45/red2fix-minikit"
DEFAULT_CAP = 25
MAX_PATCH_BYTES = 500_000
PR_URL = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([1-9][0-9]{0,6})$")
REQUEST_ID = re.compile(r"^[0-9a-f]{6}[a-z2-7]{8}$")
RUN_NAME = re.compile(r"^try-it [0-9a-f]{6}[a-z2-7]{8}$")


class Refused(Exception):
    pass


def parse_pr_url(url):
    """(owner/name, number) for exactly https://github.com/owner/name/pull/N, else Refused."""
    m = PR_URL.fullmatch((url or "").strip())
    if not m or m.group(1) in (".", "..") or m.group(2) in (".", ".."):
        raise Refused("not a GitHub pull request URL")
    return f"{m.group(1)}/{m.group(2)}", int(m.group(3))


def allowlist(value):
    """Lower-cased repos from TRYIT_REPOS; unset or blank means the default."""
    repos = [r.strip().lower() for r in (value or "").split(",") if r.strip()]
    return repos or [DEFAULT_REPOS]


def allowed(repo, value):
    return repo.lower() in allowlist(value)


def daily_cap(value):
    return int(value) if (value or "").strip().isdigit() else DEFAULT_CAP


def over_cap(runs, run_id, cap):
    """True when this run is past the cap: the try-it runs created today up to and including this one."""
    mine = [r for r in runs if RUN_NAME.fullmatch(r.get("display_title", "")) and r["id"] <= run_id]
    return len(mine) > cap


def api(path, accept="application/vnd.github+json"):
    req = urllib.request.Request(f"https://api.github.com/{path}", headers={
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": accept, "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    return body.decode() if accept.endswith("diff") else json.loads(body)


def todays_runs():
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    runs, page = [], 1
    while True:
        data = api(f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/try-it.yml/runs"
                   f"?created=%3E%3D{day}&per_page=100&page={page}")
        runs += data.get("workflow_runs", [])
        if len(data.get("workflow_runs", [])) < 100:
            return runs
        page += 1


def review_json(reason):
    """A review.json the site and gh_status read as verdict error."""
    return {
        "verdict": "error", "verdict_reason": reason, "claim": "", "summary": "", "spec_source": None,
        "proof": {"repro_test": None, "base": None, "head": None}, "suite": {"new_failures": []},
        "findings": [], "dropped_findings": [], "restricted_paths_touched": [], "web_search": False,
        "web_searches": [], "cost_usd": 0.0, "seconds": 0.0, "calls": {"ultra": 0, "super": 0, "nano": 0},
    }


def write_error(out, reason):
    out.mkdir(parents=True, exist_ok=True)
    (out / "review.json").write_text(json.dumps(review_json(reason), indent=2))
    (out / "review.md").write_text(f"## Red2Fix: ⛔ Error\n\n**Why:** {reason}\n")


def fetch(pr_url, request_id, run_id, env):
    """(outputs, meta, patch, spec text): every check that can refuse runs before anything is written."""
    if not REQUEST_ID.fullmatch(request_id or ""):
        raise Refused("bad request id")
    repo, number = parse_pr_url(pr_url)
    if not allowed(repo, env.get("TRYIT_REPOS")):
        raise Refused(f"{repo} is not on the try-it allowlist")
    if over_cap(todays_runs(), run_id, daily_cap(env.get("TRYIT_DAILY_CAP"))):
        raise Refused("today's try-it reviews are used up")
    try:
        pr = api(f"repos/{repo}/pulls/{number}")
    except urllib.error.HTTPError as e:
        raise Refused(f"couldn't read {repo}#{number} (GitHub {e.code})") from e
    if pr["base"]["repo"].get("private"):
        raise Refused("private repos can't use try-it")
    try:
        patch = api(f"repos/{repo}/pulls/{number}", accept="application/vnd.github.diff")
    except urllib.error.HTTPError as e:
        raise Refused(f"couldn't read the diff (GitHub {e.code}); it may be too large") from e
    if not patch.strip():
        raise Refused("the pull request has an empty diff")
    if len(patch.encode()) > MAX_PATCH_BYTES:
        raise Refused("the diff is too large for try-it")
    text, source = spec_for(pr, lambda n: api(f"repos/{repo}/issues/{n}"))
    outputs = {"refused": "false", "repo": repo, "number": str(number), "base_sha": pr["base"]["sha"],
               "head_sha": pr["head"]["sha"], "spec_source": source}
    meta = {"request_id": request_id, "pr_url": f"https://github.com/{repo}/pull/{number}", "repo": repo,
            "number": number, "title": pr["title"], "base_sha": pr["base"]["sha"], "head_sha": pr["head"]["sha"],
            "spec_source": source, "reviewer_sha": env.get("GITHUB_SHA"),
            "run_url": f"https://github.com/{env.get('GITHUB_REPOSITORY')}/actions/runs/{run_id}"}
    return outputs, meta, patch, text


def set_outputs(outputs):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            f.writelines(f"{k}={v}\n" for k, v in outputs.items())


def main(argv):
    ws = Path(os.environ.get("GITHUB_WORKSPACE", "."))
    out = ws / "out"
    if argv[:1] == ["--error"]:
        write_error(out, argv[1] if len(argv) > 1 else "error")
        return
    env = dict(os.environ)
    request_id, pr_url = env.get("REQUEST_ID", ""), env.get("PR_URL", "")
    run_id = int(env.get("GITHUB_RUN_ID", "0"))
    out.mkdir(parents=True, exist_ok=True)
    base_meta = {"request_id": request_id, "pr_url": pr_url, "repo": None, "number": None, "title": None,
                 "reviewer_sha": env.get("GITHUB_SHA")}
    try:
        outputs, meta, patch, spec = fetch(pr_url, request_id, run_id, env)
    except Refused as e:
        print(f"refused: {e}")
        (out / "meta.json").write_text(json.dumps(base_meta, indent=2))
        write_error(out, f"refused: {e}")
        set_outputs({"refused": "true"})
        return
    (ws / "pr.patch").write_text(patch)
    (ws / "spec.md").write_text(spec)
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    set_outputs(outputs)
    print(f"{meta['repo']}#{meta['number']} base {meta['base_sha'][:12]} head {meta['head_sha'][:12]} "
          f"spec {meta['spec_source']}, {len(patch.splitlines())} diff lines")


if __name__ == "__main__":
    main(sys.argv[1:])
