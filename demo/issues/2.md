# paginate() silently drops items

Paging through 10 search results with a page size of 3 only shows 9 of them; the last result never appears.

```python
>>> from minikit.pagination import paginate
>>> paginate(list(range(10)), 3)
[[0, 1, 2], [3, 4, 5], [6, 7, 8]]
```

Expected a fourth page `[9]`. It only works when the count is an exact multiple of the page size.
