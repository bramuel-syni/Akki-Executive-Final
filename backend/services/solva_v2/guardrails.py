"""Solva v2 — Phase 15.3 guardrails: refusal ladder + therapy redirect.

Pure, deterministic policy module. Inputs: a session document, a turn id,
the refusal-engine output. Outputs: a `GuardrailDecision` describing
what the orchestrator must do for this turn.

Policies:
  * Soft block: first jailbreak_attempt classification on a session.
    Solva reframes (locked sentence) and continues; layer does NOT advance.
    `jailbreak_soft_count` increments on the session document.
  * Hard block: second jailbreak_attempt OR first jailbreak_attempt that
    also matches a system-prompt extraction marker. Session flips to
    status='blocked_hard' (terminal). Subsequent POST /turn returns 409.
  * Therapy redirect: out_of_scope AND distress_flag=true. Solva returns
    one locked sentence + a Learn link. Session stays active; user can pivot.

Invariants:
  * Guardrail decisions never call an LLM.
  * Decisions are produced from the refusal output + session state only.
  * The orchestrator persists the guardrail audit entry (engine="guardrail")
    under the active layer so it shows up in the reasoning log.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

ENGINE = "guardrail"
ENGINE_VERSION = "guardrail@1.0"

# Locked copy. Do not edit without product sign-off (Phase 15.3 decisions #5/#6).
SOFT_BLOCK_MESSAGE = (
    "That request would push Solva outside its governance remit — let's reframe."
)
HARD_BLOCK_MESSAGE_TMPL = (
    "Solva can't take this turn. Classification: {category}. Guidance: /app/learn/{learn_id}."
)
THERAPY_REDIRECT_MESSAGE = (
    "Solva is a board-level decision tool and isn't the right place for this. "
    "If it helps, this short piece on board-room stress may offer perspective: "
    "/app/learn/board-room-stress."
)

LEARN_ID_JAILBREAK = "guardrails-and-shield"
LEARN_ID_DISTRESS = "board-room-stress"


@dataclass
class GuardrailDecision:
    action: str                        # "continue" | "soft_block" | "hard_block" | "therapy_redirect"
    user_visible_message: str          # the Solva turn body for the user
    audit_output: Dict[str, Any]       # audit_entry["output"] payload
    new_status: Optional[str] = None   # 'blocked_hard' to flip session terminal
    increment_soft_count: bool = False
    learn_link: Optional[str] = None


def evaluate(
    *,
    session: Dict[str, Any],
    refusal_output: Dict[str, Any],
) -> GuardrailDecision:
    """Decide what the orchestrator must do for this turn.

    `session` MUST be the post-user-turn snapshot (the user turn already
    appended; the refusal audit entry will be appended by the orchestrator).
    """
    category = (refusal_output or {}).get("category") or "clean"
    confidence = float((refusal_output or {}).get("confidence") or 0.0)
    distress = bool((refusal_output or {}).get("distress_flag") or False)
    extraction = (refusal_output or {}).get("extraction_marker_hit")
    soft_count = int(session.get("jailbreak_soft_count") or 0)

    # Therapy redirect — out_of_scope + personal distress. NOT a block.
    if category == "out_of_scope" and distress:
        return GuardrailDecision(
            action="therapy_redirect",
            user_visible_message=THERAPY_REDIRECT_MESSAGE,
            learn_link=f"/app/learn/{LEARN_ID_DISTRESS}",
            audit_output={
                "guardrail": "therapy_redirect",
                "refusal_category": category,
                "refusal_confidence": confidence,
                "distress_flag": True,
                "session_remained_active": True,
                "learn_id": LEARN_ID_DISTRESS,
            },
        )

    # Jailbreak attempts — apply ladder.
    if category == "jailbreak_attempt":
        # Hard block: second offence OR first offence with extraction marker.
        is_hard = (soft_count >= 1) or bool(extraction)
        if is_hard:
            msg = HARD_BLOCK_MESSAGE_TMPL.format(
                category=category, learn_id=LEARN_ID_JAILBREAK,
            )
            return GuardrailDecision(
                action="hard_block",
                user_visible_message=msg,
                new_status="blocked_hard",
                learn_link=f"/app/learn/{LEARN_ID_JAILBREAK}",
                audit_output={
                    "guardrail": "hard_block",
                    "refusal_category": category,
                    "refusal_confidence": confidence,
                    "soft_count_before": soft_count,
                    "extraction_marker_hit": extraction,
                    "session_terminal": True,
                    "learn_id": LEARN_ID_JAILBREAK,
                },
            )
        # Soft block.
        return GuardrailDecision(
            action="soft_block",
            user_visible_message=SOFT_BLOCK_MESSAGE,
            increment_soft_count=True,
            audit_output={
                "guardrail": "soft_block",
                "refusal_category": category,
                "refusal_confidence": confidence,
                "soft_count_before": soft_count,
                "soft_count_after": soft_count + 1,
                "session_remained_active": True,
            },
        )

    return GuardrailDecision(
        action="continue",
        user_visible_message="",
        audit_output={
            "guardrail": "continue",
            "refusal_category": category,
            "refusal_confidence": confidence,
            "distress_flag": distress,
        },
    )


__all__ = [
    "ENGINE", "ENGINE_VERSION",
    "SOFT_BLOCK_MESSAGE", "HARD_BLOCK_MESSAGE_TMPL", "THERAPY_REDIRECT_MESSAGE",
    "LEARN_ID_JAILBREAK", "LEARN_ID_DISTRESS",
    "GuardrailDecision", "evaluate",
]
