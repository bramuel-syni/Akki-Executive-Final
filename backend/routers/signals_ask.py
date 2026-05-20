"""M5 — Signals (Highlights) generation + Ask Q&A.

Both endpoints share the same grounding pipeline (Context Object + uploaded
documents), so they live together in a single router.

Chunk 2 (2026-05-13, DJ-R05) — the original synchronous
`POST /contexts/{cid}/signals/generate` was timing out behind the
gateway (HTTP 524) because the inline LLM call routinely took
~75–100 s. The endpoint now returns **202 + `job_id`** immediately
and the LLM work runs as a `BackgroundTasks` worker that updates a
row in `db.async_jobs`. The frontend polls `GET /api/jobs/{job_id}`.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from llm_service import call_llm as llm_call_llm, parse_json_response
from bm25 import chunk_documents, score_bm25, ranked_chunks_as_grounding_block
from citation_refs import build_references
from core import (
    db, now, iso, write_audit, require_context_membership,
    gather_context_object, gather_documents_for_grounding,
    docs_as_grounding_block, docs_overall_trust,
)
from services.job_queue import (
    create_job as _create_job, mark_running as _mark_running,
    mark_completed as _mark_completed, mark_failed as _mark_failed,
    spawn as _spawn,
)

logger = logging.getLogger("akki.signals")
router = APIRouter(prefix="/api")

_CITE_RE = re.compile(r"\[doc:[a-f0-9-]+(?:[,\s]+doc:[a-f0-9-]+)*\]")
_ID_RE = re.compile(r"[a-f0-9-]{8,}")


def _extract_cited_ids(text: str) -> List[str]:
    found: List[str] = []
    for block in _CITE_RE.findall(text or ""):
        for d in _ID_RE.findall(block):
            if d not in found:
                found.append(d)
    return found


class SignalGenerateIn(BaseModel):
    focus: Optional[str] = None


@router.post("/contexts/{context_id}/signals/generate", status_code=202)
async def generate_signals(
    body: SignalGenerateIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Chunk 2 — async pattern.

    Returns **202 Accepted** with a `job_id` immediately. The actual
    LLM work runs in a `BackgroundTasks` worker that updates the
    `db.async_jobs` row. Frontend should poll
    `GET /api/jobs/{job_id}` every 2–3 s and consume the row's
    `result` payload when `status == "completed"`.

    The `result` payload mirrors the legacy sync response shape so
    the frontend's downstream logic (toast, list refresh) keeps
    working unchanged.
    """
    context_id = ctx["context"]["id"]
    # Cheap pre-flight check — we want to surface "no documents"
    # synchronously so the user sees the error immediately instead of
    # after a polling round-trip.
    docs_count = await db.documents.count_documents(
        {"context_id": context_id, "status": "extracted"},
    )
    if docs_count == 0:
        raise HTTPException(
            status_code=400,
            detail="Upload at least one document to this context before generating signals.",
        )

    job_id = await _create_job(
        kind="signals.generate",
        account_id=ctx["account"]["id"],
        context_id=context_id,
        input_summary={"focus": body.focus or "", "docs_count": docs_count},
    )

    background_account_id = ctx["account"]["id"]

    async def _runner():
        await _mark_running(job_id)
        try:
            result = await _generate_signals_worker(
                body=body, account_id=background_account_id, context_id=context_id,
            )
            await _mark_completed(job_id, result)
        except HTTPException as e:
            # 4xx/5xx surfaced by the worker — preserve the message for the
            # polling response. We do NOT re-raise because the spawned task
            # would just swallow the exception; the polling endpoint must
            # be able to see the failure shape instead.
            detail = e.detail if isinstance(e.detail, str) else str(e.detail)
            await _mark_failed(job_id, f"http_{e.status_code}: {detail}")
        except Exception as e:
            logger.exception("signals.generate worker crashed (job=%s)", job_id)
            await _mark_failed(job_id, f"{type(e).__name__}: {str(e)[:400]}")

    _spawn(_runner())
    return {"job_id": job_id, "status": "queued"}


