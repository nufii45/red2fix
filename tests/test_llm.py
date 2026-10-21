import json
from types import SimpleNamespace

import pytest

import config
from agent.llm import LLM, BudgetExceeded


class FakeClient:
    def __init__(self, in_tok, out_tok):
        self.seen = []
        usage = SimpleNamespace(prompt_tokens=in_tok, completion_tokens=out_tok)

        def create(**kw):
            self.seen.append(kw)
            return SimpleNamespace(usage=usage, choices=[])

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


def test_routes_and_ledgers(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    client = FakeClient(1_000_000, 100_000)
    llm = LLM(ledger, max_usd=10, client=client)

    llm.chat("localize", [{"role": "user", "content": "hi"}], temperature=0)

    assert client.seen[0]["model"] == config.MODELS["ultra"]
    assert client.seen[0]["temperature"] == 0
    row = json.loads(ledger.read_text())
    price_in, price_out = config.PRICES["ultra"]
    assert row["phase"] == "localize"
    assert row["in_tokens"] == 1_000_000 and row["out_tokens"] == 100_000
    assert row["cost_usd"] == pytest.approx(price_in + 0.1 * price_out)
    assert llm.spent == pytest.approx(row["cost_usd"])


def test_budget_exceeded_after_logging(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    llm = LLM(ledger, max_usd=0.0001, client=FakeClient(10_000, 0))

    with pytest.raises(BudgetExceeded):
        llm.chat("fix", [])
    assert len(ledger.read_text().splitlines()) == 1
