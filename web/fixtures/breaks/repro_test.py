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
