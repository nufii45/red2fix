"""Set the red2fix/verdict commit status on the reviewed head SHA.

Usage: python scripts/gh_status.py pending|error|REVIEW_JSON
Needs GH_TOKEN, GITHUB_REPOSITORY, HEAD_SHA (from the event payload, never HEAD at the end of the job), RUN_URL.
A missing or unreadable review.json sets `error`, so the gate fails closed.
"""

import json
import os
import sys
import urllib.error
import urllib.request

CONTEXT = "red2fix/verdict"
STATES = {  # PRD §6.1
    "proven": ("success", "✅ Proven"),
    "needs_review": ("failure", "🔶 Needs human review"),
    "doesnt_fix": ("failure", "❌ Doesn't fix"),
    "breaks_tests": ("failure", "❌ Breaks tests"),
    "error": ("error", "Error"),
}


def status_for(arg):
    """(state, description) for "pending", "error" or the path of a review.json."""
    if arg == "pending":
        return "pending", "Red2Fix is reviewing this commit"
    if arg == "error":
        return "error", "Red2Fix could not complete the review"
    try:
        review = json.load(open(arg))
        verdict = review["verdict"]
    except (OSError, ValueError, KeyError, TypeError):
        return "error", "Red2Fix wrote no readable review.json"
    if verdict == "unproven":
        # require_proof is None when the run died before reading the policy; treat that as required.
        state = "success" if review.get("require_proof") is False else "failure"
        label = "⚠️ Unproven"
    else:
        state, label = STATES.get(verdict, ("error", f"Unknown verdict {verdict}"))
    reason = review.get("verdict_reason") or ""
    text = f"{label}: {reason}" if reason else label
    # GitHub answers 422 to 4-byte characters (e.g. 🔶) in a status description.
    text = "".join(c for c in text if ord(c) <= 0xFFFF).strip()
    return state, text if len(text) < 140 else text[:138] + "…"


def main():
    state, description = status_for(sys.argv[1])
    body = {"state": state, "description": description, "context": CONTEXT, "target_url": os.environ.get("RUN_URL")}
    req = urllib.request.Request(
        f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/statuses/{os.environ['HEAD_SHA']}",
        data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"},
    )
    try:
        urllib.request.urlopen(req, timeout=30).close()
    except urllib.error.HTTPError as e:
        sys.exit(f"GitHub refused the status ({e.code}): {e.read().decode(errors='replace')}")
    print(f"{CONTEXT}: {state} - {description}")


if __name__ == "__main__":
    main()
