# Timeouts with minutes are far too short

We configure job timeouts as strings like `"5m"` and `"1h30m"`. A job with `timeout="5m"` gets killed after about 5 seconds.

```python
>>> from minikit.duration import parse_duration
>>> parse_duration("1h30m")
3630
```

I expected 5400 (one and a half hours). Hours-only and seconds-only values look right.