# ─────────────────────────────────────────────────────────────────────────────
# Background worker — runs the legacy heavy body.
# Pre-Chunk 2 callers (tests, internal tooling) can still invoke this
# directly if they need synchronous behaviour for fast-path test fixtures.
# ─────────────────────────────────────────────────────────────────────────────
async def _generate_signals_worker(
    *, body: SignalGenerateIn, account_id: str, context_id: str,
) -> Dict[str, Any]:
    ctx_obj = await gather_context_object(context_id)
    docs = await gather_documents_for_grounding(context_id)
    if not docs:
        raise HTTPException(
            status_code=400,
            detail="Upload at least one document to this context before generating signals.",
        )

    grounding = docs_as_grounding_block(docs)
    focus_line = (
        f"The caller has specifically asked you to focus on: « {body.focus} ». "
        f"Do not ignore other important signals, but weight this focus.\n\n"
        if body.focus else ""
    )
    co_answers = (ctx_obj or {}).get("answers") or {}
    persona_bits = []
    for k in ("q1_role", "q3_focus_areas", "q5_prior_concerns", "q6_lens_preference", "q7_analytical_style"):
        v = co_answers.get(k)
        if v:
            persona_bits.append(f"  · {v}")
    persona_block = ("\n".join(persona_bits)) if persona_bits else "  · (generic board lens)"

    user_query = (
        f"Read these documents as a seasoned audit-committee chair would. Look for "
        f"the 3–6 things that a sharp non-executive would notice on a careful first "
        f"read. Not the obvious, not the trivial — the things that, if they weren't "
        f"named, would represent a governance failure.\n\n"
        f"[WHO YOU'RE WRITING FOR]\n{persona_block}\n\n"
        f"{focus_line}"
        f"[DOCUMENTS — every signal MUST cite at least one doc_id from this list]\n"
        f"{grounding}\n\n"
        f"For each signal:\n"
        f"• headline: 8–14 words, declarative (a sentence, not a topic). State the "
        f"thing that is happening, not its category.\n"
        f"• summary: 2–4 sentences. Open with the finding. Give the SPECIFIC numbers "
        f"from the documents. Close with what it implies for the board or executive "
        f"— what they should ask, decide, or escalate. No filler.\n"
        f"• type: risk / opportunity / gap. Use 'gap' for things that should exist "
        f"but don't (e.g., a plan, a control, a succession).\n"
        f"• confidence: 'high' only when the numbers in the documents leave no room "
        f"for another reading. 'medium' for pattern-based inferences. 'low' only when "
        f"trust is weak.\n\n"
        "For each signal the `doc_ids` array MUST contain every doc_id you used "
        "as evidence. You may also reference them inline in the summary as "
        "[doc:xxx] using the exact same UUIDs — do not invent ids.\n\n"
        'Return JSON: {"signals":[{"type":"risk|opportunity|gap","headline":"...",'
        '"summary":"...","confidence":"high|medium|low","doc_ids":["..."]}]}'
    )

    llm_out = await llm_call_llm(
        module="highlights",
        user_query=user_query,
        context_object=ctx_obj,
        session_context={"session_id": f"signals-{context_id}"},
        data_trust={"overall": docs_overall_trust(docs)},
        response_format="json",
    )
    parsed = parse_json_response(llm_out.get("response", ""))
    signals_raw = (parsed or {}).get("signals") if isinstance(parsed, dict) else None
    if not isinstance(signals_raw, list):
        # QA-2026-05-16-007 (2026-05-18): user-facing copy is now
        # actionable. The raw 500-char slice is kept for backend
        # log/audit but the outer detail is the user-facing message
        # the frontend toasts.
        logger.warning(
            "signals.generate parse failed (mode=%s, raw_len=%d): %r",
            llm_out.get("mode"), len(llm_out.get("response", "") or ""),
            (llm_out.get("response", "") or "")[:500],
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "Akki couldn't extract signals from that document this time. "
                "Try again, or upload a fresher version of the document."
            ),
        )

    doc_by_id = {d["id"]: d for d in docs}
    created_at = iso(now())
    stored: List[Dict[str, Any]] = []
    for s in signals_raw[:8]:
        sig_id = str(uuid.uuid4())
        summary_text = (s.get("summary") or "")
        inline_ids = _extract_cited_ids(summary_text) + _extract_cited_ids(s.get("headline") or "")
        merged_ids: List[str] = []
        for d_id in (list(s.get("doc_ids") or []) + inline_ids):
            if d_id in doc_by_id and d_id not in merged_ids:
                merged_ids.append(d_id)
        sources = [
            {"doc_id": d_id, "doc_name": doc_by_id[d_id]["name"], "data_trust": doc_by_id[d_id].get("data_trust", "mixed")}
            for d_id in merged_ids
        ]
        doc = {
            "id": sig_id, "context_id": context_id,
            "type": s.get("type") if s.get("type") in ("risk", "opportunity", "gap") else "risk",
            "headline": (s.get("headline") or "Unnamed signal")[:240],
            "summary": summary_text[:2000],
            "confidence": s.get("confidence") if s.get("confidence") in ("high", "medium", "low") else "medium",
            "sources": sources,
            # Reading Viewer Phase 1: additive `references[]` alongside the
            # existing `[doc:xxx]` inline tokens. Page/paragraph fields
            # are nullable until LLM prompts are tightened in a later pass.
            "references": build_references(sources, doc_by_id),
            "data_trust": docs_overall_trust([doc_by_id[i] for i in merged_ids]) if merged_ids else "unrated",
            "generated_by": account_id,
            "focus": body.focus,
            "shielding_masked": llm_out.get("shielding", {}).get("identifiers_masked", 0),
            "shielding": llm_out.get("shielding", {}),
            "mode": llm_out.get("mode"),
            "created_at": created_at, "status": "active",
        }
        # Phase G.3 — content_hash + merge_count dedup. If the same
        # (type, headline, summary) tuple already exists in this
        # context, we increment merge_count instead of inserting a
        # duplicate row. `merged` is False when an existing row was
        # bumped; True when a fresh row was inserted.
        from services.signal_dedup import dedup_or_insert
        # Phase G.1 default — every freshly-emitted signal lands on
        # the Active tab. `state` is the canonical lifecycle field;
        # `status` is kept for back-compat with pre-G readers.
        doc["state"] = "active"
        doc["comments"] = []
        doc, merged = await dedup_or_insert(db, doc)
        # Phase E.0.2 — derive cross-board metadata signatures from
        # the freshly-inserted signal. Skip on merge — the existing
        # row already has its signatures.
        if merged:
            try:
                from services.metadata_signatures import derive_and_persist
                await derive_and_persist(
                    db,
                    text=f"{doc.get('headline') or ''} {doc.get('summary') or ''}",
                    context_id=context_id,
                    account_id=account_id,
                    source_artefact_kind="signal",
                    source_artefact_id=doc["id"],
                )
            except Exception:  # pragma: no cover — non-fatal
                pass
        stored.append(doc)

    await write_audit(
        context_id, account_id, "signals.generated", "signal", None,
        {"count": len(stored), "mode": llm_out.get("mode")},
    )
    return {"signals": stored, "mode": llm_out.get("mode"), "shielding": llm_out.get("shielding", {})}


