"""Studio block composer — Phase 8 / Advisory 9.

Generic block engine for briefings, decks, reports. v1 ships with the
Standard palette (9 block types):

  heading            — content.text + content.level (1, 2 or 3)
                       NB: level 1 is the slide divider for decks.
  paragraph          — content.text                       (Text)
  bulleted_list      — content.items[]                     (Bulleted list)
  callout            — content.text + content.tone         (Callout)
  citation           — content.doc_id, paragraph_id, page, text
                       (Citation / Quote — must resolve to a paragraph
                        anchor in the Reading Viewer)
  signal_card        — content.signal_id, optional metric{value,label,
                       delta,unit,trend} (Signal / Metric)
  divider            — no content                          (Divider)
  table              — content.headers[], rows[][]         (Table)
  image              — content.storage_key, alt, caption   (Image)

Storage:  one `db.studio_blocks` doc per (artefact_kind, artefact_id).

Lazy migration:  on first GET for an artefact with no blocks doc, we
synthesise a default block list from the artefact's existing flat
content and persist it.

Write-through:  every mutation projects the blocks back to the
artefact's legacy flat-text fields (`briefings.opening_paragraph` /
`decks.body` / `reports.body`) so v1 readers, PDF/DOCX export and
read-receipts keep working unchanged.

Sensitivity:  every mutation re-runs `studio_sensitivity.score_sensitivity()`
on the projected text. If any citation block references a document
classified Restricted, the artefact classification is floored at
Confidential — enforced server-side, not in the UI.

Lifecycle:  draft → in_review → approved → sent.  Submit-for-review
queues the artefact in Daily Review (a third kind alongside inbound docs
and briefings).  Approve transitions to `approved`.  Send dispatches
via Resend (test-mode acceptable when RESEND_API_KEY is unset — the
email_service returns mode="noop" and we record that in the audit log).
"""
from __future__ import annotations

import base64
import hashlib
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from core import db, get_current_account, iso as _iso, now as _now, write_audit


logger = logging.getLogger("akki.studio_blocks")
router = APIRouter(prefix="/api/studio", tags=["studio-blocks"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
ALLOWED_KINDS = {
    "heading", "heading_1", "heading_2", "heading_3",  # heading_N legacy aliases
    "paragraph",
    "bulleted_list",
    "callout",
    "citation",
    "signal_card",
    "divider",
    "table",
    "image",
}
ALLOWED_TONES = {"info", "warn", "risk"}
ALLOWED_TRENDS = {"up", "down", "flat"}

# Lifecycle states for the composed artefact.
LIFECYCLE_DRAFT = "draft"
LIFECYCLE_IN_REVIEW = "in_review"
LIFECYCLE_APPROVED = "approved"
LIFECYCLE_SENT = "sent"


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


class SubmitReviewIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=600)


class ApproveIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=600)


class SendIn(BaseModel):
    to: List[str] = Field(min_length=1, max_length=20)
    subject: Optional[str] = Field(default=None, max_length=240)
    body_note: Optional[str] = Field(default=None, max_length=2000)


class ImageUploadIn(BaseModel):
    """Base64-encoded inline image upload. Kept simple in v1 (no chunking)."""
    filename: str = Field(min_length=1, max_length=200)
    mime_type: str = Field(min_length=1, max_length=80)
    data_base64: str = Field(min_length=4, max_length=8 * 1024 * 1024)  # ~6 MB raw
    alt: Optional[str] = Field(default=None, max_length=240)


# ---------------------------------------------------------------------------
# Block validation
# ---------------------------------------------------------------------------
def _normalise_heading(content: Dict[str, Any]) -> Dict[str, Any]:
    text = (content.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="heading.text is required.")
    if len(text) > 200:
        raise HTTPException(status_code=400, detail="heading.text exceeds 200 chars.")
    level = content.get("level")
    if level is None:
        level = 2
    try:
        level = int(level)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="heading.level must be 1, 2 or 3.")
    if level not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="heading.level must be 1, 2 or 3.")
    return {"text": text, "level": level}


