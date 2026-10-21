BASE_URL = "https://api.tokenfactory.nebius.com/v1/"

# Placeholders from the spec; replace with the exact strings from scripts/hour_zero.py.
MODELS = {
    "ultra": "nvidia/Nemotron-3-Ultra-550b-a55b",
    "super": "nvidia/nemotron-3-super-120b-a12b",
    "nano": "nvidia/nvidia-nemotron-3-nano-30b-a3b",
}

# USD per 1M tokens: (input, output). Super price is unverified; confirm on the Token Factory pricing page.
PRICES = {
    "ultra": (1.00, 3.00),
    "super": (0.30, 0.90),
    "nano": (0.06, 0.24),
}

ROUTES = {
    "triage": "nano",
    "localize": "ultra",
    "reproduce": "ultra",
    "verify_red": "nano",
    "fix": "super",
    "escalate": "ultra",
    "summarize": "nano",
}

MAX_FIX_ITERS = 8
MAX_ESCALATIONS = 2
MAX_USD = 1.00
MAX_SECONDS = 600

TOOL_OUTPUT_LINES = 200
