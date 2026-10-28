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