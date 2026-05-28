"""Phase Y (2026-05-27) — First-login onboarding briefs.

Surfaces a 6-slide modal on first authenticated `/app/*` load per
account. Each slide carries founder-fillable copy slots via the
existing R.5.b copy-override pattern.

Endpoints:
  GET  /api/me/onboarding-briefs                 — { shown_at, slides[] }
  POST /api/me/onboarding-briefs/complete        — { ok: True, shown_at: <ISO> }

Locked copy slots (each slot can be overridden via the founder copy
editor; defaults ship inline):

  Slide 1 — Welcome.        slot: `onboarding_slide_welcome`
  Slide 2 — Surfaces.       slot: `onboarding_slide_surfaces`
  Slide 3 — How to use.     slot: `onboarding_slide_how_to_use`
  Slide 4 — Tell us.        slot: `onboarding_slide_tell_us`
  Slide 5 — Data safety.    slot: `onboarding_slide_safety`
  Slide 6 — Get started.    slot: `onboarding_slide_cta`

R.4 semantic-divergence rule: founder `[FOUNDER:` placeholders do NOT
block the modal from rendering. Defaults ship with sensible copy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from core import db, get_current_account


router = APIRouter(prefix="/api/me")


# ─────────────────────────────────────────────────────────────────────
# Locked default copy (sober, calm, executive — matches the Claude
# reference voice). Each slide is rendered as title + body. The body
# can contain a single newline-separated bullet block.
# ─────────────────────────────────────────────────────────────────────
ONBOARDING_SLIDES_DEFAULT = [
    {
        "id": "welcome",
        "slot": "onboarding_slide_welcome",
        "title": "Welcome to Akki.",
        "body": (
            "A private workspace for your executive decisions. "
            "Built for boardroom-grade work that stays yours."
        ),
    },
    {
        "id": "surfaces",
        "slot": "onboarding_slide_surfaces",
        "title": "What's inside.",
        "body": (
            "Home — the day's signals.\n"
            "Solva — structured analysis sessions.\n"
            "Work Studio — compile board packs, minutes, decks.\n"
            "Task Manager — cycles, readiness, what blocks the next pack.\n"
            "Monitor — strategic goals, performance & probability.\n"
            "Pulse — signals worth your attention.\n"
            "Chat — your private AI workspace.\n"
            "Learn — a library curated for the board table."
        ),
    },
    {
        "id": "how_to_use",
        "slot": "onboarding_slide_how_to_use",
        "title": "How it works.",
        "body": (
            "Pick a company context (or stay in General mode). "
            "Drop the documents that matter. Ask, plan, compile. "
            "Akki holds the context so you don't have to re-explain."
        ),
    },
    {
        "id": "tell_us",
        "slot": "onboarding_slide_tell_us",
        "title": "We're listening.",
        "body": (
            "If something feels off — wrong, slow, or missing — use "
            "the feedback widget in the lower-right. The team reads "
            "every note and tunes accordingly."
        ),
    },
    {
        "id": "safety",
        "slot": "onboarding_slide_safety",
        "title": "Your data stays yours.",
        "body": (
            "Synisense Shield de-identifies sensitive entities before "
            "they reach the model layer. Every answer is grounded in "
            "your evidence — no hallucinated citations. No third-party "
            "trackers; no analytics on your content."
        ),
    },
    {
        "id": "cta",
        "slot": "onboarding_slide_cta",
        "title": "Ready when you are.",
        "body": (
            "Take a minute to explore. The work that matters is the "
            "next decision, not the tour."
        ),
    },
]


def _serialize_account(row: Dict[str, Any]) -> Dict[str, Any]:
    """Strip MongoDB internals + return the relevant onboarding fields."""
    return {
        "shown_at": row.get("onboarding_briefs_shown_at"),
    }


async def _build_slides(account_id: str) -> List[Dict[str, Any]]:
    """Return the locked default slide list.

    Phase Y v1 ships with hard-coded defaults. Founder copy editing
    of slide bodies is queued as R.5.b.5 (extend `SLOT_FIELDS` with
    onboarding_slide_* keys + paired CohortCopyEditor surface) so
    each slide body can be founder-overridden via the existing
    `cohort_copy_overrides` collection without changing the modal
    consumer code.
    """
    return [dict(s) for s in ONBOARDING_SLIDES_DEFAULT]


@router.get("/onboarding-briefs")
async def get_onboarding_briefs(
    request: Request,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Return the onboarding-briefs state + locked slide list.

    The modal consumes:
      - `shown_at: Optional[str]` — ISO timestamp; null means SHOW THE MODAL.
      - `slides: List[Slide]` — 6 slides with founder overrides applied.
    """
    return {
        **_serialize_account(current),
        "slides": await _build_slides(current["id"]),
    }


@router.post("/onboarding-briefs/complete")
async def complete_onboarding_briefs(
    request: Request,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Mark the briefs as shown so the modal doesn't re-surface.

    Idempotent: re-calling stamps a fresh `shown_at` but the modal
    consumes the FIRST `shown_at !== null` check and never re-renders
    in the same session.
    """
    now = datetime.now(timezone.utc).isoformat()
    res = await db.accounts.update_one(
        {"id": current["id"]},
        {"$set": {"onboarding_briefs_shown_at": now}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Account not found.")
    # Best-effort feature event for funnel tracking. Mirrors the R.3
    # `feature_events` pattern. Silent on failure.
    try:
        await db.feature_events.insert_one({
            "account_id": current["id"],
            "event_type": "onboarding.briefs_completed",
            "occurred_at": now,
        })
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "shown_at": now}
