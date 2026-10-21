"""Hour-zero check: list live Nemotron IDs and probe each configured model for chat + tool calling.

Usage: NEBIUS_API_KEY=... uv run scripts/hour_zero.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from agent.llm import LLM  # noqa: E402

TOOL = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file from the repository.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
}


def main():
    llm = LLM(ledger_path="hour_zero_ledger.jsonl")

    live = [m.id for m in llm.client.models.list()]
    print("Live Nemotron models:")
    for mid in sorted(live):
        if "nemotron" in mid.lower():
            print("  ", mid)

    for key, mid in config.MODELS.items():
        print(f"\n[{key}] {mid}  {'(listed)' if mid in live else '(NOT in live list)'}")
        try:
            r = llm.chat("probe", [{"role": "user", "content": "Reply with the word ok."}], model_key=key)
            print("  chat:", repr(r.choices[0].message.content)[:80])
            r = llm.chat(
                "probe",
                [{"role": "user", "content": "Read the file setup.py using the tool."}],
                model_key=key,
                tools=[TOOL],
            )
            calls = r.choices[0].message.tool_calls
            print("  tool calling:", "YES" if calls else "no tool_calls returned", calls[0].function if calls else "")
        except Exception as e:  # report and keep probing the other models
            print("  ERROR:", type(e).__name__, str(e)[:200])

    print(f"\nTotal spent: ${llm.spent:.5f}  (ledger: hour_zero_ledger.jsonl)")


if __name__ == "__main__":
    main()