@router.get("/contexts/{context_id}/signals")
async def list_signals(
    ctx: Dict[str, Any] = Depends(require_context_membership()),
    limit: int = 100,
    committee_id: Optional[str] = None,
):
    q: Dict[str, Any] = {"context_id": ctx["context"]["id"], "status": "active"}
    if committee_id:
        q["committee_id"] = committee_id
    sigs = await db.signals.find(q, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 500))
    # Backfill `references[]` for legacy signals that pre-date Reading Viewer
    # Phase 1. Stored `sources[]` is the source of truth; references is a
    # view over it. No mutation — read-time projection only.
    for s in sigs:
        if "references" not in s:
            s["references"] = build_references(s.get("sources") or [])
    return sigs


@router.delete("/contexts/{context_id}/signals/{signal_id}")
async def dismiss_signal(
    context_id: str, signal_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    await db.signals.update_one(
        {"id": signal_id, "context_id": context_id},
        {"$set": {"status": "dismissed", "dismissed_at": iso(now())}},
    )
    await write_audit(context_id, ctx["account"]["id"], "signal.dismissed", "signal", signal_id, {})
    return {"ok": True}


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


@router.post("/contexts/{context_id}/ask")
async def ask(
    body: AskIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    context_id = ctx["context"]["id"]
    ctx_obj = await gather_context_object(context_id)
    docs = await gather_documents_for_grounding(context_id)

    # M13 — Hybrid retrieval: chunk every doc, then BM25-rank chunks against the
    # question. We keep `docs` around for citation bookkeeping and pass only the
    # top chunks into the prompt. This lets Ask be grounded against 50-doc
    # contexts without blowing past the prompt window.
    retrieval_mode = "bm25"
    chunks = chunk_documents(docs)
    ranked = score_bm25(body.question, chunks, k=12)
    if not ranked or all(s == 0 for s, _ in ranked):
        # Fall back to the flat, most-recent-doc block when BM25 finds nothing.
        grounding = docs_as_grounding_block(docs)
        retrieval_mode = "recency_fallback"
    else:
        grounding, _ = ranked_chunks_as_grounding_block(ranked)

    co_answers = (ctx_obj or {}).get("answers") or {}
    persona_bits = []
    for k in ("q1_role", "q3_focus_areas", "q6_lens_preference", "q7_analytical_style"):
        v = co_answers.get(k)
        if v:
            persona_bits.append(f"  · {v}")
    persona_block = ("\n".join(persona_bits)) if persona_bits else "  · (no context object — respond generally, still grounded)"

    # Plays-aware Ask (Apr-2026): if the executive has an active play
    # running in this company, include a one-line nudge so the answer
    # frames itself in the context the user is actively working in
    # ("you're in the middle of a Q2 board pack"). Keep it light — we
    # don't change retrieval ranking, just persona framing.
    active_plays = await db.plays.find(
        {"context_id": context_id, "status": "active"},
        {"_id": 0, "id": 1, "play_type": 1, "title": 1, "current_stage": 1, "updated_at": 1},
    ).sort("updated_at", -1).limit(3).to_list(3)
    plays_block = ""
    if active_plays:
        items = []
        for p in active_plays:
            stage_label = (
                ["inbox", "compose", "review", "send-up"][p.get("current_stage", 0)]
                if p.get("play_type") == "board_pack"
                else ["read", "brief", "question"][p.get("current_stage", 0)]
                if p.get("play_type") == "pre_board"
                else f"stage {p.get('current_stage', 0) + 1}"
            )
            label = (p.get("title") or p.get("play_type", "")).replace("_", " ")
            items.append(f"  · {label} (currently on {stage_label})")
        plays_block = (
            "\n[ACTIVE WORKFLOWS — frame your answer with these in mind]\n"
            + "\n".join(items)
            + "\n"
        )

    user_query = (
        f"The director / executive has just asked you this:\n\n"
        f"    « {body.question} »\n\n"
        f"Answer them directly — as a colleague, not a form response. Give them "
        f"the insight first, then the evidence. Keep it tight. Use the numbers.\n\n"
        f"[WHAT THIS PERSON CARES ABOUT]\n{persona_block}\n"
        f"{plays_block}\n"
        f"[THEIR DOCUMENTS — all citations MUST be to doc_ids in this list]\n"
        f"{grounding}\n\n"
        f"If the answer genuinely isn't in these documents, say so in one sentence "
        f"and suggest what the caller could upload to let you answer. Do not speculate."
    )
    llm_out = await llm_call_llm(
        module="ask",
        user_query=user_query,
        context_object=ctx_obj,
        session_context={"session_id": f"ask-{context_id}"},
        data_trust={"overall": docs_overall_trust(docs)},
    )

    cited_ids = list({m.group(1) for m in re.finditer(r"\[doc:([a-f0-9-]+)\]", llm_out.get("response", ""))})
    doc_by_id = {d["id"]: d for d in docs}
    sources = [
        {"doc_id": d_id, "doc_name": doc_by_id[d_id]["name"], "data_trust": doc_by_id[d_id].get("data_trust", "mixed")}
        for d_id in cited_ids if d_id in doc_by_id
    ]

    record = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "question": body.question,
        "answer": llm_out.get("response", ""),
        "sources": sources,
        # Reading Viewer Phase 1: additive `references[]` for citation chips.
        "references": build_references(sources, doc_by_id),
        "mode": llm_out.get("mode"),
        "retrieval_mode": retrieval_mode,
        "shielding_masked": llm_out.get("shielding", {}).get("identifiers_masked", 0),
        "shielding": llm_out.get("shielding", {}),
        "asked_by": ctx["account"]["id"],
        "asked_by_email": ctx["account"]["email"],
        "created_at": iso(now()),
    }
    await db.ask_messages.insert_one(record)
    record.pop("_id", None)
    await write_audit(
        context_id, ctx["account"]["id"], "ask.asked", "ask", record["id"],
        {"q_chars": len(body.question), "a_chars": len(record["answer"])},
    )
    return record


@router.get("/contexts/{context_id}/ask")
async def list_ask_history(
    ctx: Dict[str, Any] = Depends(require_context_membership()),
    limit: int = 50,
):
    msgs = await db.ask_messages.find(
        {"context_id": ctx["context"]["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(min(limit, 200))
    for m in msgs:
        if "references" not in m:
            m["references"] = build_references(m.get("sources") or [])
    return msgs
