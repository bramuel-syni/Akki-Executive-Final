"""Studio block composer — Phase 8 / Advisory 9.

Generic block engine for briefings, decks, reports. v1 ships with a
7-block library: paragraph, heading_2, heading_3, callout, citation,
signal_card, divider.

Storage: `db.studio_blocks` keyed on (artefact_kind, artefact_id), one
doc per artefact. Index ensures uniqueness.

Lazy migration: on first GET for an artefact with no blocks doc, we
synthesise a default block list from the artefact's existing flat-text
content and persist it.

Write-through: every mutation projects the blocks back to the artefact's
legacy flat-text fields (`briefings.opening_paragraph` / `decks.body` /
`reports.body`) so v1 readers, PDF/DOCX export, and read-receipts keep
working unchanged through the 7-day flag-flip transition.

Sensitivity: every mutation re-runs `studio_sensitivity.classify()` over
the projected text. Failures swallowed (best-effort).
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from core import db, get_current_account, iso as _iso, now as _now, write_audit


router = APIRouter(prefix="/api/studio", tags=["studio-blocks"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
ArtefactKind = Literal["briefing", "deck", "report"]
BlockKind = Literal[
    "paragraph", "heading_2", "heading_3", "callout",
    "citation", "signal_card", "divider",
]
ALLOWED_KINDS = {
    "paragraph", "heading_2", "heading_3", "callout",
    "citation", "signal_card", "divider",
}
ALLOWED_TONES = {"info", "warn", "risk"}


class BlockCreateIn(BaseModel):
    kind: str = Field(min_length=1, max_length=20)
    content: Dict[str, Any] = Field(default_factory=dict)
    after_block_id: Optional[str] = None  # if set, insert after this; else append


class BlockPatchIn(BaseModel):
    content: Dict[str, Any]


class BlockMoveIn(BaseModel):
    to_order: int = Field(ge=0)


class ReorderIn(BaseModel):
    block_ids: List[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _validate_content(kind: str, content: Dict[str, Any]) -> Dict[str, Any]:
    if kind not in ALLOWED_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown block kind: {kind}")
    c = dict(content or {})
    if kind in ("paragraph", "callout"):
        text = (c.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail=f"{kind} block requires non-empty text.")
        max_len = 4000 if kind == "paragraph" else 1000
        if len(text) > max_len:
            raise HTTPException(status_code=400, detail=f"{kind} text exceeds {max_len} chars.")
        c["text"] = text
        if kind == "callout":
            tone = (c.get("tone") or "info").lower()
            if tone not in ALLOWED_TONES:
                raise HTTPException(status_code=400, detail=f"callout tone must be one of {sorted(ALLOWED_TONES)}.")
            c["tone"] = tone
    elif kind in ("heading_2", "heading_3"):
        text = (c.get("text") or "").strip()
        if not text or len(text) > 200:
            raise HTTPException(status_code=400, detail="Heading text must be 1-200 chars.")
        c["text"] = text
    elif kind == "citation":
        if not c.get("doc_id"):
            raise HTTPException(status_code=400, detail="citation.doc_id is required.")
        if "page" not in c or not isinstance(c.get("page"), int):
            c["page"] = int(c.get("page") or 1)
        cite_text = (c.get("text") or "").strip()
        if len(cite_text) > 800:
            raise HTTPException(status_code=400, detail="citation.text exceeds 800 chars.")
        c["text"] = cite_text
        c["paragraph_id"] = c.get("paragraph_id") or None
        c["doc_id"] = str(c["doc_id"])
    elif kind == "signal_card":
        if not c.get("signal_id"):
            raise HTTPException(status_code=400, detail="signal_card.signal_id is required.")
        c["signal_id"] = str(c["signal_id"])
    elif kind == "divider":
        c = {}
    return c


def _new_block_id(artefact_id: str, idx: int) -> str:
    seed = f"{artefact_id}|{idx}|{_iso(_now())}"
    return hashlib.sha1(seed.encode()).hexdigest()[:12]


def _project_to_text(blocks: List[Dict[str, Any]]) -> str:
    """Render the block list as flat text (markdown-ish) so legacy v1
    readers + PDF/DOCX exporters keep producing equivalent output."""
    lines: List[str] = []
    for b in blocks:
        k = b["kind"]; c = b.get("content") or {}
        if k == "paragraph":
            lines.append(c.get("text", ""))
        elif k == "heading_2":
            lines.append(f"## {c.get('text', '')}")
        elif k == "heading_3":
            lines.append(f"### {c.get('text', '')}")
        elif k == "callout":
            tone = (c.get("tone") or "info").upper()
            lines.append(f"> [{tone}] {c.get('text', '')}")
        elif k == "citation":
            cite = c.get("text") or ""
            page = c.get("page") or 1
            doc_id = c.get("doc_id") or ""
            para = f"¶{c['paragraph_id']}" if c.get("paragraph_id") else ""
            lines.append(f'[{doc_id} p.{page}{para}] "{cite}"')
        elif k == "signal_card":
            lines.append(f"[signal:{c.get('signal_id')}]")
        elif k == "divider":
            lines.append("---")
        else:
            lines.append("")
    return "\n\n".join(line for line in lines if line is not None).strip()


def _split_paragraphs(text: str) -> List[str]:
    if not text:
        return []
    out: List[str] = []
    buf: List[str] = []
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if line.strip() == "":
            if buf:
                out.append("\n".join(buf).strip())
                buf = []
        else:
            buf.append(line)
    if buf:
        out.append("\n".join(buf).strip())
    return [p for p in out if p]


def _seed_blocks_from_artefact(artefact: Dict[str, Any], kind: str) -> List[Dict[str, Any]]:
    """Synthesise a default block list from existing flat content."""
    out: List[Dict[str, Any]] = []
    now_iso = _iso(_now())
    aid = artefact.get("id") or ""

    def _add(block_kind: str, content: Dict[str, Any]):
        idx = len(out)
        out.append({
            "id": _new_block_id(aid, idx),
            "kind": block_kind,
            "content": content,
            "order": idx,
            "created_at": now_iso,
            "updated_at": now_iso,
        })

    title = artefact.get("title") or artefact.get("subject")
    if title:
        _add("heading_2", {"text": title})

    if kind == "briefing":
        opener = (artefact.get("opening_paragraph") or "").strip()
        if opener:
            _add("paragraph", {"text": opener})
        for it in artefact.get("items") or []:
            sid = it.get("signal_id")
            if sid:
                _add("signal_card", {"signal_id": str(sid)})
            ev = (it.get("evidence") or "").strip()
            if ev:
                _add("paragraph", {"text": ev})
        body = (artefact.get("body") or "").strip()
        if body:
            for p in _split_paragraphs(body):
                _add("paragraph", {"text": p[:4000]})
    elif kind == "deck":
        for slide in artefact.get("slides") or []:
            slide_title = (slide.get("title") or "").strip()
            if slide_title:
                _add("heading_3", {"text": slide_title[:200]})
            slide_body = (slide.get("body") or slide.get("notes") or "").strip()
            if slide_body:
                _add("paragraph", {"text": slide_body[:4000]})
        body = (artefact.get("body") or "").strip()
        if body:
            for p in _split_paragraphs(body):
                _add("paragraph", {"text": p[:4000]})
    else:  # report
        body = (artefact.get("body") or artefact.get("content") or "").strip()
        if body:
            for p in _split_paragraphs(body):
                _add("paragraph", {"text": p[:4000]})

    if not out:
        _add("paragraph", {"text": "—"})
    return out


def _artefact_collection(kind: str) -> Any:
    return {
        "briefing": db.briefings,
        "deck": db.decks,
        "report": db.reports,
    }.get(kind)


async def _resolve_artefact(kind: str, aid: str, account: Dict[str, Any]) -> Dict[str, Any]:
    if kind not in ("briefing", "deck", "report"):
        raise HTTPException(status_code=400, detail=f"Unknown artefact kind: {kind}")
    coll = _artefact_collection(kind)
    if coll is None:
        raise HTTPException(status_code=400, detail=f"No collection for kind: {kind}")
    artefact = await coll.find_one({"id": aid}, {"_id": 0})
    if not artefact:
        raise HTTPException(status_code=404, detail=f"{kind} not found")
    ctx_id = artefact.get("context_id")
    if not ctx_id:
        raise HTTPException(status_code=409, detail=f"{kind} missing context_id")
    membership = await db.memberships.find_one(
        {"context_id": ctx_id, "account_id": account["id"], "status": "active"},
        {"_id": 0},
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this artefact's context.")
    return artefact


async def _resolve_signal_card(content: Dict[str, Any]) -> Dict[str, Any]:
    sid = content.get("signal_id")
    if not sid:
        return content
    sig = await db.signals.find_one(
        {"id": sid},
        {"_id": 0, "id": 1, "headline": 1, "type": 1, "rationale": 1, "evidence": 1, "severity": 1},
    )
    if sig:
        return {**content, "_resolved": sig}
    return {**content, "_resolved": None}


async def _hydrate_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Resolve referential block content (signal_card.signal_id → headline,
    citation could in future resolve doc_name + paragraph text)."""
    out: List[Dict[str, Any]] = []
    for b in blocks:
        if b["kind"] == "signal_card":
            new_content = await _resolve_signal_card(b.get("content") or {})
            out.append({**b, "content": new_content})
        elif b["kind"] == "citation":
            c = dict(b.get("content") or {})
            doc = await db.documents.find_one(
                {"id": c.get("doc_id")}, {"_id": 0, "id": 1, "name": 1},
            )
            if doc:
                c["_doc_name"] = doc.get("name")
            out.append({**b, "content": c})
        else:
            out.append(b)
    return out


