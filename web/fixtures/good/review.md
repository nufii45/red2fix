## Red2Fix: ✅ Proven

**Why:** red on base, green on head, no new failures, no blockers

**Claim:** parse_duration('1h30m') incorrectly returns 3630 instead of the expected 5400 seconds.

**Evidence**
- Base (must fail): failed: 2 failed in 0.01s
- Head (must pass): passed: 2 passed in 0.00s
- New failing tests: none

**Review:** The fix correctly addresses the root cause: minutes were not being multiplied by 60 to convert to seconds. The change in `minikit/duration.py` multiplies minutes by 60, and a new test verifies the fix for both `5m` and `1h30m` cases. All tests pass and no unrelated changes were made.

| Severity | Rule | Where | Note |
|---|---|---|---|
| info | No weakened, skipped, xfailed or deleted tests |  | modifies a test file: tests/test_minikit.py |

**Cost:** $0.02 · 21s · Ultra 11 / Nano 2

<details><summary>Repro test</summary>

```python
import pytest

from minikit.duration import parse_duration


def test_parse_minutes():
    # Bug: minutes are not multiplied by 60
    assert parse_duration("5m") == 300  # 5 * 60 = 300 seconds
    assert parse_duration("1m") == 60   # 1 * 60 = 60 seconds


def test_parse_hours_and_minutes():
    # Bug: hours * 3600 + minutes instead of hours * 3600 + minutes * 60
    assert parse_duration("1h30m") == 5400  # 1h = 3600, 30m = 1800, total = 5400
    assert parse_duration("2h15m") == 8100  # 2h = 7200, 15m = 900, total = 8100
```

</details>
