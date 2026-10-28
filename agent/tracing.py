"""Optional LangSmith tracing. Without LANGSMITH_API_KEY nothing here imports langsmith or touches the network,
and with it a failed upload never fails a run: the local ledger stays the source of truth.
"""

import contextlib
import os
import re

ENABLED = bool(os.environ.get("LANGSMITH_API_KEY"))  # GitHub passes "" for a missing secret
TRUNCATE = 2000
_SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD", re.I)
_phase = contextlib.ExitStack()


def redact(obj):
    """obj with the value of every secret-looking env var replaced, at any depth."""
    if isinstance(obj, str):
        for k, v in os.environ.items():
            if len(v) >= 8 and _SECRET_NAME.search(k) and v in obj:
                obj = obj.replace(v, "[redacted]")
        return obj
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    return obj


if ENABLED:
    import langsmith

    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", "red2fix")
    # Children (phases, tools, wrap_openai calls) inherit this client from the root's context.
    CLIENT = langsmith.Client(hide_inputs=redact, hide_outputs=redact)


def traceable(**kw):
    return langsmith.traceable(client=CLIENT, **kw) if ENABLED else (lambda f: f)


@contextlib.contextmanager
def span(name, run_type="chain", inputs=None):
    """A child span; yields record(out), which ends it with the truncated output."""
    if not ENABLED:
        yield lambda out: None
        return
    with langsmith.trace(name, run_type, inputs=inputs or {}) as rt:
        yield lambda out: rt.end(outputs={"output": str(out)[:TRUNCATE]})


def phase(name):
    """Close the previous phase span and open one named `name`."""
    _phase.close()
    if ENABLED:
        _phase.enter_context(span(name))


def finish(**meta):
    """Close the open phase, tag the root run with meta, and return its URL (None when off, unset or on any error).

    The URL is built from LANGSMITH_TRACE_URL_BASE (the project's URL from the LangSmith UI), not read from
    the API: a write-only tracing key can't look it up.
    """
    _phase.close()
    if not ENABLED:
        return None
    try:
        rt = langsmith.get_current_run_tree()
        rt.metadata.update(meta)
        rt.tags = [*(rt.tags or []), str(meta.get("mode")), str(meta.get("verdict"))]
        base = os.environ.get("LANGSMITH_TRACE_URL_BASE", "").split("?")[0].rstrip("/")
        return f"{base}/r/{rt.id}?poll=true" if base else None
    except Exception:
        return None


def root_inputs(inputs):
    """Root span inputs: the arguments as strings, without the LLM client object."""
    return {k: str(v) for k, v in inputs.items() if k != "llm"}
