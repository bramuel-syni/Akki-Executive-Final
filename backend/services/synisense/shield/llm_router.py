"""Synisense Shield — outbound LLM router (post-de-id).

Phase A:
- Single provider abstraction. The route selects a provider/model based
  on the request's `model_preference` ("analytical" | "generative" |
  "balanced"). Routing logic stays simple — Phase B will expand.
- Uses the universal LLM key via `emergentintegrations`. If
  the key is missing OR the SDK is unavailable, we fall back to a
  deterministic echo response so smoke tests are hermetic in CI.
- **No cloud LLM-NER calls.** The course correction explicitly removed
  this path. NER is now local-only (spaCy) in `deidentifier.py`.

Returns: `(response_text, llm_provider, llm_model)`. The Shield route
records all three in the audit log and trust receipt.

Chunk 18 (Track 4 item 1, 2026-05-21) — `emergentintegrations.LlmChat`
moved to module-level import (was inline inside `invoke()` for the
fallback-availability check pattern). Module-level import pays the
~500ms-1s cost ONCE at process startup instead of on every first
request post-deploy. The `_EMERGENT_AVAILABLE` flag preserves the
graceful-degradation semantics — if the package isn't importable we
still fall back to the echo path on call.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Literal, Tuple

from services.synisense.exceptions import ServiceUnavailable

# Chunk 18 cold-start fix — module-level import + availability probe.
# This replaces the previous inline `try: from emergentintegrations.llm.chat
# import LlmChat, UserMessage` inside invoke(). The probe runs ONCE at
# import time; subsequent invocations skip the try/except cost.
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: WPS433
    _EMERGENT_AVAILABLE = True
except Exception as _exc:  # noqa: BLE001
    LlmChat = None  # type: ignore[assignment]
    UserMessage = None  # type: ignore[assignment]
    _EMERGENT_AVAILABLE = False
    _EMERGENT_IMPORT_ERROR = f"{type(_exc).__name__}: {str(_exc)[:200]}"
else:
    _EMERGENT_IMPORT_ERROR = None

# Chunk 18.5 cold-start fix — lift `litellm` + `get_integration_proxy_url`
# from per-call lazy imports to module-level. The previous code paid the
# import-cache lookup + module init on every cold path even though both
# are pure-python wrappers with no side-effects worth deferring.
# Module-level matches the LlmChat probe style above + uses the same
# `_EMERGENT_AVAILABLE` flag to short-circuit on missing deps.
try:
    import litellm  # noqa: WPS433
    from emergentintegrations.llm.utils import get_integration_proxy_url  # noqa: WPS433
    _LITELLM_AVAILABLE = True
except Exception as _lite_exc:  # noqa: BLE001
    litellm = None  # type: ignore[assignment]
    get_integration_proxy_url = None  # type: ignore[assignment]
    _LITELLM_AVAILABLE = False
    _LITELLM_IMPORT_ERROR = f"{type(_lite_exc).__name__}: {str(_lite_exc)[:200]}"
else:
    _LITELLM_IMPORT_ERROR = None

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
# Deterministic echo fallback. Used when EMERGENT_LLM_KEY is missing OR
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

    Backwards-compatible wrapper around `invoke_with_metering`. Existing
    callers that don't need token metering keep the 3-tuple shape. The
    Shield client + the legacy `/api/synisense/shield/invoke` route both
    use `invoke_with_metering` to capture exact provider usage.
    """
    text, provider, model, _usage = await invoke_with_metering(
        de_id_content,
        model_preference=model_preference,
        timeout_seconds=timeout_seconds,
    )
    return (text, provider, model)


