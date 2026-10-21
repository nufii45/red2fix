# slugify mangles accented titles

Our French recipe pages get broken URLs:

```python
>>> from minikit.text import slugify
>>> slugify("Crème Brûlée")
'cr-me-br-l-e'
```

Expected `'creme-brulee'`. Accented letters should be kept as their plain ASCII letter instead of being turned into dashes.
