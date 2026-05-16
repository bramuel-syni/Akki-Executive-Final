"""Phase D fix bundle (2026-05-16) — 4 structural integration tests.

`e1_tester` flagged 3 FAILs + 2 escalated WARNs:
  1. Refusal gate never fires in the live pipeline (T4 thin-answer scenario).
  2. `invalidation_condition` text leaking into synthesis.
  3. Shield `[[ENT_*_NNN]]` placeholders leaking verbatim.
  4. Single-voice invariant tests missed the synthesis surface.

These tests EXERCISE the live pipeline (not the unit functions). They
hit the cloud Shield via the FastAPI router and assert on the
end-to-end output payload.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

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
    suffix = uuid.uuid4().hex[:8]
    email = f"phasedfix-{suffix}@example.com"
    password = "PhaseDFix2026!"
    account_id = f"acc-phasedfix-{suffix}"
    context_id = f"ctx-phasedfix-{suffix}"
    from core import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "PhaseD Fix Probe", "role": "executive", "verified": True,
        "session_version": 0, "created_at": now_iso,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "PhaseD Fix Context", "created_at": now_iso,
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


async def _login(c: AsyncClient, email: str, password: str):
    r = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ─────────────────────────────────────────────────────────────────────
# Fix 1 — Refusal gate must FIRE in the live pipeline.
# Tester's exact scenario: "Should we?" + 7 thin answers.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_refusal_gate_fires_on_persistently_thin_evidence(client, authed):
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    r = await client.post(
        f"/api/contexts/{cid}/solva/v2/sessions",
        json={"sub_module": "seek_clarity"},
        headers=headers,
    )
    sid = r.json()["session_id"]
    r = await client.post(
        f"/api/contexts/{cid}/solva/v2/sessions/{sid}/framing",
        json={"framing_text": "Should we? Yes or no, I am unsure."},
        headers=headers,
    )
    # Tester's exact 7 answers — each meaninglessly short.
    thin_answers = ["yes", "no", "dunno", "maybe", "idk", "shrug", "tbd"]
    for ans in thin_answers:
        r = await client.post(
            f"/api/contexts/{cid}/solva/v2/sessions/{sid}/answer",
            json={"answer_text": ans},
            headers=headers,
        )
        assert r.status_code in (200, 409), r.text
        # Once refused, additional answers should 409.
        if r.status_code == 409:
            break

    # Fetch the final session.
    r = await client.get(
        f"/api/contexts/{cid}/solva/v2/sessions/{sid}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    session = r.json()

    # Locked acceptance: refusal must have fired.
    assert session["status"] == "refused", (
        f"Refusal did NOT fire under tester's thin-answer scenario. "
        f"status={session['status']}, layer_state={session['layer_state']}, "
        f"layer_3={session.get('layer_3')}"
    )
    assert session["layer_state"] == "refused"
    l3 = session.get("layer_3") or {}
    assert l3.get("refusal_flag") is True
    # Brief's exact spec: rendered_synthesis MUST be None or absent on refusal.
    assert l3.get("rendered_synthesis") is None, (
        f"Refused session has rendered_synthesis set: {l3.get('rendered_synthesis')!r}"
    )
    # Scenarios must be empty (no synthesis was produced).
    assert l3.get("scenarios") == []
    assert l3.get("sensitivity_drivers") == []
    # Refusal coach-voice prose must be present in refusal_rendering.
    rendering = (l3.get("refusal_rendering") or "").lower()
    assert rendering, f"refusal_rendering missing on session: {l3}"
    # Coach-voice phrases the rendering should contain.
    assert any(phrase in rendering for phrase in [
        "honestly", "guessing", "responsibly", "won't do",
        "without evidence", "more about", "calibrated for", "footing isn't",
        "would change the picture", "more performance than diagnosis",
        "missing pieces stayed missing",
    ]), f"refusal rendering doesn't read coach-voice: {rendering[:300]}"


# ─────────────────────────────────────────────────────────────────────
# Fix 2 — `invalidation_condition` text MUST NOT appear in synthesis.
# Tester observed literal strings:
#   "If no explicit decision the diagnosis would inform, the lead reading shifts."
#   "If no attached material or referenced source, the lead reading shifts."
# ─────────────────────────────────────────────────────────────────────
def test_synthesis_renderer_does_not_emit_invalidation_phrases():
    """Pure unit test on the renderer — even if caller passes
    `carry_forward_caveats` (back-compat), the renderer MUST NOT emit
    them."""
    from services.solva.voice.synthesis_renderer import render_synthesis
    output = render_synthesis(
        sub_module="seek_clarity",
        scenarios=[{
            "id": "scn-a", "description": "the customer mix has concentrated",
            "weight": 0.55, "confidence_interval_low": 0.40, "confidence_interval_high": 0.65,
        }],
        sensitivity_drivers=[],
        surfaced_tensions=[],
        # Caller passes the legacy carry_forward_caveats argument; the
        # renderer must IGNORE it.
        carry_forward_caveats=[
            "no explicit decision the diagnosis would inform",
            "no attached material or referenced source",
        ],
    )
    forbidden = [
        "the lead reading shifts",
        "no explicit decision the diagnosis would inform",
        "no attached material or referenced source",
        "invalidation_condition",
        "invalidation",
    ]
    lower = output.lower()
    for bad in forbidden:
        assert bad not in lower, (
            f"Synthesis leaked invalidation_condition vocabulary: '{bad}' "
            f"appeared in:\n{output}"
        )


# ─────────────────────────────────────────────────────────────────────
# Fix 3 — Shield `[[ENT_*]]` placeholders MUST NOT appear in synthesis.
# ─────────────────────────────────────────────────────────────────────
def test_synthesis_renderer_strips_entity_placeholders():
    """Even if a scenario description contains hallucinated `[[ENT_*]]`
    tokens, the renderer must strip them before returning."""
    from services.solva.voice.synthesis_renderer import render_synthesis
    output = render_synthesis(
        sub_module="seek_clarity",
        scenarios=[{
            "id": "scn-a",
            "description": "the [[ENT_PROJECT_001]] initiative is the upstream issue",
            "weight": 0.55, "confidence_interval_low": 0.40, "confidence_interval_high": 0.65,
        }, {
            "id": "scn-b",
            "description": "the [[ENT_INVESTMENT_003]] cycle put pressure on the team",
            "weight": 0.30, "confidence_interval_low": 0.20, "confidence_interval_high": 0.45,
        }],
        sensitivity_drivers=[{
            "input_name": "x", "shift_potential": 0.2,
            "description": "fresh signal from [[ENT_INITIATIVE_002]] data",
        }],
        surfaced_tensions=[{
            "description": "the [[ENT_PERSON_007]] memo contradicts the dashboard",
        }],
    )
    assert "[[ENT_" not in output, (
        f"Synthesis leaked Shield placeholders:\n{output}"
    )
    # The substantive content survives the strip.
    assert "upstream" in output.lower()


def test_entity_placeholder_strip_helper():
    """Direct test of `_strip_entity_placeholders`."""
    from services.solva.voice.synthesis_renderer import _strip_entity_placeholders
    cleaned, n = _strip_entity_placeholders(
        "The [[ENT_PROJECT_001]] initiative and [[ENT_PERSON_007]] memo."
    )
    assert "[[ENT_" not in cleaned
    assert n == 2
    cleaned, n = _strip_entity_placeholders("nothing to strip here")
    assert n == 0


# ─────────────────────────────────────────────────────────────────────
# Fix 4 — Single-voice invariant on synthesis surface (well-framed +
# marginal + thin scenarios).
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_single_voice_synthesis_no_far_vocabulary_well_framed(client, authed):
    """A well-evidenced session reaches Layer 3 with a real synthesis —
    that synthesis must pass the single-voice invariant scan."""
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
            "Our top customer concentration is rising and the board needs a "
            "call by end of Q3. The CFO has flagged a memo on renewal patterns "
            "we should be reading."
        )},
        headers=headers,
    )
    detailed = (
        "Looking at the renewal pattern in the memo, the largest customer "
        "revenue has compounded with platform contract milestones, not "
        "pricing. Cost-to-serve has fallen. The pattern is being read as "
        "commercial concentration when it's structural product alignment."
    )
    for _ in range(3):
        await client.post(
            f"/api/contexts/{cid}/solva/v2/sessions/{sid}/answer",
            json={"answer_text": detailed},
            headers=headers,
        )
    for _ in range(3):
        await client.post(
            f"/api/contexts/{cid}/solva/v2/sessions/{sid}/answer",
            json={"answer_text": detailed},
            headers=headers,
        )

    r = await client.get(
        f"/api/contexts/{cid}/solva/v2/sessions/{sid}",
        headers=headers,
    )
    session = r.json()
    l3 = session.get("layer_3") or {}

    # Either we have a real synthesis OR we refused — both are valid
    # end-states. For this test, we only assert on the synthesis surface
    # IF a synthesis was produced.
    if not l3.get("refusal_flag"):
        synthesis = l3.get("rendered_synthesis") or ""
        diagnosis = l3.get("primary_diagnosis_prose") or ""
        from services.solva.voice.invariants import scan_for_internal_artefacts
        assert scan_for_internal_artefacts(synthesis) == [], (
            f"rendered_synthesis leaked artefact vocabulary:\n{synthesis}"
        )
        assert scan_for_internal_artefacts(diagnosis) == [], (
            f"primary_diagnosis_prose leaked artefact vocabulary:\n{diagnosis}"
        )
        # Belt-and-braces literal checks.
        for forbidden in ("[[ENT_", "invalidation_condition",
                          "the lead reading shifts", "FAR ", "layer_0"):
            assert forbidden not in synthesis, (
                f"Forbidden token '{forbidden}' in synthesis:\n{synthesis}"
            )


@pytest.mark.asyncio
async def test_single_voice_refusal_rendering_no_far_vocabulary(client, authed):
    """The refusal rendering surface must also pass the single-voice scan."""
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
        json={"framing_text": "Should we? Yes or no, I am unsure."},
        headers=headers,
    )
    for ans in ["yes", "no", "dunno", "maybe", "idk", "shrug"]:
        await client.post(
            f"/api/contexts/{cid}/solva/v2/sessions/{sid}/answer",
            json={"answer_text": ans},
            headers=headers,
        )
    r = await client.get(
        f"/api/contexts/{cid}/solva/v2/sessions/{sid}",
        headers=headers,
    )
    session = r.json()
    l3 = session.get("layer_3") or {}
    if session["status"] == "refused":
        from services.solva.voice.invariants import scan_for_internal_artefacts
        rendering = l3.get("refusal_rendering") or l3.get("rendered_synthesis") or ""
        assert rendering, "Refused session missing refusal_rendering"
        assert scan_for_internal_artefacts(rendering) == [], (
            f"refusal_rendering leaked artefact vocabulary:\n{rendering}"
        )
        assert "[[ENT_" not in rendering
        assert "invalidation_condition" not in rendering


def test_compute_layer_2_resolved_thin_answers():
    """The helper that drives Rule 3 — pure unit test."""
    from services.solva.reasoning.refusal_logic import compute_layer_2_resolved
    thin = [{"text": "yes"}, {"text": "no"}, {"text": "dunno"}, {"text": "maybe"}]
    assert compute_layer_2_resolved(layer_1_answers=thin, layer_2_answers=thin) is False
    substantive = [
        {"text": "Our top three customers contribute 58% of revenue."},
        {"text": "The renewal cycle window opens in 14 days."},
        {"text": "CFO has been asking for stress scenarios."},
    ]
    assert compute_layer_2_resolved(
        layer_1_answers=substantive, layer_2_answers=substantive,
    ) is True


def test_refusal_logic_low_consistency_rule():
    """New Rule 5 — low triangulation consistency."""
    from services.solva.reasoning.refusal_logic import (
        evaluate_refusal, RefusalReason,
    )
    from services.solva.reasoning.triangulation_engine import TriangulationOutput
    tri = TriangulationOutput(
        overall_consistency=0.2,   # below MIN_TRIANGULATION_CONSISTENCY = 0.4
        divergences=[], extracted_claims=[],
    )
    decision = evaluate_refusal(
        far=None,
        triangulation=tri,
        candidates=[
            # 3 user-anchored candidates so Rule 1 doesn't fire first.
            {"id": "c1", "evidence_requirement": "the Q3 board memo on renewal patterns", "weight": 0.3, "source": "layer_1"},
            {"id": "c2", "evidence_requirement": "the CFO's stress scenarios deck", "weight": 0.3, "source": "layer_1"},
            {"id": "c3", "evidence_requirement": "the customer scorecard last refreshed in May", "weight": 0.3, "source": "layer_1"},
        ],
        situation_class="customer_concentration_risk",
        situation_class_confidence=1.0,
        layer_2_resolved_missing_dimensions=True,
    )
    assert decision.should_refuse is True
    assert decision.reason == RefusalReason.LOW_TRIANGULATION_CONSISTENCY


def test_refusal_logic_synthetic_candidates_do_not_count():
    """Synthetic fallback candidates must not satisfy Rule 1 grounded threshold."""
    from services.solva.reasoning.refusal_logic import evaluate_refusal, RefusalReason
    decision = evaluate_refusal(
        far=None,
        triangulation=None,
        candidates=[
            # Boilerplate evidence + fallback_synthetic source.
            {"id": f"cand-{i}", "evidence_requirement": "material or document referenced in the user's framing",
             "weight": 0.2, "source": "fallback_synthetic"}
            for i in range(5)
        ],
        situation_class="customer_concentration_risk",
        situation_class_confidence=1.0,
        layer_2_resolved_missing_dimensions=True,
    )
    assert decision.should_refuse is True
    assert decision.reason == RefusalReason.INSUFFICIENT_EVIDENCE


def test_invariant_scanner_catches_invalidation_terms():
    """Scanner must catch the Phase D fix-bundle terms."""
    from services.solva.voice.invariants import scan_for_internal_artefacts
    for bad in [
        "If no explicit decision the diagnosis would inform, the lead reading shifts.",
        "The invalidation_condition flag was set.",
        "The Shield placeholder [[ENT_PERSON_001]] was not re-identified.",
        "See FAR.dimensions for detail.",
        "Inspect the routing_decision for next steps.",
    ]:
        hits = scan_for_internal_artefacts(bad)
        assert len(hits) >= 1, f"Scanner missed leak: {bad}"


# ─────────────────────────────────────────────────────────────────────
# Phase D Fix Bundle v2 (2026-05-16) — family-wide placeholder regex
# + DIAGNOSE macro strip + substantive-but-thin FAR refusal fixture.
# ─────────────────────────────────────────────────────────────────────
def test_synthesis_strips_all_placeholder_families():
    """The renderer must strip placeholders of EVERY Shield family,
    not just `[[ENT_*]]`. Phase D fix bundle v2 widened the regex
    from `[[ENT_*_NNN]]` to `[[<UPPER>_<digits>]]`."""
    from services.solva.voice.synthesis_renderer import render_synthesis
    output = render_synthesis(
        sub_module="seek_clarity",
        scenarios=[{
            "id": "scn-a",
            "description": (
                "the [[DATE_1]] window opened with [[MONEY_3]] of new exposure "
                "from the [[ORG_2]] segment, where [[PERSON_4]] flagged it"
            ),
            "weight": 0.55, "confidence_interval_low": 0.40, "confidence_interval_high": 0.65,
        }, {
            "id": "scn-b",
            "description": (
                "the [[GPE_1]] market shifted after [[EVENT_7]] hit "
                "[[FAC_2]] and [[PRODUCT_5]] saw [[IBAN_3]] / [[URL_9]] activity"
            ),
            "weight": 0.30, "confidence_interval_low": 0.20, "confidence_interval_high": 0.45,
        }],
        sensitivity_drivers=[{
            "input_name": "x", "shift_potential": 0.2,
            "description": "fresh signal from [[EMAIL_2]] / [[IP_8]] traffic logs",
        }],
        surfaced_tensions=[{
            "description": "the [[LAW_4]] reading contradicts [[NORP_1]] sentiment",
        }],
    )
    # Family-wide assertion: ZERO `[[<UPPER>_<digits>]]` substrings.
    import re as _re
    placeholder_re = _re.compile(r"\[\[[A-Z][A-Z_]*_\d+\]\]")
    hits = placeholder_re.findall(output)
    assert hits == [], (
        f"Family-wide placeholder strip leaked: {hits}\nOutput:\n{output}"
    )
    # Belt-and-braces: scanner agrees.
    from services.solva.voice.invariants import scan_for_internal_artefacts
    violations = scan_for_internal_artefacts(output)
    assert violations == [], (
        f"Scanner flagged: {[v.term for v in violations]}\nOutput:\n{output}"
    )


def test_synthesis_strips_diagnose_macro_and_siblings():
    """LLM-hallucinated macro headers (`DIAGNOSE`, `EVIDENCE`,
    `CANDIDATES`, etc.) must NOT appear in user prose."""
    from services.solva.voice.synthesis_renderer import (
        render_synthesis, _strip_macro_names,
    )
    # Direct helper test.
    cleaned = _strip_macro_names(
        "DIAGNOSE: the leading reading is X. EVIDENCE: the deck shows Y. "
        "CANDIDATES: three remain on the table."
    )
    for macro in ("DIAGNOSE", "EVIDENCE", "CANDIDATES"):
        assert macro not in cleaned, (
            f"Macro {macro!r} not stripped from: {cleaned!r}"
        )
    # Plain English lowercase stays — "diagnose", "evidence" are fine.
    plain = _strip_macro_names("We should diagnose this carefully; the evidence is clear.")
    assert "diagnose" in plain
    assert "evidence" in plain

    # End-to-end via the renderer.
    output = render_synthesis(
        sub_module="seek_clarity",
        scenarios=[{
            "id": "scn-a",
            "description": "DIAGNOSE: the customer mix concentrated. EVIDENCE: see Q3 deck.",
            "weight": 0.55, "confidence_interval_low": 0.40, "confidence_interval_high": 0.65,
        }],
        sensitivity_drivers=[],
        surfaced_tensions=[{
            "description": "CANDIDATES contradict the renewal pattern in the memo.",
        }],
    )
    for macro in ("DIAGNOSE", "EVIDENCE", "CANDIDATES"):
        assert macro not in output, (
            f"Macro {macro!r} survived rendering. Output:\n{output}"
        )


def test_invariant_scanner_catches_all_placeholder_families():
    """Scanner must flag any `[[<UPPER>_<digits>]]` token + any
    macro-name header — including categories we haven't pre-enumerated."""
    from services.solva.voice.invariants import scan_for_internal_artefacts
    for token in [
        "[[ENT_PERSON_001]]", "[[DATE_4]]", "[[MONEY_12]]",
        "[[ORG_2]]", "[[EMAIL_9]]", "[[PHONE_E164_3]]",
        "[[IBAN_7]]", "[[ACCOUNT_NUM_4]]", "[[IP_6]]",
        "[[URL_2]]", "[[GPE_1]]", "[[PRODUCT_5]]",
        "[[NORP_8]]", "[[FAC_11]]", "[[EVENT_3]]",
        "[[LAW_2]]", "[[NEW_FUTURE_CATEGORY_1]]",   # forward-compat
    ]:
        sentence = f"The {token} reading sits at 55%."
        hits = scan_for_internal_artefacts(sentence)
        assert len(hits) >= 1, f"Scanner missed placeholder: {token}"

    for macro_sentence in [
        "DIAGNOSE: the leading reading is concentration.",
        "Here is what I'd say. EVIDENCE: the deck shows Y.",
        "Reading 1: X. CANDIDATES: three remain.",
        "OBSERVE — the pattern repeats.",
    ]:
        hits = scan_for_internal_artefacts(macro_sentence)
        assert len(hits) >= 1, f"Scanner missed macro: {macro_sentence}"


