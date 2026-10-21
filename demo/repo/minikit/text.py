import re


def slugify(text):
    """Turn a title into a URL slug: 'Hello World!' -> 'hello-world'."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")
