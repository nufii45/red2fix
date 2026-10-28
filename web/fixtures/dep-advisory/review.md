## Red2Fix: 🔶 Needs review

**Why:** blocker: No dependencies with known advisories; blocker: No changes unrelated to the spec; proven claim: parse_duration('1h30m') should return 5400

**Claim:** parse_duration('1h30m') should return 5400

**Evidence**
- Base (must fail): failed: 3 failed in 0.01s
- Head (must pass): passed: 3 passed in 0.00s
- New failing tests: none

**Review:** The PR fixes the duration parsing bug (minutes weren't multiplied by 60) and adds the required notify_timeout function with tests. However, the pinned requests==2.19.1 has known security vulnerabilities per the dependency search results, which is a blocker. The notify_timeout function also adds an undocumented timeout=10 parameter.

| Severity | Rule | Where | Note |
|---|---|---|---|
| info | No weakened, skipped, xfailed or deleted tests |  | modifies a test file: tests/test_minikit.py |
| blocker | No dependencies with known advisories | requirements.txt:1 | requests 2.19.1 has published security advisories including and information exposure vulnerabilities (sends Authorization header on https-to-http redirect, certificate verification bypass). The search results show upgrading to 2.20+ fixes the information exposure issue. (source: https://security.snyk.io/package/pip/requests/2.19.1) |
| info | No changes unrelated to the spec | minikit/notify.py:7 | The spec doesn't mention a timeout parameter for the webhook request; adding timeout=10 is a reasonable practice but an undocumented behavioral addition. |

**Cost:** $0.04 · 33s · Ultra 12 / Nano 1

<details><summary>Repro test</summary>

```python
import pytest

from minikit.duration import parse_duration


def test_parse_minutes():
    # Minutes should be converted to seconds (multiplied by 60)
    assert parse_duration("5m") == 300
    assert parse_duration("30m") == 1800


def test_parse_hours_and_minutes():
    # Combined hours and minutes: 1h30m = 3600 + 1800 = 5400
    assert parse_duration("1h30m") == 5400
    assert parse_duration("2h15m") == 8100


def test_parse_all_units():
    # Hours, minutes, and seconds combined
    assert parse_duration("1h30m45s") == 5445
```

</details>

<details><summary>Searches (2)</summary>

- REVIEW: `requests 2.19.1 security advisory` → https://security.snyk.io/package/pip/requests/2.19.1, https://nvd.nist.gov/vuln/detail/CVE-2026-47754, https://security.snyk.io/package/maven/com.fasterxml.jackson.core%3Ajackson-databind/2.19.1
- REVIEW: `requests 2.19.1 deprecated` → https://security.snyk.io/package/pip/requests/2.19.1, https://security.snyk.io/package/npm/angular-translate/2.19.1, https://security.snyk.io/package/npm/moment/2.19.1

</details>
