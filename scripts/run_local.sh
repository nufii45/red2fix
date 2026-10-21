#!/usr/bin/env bash
# Run the agent in Docker on one seeded demo issue.
# Usage: scripts/run_local.sh <issue number>   (needs Docker running and NEBIUS_API_KEY in .env)
set -euo pipefail
n="${1:?usage: scripts/run_local.sh <issue number, e.g. 1>}"
cd "$(dirname "$0")/.."
docker build -q -t red2fix-agent . >/dev/null
mkdir -p "out/$n"
docker run --rm --env-file .env \
  -v "$PWD/demo/repo:/src:ro" -v "$PWD/demo/issues:/issues:ro" -v "$PWD/out/$n:/out" \
  red2fix-agent --repo /src --issue "/issues/$n.md" --out /out --number "$n"