async def invoke_with_metering(
    de_id_content: str,
    *,
    model_preference: ModelPreference = "balanced",
    timeout_seconds: float = 20.0,
) -> Tuple[str, str, str, Dict[str, Any]]:
    """Same contract as `invoke()` but additionally returns a usage dict.

    Chunk 18 (Track 4 item 2, 2026-05-21) — token-accurate metering.

    `usage` shape:
      - Live SDK call: `{"input_tokens": int, "output_tokens": int, "method": "exact"}`
      - Mock / fallback: `{}` (caller must fall back to estimation).

    Implementation: we call `litellm.acompletion` directly instead of
    `LlmChat.send_message` because the latter discards the
    `ModelResponse.usage` payload. The request shape mirrors what
    `LlmChat._execute_completion` builds (same LLM-gateway proxy URL,
    same `custom_llm_provider="openai"` envelope, same model name
    transform for Gemini), so behaviour stays identical to the legacy
    path apart from the additional usage capture.
    """
    provider, model = _provider_for(model_preference)

    # Mock mode — explicit opt-in OR no key configured.
    llm_mode = os.environ.get("SYNISENSE_LLM_MODE", "").lower()
    emergent_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if llm_mode == "mock" or not emergent_key:
        if not emergent_key and llm_mode != "mock":
            log.info("synisense.shield.llm_router: EMERGENT_LLM_KEY absent — using echo fallback")
        return (_mock_invoke(de_id_content), provider + ":mock", model + ":mock", {})

    # Live mode — call litellm directly so we can keep the ModelResponse
    # and pull `usage.prompt_tokens` / `usage.completion_tokens`. Module-
    # level import probe (Chunk 18 cold-start) covers the integrations SDK;
    # `_LITELLM_AVAILABLE` (Chunk 18.5) covers litellm + the proxy URL
    # helper. Both probes run ONCE at import time.
    if not _EMERGENT_AVAILABLE or not _LITELLM_AVAILABLE:
        log.warning(
            "synisense.shield.llm_router: SDK unavailable (emergent=%s litellm=%s)",
            _EMERGENT_IMPORT_ERROR or "ok",
            _LITELLM_IMPORT_ERROR or "ok",
        )
        return (_mock_invoke(de_id_content), provider + ":mock", model + ":mock", {})

    try:
        proxy_url = get_integration_proxy_url()
        if provider == "gemini":
            litellm_model = f"gemini/{model}"
        else:
            litellm_model = model  # openai, anthropic via the universal LLM proxy
        params = {
            "model": litellm_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a privacy-governed assistant. The user message contains "
                        "opaque tokens of the shape [[ENT_XXX_NNN]] — preserve them "
                        "verbatim. Do not invent meanings for them. Respond concisely."
                    ),
                },
                {"role": "user", "content": de_id_content},
            ],
            "api_key": emergent_key,
            "api_base": proxy_url + "/llm",
            "custom_llm_provider": "openai",
        }
        response = await asyncio.wait_for(
            litellm.acompletion(**params),
            timeout=timeout_seconds,
        )
        # Extract text from the OpenAI-compatible response envelope.
        text = ""
        try:
            text = response.choices[0].message.content or ""
        except Exception:  # noqa: BLE001
            text = str(response)
        usage: Dict[str, Any] = {}
        try:
            u = getattr(response, "usage", None)
            prompt = int(getattr(u, "prompt_tokens", 0) or 0)
            completion = int(getattr(u, "completion_tokens", 0) or 0)
            if prompt > 0 or completion > 0:
                usage = {
                    "input_tokens": prompt,
                    "output_tokens": completion,
                    "method": "exact",
                }
        except Exception:  # noqa: BLE001 — usage is best-effort; estimation path absorbs gaps
            usage = {}
        # Suppress unused-import warnings when emergentintegrations imports
        # have already been done at module load.
        _ = (LlmChat, UserMessage)
        return (text, provider, model, usage)
    except asyncio.TimeoutError as exc:
        raise ServiceUnavailable(
            f"LLM provider timeout after {timeout_seconds}s"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        log.warning("synisense.shield.llm_router: invoke failed (%s)", type(exc).__name__)
        raise ServiceUnavailable(
            f"LLM provider call failed: {type(exc).__name__}: {str(exc)[:200]}"
        ) from exc
