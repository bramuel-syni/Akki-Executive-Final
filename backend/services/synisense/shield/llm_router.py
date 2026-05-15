"""Synisense Shield — outbound LLM router (post-de-id).

Phase A:
- Single provider abstraction. The route selects a provider/model based
  on the request's `model_preference` ("analytical" | "generative" |
  "balanced"). Routing logic stays simple — Phase B will expand.
- Uses the Emergent universal LLM key via `emergentintegrations`. If
  the key is missing OR the SDK is unavailable, we fall back to a
  deterministic echo response so smoke tests are hermetic in CI.
- **No cloud LLM-NER calls.** The course correction explicitly removed
  this path. NER is now local-only (spaCy) in `deidentifier.py`.

Returns: `(response_text, llm_provider, llm_model)`. The Shield route
records all three in the audit log and trust receipt.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Literal, Tuple

from services.synisense.exceptions import ServiceUnavailable

log = logging.getLogger("synisense.shield.llm_router")

ModelPreference = Literal["analytical", "generative", "balanced"]

# Provider/model selection table — locked for Phase A.
_PROVIDER_TABLE: dict = {
    "analytical": ("anthropic", "claude-sonnet-4-5-20250929"),
    "generative": ("openai", "gpt-4o"),
    "balanced":   ("gemini", "gemini-2.5-flash"),
}


def _provider_for(preference: ModelPreference) -> Tuple[str, str]:
    return _PROVIDER_TABLE.get(preference, _PROVIDER_TABLE["balanced"])


# ─────────────────────────────────────────────────────────────────────
# Deterministic echo fallback. Used when Emergent LLM key is missing OR
# when SYNISENSE_LLM_MODE=mock. Smoke tests opt into this so they don't
# burn LLM budget. The fallback intentionally echoes the de-identified
# content verbatim so `reidentify()` has tokens to swap back, exercising
# the full pipeline.
# ─────────────────────────────────────────────────────────────────────
def _mock_invoke(de_id_content: str) -> str:
    return de_id_content


async def invoke(
    de_id_content: str,
    *,
    model_preference: ModelPreference = "balanced",
    timeout_seconds: float = 20.0,
) -> Tuple[str, str, str]:
    """Call the consumer LLM with de-identified content.

    Returns `(response_text, provider, model)`. Raises
    `ServiceUnavailable` on hard failure (timeout / SDK exception /
    network) so the Shield can fail-closed and emit a 503.
    """
    provider, model = _provider_for(model_preference)

    # Mock mode — explicit opt-in OR no key configured.
    llm_mode = os.environ.get("SYNISENSE_LLM_MODE", "").lower()
    emergent_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if llm_mode == "mock" or not emergent_key:
        if not emergent_key and llm_mode != "mock":
            log.info("synisense.shield.llm_router: EMERGENT_LLM_KEY absent — using echo fallback")
        return (_mock_invoke(de_id_content), provider + ":mock", model + ":mock")

    # Live mode — emergentintegrations.
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: WPS433
    except Exception as exc:  # noqa: BLE001
        log.warning("synisense.shield.llm_router: emergentintegrations unavailable (%s)",
                    type(exc).__name__)
        return (_mock_invoke(de_id_content), provider + ":mock", model + ":mock")

    try:
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"synisense-shield-{uuid.uuid4().hex[:8]}",
            system_message=(
                "You are a privacy-governed assistant. The user message contains "
                "opaque tokens of the shape [[ENT_XXX_NNN]] — preserve them "
                "verbatim. Do not invent meanings for them. Respond concisely."
            ),
        ).with_model(provider, model)
        msg = UserMessage(text=de_id_content)
        raw = await asyncio.wait_for(chat.send_message(msg), timeout=timeout_seconds)
        text = raw if isinstance(raw, str) else str(raw)
        return (text, provider, model)
    except asyncio.TimeoutError as exc:
        raise ServiceUnavailable(
            f"LLM provider timeout after {timeout_seconds}s"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        log.warning("synisense.shield.llm_router: invoke failed (%s)", type(exc).__name__)
        raise ServiceUnavailable(
            f"LLM provider call failed: {type(exc).__name__}: {str(exc)[:200]}"
        ) from exc
