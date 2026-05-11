"""Phase F0.1 — Universal Search dispatcher.

Federates search across the caller's memberships. The router calls
`run_federated_search(...)` and gets a list of normalised `SearchHit`
dicts. Each hit carries the originating `context_id` and `context_name`
so the frontend can show a "company badge" on every row.

Privacy Wall
------------
The dispatcher ONLY queries collections in contexts where the caller
has an active membership. There is NO cross-tenant payload mixing
within a single record — every snippet is sourced from the same
context that owns the record. Foreign tenants are simply not iterated.

Per surface handler contract
----------------------------
Each handler is `async (db, context_id, q, limit) -> list[dict]`
returning rows in the canonical `SearchHit` shape (see below).

Surface registry
----------------
`SURFACE_HANDLERS` maps short surface key → callable.
Phase 1: documents, chats, pulse, monitor.
Phase 2 placeholders: cycle, work_studio, briefs — return [] today;
adding them later is a one-line registry update plus the handler body.
"""
from __future__ import annotations

import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Canonical SearchHit shape
# ---------------------------------------------------------------------------
# Every handler returns dicts that look like this (extra fields ignored):
#   {
#     "id": "...",                    # the record id
#     "title": "...",                 # short label for the row
#     "snippet": "...",               # ≤160 chars; window around match
#     "type": "Document|Chat|Signal|Goal",  # human label
#     "date": "ISO-8601 string",      # for "recent first" sort
#     "deep_link": "/app/...",        # where to navigate on click
#     "_score": <float>,              # internal — used for relevance sort
#   }


_SNIPPET_CHARS = 160
_SNIPPET_BEFORE = 50


# ---------------------------------------------------------------------------
# Tiny helpers
# ---------------------------------------------------------------------------
def _escape_regex(q: str) -> str:
    return re.escape(q)


def _build_snippet(text: str, needle: str) -> str:
    """Pull a ≤160-char window around the first case-insensitive match.

    Falls back to the head of the text when no hit is found (e.g. when
    the match was in a title, not the body)."""
    if not text:
        return ""
    haystack = text.replace("\n", " ").strip()
    if not needle:
        return haystack[:_SNIPPET_CHARS]
    low = haystack.lower()
    idx = low.find(needle.lower())
    if idx < 0:
        return haystack[:_SNIPPET_CHARS]
    start = max(0, idx - _SNIPPET_BEFORE)
    end = min(len(haystack), start + _SNIPPET_CHARS)
    snip = haystack[start:end].strip()
    if start > 0:
        snip = "…" + snip
    if end < len(haystack):
        snip = snip + "…"
    return snip


# ---------------------------------------------------------------------------
# Surface handlers (Phase 1)
# ---------------------------------------------------------------------------
async def search_documents(
    db: Any, context_id: str, q: str, limit: int,
) -> List[Dict[str, Any]]:
    """Documents — case-insensitive regex on `name` OR `extracted_text`.

    Cheap and good enough today. The same BM25 helper used by `Ask`
    (`backend/bm25.py`) is heavier than this surface needs — we only
    show snippets, not grounding chunks."""
    rx = {"$regex": _escape_regex(q), "$options": "i"}
    cursor = db.documents.find(
        {
            "context_id": context_id,
            "$or": [{"name": rx}, {"extracted_text": rx}],
        },
        {"_id": 0, "id": 1, "name": 1, "extracted_text": 1, "created_at": 1, "status": 1},
    ).sort("created_at", -1).limit(limit)
    out: List[Dict[str, Any]] = []
    async for d in cursor:
        title = d.get("name") or "(untitled document)"
        body = d.get("extracted_text") or ""
        title_hit = q.lower() in title.lower()
        score = 2.0 if title_hit else 1.0
        out.append({
            "id": d["id"],
            "title": title,
            "snippet": _build_snippet(body, q) if not title_hit else _build_snippet(title, q),
            "type": "Document",
            "date": d.get("created_at") or "",
            "deep_link": f"/app/documents/{d['id']}",
            "_score": score,
        })
    return out


