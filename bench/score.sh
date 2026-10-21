#!/usr/bin/env bash
# Score with the official SWE-bench harness (hidden tests).
# Usage: bench/score.sh <run-id>   score out/bench/<run-id>/preds.jsonl
#        bench/score.sh gold       sanity-check the harness with the reference patches (no credits)
set -euo pipefail
id="${1:?usage: bench/score.sh <run-id> | gold}"
cd "$(dirname "$0")/.."
if [ "$id" = gold ]; then
  ids=$(python3 -c "import json; print(' '.join('-i ' + i['instance_id'] for i in json.load(open('bench/instances.json'))))")
  # shellcheck disable=SC2086
  uvx --python 3.11 swebench eval SWE-bench/SWE-bench_Lite --gold --run-id gold -j 2 $ids
else
  uvx --python 3.11 swebench eval SWE-bench/SWE-bench_Lite -p "out/bench/$id/preds.jsonl" --run-id "$id" -j 2
fi
cat "logs/evaluation/$id/results.json" 2>/dev/null || ls -R "logs/evaluation/$id" | head -20
