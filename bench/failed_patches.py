"""Pick one officially unresolved patch per frozen instance from public SWE-bench Lite submissions.

Usage: uv run bench/failed_patches.py [--systems 12]   writes bench/failed_patches.json

SWE-bench/experiments holds entries, not artifacts: each Lite system has results/results.json (resolved
ids) and metadata.yaml, whose `assets` point at s3://swe-bench-submissions/lite/<system>/logs. That
public bucket has logs/<instance>/patch.diff and report.json (the official harness's verdict) per instance.
A patch qualifies when report.json says it applied to the base commit and did not resolve the instance.
Systems are tried strongest first (most resolved), then most recent.
"""

import argparse
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTANCES = ROOT / "bench" / "instances.json"
OUT = ROOT / "bench" / "failed_patches.json"
LISTING = "https://api.github.com/repos/SWE-bench/experiments/contents/evaluation/lite"
RAW = "https://raw.githubusercontent.com/SWE-bench/experiments/main/evaluation/lite"
S3 = "https://swe-bench-submissions.s3.amazonaws.com"
ASSETS = re.compile(r"s3://swe-bench-submissions/(lite/[^/\s]+)/logs")


def get(url):
    """Response text, or None for a 404."""
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def systems():
    """[(name, s3 prefix, resolved ids)], strongest first, then most recent. Systems not on S3 are skipped."""
    found = []
    for entry in json.loads(get(LISTING)):
        if entry["type"] != "dir":
            continue
        name = entry["name"]
        meta, results = get(f"{RAW}/{name}/metadata.yaml"), get(f"{RAW}/{name}/results/results.json")
        m = ASSETS.search(meta or "")
        if m and results:
            found.append((name, m.group(1), set(json.loads(results).get("resolved", []))))
    return sorted(found, key=lambda s: (len(s[2]), s[0]), reverse=True)


def choose(iid, ranked, fetch_report, fetch_patch):
    """{system, patch} for the first system whose patch for iid officially applied and did not resolve it."""
    for name, prefix, resolved in ranked:
        if iid in resolved:
            continue
        report = (fetch_report(prefix, iid) or {}).get(iid, {})
        if not report.get("patch_successfully_applied") or report.get("resolved") is not False:
            continue
        patch = fetch_patch(prefix, iid)
        if patch and patch.strip():
            return {"system": name, "patch": patch}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", type=int, default=12, help="how many of the strongest systems to try")
    a = ap.parse_args()
    ranked = systems()[: a.systems]
    print("trying:", ", ".join(f"{n} ({len(r)})" for n, _, r in ranked))

    def fetch_report(prefix, iid):
        text = get(f"{S3}/{prefix}/logs/{iid}/report.json")
        return json.loads(text) if text else None

    def fetch_patch(prefix, iid):
        return get(f"{S3}/{prefix}/logs/{iid}/patch.diff")

    chosen, missing = {}, []
    for inst in json.loads(INSTANCES.read_text()):
        iid = inst["instance_id"]
        pick = choose(iid, ranked, fetch_report, fetch_patch)
        if pick:
            chosen[iid] = pick
            print(f"{iid:40} {pick['system']}")
        else:
            missing.append(iid)
            print(f"{iid:40} (no usable failed patch)")
    OUT.write_text(json.dumps(chosen, indent=2) + "\n")
    print(f"{len(chosen)} failed patches -> {OUT}; none for: {', '.join(missing) or '-'}")


if __name__ == "__main__":
    main()