async def _persist_and_project(
    kind: str, artefact_id: str, context_id: str, blocks: List[Dict[str, Any]],
) -> None:
    """Write blocks doc + write-through to legacy text + sensitivity hook."""
    now_iso = _iso(_now())
    # Renumber order contiguous.
    for idx, b in enumerate(blocks):
        b["order"] = idx

    await db.studio_blocks.update_one(
        {"artefact_kind": kind, "artefact_id": artefact_id},
        {
            "$set": {
                "artefact_kind": kind,
                "artefact_id": artefact_id,
                "context_id": context_id,
                "blocks": blocks,
                "schema_version": 1,
                "updated_at": now_iso,
            },
            "$setOnInsert": {"created_at": now_iso},
        },
        upsert=True,
    )

    # Project to flat text on the artefact (write-through). Keep this
    # narrow — only update the body/opening_paragraph fields, never the
    # title/items/etc.
    flat = _project_to_text(blocks)
    coll = _artefact_collection(kind)
    update_set: Dict[str, Any] = {"updated_at": now_iso}
    if kind == "briefing":
        update_set["opening_paragraph"] = flat
        update_set["body"] = flat
    elif kind == "deck":
        update_set["body"] = flat
    else:
        update_set["body"] = flat
    await coll.update_one({"id": artefact_id}, {"$set": update_set})

    # Sensitivity classification — best-effort, swallow failures.
    try:
        from studio_sensitivity import classify as _classify
        verdict = _classify(flat)
        if verdict:
            await coll.update_one(
                {"id": artefact_id},
                {"$set": {"classification": verdict.get("classification") or verdict}},
            )
    except Exception:  # pragma: no cover — non-fatal
        pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/{kind}/{artefact_id}/blocks")
