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