def _validate_content(kind: str, content: Dict[str, Any]) -> Dict[str, Any]:  # noqa: C901
    if kind not in ALLOWED_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown block kind: {kind}")
    c = dict(content or {})

    if kind == "heading":
        return _normalise_heading(c)
    if kind in ("heading_1", "heading_2", "heading_3"):
        # Back-compat: collapse level-suffixed kinds into the canonical
        # heading kind so the projection + render stays consistent.
        c["level"] = int(kind.split("_")[1])
        return _normalise_heading(c)

    if kind == "paragraph":
        text = (c.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="paragraph.text is required.")
        if len(text) > 4000:
            raise HTTPException(status_code=400, detail="paragraph.text exceeds 4000 chars.")
        return {"text": text}

    if kind == "callout":
        text = (c.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="callout.text is required.")
        if len(text) > 1000:
            raise HTTPException(status_code=400, detail="callout.text exceeds 1000 chars.")
        tone = (c.get("tone") or "info").lower()
        if tone not in ALLOWED_TONES:
            raise HTTPException(status_code=400, detail=f"callout.tone must be one of {sorted(ALLOWED_TONES)}.")
        return {"text": text, "tone": tone}

    if kind == "bulleted_list":
        items = c.get("items") or []
        if not isinstance(items, list) or not items:
            raise HTTPException(status_code=400, detail="bulleted_list.items must be a non-empty array.")
        if len(items) > 50:
            raise HTTPException(status_code=400, detail="bulleted_list.items capped at 50 entries.")
        norm: List[str] = []
        for it in items:
            if not isinstance(it, str):
                raise HTTPException(status_code=400, detail="bulleted_list.items must be strings.")
            t = it.strip()
            if not t:
                continue
            if len(t) > 500:
                raise HTTPException(status_code=400, detail="bulleted_list item exceeds 500 chars.")
            norm.append(t)
        if not norm:
            raise HTTPException(status_code=400, detail="bulleted_list.items must contain at least one non-empty entry.")
        return {"items": norm}

    if kind == "citation":
        if not c.get("doc_id"):
            raise HTTPException(status_code=400, detail="citation.doc_id is required.")
        try:
            page = int(c.get("page") or 1)
        except (TypeError, ValueError):
            page = 1
        text = (c.get("text") or "").strip()
        if len(text) > 800:
            raise HTTPException(status_code=400, detail="citation.text exceeds 800 chars.")
        return {
            "doc_id": str(c["doc_id"]),
            "page": page,
            "paragraph_id": (c.get("paragraph_id") or None),
            "text": text,
        }

    if kind == "signal_card":
        sid = c.get("signal_id")
        if not sid:
            raise HTTPException(status_code=400, detail="signal_card.signal_id is required.")
        out: Dict[str, Any] = {"signal_id": str(sid)}
        metric = c.get("metric")
        if metric is not None:
            if not isinstance(metric, dict):
                raise HTTPException(status_code=400, detail="signal_card.metric must be an object.")
            label = (metric.get("label") or "").strip()[:120]
            value = metric.get("value")
            if value is not None:
                value = str(value)[:60]
            delta = metric.get("delta")
            if delta is not None:
                delta = str(delta)[:32]
            unit = (metric.get("unit") or "").strip()[:16]
            trend = (metric.get("trend") or "").lower().strip()
            if trend and trend not in ALLOWED_TRENDS:
                raise HTTPException(status_code=400, detail=f"signal_card.metric.trend must be one of {sorted(ALLOWED_TRENDS)}.")
            out["metric"] = {
                "label": label, "value": value, "delta": delta,
                "unit": unit, "trend": trend or None,
            }
        return out

    if kind == "divider":
        return {}

    if kind == "table":
        headers = c.get("headers") or []
        rows = c.get("rows") or []
        if not isinstance(headers, list) or not isinstance(rows, list):
            raise HTTPException(status_code=400, detail="table.headers / table.rows must be arrays.")
        if not headers:
            raise HTTPException(status_code=400, detail="table.headers must be non-empty.")
        if len(headers) > 12:
            raise HTTPException(status_code=400, detail="table.headers capped at 12 columns.")
        if len(rows) > 100:
            raise HTTPException(status_code=400, detail="table.rows capped at 100 rows.")
        norm_headers = [str(h)[:120] for h in headers]
        col_count = len(norm_headers)
        norm_rows: List[List[str]] = []
        for r in rows:
            if not isinstance(r, list):
                raise HTTPException(status_code=400, detail="table.rows entries must be arrays of strings.")
            row = [str(cell)[:240] for cell in r[:col_count]]
            while len(row) < col_count:
                row.append("")
            norm_rows.append(row)
        return {"headers": norm_headers, "rows": norm_rows}

    if kind == "image":
        if not c.get("storage_key"):
            raise HTTPException(status_code=400, detail="image.storage_key is required.")
        scan = c.get("scan")
        if scan is not None:
            scan = str(scan)[:32].lower()
            if scan not in ("clamav", "unknown"):
                scan = None
        return {
            "storage_key": str(c["storage_key"])[:300],
            "alt": (c.get("alt") or "")[:240],
            "caption": (c.get("caption") or "")[:300],
            "mime_type": (c.get("mime_type") or "")[:80],
            "width": int(c.get("width") or 0) or None,
            "height": int(c.get("height") or 0) or None,
            # Scanner provenance — the UI reads this, not a literal.
            "scan": scan,
        }

    raise HTTPException(status_code=400, detail=f"Unhandled kind: {kind}")