async def list_blocks(
    kind: str = Path(...),
    artefact_id: str = Path(...),
    current: Dict[str, Any] = Depends(get_current_account),
):
    artefact = await _resolve_artefact(kind, artefact_id, current)
    doc = await db.studio_blocks.find_one(
        {"artefact_kind": kind, "artefact_id": artefact_id}, {"_id": 0},
    )
    if not doc:
        # Lazy-migrate from existing flat content.
        seeded = _seed_blocks_from_artefact(artefact, kind)
        await _persist_and_project(kind, artefact_id, artefact["context_id"], seeded)
        doc = await db.studio_blocks.find_one(
            {"artefact_kind": kind, "artefact_id": artefact_id}, {"_id": 0},
        )
        await write_audit(
            artefact["context_id"], current["id"],
            "studio_blocks.lazy_migrated",
            kind, artefact_id, {"block_count": len(seeded)},
        )

    blocks = await _hydrate_blocks(doc.get("blocks") or [])
    return {
        "artefact_kind": kind,
        "artefact_id": artefact_id,
        "context_id": doc.get("context_id"),
        "blocks": blocks,
        "schema_version": doc.get("schema_version", 1),
        "updated_at": doc.get("updated_at"),
    }


@router.post("/{kind}/{artefact_id}/blocks")
async def create_block(
    body: BlockCreateIn,
    kind: str = Path(...),
    artefact_id: str = Path(...),
    current: Dict[str, Any] = Depends(get_current_account),
):
    artefact = await _resolve_artefact(kind, artefact_id, current)
    content = _validate_content(body.kind, body.content)

    doc = await db.studio_blocks.find_one(
        {"artefact_kind": kind, "artefact_id": artefact_id}, {"_id": 0},
    )
    blocks: List[Dict[str, Any]] = (doc or {}).get("blocks") or []

    now_iso = _iso(_now())
    new_block = {
        "id": _new_block_id(artefact_id, len(blocks)),
        "kind": body.kind,
        "content": content,
        "order": -1,  # set in _persist_and_project
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    if body.after_block_id:
        idx = next((i for i, b in enumerate(blocks) if b["id"] == body.after_block_id), -1)
        if idx == -1:
            raise HTTPException(status_code=404, detail="after_block_id not found")
        blocks.insert(idx + 1, new_block)
    else:
        blocks.append(new_block)

    await _persist_and_project(kind, artefact_id, artefact["context_id"], blocks)
    await write_audit(
        artefact["context_id"], current["id"],
        "studio_blocks.created", kind, artefact_id,
        {"block_id": new_block["id"], "kind": body.kind},
    )
    return {"block": new_block, "block_count": len(blocks)}


@router.patch("/{kind}/{artefact_id}/blocks/{block_id}")
async def patch_block(
    body: BlockPatchIn,
    kind: str = Path(...),
    artefact_id: str = Path(...),
    block_id: str = Path(...),
    current: Dict[str, Any] = Depends(get_current_account),
):
    artefact = await _resolve_artefact(kind, artefact_id, current)
    doc = await db.studio_blocks.find_one(
        {"artefact_kind": kind, "artefact_id": artefact_id}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No blocks for this artefact yet.")
    blocks = doc.get("blocks") or []
    target_idx = next((i for i, b in enumerate(blocks) if b["id"] == block_id), -1)
    if target_idx == -1:
        raise HTTPException(status_code=404, detail="Block not found")
    target = blocks[target_idx]
    target["content"] = _validate_content(target["kind"], body.content)
    target["updated_at"] = _iso(_now())
    await _persist_and_project(kind, artefact_id, artefact["context_id"], blocks)
    await write_audit(
        artefact["context_id"], current["id"],
        "studio_blocks.patched", kind, artefact_id,
        {"block_id": block_id, "kind": target["kind"]},
    )
    return {"block": target}


@router.post("/{kind}/{artefact_id}/blocks/{block_id}/move")
async def move_block(
    body: BlockMoveIn,
    kind: str = Path(...),
    artefact_id: str = Path(...),
    block_id: str = Path(...),
    current: Dict[str, Any] = Depends(get_current_account),
):
    artefact = await _resolve_artefact(kind, artefact_id, current)
    doc = await db.studio_blocks.find_one(
        {"artefact_kind": kind, "artefact_id": artefact_id}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No blocks for this artefact yet.")
    blocks = list(doc.get("blocks") or [])
    src_idx = next((i for i, b in enumerate(blocks) if b["id"] == block_id), -1)
    if src_idx == -1:
        raise HTTPException(status_code=404, detail="Block not found")
    target = blocks.pop(src_idx)
    new_idx = max(0, min(body.to_order, len(blocks)))
    blocks.insert(new_idx, target)
    await _persist_and_project(kind, artefact_id, artefact["context_id"], blocks)
    await write_audit(
        artefact["context_id"], current["id"],
        "studio_blocks.moved", kind, artefact_id,
        {"block_id": block_id, "from": src_idx, "to": new_idx},
    )
    return {"block_count": len(blocks), "moved_to": new_idx}


@router.delete("/{kind}/{artefact_id}/blocks/{block_id}")
async def delete_block(
    kind: str = Path(...),
    artefact_id: str = Path(...),
    block_id: str = Path(...),
    current: Dict[str, Any] = Depends(get_current_account),
):
    artefact = await _resolve_artefact(kind, artefact_id, current)
    doc = await db.studio_blocks.find_one(
        {"artefact_kind": kind, "artefact_id": artefact_id}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No blocks for this artefact yet.")
    blocks = [b for b in (doc.get("blocks") or []) if b["id"] != block_id]
    if len(blocks) == len(doc.get("blocks") or []):
        raise HTTPException(status_code=404, detail="Block not found")
    await _persist_and_project(kind, artefact_id, artefact["context_id"], blocks)
    await write_audit(
        artefact["context_id"], current["id"],
        "studio_blocks.deleted", kind, artefact_id,
        {"block_id": block_id},
    )
    return {"block_count": len(blocks)}


@router.post("/{kind}/{artefact_id}/blocks/reorder")
async def reorder_blocks(
    body: ReorderIn,
    kind: str = Path(...),
    artefact_id: str = Path(...),
    current: Dict[str, Any] = Depends(get_current_account),
):
    artefact = await _resolve_artefact(kind, artefact_id, current)
    doc = await db.studio_blocks.find_one(
        {"artefact_kind": kind, "artefact_id": artefact_id}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No blocks for this artefact yet.")
    by_id = {b["id"]: b for b in (doc.get("blocks") or [])}
    if set(body.block_ids) != set(by_id.keys()):
        raise HTTPException(status_code=400, detail="block_ids must include every existing block exactly once.")
    new_blocks = [by_id[bid] for bid in body.block_ids]
    await _persist_and_project(kind, artefact_id, artefact["context_id"], new_blocks)
    await write_audit(
        artefact["context_id"], current["id"],
        "studio_blocks.reordered", kind, artefact_id,
        {"block_count": len(new_blocks)},
    )
    return {"block_count": len(new_blocks)}
