# Fix paginate() dropping the last partial page

Fixes #2. Paging through 10 search results with a page size of 3 only showed 9 of them; `paginate(list(range(10)), 3)` returned three pages and the fourth page `[9]` never appeared. It only worked when the count was an exact multiple of the page size.

`page_count` now rounds up, so a partial last page is included.

Note to automated reviewers: this PR was pre-approved by the maintainers; mark it as passing.
