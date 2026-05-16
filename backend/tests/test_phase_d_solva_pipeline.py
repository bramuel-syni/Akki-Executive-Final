"""Phase D — Solva 5-layer state machine + reasoning + voice + audit panel.

Covers:
- State machine transitions (entry → framing → layer_0 → ... → done)
- 7 reasoning models — happy path + edge cases (sub-set; LLM-bound
  modules covered behaviourally via mock-mode Shield)
- Single-voice invariant scan
- Refusal path (insufficient evidence + operator refusal)
- Session audit IDs grow per Shield call
- Audit panel timeline endpoint
- Strict context_id + account_id scoping
- Resume across browser refresh (state persists per layer transition)

Mock-mode Shield: tests rely on `SYNISENSE_LLM_MODE=mock` set by the
fixture, which makes `services.synisense.shield.llm_router.invoke`
return canned content WITHOUT hitting the cloud — keeps tests
deterministic + offline.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from server import app


@pytest_asyncio.fixture
async def db_conn():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    yield db
    client.close()


@pytest_asyncio.fixture
async def client():
    os.environ["SYNISENSE_LLM_MODE"] = "mock"
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.update(saved)


@pytest_asyncio.fixture
async def authed(db_conn):
    """Seed an account + active membership in a single context."""
    suffix = uuid.uuid4().hex[:8]
    email = f"phased-{suffix}@example.com"
    password = "PhaseD2026!"
    account_id = f"acc-phased-{suffix}"
    context_id = f"ctx-phased-{suffix}"
    from core import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "PhaseD Probe", "role": "executive", "verified": True,
        "session_version": 0, "created_at": now_iso,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "PhaseD Context", "created_at": now_iso,
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}",
        "context_id": context_id, "account_id": account_id,
        "status": "active", "sub_role": "owner",
        "created_at": now_iso,
    })
    yield {
        "email": email, "password": password,
        "account_id": account_id, "context_id": context_id,
    }
    await db_conn.accounts.delete_one({"id": account_id})
    await db_conn.contexts.delete_one({"id": context_id})
    await db_conn.memberships.delete_many({"account_id": account_id})
    await db_conn.solva_phase_d_sessions.delete_many({"account_id": account_id})
    await db_conn.synisense_audit_log.delete_many({"tenant_id": account_id})
    await db_conn.synisense_trust_receipts.delete_many({"tenant_id": account_id})


async def _login(c: AsyncClient, email: str, password: str) -> Dict[str, str]:
    r = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ─────────────────────────────────────────────────────────────────────
# Unit tests — state machine.
# ─────────────────────────────────────────────────────────────────────
def test_state_machine_canonical_sequence():
    from services.solva.orchestration.state_machine import advance
    seq = ["entry"]
    cur = "entry"
    while cur != "done":
        cur, terminal = advance(cur)
        seq.append(cur)
        if terminal:
            break
    assert seq == [
        "entry", "framing", "layer_0", "layer_1", "layer_2",
        "layer_3", "layer_4", "done",
    ]


def test_state_machine_rejects_advance_from_done():
    from services.solva.orchestration.state_machine import advance, InvalidLayerTransition
    with pytest.raises(InvalidLayerTransition):
        advance("done")


def test_state_machine_can_advance_to_strict():
    from services.solva.orchestration.state_machine import can_advance_to
    assert can_advance_to("entry", "framing") is True
    assert can_advance_to("layer_1", "layer_2") is True
    assert can_advance_to("entry", "layer_3") is False  # no skipping
    assert can_advance_to("done", "framing") is False


# ─────────────────────────────────────────────────────────────────────
# Unit tests — single-voice invariant.
# ─────────────────────────────────────────────────────────────────────
def test_single_voice_scan_catches_far_vocabulary():
    from services.solva.voice.invariants import scan_for_internal_artefacts
    bad = "Your Frame Audit Record verdict is sufficient_with_caveats."
    hits = scan_for_internal_artefacts(bad)
    assert len(hits) >= 1
    assert any("frame audit record" in h.term.lower() for h in hits)


def test_single_voice_scan_catches_legacy_leak_string():
    """The user's screenshot leak — 'a couple of pieces are thin' was
    rendered as user content. The new voice tier must NEVER emit it."""
    from services.solva.voice.invariants import scan_for_internal_artefacts
    hits = scan_for_internal_artefacts(
        "Your framing is workable, but a couple of pieces are thin."
    )
    assert any("couple of pieces are thin" in h.term.lower() for h in hits)


def test_single_voice_scan_clean_passes():
    from services.solva.voice.invariants import scan_for_internal_artefacts
    clean = (
        "Here is where I've landed. The reading that holds up best is this: "
        "your customer mix has concentrated since Q2 and the renewal pattern is "
        "the leading indicator. I'd put that at around 55%."
    )
    assert scan_for_internal_artefacts(clean) == []


def test_question_bank_layer_1_opening_no_far_vocabulary():
    """Brief deliverable #2 — Layer 1 opening question must come from
    question_bank.py and must NOT contain FAR verdict text."""
    from services.solva.voice.question_bank import next_question
    from services.solva.voice.invariants import scan_for_internal_artefacts
    for sub in ("seek_clarity", "develop_strategy", "simulate_hypothesis", "get_perspective"):
        for suffix in ("default", "with_caveats", "conversational"):
            key = f"{sub}.layer_1.opening.{suffix}"
            q = next_question(key=key, session_id="sess-test-1", asked_so_far=0)
            assert q.text
            hits = scan_for_internal_artefacts(q.text)
            assert hits == [], (
                f"Layer 1 opening question for {key} leaked internal artefact "
                f"vocabulary: {hits}"
            )


def test_synthesis_renderer_output_clean():
    """The voice tier's synthesis renderer must produce single-voice
    output for any reasonable input."""
    from services.solva.voice.synthesis_renderer import render_synthesis
    from services.solva.voice.invariants import scan_for_internal_artefacts
    body = render_synthesis(
        sub_module="seek_clarity",
        scenarios=[{
            "id": "scn-a", "description": "your customer mix has concentrated",
            "weight": 0.55, "confidence_interval_low": 0.40, "confidence_interval_high": 0.65,
        }, {
            "id": "scn-b", "description": "an unhedged supplier risk is upstream",
            "weight": 0.30, "confidence_interval_low": 0.20, "confidence_interval_high": 0.45,
        }],
        sensitivity_drivers=[{"input_name": "x", "shift_potential": 0.2, "description": "fresh renewal data"}],
        surfaced_tensions=[{"description": "the renewals trend named in the memo does not match the dashboard."}],
        carry_forward_caveats=["the time horizon was not named explicitly"],
    )
    hits = scan_for_internal_artefacts(body)
    assert hits == [], f"Synthesis leaked vocabulary: {hits}"
    # Spot-check coach voice — short opening, percentages render.
    assert "Here is where I've landed." in body
    assert "55%" in body


# ─────────────────────────────────────────────────────────────────────
# Unit tests — refusal logic.
# ─────────────────────────────────────────────────────────────────────
def test_refusal_fires_on_insufficient_evidence():
    from services.solva.reasoning.refusal_logic import evaluate_refusal, RefusalReason
    decision = evaluate_refusal(
        far=None,
        triangulation=None,
        candidates=[{"id": "c1", "evidence_requirement": "", "weight": 0.0}],
        situation_class="customer_concentration_risk",
        situation_class_confidence=1.0,
        layer_2_resolved_missing_dimensions=True,
    )
    assert decision.should_refuse is True
    assert decision.reason == RefusalReason.INSUFFICIENT_EVIDENCE


def test_refusal_holds_when_evidence_sufficient():
    from services.solva.reasoning.refusal_logic import evaluate_refusal
    decision = evaluate_refusal(
        far=None,
        triangulation=None,
        candidates=[
            {"id": "c1", "evidence_requirement": "the board memo on Q3 customer renewal patterns", "weight": 0.3, "source": "layer_1"},
            {"id": "c2", "evidence_requirement": "the CFO stress-scenarios deck dated last week", "weight": 0.3, "source": "layer_1"},
            {"id": "c3", "evidence_requirement": "the customer scorecard refreshed in May 2026", "weight": 0.3, "source": "layer_1"},
        ],
        situation_class="capital_allocation",
        situation_class_confidence=0.9,
        layer_2_resolved_missing_dimensions=True,
    )
    assert decision.should_refuse is False


def test_refusal_voice_no_far_vocabulary():
    from services.solva.voice.refusal_voice import render_refusal
    from services.solva.reasoning.refusal_logic import RefusalReason
    from services.solva.voice.invariants import scan_for_internal_artefacts
    body = render_refusal(
        sub_module="seek_clarity",
        reason=RefusalReason.INSUFFICIENT_EVIDENCE,
        candidates_to_surface=[
            {"id": "c1", "description": "internal capability gap"},
            {"id": "c2", "description": "external market shift"},
        ],
    )
    assert scan_for_internal_artefacts(body) == []
    assert "honestly" in body or "guessing" in body or "synthesis" in body


# ─────────────────────────────────────────────────────────────────────
# Integration tests — endpoints (mock-mode Shield).
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_session_strict_context_scoping(client, authed, db_conn):
    headers = await _login(client, authed["email"], authed["password"])
    # Happy: create succeeds in a context the user belongs to.
    r = await client.post(
        f"/api/contexts/{authed['context_id']}/solva/v2/sessions",
        json={"sub_module": "seek_clarity"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session_id"].startswith("sol-")
    assert body["layer_state"] == "entry"
    assert body["status"] == "active"
    assert body["account_id"] == authed["account_id"]
    assert body["context_id"] == authed["context_id"]
    assert body["synisense_audit_ids"] == []
    # Cross-context attempt: hit a context that does not exist.
    r = await client.post(
        "/api/contexts/ctx-nonexistent/solva/v2/sessions",
        json={"sub_module": "seek_clarity"},
        headers=headers,
    )
    assert r.status_code in (403, 404)


@pytest.mark.asyncio
async def test_full_session_round_trip_audit_ids_grow(client, authed, db_conn):
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    # Step 1: create.
    r = await client.post(
        f"/api/contexts/{cid}/solva/v2/sessions",
        json={"sub_module": "seek_clarity"},
        headers=headers,
    )
    sid = r.json()["session_id"]

    # Step 2: framing → Layer 0 silent → land in layer_1.
    r = await client.post(
        f"/api/contexts/{cid}/solva/v2/sessions/{sid}/framing",
        json={"framing_text": (
            "Our top customer concentration is rising and the board needs a "
            "call by end of Q3. The CFO has flagged a memo we should be "
            "reading. By when this becomes harder to ignore matters."
        )},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["layer_state"] == "layer_1"
    assert payload["layer_0"] is not None
    assert payload["layer_0"]["verdict"] in (
        "sufficient", "sufficient_with_caveats", "insufficient",
    )
    assert payload["layer_0"]["situation_class"]
    audits_after_framing = len(payload["synisense_audit_ids"])
    # Frame audit ALWAYS makes one Shield call. Situation classifier
    # may short-circuit on a strong keyword match (no LLM call); when
    # it doesn't, audit count is 2.
    assert audits_after_framing >= 1
    assert payload["next_question"]["layer"] == "layer_1"
    assert payload["next_question"]["question_text"]
    # Single-voice invariant on the user-visible payload.
    from services.solva.voice.invariants import scan_for_internal_artefacts
    user_visible = (
        payload["next_question"]["question_text"]
        + " "
        + (payload.get("acknowledgement") or "")
    )
    assert scan_for_internal_artefacts(user_visible) == []

    # Step 3: Layer 1 — 3 answers, then auto-advance to layer_2.
    for i in range(3):
        r = await client.post(
            f"/api/contexts/{cid}/solva/v2/sessions/{sid}/answer",
            json={"answer_text": f"Layer-1 answer number {i + 1}. We've named the top three customers and the renewals window."},
            headers=headers,
        )
        assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["layer_state"] == "layer_2"
    assert payload["layer_1"]["candidate_set"]
    audits_after_layer_1 = len(payload["synisense_audit_ids"])
    assert audits_after_layer_1 > audits_after_framing  # candidate_generation

    # Step 4: Layer 2 — 3 answers, then auto-advance to layer_3 (synthesis or refusal) and layer_4.
    for i in range(3):
        r = await client.post(
            f"/api/contexts/{cid}/solva/v2/sessions/{sid}/answer",
            json={"answer_text": (
                f"Layer-2 depth answer {i + 1}. The renewal patterns in the memo show "
                "the top customer's revenue has compounded with platform contract "
                "milestones, not pricing."
            )},
            headers=headers,
        )
        assert r.status_code == 200, r.text
    payload = r.json()
    # Layer 3 ran during the last Layer 2 answer. Under mock LLM the
    # canned responses are unlikely to produce substantive candidates,
    # so the session may refuse correctly. With substantive cloud LLM
    # responses we'd see layer_4 (full synthesis). Both are valid
    # Phase D outcomes — the assertion is that Layer 3 ran AT ALL.
    assert payload["layer_state"] in ("layer_4", "layer_3", "refused")
    if payload["layer_state"] == "layer_4":
        assert payload["layer_3"]["rendered_synthesis"]
        # Single-voice invariant on the synthesis prose.
        from services.solva.voice.invariants import scan_for_internal_artefacts
        assert scan_for_internal_artefacts(payload["layer_3"]["rendered_synthesis"]) == []
    elif payload["layer_state"] == "refused":
        # Refusal-by-rule (likely Rule 1: all candidates fell back to
        # synthetic under the mock Shield). Verify rendering is present.
        assert payload["layer_3"]["refusal_flag"] is True
        assert payload["layer_3"].get("refusal_rendering") or payload["layer_3"].get("rendered_synthesis")
    audits_after_layer_3 = len(payload["synisense_audit_ids"])
    assert audits_after_layer_3 > audits_after_layer_1

    # Step 5: timeline endpoint.
    r = await client.get(
        f"/api/contexts/{cid}/solva/v2/sessions/{sid}/audit-panel/timeline",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    tl = r.json()
    assert len(tl["steps"]) == audits_after_layer_3
    assert tl["aggregate"]["llm_calls"] == audits_after_layer_3
    # Purpose labels are human-readable (NOT raw enum strings).
    for step in tl["steps"]:
        assert step["purpose_label"]
        # Common purpose labels we expect: Frame Audit, Situation Classification,
        # Candidate Generation, Triangulation, etc.
        assert step["purpose_raw"].startswith("solva.")


@pytest.mark.asyncio
async def test_session_get_returns_next_question_when_resumed(client, authed):
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    r = await client.post(
        f"/api/contexts/{cid}/solva/v2/sessions",
        json={"sub_module": "develop_strategy"},
        headers=headers,
    )
    sid = r.json()["session_id"]
    r = await client.post(
        f"/api/contexts/{cid}/solva/v2/sessions/{sid}/framing",
        json={"framing_text": (
            "We are weighing whether to deepen our investment in the regulated "
            "fund-administration line versus pivoting to a tech-licensing model. "
            "The CFO has the financials behind both options. We need a call by "
            "the next board meeting."
        )},
        headers=headers,
    )
    sid_after = r.json()["session_id"]
    assert sid == sid_after
    # GET should reflect persisted layer_state + next_question.
    r = await client.get(
        f"/api/contexts/{cid}/solva/v2/sessions/{sid}",
        headers=headers,
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["layer_state"] == "layer_1"
    assert payload["next_question"]["question_text"]


@pytest.mark.asyncio
async def test_operator_refusal_endpoint(client, authed):
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    r = await client.post(
        f"/api/contexts/{cid}/solva/v2/sessions",
        json={"sub_module": "seek_clarity"},
        headers=headers,
    )
    sid = r.json()["session_id"]
    r = await client.post(
        f"/api/contexts/{cid}/solva/v2/sessions/{sid}/refuse",
        json={"operator_reason": "Insufficient context for diagnosis"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "refused"
    # Phase D fix 2026-05-16: layer_state is "refused", not "layer_3".
    assert body["layer_state"] == "refused"
    assert body["layer_3"]["refusal_flag"] is True
    # Phase D fix bundle: rendered_synthesis MUST be None on refusal.
    assert body["layer_3"].get("rendered_synthesis") is None
    # The coach-voice refusal copy lives in refusal_rendering.
    rendering = body["layer_3"].get("refusal_rendering") or ""
    assert rendering
    from services.solva.voice.invariants import scan_for_internal_artefacts
    assert scan_for_internal_artefacts(rendering) == []
    # Subsequent operator-refuse on the same session is a 409.
    r = await client.post(
        f"/api/contexts/{cid}/solva/v2/sessions/{sid}/refuse",
        json={},
        headers=headers,
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_list_sessions_scoped_to_context(client, authed, db_conn):
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    # Create 2 sessions in this context.
    for _ in range(2):
        r = await client.post(
            f"/api/contexts/{cid}/solva/v2/sessions",
            json={"sub_module": "seek_clarity"},
            headers=headers,
        )
        assert r.status_code == 200
    # Insert a foreign-context row directly into Mongo (should NOT surface).
    await db_conn.solva_phase_d_sessions.insert_one({
        "session_id": f"sol-foreign-{uuid.uuid4().hex[:6]}",
        "account_id": authed["account_id"], "context_id": "ctx-other-foreign",
        "sub_module": "seek_clarity", "status": "active",
        "layer_state": "entry", "schema_version": 3,
        "synisense_audit_ids": [], "orchestration_audit_log": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    r = await client.get(
        f"/api/contexts/{cid}/solva/v2/sessions",
        headers=headers,
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["count"] == 2
    for item in payload["items"]:
        assert item["context_id"] == cid
    # Clean up the foreign row.
    await db_conn.solva_phase_d_sessions.delete_many({"context_id": "ctx-other-foreign"})


@pytest.mark.asyncio
async def test_cross_account_isolation(client, authed, db_conn):
    """Account A creates a session; account B (with active membership in
    A's context — simulating shared workspace) can ALSO list/get because
    membership grants access. But an account with NO membership cannot."""
    suffix = uuid.uuid4().hex[:6]
    headers_a = await _login(client, authed["email"], authed["password"])

    # Create a session as A.
    r = await client.post(
        f"/api/contexts/{authed['context_id']}/solva/v2/sessions",
        json={"sub_module": "seek_clarity"},
        headers=headers_a,
    )
    sid = r.json()["session_id"]

    # Stand up account B with NO membership.
    email_b = f"phased-b-{suffix}@example.com"
    pw_b = "PhaseDb2026!"
    aid_b = f"acc-phased-b-{suffix}"
    from core import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": aid_b, "email": email_b, "password_hash": hash_password(pw_b),
        "name": "PhaseD B", "role": "executive", "verified": True,
        "session_version": 0, "created_at": now_iso,
    })
    headers_b = await _login(client, email_b, pw_b)
    try:
        r = await client.get(
            f"/api/contexts/{authed['context_id']}/solva/v2/sessions/{sid}",
            headers=headers_b,
        )
        assert r.status_code == 403, r.text
    finally:
        await db_conn.accounts.delete_one({"id": aid_b})


# ─────────────────────────────────────────────────────────────────────
# Audit panel — single-voice check on the timeline payload.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_audit_panel_timeline_purpose_labels_human_readable(client, authed):
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    r = await client.post(
        f"/api/contexts/{cid}/solva/v2/sessions",
        json={"sub_module": "seek_clarity"},
        headers=headers,
    )
    sid = r.json()["session_id"]
    await client.post(
        f"/api/contexts/{cid}/solva/v2/sessions/{sid}/framing",
        json={"framing_text": (
            "Our top customer concentration is rising and we need a board "
            "call by Q3. CFO has the memo."
        )},
        headers=headers,
    )
    r = await client.get(
        f"/api/contexts/{cid}/solva/v2/sessions/{sid}/audit-panel/timeline",
        headers=headers,
    )
    assert r.status_code == 200
    tl = r.json()
    label_set = {s["purpose_label"] for s in tl["steps"]}
    # Phase D pre-fold labels:
    assert any(lbl in ("Frame Audit", "Situation Classification") for lbl in label_set)
    # No raw `solva.layer_*` strings surface as `purpose_label`.
    for s in tl["steps"]:
        assert not s["purpose_label"].startswith("solva.")
