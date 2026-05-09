"""Phase B.3 — direct-provider token streaming + strategic failover.

Replaces the briefings-local Claude→Gemini band-aid (option-b) with a
service-layer mechanism that benefits every LLM-using surface.

Design
------
* `stream_llm_direct(...)` is an async generator yielding `LlmStreamChunk`
  objects (`kind ∈ {delta, done, error}`).
* If a direct provider key is present (`ANTHROPIC_API_KEY` for anthropic,
  `GEMINI_API_KEY` for gemini) we attempt the direct streaming SDK first.
* On any direct-call failure (network, 5xx, 4xx, parse) we log a single
  `[llm-fallback]` warning and fall back to the existing Emergent proxy
  via `LlmChat.send_message`. The fallback path is non-streaming — we
  emit one big `delta` containing the whole reply so the consumer's
  delta-loop logic still works.
* The `done` chunk always carries `provider_used` and `fallback_triggered`
  so callers can audit which path served the request.

GPT-5.2 / OpenAI is intentionally unsupported here — stays on the proxy
buffered path until direct keys are provisioned for that provider too.
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
    """
    forced = (os.environ.get("CHAT_STREAMING_MODE") or "").strip().lower()
    has_anth = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_gem  = bool(os.environ.get("GEMINI_API_KEY"))
    if forced == "proxy_buffered":
        return {"claude": "proxy_buffered", "gemini": "proxy_buffered", "gpt": "proxy_buffered"}
    return {
        "claude": "direct_stream" if has_anth else "proxy_buffered",
        "gemini": "direct_stream" if has_gem  else "proxy_buffered",
        "gpt":    "proxy_buffered",   # always — no direct OpenAI key wired today
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
        (provider == "gemini"    and modes["gemini"] == "direct_stream")
    )

    if not direct_active:
        async for c in _stream_proxy_buffered(
            provider=provider, model_id=model_id, system_msg=system_msg,
            user_text=user_text, session_id=sid,
        ):
            yield c
        return

    direct_gen = (
        _stream_anthropic if provider == "anthropic"
        else _stream_gemini
    )

    parts: List[str] = []
    direct_failed = False
    direct_failure_reason = ""
    started_emitting = False
    try:
        async for c in direct_gen(
            model_id=model_id, system_msg=system_msg,
            user_text=user_text, max_tokens=max_tokens,
        ):
            if c.kind == "delta":
                started_emitting = True
                parts.append(c.text)
            yield c
        return
    except asyncio.CancelledError:
        # Client disconnect — propagate, do NOT fall back.
        raise
    except Exception as e:
        direct_failed = True
        direct_failure_reason = f"{type(e).__name__}: {str(e)[:200]}"
        logger.warning(
            "[llm-fallback] direct_%s failed (%s) → proxy_buffered",
            provider, direct_failure_reason,
        )

    if not direct_failed:
        return

    # Mid-stream failure with content already emitted → surface error.
    # We CANNOT silently fall back to proxy because the consumer has
    # already accumulated partial text from the direct stream; the proxy
    # call would emit the *full* reply again, double-counting.
    if started_emitting:
        yield LlmStreamChunk(
            kind="error",
            error=f"direct_{provider}_mid_stream_failure: {direct_failure_reason}",
            provider_used=f"{provider}_direct",
            fallback_triggered=False,
        )
        return

    # No bytes shipped yet — safe to retry via proxy.
    try:
        async for c in _stream_proxy_buffered(
            provider=provider, model_id=model_id, system_msg=system_msg,
            user_text=user_text, session_id=sid,
        ):
            # Annotate the fallback flag on every chunk so audit captures it.
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
