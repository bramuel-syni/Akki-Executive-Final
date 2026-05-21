"""LLM fallback layer for low-confidence Presidio spans.

Contract: receive a list of (text, span) tuples where span.score < 0.55,
ask the gateway-routed classifier whether the span is PII in a
governance context, return a list of decisions. Capped per-document to
bound cost.

The LLM sees ONLY the suspicious substring plus a small surrounding
window — never the full document. This is both a cost control and a
privacy-leak hedge: whatever the model sees, it sees out-of-context.

Chunk 18.5 (Track 4 item 1, 2026-05-21) — cold-start latency fix.
Previously this module imported `emergentintegrations.LlmChat` directly
and constructed a fresh chat per call. That:
  • Bypassed `SYNISENSE_LLM_MODE=mock` (so tests + dev paid 5-13s per
    pre-pass; the steady-state cost shown up to 20× per `call_llm`).
  • Used a separate Anthropic/Gemini SDK init (no warm-up sharing with
    `shield.client.invoke()`'s pool — every `call_llm` paid the cold
    SDK init twice).
  • Was structurally vulnerable to the same leak the public CI guard
    `test_no_direct_llm_calls_outside_shield` blocks — this file just
    happened to live INSIDE `shield/` so the guard didn't fire.

The fix routes through `shield.llm_router.invoke()`, which is the
single approved LLM call site inside `shield/` (now enforced by the
companion guard `test_no_direct_llm_calls_inside_shield_except_router`).
That gives us:
  • Mock-mode coverage for free (router short-circuits cleanly).
  • Shared litellm + httpx client pool with `client.invoke()` so the
    first prod call only warms the SDK ONCE per process.
  • Centralised credential handling (no `EMERGENT_LLM_KEY` env read in
    this module — the router owns it).
"""
from __future__ import annotations

import asyncio
import logging
import time as _time
from typing import Any, Dict, List, Tuple

from . import llm_router

logger = logging.getLogger("akki.synisense.llm")

_WINDOW_CHARS = 60  # chars of context either side of the suspicious span


def _extract_window(text: str, start: int, end: int) -> Tuple[str, str, str]:
    w_start = max(0, start - _WINDOW_CHARS)
    w_end = min(len(text), end + _WINDOW_CHARS)
    return (
        text[w_start:start],
        text[start:end],
        text[end:w_end],
    )


async def _classify_one(
    text: str, span: Dict[str, Any], *, timeout_ms: int,
) -> Dict[str, Any]:
    """Ask the gateway-routed classifier whether this span is actually
    PII in a governance context.

    Returns the span dict augmented with:
        - `llm_verdict`: 'pii' | 'not_pii' | 'uncertain'
        - `llm_suggested_type`: str | None
        - `elapsed_ms`: int
    Never blocks the parent pipeline on error — falls back to
    'uncertain' so the caller decides whether to redact or pass.

    Chunk 18.5 — uses `llm_router.invoke()` instead of `LlmChat` so
    `SYNISENSE_LLM_MODE=mock` works for tests + dev, and the router's
    shared litellm pool eliminates the per-call cold-SDK-init cost.
    """
    started = _time.monotonic()
    before, middle, after = _extract_window(text, span["start"], span["end"])
    prompt = (
        "You are a privacy classifier for governance documents. Decide "
        "whether the bracketed SUBSTRING below is personally identifying "
        "information (PII) or sensitive in a board/executive context. "
        "Respond with STRICT JSON only, no preamble: "
        '{"verdict":"pii"|"not_pii"|"uncertain","type":"<short_label>"}. '
        "Types: PERSON, EMAIL, PHONE, LOCATION, ORGANIZATION, "
        "FINANCIAL, DEAL_CODENAME, OTHER.\n\n"
        f"Context before: ...{before}[[\n"
        f"Substring: {middle}\n"
        f"]]{after}...\n"
    )
    try:
        # `model_preference="balanced"` → Gemini 2.5 Flash (the same
        # cheap classifier the legacy LlmChat path used). The router
        # honours `SYNISENSE_LLM_MODE=mock` + missing-key gracefully so
        # the previous "no_emergent_key" branch is no longer needed
        # here — the router's mock path returns deterministically.
        raw, _provider, _model = await asyncio.wait_for(
            llm_router.invoke(
                prompt,
                model_preference="balanced",
                timeout_seconds=max(0.5, timeout_ms / 1000.0),
            ),
            timeout=max(0.5, (timeout_ms / 1000.0) + 0.5),
        )
        import json as _json
        import re as _re
        s = raw if isinstance(raw, str) else str(raw)
        m = _re.search(r"\{.*?\}", s, _re.DOTALL)
        parsed = _json.loads(m.group(0)) if m else {}
        verdict = str(parsed.get("verdict") or "uncertain").lower()
        if verdict not in {"pii", "not_pii", "uncertain"}:
            verdict = "uncertain"
        label = str(parsed.get("type") or "")[:32] or None
        return {**span, "llm_verdict": verdict,
                "llm_suggested_type": label,
                "elapsed_ms": int((_time.monotonic() - started) * 1000),
                "source": "llm"}
    except Exception as e:  # noqa: BLE001
        logger.warning("synisense llm classify failed: %s", e.__class__.__name__)
        return {**span, "llm_verdict": "uncertain",
                "llm_suggested_type": None,
                "elapsed_ms": int((_time.monotonic() - started) * 1000),
                "llm_reason": e.__class__.__name__}


async def classify_low_confidence(
    text: str, spans: List[Dict[str, Any]], *,
    cap: int = 20,
    concurrency: int = 5,
    timeout_ms: int = 2000,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Classify the first `cap` spans via LLM; remaining are returned
    with `llm_verdict='skipped_cap'` and are treated by the pipeline as
    'not PII' (honest conservative default when Presidio's own score
    was already below the confidence threshold).

    Returns (classified_spans, stats).
    """
    stats = {"llm_calls": 0, "llm_pii": 0, "llm_not_pii": 0,
            "llm_uncertain": 0, "llm_skipped_cap": 0}
    if not spans:
        return [], stats
    head = spans[:cap]
    tail = spans[cap:]
    for s in tail:
        s["llm_verdict"] = "skipped_cap"
        stats["llm_skipped_cap"] += 1

    sem = asyncio.Semaphore(max(1, concurrency))

    async def _bounded(sp):  # noqa: ANN202
        async with sem:
            return await _classify_one(text, sp, timeout_ms=timeout_ms)

    results = await asyncio.gather(*[_bounded(s) for s in head])
    for r in results:
        stats["llm_calls"] += 1
        v = r.get("llm_verdict", "uncertain")
        stats[f"llm_{v}"] = stats.get(f"llm_{v}", 0) + 1
    return list(results) + tail, stats
