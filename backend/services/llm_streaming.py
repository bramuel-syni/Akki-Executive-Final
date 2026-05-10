"""Phase B.3 / Phase A.1 — direct-provider token streaming + strategic failover.

Replaces the briefings-local Claude→Gemini band-aid (option-b) with a
service-layer mechanism that benefits every LLM-using surface.

Design
------
* `stream_llm_direct(...)` is an async generator yielding `LlmStreamChunk`
  objects (`kind ∈ {delta, done, error}`).
* Per-provider direct streaming:
    - Anthropic — official `anthropic` SDK `messages.stream`.
    - Gemini    — official `google-genai` SDK `aio.generate_content_stream`.
    - OpenAI    — `litellm.acompletion(stream=True)` against the Emergent
                  integrations proxy (no separate OPENAI_API_KEY needed).
                  This is the same library `emergentintegrations.LlmChat`
                  already uses for non-streaming proxy calls; we just turn
                  on `stream=True`.
* If the direct SDK call for a provider fails (e.g. tier 429 on Gemini
  Pro), we attempt a litellm-stream retry through the Emergent proxy
  (still token-level streaming) before giving up and emitting one
  buffered delta. This means proxy-buffered is the LAST resort, not the
  default for non-Anthropic providers.
* The `done` chunk always carries `provider_used` and `fallback_triggered`
  so callers can audit which path served the request.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, List, Optional, Tuple

logger = logging.getLogger("akki.llm.stream")

# ---------------------------------------------------------------------------
# Public dataclass — stable shape for callers (chat router, briefings, etc.)
# ---------------------------------------------------------------------------
@dataclass
class LlmStreamChunk:
    kind: str                                # "delta" | "done" | "error"
    text: str = ""
    provider_used: str = ""                  # "anthropic_direct" | "gemini_direct" | "proxy_buffered"
    fallback_triggered: bool = False
    error: Optional[str] = None
    usage: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Provider detection from a model id (matches the strings llm_service uses)
# ---------------------------------------------------------------------------
def provider_for_model(model_id: str) -> str:
    """Return one of: 'anthropic', 'gemini', 'openai'."""
    m = (model_id or "").lower()
    if m.startswith("claude") or "sonnet" in m or "opus" in m or "haiku" in m:
        return "anthropic"
    if m.startswith("gemini") or "gemini" in m:
        return "gemini"
    return "openai"


# ---------------------------------------------------------------------------
# Boot-time mode probe — used by server.py to print the streaming banner
# ---------------------------------------------------------------------------
def streaming_mode_per_provider() -> Dict[str, str]:
    """Return {'claude': 'direct_stream'|'proxy_buffered', 'gemini': ..., 'gpt': ...}.

    Honours `CHAT_STREAMING_MODE` if explicitly set to one of:
        proxy_buffered   — force proxy on every provider (rollback path)
        proxy_stream     — not implemented today (proxy doesn't really stream)
        direct_stream    — direct where keys are present, proxy_buffered fallback
    Default behaviour: direct where keys present, else proxy_buffered.

    Phase A.1 — `gpt` reports `direct_stream` because OpenAI streaming
    now goes through the Emergent integrations proxy via litellm with
    `stream=True` (no separate OPENAI_API_KEY required).
    """
    forced = (os.environ.get("CHAT_STREAMING_MODE") or "").strip().lower()
    has_anth = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_gem  = bool(os.environ.get("GEMINI_API_KEY"))
    has_proxy = bool(os.environ.get("EMERGENT_LLM_KEY"))
    if forced == "proxy_buffered":
        return {"claude": "proxy_buffered", "gemini": "proxy_buffered", "gpt": "proxy_buffered"}
    return {
        "claude": "direct_stream" if has_anth else "proxy_buffered",
        "gemini": "direct_stream" if has_gem  else "proxy_buffered",
        "gpt":    "direct_stream" if has_proxy else "proxy_buffered",
    }


# ---------------------------------------------------------------------------
# Direct streaming — Anthropic
# ---------------------------------------------------------------------------
async def _stream_anthropic(
    *, model_id: str, system_msg: str, user_text: str,
    max_tokens: int = 4096,
) -> AsyncIterator[LlmStreamChunk]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=api_key)
    parts: List[str] = []
    async with client.messages.stream(
        model=model_id,
        max_tokens=max_tokens,
        system=system_msg or "You are a helpful assistant.",
        messages=[{"role": "user", "content": user_text}],
    ) as stream:
        async for delta in stream.text_stream:
            if not delta:
                continue
            parts.append(delta)
            yield LlmStreamChunk(
                kind="delta", text=delta, provider_used="anthropic_direct",
            )
        # `stream.get_final_message()` returns usage; cheap to await.
        try:
            final = await stream.get_final_message()
            usage = {
                "input_tokens":  getattr(final.usage, "input_tokens", 0),
                "output_tokens": getattr(final.usage, "output_tokens", 0),
            }
        except Exception:
            usage = {}
    yield LlmStreamChunk(
        kind="done", text="".join(parts),
        provider_used="anthropic_direct", usage=usage,
    )


# ---------------------------------------------------------------------------
# Direct streaming — Gemini (google-genai SDK ≥ 1.71)
# ---------------------------------------------------------------------------
async def _stream_gemini(
    *, model_id: str, system_msg: str, user_text: str,
    max_tokens: int = 4096,
) -> AsyncIterator[LlmStreamChunk]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    from google import genai
    from google.genai import types as gtypes
    client = genai.Client(api_key=api_key)
    cfg = gtypes.GenerateContentConfig(
        max_output_tokens=max_tokens,
        system_instruction=system_msg or "You are a helpful assistant.",
    )
    parts: List[str] = []
    # `aio.models.generate_content_stream` returns a coroutine that yields
    # an async iterator of GenerateContentResponse chunks.
    stream = await client.aio.models.generate_content_stream(
        model=model_id,
        contents=user_text,
        config=cfg,
    )
    async for chunk in stream:
        text = getattr(chunk, "text", None)
        if not text:
            continue
        parts.append(text)
        yield LlmStreamChunk(
            kind="delta", text=text, provider_used="gemini_direct",
        )
    yield LlmStreamChunk(
        kind="done", text="".join(parts),
        provider_used="gemini_direct",
    )


# ---------------------------------------------------------------------------
# Direct streaming — OpenAI (and Gemini fallback) via LiteLLM through the
# Emergent integrations proxy. This is the SAME library and proxy URL
# `emergentintegrations.LlmChat` already uses for non-streaming calls; we
# just turn on `stream=True` and iterate the OpenAI-compat delta chunks.
# No new SDK, no new key — re-uses EMERGENT_LLM_KEY.
# ---------------------------------------------------------------------------
async def _stream_via_litellm_proxy(
    *, provider: str, model_id: str, system_msg: str, user_text: str,
    max_tokens: int = 4096,
) -> AsyncIterator[LlmStreamChunk]:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY not set")
    import litellm
    from emergentintegrations.llm.utils import get_integration_proxy_url
    proxy_url = get_integration_proxy_url()
    # Match the param shape `LlmChat._execute_completion` builds — same
    # api_base, same custom_llm_provider; only difference is stream=True.
    if provider == "gemini":
        litellm_model = f"gemini/{model_id}"
    else:
        litellm_model = model_id  # openai (gpt-5.2) and anything else
    params = {
        "model":               litellm_model,
        "messages":            [
            {"role": "system", "content": system_msg or "You are a helpful assistant."},
            {"role": "user",   "content": user_text},
        ],
        "api_key":             api_key,
        "api_base":            proxy_url + "/llm",
        "custom_llm_provider": "openai",
        "max_tokens":          max_tokens,
        "stream":              True,
    }
    label = f"{provider}_direct"
    parts: List[str] = []
    response = await litellm.acompletion(**params)
    async for chunk in response:
        # OpenAI-compatible delta shape: chunk.choices[0].delta.content.
        try:
            delta = chunk.choices[0].delta
            text = getattr(delta, "content", None)
        except (AttributeError, IndexError, KeyError):
            text = None
        if not text:
            continue
        parts.append(text)
        yield LlmStreamChunk(kind="delta", text=text, provider_used=label)
    yield LlmStreamChunk(
        kind="done", text="".join(parts), provider_used=label,
    )


# ---------------------------------------------------------------------------
# Proxy fallback (non-streaming — single-shot via LlmChat) — wrapped as
# one delta + one done so consumers don't need a special path.
# ---------------------------------------------------------------------------
async def _stream_proxy_buffered(
    *, provider: str, model_id: str, system_msg: str, user_text: str,
    session_id: str,
) -> AsyncIterator[LlmStreamChunk]:
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    if not emergent_key:
        yield LlmStreamChunk(
            kind="error", error="no EMERGENT_LLM_KEY configured",
            provider_used="proxy_buffered",
        )
        return
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(
        api_key=emergent_key,
        session_id=session_id,
        system_message=system_msg or "You are a helpful assistant.",
    ).with_model(provider, model_id)
    raw = await chat.send_message(UserMessage(text=user_text))
    text = raw if isinstance(raw, str) else str(raw)
    yield LlmStreamChunk(
        kind="delta", text=text, provider_used="proxy_buffered",
        fallback_triggered=False,
    )
    yield LlmStreamChunk(
        kind="done", text=text, provider_used="proxy_buffered",
        fallback_triggered=False,
    )


# ---------------------------------------------------------------------------
# Public entry point — the function chat router (and any future streaming
# caller) consumes. Tries direct first, falls back to proxy on failure.
# ---------------------------------------------------------------------------
async def stream_llm_direct(
    *, provider: str, model_id: str, system_msg: str, user_text: str,
    session_id: Optional[str] = None, max_tokens: int = 4096,
) -> AsyncIterator[LlmStreamChunk]:
    """Yield streaming chunks. Always terminates with exactly one `done`
    chunk OR one `error` chunk."""
    sid = session_id or str(uuid.uuid4())
    modes = streaming_mode_per_provider()
    direct_active = (
        (provider == "anthropic" and modes["claude"] == "direct_stream") or
        (provider == "gemini"    and modes["gemini"] == "direct_stream") or
        (provider == "openai"    and modes["gpt"]    == "direct_stream")
    )

    if not direct_active:
        async for c in _stream_proxy_buffered(
            provider=provider, model_id=model_id, system_msg=system_msg,
            user_text=user_text, session_id=sid,
        ):
            yield c
        return

    # Pick the first-choice direct streamer per provider.
    if provider == "anthropic":
        direct_gen = _stream_anthropic
    elif provider == "gemini":
        direct_gen = _stream_gemini
    else:  # openai (gpt-5.2) — direct via litellm through Emergent proxy
        direct_gen = _stream_via_litellm_proxy

    parts: List[str] = []
    direct_failed = False
    direct_failure_reason = ""
    started_emitting = False
    try:
        # _stream_via_litellm_proxy needs `provider` because gemini gets
        # a `gemini/` model prefix; the others ignore the kwarg.
        if direct_gen is _stream_via_litellm_proxy:
            gen = direct_gen(
                provider=provider, model_id=model_id, system_msg=system_msg,
                user_text=user_text, max_tokens=max_tokens,
            )
        else:
            gen = direct_gen(
                model_id=model_id, system_msg=system_msg,
                user_text=user_text, max_tokens=max_tokens,
            )
        async for c in gen:
            if c.kind == "delta":
                started_emitting = True
                parts.append(c.text)
            yield c
        return
    except asyncio.CancelledError:
        raise
    except Exception as e:
        direct_failed = True
        direct_failure_reason = f"{type(e).__name__}: {str(e)[:200]}"
        logger.warning(
            "[llm-fallback] direct_%s failed (%s) → litellm_stream_proxy",
            provider, direct_failure_reason,
        )

    if not direct_failed:
        return

    if started_emitting:
        yield LlmStreamChunk(
            kind="error",
            error=f"direct_{provider}_mid_stream_failure: {direct_failure_reason}",
            provider_used=f"{provider}_direct",
            fallback_triggered=False,
        )
        return

    # No bytes shipped yet — try LiteLLM-stream through the Emergent proxy
    # before falling all the way back to a single buffered blob. This is
    # the path that recovers Gemini Pro from a tier 429 on the user's
    # GEMINI_API_KEY: same provider, different transport, still token-
    # level streaming. Still labelled `<provider>_direct` because the
    # consumer sees real per-token deltas.
    if provider in ("openai", "gemini") and direct_gen is not _stream_via_litellm_proxy:
        try:
            async for c in _stream_via_litellm_proxy(
                provider=provider, model_id=model_id, system_msg=system_msg,
                user_text=user_text, max_tokens=max_tokens,
            ):
                yield c
            return
        except Exception as e2:
            logger.warning(
                "[llm-fallback] litellm_stream_proxy_%s also failed (%s) → proxy_buffered",
                provider, f"{type(e2).__name__}: {str(e2)[:200]}",
            )

    # Last resort — single-shot buffered proxy. Consumers see one big
    # delta + a done with `fallback_triggered=True`.
    try:
        async for c in _stream_proxy_buffered(
            provider=provider, model_id=model_id, system_msg=system_msg,
            user_text=user_text, session_id=sid,
        ):
            c.fallback_triggered = True
            yield c
    except Exception as e:
        yield LlmStreamChunk(
            kind="error",
            error=f"proxy_fallback_failed: {type(e).__name__}: {str(e)[:200]}",
            provider_used="proxy_buffered",
            fallback_triggered=True,
        )


# ---------------------------------------------------------------------------
# Non-streaming companion — consumed by `llm_service.call_llm` so every
# request-response surface (briefings, signals, decks, solva v2, etc.)
# also benefits from the same direct-first / proxy-fallback envelope.
# Returns a tuple: (text, provider_used, fallback_triggered, error_or_None).
# ---------------------------------------------------------------------------
async def collect_llm_text(
    *, provider: str, model_id: str, system_msg: str, user_text: str,
    session_id: Optional[str] = None, max_tokens: int = 4096,
) -> Tuple[str, str, bool, Optional[str]]:
    parts: List[str] = []
    provider_used = ""
    fallback = False
    err: Optional[str] = None
    async for c in stream_llm_direct(
        provider=provider, model_id=model_id, system_msg=system_msg,
        user_text=user_text, session_id=session_id, max_tokens=max_tokens,
    ):
        if c.kind == "delta":
            parts.append(c.text)
        elif c.kind == "done":
            provider_used = c.provider_used
            fallback = c.fallback_triggered
            # Prefer the accumulated parts (consistency); done.text is
            # populated for proxy_buffered too.
            if not parts and c.text:
                parts.append(c.text)
        elif c.kind == "error":
            err = c.error or "unknown stream error"
            provider_used = c.provider_used or provider_used
            fallback = c.fallback_triggered or fallback
    return ("".join(parts), provider_used, fallback, err)
