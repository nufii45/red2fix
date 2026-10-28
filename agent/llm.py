import json
import os
import time

import config
from agent import tracing


class BudgetExceeded(Exception):
    pass


class LLM:
    """Token Factory client that routes by phase and logs every call to a JSONL ledger."""

    def __init__(self, ledger_path, max_usd=config.MAX_USD, client=None):
        if client is None:
            from openai import OpenAI

            client = OpenAI(base_url=config.BASE_URL, api_key=os.environ["NEBIUS_API_KEY"])
            if tracing.ENABLED:
                from langsmith.wrappers import wrap_openai

                client = wrap_openai(client)
        self.client = client
        self.ledger_path = ledger_path
        self.max_usd = max_usd
        self.spent = 0.0

    def chat(self, phase, messages, model_key=None, **kw):
        key = model_key or config.ROUTES[phase]
        model = config.MODELS[key]
        start = time.monotonic()
        resp = self.client.chat.completions.create(model=model, messages=messages, **kw)
        latency_ms = int((time.monotonic() - start) * 1000)

        in_tok = resp.usage.prompt_tokens if resp.usage else 0
        out_tok = resp.usage.completion_tokens if resp.usage else 0
        price_in, price_out = config.PRICES[key]
        cost = (in_tok * price_in + out_tok * price_out) / 1_000_000
        self.spent += cost

        row = {
            "ts": time.time(),
            "phase": phase,
            "model": model,
            "in_tokens": in_tok,
            "out_tokens": out_tok,
            "latency_ms": latency_ms,
            "cost_usd": round(cost, 6),
        }
        with open(self.ledger_path, "a") as f:
            f.write(json.dumps(row) + "\n")

        # Checked after the call so the overspending call is still in the ledger.
        if self.spent > self.max_usd:
            raise BudgetExceeded(f"spent ${self.spent:.4f} > cap ${self.max_usd:.2f}")
        return resp
