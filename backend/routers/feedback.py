"""Phase R.4 (2026-05-27) — In-app feedback widget endpoint.

Single endpoint that the fixed-position lower-right `<FeedbackWidget>`
React component POSTs to from any authenticated app surface.

  POST /api/feedback
       body: { text: string, tag: "Broken" | "Wrong" | "Great", surface_path: string }
       response: { feedback_id, dispatched: bool }
       422: tag not in locked taxonomy OR auto-thanks body still has `[FOUNDER:` placeholders.

Side effects:
  1. Writes a `feedback.submitted` row to `db.feature_events`
     (R.3 pipe) with payload `{text, tag, surface_path}`.
  2. Queues the auto-thanks SendGrid send via BackgroundTasks.
     Default `?send=1` (real send); `?send=0` for dev/test or when
     the founder hasn't filled in the placeholders.
  3. NEVER raises uncaught — auto-thanks failures emit
     `feedback_thanks_failed` logs the admin can review + manually
     re-send.

Auth: any authenticated account. The endpoint is intentionally
NOT superadmin-gated — founder cohort users + admins all submit
feedback through the same path.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import db, get_current_account
from services.cohort.feedback_widget import (
    FEEDBACK_TAGS,
    build_thanks_html,
    send_thanks_email_async,
)
from services.cohort.welcome_email import assert_no_founder_placeholder
from services.cohort.feature_events import (
    emit_feature_event, FEEDBACK_SUBMITTED,
)


log = logging.getLogger("akki.cohort.feedback")
router = APIRouter(prefix="/api/feedback", tags=["feedback"])


# ─────────────────────────────────────────────────────────────────────
# Body schema
# ─────────────────────────────────────────────────────────────────────
class FeedbackIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    tag: Literal["Broken", "Wrong", "Great"]
    surface_path: str = Field(..., min_length=1, max_length=200)


# ─────────────────────────────────────────────────────────────────────
# POST /api/feedback — receive a feedback submission
# ─────────────────────────────────────────────────────────────────────
@router.post("", status_code=200)
async def submit_feedback(
    body: FeedbackIn,
    background_tasks: BackgroundTasks,
    send: int = Query(default=1, ge=0, le=1),
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    feedback_id = uuid.uuid4().hex

    # Phase R.4 (2026-05-27) — defence-in-depth tag check (pydantic
    # `Literal` already enforces; this catches any future widget bug
    # that smuggles a tag through).
    if body.tag not in FEEDBACK_TAGS:
        raise HTTPException(
            status_code=422,
            detail={"code": "feedback_tag_unknown",
                    "message": f"Tag must be one of {FEEDBACK_TAGS}; got {body.tag!r}"},
        )

    # 1) Emit the feature_event row (R.3 pipe). Best-effort; never raises.
    await emit_feature_event(
        event_type=FEEDBACK_SUBMITTED,
        account_id=account["id"],
        cohort_tag=account.get("cohort_tag"),
        payload={
            "feedback_id":  feedback_id,
            "tag":          body.tag,
            "text":         body.text[:4000],
            "surface_path": body.surface_path,
        },
    )

    # 2) Optionally send the auto-thanks email (default: yes).
    #
    # R.4 semantic note: unlike R.2 (where the [FOUNDER:] guard
    # blocks invite creation), in R.4 we ALWAYS capture the feedback
    # — the founder may not have filled in the thanks copy yet, but
    # we never want to lose a user's note. If the guard fires, we log
    # `feedback_thanks_blocked_by_placeholder` + return 200 with
    # `dispatched_thanks=false` + `block_reason` so the widget can
    # show a friendlier message.
    block_reason: Optional[str] = None
    if send == 1:
        rendered = build_thanks_html({
            "first_name":   account.get("first_name") or "there",
            "tag":          body.tag,
            "text":         body.text,
            "surface_path": body.surface_path,
        })
        try:
            assert_no_founder_placeholder(rendered)
        except HTTPException as exc:
            # Guard fired — log + skip the send + still return 200.
            block_reason = "founder_placeholder_present"
            log.info("feedback_thanks_blocked_by_placeholder: %s", {
                "feedback_id":            feedback_id,
                "to":                     account["email"],
                "tag":                    body.tag,
                "placeholders_remaining": (
                    exc.detail.get("founder_placeholders_remaining")
                    if isinstance(exc.detail, dict) else None
                ),
            })
        else:
            background_tasks.add_task(
                send_thanks_email_async,
                rendered=rendered,
                to_email=account["email"],
                feedback_id=feedback_id,
                tag=body.tag,
            )
            log.info("feedback_thanks_dispatched: %s", {
                "feedback_id": feedback_id, "to": account["email"],
                "tag": body.tag,
            })
    else:
        log.info("feedback_thanks_skipped: %s", {
            "feedback_id": feedback_id, "to": account["email"],
            "tag": body.tag,
        })

    dispatched = (send == 1 and block_reason is None)

    return {
        "feedback_id":         feedback_id,
        "tag":                 body.tag,
        "dispatched_thanks":   dispatched,
        "block_reason":        block_reason,
        "received_at":         datetime.now(timezone.utc).isoformat(),
    }
