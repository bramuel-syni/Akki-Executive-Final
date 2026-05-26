"""Phase D Solva Cleanup — wire-check + endpoint invariants.

D.1 — briefing deck slide copy + button flow + suppression state.
D.3 — Chat context-passing chip injection.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

REPO = Path(__file__).resolve().parents[2]
SLIDES_JS = REPO / "frontend" / "src" / "data" / "solva-briefings.js"
DECK_JSX = REPO / "frontend" / "src" / "components" / "solva" / "SolvaBriefingDeck.jsx"
SOLVA_LANDING = REPO / "frontend" / "src" / "components" / "solva" / "SolvaLanding.jsx"
SOLVA_SESSION = REPO / "frontend" / "src" / "pages" / "SolvaPhaseDSession.jsx"
CHAT = REPO / "frontend" / "src" / "pages" / "Chat.jsx"


def _read(p: Path) -> str:
    assert p.exists(), f"missing file: {p}"
    return p.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────
# D.1 — slide copy verbatim
# ─────────────────────────────────────────────────────────────────
VERBATIM_TITLES = [
    # Seek Clarity (4)
    "Solva seeks clarity.",
    "Speak plainly. That's it.",
    "A short, focused conversation.",
    "Have your context within reach.",
    # Test Your Hypothesis (4)
    "Bring a theory. Solva will pressure-test it.",
    "State your hypothesis up front.",
    "A structured stress test.",
    "Bring the evidence you'd actually defend with.",
    # Develop Strategy (4)
    "Build the strategy with you, not for you.",
    "Frame the goal and the constraints.",
    "A working outline by the end.",
    "Know your boundaries before you start.",
    # See From Different Perspective (4)
    "Step out of your seat for a minute.",
    "Describe the situation, then pick the lenses.",
    "Multiple lenses, side by side.",
    "Some perspectives may sting.",
]


def test_phase_d_slides_canonical_data_file_exists():
    src = _read(SLIDES_JS)
    assert "export const SOLVA_AREAS" in src
    assert '"seek-clarity"' in src
    assert '"test-hypothesis"' in src
    assert '"develop-strategy"' in src
    assert '"different-perspective"' in src


@pytest.mark.parametrize("title", VERBATIM_TITLES)
def test_phase_d_slide_title_verbatim(title: str):
    src = _read(SLIDES_JS)
    assert title in src, f"Verbatim slide title missing: {title!r}"


def test_phase_d_slide_body_anchor_phrases():
    """Spot-check verbatim body phrases across all 4 areas."""
    src = _read(SLIDES_JS)
    must_contain = [
        # Seek Clarity
        "Use it for: board calls, regulator responses",
        "3 to 7 questions, depending on complexity",
        # Test Your Hypothesis
        "investment theses, market bets",
        "Plan for 10 to 20 minutes. The harder your hypothesis",
        # Develop Strategy
        "2 to 4 viable paths with honest trade-offs",
        "Plan for 15 to 30 minutes",
        # Different Perspective
        "2 to 5 stakeholder perspectives",
        "If a regulator would call your plan reckless",
    ]
    for phrase in must_contain:
        assert phrase in src, f"Body phrase missing: {phrase!r}"


def test_phase_d_area_to_submodule_mapping():
    src = _read(SLIDES_JS)
    assert "AREA_TO_SUBMODULE" in src
    assert '"seek-clarity": "seek_clarity"' in src
    assert '"test-hypothesis": "simulate_hypothesis"' in src
    assert '"develop-strategy": "develop_strategy"' in src
    assert '"different-perspective": "get_perspective"' in src


# ─────────────────────────────────────────────────────────────────
# D.1 — deck component button flow + suppression
# ─────────────────────────────────────────────────────────────────
def test_phase_d_deck_buttons_present():
    src = _read(DECK_JSX)
    for testid in (
        'data-testid="solva-briefing-deck"',
        'data-testid="solva-briefing-title"',
        'data-testid="solva-briefing-body"',
        'data-testid="solva-briefing-skip-btn"',
        'data-testid="solva-briefing-back-btn"',
        'data-testid="solva-briefing-next-btn"',
        'data-testid="solva-briefing-gotit-btn"',
        'data-testid="solva-briefing-suppress-checkbox"',
        'data-testid="solva-briefing-progress"',
    ):
        assert testid in src, f"Deck testid missing: {testid}"


def test_phase_d_deck_first_word_oxblood():
    src = _read(DECK_JSX)
    # First-word rendered with var(--oxblood) color.
    assert 'data-testid="solva-briefing-title-first-word"' in src
    assert 'color: "var(--oxblood)"' in src


def test_phase_d_deck_suppression_logic():
    src = _read(DECK_JSX)
    # Increment posted on open.
    assert '"action": "increment"' in src or 'action: "increment"' in src
    # Suppress posted on (got_it + suppressCheck).
    assert 'action: "suppress"' in src
    # Suppression check shows from visit_count >= 1 (i.e. visit count
    # of 1 BEFORE this open's increment ⇒ this is the 2nd visit).
    assert "state.visit_count >= 1" in src


def test_phase_d_deck_reopen_via_info_icon():
    src = _read(SOLVA_SESSION)
    # (i) info icon next to composer.
    assert 'data-testid="solva-briefing-reopen-btn"' in src
    # Force-open bypasses suppression.
    assert "force={true}" in src
    # Imports the deck.
    assert "SolvaBriefingDeck" in src
    assert "SUBMODULE_TO_AREA" in src


def test_phase_d_deck_wired_into_landing():
    src = _read(SOLVA_LANDING)
    assert "SolvaBriefingDeck" in src
    assert "setBriefingOpen" in src
    assert "SUBMODULE_TO_AREA" in src
    # Card selection routes through the deck before navigating.
    assert "_navigateAfterCard" in src
    assert "onBriefingClose" in src


# ─────────────────────────────────────────────────────────────────
# D.1 — backend endpoint contract (live in-process via AsyncClient)
# ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_phase_d_briefing_state_endpoint_lifecycle():
    """Exercise the full lifecycle: get → increment → get → suppress
    → get → unsuppress → get. Uses an in-process TestClient with a
    seeded account."""
    from server import app  # noqa: F401  – ensures router is mounted
    from core import db, hash_password
    from datetime import datetime, timezone
    import uuid

    aid = f"test-d1-{uuid.uuid4().hex[:8]}"
    email = f"d1-{uuid.uuid4().hex[:6]}@test.local"
    await db.accounts.insert_one({
        "id": aid,
        "email": email,
        "password_hash": hash_password("Pw!1234567Abc"),
        "name": "D1 Tester",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tier": "executive",
        "mfa_enrolled": False,
        "declared_role": "executive",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Login
        r = await c.post("/api/auth/login", json={"email": email, "password": "Pw!1234567Abc"})
        assert r.status_code == 200, r.text
        body = r.json()
        token = body.get("access_token") or body.get("token")
        assert token, body
        hdr = {"Authorization": f"Bearer {token}"}

        # 1. Initial GET — no row yet.
        r = await c.get("/api/solva/briefing/state?area=seek-clarity", headers=hdr)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s == {"area": "seek-clarity", "visit_count": 0, "suppressed": False, "suppressed_at": None}

        # 2. Increment.
        r = await c.post("/api/solva/briefing/state", headers=hdr,
                         json={"area": "seek-clarity", "action": "increment"})
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["visit_count"] == 1
        assert s["suppressed"] is False

        # 3. Increment again.
        r = await c.post("/api/solva/briefing/state", headers=hdr,
                         json={"area": "seek-clarity", "action": "increment"})
        s = r.json()
        assert s["visit_count"] == 2

        # 4. Suppress.
        r = await c.post("/api/solva/briefing/state", headers=hdr,
                         json={"area": "seek-clarity", "action": "suppress"})
        s = r.json()
        assert s["suppressed"] is True
        assert s["suppressed_at"] is not None

        # 5. GET — suppression sticky.
        r = await c.get("/api/solva/briefing/state?area=seek-clarity", headers=hdr)
        s = r.json()
        assert s["suppressed"] is True
        assert s["visit_count"] == 2  # not bumped by suppress

        # 6. Unsuppress.
        r = await c.post("/api/solva/briefing/state", headers=hdr,
                         json={"area": "seek-clarity", "action": "unsuppress"})
        s = r.json()
        assert s["suppressed"] is False
        assert s["suppressed_at"] is None
        assert s["visit_count"] == 2

        # 7. Unknown area → 400.
        r = await c.get("/api/solva/briefing/state?area=garbage", headers=hdr)
        assert r.status_code == 400

        # 8. Per-area isolation — develop-strategy still at 0.
        r = await c.get("/api/solva/briefing/state?area=develop-strategy", headers=hdr)
        s = r.json()
        assert s["visit_count"] == 0
        assert s["suppressed"] is False

    # Cleanup
    await db.solva_briefing_state.delete_many({"user_id": aid})
    await db.accounts.delete_one({"id": aid})


# ─────────────────────────────────────────────────────────────────
# D.3 — Chat context-passing chip injection
# ─────────────────────────────────────────────────────────────────
def test_phase_d3_chat_doc_param_calls_attach():
    """Chat?doc=<id> must (a) mint a chat and (b) register the doc
    as an attachment via /chats/{cid}/attach so the AI gets the
    doc body in its first message context."""
    src = _read(CHAT)
    # The bootstrap effect must POST /chats/{cid}/attach with the doc.
    assert "/chats/${data.id}/attach" in src, (
        "Chat ?doc= flow must call /chats/{cid}/attach so the doc "
        "lands as a real attachment + body gets pulled into AI context"
    )
    # The chip object carries a linked_context: true marker so the
    # render layer can render it differently if desired.
    assert "linked_context: true" in src


def test_phase_d3_chat_doc_flow_graceful_degradation():
    """If /chats/{cid}/attach fails, the chat surface still works —
    the chat was minted, the prompt was pre-filled, no error toast."""
    src = _read(CHAT)
    # The attach call must be wrapped in try/catch.
    idx = src.find("/chats/${data.id}/attach")
    assert idx != -1
    pre = src[max(0, idx - 200):idx]
    assert "try {" in pre


# ─────────────────────────────────────────────────────────────────
# D.3 — Solva already passes context via takeToSolva (existing infra)
# ─────────────────────────────────────────────────────────────────
def test_phase_d3_solva_context_passing_via_existing_helper():
    """Phase F.2.A's takeToSolva already implements ctx_type / ctx_id
    as seed_kind / seed_id query params. The brief said to MATCH
    existing patterns — verify the helper remains intact and is
    invoked from the document detail surface."""
    helper = REPO / "frontend" / "src" / "lib" / "takeToSolva.js"
    assert helper.exists()
    src = helper.read_text("utf-8")
    assert "seed_kind" in src
    assert "seed_id" in src
    # Sole call site that still ships a Solva CTA from a context surface.
    handoff = REPO / "frontend" / "src" / "components" / "shell" / "HandoffActions.jsx"
    handoff_src = handoff.read_text("utf-8")
    assert "takeToSolva" in handoff_src
