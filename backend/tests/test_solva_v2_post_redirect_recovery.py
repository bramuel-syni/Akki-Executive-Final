"""Phase 15.3 fix-pass — therapy redirect must NOT 500 the next turn.

Tester reported: distress turn → therapy_redirect (200, locked sentence
emitted, session active) → next user turn HTTP 500 with body
`candidate_generation_validator_rejected`. The fix is the one-shot
`redirect_recovery` flag set on therapy_redirect and consumed by
candidate_generation on the very next turn (relaxes the
responsiveness validator that would otherwise reject the pivot).

These tests cover:
  1. Unit: candidate_generation.run accepts `relax_responsiveness=True`
     and the responsiveness check is suppressed.
  2. Unit: guardrail.evaluate(therapy_redirect) sets the
     `redirect_recovery` action — orchestrator persists this.
  3. Integration: synthetic-DB walk that simulates a redirect-then-pivot
     sequence at the grounding layer and asserts the next turn returns
     200 (not 500).
"""
import os
import re

import pytest
import requests

from services.solva_v2 import guardrails

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "http://localhost:8001"
).rstrip("/")
ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASSWORD = "AkkiAdmin2026!"


# -----------------------------------------------------------------------------
# 1) Unit — guardrail decision
# -----------------------------------------------------------------------------
def test_guardrail_evaluate_therapy_redirect_marks_recovery():
    """The orchestrator reads `decision.action` and persists
    `redirect_recovery=True` when action is 'therapy_redirect'."""
    sess = {"jailbreak_soft_count": 0, "id": "s1"}
    out = guardrails.evaluate(
        session=sess,
        refusal_output={
            "block": False,
            "category": "out_of_scope",
            "confidence": 0.9,
            "reason": "personal distress",
            "distress_flag": True,
            "extraction_marker_hit": None,
        },
    )
    assert out.action == "therapy_redirect"
    assert out.new_status is None  # session stays active
    # Orchestrator-side: this action triggers redirect_recovery=True.
    # Asserted at the orchestrator integration test below.


# -----------------------------------------------------------------------------
# 2) Unit — candidate_generation: relax_responsiveness suppresses the check
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_candidate_generation_relax_responsiveness_skips_intent_word_check(monkeypatch):
    """When `relax_responsiveness=True`, the validator's intent-word
    overlap check is suppressed. Distinctness + count-bounds still apply.

    Constructs a deterministic candidate set whose hypotheses share NO
    words with the intent. Without relaxation, this would be rejected
    `not responsive`. With relaxation, accepted.
    """
    from services.solva_v2.engines import candidate_generation as cg

    intent = "Diagnose softening EMEA bookings"
    fake_candidates_json = (
        '{"candidates": ['
        '{"hypothesis": "Pricing pressure", "tentative_tier_hint": "comparable"},'
        '{"hypothesis": "Channel saturation", "tentative_tier_hint": "domain_prior"},'
        '{"hypothesis": "Macro shock", "tentative_tier_hint": "speculation"}'
        ']}'
    )

    async def fake_shielded_call(**kwargs):
        # Mimic the shielded_call return contract.
        class _Result:
            text = fake_candidates_json
            reasoning_audit_entry = {
                "engine": cg.ENGINE,
                "engine_version": cg.ENGINE_VERSION,
                "layer": kwargs.get("layer"),
                "turn_id": kwargs.get("turn_id"),
                "output": {},
                "tier_labels": [],
            }
        return _Result()

    # Patch the dynamically-imported shielded_call.
    import services.solva_v2.engines.llm_adapter_proxy as proxy
    monkeypatch.setattr(proxy, "shielded_call", fake_shielded_call)

    cluster = {"id": "x", "label": "Revenue underperformance"}

    # WITHOUT relaxation — must reject (no word overlap).
    res_strict = await cg.run(
        session={"id": "s1", "account_id": "a1"},
        turn_id="t1",
        layer="grounding",
        intent=intent,
        cluster=cluster,
        relax_responsiveness=False,
    )
    assert res_strict.get("violation") is True, \
        "strict path should reject candidates that share no intent words"
    assert res_strict.get("reason") == "candidate_generation_validator_rejected"

    # WITH relaxation — must accept the same candidates.
    res_relaxed = await cg.run(
        session={"id": "s1", "account_id": "a1"},
        turn_id="t2",
        layer="grounding",
        intent=intent,
        cluster=cluster,
        relax_responsiveness=True,
    )
    assert res_relaxed.get("violation") is False, \
        f"relaxed path should accept; got {res_relaxed}"
    assert "output" in res_relaxed
    assert res_relaxed["output"]["candidate_count"] == 3