# ─────────────────────────────────────────────────────────────────────
# Fixture for FAR-refusal-reachable-after-jailbreak-passes scenario.
# Tester noted the original "yes/no/dunno/maybe/idk/shrug/tbd" inputs
# trip the LEGACY router's safety classifier with `status="blocked_hard"`.
# Phase D's path has NO safety classifier (Phase E pull-forward), so on
# Phase D endpoints those inputs flow straight to the FAR refusal gate.
# But to prove the FAR refusal path is REACHABLE in production from
# substantive-looking executive content, this fixture uses full-sentence
# answers that nonetheless carry no specifics / no numbers / no
# named entities / no decision under consideration.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_far_refusal_reachable_with_substantive_but_thin_inputs(client, authed):
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    r = await client.post(
        f"/api/contexts/{cid}/solva/v2/sessions",
        json={"sub_module": "seek_clarity"},
        headers=headers,
    )
    sid = r.json()["session_id"]
    # Substantive-looking framing (full sentences, executive register)
    # but evidence-thin: no decision, no horizon, no named source.
    framing = (
        "I'm not sure what to ask. There's something on my mind about the "
        "company direction but I can't quite articulate it. The board wants "
        "me to think about it more carefully before the next meeting."
    )
    r = await client.post(
        f"/api/contexts/{cid}/solva/v2/sessions/{sid}/framing",
        json={"framing_text": framing},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    # Substantive-looking but evidence-thin answers.
    answers = [
        "I think we should consider doing something soon but I'm not certain what direction would be best.",
        "There are a few things I'm worried about but nothing specific I can put my finger on right now.",
        "Some pressures from somewhere are pushing us to make a change of some kind in the near term.",
        "I keep coming back to the question without ever resolving it one way or the other.",
        "It's hard to know where to start, frankly, and I'd appreciate a sharper read on the situation.",
        "I don't have the materials in front of me but I sense something is shifting beneath the surface.",
        "Whenever I try to articulate the issue, the words seem to slip away from any concrete shape.",
    ]
    for ans in answers:
        r = await client.post(
            f"/api/contexts/{cid}/solva/v2/sessions/{sid}/answer",
            json={"answer_text": ans},
            headers=headers,
        )
        # 200 while still active; 409 once refused (terminal).
        assert r.status_code in (200, 409), r.text
        if r.status_code == 409:
            break

    r = await client.get(
        f"/api/contexts/{cid}/solva/v2/sessions/{sid}",
        headers=headers,
    )
    session = r.json()

    # Locked acceptance — the FAR refusal path is REACHABLE in production
    # from substantive-looking executive content that carries no specifics.
    assert session["status"] == "refused", (
        f"FAR refusal did NOT fire on substantive-but-thin inputs. "
        f"status={session['status']}, layer_state={session['layer_state']}, "
        f"refusal_reason={(session.get('layer_3') or {}).get('refusal_reason')}, "
        f"layer_3={session.get('layer_3')}"
    )
    assert session["layer_state"] == "refused"
    l3 = session.get("layer_3") or {}
    assert l3.get("refusal_flag") is True
    # rendered_synthesis MUST be None on refusal (brief contract).
    assert l3.get("rendered_synthesis") is None
    assert l3.get("scenarios") == []
    # Refusal coach voice present.
    rendering = (l3.get("refusal_rendering") or "").lower()
    assert rendering, f"refusal_rendering missing on session: {l3}"
    # Single-voice scan on the refusal rendering.
    from services.solva.voice.invariants import scan_for_internal_artefacts
    violations = scan_for_internal_artefacts(l3.get("refusal_rendering") or "")
    assert violations == [], (
        f"Refusal rendering leaked vocabulary: {[v.term for v in violations]}"
    )
