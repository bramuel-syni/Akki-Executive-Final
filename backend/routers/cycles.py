"""Cycle Manager v2 — multi-cycle master endpoints.

Routes:
  POST   /api/contexts/{cid}/cycles                — create draft
  GET    /api/contexts/{cid}/cycles                — paginated, search + sort
  GET    /api/contexts/{cid}/cycles/{cycle_id}     — detail + counts + readiness
  POST   /api/contexts/{cid}/cycles/{cycle_id}/activate
  POST   /api/contexts/{cid}/cycles/{cycle_id}/close

The `cycles` collection is the new master. `cycle_agendas` continues
to hold the items but is now keyed by `cycle_id` (= `cycle_agendas.id`).
See `services/cycle_lifecycle.py` for the shared helpers.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import db, iso, now, require_context_membership, write_audit
from services.cycle_lifecycle import (
    CYCLE_STATUSES,
    compute_cycle_counts,
    compute_readiness_score,
    get_cycle_or_404,
)

logger = logging.getLogger("akki.cycles")

router = APIRouter(prefix="/api")


# ─────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────
class CycleCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class CycleOut(BaseModel):
    id: str
    context_id: str
    title: str
    status: str
    created_at: str
    activated_at: Optional[str] = None
    closed_at: Optional[str] = None
    readiness_score: Optional[int] = None
    agenda_count: int = 0
    contributor_count: int = 0


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
async def _persist_agenda_shell(cycle_id: str, context_id: str, account_id: str, title: str) -> None:
    """Create the matching `cycle_agendas` row with the same id so the
    legacy single-cycle endpoints continue to resolve it. Idempotent."""
    existing = await db.cycle_agendas.find_one({"id": cycle_id}, {"_id": 0, "id": 1})
    if existing:
        return
    await db.cycle_agendas.insert_one({
        "id": cycle_id,
        "cycle_id": cycle_id,  # alias for new code paths
        "context_id": context_id,
        "account_id": account_id,
        "title": title,
        "items": [],
        "status": "active",  # legacy field — the new state lives on db.cycles
        "created_at": iso(now()),
        "updated_at": iso(now()),
    })


async def _hydrate_cycle(row: Dict[str, Any]) -> Dict[str, Any]:
    counts = await compute_cycle_counts(row["id"])
    readiness = await compute_readiness_score(row["id"])
    cycle_id = row["id"]
    agenda_count = counts["agenda_count"]
    team_count = counts["contributor_count"]
    # Readiness % — count agenda items that have at least one contribution.
    readiness_pct = 0
    if agenda_count > 0:
        agenda_doc = await db.cycle_agendas.find_one(
            {"id": cycle_id}, {"_id": 0, "items": 1},
        )
        items = (agenda_doc or {}).get("items") or []
        item_ids_with_contrib = await db.cycle_contributions.distinct(
            "agenda_item_id",
            {"agenda_id": cycle_id, "agenda_item_id": {"$ne": None}},
        )
        covered = sum(1 for it in items if it.get("id") in item_ids_with_contrib)
        readiness_pct = int((covered * 100) // agenda_count) if agenda_count else 0
    # Last activity = most recent updated_at across the cycle-scoped
    # collections, falling back to the cycle's own created_at.
    # collections, falling back to the cycle's own created_at.
    last_act = row.get("updated_at") or row.get("created_at")
    for coll, ts_field in (
        ("cycle_contributions", "created_at"),
        ("cycle_team", "updated_at"),
        ("cycle_followups", "updated_at"),
    ):
        c = getattr(db, coll)
        latest = await c.find_one(
            {"agenda_id": cycle_id}, {"_id": 0, ts_field: 1},
            sort=[(ts_field, -1)],
        )
        if latest and latest.get(ts_field) and latest[ts_field] > (last_act or ""):
            last_act = latest[ts_field]
    # Next-action hint — deterministic finite-state ladder.
    cycle_status = (row.get("status") or "draft").lower()
    if cycle_status == "completed":
        next_hint = "Closed"
    elif agenda_count == 0:
        next_hint = "Add agenda items"
    elif team_count == 0:
        next_hint = "Add team"
    elif readiness_pct == 0:
        next_hint = "Awaiting contributions"
    elif readiness_pct < 100:
        scored_count = await db.cycle_contributions.count_documents({
            "agenda_id": cycle_id, "scores.readiness": {"$exists": True},
        })
        next_hint = "Score available" if scored_count > 0 else "Ready to score"
    else:
        next_hint = "Ready to compile" if not row.get("compiled_brief_id") else "Ready to close"

    # Blocker 2 (2026-05-25, backlog-b) — multi-path compilation
    # linkage lookup. Pre-backlog-b, the Cycle Page's CompilationStep
    # only knew about a compiled artefact when the user clicked
    # "Produce draft compilation" and received the response payload
    # holding {export_id, file_name}. Cycles compiled in a prior
    # session, restored from seeds, or arriving via the v-pre-Cycle-v2
    # migration showed NO download chips — the UI treated them as
    # uncompiled.
    #
    # The defensive lookup below tries three independent linkage paths
    # in order so the chips render reliably regardless of which path
    # the upstream write took:
    #   1. cycles.compilation_export_id  — populated by seeds + tests.
    #   2. cycles.compiled_brief_id      — legacy field already read
    #      above for `next_hint`.
    #   3. work_studio_exports query     — kind=cycle_board_pack rows
    #      where the source_cycle_id maps back to this cycle.
    # Whichever path resolves first wins; the lookup is short-circuit
    # and reads at most two collections.
    compilation = None
    candidate_export_id = (
        row.get("compilation_export_id")
        or row.get("compiled_brief_id")
    )
    if candidate_export_id:
        export_row = await db.work_studio_exports.find_one(
            {"id": candidate_export_id, "context_id": row["context_id"]},
            {"_id": 0, "id": 1, "kind": 1, "title": 1, "file_name": 1,
             "output_format": 1, "lifecycle_state": 1, "status": 1,
             "structured_content": 1},
        )
        if export_row and (export_row.get("structured_content") or {}).get("sections"):
            compilation = {
                "export_id": export_row["id"],
                "file_name": export_row.get("file_name")
                             or export_row.get("title")
                             or "cycle-compilation",
                "output_format": export_row.get("output_format") or "docx",
                "kind": export_row.get("kind"),
                "lifecycle_state": export_row.get("lifecycle_state"),
                "linkage_path": "cycles.compilation_export_id"
                                if row.get("compilation_export_id")
                                else "cycles.compiled_brief_id",
            }
    if compilation is None:
        # Path 3 — direct work_studio_exports query. Picks up any cycle
        # compilation that wasn't written back to the cycles row but
        # left a tagged work_studio_exports trail (e.g. compile flow
        # crash between insert + cycles.update).
        ws_row = await db.work_studio_exports.find_one(
            {
                "context_id": row["context_id"],
                "kind": "cycle_board_pack",
                "source_cycle_id": cycle_id,
                "structured_content.sections": {"$exists": True, "$ne": []},
            },
            {"_id": 0, "id": 1, "title": 1, "file_name": 1,
             "output_format": 1, "lifecycle_state": 1, "kind": 1},
            sort=[("updated_at", -1)],
        )
        if ws_row:
            compilation = {
                "export_id": ws_row["id"],
                "file_name": ws_row.get("file_name")
                             or ws_row.get("title")
                             or "cycle-compilation",
                "output_format": ws_row.get("output_format") or "docx",
                "kind": ws_row.get("kind"),
                "lifecycle_state": ws_row.get("lifecycle_state"),
                "linkage_path": "work_studio_exports.source_cycle_id",
            }

    return {
        **row,
        "agenda_count": agenda_count,
        "team_count": team_count,
        "contributor_count": team_count,  # legacy alias kept for v2 callers
        "readiness_pct": readiness_pct,
        "readiness_score": readiness,
        "last_activity_at": last_act,
        "next_action_hint": next_hint,
        "compilation": compilation,
    }


# ─────────────────────────────────────────────────────────────────────
# 1. Create
# ─────────────────────────────────────────────────────────────────────
@router.post("/contexts/{context_id}/cycles", status_code=201)
async def create_cycle(
    context_id: str,
    body: CycleCreateIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    cycle_id = str(uuid.uuid4())
    title = body.title.strip()
    now_iso = iso(now())
    row = {
        "id": cycle_id,
        "context_id": context_id,
        "account_id": ctx["account"]["id"],
        "title": title,
        "status": "draft",
        "created_at": now_iso,
        "activated_at": None,
        "closed_at": None,
    }
    await db.cycles.insert_one(row)
    await _persist_agenda_shell(cycle_id, context_id, ctx["account"]["id"], title)
    await write_audit(
        context_id, ctx["account"]["id"],
        "cycle.created", "cycle", cycle_id,
        {"title": title},
    )
    return {
        "id": cycle_id,
        "context_id": context_id,
        "title": title,
        "status": "draft",
        "created_at": now_iso,
        "activated_at": None,
        "closed_at": None,
        "readiness_score": None,
        "agenda_count": 0,
        "contributor_count": 0,
        "redirect_url": f"/app/cycle/{cycle_id}?tab=agenda",
    }


# ─────────────────────────────────────────────────────────────────────
# 2. List (paginated + searchable + sortable)
# ─────────────────────────────────────────────────────────────────────
_SORT_MAP = {
    "recent":  [("created_at", -1)],
    "oldest":  [("created_at", 1)],
    "alpha":   [("title", 1)],
    "status":  None,  # custom — active > draft > completed
}


@router.get("/contexts/{context_id}/cycles")
async def list_cycles(
    context_id: str,
    q: Optional[str] = Query(default=None, max_length=200),
    status: Optional[str] = Query(
        default=None,
        pattern=r"^(all|active|draft|completed)$",
    ),
    sort: str = Query(default="recent", pattern=r"^(recent|oldest|alpha|status)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=60),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Cycle list with ListingShell-shaped pagination envelope.

    Cycle Manager Feel pass (Patch 2 of 4, 2026-02): added `status`
    filter, mirrored Work Studio's `counts_by_status` envelope, and
    extended each row with intel fields for the Cycle Card visual:
    `agenda_count`, `team_count`, `readiness_pct`, `last_activity_at`,
    `next_action_hint`.
    """
    filt: Dict[str, Any] = {"context_id": context_id}
    if q:
        filt["title"] = {"$regex": re.escape(q.strip()), "$options": "i"}

    # Counts pre-status-filter (the filter-tab badges show the full
    # picture, not the post-filter result).
    counts_filt = {"context_id": context_id}
    if q:
        counts_filt["title"] = filt["title"]
    counts_by_status = {
        "all":       await db.cycles.count_documents(counts_filt),
        "active":    await db.cycles.count_documents({**counts_filt, "status": "active"}),
        "draft":     await db.cycles.count_documents({**counts_filt, "status": "draft"}),
        "completed": await db.cycles.count_documents({**counts_filt, "status": "completed"}),
    }

    if status and status != "all":
        filt["status"] = status

    total = await db.cycles.count_documents(filt)

    if sort == "status":
        cur = db.cycles.find(filt, {"_id": 0})
        rows = await cur.to_list(2000)
        order = {"active": 0, "draft": 1, "completed": 2}
        rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        rows.sort(key=lambda r: order.get((r.get("status") or "draft"), 3))
        rows = rows[(page - 1) * page_size : page * page_size]
    else:
        sort_spec = _SORT_MAP[sort]
        cur = db.cycles.find(filt, {"_id": 0}).sort(sort_spec)
        cur = cur.skip((page - 1) * page_size).limit(page_size)
        rows = await cur.to_list(page_size)

    cycles_out: List[Dict[str, Any]] = []
    for r in rows:
        cycles_out.append(await _hydrate_cycle(r))

    return {
        "cycles": cycles_out,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "counts_by_status": counts_by_status,
        "sort": sort,
        "status": status or "all",
        "q": q or "",
    }


