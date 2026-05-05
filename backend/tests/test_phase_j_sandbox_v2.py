"""Phase J.1 — Sandbox v2 persistence smoke + welcome lifecycle.

Run:  pytest -q backend/tests/test_phase_j_sandbox_v2.py
"""
from __future__ import annotations

import sys
import uuid

import httpx
import pytest
import pytest_asyncio

sys.path.insert(0, "/app/backend")
from server import app  # noqa: E402
from core import db  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


# ---------------------------------------------------------------------------
# J.1 — POST / GET / PATCH / EXIT
# ---------------------------------------------------------------------------
async def test_create_session_returns_session_id_and_ttl(client):
    r = await client.post("/api/sandbox/v2/sessions", json={
        "name": "Sam Director", "role": "ned", "org_type": "bank",
        "hope": "Want refusal in action.",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["session_id"]
    assert data["expires_at"]
    assert data["state"] == "WELCOME"
    assert data["role"] == "ned"
    assert data["org_type"] == "bank"
    assert data["hope"] == "Want refusal in action."


async def test_create_session_rejects_invalid_role(client):
    r = await client.post("/api/sandbox/v2/sessions", json={
        "name": "X", "role": "supreme_leader", "org_type": "bank",
    })
    assert r.status_code == 422, r.text


async def test_create_session_accepts_optional_hope(client):
    r = await client.post("/api/sandbox/v2/sessions", json={
        "name": "X", "role": "ceo", "org_type": "saas",
    })
    assert r.status_code == 200
    assert r.json()["hope"] is None


async def test_get_session_round_trip(client):
    create = await client.post("/api/sandbox/v2/sessions", json={
        "name": "Mara", "role": "ceo", "org_type": "saas", "hope": "Show me citations.",
    })
    sid = create.json()["session_id"]
    r = await client.get(f"/api/sandbox/v2/sessions/{sid}")
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["id"] == sid
    assert rec["name"] == "Mara"
    assert rec["state"] == "WELCOME"
    assert rec["role"] == "ceo"


async def test_get_session_404_for_unknown(client):
    r = await client.get(f"/api/sandbox/v2/sessions/{uuid.uuid4()}")
    assert r.status_code == 404


async def test_patch_session_advances_state_and_payload(client):
    create = await client.post("/api/sandbox/v2/sessions", json={
        "name": "Sam", "role": "ned", "org_type": "bank",
    })
    sid = create.json()["session_id"]
    r = await client.patch(f"/api/sandbox/v2/sessions/{sid}", json={
        "state": "STEP_1_SOLVA",
        "payload": {"solva_session_id": "solva-xyz"},
    })
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["state"] == "STEP_1_SOLVA"
    assert rec["solva_session_id"] == "solva-xyz"


async def test_patch_session_rejects_unknown_state(client):
    create = await client.post("/api/sandbox/v2/sessions", json={
        "name": "Sam", "role": "ned", "org_type": "bank",
    })
    sid = create.json()["session_id"]
    r = await client.patch(f"/api/sandbox/v2/sessions/{sid}", json={
        "state": "WANDERING_THE_VOID",
    })
    assert r.status_code == 422


async def test_patch_payload_whitelists_keys(client):
    create = await client.post("/api/sandbox/v2/sessions", json={
        "name": "Sam", "role": "ned", "org_type": "bank",
    })
    sid = create.json()["session_id"]
    r = await client.patch(f"/api/sandbox/v2/sessions/{sid}", json={
        "payload": {
            "studio_state": {"draft_built": True, "added_sentence": None, "refused_sentence": None},
            "evil_field": "zomg",
        },
    })
    assert r.status_code == 200
    rec = r.json()
    assert rec["studio_state"]["draft_built"] is True
    assert "evil_field" not in rec


async def test_exit_session_marks_exited_and_preserves(client):
    create = await client.post("/api/sandbox/v2/sessions", json={
        "name": "Sam", "role": "ned", "org_type": "bank",
    })
    sid = create.json()["session_id"]
    r = await client.post(f"/api/sandbox/v2/sessions/{sid}/exit", json={})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # Still readable for the 7-day TTL window.
    r2 = await client.get(f"/api/sandbox/v2/sessions/{sid}")
    assert r2.status_code == 200
    assert r2.json()["exited_at"]


async def test_legacy_endpoints_still_reachable(client):
    """The Sandbox UX rebuild adds /v2 endpoints purely additively;
    the legacy /api/sandbox/templates path must keep working so the
    old /sandbox/legacy fallback flow stays alive for 30 days."""
    r = await client.get("/api/sandbox/templates")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, (list, dict))
    if isinstance(body, list):
        assert len(body) > 0


# ---------------------------------------------------------------------------
# J.2 — sandbox flag accepted on Solva v2 session create
# ---------------------------------------------------------------------------
async def test_solva_v2_accepts_sandbox_flag(client):
    """sandbox=true on POST /api/solva/v2/sessions is purely additive
    (the orchestrator persists it; the FE state machine uses it to skip
    the depth round). It must not break the existing flow."""
    # Register an account so Solva v2 is reachable.
    email = f"phase-j-{uuid.uuid4().hex[:10]}@example.com"
    pw = "Phase-J-Sandbox-2026!"
    rr = await client.post("/api/auth/register", json={
        "email": email, "password": pw, "name": "Phase J Probe",
    })
    assert rr.status_code == 200, rr.text
    token = rr.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    body = {
        "intent": "We have an 8-week window to commit to a divestment or pull back.",
        "submodule": "develop_strategy",
        "auto_cluster": True,
        "sandbox": True,
    }
    r = await client.post("/api/solva/v2/sessions", json=body, headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["cluster_id"]
    # The flag is persisted on the session record (visible via GET).
    sid = data["id"]
    rg = await client.get(f"/api/solva/v2/sessions/{sid}", headers=h)
    assert rg.status_code == 200
    assert rg.json().get("sandbox") is True


# ---------------------------------------------------------------------------
# J.1 — Welcome creates a disposable account + JWT (Bearer fallback)
# ---------------------------------------------------------------------------
async def test_create_session_returns_bearer_token_and_account_id(client):
    r = await client.post("/api/sandbox/v2/sessions", json={
        "name": "Sam", "role": "ned", "org_type": "bank",
    })
    assert r.status_code == 200
    data = r.json()
    assert data.get("access_token")
    assert data.get("refresh_token")
    assert data.get("account_id")
    # The disposable account is real and `is_sandbox=True`.
    acc = await db.accounts.find_one({"id": data["account_id"]})
    assert acc is not None
    assert acc["is_sandbox"] is True
    assert acc["sandbox_v2_session_id"] == data["session_id"]


async def test_create_session_bearer_works_against_solva_v2(client):
    """The disposable JWT minted on welcome creation must be usable
    against the auth-gated Solva v2 endpoints — that's the whole point."""
    r = await client.post("/api/sandbox/v2/sessions", json={
        "name": "Sam", "role": "ned", "org_type": "bank",
    })
    assert r.status_code == 200
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    sr = await client.post("/api/solva/v2/sessions", json={
        "intent": "We have a 3-year strategic refresh due and the CFO is sceptical about the cash to back it.",
        "submodule": "develop_strategy",
        "auto_cluster": True,
        "sandbox": True,
    }, headers=h)
    assert sr.status_code == 200, sr.text


# ---------------------------------------------------------------------------
# J.5 — corpus health (verbatim Sandbox Content Pack)
# ---------------------------------------------------------------------------
async def test_corpus_health_no_breaks_no_drafts():
    """Run the corpus's own end-to-end health check. Verifies:
       - all 5 contexts present
       - 64 (role × org_type) cells all return non-empty content
       - Pulse signal source citations resolve to Step 3 source docs
       - composed drafts reference all 3 source docs
       - zero DRAFT markers (content pack is production-ready)
    """
    from sandbox_v2_corpus import corpus_health
    h = corpus_health()
    assert h["context_count"] == 5
    assert sorted(h["contexts"]) == ["bank", "government", "healthcare", "logistics", "technology"]
    assert h["cells_checked"] == 64    # 8 org_types × 8 roles
    assert h["draft_markers"] == 0
    assert h["breaks"] == [], f"inter-connection breaks: {h['breaks'][:5]}"


async def test_corpus_routing_listed_corporate_operational_to_logistics():
    """Pack rule: listed_corporate → bank, OR logistics if role is operational."""
    from sandbox_v2_corpus import route_org_type
    assert route_org_type("listed_corporate", "ned") == "bank"
    assert route_org_type("listed_corporate", "ceo") == "bank"
    # Operational roles → logistics per the pack qualifier
    assert route_org_type("listed_corporate", "cfo") == "logistics"
    assert route_org_type("listed_corporate", "coo") == "logistics"
    assert route_org_type("listed_corporate", "exco_member") == "logistics"


async def test_corpus_routing_pre_ipo_and_other():
    from sandbox_v2_corpus import route_org_type
    assert route_org_type("pre_ipo", "ceo") == "bank"
    assert route_org_type("other", "ceo") == "technology"
    assert route_org_type("saas", "ceo") == "technology"
    assert route_org_type("government", "ceo") == "government"


async def test_corpus_routing_government_role_overrides_context():
    """Pack rule: government_executive → use Government context regardless
    of organisation type if user signals public sector context.

    Implemented in route_role: when context is government, government_executive
    role is the bucket. We also verify that the Government context returns
    government-style opening questions for the role bucket."""
    from sandbox_v2_corpus import pick_opening_question
    q = pick_opening_question("government_executive", "government", seed=0)
    assert "Cabinet" in q or "Directorate" in q or "policy" in q.lower()


async def test_corpus_walk_each_context_returns_full_payload():
    """Walk each of the 5 contexts as a CEO and confirm Step 1..4 content
    is present and non-trivial."""
    from sandbox_v2_corpus import (
        pick_opening_question, pick_fallback_situation,
        pick_pulse_signals, pick_studio_sources, pick_composed_draft,
        pick_provenance_refusal, pick_cycle_snapshot,
    )
    walks = [
        ("ceo", "bank"),
        ("ceo", "healthcare"),
        ("ceo", "logistics"),
        ("ceo", "saas"),
        ("government_executive", "government"),
    ]
    for role, org in walks:
        oq = pick_opening_question(role, org, seed=0)
        assert len(oq) > 80, f"opening question too short for ({role}, {org})"
        fb = pick_fallback_situation(role, org)
        assert len(fb) > 200, f"fallback situation too short for ({role}, {org})"
        sigs = pick_pulse_signals(role, org)
        assert len(sigs) == 3
        for s in sigs:
            assert s["title"] and s["pattern"] and s["next_move"]
            assert s["implication"], f"missing implication for ({role}, {org}) signal {s['id']}"
            assert isinstance(s["source_citations"], list) and len(s["source_citations"]) >= 2
        docs = pick_studio_sources(role, org)
        assert len(docs) == 3
        for d in docs:
            assert d["id"] and d["title"] and d["body"] and d["keywords"]
        draft = pick_composed_draft(role, org)
        assert isinstance(draft.get("paragraphs"), list) and len(draft["paragraphs"]) == 4
        assert pick_provenance_refusal(role, org).startswith("This claim isn't sourced")
        snap = pick_cycle_snapshot(role, org)
        assert len(snap["timeline"]) >= 7
        assert len(snap["open_items"]) >= 4
        assert len(snap["strategic_baseline"]) >= 4
        assert len(snap["pulse_items"]) >= 3
        assert snap["voice"].startswith("This is a snapshot")


async def test_corpus_bank_provenance_refusal_is_pack_verbatim():
    """The Bank refusal voice is taken verbatim from the pack §3 (Bank
    Step 3 provenance demonstration)."""
    from sandbox_v2_corpus import pick_provenance_refusal
    pack_verbatim = (
        "This claim isn't sourced from anything in your materials. The source documents discuss the current "
        "trajectory but don't compare it to historical patterns. We can't add it without a citation. If you "
        "have material that supports it, attach it and we can incorporate."
    )
    assert pick_provenance_refusal("ned", "bank") == pack_verbatim


# ---------------------------------------------------------------------------
# J.5 (cont) — corpus selectors round-trip via HTTP, on top of the pack
# ---------------------------------------------------------------------------
async def test_opening_question_endpoint_uses_pack(client):
    """The /opening-question endpoint should return the verbatim pack
    text for a NED at a Bank — one of the three known variants."""
    r = await client.post("/api/sandbox/v2/sessions", json={
        "name": "Sam", "role": "ned", "org_type": "bank",
    })
    sid = r.json()["session_id"]
    rq = await client.get(f"/api/sandbox/v2/sessions/{sid}/opening-question")
    assert rq.status_code == 200
    q = rq.json()["question"]
    pack_variants = [
        "It's Sunday evening. The audit committee pack has landed. Three notes flag provisioning adequacy. Two flag concentration drift. The external auditor's letter is buried in appendix four. What's the question that wasn't put on the agenda?",
        "Management's narrative says provisioning is adequate. The numbers don't quite agree. You've sat on this board for four years and you've seen this pattern before. What does your experience tell you about how this ends?",
        "The Risk Committee meets Tuesday. The CBK self-assessment on AML is due to the regulator the following week. The sequence matters more than the management note suggests. What's the order in which the questions should be asked?",
    ]
    assert q in pack_variants


async def test_studio_sources_endpoint_returns_three_chips(client):
    r = await client.post("/api/sandbox/v2/sessions", json={
        "name": "Sam", "role": "ned", "org_type": "bank",
    })
    sid = r.json()["session_id"]
    rq = await client.get(f"/api/sandbox/v2/sessions/{sid}/studio-sources")
    assert rq.status_code == 200
    sources = rq.json()["sources"]
    assert isinstance(sources, list) and len(sources) == 3
    titles = [s["title"] for s in sources]
    # Pack §Bank Step 3 — three named source documents
    assert any("Q1 2026" in t for t in titles)
    assert any("Risk Committee" in t for t in titles)
    assert any("Thematic Review" in t for t in titles)
    for s in sources:
        assert s.get("keywords")


async def test_cycle_snapshot_endpoint_returns_pack_timeline(client):
    r = await client.post("/api/sandbox/v2/sessions", json={
        "name": "Sam", "role": "ned", "org_type": "bank",
    })
    sid = r.json()["session_id"]
    rq = await client.get(f"/api/sandbox/v2/sessions/{sid}/cycle-snapshot")
    assert rq.status_code == 200
    snap = rq.json()["snapshot"]
    # Pack §Bank Step 4 — 8 timeline anchors, 5 open items, 4 strategic baseline lines
    assert len(snap["timeline"]) == 8
    assert len(snap["open_items"]) == 5
    assert len(snap["strategic_baseline"]) == 4
    # The pack includes a "CBK Supervisory Letter" anchor specific to bank
    anchors = [t["anchor"] for t in snap["timeline"]]
    assert any("CBK" in a for a in anchors)


# ---------------------------------------------------------------------------
# J.3 — Studio "add a sentence" provenance check (with pack content)
# ---------------------------------------------------------------------------
async def test_studio_add_sentence_accepts_sourced_claim(client):
    r = await client.post("/api/sandbox/v2/sessions", json={
        "name": "Sam", "role": "ned", "org_type": "bank",
    })
    sid = r.json()["session_id"]
    # Pack Bank Doc 2 contains "real estate", "31.2%", "ICAAP", "concentration"
    rs = await client.post(f"/api/sandbox/v2/sessions/{sid}/studio/add-sentence", json={
        "sentence": "Real estate concentration is approaching the ICAAP threshold faster than the linear projection suggests.",
    })
    assert rs.status_code == 200, rs.text
    data = rs.json()
    assert data["accepted"] is True
    assert data["citation"]["sources"]


async def test_studio_add_sentence_refuses_with_pack_voice(client):
    r = await client.post("/api/sandbox/v2/sessions", json={
        "name": "Sam", "role": "ned", "org_type": "bank",
    })
    sid = r.json()["session_id"]
    rs = await client.post(f"/api/sandbox/v2/sessions/{sid}/studio/add-sentence", json={
        "sentence": "Customers love eating jellybeans on Tuesdays.",
    })
    assert rs.status_code == 200
    data = rs.json()
    assert data["accepted"] is False
    assert data["reason"] == "no_source"
    # Pack Bank refusal voice — verbatim
    assert "This claim isn't sourced" in data["message"]
    assert "we can incorporate" in data["message"].lower() or "we can incorporate" in data["message"]


# ---------------------------------------------------------------------------
# J.4 — Save & send (delivery_mode varies by env)
# ---------------------------------------------------------------------------
async def test_save_and_send_persists_email_and_returns_resume_url(client):
    r = await client.post("/api/sandbox/v2/sessions", json={
        "name": "Sam", "role": "ned", "org_type": "bank",
    })
    sid = r.json()["session_id"]
    rs = await client.post(f"/api/sandbox/v2/sessions/{sid}/save-and-send", json={
        "email": "phasej.demo@example.com",
    })
    assert rs.status_code == 200, rs.text
    data = rs.json()
    assert data["ok"] is True
    assert data["email"] == "phasej.demo@example.com"
    assert data["resume_url"].endswith(f"token={sid}")
    assert data["delivery_mode"] in {"sent", "noop", "error"}
    rg = await client.get(f"/api/sandbox/v2/sessions/{sid}")
    assert rg.json()["captured_email"] == "phasej.demo@example.com"
