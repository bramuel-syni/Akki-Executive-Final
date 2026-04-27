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

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from core import db, get_current_account, now as _now, iso as _iso
from core import require_context_membership
from email_service import send_email

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


# ──────────────────────────────────────────────────────────────────────
# Weekly Influence Digest — Monday 08:00 UTC cron
# ──────────────────────────────────────────────────────────────────────

def _digest_html(*, exec_name: str, context_name: str, payload: Dict[str, Any],
                 view_url: str) -> str:
    """Editorial email body — top 5 influencers + most-read docs of the week.
    Style matches the rest of AKKI's transactional email: cream + oxblood."""
    people = payload.get("people", [])[:5]
    docs = payload.get("top_docs", [])[:5]
    totals = payload.get("totals", {})

    def _row_html(rows, kind):
        if not rows:
            return ('<p style="font-size:12.5px;color:#7a6a52;font-style:italic;'
                    'margin:0 0 18px 0;">Nothing to flag this week.</p>')
        items = []
        for i, r in enumerate(rows, 1):
            right = (
                f"score {r.get('score', 0)}" if kind == "people"
                else f"{r.get('readers', 0)} reader{'' if r.get('readers') == 1 else 's'}"
            )
            items.append(
                f'<li style="margin-bottom:8px;padding:0;font-size:13.5px;'
                f'line-height:1.55;color:#1a1f2e;">'
                f'<span style="font-family:monospace;color:#7a6a52;'
                f'margin-right:6px;">{i:02d}</span>'
                f'<span>{r["label"]}</span>'
                f'<span style="float:right;font-size:11px;color:#7a6a52;'
                f'font-family:monospace;">{right}</span>'
                f'</li>'
            )
        return f'<ol style="list-style:none;padding:0;margin:0 0 22px 0;">{"".join(items)}</ol>'

    return (
        '<div style="font-family:Georgia,serif;max-width:600px;margin:0 auto;'
        'padding:36px 28px;background:#f5efe6;color:#1a1f2e;">'
        f'<p style="font-size:11px;letter-spacing:0.2em;text-transform:uppercase;'
        f'color:#7a6a52;margin:0 0 14px 0;">'
        f'AKKI · Influence digest · {context_name}</p>'
        f'<h1 style="font-size:24px;line-height:1.25;margin:0 0 6px 0;'
        f'font-weight:normal;">Who actually read.</h1>'
        f'<p style="font-size:14px;line-height:1.6;color:#3a3a3a;margin:0 0 26px 0;">'
        f'Good morning, {exec_name}. The pattern of attention across your '
        f'board\'s papers, this past week.</p>'
        '<p style="font-size:11px;letter-spacing:0.18em;text-transform:uppercase;'
        'color:#722f37;margin:0 0 8px 0;">Top influencers</p>'
        + _row_html(people, "people") +
        '<p style="font-size:11px;letter-spacing:0.18em;text-transform:uppercase;'
        'color:#722f37;margin:0 0 8px 0;">Most-engaged documents</p>'
        + _row_html(docs, "docs") +
        '<div style="border-top:1px solid #d6caa6;padding-top:18px;margin-top:6px;'
        'font-size:11.5px;color:#7a6a52;line-height:1.6;">'
        f'{totals.get("people", 0)} people · {totals.get("documents_engaged", 0)} docs · '
        f'{totals.get("reads", 0)} reads · {totals.get("shares", 0)} shares · '
        f'{totals.get("comments", 0)} comments · {totals.get("mentions", 0)} mentions'
        '</div>'
        f'<a href="{view_url}" style="display:inline-block;background:#722f37;color:#fff;'
        'padding:11px 22px;text-decoration:none;font-size:13px;letter-spacing:0.05em;'
        'margin-top:24px;">Open the full map &rarr;</a>'
        '<p style="font-size:11px;color:#7a6a52;margin:32px 0 0 0;">'
        'Sent every Monday morning · adjust in <em>Settings → Notifications</em>'
        '</p>'
        '</div>'
    )


