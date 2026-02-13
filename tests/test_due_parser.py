import pytest
from src.due_parser import parse_period

def test_parse_period_range():
    raw = "2023-01-01 ~ 2023-12-31"
    start, end = parse_period(raw)
    assert start == "2023-01-01"
    assert end == "2023-12-31"

def test_parse_period_dots():
    raw = "2023.01.01 ~ 2023.12.31"
    start, end = parse_period(raw)
    assert start == "2023-01-01"
    assert end == "2023-12-31"

def test_parse_single_date():
    # E.g. deadline only
    raw = "2023-10-10"
    start, end = parse_period(raw)
    # Our logic currently maps single date to both start/end or just end?
    # Logic was: return single_match.group(1), single_match.group(1)
    assert start == "2023-10-10"
    assert end == "2023-10-10"

def test_parse_none():
    assert parse_period(None) == (None, None)
    assert parse_period("") == (None, None)
