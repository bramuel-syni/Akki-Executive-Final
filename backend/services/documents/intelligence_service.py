"""Phase E.3 (2026-05-26) — Document intelligence extraction.

Surfaces the Intelligence-tab content for the Universal Document
Drawer. One module exports `extract_intelligence(doc)` which produces
the canonical envelope cached on `db.document_intelligence`:

    {
      doc_id, doc_hash, generated_at,
      summary:               str    (2-sentence editorial; Reference mode)
      key_signals:           [{type, value, source_span, confidence}, ...]
      open_questions:        [str, ...]                  (Reference mode)
      completeness_gaps:     [str, ...]                  (Creation mode)
      clarity_signals:       {jargon_density, avg_sentence_length, contradictions}
      audience_fit:          {expected, observed, score, gaps:[...]} | None
      objective_score:       int 0-100 | None            (Creation mode)
      suggested_improvements:[{title, body, anchor_span}, ...]  (Creation mode)
    }

Routing through Shield's `invoke()` — every LLM call passes through
the de-id pipeline; no raw doc body reaches the provider un-redacted.
Failures are logged and swallowed so the drawer can render the
skeleton state without crashing.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.synisense.shield.client import invoke as shield_invoke


log = logging.getLogger("documents.intelligence")


# ─────────────────────────────────────────────────────────────────────
# Helpers — heuristic signals (no LLM, deterministic)
# ─────────────────────────────────────────────────────────────────────
def _doc_hash(doc: Dict[str, Any]) -> str:
    """Stable hash of (id, body, title, state). Invalidates the cache
    on any edit."""
    payload = "|".join([
        str(doc.get("id") or ""),
        str(doc.get("name") or ""),
        str(doc.get("title") or ""),
        str(doc.get("state") or ""),
        str(doc.get("extracted_text") or doc.get("body") or "")[:50000],
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _clarity_signals(body: str) -> Dict[str, Any]:
    """Heuristic clarity stats — no LLM. Cheap to recompute on every
    drawer open even when intelligence is uncached."""
    if not body:
        return {"jargon_density": 0.0, "avg_sentence_length": 0.0,
                "contradictions": 0, "word_count": 0}
    # Token-ish split.
    words = re.findall(r"\b\w[\w'-]*\b", body)
    word_count = len(words)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    avg_sent = round(word_count / max(1, len(sentences)), 1)
    # Jargon proxy: ratio of words ≥ 12 chars (corporate/board lexicon
    # tends to skew long-word). Crude but deterministic.
    long_words = sum(1 for w in words if len(w) >= 12)
    jargon = round(long_words / max(1, word_count), 3)
    return {
        "jargon_density":      jargon,
        "avg_sentence_length": avg_sent,
        "contradictions":      0,  # LLM-derived; 0 until extraction lands
        "word_count":          word_count,
    }


def _completeness_gaps_heuristic(body: str) -> List[str]:
    """Detect obvious gaps: unfilled placeholders, TBD/TK markers,
    missing dates. Surfaced even before the LLM call returns."""
    out: List[str] = []
    if not body:
        return ["Document body is empty."]
    if re.search(r"\b(TBD|TODO|TK|XXX|\[\.\.\.\])\b", body):
        out.append("Document contains TBD / TODO / TK placeholders that need filling.")
    if re.search(r"\{\{\s*[\w_]+\s*\}\}", body):
        out.append("Document contains unfilled template placeholders.")
    if not re.search(r"\b(20\d{2}|19\d{2})\b", body):
        out.append("Document doesn't reference any specific year — add dates where applicable.")
    if len(body) < 280:
        out.append("Document body is very short — consider adding more substance.")
    return out


# ─────────────────────────────────────────────────────────────────────
# Main entrypoint
# ─────────────────────────────────────────────────────────────────────
async def extract_intelligence(
    *,
    doc: Dict[str, Any],
    account_id: str,
    mode: str,                # "creation" | "reference"
) -> Dict[str, Any]:
    """Build the intelligence envelope. Wraps Shield-bounded LLM calls
    where appropriate. Returns a fully-populated envelope; LLM-derived
    fields default to None on failure (heuristic fields always
    populated)."""
    body = (doc.get("extracted_text") or doc.get("body") or "")[:40000]
    title = doc.get("name") or doc.get("original_filename") or "Untitled"
    objective = doc.get("objective") or None

    out: Dict[str, Any] = {
        "doc_id":            doc.get("id"),
        "doc_hash":          _doc_hash(doc),
        "generated_at":      datetime.now(timezone.utc).isoformat(),
        "mode":              mode,
        "clarity_signals":   _clarity_signals(body),
        "completeness_gaps": _completeness_gaps_heuristic(body),
        "summary":           None,
        "key_signals":       [],
        "open_questions":    [],
        "objective_score":   None,
        "audience_fit":      None,
        "suggested_improvements": [],
    }

    if not body:
        # Nothing to extract; return the skeleton.
        return out

    # ── LLM call 1: 2-sentence summary (Reference mode only)
    if mode == "reference":
        try:
            prompt = (
                "You are an executive editor. Read the document below and write "
                "exactly two short sentences (max ~30 words each) summarising what "
                "the document is and why it matters. Be specific. No filler. Return "
                "the two sentences as a single string, no labels.\n\n"
                f"TITLE: {title}\n\n"
                f"BODY:\n{body}"
            )
            result = await shield_invoke(
                purpose="document_journal.intelligence.extract",
                content=prompt,
                tenant_id=account_id,
                consumer_id="documents",
                user_id=account_id,
                model_preference="balanced",
            )
            out["summary"] = (result.get("response") or "").strip()[:600] or None
        except Exception as e:  # noqa: BLE001
            log.warning("intelligence.summary failed: %s", e)

    # ── LLM call 2: signals + open questions (joint structured ask)
    try:
        signals_prompt = (
            "Extract structured signals from the document. Respond with strict "
            "JSON only — no prose, no preamble. Shape:\n"
            "{\n"
            "  \"key_signals\": [{\"type\":\"kpi|decision|date|figure|risk|action\","
            " \"value\":\"...\",\"source_span\":\"...\",\"confidence\":0.0}],\n"
            "  \"open_questions\": [\"...\"]\n"
            "}\n"
            "Open questions = things the document raises but does not answer. "
            "Use a calm coach voice (Solva style). Max 6 signals, max 4 questions.\n\n"
            f"TITLE: {title}\n\nBODY:\n{body}"
        )
        result = await shield_invoke(
            purpose="document_journal.signals.generate",
            content=signals_prompt,
            tenant_id=account_id,
            consumer_id="documents",
            user_id=account_id,
            model_preference="analytical",
        )
        raw = (result.get("response") or "").strip()
        # Best-effort JSON parse — tolerate prose preamble.
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            parsed = json.loads(m.group(0))
            sigs = parsed.get("key_signals") or []
            if isinstance(sigs, list):
                out["key_signals"] = sigs[:6]
            qs = parsed.get("open_questions") or []
            if isinstance(qs, list):
                out["open_questions"] = [q for q in qs if isinstance(q, str)][:4]
    except Exception as e:  # noqa: BLE001
        log.warning("intelligence.signals failed: %s", e)

    # ── LLM call 3: objective adherence + suggested improvements
    # (Creation mode only)
    if mode == "creation" and objective and isinstance(objective, dict):
        goal = (objective.get("goal") or "").strip()
        ctx = (objective.get("context") or "").strip()
        if goal:
            try:
                obj_prompt = (
                    "You are an executive editor. Score how well the draft below "
                    "achieves the stated objective on a 0-100 scale. Also propose "
                    "3 short, specific improvements. Return strict JSON only.\n"
                    "Shape:\n"
                    "{\n"
                    "  \"objective_score\": 0-100,\n"
                    "  \"suggested_improvements\": [\n"
                    "    {\"title\":\"...\",\"body\":\"one-sentence rationale\","
                    " \"anchor_span\":\"the phrase in the draft to anchor on\"}\n"
                    "  ]\n"
                    "}\n"
                    f"OBJECTIVE goal: {goal}\n"
                    f"OBJECTIVE context: {ctx}\n\n"
                    f"DRAFT:\n{body}"
                )
                result = await shield_invoke(
                    purpose="document_journal.intelligence.extract",
                    content=obj_prompt,
                    tenant_id=account_id,
                    consumer_id="documents",
                    user_id=account_id,
                    model_preference="analytical",
                )
                raw = (result.get("response") or "").strip()
                m = re.search(r"\{[\s\S]*\}", raw)
                if m:
                    parsed = json.loads(m.group(0))
                    score = parsed.get("objective_score")
                    if isinstance(score, (int, float)):
                        out["objective_score"] = max(0, min(100, int(score)))
                    sugs = parsed.get("suggested_improvements") or []
                    if isinstance(sugs, list):
                        out["suggested_improvements"] = sugs[:5]
            except Exception as e:  # noqa: BLE001
                log.warning("intelligence.objective failed: %s", e)

    # ── Audience fit (Creation mode, if audience set)
    audience = doc.get("audience")
    if mode == "creation" and audience in ("board", "committee", "regulator", "public"):
        # Heuristic-only audience fit — sentence-length expectation per
        # audience. Replace with LLM-driven analysis in a follow-up.
        expected_avg = {"board": 18, "committee": 18, "regulator": 22, "public": 12}[audience]
        observed_avg = out["clarity_signals"]["avg_sentence_length"] or 0
        score = max(0, 100 - abs(observed_avg - expected_avg) * 4)
        out["audience_fit"] = {
            "expected":      audience,
            "expected_avg":  expected_avg,
            "observed_avg":  observed_avg,
            "score":         round(score),
            "gaps":          [] if score >= 70 else [
                "Sentence length diverges from the expected register for the audience."
            ],
        }

    return out
