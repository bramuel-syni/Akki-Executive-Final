"""Phase ZZ.2.x (2026-02 fork-resume v2) — deterministic chat fixtures.

ONE source of truth for the five canned streaming responses Playwright
exercises in `tests/zz2_x_playwright.py`. Each fixture emits a tiny
SSE script: `start` → `delta` chunks → `phase: complete` → terminal
`message` event carrying the canned `zz2_governance` payload.

Fixtures are gated by `AKKI_CHAT_FIXTURES_ENABLED=1` + admin role at
the caller side (chat.py), so this module is harmless if accidentally
imported in production.
"""
from __future__ import annotations
import json
import uuid

FIXTURES = {
    "unsourced_number": {
        "text": "Revenue growth is on track at 23% YoY.",
        "gov": {"ok": False, "numeric_claims_total": 1, "numeric_claims_unsourced": 1,
                "confidence_named": False, "bias_flags": [], "notes": ["numeric_claim_without_source"],
                "recommendation_request": False, "escalate_to_solva": False},
    },
    "bias_anchoring": {
        "text": "Anchoring risk on the Q4 figure — [anchoring · Q4 number] — the comparison isn't like-for-like.",
        "gov": {"ok": True, "numeric_claims_total": 0, "numeric_claims_unsourced": 0,
                "confidence_named": False, "bias_flags": ["anchoring · Q4 number"], "notes": [],
                "recommendation_request": False, "escalate_to_solva": False},
    },
    "recommendation_with_counter": {
        "text": "Counter-case first: the cohort sample is thin and the comparable transactions are stale. With that caveat, medium confidence — proceed.",
        "gov": {"ok": True, "numeric_claims_total": 0, "numeric_claims_unsourced": 0,
                "confidence_named": True, "bias_flags": [], "notes": [],
                "recommendation_request": True, "escalate_to_solva": False},
    },
    "escalation_trigger": {
        "text": "Medium confidence on direction; I would not sign off without a fuller diagnostic.",
        "gov": {"ok": True, "numeric_claims_total": 0, "numeric_claims_unsourced": 0,
                "confidence_named": True, "bias_flags": [], "notes": [],
                "recommendation_request": True, "escalate_to_solva": True},
    },
    "clean_response": {
        "text": "Acknowledged. Nothing further from me on this thread.",
        "gov": {"ok": True, "numeric_claims_total": 0, "numeric_claims_unsourced": 0,
                "confidence_named": False, "bias_flags": [], "notes": [],
                "recommendation_request": False, "escalate_to_solva": False},
    },
}


async def stream_fixture(name: str, chat_id: str):
    f = FIXTURES.get(name)
    if not f:
        yield "data: " + json.dumps({"type": "error", "detail": f"unknown fixture {name!r}"}) + "\n\n"
        return
    mid = str(uuid.uuid4())
    yield "data: " + json.dumps({"type": "start", "message_id": mid}) + "\n\n"
    yield "data: " + json.dumps({"type": "delta", "content": f["text"]}) + "\n\n"
    yield "data: " + json.dumps({"type": "phase", "phase": "complete"}) + "\n\n"
    yield "data: " + json.dumps({"type": "message", "message_id": mid,
                                  "assistant_text": f["text"],
                                  "zz2_governance": f["gov"]}) + "\n\n"
    yield "data: " + json.dumps({"type": "done"}) + "\n\n"
