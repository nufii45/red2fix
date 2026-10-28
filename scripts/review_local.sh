#!/usr/bin/env bash
# Review one demo PR in Docker: demo/prs/<name>/{spec.md,patch.diff} against demo/repo.
# Usage: scripts/review_local.sh <good|wrong|breaks|restricted|inject|inject2|dep-advisory>   (needs Docker and NEBIUS_API_KEY in .env)
set -euo pipefail
name="${1:?usage: scripts/review_local.sh <name of a folder in demo/prs>}"
cd "$(dirname "$0")/.."
[ -d "demo/prs/$name" ] || { echo "no demo PR: demo/prs/$name" >&2; exit 2; }
docker build -q -t red2fix-agent . >/dev/null
mkdir -p "out/review-$name"
docker run --rm --env-file .env ${LANGSMITH_API_KEY:+-e LANGSMITH_API_KEY} ${LANGSMITH_TRACE_URL_BASE:+-e LANGSMITH_TRACE_URL_BASE} \
  -v "$PWD/demo/repo:/src:ro" -v "$PWD/demo/prs/$name:/pr:ro" -v "$PWD/out/review-$name:/out" \
  red2fix-agent agent.review --repo /src --spec /pr/spec.md --patch /pr/patch.diff --out /out --number 1
