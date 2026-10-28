import pytest
from minikit.pagination import paginate, page_count


def test_paginate_partial_last_page():
    """Test that paginate includes the last partial page when items don't divide evenly."""
    # 10 items with page size 3 should give 4 pages: 3 full + 1 partial
    result = paginate(list(range(10)), 3)
    assert result == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]


def test_page_count_ceiling_division():
    """Test that page_count uses ceiling division, not floor division."""
    # 10 items with page size 3 needs 4 pages, not 3
    assert page_count(10, 3) == 4
    
    # Additional cases
    assert page_count(0, 3) == 0
    assert page_count(1, 3) == 1
    assert page_count(3, 3) == 1
    assert page_count(4, 3) == 2
