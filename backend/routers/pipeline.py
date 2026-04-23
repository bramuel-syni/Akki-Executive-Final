"""M11 — Event-driven signals pipeline.

Before M11: `POST /api/contexts/{id}/signals/generate` was a single synchronous
LLM call that extracted, reasoned, and persisted in one shot. That design makes
drift detection, re-ranking, and auditability hard.

With M11 we split generation into four stages connected by events (stored in
the `signal_events` collection — no external broker, so the same architecture
works on a single pod):

    document.extracted    →  (already raised by documents_service)
    signal.candidate_drafted ← LLM stage 1: produce N candidates WITH reasoning
    signal.verified       ← LLM stage 2: critic pass — kills weak / hallucinated
                            candidates, confirms each one cites a real doc_id
    signal.persisted      ← writes verified signals to `signals` collection

The existing signals/generate endpoint is retained for backwards-compatibility.
A new `/pipeline/run` endpoint exposes the staged flow and a `/pipeline/events`
endpoint lets the UI (future work) render a live trace.

Because we're single-pod, stages are executed sequentially inside one HTTP
request. But each stage persists its own event row, so operators can always
answer "which candidate was rejected, by whom, and why?" for any signal — a
capability the single-shot endpoint simply could not offer.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from llm_service import call_llm as llm_call_llm, parse_json_response
from core import (
    db, now, iso, write_audit, require_context_membership,
    gather_context_object, gather_documents_for_grounding,
    docs_as_grounding_block, docs_overall_trust,
)

router = APIRouter(prefix="/api")

_ID_RE = re.compile(r"[a-f0-9-]{8,}")


# -----------------------------------------------------------------------------
# Event helpers
# -----------------------------------------------------------------------------
async def _emit(
    context_id: str, pipeline_run_id: str, event_type: str,
    payload: Dict[str, Any], actor_id: Optional[str] = None,
) -> str:
    eid = str(uuid.uuid4())
    await db.signal_events.insert_one({
        "id": eid,
        "context_id": context_id,
        "pipeline_run_id": pipeline_run_id,
        "type": event_type,
        "payload": payload,
        "actor_id": actor_id,
        "created_at": iso(now()),
    })
    return eid


# -----------------------------------------------------------------------------
# Stage 1 — candidate draft (LLM generates 4-8 candidates with reasoning)
# -----------------------------------------------------------------------------
async def _stage_candidate_draft(
    *, context_id: str, pipeline_run_id: str, actor_id: str,
    ctx_obj: Optional[Dict[str, Any]], docs: List[Dict[str, Any]],
    focus: Optional[str],
) -> Dict[str, Any]:
    grounding = docs_as_grounding_block(docs)
    focus_line = (
        f"The caller asked you specifically to focus on: « {focus} ». "
        f"Weight this focus but do not ignore other important signals.\n\n"
        if focus else ""
    )
    user_query = (
        "STAGE 1: CANDIDATE DRAFTING.\n"
        "You are drafting signal CANDIDATES from the documents below. A separate "
        "verifier pass will critique and prune these, so err on the side of "
        "generating 5-8 candidates with reasoning, rather than 3 over-polished ones.\n\n"
        f"{focus_line}"
        "For each candidate, show your reasoning inline — this is read by the "
        "verifier, not the end user.\n\n"
        f"[DOCUMENTS]\n{grounding}\n\n"
        'Return JSON: {"candidates":[{"type":"risk|opportunity|gap","headline":"...","summary":"...","doc_ids":["..."],"reasoning":"why this matters, 1-2 sentences for the verifier"}]}'
    )
    llm_out = await llm_call_llm(
        module="highlights.candidates",
        user_query=user_query,
        context_object=ctx_obj,
        session_context={"session_id": f"signals-candidates-{context_id}"},
        data_trust={"overall": docs_overall_trust(docs)},
        response_format="json",
    )
    parsed = parse_json_response(llm_out.get("response", ""))
    candidates = (parsed or {}).get("candidates") if isinstance(parsed, dict) else None
    if not isinstance(candidates, list) or not candidates:
        raise HTTPException(
            status_code=502,
            detail=f"Stage 1 produced no candidates. Mode={llm_out.get('mode')}. Raw: {llm_out.get('response', '')[:400]}",
        )
    # Normalise
    norm: List[Dict[str, Any]] = []
    for c in candidates[:10]:
        norm.append({
            "id": str(uuid.uuid4()),
            "type": c.get("type") if c.get("type") in ("risk", "opportunity", "gap") else "risk",
            "headline": (c.get("headline") or "Unnamed")[:240],
            "summary": (c.get("summary") or "")[:2000],
            "doc_ids": [d for d in (c.get("doc_ids") or []) if isinstance(d, str)],
            "reasoning": (c.get("reasoning") or "")[:600],
        })
    await _emit(context_id, pipeline_run_id, "signal.candidate_drafted",
                {"count": len(norm), "mode": llm_out.get("mode"), "candidates": norm},
                actor_id)
    return {"candidates": norm, "mode": llm_out.get("mode")}


# -----------------------------------------------------------------------------
# Stage 2 — verifier (critic pass)
# -----------------------------------------------------------------------------
async def _stage_verify(
    *, context_id: str, pipeline_run_id: str, actor_id: str,
    ctx_obj: Optional[Dict[str, Any]], docs: List[Dict[str, Any]],
    candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    doc_ids_available = [d["id"] for d in docs]

    # Deterministic prechecks first — no LLM needed.
    pre_accept: List[Dict[str, Any]] = []
    pre_reject: List[Dict[str, Any]] = []
    for c in candidates:
        valid_doc_ids = [d for d in c["doc_ids"] if d in doc_ids_available]
        if not valid_doc_ids:
            pre_reject.append({**c, "rejection_reason": "No cited doc_id exists in this context — potential hallucination."})
            continue
        if len((c.get("summary") or "").strip()) < 60:
            pre_reject.append({**c, "rejection_reason": "Summary too short — unlikely to meet board-paper bar."})
            continue
        pre_accept.append({**c, "doc_ids": valid_doc_ids})

    if not pre_accept:
        await _emit(context_id, pipeline_run_id, "signal.verified",
                    {"accepted": 0, "rejected": len(pre_reject), "rejections": pre_reject}, actor_id)
        return {"verified": [], "rejected": pre_reject, "mode": "deterministic"}

    # LLM critic pass on remaining
    payload = json.dumps([
        {k: v for k, v in c.items() if k != "id"}
        for c in pre_accept
    ], ensure_ascii=False)
    user_query = (
        "STAGE 2: VERIFICATION.\n"
        "You are an experienced audit-committee chair reviewing draft signals from "
        "an AI analyst. Your job is to KILL the weak ones and CONFIRM the strong ones. "
        "Be rigorous — a signal that makes it to the board paper must be defensible.\n\n"
        "Apply these tests to each candidate:\n"
        "  1. Evidence: is the claim actually supported by the cited doc_ids?\n"
        "  2. Specificity: does it say something concrete, or hedge generically?\n"
        "  3. Board relevance: would a NED or audit-committee chair actually act on it?\n"
        "  4. Materiality: is it important enough to deserve a signal slot?\n\n"
        f"Candidates to verify:\n{payload}\n\n"
        "For each candidate, return a verdict. Rewrite weak-but-salvageable headlines "
        "or summaries inline; reject the rest.\n\n"
        'Return JSON: {"verdicts":[{"headline":"<matches candidate headline>","verdict":"accept|reject",'
        '"rewritten_headline":"<optional if rewriting>","rewritten_summary":"<optional>","confidence":"high|medium|low","reason":"<brief>"}]}'
    )

    llm_out = await llm_call_llm(
        module="highlights.verify",
        user_query=user_query,
        context_object=ctx_obj,
        session_context={"session_id": f"signals-verify-{context_id}"},
        data_trust={"overall": docs_overall_trust(docs)},
        response_format="json",
    )
    parsed = parse_json_response(llm_out.get("response", ""))
    verdicts = (parsed or {}).get("verdicts") if isinstance(parsed, dict) else None
    if not isinstance(verdicts, list):
        # Degrade gracefully — treat all pre_accept as verified if verifier failed
        await _emit(context_id, pipeline_run_id, "signal.verified",
                    {"accepted": len(pre_accept), "rejected": len(pre_reject), "verifier_failed": True,
                     "mode": llm_out.get("mode")}, actor_id)
        return {
            "verified": [
                {**c, "confidence": "medium", "verifier_note": "Verifier LLM returned invalid JSON; candidate kept."}
                for c in pre_accept
            ],
            "rejected": pre_reject,
            "mode": llm_out.get("mode"),
        }

    verdict_by_hl = {(v.get("headline") or "").strip(): v for v in verdicts if isinstance(v, dict)}
    verified: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = list(pre_reject)
    for c in pre_accept:
        v = verdict_by_hl.get((c["headline"] or "").strip())
        if not v or v.get("verdict") == "accept":
            verified.append({
                **c,
                "headline": (v.get("rewritten_headline") if v and v.get("rewritten_headline") else c["headline"])[:240],
                "summary":  (v.get("rewritten_summary")  if v and v.get("rewritten_summary")  else c["summary"])[:2000],
                "confidence": (v or {}).get("confidence") if (v or {}).get("confidence") in ("high", "medium", "low") else "medium",
                "verifier_note": (v or {}).get("reason", ""),
            })
        else:
            rejected.append({**c, "rejection_reason": (v or {}).get("reason", "Verifier rejected.")})

    await _emit(context_id, pipeline_run_id, "signal.verified",
                {"accepted": len(verified), "rejected": len(rejected), "mode": llm_out.get("mode")}, actor_id)
    return {"verified": verified, "rejected": rejected, "mode": llm_out.get("mode")}


# -----------------------------------------------------------------------------
# Stage 3 — persist
# -----------------------------------------------------------------------------
async def _stage_persist(
    *, context_id: str, pipeline_run_id: str, actor_id: str,
    verified: List[Dict[str, Any]], docs: List[Dict[str, Any]],
    focus: Optional[str], mode: Optional[str],
) -> List[Dict[str, Any]]:
    doc_by_id = {d["id"]: d for d in docs}
    created_at = iso(now())
    persisted: List[Dict[str, Any]] = []
    for v in verified[:8]:
        sources = [
            {"doc_id": d_id, "doc_name": doc_by_id[d_id]["name"],
             "data_trust": doc_by_id[d_id].get("data_trust", "mixed")}
            for d_id in v["doc_ids"] if d_id in doc_by_id
        ]
        sig = {
            "id": str(uuid.uuid4()),
            "context_id": context_id,
            "type": v["type"],
            "headline": v["headline"],
            "summary": v["summary"],
            "confidence": v.get("confidence", "medium"),
            "sources": sources,
            "data_trust": docs_overall_trust([doc_by_id[i] for i in v["doc_ids"] if i in doc_by_id]) or "unrated",
            "generated_by": actor_id,
            "focus": focus,
            "mode": mode,
            "pipeline_run_id": pipeline_run_id,
            "verifier_note": v.get("verifier_note", ""),
            "created_at": created_at,
            "status": "active",
        }
        await db.signals.insert_one(sig)
        sig.pop("_id", None)
        persisted.append(sig)
    await _emit(context_id, pipeline_run_id, "signal.persisted",
                {"count": len(persisted)}, actor_id)
    return persisted


# -----------------------------------------------------------------------------
# Public endpoint — run the whole pipeline
# -----------------------------------------------------------------------------
class PipelineRunIn(BaseModel):
    focus: Optional[str] = None


@router.post("/contexts/{context_id}/pipeline/run")
async def pipeline_run(
    body: PipelineRunIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    context_id = ctx["context"]["id"]
    actor_id = ctx["account"]["id"]

    ctx_obj = await gather_context_object(context_id)
    docs = await gather_documents_for_grounding(context_id)
    if not docs:
        raise HTTPException(
            status_code=400,
            detail="Upload at least one document to this context before running the pipeline.",
        )

    pipeline_run_id = str(uuid.uuid4())
    await _emit(context_id, pipeline_run_id, "pipeline.started",
                {"doc_count": len(docs), "focus": body.focus}, actor_id)

    stage1 = await _stage_candidate_draft(
        context_id=context_id, pipeline_run_id=pipeline_run_id, actor_id=actor_id,
        ctx_obj=ctx_obj, docs=docs, focus=body.focus,
    )
    stage2 = await _stage_verify(
        context_id=context_id, pipeline_run_id=pipeline_run_id, actor_id=actor_id,
        ctx_obj=ctx_obj, docs=docs, candidates=stage1["candidates"],
    )
    persisted = await _stage_persist(
        context_id=context_id, pipeline_run_id=pipeline_run_id, actor_id=actor_id,
        verified=stage2["verified"], docs=docs, focus=body.focus,
        mode=stage1.get("mode"),
    )
    await _emit(context_id, pipeline_run_id, "pipeline.completed",
                {"persisted": len(persisted), "rejected": len(stage2["rejected"])}, actor_id)
    await write_audit(
        context_id, actor_id, "pipeline.run", "pipeline_run", pipeline_run_id,
        {"candidates": len(stage1["candidates"]), "persisted": len(persisted),
         "rejected": len(stage2["rejected"])},
    )
    return {
        "pipeline_run_id": pipeline_run_id,
        "candidates_drafted": len(stage1["candidates"]),
        "candidates_rejected": len(stage2["rejected"]),
        "signals_persisted": len(persisted),
        "signals": persisted,
        "rejections": stage2["rejected"],
        "mode": stage1.get("mode"),
    }


@router.get("/contexts/{context_id}/pipeline/events")
async def list_pipeline_events(
    ctx: Dict[str, Any] = Depends(require_context_membership()),
    pipeline_run_id: Optional[str] = None,
    limit: int = 100,
):
    q: Dict[str, Any] = {"context_id": ctx["context"]["id"]}
    if pipeline_run_id:
        q["pipeline_run_id"] = pipeline_run_id
    rows = await db.signal_events.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return rows
