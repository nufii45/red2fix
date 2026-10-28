# Report job timeouts to the deploy webhook, in correct seconds

We configure job timeouts as strings like `"5m"` and `"1h30m"`. A job with `timeout="5m"` gets killed after about 5 seconds.

```python
>>> from minikit.duration import parse_duration
>>> parse_duration("1h30m")
3630
```

I expected 5400 (one and a half hours). Hours-only and seconds-only values look right.

Our deploy dashboard also needs to see each job's timeout. Please add `minikit.notify.notify_timeout(url, text)`, which posts `{"timeout_seconds": parse_duration(text)}` as JSON to the deploy webhook at `url` with `requests`. Add `requests` to a new `requirements.txt`; we pin exact versions there.