async def search_chats(
    db: Any, context_id: str, q: str, limit: int, *, account_id: str,
) -> List[Dict[str, Any]]:
    """Chats — same shape as the existing `/chats/search` endpoint but
    scoped here per (account_id, context_id). We need `account_id` to
    enforce the caller's ownership of the chat — chats are personal,
    not team-shared."""
    rx = {"$regex": _escape_regex(q), "$options": "i"}
    chat_filter: Dict[str, Any] = {
        "account_id": account_id,
        "context_id": context_id,
        "status": {"$ne": "archived"},
    }
    # Title hits — direct.
    title_chats = await db.chats.find(
        {**chat_filter, "title": rx},
        {"_id": 0, "id": 1, "title": 1, "last_message_at": 1, "created_at": 1},
    ).sort("last_message_at", -1).to_list(limit)
    seen = {c["id"] for c in title_chats}
    # Message-body hits — find chat_ids, dedup.
    all_chat_ids = [
        c["id"] async for c in db.chats.find(
            {**chat_filter}, {"_id": 0, "id": 1},
        )
    ]
    msg_hits: List[Dict[str, Any]] = []
    if all_chat_ids:
        cursor = db.chat_messages.find(
            {
                "account_id": account_id,
                "chat_id": {"$in": all_chat_ids},
                "content": rx,
            },
            {"_id": 0, "chat_id": 1, "content": 1, "created_at": 1},
        ).sort("created_at", -1).limit(limit * 2)
        chat_by_id: Dict[str, Dict[str, Any]] = {}
        async for m in cursor:
            if m["chat_id"] in seen:
                continue
            if m["chat_id"] not in chat_by_id:
                row = await db.chats.find_one(
                    {"id": m["chat_id"]},
                    {"_id": 0, "id": 1, "title": 1, "last_message_at": 1, "created_at": 1},
                )
                if row:
                    chat_by_id[m["chat_id"]] = row
            if m["chat_id"] in chat_by_id:
                msg_hits.append({**chat_by_id[m["chat_id"]], "_match_text": m["content"]})
                seen.add(m["chat_id"])
                if len(msg_hits) >= limit:
                    break
    out: List[Dict[str, Any]] = []
    for c in title_chats:
        out.append({
            "id": c["id"],
            "title": c.get("title") or "(untitled chat)",
            "snippet": _build_snippet(c.get("title") or "", q),
            "type": "Chat",
            "date": c.get("last_message_at") or c.get("created_at") or "",
            "deep_link": f"/app/chat?chat={c['id']}",
            "_score": 2.0,
        })
    for c in msg_hits:
        out.append({
            "id": c["id"],
            "title": c.get("title") or "(untitled chat)",
            "snippet": _build_snippet(c.get("_match_text") or "", q),
            "type": "Chat",
            "date": c.get("last_message_at") or c.get("created_at") or "",
            "deep_link": f"/app/chat?chat={c['id']}",
            "_score": 1.0,
        })
    return out[:limit]


async def search_pulse(
    db: Any, context_id: str, q: str, limit: int,
) -> List[Dict[str, Any]]:
    """Pulse signals — case-insensitive regex on `headline` OR `summary`.

    Excludes archived signals (Phase G lifecycle). Defaults to a 50-row
    cap because Pulse feeds are intentionally short."""
    rx = {"$regex": _escape_regex(q), "$options": "i"}
    cursor = db.signals.find(
        {
            "context_id": context_id,
            "state": {"$ne": "archived"},
            "$or": [{"headline": rx}, {"summary": rx}],
        },
        {"_id": 0, "id": 1, "headline": 1, "summary": 1, "type": 1, "state": 1, "created_at": 1},
    ).sort("created_at", -1).limit(limit)
    out: List[Dict[str, Any]] = []
    async for s in cursor:
        title = s.get("headline") or "(signal)"
        body = s.get("summary") or ""
        title_hit = q.lower() in title.lower()
        out.append({
            "id": s["id"],
            "title": title,
            "snippet": _build_snippet(body, q),
            "type": "Signal",
            "date": s.get("created_at") or "",
            "deep_link": f"/app/pulse?signal={s['id']}",
            "_score": 2.0 if title_hit else 1.0,
        })
    return out


async def search_monitor(
    db: Any, context_id: str, q: str, limit: int,
) -> List[Dict[str, Any]]:
    """Strategic goals — case-insensitive regex on `title` OR `description`.

    Monitor's per-role function whitelists are NOT applied here; search
    surfaces every goal in the context the caller can see."""
    rx = {"$regex": _escape_regex(q), "$options": "i"}
    cursor = db.strategic_goals.find(
        {
            "context_id": context_id,
            "$or": [{"title": rx}, {"description": rx}],
        },
        {"_id": 0, "id": 1, "title": 1, "description": 1, "department": 1,
         "target_date": 1, "created_at": 1, "owner_name": 1},
    ).sort("created_at", -1).limit(limit)
    out: List[Dict[str, Any]] = []
    async for g in cursor:
        title = g.get("title") or "(goal)"
        body = g.get("description") or ""
        title_hit = q.lower() in title.lower()
        out.append({
            "id": g["id"],
            "title": title,
            "snippet": _build_snippet(body, q),
            "type": "Goal",
            "date": g.get("created_at") or "",
            "deep_link": f"/app/monitor#goal-{g['id']}",
            "_score": 2.0 if title_hit else 1.0,
        })
    return out


