"""Write the review spec for a pull_request(_target) event and print its source.

Usage: python scripts/gh_spec.py OUT_FILE   (needs GITHUB_EVENT_PATH, GITHUB_REPOSITORY, GH_TOKEN)
The spec is the linked issue when the PR body says Fixes/Closes/Resolves #N, else the PR title and body.
"""

import json
import os
import re
import sys
import urllib.request

LINK = re.compile(r"\b(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?)\s+#(\d+)\b", re.I)


def linked_issue(body):
    m = LINK.search(body or "")
    return int(m.group(1)) if m else None


def github(path):
    req = urllib.request.Request(
        f"https://api.github.com/{path}",
        headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def spec_for(pr, fetch_issue):
    """(spec text, spec_source)."""
    n = linked_issue(pr.get("body"))
    if n:
        issue = fetch_issue(n)
        return f"# {issue['title']}\n\n{issue.get('body') or ''}\n", f"issue#{n}"
    return f"# {pr['title']}\n\n{pr.get('body') or ''}\n", "pr_description"


def main():
    pr = json.load(open(os.environ["GITHUB_EVENT_PATH"]))["pull_request"]
    repo = os.environ["GITHUB_REPOSITORY"]
    text, source = spec_for(pr, lambda n: github(f"repos/{repo}/issues/{n}"))
    with open(sys.argv[1], "w") as f:
        f.write(text)
    print(source)


if __name__ == "__main__":
    main()
