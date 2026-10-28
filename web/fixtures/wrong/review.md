## Red2Fix: ❌ Doesn't fix

**Why:** the repro test still fails with the PR applied

**Claim:** Parsing minute‑based durations results in incorrect timeout values.

**Evidence**
- Base (must fail): failed: 3 failed in 0.01s
- Head (must pass): failed (exit 1): 1 failed, 2 passed in 0.01s
- New failing tests: none

**Review:** The fix only multiplies minutes by 60 when hours is zero, but the spec requires minutes to be converted to seconds in all cases (e.g., "1h30m" should be 5400, not 3630). The root cause is that minutes are never multiplied by 60 when hours are present.

| Severity | Rule | Where | Note |
|---|---|---|---|
| blocker | Fixes the root cause described in the spec, not just the symptom | minikit/duration.py:10 | This only fixes the minutes-only case. For "1h30m", hours=1 so minutes stays 30, returning 3630 instead of 5400. Minutes must always be multiplied by 60. |
| blocker | Handles the edge cases the spec mentions | minikit/duration.py:12 | With the current fix, "1h30m" still returns 3630 (1*3600 + 30) instead of the expected 5400 (1*3600 + 30*60). The spec explicitly mentions this case. |

**Cost:** $0.02 · 18s · Ultra 7 / Nano 1

<details><summary>Repro test</summary>

```python
import pytest

from minikit.duration import parse_duration


def test_parse_minutes():
    # Minutes should be converted to seconds (multiplied by 60)
    assert parse_duration("5m") == 300
    assert parse_duration("1m") == 60


def test_parse_hours_and_minutes():
    # Hours and minutes combined: 1h30m = 1*3600 + 30*60 = 3600 + 1800 = 5400
    assert parse_duration("1h30m") == 5400
    assert parse_duration("2h15m") == 8100


def test_parse_minutes_and_seconds():
    # Minutes and seconds combined: 5m30s = 5*60 + 30 = 330
    assert parse_duration("5m30s") == 330
```

</details>
