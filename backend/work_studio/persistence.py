"""
Phase C.2 — Brief persistence layer.

C.1 (`brief.py`) is the canonical structured form. C.2 persists that
structure into Mongo so it can be enhanced (`enhance.py`) and re-
exported by the C.1 generators without re-querying the source Solva
session.

Two collections (registered as indexes in `server.py:on_startup`):

  db.work_studio_briefs              — one row per (account, source).
                                       Holds metadata + active_revision_id.
  db.work_studio_brief_revisions     — many rows per brief. Each row
                                       carries a snapshot of the full
                                       Brief dict + the instruction +
                                       parent_revision_id + validation.

The revision chain forms a tree; `parent_revision_id=None` is the
original (revision_0). `active_revision_id` on the parent points at the
revision that is "current" — used by C.1 export when no explicit
`revision_id` is passed.

A brief_id is a deterministic UUIDv5 of (account_id, source_type,
source_id) so the same Solva session yields the same brief_id across
calls. This makes idempotent persistence trivial: two concurrent C.1
exports of the same session converge on the same brief.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .brief import Brief, BriefSection, BriefTable

# Stable namespace for brief_id derivation. Generated once; baked in.
_BRIEF_NAMESPACE = uuid.UUID("8c5d2f4e-9a01-4f23-9b18-7a3c2e6d1a90")


# ---------------------------------------------------------------------------
# Brief ↔ dict shims (kept here so brief.py stays untouched)
# ---------------------------------------------------------------------------
def slugify(text: str, *, fallback: str = "section") -> str:
    """Lower-case alnum-only slug, max 40 chars. Used for stable section_ids."""
    if not text:
        return fallback
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (s[:40] or fallback)


def brief_to_dict(brief: Brief) -> Dict[str, Any]:
    """Serialise a Brief to a dict with stable section_ids assigned.

    section_id = slug(section.title) + numeric suffix when titles collide.
    The first occurrence keeps the bare slug; subsequent collisions get
    `-2`, `-3`, … so the IDs are stable across enhances that don't
    rename sections."""
    d = asdict(brief)
    seen: Dict[str, int] = {}
    for sec in d.get("sections") or []:
        base = slugify(sec.get("title") or "section")
        seen[base] = seen.get(base, 0) + 1
        sec["section_id"] = base if seen[base] == 1 else f"{base}-{seen[base]}"
    return d


def dict_to_brief(d: Dict[str, Any]) -> Brief:
    """Inverse of `brief_to_dict`. Drops `section_id` keys (the dataclass
    doesn't carry them)."""
    sections: List[BriefSection] = []
    for sec in d.get("sections") or []:
        tables = [BriefTable(**t) for t in (sec.get("tables") or [])]
        sections.append(BriefSection(
            title=sec.get("title") or "",
            kicker=sec.get("kicker"),
            body_paragraphs=list(sec.get("body_paragraphs") or []),
            bullets=list(sec.get("bullets") or []),
            tables=tables,
        ))
    return Brief(
        title=d.get("title") or "",
        subtitle=d.get("subtitle") or "",
        company_label=d.get("company_label") or "Akki",
        document_type=d.get("document_type") or "Board Briefing",
        programme=d.get("programme"),
        version=d.get("version") or "v1.0",
        date_text=d.get("date_text") or "",
        host_org_line=d.get("host_org_line"),
        audience=d.get("audience"),
        framework_spine=d.get("framework_spine"),
        cover_lead_paragraph=d.get("cover_lead_paragraph"),
        sections=sections,
        closing_recap=d.get("closing_recap"),
        closing_brand_line=d.get("closing_brand_line"),
        source_id=d.get("source_id") or "",
        source_type=d.get("source_type") or "",
        depth=d.get("depth") or "board_summary",
        fidelity=d.get("fidelity") or "high",
    )


# ---------------------------------------------------------------------------
# IDs
# ---------------------------------------------------------------------------
def compute_brief_id(*, account_id: str, source_type: str, source_id: str) -> str:
    """Deterministic UUIDv5 over (account, source_type, source_id).

    Same source → same brief_id, idempotently. Two concurrent C.1
    exports of the same Solva session converge on the same row.
    """
    name = f"{account_id}|{source_type}|{source_id}"
    return str(uuid.uuid5(_BRIEF_NAMESPACE, name))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Mongo helpers
# ---------------------------------------------------------------------------
async def ensure_brief_persisted(
    db, *,
    brief: Brief,
    account_id: str,
    context_id: Optional[str],
    source_type: str,
    source_id: str,
) -> Dict[str, Any]:
    """Upsert the brief parent row + revision_0 if absent. Idempotent.

    Returns the parent doc (dict, _id stripped) with `active_revision_id`
    populated. If the brief already exists, returns it as-is — the
    snapshot is NOT overwritten (C.1's source of truth is the original
    Solva session; once persisted, enhances are the only mutation
    path).
    """
    bid = compute_brief_id(
        account_id=account_id, source_type=source_type, source_id=source_id,
    )
    existing = await db.work_studio_briefs.find_one({"id": bid}, {"_id": 0})
    if existing:
        return existing

    revision_0_id = str(uuid.uuid4())
    snapshot = brief_to_dict(brief)
    now = _now_iso()

    revision_0 = {
        "id": revision_0_id,
        "brief_id": bid,
        "account_id": account_id,
        "context_id": context_id,
        "parent_revision_id": None,
        "instruction": "(original — built from source)",
        "scope": "whole_brief",
        "snapshot": snapshot,
        "diff": [],          # no parent → no diff
        "claims_changed": 0,
        "claims_added_without_citation": 0,
        "validation": {
            "verdict": "validated",
            "reason": "Original revision; no enhance applied.",
            "validator_provider": "n/a",
            "validator_model": "n/a",
        },
        "llm_audit": {"mode": "no-llm", "model": "n/a", "tier": "n/a"},
        "created_at": now,
    }
    parent = {
        "id": bid,
        "account_id": account_id,
        "context_id": context_id,
        "source_type": source_type,
        "source_id": source_id,
        "title": brief.title,
        "subtitle": brief.subtitle,
        "company_label": brief.company_label,
        "document_type": brief.document_type,
        "programme": brief.programme,
        "active_revision_id": revision_0_id,
        "revision_count": 1,
        "created_at": now,
        "updated_at": now,
    }
    # Race-safe insert: on duplicate (concurrent ensure), the loser's
    # insert is silently dropped and we re-read the winning row. The
    # unique index on `id` makes this collision-safe at the DB level.
    try:
        await db.work_studio_brief_revisions.insert_one(revision_0)
        await db.work_studio_briefs.insert_one(parent)
    except Exception:
        # The most likely cause is a concurrent ensure_brief_persisted
        # call that already inserted. Re-read.
        existing = await db.work_studio_briefs.find_one({"id": bid}, {"_id": 0})
        if existing:
            return existing
        raise
    return parent


async def get_brief(db, brief_id: str, account_id: str) -> Optional[Dict[str, Any]]:
    return await db.work_studio_briefs.find_one(
        {"id": brief_id, "account_id": account_id}, {"_id": 0},
    )


async def get_revision(
    db, *, brief_id: str, revision_id: str, account_id: str,
) -> Optional[Dict[str, Any]]:
    return await db.work_studio_brief_revisions.find_one(
        {"id": revision_id, "brief_id": brief_id, "account_id": account_id},
        {"_id": 0},
    )


async def get_active_revision(
    db, *, brief_id: str, account_id: str,
) -> Optional[Dict[str, Any]]:
    parent = await get_brief(db, brief_id, account_id)
    if not parent:
        return None
    return await get_revision(
        db, brief_id=brief_id,
        revision_id=parent["active_revision_id"],
        account_id=account_id,
    )


async def list_revisions(
    db, *, brief_id: str, account_id: str,
) -> List[Dict[str, Any]]:
    cursor = db.work_studio_brief_revisions.find(
        {"brief_id": brief_id, "account_id": account_id},
        {"_id": 0, "snapshot": 0},   # snapshot is fat; omit from list view
    ).sort("created_at", 1)
    return await cursor.to_list(length=500)


async def insert_revision(
    db, *,
    brief_id: str, account_id: str, context_id: Optional[str],
    parent_revision_id: str,
    instruction: str, scope: str,
    snapshot: Dict[str, Any],
    diff: List[Dict[str, Any]],
    claims_changed: int,
    claims_added_without_citation: int,
    validation: Dict[str, Any],
    llm_audit: Dict[str, Any],
) -> Dict[str, Any]:
    rid = str(uuid.uuid4())
    now = _now_iso()
    doc = {
        "id": rid,
        "brief_id": brief_id,
        "account_id": account_id,
        "context_id": context_id,
        "parent_revision_id": parent_revision_id,
        "instruction": instruction,
        "scope": scope,
        "snapshot": snapshot,
        "diff": diff,
        "claims_changed": claims_changed,
        "claims_added_without_citation": claims_added_without_citation,
        "validation": validation,
        "llm_audit": llm_audit,
        "created_at": now,
    }
    await db.work_studio_brief_revisions.insert_one(doc)
    # Bump revision_count on the parent.
    await db.work_studio_briefs.update_one(
        {"id": brief_id, "account_id": account_id},
        {"$set": {"updated_at": now}, "$inc": {"revision_count": 1}},
    )
    return doc


async def set_active_revision(
    db, *, brief_id: str, revision_id: str, account_id: str,
) -> bool:
    """Atomic: only set active when the revision exists and was NOT
    refused by the validator. Returns True on success, False otherwise.
    """
    rev = await get_revision(
        db, brief_id=brief_id, revision_id=revision_id, account_id=account_id,
    )
    if not rev:
        return False
    if (rev.get("validation") or {}).get("verdict") == "refused":
        return False
    await db.work_studio_briefs.update_one(
        {"id": brief_id, "account_id": account_id},
        {"$set": {
            "active_revision_id": revision_id,
            "updated_at": _now_iso(),
        }},
    )
    return True
