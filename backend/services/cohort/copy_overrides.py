"""Phase R.5.b (2026-05-27) — Founder copy overrides.

Centralised storage + render for the 5 founder-fillable copy slots
shipped across R.2 / R.4 / R.5.a. The R.5.b editor page lets the
founder edit these in-app; this module is the persistence + render
layer that the existing welcome_email / feedback_widget /
EarlyAccessOptIn consumers consult.

Locked slot taxonomy (do NOT rename — copy consumers reference by id):

  welcome_email        — R.2 welcome email (subject + html + text)
  feedback_thanks      — R.4 auto-thanks email (subject + html + text)
  day_16_banner        — soft-warning in-app banner (heading + body)
  early_access_opt_in  — hard-cutoff page copy (heading + body + thanks + signoff)
  special_ask          — day-14 special-ask in-app modal + email
                          (heading + body for both surfaces)

Each slot persists into `db.cohort_copy_overrides` as a single row
keyed by `slot`. The schema is open — different slots have different
fields (e.g. email slots have `subject`, banner slots have `heading`).
The frontend editor introspects via `SLOT_FIELDS` so adding a field
later is a single dict update.

Save guard: the slot-save endpoint refuses to persist if any
`[FOUNDER:` literal still appears in any text-bearing field. This is
the LOCKED institutional pattern from R.2 (same prefix, same 422
contract). The R.4 semantic divergence (always-capture-200) does NOT
apply here — editor saves are explicit founder actions, not user
data, so hard 422s are correct.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core import db
from services.cohort.welcome_email import FOUNDER_PLACEHOLDER_PREFIX


log = logging.getLogger("akki.cohort.copy_overrides")


# ─────────────────────────────────────────────────────────────────────
# Locked slot taxonomy — 5 slots, each with a fixed set of text fields.
# Adding a slot requires a new R sub-phase dispatch.
# ─────────────────────────────────────────────────────────────────────
SLOT_FIELDS: Dict[str, List[str]] = {
    "welcome_email":       ["subject", "html", "text"],
    "feedback_thanks":     ["subject", "html", "text"],
    "day_16_banner":       ["heading", "body"],
    "early_access_opt_in": ["heading", "body", "thanks_body", "signoff"],
    "special_ask":         ["modal_heading", "modal_body",
                            "email_subject", "email_body"],
}

KNOWN_SLOTS = frozenset(SLOT_FIELDS.keys())


def slot_field_list(slot: str) -> List[str]:
    """Public accessor — used by the editor page + tests."""
    return list(SLOT_FIELDS.get(slot, []))


# ─────────────────────────────────────────────────────────────────────
# Get-with-default — returns the override row (or None) for a slot.
# Consumers (welcome_email.py, feedback_widget.py, EarlyAccessOptIn)
# call this AFTER building their default templates, then overlay any
# non-empty override fields.
# ─────────────────────────────────────────────────────────────────────
async def get_slot_override(slot: str) -> Optional[Dict[str, Any]]:
    if slot not in KNOWN_SLOTS:
        return None
    row = await db.cohort_copy_overrides.find_one(
        {"slot": slot}, {"_id": 0},
    )
    return row


def overlay_slot(
    *,
    default_payload: Dict[str, str],
    override_row: Optional[Dict[str, Any]],
    slot: str,
) -> Dict[str, str]:
    """Overlay non-empty override fields onto a default payload.

    Returns a NEW dict — the input default is not mutated. If
    `override_row` is None OR the override field is None/empty, the
    default field stays.
    """
    out = dict(default_payload)
    if not override_row:
        return out
    for field in SLOT_FIELDS.get(slot, []):
        val = override_row.get(field)
        if isinstance(val, str) and val.strip():
            out[field] = val
    return out


# ─────────────────────────────────────────────────────────────────────
# Save guard — refuses to persist when [FOUNDER: still present
# ─────────────────────────────────────────────────────────────────────
def assert_save_clean(*, slot: str, fields: Dict[str, str]) -> None:
    """Raise HTTPException(422) if any text-bearing field still
    contains the locked `[FOUNDER:` placeholder prefix. The error
    payload identifies WHICH fields are dirty so the editor can
    flag them inline."""
    dirty: List[Dict[str, Any]] = []
    for field in SLOT_FIELDS.get(slot, []):
        val = fields.get(field)
        if not isinstance(val, str):
            continue
        if FOUNDER_PLACEHOLDER_PREFIX in val:
            # Capture a short window for the editor to flag inline.
            i = val.find(FOUNDER_PLACEHOLDER_PREFIX)
            dirty.append({
                "field":  field,
                "window": val[i:i + 80].replace("\n", " "),
            })
    if dirty:
        raise HTTPException(
            status_code=422,
            detail={
                "code":  "founder_placeholder_present",
                "slot":  slot,
                "dirty_fields": dirty,
                "message": (
                    "Cannot save while `[FOUNDER:` placeholders are still "
                    "in the copy. Edit the highlighted fields and try again."
                ),
            },
        )


# ─────────────────────────────────────────────────────────────────────
# Save (upsert) — persists the row + stamps updated metadata
# ─────────────────────────────────────────────────────────────────────
async def save_slot_override(
    *,
    slot: str,
    fields: Dict[str, str],
    updated_by: str,
) -> Dict[str, Any]:
    if slot not in KNOWN_SLOTS:
        raise HTTPException(status_code=400, detail=f"Unknown slot: {slot!r}")
    assert_save_clean(slot=slot, fields=fields)
    now_iso = datetime.now(timezone.utc).isoformat()
    update_set = {
        "slot":       slot,
        "updated_at": now_iso,
        "updated_by": updated_by,
    }
    for field in SLOT_FIELDS[slot]:
        update_set[field] = (fields.get(field) or "").strip() or None
    await db.cohort_copy_overrides.update_one(
        {"slot": slot},
        {"$set": update_set, "$setOnInsert": {"created_at": now_iso}},
        upsert=True,
    )
    return {
        "slot":       slot,
        "updated_at": now_iso,
        "fields":     {k: update_set.get(k) for k in SLOT_FIELDS[slot]},
    }


async def list_all_slots() -> Dict[str, Any]:
    """Read every override row. Used by the editor page on load."""
    rows = await db.cohort_copy_overrides.find(
        {}, {"_id": 0},
    ).to_list(length=64)
    by_slot = {r["slot"]: r for r in rows if r.get("slot") in KNOWN_SLOTS}
    out = {}
    for slot in KNOWN_SLOTS:
        row = by_slot.get(slot)
        out[slot] = {
            "fields":      slot_field_list(slot),
            "values":      {f: (row or {}).get(f) for f in SLOT_FIELDS[slot]},
            "updated_at":  (row or {}).get("updated_at"),
            "updated_by":  (row or {}).get("updated_by"),
        }
    return out
