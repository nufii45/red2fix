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