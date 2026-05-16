"""Synisense — illustrative per-provider/per-model pricing table.

Phase F (2026-05-16). Code-controlled (NOT API-editable) — same
governance pattern as `ALLOWED_PURPOSES` in `config.py`.

Values are ILLUSTRATIVE approximations for the bank-QA billing
estimate surface. They are NOT committed pricing, NOT invoiced, and
the frontend MUST mark every figure as "estimated" prominently.

Each entry: `(input_usd_per_million_tokens, output_usd_per_million_tokens,
flat_usd_per_call_assumption)`. We use a flat-per-call estimate
because the Shield audit log doesn't record token counts today —
that's a Phase G+ task once real metering is in place.
"""
from __future__ import annotations

from typing import Dict, Tuple

# (per_million_input_USD, per_million_output_USD, flat_per_call_USD_estimate)
PROVIDER_MODEL_PRICING: Dict[Tuple[str, str], Tuple[float, float, float]] = {
    ("anthropic", "claude-sonnet-4-5-20250929"): (3.00, 15.00, 0.0030),
    ("anthropic", "claude-sonnet-4-5"):          (3.00, 15.00, 0.0030),
    ("anthropic", "claude-haiku-4-5"):           (0.80, 4.00,  0.0008),
    ("anthropic", "claude-opus-4-5"):            (15.00, 75.00, 0.0150),
    ("openai",    "gpt-4o"):                     (2.50, 10.00, 0.0025),
    ("openai",    "gpt-4o-mini"):                (0.15, 0.60,  0.0002),
    ("gemini",    "gemini-2.5-flash"):           (0.30, 1.20,  0.0006),
    ("gemini",    "gemini-3-flash"):             (0.50, 2.00,  0.0010),
    ("gemini",    "gemini-3-pro"):               (1.25, 5.00,  0.0025),
}

# Fallback for unknown combinations — conservative midpoint.
DEFAULT_FLAT_USD_PER_CALL = 0.0020


def flat_cost_for(provider: str, model: str) -> float:
    """Return the per-call flat USD estimate for a (provider, model)
    pair, falling back to the default if unknown."""
    key = (provider or "", model or "")
    entry = PROVIDER_MODEL_PRICING.get(key)
    if entry is None:
        # Try matching by provider alone (model variants).
        for (p, _), v in PROVIDER_MODEL_PRICING.items():
            if p == provider:
                return v[2]
        return DEFAULT_FLAT_USD_PER_CALL
    return entry[2]