# ─────────────────────────────────────────────────────────────────────
# 3. Detail
# ─────────────────────────────────────────────────────────────────────
@router.get("/contexts/{context_id}/cycles/{cycle_id}")
async def get_cycle(
    context_id: str,
    cycle_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    row = await get_cycle_or_404(context_id, cycle_id)
    return await _hydrate_cycle(row)


# ─────────────────────────────────────────────────────────────────────
# 4. Activate (draft → active)
# ─────────────────────────────────────────────────────────────────────
@router.post("/contexts/{context_id}/cycles/{cycle_id}/activate")
async def activate_cycle(
    context_id: str,
    cycle_id: str,
    body: Dict[str, Any] = Body(default_factory=dict),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    row = await get_cycle_or_404(context_id, cycle_id)
    if (row.get("status") or "draft") == "completed":
        raise HTTPException(status_code=409, detail="Completed cycles cannot be re-activated.")
    if (row.get("status") or "draft") == "active":
        return await _hydrate_cycle(row)  # idempotent
    if not (row.get("title") or "").strip():
        raise HTTPException(status_code=400, detail="Cycle title is required to activate.")
    # Require at least one agenda item.
    agenda = await db.cycle_agendas.find_one({"id": cycle_id}, {"_id": 0, "items": 1})
    if not agenda or not (agenda.get("items") or []):
        raise HTTPException(
            status_code=400,
            detail="At least one agenda item is required to activate a cycle.",
        )
    now_iso = iso(now())
    # Patch 10 — `expected_close_at` is optional on activate. Default to
    # now + 30 days when the client doesn't provide one so the Home 2
    # `cycles_closing_this_week` count has a denominator to look at.
    raw_close = (body or {}).get("expected_close_at")
    if raw_close in (None, ""):
        expected_close_at = iso(now() + timedelta(days=30))
    else:
        # Accept either a bare YYYY-MM-DD date or a full ISO timestamp;
        # normalise to ISO so downstream queries stay consistent.
        try:
            from datetime import datetime as _dt
            if len(str(raw_close)) <= 10:
                expected_close_at = iso(_dt.fromisoformat(str(raw_close)))
            else:
                expected_close_at = iso(_dt.fromisoformat(str(raw_close).replace("Z", "+00:00")))
        except Exception:
            raise HTTPException(status_code=400, detail="expected_close_at must be ISO date or datetime.")
    await db.cycles.update_one(
        {"id": cycle_id, "context_id": context_id},
        {"$set": {
            "status": "active",
            "activated_at": now_iso,
            "expected_close_at": expected_close_at,
        }},
    )
    await write_audit(
        context_id, ctx["account"]["id"],
        "cycle.activated", "cycle", cycle_id,
        {"expected_close_at": expected_close_at},
    )
    return await _hydrate_cycle(await get_cycle_or_404(context_id, cycle_id))


# ─────────────────────────────────────────────────────────────────────
# 5. Close (active → completed)
# ─────────────────────────────────────────────────────────────────────
@router.post("/contexts/{context_id}/cycles/{cycle_id}/close")
async def close_cycle(
    context_id: str,
    cycle_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    row = await get_cycle_or_404(context_id, cycle_id)
    if (row.get("status") or "draft") == "completed":
        return await _hydrate_cycle(row)  # idempotent
    if (row.get("status") or "draft") == "draft":
        raise HTTPException(status_code=400, detail="Cannot close a draft cycle. Activate first.")
    now_iso = iso(now())
    readiness = await compute_readiness_score(cycle_id)
    await db.cycles.update_one(
        {"id": cycle_id, "context_id": context_id},
        {"$set": {
            "status": "completed",
            "closed_at": now_iso,
            "final_readiness_score": readiness,
        }},
    )
    await write_audit(
        context_id, ctx["account"]["id"],
        "cycle.closed", "cycle", cycle_id,
        {"final_readiness_score": readiness},
    )
    return await _hydrate_cycle(await get_cycle_or_404(context_id, cycle_id))



# ─────────────────────────────────────────────────────────────────────
# 6. Apply template (Quick Action — Prepare for Main Board)
# ─────────────────────────────────────────────────────────────────────
class ApplyTemplateIn(BaseModel):
    template_key: str = Field(min_length=1, max_length=64)


_MAIN_BOARD_AGENDA_ITEMS = (
    "Strategy review",
    "Financial performance",
    "Risk and compliance",
    "People and culture",
    "ExCo report",
    "Forward look",
)


@router.post("/contexts/{context_id}/cycles/{cycle_id}/apply-template")
async def apply_template(
    context_id: str,
    cycle_id: str,
    body: ApplyTemplateIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Seed a draft cycle with a structured template.

    Quick Action "Prepare for Main Board" — `template_key="main_board"`:
      • Seeds 6 agenda items (in canonical order).
      • Seeds the team from the workspace `team_catalogue`, with empty
        role / contribution_description / agenda_assignments.
      • Idempotent — refuses (409, `cycle_not_empty`) if the cycle
        already has agenda items.
    """
    cycle = await get_cycle_or_404(context_id, cycle_id)
    if (cycle.get("status") or "draft") == "completed":
        raise HTTPException(status_code=409, detail="Cycle is closed.")

    if body.template_key != "main_board":
        raise HTTPException(
            status_code=400,
            detail=f"Unknown template_key {body.template_key!r}.",
        )

    # Idempotency guard — refuse if agenda already has items.
    agenda = await db.cycle_agendas.find_one({"id": cycle_id}, {"_id": 0, "items": 1})
    if agenda and (agenda.get("items") or []):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "cycle_not_empty",
                "message": (
                    "This cycle already has agenda items. Apply a template "
                    "to an empty draft cycle instead."
                ),
            },
        )

    # Seed agenda items.
    now_iso = iso(now())
    items = [
        {"id": str(uuid.uuid4()), "label": lbl, "created_at": now_iso}
        for lbl in _MAIN_BOARD_AGENDA_ITEMS
    ]
    await db.cycle_agendas.update_one(
        {"id": cycle_id, "context_id": context_id},
        {"$set": {
            "items": items,
            "updated_at": now_iso,
        }},
        upsert=False,
    )

    # Seed team from the (account-scoped) catalogue, skipping any
    # member already present in this cycle.
    catalogue = await db.team_catalogue.find(
        {"context_id": context_id, "deleted_at": None},
        {"_id": 0, "name": 1, "email": 1},
    ).to_list(500)
    existing_emails = await db.cycle_team.distinct(
        "email", {"agenda_id": cycle_id, "status": "active"},
    )
    existing_lc = {(e or "").strip().lower() for e in existing_emails}
    team_inserted = 0
    for m in catalogue:
        email_lc = (m.get("email") or "").strip().lower()
        if not email_lc or email_lc in existing_lc:
            continue
        await db.cycle_team.insert_one({
            "id": str(uuid.uuid4()),
            "context_id": context_id,
            "agenda_id": cycle_id,
            "cycle_id": cycle_id,
            "name": m.get("name") or "",
            "email": m.get("email") or "",
            "role": None,
            "contribution_description": "—",
            "owns_item_ids": [],
            "status": "active",
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        team_inserted += 1

    await write_audit(
        context_id, ctx["account"]["id"],
        "cycle.template_applied", "cycle", cycle_id,
        {
            "template_key": body.template_key,
            "agenda_items_added": len(items),
            "team_members_added": team_inserted,
        },
    )

    return {
        "cycle_id": cycle_id,
        "template_key": body.template_key,
        "agenda_items_added": len(items),
        "team_members_added": team_inserted,
        "cycle": await _hydrate_cycle(
            await get_cycle_or_404(context_id, cycle_id)
        ),
    }
