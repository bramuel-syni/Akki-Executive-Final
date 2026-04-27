"""Influence Map — who is reading, sharing, mentioning what.

Aggregates already-existing engagement signals into a single
node-and-edge view so executives and NEDs can see, at a glance, who's
actually engaging with the company's documents and decisions.

Read-only. No new collections; this is purely a query layer over:

    document_engagement      — read receipts on documents
    shares                   — outbound shares of artefacts
    mentions / collab.comments — comments + @-mentions

Endpoint:
    GET /api/contexts/{cid}/influence-map?days=30

Returns:
    {
      "nodes": [
        {"id": "<id>", "kind": "person"|"document",
         "label": "...", "meta": {...}}, ...
      ],
      "edges": [
        {"source": "<person_id>", "target": "<doc_id>",
         "kind": "read"|"share"|"comment"|"mention",
         "weight": int, "last_at": iso}, ...
      ],
      "people": [{id, label, score, breakdown:{read,share,comment}}],
      "top_docs": [{id, label, score, readers:int}],
      "window_days": int
    }
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from core import db, get_current_account, now as _now, iso as _iso
from core import require_context_membership

router = APIRouter(prefix="/api")


# Edge weights — a share is louder than a read; a comment is louder
# than a share because it's an explicit position. Mentions are at the
# top because they're a direct call-out.
_KIND_WEIGHT = {
    "read":    1,
    "share":   3,
    "comment": 4,
    "mention": 5,
}


def _person_label(rec: Dict[str, Any]) -> str:
    return (
        rec.get("user_name") or rec.get("from_name") or rec.get("shared_by_name")
        or rec.get("user_email") or rec.get("from_email") or rec.get("shared_by_email")
        or "Unknown"
    )


def _person_id(rec: Dict[str, Any]) -> str:
    """Stable identity for a person across collections — prefer
    account_id; fall back to email so external contacts who haven't
    joined still show up as nodes."""
    return (
        rec.get("user_id") or rec.get("account_id")
        or rec.get("from_account_id") or rec.get("shared_by_account_id")
        or rec.get("user_email") or rec.get("from_email")
        or rec.get("shared_by_email") or "unknown"
    )


@router.get("/contexts/{context_id}/influence-map")
async def get_influence_map(
    context_id: str,
    days: int = Query(30, ge=1, le=365),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    cutoff = _iso(_now() - timedelta(days=days))

    # ── 1. Documents in this context (the right-hand axis)
    docs = await db.documents.find(
        {"context_id": context_id, "status": {"$ne": "archived"}},
        {"_id": 0, "id": 1, "name": 1, "original_filename": 1,
         "created_at": 1, "data_trust": 1},
    ).to_list(2000)
    doc_by_id = {d["id"]: d for d in docs}

    # ── 2. Read receipts within the window
    reads = await db.document_engagement.find(
        {"context_id": context_id, "timestamp": {"$gte": cutoff}},
        {"_id": 0},
    ).to_list(20_000)

    # ── 3. Shares of this context's artefacts
    shares = await db.shares.find(
        {"context_id": context_id, "created_at": {"$gte": cutoff}},
        {"_id": 0},
    ).to_list(5000)

    # ── 4. Comments + mentions on this context's artefacts
    comments = await db.collab_comments.find(
        {"context_id": context_id, "created_at": {"$gte": cutoff}},
        {"_id": 0},
    ).to_list(5000)
    mentions = await db.mentions.find(
        {"context_id": context_id, "created_at": {"$gte": cutoff}},
        {"_id": 0},
    ).to_list(5000)

    # ── Aggregate edges
    # edge key = (person_id, doc_id, kind) → {weight, last_at, person_label, doc_label}
    edges: Dict[tuple, Dict[str, Any]] = defaultdict(
        lambda: {"weight": 0, "last_at": None, "person_label": "", "doc_label": ""}
    )
    person_meta: Dict[str, Dict[str, Any]] = {}
    doc_meta: Dict[str, Dict[str, Any]] = {}

    def _bump(person_id: str, person_label: str, doc_id: str, doc_label: str,
              kind: str, at: str) -> None:
        if not doc_id or not person_id:
            return
        e = edges[(person_id, doc_id, kind)]
        e["weight"] += 1
        if not e["last_at"] or (at and at > e["last_at"]):
            e["last_at"] = at
        e["person_label"] = person_label
        e["doc_label"] = doc_label
        person_meta.setdefault(person_id, {"label": person_label,
                                           "breakdown": {"read": 0, "share": 0,
                                                         "comment": 0, "mention": 0}})
        person_meta[person_id]["breakdown"][kind] = (
            person_meta[person_id]["breakdown"].get(kind, 0) + 1
        )
        doc_meta.setdefault(doc_id, {"label": doc_label, "readers": set()})
        doc_meta[doc_id]["readers"].add(person_id)

    for r in reads:
        d = doc_by_id.get(r.get("document_id"))
        if not d:
            continue
        if r.get("action") not in ("read", "view", "open"):
            # We only count a real read; download/print already imply read.
            pass
        _bump(
            _person_id(r), _person_label(r),
            d["id"], d.get("name") or d.get("original_filename") or "Document",
            "read", r.get("timestamp") or "",
        )

    for s in shares:
        # Shares are people-to-people (not always a document) — only the
        # share types that point at a document map to the bipartite view.
        if s.get("item_type") not in ("doc_summary", "doc_evolution"):
            continue
        d = doc_by_id.get(s.get("item_id"))
        if not d:
            continue
        _bump(
            _person_id(s), _person_label(s),
            d["id"], d.get("name") or d.get("original_filename") or "Document",
            "share", s.get("created_at") or "",
        )

    for c in comments:
        if c.get("artefact_type") != "document":
            continue
        d = doc_by_id.get(c.get("artefact_id"))
        if not d:
            continue
        _bump(
            _person_id(c), _person_label(c),
            d["id"], d.get("name") or d.get("original_filename") or "Document",
            "comment", c.get("created_at") or "",
        )

    for m in mentions:
        if m.get("artefact_type") != "document":
            continue
        d = doc_by_id.get(m.get("artefact_id"))
        if not d:
            continue
        _bump(
            _person_id(m), _person_label(m),
            d["id"], d.get("name") or d.get("original_filename") or "Document",
            "mention", m.get("created_at") or "",
        )

    # ── Build nodes
    nodes: List[Dict[str, Any]] = []
    for pid, meta in person_meta.items():
        score = sum(meta["breakdown"][k] * _KIND_WEIGHT.get(k, 1)
                    for k in meta["breakdown"])
        nodes.append({
            "id": f"p:{pid}", "kind": "person",
            "label": meta["label"], "score": score,
            "breakdown": meta["breakdown"],
        })
    for did, meta in doc_meta.items():
        nodes.append({
            "id": f"d:{did}", "kind": "document",
            "label": meta["label"], "readers": len(meta["readers"]),
        })

    # ── Build edges (flattened)
    edge_list: List[Dict[str, Any]] = []
    for (pid, did, kind), e in edges.items():
        edge_list.append({
            "source": f"p:{pid}", "target": f"d:{did}",
            "kind": kind, "weight": e["weight"],
            "last_at": e["last_at"],
        })
    edge_list.sort(key=lambda e: (e["weight"], e["last_at"] or ""), reverse=True)

    # ── Roll-ups for the side panels
    people = sorted(
        [
            {"id": f"p:{pid}", "label": m["label"],
             "score": sum(m["breakdown"][k] * _KIND_WEIGHT.get(k, 1)
                          for k in m["breakdown"]),
             "breakdown": m["breakdown"]}
            for pid, m in person_meta.items()
        ],
        key=lambda r: r["score"], reverse=True,
    )

    top_docs = sorted(
        [
            {"id": f"d:{did}", "label": m["label"],
             "readers": len(m["readers"]),
             "score": sum(e["weight"] * _KIND_WEIGHT.get(kind, 1)
                          for (pid, ddid, kind), e in edges.items()
                          if ddid == did)}
            for did, m in doc_meta.items()
        ],
        key=lambda r: r["score"], reverse=True,
    )

    return {
        "context_id": context_id,
        "window_days": days,
        "generated_at": _iso(_now()),
        "nodes": nodes,
        "edges": edge_list,
        "people": people[:50],
        "top_docs": top_docs[:50],
        "totals": {
            "people": len(person_meta),
            "documents_engaged": len(doc_meta),
            "edges": len(edge_list),
            "reads": sum(1 for e in edges if e[2] == "read"),
            "shares": sum(1 for e in edges if e[2] == "share"),
            "comments": sum(1 for e in edges if e[2] == "comment"),
            "mentions": sum(1 for e in edges if e[2] == "mention"),
        },
    }