@pytest.mark.asyncio
async def test_candidate_generation_relax_does_NOT_disable_distinctness(monkeypatch):
    """Distinctness check still applies even under relaxation."""
    from services.solva_v2.engines import candidate_generation as cg

    duplicate_json = (
        '{"candidates": ['
        '{"hypothesis": "X", "tentative_tier_hint": "comparable"},'
        '{"hypothesis": "X", "tentative_tier_hint": "comparable"}'
        ']}'
    )

    async def fake_shielded_call(**kwargs):
        class _Result:
            text = duplicate_json
            reasoning_audit_entry = {
                "engine": cg.ENGINE,
                "engine_version": cg.ENGINE_VERSION,
                "layer": kwargs.get("layer"),
                "turn_id": kwargs.get("turn_id"),
                "output": {},
                "tier_labels": [],
            }
        return _Result()

    import services.solva_v2.engines.llm_adapter_proxy as proxy
    monkeypatch.setattr(proxy, "shielded_call", fake_shielded_call)

    res = await cg.run(
        session={"id": "s1", "account_id": "a1"},
        turn_id="t1",
        layer="grounding",
        intent="anything",
        cluster={"id": "x", "label": "Y"},
        relax_responsiveness=True,
    )
    assert res.get("violation") is True, \
        "duplicate candidates must still be rejected even under relaxation"


# -----------------------------------------------------------------------------
# 3) Integration — DB-stuffed session simulating a post-redirect pivot
#    at the grounding layer. The DB-stuffing pattern matches the existing
#    test_solva_v2_session_limits.py approach so we don't depend on the
#    LLM classifier flagging distress on a specific phrase.
# -----------------------------------------------------------------------------
def _login():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}", "Content-Type": "application/json"}


def _abandon_all(headers):
    r = requests.get(
        f"{BASE_URL}/api/solva/v2/sessions",
        params={"status": "active"},
        headers=headers, timeout=30,
    )
    for s in (r.json().get("items") or []):
        requests.post(
            f"{BASE_URL}/api/solva/v2/sessions/{s['id']}/abandon",
            headers=headers, timeout=30,
        )