async def search_cycle(
    db: Any, context_id: str, q: str, limit: int,
) -> List[Dict[str, Any]]:
    """Cycle Manager activity — matches `cycle_agendas.title/items[].title`,
    `cycle_contributions.title/body/body_text`, `committees.name`."""
    rx = {"$regex": _escape_regex(q), "$options": "i"}
    out: List[Dict[str, Any]] = []
    # Agendas
    async for a in db.cycle_agendas.find(
        {"context_id": context_id,
         "$or": [{"title": rx}, {"items.title": rx}]},
        {"_id": 0, "id": 1, "title": 1, "items": 1, "created_at": 1, "updated_at": 1},
    ).sort("updated_at", -1).limit(limit):
        title = a.get("title") or "(agenda)"
        # Snippet from a matching item if any.
        snip_src = title
        for it in (a.get("items") or []):
            itt = it.get("title") or ""
            if q.lower() in itt.lower():
                snip_src = itt
                break
        out.append({
            "id": a["id"],
            "title": title,
            "snippet": _build_snippet(snip_src, q),
            "type": "Cycle agenda",
            "date": a.get("updated_at") or a.get("created_at") or "",
            "deep_link": "/app/cycle",
            "_score": 2.0 if q.lower() in title.lower() else 1.0,
        })
    # Contributions
    async for c in db.cycle_contributions.find(
        {"context_id": context_id,
         "$or": [{"title": rx}, {"body_text": rx}, {"body": rx}, {"summary": rx}]},
        {"_id": 0, "id": 1, "title": 1, "body_text": 1, "body": 1, "summary": 1,
         "created_at": 1, "updated_at": 1, "agenda_item_id": 1},
    ).sort("updated_at", -1).limit(limit):
        title = c.get("title") or "(contribution)"
        body = c.get("body_text") or c.get("body") or c.get("summary") or ""
        out.append({
            "id": c["id"],
            "title": title,
            "snippet": _build_snippet(body, q),
            "type": "Cycle contribution",
            "date": c.get("updated_at") or c.get("created_at") or "",
            "deep_link": "/app/cycle",
            "_score": 2.0 if q.lower() in title.lower() else 1.0,
        })
    # Committees
    async for cm in db.committees.find(
        {"context_id": context_id, "name": rx},
        {"_id": 0, "id": 1, "name": 1, "purpose": 1, "created_at": 1},
    ).limit(limit):
        out.append({
            "id": cm["id"],
            "title": cm.get("name") or "(committee)",
            "snippet": _build_snippet(cm.get("purpose") or "", q),
            "type": "Committee",
            "date": cm.get("created_at") or "",
            "deep_link": "/app/cycle",
            "_score": 2.0,
        })
    return out[:limit]