def _canonical_kind(kind: str) -> str:
    """Collapse heading_N kinds back to the canonical 'heading'."""
    if kind in ("heading_1", "heading_2", "heading_3"):
        return "heading"
    return kind


def _new_block_id(artefact_id: str, idx: int) -> str:
    seed = f"{artefact_id}|{idx}|{_iso(_now())}|{uuid.uuid4().hex[:6]}"
    return hashlib.sha1(seed.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Projection helpers (write-through to legacy flat-text)
# ---------------------------------------------------------------------------
def _project_to_text(blocks: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for b in blocks:
        k = b["kind"]
        c = b.get("content") or {}
        if k == "heading":
            level = int(c.get("level") or 2)
            prefix = "#" * max(1, min(level, 3))
            lines.append(f"{prefix} {c.get('text', '')}")
        elif k == "paragraph":
            lines.append(c.get("text", ""))
        elif k == "bulleted_list":
            for it in c.get("items") or []:
                lines.append(f"- {it}")
        elif k == "callout":
            tone = (c.get("tone") or "info").upper()
            lines.append(f"> [{tone}] {c.get('text', '')}")
        elif k == "citation":
            cite = c.get("text") or ""
            page = c.get("page") or 1
            doc_id = c.get("doc_id") or ""
            para = f"¶{c['paragraph_id']}" if c.get("paragraph_id") else ""
            quoted = f' "{cite}"' if cite else ""
            lines.append(f"[{doc_id} p.{page}{para}]{quoted}")
        elif k == "signal_card":
            sid = c.get("signal_id")
            metric = c.get("metric") or {}
            mlabel = metric.get("label") or ""
            mval = metric.get("value") or ""
            mdelta = metric.get("delta") or ""
            mtrend = metric.get("trend") or ""
            extras = " ".join(s for s in [mlabel, mval, mdelta, mtrend] if s)
            lines.append(f"[signal:{sid}] {extras}".strip())
        elif k == "divider":
            lines.append("---")
        elif k == "table":
            headers = c.get("headers") or []
            rows = c.get("rows") or []
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join("---" for _ in headers) + " |")
            for r in rows:
                lines.append("| " + " | ".join(r) + " |")
        elif k == "image":
            alt = c.get("alt") or ""
            caption = c.get("caption") or ""
            lines.append(f"[image:{c.get('storage_key')}] {alt}".strip())
            if caption:
                lines.append(f"_{caption}_")
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
        if not line.strip():
            if buf:
                out.append("\n".join(buf).strip())
                buf = []
        else:
            buf.append(line)
    if buf:
        out.append("\n".join(buf).strip())
    return [p for p in out if p]


def _seed_blocks_from_artefact(artefact: Dict[str, Any], kind: str) -> List[Dict[str, Any]]:
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
        _add("heading", {"text": str(title)[:200], "level": 2})

    if kind == "briefing":
        opener = (artefact.get("opening_paragraph") or "").strip()
        if opener:
            _add("paragraph", {"text": opener[:4000]})
        for it in artefact.get("items") or []:
            sid = it.get("signal_id")
            if sid:
                _add("signal_card", {"signal_id": str(sid)})
            ev = (it.get("evidence") or "").strip()
            if ev:
                _add("paragraph", {"text": ev[:4000]})
        body = (artefact.get("body") or "").strip()
        if body:
            for p in _split_paragraphs(body):
                _add("paragraph", {"text": p[:4000]})
    elif kind == "deck":
        for slide in artefact.get("slides") or []:
            stitle = (slide.get("title") or "").strip()
            if stitle:
                _add("heading", {"text": stitle[:200], "level": 1})
            sbody = (slide.get("body") or slide.get("body_md") or slide.get("notes") or "").strip()
            if sbody:
                for p in _split_paragraphs(sbody):
                    _add("paragraph", {"text": p[:4000]})
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


# ---------------------------------------------------------------------------
# Artefact resolution + access control
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Hydration
# ---------------------------------------------------------------------------
async def _resolve_signal_card(content: Dict[str, Any]) -> Dict[str, Any]:
    sid = content.get("signal_id")
    if not sid:
        return content
    sig = await db.signals.find_one(
        {"id": sid},
        {"_id": 0, "id": 1, "headline": 1, "type": 1, "rationale": 1,
         "evidence": 1, "severity": 1},
    )
    return {**content, "_resolved": sig or None}


async def _hydrate_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for b in blocks:
        if b["kind"] == "signal_card":
            new_content = await _resolve_signal_card(b.get("content") or {})
            out.append({**b, "content": new_content})
        elif b["kind"] == "citation":
            c = dict(b.get("content") or {})
            doc = await db.documents.find_one(
                {"id": c.get("doc_id")},
                {"_id": 0, "id": 1, "name": 1, "classification": 1},
            )
            if doc:
                c["_doc_name"] = doc.get("name")
                c["_doc_classification"] = doc.get("classification")
            out.append({**b, "content": c})
        else:
            out.append(b)
    return out


# ---------------------------------------------------------------------------
# Sensitivity + persistence
# ---------------------------------------------------------------------------
async def _classification_floor_from_citations(blocks: List[Dict[str, Any]]) -> Optional[str]:
    """If any citation block references a doc classified Restricted, we
    floor the artefact at Confidential. A Confidential-source citation
    floors the artefact at Internal. Returns the floor key, or None.

    Implemented server-side per the product rule — the UI does not get
    to override this.
    """
    band_order = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
    highest_seen = -1
    for b in blocks:
        if b.get("kind") != "citation":
            continue
        c = b.get("content") or {}
        doc_id = c.get("doc_id")
        if not doc_id:
            continue
        doc = await db.documents.find_one(
            {"id": doc_id}, {"_id": 0, "classification": 1},
        )
        cls = ((doc or {}).get("classification") or {}).get("classification") or (doc or {}).get("classification")
        if isinstance(cls, str):
            highest_seen = max(highest_seen, band_order.get(cls.lower(), -1))
    if highest_seen < 0:
        return None
    # Restricted source ⇒ at least Confidential.
    if highest_seen >= band_order["restricted"]:
        return "confidential"
    # Confidential source ⇒ at least Internal.
    if highest_seen >= band_order["confidential"]:
        return "internal"
    return None


async def _recompute_sensitivity(
    coll: Any,
    artefact_id: str,
    blocks: List[Dict[str, Any]],
    flat_text: str,
) -> Optional[Dict[str, Any]]:
    """Run the sensitivity scorer + apply the citation floor. Best-effort.

    NB: `studio_sensitivity._extract_text` walks a curated set of artefact
    keys (title / subtitle / intent / research_question / objective /
    opening_paragraph / closing_note / synthesis / lockin / slides[] /
    items[]). It does NOT read `body`. We therefore feed the flat text in
    via `opening_paragraph`, which is the key briefings already use, so
    the existing scorer covers all three artefact kinds without a fork.
    """
    try:
        from studio_sensitivity import score_sensitivity
        verdict = score_sensitivity({"opening_paragraph": flat_text, "body": flat_text})
        floor = await _classification_floor_from_citations(blocks)
        if floor:
            band_order = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
            if band_order.get(verdict.get("classification", "internal"), 0) < band_order[floor]:
                verdict["classification"] = floor
                verdict["label"] = floor.capitalize()
                verdict["score"] = max(verdict.get("score", 0), 50 if floor == "confidential" else 75)
                verdict.setdefault("reasons", []).append(
                    "Floored by referenced source's classification"
                )
                verdict["citation_floor_applied"] = True
        await coll.update_one(
            {"id": artefact_id},
            {"$set": {"classification": verdict, "classification_at": _iso(_now())}},
        )
        return verdict
    except Exception as e:  # noqa: BLE001 — non-fatal
        logger.warning("sensitivity recompute failed: %s", e)
        return None


async def _persist_and_project(
    kind: str, artefact_id: str, context_id: str, blocks: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Write blocks doc + write-through to legacy text + sensitivity.
    Phase 12.2 ITEM C — also runs Synisense on the concatenated block
    text and persists a parallel `synisense` projection on the artefact
    so the PreviewDrawer can render the spans on first save and the
    public-read endpoint can assert `synisense_version >= 1` before
    serving externally.

    Returns a dict shaped:
        {
          "classification": <legacy sensitivity payload>,
          "synisense": <preview payload or None>,
          "synisense_first_accept_pending": bool,
          "synisense_drawer_reopen": bool,  # set when new sensitive
                                            # content appears since
                                            # the last user accept.
        }
    Callers persist this verbatim into their endpoint response.
    """
    now_iso = _iso(_now())
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
                "schema_version": 2,
                "updated_at": now_iso,
            },
            "$setOnInsert": {"created_at": now_iso},
        },
        upsert=True,
    )

    flat = _project_to_text(blocks)
    coll = _artefact_collection(kind)

    # ── Phase 12.2 ITEM C — Synisense screening on the flat text. We
    # store the redacted projection alongside the original because the
    # blocks themselves remain the editable source of truth; downstream
    # surfaces (public read, share email, validator) read the redacted
    # version, while the editor reads the original.
    syn_preview: Optional[Dict[str, Any]] = None
    redacted_flat = flat
    if (flat or "").strip():
        try:
            from services.synisense import run as syn_run
            out = await syn_run(
                text=flat, context_id=context_id,
                surface=kind if kind in {"briefing", "deck", "report"} else "report",
                mode="redact",
            )
            redacted_flat = out["redacted_text"]
            syn_preview = {
                "spans": out.get("spans") or [],
                "stats": out.get("stats") or {},
                "version": 1,
                "histogram": _entity_histogram(out.get("spans") or []),
                "computed_at": now_iso,
            }
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "synisense studio hook failed (degraded — original "
                "persisted): %s", e.__class__.__name__,
            )

    update_set: Dict[str, Any] = {"updated_at": now_iso}
    if kind == "briefing":
        update_set["opening_paragraph"] = flat
        update_set["body"] = flat
    elif kind == "deck":
        update_set["body"] = flat
    else:
        update_set["body"] = flat

    if syn_preview is not None:
        update_set["body_redacted"] = redacted_flat
        update_set["synisense"] = syn_preview
        update_set["synisense_version"] = 1

    await coll.update_one({"id": artefact_id}, {"$set": update_set})

    classification = await _recompute_sensitivity(coll, artefact_id, blocks, flat)

    # Drawer state: first save (no first_accept_at yet) → pending.
    # Subsequent save with strictly NEW entity types → reopen once.
    artefact_now = await coll.find_one(
        {"id": artefact_id},
        {"_id": 0, "synisense_first_accept_at": 1,
         "synisense_last_accepted_histogram": 1},
    ) or {}
    first_accept_at = artefact_now.get("synisense_first_accept_at")
    pending = (syn_preview is not None) and (not first_accept_at)
    drawer_reopen = False
    if first_accept_at and syn_preview:
        prev = artefact_now.get("synisense_last_accepted_histogram") or {}
        cur = syn_preview.get("histogram") or {}
        new_types = set(cur) - set(prev)
        if new_types:
            drawer_reopen = True

    return {
        "classification": classification,
        "synisense": syn_preview,
        "synisense_first_accept_pending": pending,
        "synisense_drawer_reopen": drawer_reopen,
    }


def _entity_histogram(spans: List[Dict[str, Any]]) -> Dict[str, int]:
    h: Dict[str, int] = {}
    for s in spans:
        t = s.get("entity_type") or "UNKNOWN"
        h[t] = h.get(t, 0) + 1
    return h


# ---------------------------------------------------------------------------
# Endpoints — block CRUD
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
    # Re-fetch the artefact to reflect any classification updates.
    artefact = await _artefact_collection(kind).find_one(
        {"id": artefact_id},
        {"_id": 0, "id": 1, "title": 1, "classification": 1, "block_status": 1,
         "submitted_at": 1, "approved_at": 1, "sent_at": 1},
    )
    return {
        "artefact_kind": kind,
        "artefact_id": artefact_id,
        "context_id": doc.get("context_id"),
        "blocks": blocks,
        "schema_version": doc.get("schema_version", 2),
        "updated_at": doc.get("updated_at"),
        "artefact": artefact,
    }


@router.post("/{kind}/{artefact_id}/blocks")
async def create_block(
    body: BlockCreateIn,
    kind: str = Path(...),
    artefact_id: str = Path(...),
    current: Dict[str, Any] = Depends(get_current_account),
):
    artefact = await _resolve_artefact(kind, artefact_id, current)
    canonical = _canonical_kind(body.kind)
    content = _validate_content(body.kind, body.content)

    doc = await db.studio_blocks.find_one(
        {"artefact_kind": kind, "artefact_id": artefact_id}, {"_id": 0},
    )
    blocks: List[Dict[str, Any]] = (doc or {}).get("blocks") or []

    now_iso = _iso(_now())
    new_block = {
        "id": _new_block_id(artefact_id, len(blocks)),
        "kind": canonical,
        "content": content,
        "order": -1,
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

    proj = await _persist_and_project(kind, artefact_id, artefact["context_id"], blocks)
    await write_audit(
        artefact["context_id"], current["id"],
        "studio_blocks.created", kind, artefact_id,
        {"block_id": new_block["id"], "kind": canonical},
    )
    return {
        "block": new_block, "block_count": len(blocks),
        "classification": proj.get("classification"),
        "synisense": proj.get("synisense"),
        "synisense_first_accept_pending": proj.get("synisense_first_accept_pending", False),
        "synisense_drawer_reopen": proj.get("synisense_drawer_reopen", False),
    }


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
    proj = await _persist_and_project(kind, artefact_id, artefact["context_id"], blocks)
    await write_audit(
        artefact["context_id"], current["id"],
        "studio_blocks.patched", kind, artefact_id,
        {"block_id": block_id, "kind": target["kind"]},
    )
    return {
        "block": target,
        "classification": proj.get("classification"),
        "synisense": proj.get("synisense"),
        "synisense_first_accept_pending": proj.get("synisense_first_accept_pending", False),
        "synisense_drawer_reopen": proj.get("synisense_drawer_reopen", False),
    }


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


# ---------------------------------------------------------------------------
# Image upload — Phase 10 wires real ClamAV scanning (services.clamav_service).
# Scanner-unreachable returns 503; signature match returns 422; neither
# branch persists the file.
# ---------------------------------------------------------------------------
@router.post("/{kind}/{artefact_id}/upload-image")
async def upload_image(
    body: ImageUploadIn,
    kind: str = Path(...),
    artefact_id: str = Path(...),
    current: Dict[str, Any] = Depends(get_current_account),
):
    artefact = await _resolve_artefact(kind, artefact_id, current)
    if not body.mime_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image/* mime types accepted.")
    try:
        raw = base64.b64decode(body.data_base64, validate=False)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 payload.")
    if len(raw) < 16:
        raise HTTPException(status_code=400, detail="Image payload too small.")
    if len(raw) > 6 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image exceeds 6 MB limit.")

    from documents_service import save_to_storage
    from services import clamav_service
    from services.clamav_service import ClamAVUnreachable
    try:
        scan_result = clamav_service.scan(raw, body.filename)
    except ClamAVUnreachable as e:
        await write_audit(
            artefact["context_id"], current["id"],
            "upload.virus_scan.unreachable",
            kind, artefact_id, {"error": str(e)[:200]},
        )
        raise HTTPException(
            status_code=503,
            detail={"error": "scanner_unavailable", "reason": "virus scanner offline"},
        )
    if not scan_result.clean:
        await write_audit(
            artefact["context_id"], current["id"],
            "upload.virus_scan.blocked",
            kind, artefact_id,
            {"signature": scan_result.signature, "size_bytes": len(raw)},
        )
        raise HTTPException(
            status_code=422,
            detail={"error": "blocked", "reason": "malware_suspected", "signature": scan_result.signature},
        )

    image_id = str(uuid.uuid4())
    storage_key = save_to_storage(
        artefact["context_id"], image_id, body.filename, raw, content_type=body.mime_type,
    )
    # Persist a lightweight record so /uploads/* GET routes can resolve it.
    await db.studio_images.insert_one({
        "id": image_id,
        "context_id": artefact["context_id"],
        "artefact_kind": kind,
        "artefact_id": artefact_id,
        "storage_key": storage_key,
        "mime_type": body.mime_type,
        "filename": body.filename,
        "alt": body.alt or "",
        "size_bytes": len(raw),
        "uploaded_by": current["id"],
        "created_at": _iso(_now()),
        "scan": "clamav",
        "scan_signature": scan_result.signature,
        "scan_ms": scan_result.scan_ms,
    })
    await write_audit(
        artefact["context_id"], current["id"],
        "studio_blocks.image.uploaded",
        kind, artefact_id,
        {"image_id": image_id, "size_bytes": len(raw), "scan": "clamav"},
    )
    return {
        "id": image_id,
        "storage_key": storage_key,
        "mime_type": body.mime_type,
        "alt": body.alt or "",
        "scan": "clamav",
        "scan_ms": scan_result.scan_ms,
    }


# ---------------------------------------------------------------------------
# Lifecycle: submit / approve / send
# ---------------------------------------------------------------------------
@router.get("/{kind}/{artefact_id}/lifecycle")
async def get_lifecycle(
    kind: str = Path(...),
    artefact_id: str = Path(...),
    current: Dict[str, Any] = Depends(get_current_account),
):
    artefact = await _resolve_artefact(kind, artefact_id, current)
    return {
        "artefact_kind": kind,
        "artefact_id": artefact_id,
        "block_status": artefact.get("block_status") or LIFECYCLE_DRAFT,
        "submitted_at": artefact.get("submitted_at"),
        "approved_at": artefact.get("approved_at"),
        "sent_at": artefact.get("sent_at"),
        "classification": artefact.get("classification"),
    }


@router.post("/{kind}/{artefact_id}/submit-review")
async def submit_for_review(
    body: SubmitReviewIn,
    kind: str = Path(...),
    artefact_id: str = Path(...),
    current: Dict[str, Any] = Depends(get_current_account),
):
    artefact = await _resolve_artefact(kind, artefact_id, current)
    current_status = artefact.get("block_status") or LIFECYCLE_DRAFT
    if current_status not in (LIFECYCLE_DRAFT, LIFECYCLE_IN_REVIEW):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot submit from state '{current_status}'.",
        )
    coll = _artefact_collection(kind)
    now_iso = _iso(_now())
    await coll.update_one(
        {"id": artefact_id},
        {"$set": {
            "block_status": LIFECYCLE_IN_REVIEW,
            "submitted_at": now_iso,
            "submitted_by": current["id"],
            "submission_note": (body.note or "")[:600],
        }},
    )
    await write_audit(
        artefact["context_id"], current["id"],
        "studio_blocks.submit_review", kind, artefact_id,
        {"note": (body.note or "")[:200]},
    )
    return {"block_status": LIFECYCLE_IN_REVIEW, "submitted_at": now_iso}


@router.post("/{kind}/{artefact_id}/approve")
async def approve_composed(
    body: ApproveIn,
    kind: str = Path(...),
    artefact_id: str = Path(...),
    current: Dict[str, Any] = Depends(get_current_account),
):
    artefact = await _resolve_artefact(kind, artefact_id, current)
    current_status = artefact.get("block_status") or LIFECYCLE_DRAFT
    if current_status != LIFECYCLE_IN_REVIEW:
        raise HTTPException(
            status_code=409,
            detail="Only artefacts in review can be approved.",
        )
    coll = _artefact_collection(kind)
    now_iso = _iso(_now())
    await coll.update_one(
        {"id": artefact_id},
        {"$set": {
            "block_status": LIFECYCLE_APPROVED,
            "approved_at": now_iso,
            "approved_by": current["id"],
            "approval_note": (body.note or "")[:600],
        }},
    )
    await write_audit(
        artefact["context_id"], current["id"],
        "studio_blocks.approve", kind, artefact_id,
        {"note": (body.note or "")[:200]},
    )
    return {"block_status": LIFECYCLE_APPROVED, "approved_at": now_iso}


@router.post("/{kind}/{artefact_id}/send")
async def send_composed(
    body: SendIn,
    kind: str = Path(...),
    artefact_id: str = Path(...),
    current: Dict[str, Any] = Depends(get_current_account),
):
    artefact = await _resolve_artefact(kind, artefact_id, current)
    current_status = artefact.get("block_status") or LIFECYCLE_DRAFT
    if current_status != LIFECYCLE_APPROVED:
        raise HTTPException(
            status_code=409,
            detail="Only approved artefacts can be sent.",
        )

    # Build a plain-text body from the most recent block snapshot.
    doc = await db.studio_blocks.find_one(
        {"artefact_kind": kind, "artefact_id": artefact_id}, {"_id": 0},
    )
    blocks = (doc or {}).get("blocks") or []
    flat_text = _project_to_text(blocks)
    title = artefact.get("title") or f"AKKI {kind}"
    subject = (body.subject or f"{title}").strip()[:240]
    note = (body.body_note or "").strip()

    # Minimal, editorial HTML body. Keep it deliberately plain — the
    # composed text carries the editorial weight; we do not theme it
    # here.
    html_chunks = [f"<h2 style=\"font-family:Georgia,serif;color:#0A1F44;\">{title}</h2>"]
    if note:
        html_chunks.append(f"<p style=\"color:#2A2622;line-height:1.55;\">{note}</p>")
    html_chunks.append(
        "<pre style=\"font-family:Georgia,serif;white-space:pre-wrap;color:#1a1a1a;"
        "background:#F7F3EA;padding:18px;border-left:3px solid #8B2E2B;\">"
        + (flat_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        + "</pre>"
    )
    html_body = "<div>" + "".join(html_chunks) + "</div>"

    from email_service import send_email, configured as resend_configured
    result = await send_email(
        to=list(body.to),
        subject=subject,
        html=html_body,
        text=(flat_text if not note else f"{note}\n\n{flat_text}"),
        from_executive_name=current.get("name") or current.get("email"),
        reply_to=current.get("email"),
        tags=[
            {"name": "artefact_kind", "value": kind},
            {"name": "artefact_id", "value": artefact_id},
        ],
    )

    coll = _artefact_collection(kind)
    now_iso = _iso(_now())
    await coll.update_one(
        {"id": artefact_id},
        {"$set": {
            "block_status": LIFECYCLE_SENT,
            "sent_at": now_iso,
            "sent_by": current["id"],
            "sent_to": list(body.to),
            "send_mode": result.get("mode"),
        }},
    )
    await write_audit(
        artefact["context_id"], current["id"],
        "studio_blocks.send", kind, artefact_id,
        {
            "to": list(body.to),
            "subject": subject,
            "mode": result.get("mode"),
            "resend_configured": resend_configured(),
        },
    )
    return {
        "block_status": LIFECYCLE_SENT,
        "sent_at": now_iso,
        "send_result": {"ok": result.get("ok"), "mode": result.get("mode"), "id": result.get("id")},
    }



# ---------------------------------------------------------------------------
# Phase 12.2 ITEM C — Synisense first-save preview accept
# ---------------------------------------------------------------------------
@router.post("/{kind}/{artefact_id}/synisense-accept")
async def accept_synisense_preview(
    kind: str = Path(...),
    artefact_id: str = Path(...),
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Persist the user's first-save acceptance of the Synisense
    preview. After this call, subsequent saves redact silently and the
    PreviewDrawer only reopens when *new* entity types are detected
    (see `synisense_drawer_reopen` on `_persist_and_project`).

    The accept is a state-transition only — the redacted projection
    has already been persisted by the most recent save. We mark the
    transition timestamp and snapshot the entity histogram the user
    accepted so we know what 'new sensitive content' means next time.
    """
    artefact = await _resolve_artefact(kind, artefact_id, current)
    coll = _artefact_collection(kind)
    cur = await coll.find_one(
        {"id": artefact_id},
        {"_id": 0, "synisense": 1, "synisense_first_accept_at": 1,
         "synisense_version": 1},
    ) or {}
    syn = cur.get("synisense") or {}
    histogram = syn.get("histogram") or {}
    now_iso = _iso(_now())
    # Phase 12.2 closeout BUG 2 — defensive bump of synisense_version
    # on accept. Normally `_persist_and_project` has already set it on
    # the most recent save, but if the artefact was created via a
    # non-block-composer path (e.g. decks.generate_deck) and only later
    # accepted via the drawer, this is the place to ensure the public
    # read assertion never trips on a 'forgot to bump' edge case.
    new_version = max(int(cur.get("synisense_version") or 0), 1)
    await coll.update_one(
        {"id": artefact_id},
        {"$set": {
            "synisense_first_accept_at": cur.get("synisense_first_accept_at") or now_iso,
            "synisense_last_accepted_at": now_iso,
            "synisense_last_accepted_histogram": histogram,
            "synisense_last_accepted_by": current["id"],
            "synisense_version": new_version,
        }},
    )
    await write_audit(
        artefact["context_id"], current["id"],
        "synisense.studio.accepted", kind, artefact_id,
        {"histogram": histogram, "spans": (syn.get("stats") or {}).get("regex_hits", 0)
         + (syn.get("stats") or {}).get("presidio_hits", 0)},
    )
    return {
        "ok": True,
        "synisense_first_accept_at": now_iso,
        "histogram_accepted": histogram,
    }
