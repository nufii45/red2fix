import pytest

from minikit.duration import parse_duration
from minikit.pagination import paginate
from minikit.text import slugify


def test_parse_hours_and_seconds():
    assert parse_duration("2h") == 7200
    assert parse_duration("45s") == 45


def test_parse_invalid():
    with pytest.raises(ValueError):
        parse_duration("soon")


def test_paginate_even():
    assert paginate([1, 2, 3, 4, 5, 6], 3) == [[1, 2, 3], [4, 5, 6]]


def test_paginate_bad_size():
    with pytest.raises(ValueError):
        paginate([1], 0)


def test_slugify():
    assert slugify("Hello World!") == "hello-world"
    assert slugify("  a  b ") == "a-b"
