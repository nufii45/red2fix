import pytest
from minikit.pagination import paginate


def test_paginate_partial_last_page():
    """Test that paginate includes the last partial page when total is not a multiple of page_size."""
    # 10 items with page_size=3 should give 4 pages: [0,1,2], [3,4,5], [6,7,8], [9]
    result = paginate(list(range(10)), 3)
    assert result == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]
    assert len(result) == 4


def test_page_count_rounds_up():
    """Test that page_count rounds up for partial pages."""
    from minikit.pagination import page_count
    # 10 items with page_size=3 should give 4 pages (not 3)
    assert page_count(10, 3) == 4
    # Additional cases
    assert page_count(1, 3) == 1
    assert page_count(4, 3) == 2
    assert page_count(6, 3) == 2
