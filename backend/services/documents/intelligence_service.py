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
# Phase P1-A (2026-02) — Pulse + Brief surfacing helper.
#
# `document_intelligence.key_signals` is the canonical document-level
# extracted-signal store. The Pulse feed (routers/pulse.py:177) and
# the document-Brief gate (routers/documents.py:975) BOTH read from
# `db.signals`. Without a bridge, the user-visible "Signals" extracted
# by intelligence never reach either surface.
#
# This helper materialises each `key_signal` as a row in `db.signals`
# with stable id `sig:from_intel:{doc_id}:{idx}` so the upsert is
# idempotent across every caller: eager promotion at extraction time,
# lazy promotion at Brief-click time, future bulk back-fills. Two
# callers writing for the same `(doc_id, idx)` produce ONE row.
#
# Schema is the Pulse-compatible signal shape:
#   id, context_id, type, headline, summary, confidence, sources,
#   data_trust, state, status, created_at, promoted_from.
# Pulse's serializer at pulse.py:280-355 reads all of these. The
# Brief worker's downstream `signal_ids` consumer also accepts them.
#
# Tenant scoping: every row is stamped with the caller's `context_id`,
# the same one Pulse's feed query filters on. No cross-tenant write.
# ─────────────────────────────────────────────────────────────────────
async def promote_intelligence_signals_to_pulse(
    db,
    *,
    doc: Dict[str, Any],
    context_id: str,
    account_id: str,
    key_signals: List[Dict[str, Any]],
) -> List[str]:
    """Idempotently promote `key_signals` into `db.signals`.

    Returns the list of stable signal ids written/refreshed. Never
    duplicates rows — same `(doc_id, idx)` always lands on the same
    `sig:from_intel:{doc_id}:{idx}` row.

    No-op when `key_signals` is empty.
    """
    if not key_signals:
        return []
    doc_id = doc.get("id")
    if not doc_id or not context_id:
        return []

    now_iso = datetime.now(timezone.utc).isoformat()
    promoted: List[str] = []
    for idx, raw in enumerate(key_signals[:8]):
        if not isinstance(raw, dict):
            continue
        sig_id = f"sig:from_intel:{doc_id}:{idx}"
        value = (raw.get("value") or "").strip()
        kind = (raw.get("type") or "risk").lower()
        # Pulse serializer maps via _surface_type(s.get("type")); it
        # accepts risk/opportunity/observation. The intelligence
        # schema emits kpi|decision|date|figure|risk|action — coerce
        # to the Pulse-visible bucket.
        if kind not in ("risk", "opportunity", "observation"):
            kind = "observation" if kind in ("kpi", "figure", "date") else "risk"
        conf_raw = raw.get("confidence")
        if isinstance(conf_raw, (int, float)):
            confidence = (
                "high" if conf_raw >= 0.7
                else "medium" if conf_raw >= 0.4
                else "low"
            )
        elif isinstance(conf_raw, str) and conf_raw.lower() in ("high", "medium", "low"):
            confidence = conf_raw.lower()
        else:
            confidence = "medium"
        headline = (value[:240] or f"Intelligence signal #{idx + 1}")
        sig_doc = {
            "id": sig_id,
            "context_id": context_id,
            "type": kind,
            "headline": headline,
            "summary": (
                value
                + (f"\n\nSource span: {raw.get('source_span')}" if raw.get("source_span") else "")
            )[:2000],
            "confidence": confidence,
            "sources": [{
                "doc_id": doc_id,
                "doc_name": doc.get("name") or "Document",
                "data_trust": "mixed",
            }],
            "references": [],
            "data_trust": "mixed",
            "generated_by": account_id,
            "focus": "document_intelligence",
            "state": "active",
            "status": "active",
            "comments": [],
            "created_at": now_iso,
            "promoted_from": "document_intelligence",
        }
        # `created_at` is only set on insert (preserve original surface
        # timestamp on idempotent re-runs). The rest is rewritten so a
        # re-extraction with refined values lands on Pulse.
        await db.signals.update_one(
            {"id": sig_id},
            {
                "$set": {k: v for k, v in sig_doc.items() if k != "created_at"},
                "$setOnInsert": {"created_at": now_iso},
            },
            upsert=True,
        )
        promoted.append(sig_id)
    return promoted


