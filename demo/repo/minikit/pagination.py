def page_count(total, page_size):
    return total // page_size


def paginate(items, page_size):
    """Split items into consecutive pages of at most page_size items."""
    if page_size < 1:
        raise ValueError("page_size must be at least 1")
    return [items[i * page_size : (i + 1) * page_size] for i in range(page_count(len(items), page_size))]