@router.post("/contexts/{context_id}/influence-map/digest")
async def send_influence_digest_now(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Send the Influence Digest email for THIS context to the calling user
    immediately. Used by the admin tile and as the unit of work the cron
    calls per context."""
    payload = await get_influence_map(context_id=context_id, days=7, ctx=ctx)
    if payload["totals"]["edges"] == 0:
        return {"ok": False, "skipped": True, "reason": "no engagement"}

    account = ctx.get("account") or {}
    context = ctx.get("context") or {}
    exec_name = (account.get("name") or account.get("email") or "there").split("@")[0]
    context_name = context.get("name") or "your company"
    origin = (__import__("os").environ.get("FRONTEND_ORIGIN") or "").rstrip("/")
    view_url = f"{origin}/app/influence" if origin else "/app/influence"

    html = _digest_html(
        exec_name=exec_name, context_name=context_name,
        payload=payload, view_url=view_url,
    )
    res = await send_email(
        to=[account["email"]],
        subject=f"Influence Digest · {context_name}",
        html=html,
        tags=[{"name": "kind", "value": "influence_digest"},
              {"name": "context_id", "value": context_id}],
    )
    return {"ok": res.get("ok"), "mode": res.get("mode"),
            "id": res.get("id"), "totals": payload["totals"]}


@router.post("/cron/weekly-digest")
async def cron_weekly_digest(
    x_cron_secret: str = Header(default=""),
):
    """Internal cron endpoint — called by APScheduler every Monday 08:00
    UTC. Iterates every active executive role across every context,
    builds the previous-7-day digest, and emails each executive their
    own roll-up.

    Authenticated via the `AKKI_CRON_SECRET` shared header. Mirrors the
    blog cron so the same secret rotates the lot.
    """
    import os as _os
    expected = _os.environ.get("AKKI_CRON_SECRET", "")
    if not expected or x_cron_secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")

    sent = 0
    skipped = 0
    failed = 0
    # Walk every active context. For each, build the digest once, then
    # send to each executive member. NEDs get a lightweight version
    # (this v1 emails executives only — they own the read patterns;
    # NEDs receive briefings via a different cadence).
    contexts = await db.contexts.find(
        {"status": {"$ne": "archived"}}, {"_id": 0, "id": 1, "name": 1},
    ).to_list(2000)

    for c in contexts:
        cid = c["id"]
        # Members with the 'executive' role on this context
        members = await db.context_members.find(
            {"context_id": cid, "status": {"$ne": "archived"}},
            {"_id": 0},
        ).to_list(2000)
        execs = [m for m in members if "executive" in (m.get("roles") or [])]
        if not execs:
            continue

        # Build the digest payload ONCE for this context (cheap; same
        # 7-day rollup for everyone here).
        # Fake `ctx` dependency object — the helper only uses .context.
        # Use the route function directly with a synthetic ctx.
        try:
            payload = await get_influence_map(
                context_id=cid, days=7,
                ctx={"context": c, "account": {"id": "cron"}},
            )
        except Exception:
            failed += 1
            continue

        if payload["totals"]["edges"] == 0:
            skipped += 1
            continue

        origin = (_os.environ.get("FRONTEND_ORIGIN") or "").rstrip("/")
        view_url = f"{origin}/app/influence" if origin else "/app/influence"

        for ex in execs:
            account = await db.accounts.find_one(
                {"id": ex.get("account_id")}, {"_id": 0, "email": 1, "name": 1},
            )
            if not account or not account.get("email"):
                continue
            # Honour an opt-out flag if present on the member record.
            if ex.get("digest_opt_out") is True:
                continue
            exec_name = (account.get("name") or account["email"]).split("@")[0]
            html = _digest_html(
                exec_name=exec_name, context_name=c.get("name") or "your company",
                payload=payload, view_url=view_url,
            )
            res = await send_email(
                to=[account["email"]],
                subject=f"Influence Digest · {c.get('name') or 'your company'}",
                html=html,
                tags=[{"name": "kind", "value": "influence_digest"},
                      {"name": "context_id", "value": cid}],
            )
            if res.get("ok"):
                sent += 1
            else:
                failed += 1
    return {"sent": sent, "skipped_no_engagement": skipped,
            "failed": failed, "ran_at": _iso(_now())}