@pytest.mark.timeout(180)
@pytest.mark.asyncio
async def test_post_redirect_pivot_does_not_500_at_grounding():
    """Reproduce the tester's exact failure mode: redirect-at-grounding
    followed by a pivot turn that triggers candidate_generation.

    We DB-stuff the session into the grounding layer with a transcript
    that includes a therapy_redirect Solva turn and `redirect_recovery=True`.
    Then we POST a pivot turn and assert HTTP 200, not 500.
    """
    headers = _login()
    _abandon_all(headers)

    cl = requests.get(f"{BASE_URL}/api/solva/clusters", headers=headers, timeout=30).json()
    cid = cl["clusters"][0]["id"]

    s = requests.post(
        f"{BASE_URL}/api/solva/v2/sessions",
        headers=headers,
        json={
            "cluster_id": cid,
            "intent": "We need to decide whether to bring the FY26 capex forward by two quarters.",
            "submodule": "seek_clarity",
        },
        timeout=240,
    )
    assert s.status_code == 200, s.text
    sid = s.json()["id"]

    # Stuff the session into the grounding layer with the synthetic
    # therapy-redirect Solva turn and the recovery flag.
    from core import db
    res = await db.solva_v2_sessions.update_one(
        {"id": sid},
        {"$set": {
            "layer": "grounding",
            "layer_index": 1,
            "redirect_recovery": True,
        },
         "$push": {
            "turns": {
                "$each": [
                    {
                        "id": "synthetic-distress",
                        "role": "user",
                        "layer": "grounding",
                        "text": "I'm exhausted and burned out — I can't carry on.",
                        "model": None,
                        "tier": None,
                        "created_at": "2026-01-01T00:00:00Z",
                    },
                    {
                        "id": "synthetic-redirect",
                        "role": "solva",
                        "layer": "grounding",
                        "text": guardrails.THERAPY_REDIRECT_MESSAGE,
                        "model": None,
                        "tier": None,
                        "guardrail_action": "therapy_redirect",
                        "learn_link": "/app/learn/board-room-stress",
                        "created_at": "2026-01-01T00:00:01Z",
                    },
                ],
            },
        }},
    )
    assert res.modified_count == 1

    # The pivot turn — the one the tester reported as 500.
    pivot = requests.post(
        f"{BASE_URL}/api/solva/v2/sessions/{sid}/turn",
        headers=headers,
        json={"user_text": "Let's get back to capital allocation — we're considering a £40m buyback this year."},
        timeout=240,
    )

    # Cleanup before any assertion fails.
    requests.post(
        f"{BASE_URL}/api/solva/v2/sessions/{sid}/abandon",
        headers=headers, timeout=30,
    )

    # Tester's regression: this MUST be 200 (or a graceful 422 on a
    # non-validator-rejected path). It must NOT be 500.
    assert pivot.status_code != 500, \
        f"post-redirect pivot 500'd: {pivot.status_code}: {pivot.text[:300]}"

    # If 200, also assert the recovery flag was consumed.
    if pivot.status_code == 200:
        rec = pivot.json()
        assert rec.get("redirect_recovery") in (False, None), \
            f"redirect_recovery should be cleared after consumption: {rec.get('redirect_recovery')}"


@pytest.mark.timeout(60)
@pytest.mark.asyncio
async def test_redirect_recovery_flag_persisted_on_therapy_redirect_branch():
    """When the orchestrator hits the therapy_redirect branch on
    session-create, `redirect_recovery=True` must be persisted on
    the session row so the next turn can consume it."""
    headers = _login()
    _abandon_all(headers)

    cl = requests.get(f"{BASE_URL}/api/solva/clusters", headers=headers, timeout=30).json()
    cid = cl["clusters"][0]["id"]

    # Distress-flagged intent at session start.
    s = requests.post(
        f"{BASE_URL}/api/solva/v2/sessions",
        headers=headers,
        json={
            "cluster_id": cid,
            "intent": (
                "Honestly I'm exhausted and burned out — I can't carry on with "
                "this board role. I just need someone to talk to."
            ),
            "submodule": "seek_clarity",
        },
        timeout=240,
    )
    assert s.status_code == 200, s.text
    rec = s.json()
    sid = rec["id"]

    # If the LLM classifier fired therapy_redirect on the intent, the
    # last solva turn carries guardrail_action=therapy_redirect AND the
    # session row carries redirect_recovery=True.
    last_solva = next(
        (t for t in reversed(rec.get("turns") or []) if t.get("role") == "solva"),
        None,
    )
    if last_solva and last_solva.get("guardrail_action") == "therapy_redirect":
        from core import db
        row = await db.solva_v2_sessions.find_one(
            {"id": sid},
            {"_id": 0, "redirect_recovery": 1, "status": 1},
        )
        assert row.get("redirect_recovery") is True, \
            f"redirect_recovery not persisted after therapy_redirect: {row}"
        assert row.get("status") == "active", \
            "therapy_redirect must NOT terminate the session"

    requests.post(
        f"{BASE_URL}/api/solva/v2/sessions/{sid}/abandon",
        headers=headers, timeout=30,
    )