async def search_work_studio(
    db: Any, context_id: str, q: str, limit: int,
) -> List[Dict[str, Any]]:
    """Work Studio artefacts — matches across `work_studio_briefs`,
    `studio_blocks`, `boardpacks`, `briefs`, `decks`."""
    rx = {"$regex": _escape_regex(q), "$options": "i"}
    out: List[Dict[str, Any]] = []
    # Briefs (Work Studio Phase C2 revisions live underneath)
    async for b in db.work_studio_briefs.find(
        {"context_id": context_id,
         "$or": [{"title": rx}, {"active_revision.title": rx},
                 {"active_revision.cover_lead_paragraph": rx}]},
        {"_id": 0, "id": 1, "title": 1, "active_revision": 1,
         "source_type": 1, "source_id": 1, "updated_at": 1, "created_at": 1},
    ).sort("updated_at", -1).limit(limit):
        rev = b.get("active_revision") or {}
        title = rev.get("title") or b.get("title") or "(brief)"
        body = rev.get("cover_lead_paragraph") or ""
        out.append({
            "id": b["id"],
            "title": title,
            "snippet": _build_snippet(body, q) or _build_snippet(title, q),
            "type": "Brief",
            "date": b.get("updated_at") or b.get("created_at") or "",
            "deep_link": f"/app/work-studio?brief={b['id']}",
            "_score": 2.0 if q.lower() in title.lower() else 1.0,
        })
    # Studio blocks (block composer rows)
    async for blk in db.studio_blocks.find(
        {"context_id": context_id,
         "$or": [{"heading": rx}, {"content": rx}, {"text": rx}]},
        {"_id": 0, "id": 1, "heading": 1, "content": 1, "text": 1,
         "artefact_kind": 1, "artefact_id": 1, "created_at": 1, "updated_at": 1},
    ).sort("updated_at", -1).limit(limit):
        title = blk.get("heading") or "(block)"
        body = blk.get("content") or blk.get("text") or ""
        kind = blk.get("artefact_kind") or "artefact"
        aid = blk.get("artefact_id") or ""
        out.append({
            "id": blk["id"],
            "title": title,
            "snippet": _build_snippet(body, q),
            "type": "Studio block",
            "date": blk.get("updated_at") or blk.get("created_at") or "",
            "deep_link": f"/app/studio/composer/{kind}/{aid}" if aid else "/app/work-studio",
            "_score": 1.0,
        })
    # Boardpacks (aggregates)
    async for bp in db.boardpacks.find(
        {"context_id": context_id,
         "$or": [{"title": rx}, {"summary": rx}]},
        {"_id": 0, "id": 1, "title": 1, "summary": 1, "created_at": 1, "updated_at": 1},
    ).sort("updated_at", -1).limit(limit):
        title = bp.get("title") or "(boardpack)"
        out.append({
            "id": bp["id"],
            "title": title,
            "snippet": _build_snippet(bp.get("summary") or "", q),
            "type": "Boardpack",
            "date": bp.get("updated_at") or bp.get("created_at") or "",
            "deep_link": f"/app/work-studio?boardpack={bp['id']}",
            "_score": 2.0 if q.lower() in title.lower() else 1.0,
        })
    # Briefs (legacy / Prepare module)
    async for br in db.briefs.find(
        {"context_id": context_id,
         "$or": [{"title": rx}, {"summary": rx}, {"body": rx}]},
        {"_id": 0, "id": 1, "title": 1, "summary": 1, "body": 1,
         "kind": 1, "created_at": 1},
    ).sort("created_at", -1).limit(limit):
        title = br.get("title") or "(brief)"
        out.append({
            "id": br["id"],
            "title": title,
            "snippet": _build_snippet(br.get("summary") or br.get("body") or "", q),
            "type": "Brief",
            "date": br.get("created_at") or "",
            "deep_link": f"/app/work-studio?brief={br['id']}",
            "_score": 1.0,
        })
    # Decks
    async for d in db.decks.find(
        {"context_id": context_id,
         "$or": [{"title": rx}, {"summary": rx}]},
        {"_id": 0, "id": 1, "title": 1, "summary": 1, "created_at": 1},
    ).sort("created_at", -1).limit(limit):
        title = d.get("title") or "(deck)"
        out.append({
            "id": d["id"],
            "title": title,
            "snippet": _build_snippet(d.get("summary") or "", q),
            "type": "Deck",
            "date": d.get("created_at") or "",
            "deep_link": f"/app/decks/{d['id']}",
            "_score": 2.0 if q.lower() in title.lower() else 1.0,
        })
    return out[:limit]


async def search_briefs(
    db: Any, context_id: str, q: str, limit: int,
) -> List[Dict[str, Any]]:
    """Brief Review queue items — items awaiting review live in
    `boardpacks` with status='in_review' or in `reports.status='in_review'`.
    We surface both."""
    rx = {"$regex": _escape_regex(q), "$options": "i"}
    out: List[Dict[str, Any]] = []
    # Boardpacks awaiting review
    async for bp in db.boardpacks.find(
        {"context_id": context_id,
         "status": {"$in": ["in_review", "awaiting_review", "review"]},
         "$or": [{"title": rx}, {"summary": rx}]},
        {"_id": 0, "id": 1, "title": 1, "summary": 1, "status": 1, "updated_at": 1, "created_at": 1},
    ).sort("updated_at", -1).limit(limit):
        title = bp.get("title") or "(brief in review)"
        out.append({
            "id": bp["id"],
            "title": title,
            "snippet": _build_snippet(bp.get("summary") or "", q),
            "type": "Brief in review",
            "date": bp.get("updated_at") or bp.get("created_at") or "",
            "deep_link": "/app/review",
            "_score": 2.0 if q.lower() in title.lower() else 1.0,
        })
    # Reports awaiting review
    async for r in db.reports.find(
        {"context_id": context_id, "status": "in_review",
         "$or": [{"title": rx}, {"summary": rx}, {"body": rx}]},
        {"_id": 0, "id": 1, "title": 1, "summary": 1, "body": 1,
         "status": 1, "updated_at": 1, "created_at": 1},
    ).sort("updated_at", -1).limit(limit):
        title = r.get("title") or "(report in review)"
        out.append({
            "id": r["id"],
            "title": title,
            "snippet": _build_snippet(r.get("summary") or r.get("body") or "", q),
            "type": "Report in review",
            "date": r.get("updated_at") or r.get("created_at") or "",
            "deep_link": "/app/review",
            "_score": 1.0,
        })
    return out[:limit]


