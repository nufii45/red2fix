import pytest

from minikit.text import slugify


def test_slugify_accented_letters():
    # Accented characters should be transliterated to their ASCII equivalents
    assert slugify("Crème Brûlée") == "creme-brulee"
    assert slugify("Café au lait") == "cafe-au-lait"
    assert slugify("naïve") == "naive"
    assert slugify("résumé") == "resume"
    assert slugify("São Paulo") == "sao-paulo"
