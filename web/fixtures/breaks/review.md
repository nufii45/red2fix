## Red2Fix: ❌ Breaks tests

**Why:** new failing tests: tests.test_minikit::test_slugify

**Claim:** slugify must replace accented letters with their plain ASCII equivalents rather than inserting dashes.

**Evidence**
- Base (must fail): failed: 2 failed in 0.01s
- Head (must pass): failed (exit 1): 1 failed, 1 passed in 0.01s
- New failing tests: tests.test_minikit::test_slugify

**Review:** The diff fixes the accented character handling by using Unicode NFKD normalization and ASCII encoding, but removes the `strip('-')` call which causes a regression (new failing test `test_slugify`). This unrelated change breaks existing behavior for titles with leading/trailing non-alphanumeric characters.

| Severity | Rule | Where | Note |
|---|---|---|---|
| blocker | No weakened, skipped, xfailed or deleted tests | minikit/text.py:7 | Removing strip('-') causes a new failing test (test_slugify), indicating a regression for titles with leading/trailing non-alphanumeric characters. |
| warning | No changes unrelated to the spec | minikit/text.py:7 | The spec only mentions fixing accented letters; removing strip('-') is an unrelated behavior change not described in the spec. |
| info | Fixes the root cause described in the spec, not just the symptom | minikit/text.py:6 | The NFKD normalization + ASCII encoding correctly decomposes accented letters (e.g., é → e) before slugification, addressing the root cause. |

**Cost:** $0.04 · 30s · Ultra 13 / Nano 2

<details><summary>Repro test</summary>

```python
import pytest

from minikit.text import slugify


def test_slugify_accented_characters():
    """Accented characters should be converted to their ASCII equivalents."""
    assert slugify("Crème Brûlée") == "creme-brulee"


def test_slugify_various_accents():
    """Test various accented characters from different languages."""
    assert slugify("café") == "cafe"
    assert slugify("niño") == "nino"
    assert slugify("Zürich") == "zurich"
    assert slugify("Straße") == "strasse"
    assert slugify("São Paulo") == "sao-paulo"
```

</details>