# ─────────────────────────────────────────────────────────────────────
# Track B Phase B4 G11 (2026-06-04) — Q4Y promotion mirror.
#
# The user-reported gap (MASTER_STATE.md G11): doc-extracted
# `open_questions` were cached on `db.document_intelligence` only and
# never reached `cycle_questions`. Net effect: the CompanyHome
# "Open questions" attention card showed 0 even when docs contained
# extracted questions, and Q4Y had no row to drill into.
#
# This helper idempotently mirrors `open_questions[]` into
# `db.cycle_questions` with stable id `q4y:from_intel:{doc_id}:{idx}`
# so two callers (eager extraction-time + lazy Brief-gate back-fill)
# write the same row exactly once. Mirrors `promote_intelligence_
# signals_to_pulse` shape so future Track B promoters land in the
# same module.
#
# Tightening 1 (orchestrator R3v5+1, 2026-06-04) — orphan close-out.
# When a doc is re-extracted and the new open_questions list is
# SHORTER than the previous one (M → N, N < M), the leftover
# `q4y:from_intel:{doc_id}:{N..M-1}` rows are flipped to
# `status="closed"` with a history entry recording the reason. Rows
# are NOT deleted — preserving the audit trail.
#
# Schema fields written:
#   id (stable), context_id, cycle_id=""  (sentinel — doc-extracted
#   questions are cycle-less; matches admin_qa_hooks pattern),
#   text, asked_by_account_id, asker_role, asked_at,
#   assignee_account_id, source_doc_id (provenance for G13 drawer),
#   status, history[], promoted_from="document_intelligence".
# ─────────────────────────────────────────────────────────────────────
async def promote_intelligence_questions_to_q4y(
    db,
    *,
    doc: Dict[str, Any],
    context_id: str,
    account_id: str,
    open_questions: List[str],
) -> List[str]:
    """Idempotently promote `open_questions` into `db.cycle_questions`.

    Returns the list of stable q4y ids written/refreshed. Never
    duplicates rows — same `(doc_id, idx)` always lands on the same
    `q4y:from_intel:{doc_id}:{idx}` row. When the input list shrinks
    relative to a prior run, the leftover (orphan) rows are closed
    (not deleted) with a `superseded_by_reextraction` history entry.

    No-op when `open_questions` is empty AND no prior rows exist for
    `doc_id`. If prior rows DO exist and the new input is empty,
    every prior row is closed (the doc no longer surfaces any
    questions).
    """
    doc_id = doc.get("id")
    if not doc_id or not context_id:
        return []

    # Derive the executive's role once per call (matches the
    # questions.raise_question path).
    from services.open_questions.asker_role_map import derive_asker_role
    asker_role = await derive_asker_role(account_id, context_id)

    now_iso = datetime.now(timezone.utc).isoformat()
    # Cap at 8 (mirrors the signals cap and the intel envelope's
    # own `[:4]` truncation — but the intel envelope can change so
    # we cap defensively).
    items = [
        q.strip() for q in (open_questions or [])
        if isinstance(q, str) and q.strip()
    ][:8]

    promoted: List[str] = []
    for idx, q_text in enumerate(items):
        q_id = f"q4y:from_intel:{doc_id}:{idx}"
        q_doc = {
            "id":                   q_id,
            "context_id":           context_id,
            "cycle_id":             "",
            "agenda_item_id":       None,
            "text":                 q_text[:2000],
            "asked_by_account_id":  account_id,
            "asker_role":           asker_role,
            "asked_at":             now_iso,
            "assignee_account_id":  account_id,
            "source_doc_id":        doc_id,
            "status":               "open",
            "promoted_from":        "document_intelligence",
        }
        # Idempotency contract:
        #   • `$set` rewrites text + provenance every run (refined
        #     extractions update the live row).
        #   • `$setOnInsert` pins `asked_at` + initial `history[]` so
        #     re-runs don't reset the original surface timestamp.
        #   • Status is NEVER blindly reset to "open" — a question
        #     marked answered by the user must not regress on a
        #     re-extraction. We only set status=open on insert.
        await db.cycle_questions.update_one(
            {"id": q_id},
            {
                "$set": {
                    "context_id":          q_doc["context_id"],
                    "cycle_id":            q_doc["cycle_id"],
                    "agenda_item_id":      q_doc["agenda_item_id"],
                    "text":                q_doc["text"],
                    "asked_by_account_id": q_doc["asked_by_account_id"],
                    "asker_role":          q_doc["asker_role"],
                    "assignee_account_id": q_doc["assignee_account_id"],
                    "source_doc_id":       q_doc["source_doc_id"],
                    "promoted_from":       q_doc["promoted_from"],
                },
                "$setOnInsert": {
                    "asked_at": q_doc["asked_at"],
                    "status":   q_doc["status"],
                    "history":  [{
                        "ts":       q_doc["asked_at"],
                        "kind":     "raised_from_doc",
                        "actor_id": account_id,
                        "note":     f"Surfaced from document {doc.get('name') or doc_id}.",
                    }],
                },
            },
            upsert=True,
        )
        promoted.append(q_id)

    # Tightening 1 — orphan close-out. After the upsert pass, any
    # prior `q4y:from_intel:{doc_id}:*` row whose idx is >= len(items)
    # is closed (not deleted). Prefix-match via $regex (anchored).
    # The full id format is `q4y:from_intel:{doc_id}:{idx}` so
    # `^q4y:from_intel:{doc_id}:` is the unambiguous prefix.
    prefix = f"q4y:from_intel:{doc_id}:"
    cur = db.cycle_questions.find(
        {"id": {"$regex": f"^{re.escape(prefix)}"}},
        {"_id": 0, "id": 1, "status": 1, "history": 1},
    )
    async for row in cur:
        suffix = row["id"][len(prefix):]
        try:
            row_idx = int(suffix)
        except (ValueError, TypeError):
            continue
        if row_idx < len(items):
            # Active row — already handled by the upsert above.
            continue
        if row.get("status") == "closed":
            # Already closed by a prior re-extraction — idempotent.
            continue
        history = list(row.get("history") or [])
        history.append({
            "ts":     now_iso,
            "kind":   "closed",
            "actor_id": account_id,
            "note":   "superseded_by_reextraction",
        })
        await db.cycle_questions.update_one(
            {"id": row["id"]},
            {"$set": {"status": "closed", "history": history}},
        )
    return promoted


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
