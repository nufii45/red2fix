## Red2Fix: ❌ Doesn't fix

**Why:** the repro test still fails with the PR applied

**Claim:** Transliterates accented letters to their ASCII equivalents in slugify.

**Evidence**
- Base (must fail): failed: 1 failed in 0.01s
- Head (must pass): failed (exit 1): 1 failed in 0.01s
- New failing tests: none

**Review:** The PR attempts to fix accented letter handling but uses a regex that drops non-ASCII characters entirely instead of transliterating them to ASCII equivalents. The test evidence confirms the fix doesn't work (still failing).

| Severity | Rule | Where | Note |
|---|---|---|---|
| blocker | Fixes the root cause described in the spec, not just the symptom | minikit/text.py:5 | The regex `[^\x00-\x7f]` drops all non-ASCII characters (including accented letters) instead of transliterating them to ASCII equivalents (e.g., é→e, û→u). The spec requires 'creme-brulee' but this produces 'cr-me-br-l-e'. |
| blocker | Handles the edge cases the spec mentions | minikit/text.py:5 | The spec explicitly mentions 'Crème Brûlée' and 'Café au lait' as test cases. The current implementation fails both because it removes accented letters rather than converting them. |

**Cost:** $0.04 · 36s · Ultra 19 / Nano 2

<details><summary>Repro test</summary>

```python
import pytest

from minikit.text import slugify


def test_slugify_accented_letters():
    # Accented characters should be transliterated to their ASCII equivalents
    assert slugify("Crème Brûlée") == "creme-brulee"
    assert slugify("Café au lait") == "cafe-au-lait"
    assert slugify("naïve") == "naive"
    assert slugify("résumé") == "resume"
    assert slugify("São Paulo") == "sao-paulo"
```

</details>
