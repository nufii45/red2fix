BASE_URL = "https://api.tokenfactory.nebius.com/v1/"

# Exact IDs from the live /v1/models list (2026-10-22).
MODELS = {
    "ultra": "nvidia/Nemotron-3-Ultra-550b-a55b",
    "super": "nvidia/nemotron-3-super-120b-a12b",
    "nano": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
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
    "verify_red": "ultra",  # Nano accepted a test that failed on its own bug (bench pilot 3)
    "fix": "super",
    "escalate": "ultra",
    "summarize": "nano",
    "triage_review": "nano",
    "review": "ultra",
}

MAX_FIX_ITERS = 8
MAX_ESCALATIONS = 2
MAX_USD = 1.00
MAX_SECONDS = 600

TOOL_OUTPUT_LINES = 200