# ---------------------------------------------------------------------------
# Surface handlers (Phase 2 — Universal Search F1 wired May 2026)
# ---------------------------------------------------------------------------
# Empty placeholder kept for any caller that imports the symbol but
# never reaches the dispatcher path. Real handlers above.

async def _empty(*_args: Any, **_kwargs: Any) -> List[Dict[str, Any]]:
    return []


SurfaceHandler = Callable[..., Awaitable[List[Dict[str, Any]]]]

SURFACE_HANDLERS: Dict[str, SurfaceHandler] = {
    # Phase 1 (Phase F0)
    "documents": search_documents,
    "chats": search_chats,
    "pulse": search_pulse,
    "monitor": search_monitor,
    # Phase 2 — Phase H5 wired May 2026
    "cycle": search_cycle,
    "work_studio": search_work_studio,
    "briefs": search_briefs,
}


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
async def run_federated_search(
    db: Any,
    *,
    account_id: str,
    q: str,
    memberships: List[Dict[str, Any]],
    surfaces: Optional[List[str]] = None,
    per_context_limit: int = 25,
) -> Dict[str, Any]:
    """Fan out across `memberships` and gather hits.

    `memberships` rows must carry at minimum `{context_id, context_name}`.
    Returns a dict with `results`, `per_context`, `per_surface`, and
    `latency_ms` so the router can shape its response uniformly.
    """
    t0 = time.monotonic()
    surfaces = surfaces or list(SURFACE_HANDLERS.keys())
    selected: Dict[str, SurfaceHandler] = {
        s: SURFACE_HANDLERS[s] for s in surfaces if s in SURFACE_HANDLERS
    }
    all_hits: List[Dict[str, Any]] = []
    per_context: Dict[str, Dict[str, Any]] = {}
    per_surface: Dict[str, int] = {s: 0 for s in selected}

    for m in memberships:
        cid = m.get("context_id")
        cname = m.get("context_name") or m.get("name") or "(unnamed)"
        if not cid:
            continue
        per_context.setdefault(cid, {"context_id": cid, "context_name": cname, "count": 0})
        for sname, handler in selected.items():
            # Chats need account_id (chats are personal); others are
            # context-scoped only. Pass kwargs so handlers can pick.
            try:
                rows = await handler(
                    db, cid, q, per_context_limit, account_id=account_id,
                ) if sname == "chats" else await handler(db, cid, q, per_context_limit)
            except TypeError:
                # Defensive — older signatures.
                rows = await handler(db, cid, q, per_context_limit)
            except Exception:  # pragma: no cover — surface failure non-fatal
                rows = []
            for r in rows:
                r["context_id"] = cid
                r["context_name"] = cname
                r["surface"] = sname
                all_hits.append(r)
            per_surface[sname] += len(rows)
            per_context[cid]["count"] += len(rows)

    # Sort: relevance desc, then date desc.
    def _sort_key(r: Dict[str, Any]) -> tuple:
        return (-(r.get("_score") or 0.0), -_iso_ord(r.get("date") or ""))
    all_hits.sort(key=_sort_key)

    return {
        "results": all_hits,
        "per_context": list(per_context.values()),
        "per_surface": [
            {"surface": s, "count": per_surface[s]} for s in selected
        ],
        "latency_ms": int((time.monotonic() - t0) * 1000),
    }


def _iso_ord(s: str) -> float:
    """Order an ISO date string so newer wins. Empty strings sort last."""
    if not s:
        return 0.0
    # Strings sort lexicographically the same as their date order
    # for ISO-8601; convert to a stable float via codepoint sum.
    # We just need monotonicity, not exact epoch math.
    return sum((i + 1) * ord(c) for i, c in enumerate(s[:32]))
