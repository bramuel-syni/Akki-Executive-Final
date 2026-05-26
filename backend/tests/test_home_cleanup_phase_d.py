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
    email = f"d1-{uuid.uuid4().hex[:6]}@example.com"
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


@pytest.mark.asyncio
async def test_phase_d3_chat_linked_context_lifecycle():
    """D.3 end-to-end (option b — full persistence) on the live FastAPI
    app. Asserts:

      1. POST /chats with linked_context: {ctx_type, ctx_id} persists
         a resolved snapshot (title, excerpt, href, attached_at) on
         the chat row.
      2. GET /chats/{id} returns the same linked_context block.
      3. PATCH /chats/{id} with clear_linked_context: true $unsets it.
      4. Resolving a non-existent ctx_id silently drops linked_context
         (no error, no chip).
    """
    from server import app  # noqa: F401
    from core import db, hash_password
    from datetime import datetime, timezone
    import uuid

    aid = f"test-d3-{uuid.uuid4().hex[:8]}"
    email = f"d3-{uuid.uuid4().hex[:6]}@example.com"
    cid = f"ctx-d3-{uuid.uuid4().hex[:8]}"
    did = f"doc-d3-{uuid.uuid4().hex[:8]}"

    # Seed: account + context + membership + document.
    await db.accounts.insert_one({
        "id": aid, "email": email,
        "password_hash": hash_password("Pw!1234567Abc"),
        "name": "D3 Tester",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tier": "executive", "mfa_enrolled": False,
        "declared_role": "executive",
    })
    await db.contexts.insert_one({
        "id": cid, "name": "D3 Test Co",
        "owner_account_id": aid, "type": "executive_personal",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}",
        "account_id": aid, "context_id": cid,
        "role": "executive", "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.documents.insert_one({
        "id": did, "context_id": cid,
        "name": "Q3 Risk Report.pdf",
        "original_filename": "Q3 Risk Report.pdf",
        "extracted_text": "This is a sample extracted text from the Q3 risk report. "
                          "Key findings: regulator escalation risk on Pillar 2.",
        "preview": "Q3 risk report preview.",
        "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            # Auth
            r = await c.post("/api/auth/login",
                             json={"email": email, "password": "Pw!1234567Abc"})
            assert r.status_code == 200, r.text
            token = (r.json().get("access_token") or r.json().get("token"))
            hdr = {"Authorization": f"Bearer {token}",
                   "X-Active-Context": cid}

            # 1. Create chat with linked_context.
            r = await c.post("/api/chats", headers=hdr, json={
                "title": "Risk-report deep dive",
                "model_id": "claude-sonnet-4-5",
                "shielding_policy": "auto",
                "context_id": cid,
                "linked_context": {"ctx_type": "document", "ctx_id": did},
            })
            assert r.status_code == 200, r.text
            chat = r.json()
            assert "linked_context" in chat, f"linked_context missing: {chat}"
            lc = chat["linked_context"]
            assert lc["ctx_type"] == "document"
            assert lc["ctx_id"] == did
            assert lc["title"] == "Q3 Risk Report.pdf"
            assert "Q3 risk report" in lc["excerpt"]
            assert lc["href"] == f"/app/workspace?doc={did}"
            assert lc["attached_at"], "attached_at must be set"
            chat_id = chat["id"]

            # 2. GET re-reads the same payload (resume contract).
            r = await c.get(f"/api/chats/{chat_id}", headers=hdr)
            assert r.status_code == 200
            assert r.json()["linked_context"]["ctx_id"] == did

            # 3. PATCH clear.
            r = await c.patch(f"/api/chats/{chat_id}", headers=hdr,
                              json={"clear_linked_context": True})
            assert r.status_code == 200, r.text
            assert "linked_context" not in r.json() or r.json().get("linked_context") is None

            # 4. Non-existent ctx_id → silent miss (no chip persisted,
            #    chat still created OK).
            r = await c.post("/api/chats", headers=hdr, json={
                "title": "Phantom link",
                "model_id": "claude-sonnet-4-5",
                "shielding_policy": "auto",
                "context_id": cid,
                "linked_context": {"ctx_type": "document",
                                   "ctx_id": "doc-does-not-exist-xyz"},
            })
            assert r.status_code == 200, r.text
            assert "linked_context" not in r.json() or r.json().get("linked_context") is None

            # 5. Invalid ctx_type → 422 (schema validator).
            r = await c.post("/api/chats", headers=hdr, json={
                "title": "Bad type",
                "model_id": "claude-sonnet-4-5",
                "shielding_policy": "auto",
                "context_id": cid,
                "linked_context": {"ctx_type": "garbage",
                                   "ctx_id": "anything"},
            })
            assert r.status_code == 422, r.text
    finally:
        # Cleanup
        await db.chats.delete_many({"account_id": aid})
        await db.chat_audit_log.delete_many({"account_id": aid})
        await db.documents.delete_many({"id": did})
        await db.memberships.delete_many({"account_id": aid})
        await db.contexts.delete_many({"id": cid})
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


# ─────────────────────────────────────────────────────────────────
# D.1 — bug guard: SolvaBriefingDeck must live in SolvaLanding's
# parent scope (NOT inside DisambiguatorDialog). The deck references
# briefingArea / briefingOpen / onBriefingClose which only exist in
# the parent component; placing it inside the sub-component would
# throw "ReferenceError: briefingArea is not defined" at render.
# ─────────────────────────────────────────────────────────────────
def test_phase_d_landing_deck_lives_in_parent_scope_not_disambiguator():
    src = _read(SOLVA_LANDING)
    parts = src.split("function DisambiguatorDialog")
    assert len(parts) == 2, "DisambiguatorDialog function not found in expected shape"
    parent_body, disambig_body = parts
    assert "<SolvaBriefingDeck" in parent_body, (
        "SolvaBriefingDeck must be rendered in SolvaLanding's parent "
        "scope (where briefingArea / briefingOpen / onBriefingClose live)"
    )
    assert "<SolvaBriefingDeck" not in disambig_body, (
        "SolvaBriefingDeck must NOT be rendered inside DisambiguatorDialog "
        "(scope bug — parent-only state vars would be undefined there)"
    )


# ─────────────────────────────────────────────────────────────────
# D.3 — ctx_type / ctx_id canonical aliases (Solva surface)
# ─────────────────────────────────────────────────────────────────
def test_phase_d3_solva_app_accepts_ctx_type_ctx_id_alias():
    """SolvaApp.jsx reads BOTH ctx_type/ctx_id (canonical) AND
    seed_kind/seed_id (legacy alias) on mount, with both resolving
    identically into the seed handoff plumbing."""
    src = (REPO / "frontend" / "src" / "pages" / "SolvaApp.jsx").read_text("utf-8")
    assert 'params.get("ctx_type")' in src
    assert 'params.get("ctx_id")' in src
    assert 'params.get("seed_kind")' in src
    assert 'params.get("seed_id")' in src
    # The URL cleanup pass deletes both query-param forms after capture.
    assert 'next.delete("ctx_type")' in src
    assert 'next.delete("ctx_id")' in src


def test_phase_d3_solva_session_accepts_ctx_type_ctx_id_alias():
    """SolvaPhaseDSession.jsx (direct URL landing) also accepts the
    new aliases. The capture line MUST OR-fall-through both forms so
    a single seed flows downstream."""
    src = _read(SOLVA_SESSION)
    assert 'searchParams.get("ctx_type") || searchParams.get("seed_kind")' in src
    assert 'searchParams.get("ctx_id")   || searchParams.get("seed_id")' in src


# ─────────────────────────────────────────────────────────────────
# D.3 — Chat backend: linked_context schema + resolver + injection
# ─────────────────────────────────────────────────────────────────
CHAT_BE = REPO / "backend" / "routers" / "chat.py"


def test_phase_d3_chat_backend_linked_context_schema():
    src = CHAT_BE.read_text("utf-8")
    assert "class LinkedContextIn(BaseModel)" in src
    assert "ctx_type: str = Field(min_length=1" in src
    assert "ctx_id:   str = Field(min_length=1" in src
    # Allowlist of ctx_types.
    assert '"document"' in src and '"cycle"' in src and '"work_studio_artefact"' in src
    # `work_studio` shortcut normalises to the canonical name.
    assert 'if v == "work_studio":' in src


def test_phase_d3_chat_backend_create_persists_linked_context():
    src = CHAT_BE.read_text("utf-8")
    create_section = src.split("@router.post(\"/chats\")")[1].split("@router.")[0]
    assert "linked_context" in create_section
    assert "_resolve_linked_context" in create_section
    assert 'rec["linked_context"]' in create_section


def test_phase_d3_chat_backend_resolver_supports_3_ctx_types():
    src = CHAT_BE.read_text("utf-8")
    assert "async def _resolve_linked_context(" in src
    resolver = src.split("async def _resolve_linked_context(")[1].split("\n\nasync def")[0]
    # Each branch reads from the appropriate collection.
    assert "db.documents.find_one(" in resolver
    assert "db.cycles.find_one(" in resolver
    assert "db.work_studio_artefacts.find_one(" in resolver
    # Each returns a canonical envelope.
    for needed in ('"ctx_type": "document"', '"ctx_type": "cycle"',
                   '"ctx_type": "work_studio_artefact"',
                   '"title":', '"excerpt":', '"href":'):
        assert needed in resolver, f"resolver missing key '{needed}'"


def test_phase_d3_chat_backend_clear_via_patch():
    src = CHAT_BE.read_text("utf-8")
    assert "clear_linked_context: Optional[bool]" in src
    assert "body.clear_linked_context is True" in src
    # $unset is the canonical clear path.
    assert 'unset["linked_context"]' in src


def test_phase_d3_chat_backend_injects_linked_context_on_every_turn():
    """Both /messages (sync) AND /messages/stream (SSE) must rebuild
    the linked-context prompt block from a fresh resolve on every
    turn — so deleted items silently drop and Shield runs over the
    re-resolved excerpt each time."""
    src = CHAT_BE.read_text("utf-8")
    import re as _re
    # Count `if linked_block:` blocks that append onto full_prompt_parts.
    matches = _re.findall(
        r"if linked_block:\s*\n\s+full_prompt_parts\.append\(linked_block\)",
        src,
    )
    assert len(matches) >= 2, (
        f"linked_block injection must appear in BOTH send_message AND "
        f"stream_message (found {len(matches)})"
    )
    # The injection block must use the [LINKED_CONTEXT]…[/LINKED_CONTEXT]
    # markers (separate from [GROUNDING] / [ATTACHMENT]).
    assert "[LINKED_CONTEXT]" in src
    assert "[/LINKED_CONTEXT]" in src


# ─────────────────────────────────────────────────────────────────
# D.3 — Chat frontend: chip + URL handler + remove flow
# ─────────────────────────────────────────────────────────────────
def test_phase_d3_chat_frontend_handles_ctx_type_ctx_id_url():
    src = _read(CHAT)
    assert 'searchParams.get("ctx_type")' in src
    assert 'searchParams.get("ctx_id")' in src
    # New chat created with linked_context payload.
    assert "linked_context: { ctx_type: ctxType, ctx_id: ctxId }" in src
    # URL cleanup pass deletes ctx_type + ctx_id after consumption.
    assert 'next.delete("ctx_type")' in src
    assert 'next.delete("ctx_id")' in src


def test_phase_d3_chat_frontend_renders_linked_context_chip():
    src = _read(CHAT)
    assert "function LinkedContextChip" in src
    for tid in (
        'data-testid="chat-linked-context-chip"',
        'data-testid="chat-linked-context-remove"',
        'data-testid="chat-linked-context-title"',
        'data-testid="chat-linked-context-title-unavailable"',
    ):
        assert tid in src, f"missing testid: {tid}"
    # Chip is wired into Composer's prop set.
    assert "linkedContext={activeChat.linked_context" in src
    assert "onRemoveLinkedContext" in src


def test_phase_d3_chat_frontend_remove_chip_persists_clear():
    """The ✕ Remove button calls onRemoveLinkedContext which PATCHes
    {clear_linked_context: true} so the chip doesn't reappear on
    thread resume."""
    src = _read(CHAT)
    remove_section = src.split("const onRemoveLinkedContext")[1].split("const onArchive")[0]
    assert "clear_linked_context: true" in remove_section
    assert "/chats/${activeId}" in remove_section
    # Local state cleanup strips linked_context from both activeChat
    # and the sidebar chats[] row.
    assert "delete merged.linked_context" in remove_section


def test_phase_d3_chat_frontend_chip_muted_state_when_item_gone():
    """Item deleted server-side OR access lost → muted chip with
    "Item no longer available". No error toast (per Acceptance #5)."""
    src = _read(CHAT)
    chip_section = src.split("function LinkedContextChip")[1].split("function ")[0]
    assert "const gone  = !linked?.excerpt" in chip_section
    assert "item no longer available" in chip_section


def test_phase_d3_chat_create_audit_payload_carries_linked_context():
    """Acceptance — privacy/audit: chat.created audit row payload
    must include the resolved linked_context snapshot so Trust Center
    can replay the attach event."""
    src = CHAT_BE.read_text("utf-8")
    create_section = src.split("@router.post(\"/chats\")")[1].split("@router.")[0]
    # The _append_audit payload includes a linked_context key.
    assert '"linked_context": rec.get("linked_context")' in create_section


# ─────────────────────────────────────────────────────────────────
# D.2 — audit writeup recorded in HOME_CLEANUP_LOG.md
# ─────────────────────────────────────────────────────────────────
def test_phase_d2_audit_recorded_in_home_cleanup_log():
    log_path = REPO / "memory" / "sprints" / "HOME_CLEANUP_LOG.md"
    log = log_path.read_text("utf-8")
    assert "## Phase D — Solva surface" in log
    assert "### D.2 — Solva question-generation logic (READ-ONLY audit)" in log
    # Key audit findings must land in the writeup.
    assert "NO LLM-generated questions" in log
    assert "hand-written" in log
    assert "deterministic" in log
    assert "REFLECTION_QUESTIONS" in log


def test_phase_d2_question_bank_docstring_asserts_no_llm_generation():
    src = (REPO / "backend" / "services" / "solva" / "voice" / "question_bank.py").read_text("utf-8")
    assert "NO LLM-generated questions" in src
    assert "deterministic hash-based variant picker" in src



# ─────────────────────────────────────────────────────────────────────
# Phase D — Post-test fixes (2026-05-26)
#
# Tester verified the canonical /app/chat?ctx_type=document&ctx_id=…
# URL works end-to-end, but the actual handoff buttons across the
# codebase were still emitting the LEGACY ?doc= / ?doc_id= / ?seed_kind=
# URL params — so the user's reported bug ("clicking Ask in Chat from
# a document detail page does NOT load the document") was still live.
#
# These tests assert the actual URL each handoff button generates —
# NOT the className or the JSX structure (Phase C tests learned this
# the hard way). Wire tests must check what the user's browser sees.
# ─────────────────────────────────────────────────────────────────────

def test_phase_d_handoff_ask_in_chat_emits_ctx_type_ctx_id():
    """HandoffActions.jsx::onAskInChat must navigate to
    `/app/chat?ctx_type=document&ctx_id=…` (canonical) NOT to
    `/app/chat?doc=…` (legacy)."""
    src = (REPO / "frontend" / "src" / "components" / "shell" / "HandoffActions.jsx").read_text("utf-8")
    # Locate the onAskInChat callback body.
    cb = src.split("const onAskInChat = useCallback(")[1].split("}, [")[0]
    # Strip JS line + block comments so commit-notes mentioning the
    # legacy URL don't trip the matcher.
    code_lines = [ln for ln in cb.splitlines()
                  if not ln.lstrip().startswith("//")
                  and not ln.lstrip().startswith("*")]
    code_only = "\n".join(code_lines)
    # MUST emit the canonical pair.
    assert "ctx_type=document&ctx_id=" in code_only, (
        "onAskInChat must navigate to /app/chat?ctx_type=document&ctx_id=… "
        "(canonical Phase D.3 contract)"
    )
    # MUST NOT emit the legacy form anywhere in this callback's code.
    assert "?doc=" not in code_only, (
        "onAskInChat must NOT emit the legacy ?doc=… URL anymore"
    )


def test_phase_d_take_to_solva_helper_emits_ctx_type_ctx_id():
    """lib/takeToSolva.js must emit `?ctx_type=…&ctx_id=…` (canonical)
    in the URL — NOT `?seed_kind=…&seed_id=…` (legacy)."""
    src = (REPO / "frontend" / "src" / "lib" / "takeToSolva.js").read_text("utf-8")
    # Locate the URLSearchParams construction inside takeToSolva().
    assert 'new URLSearchParams({ ctx_type: String(kind), ctx_id: String(id) })' in src, (
        "takeToSolva must build params with canonical {ctx_type, ctx_id}"
    )
    # Same check for the sync builder.
    assert src.count('new URLSearchParams({ ctx_type: String(kind), ctx_id: String(id) })') >= 2, (
        "Both takeToSolva and takeToSolvaPath must emit canonical params"
    )
    # The legacy form must NOT appear in any URL-building line. (Doc
    # comments referring to the legacy alias are fine — we strip those.)
    code_lines = [ln for ln in src.splitlines()
                  if not ln.lstrip().startswith("*")
                  and not ln.lstrip().startswith("//")]
    code_only = "\n".join(code_lines)
    assert "seed_kind:" not in code_only, (
        "takeToSolva must NOT emit ?seed_kind= in any URL-building code"
    )
    assert "seed_id:" not in code_only, (
        "takeToSolva must NOT emit ?seed_id= in any URL-building code"
    )


def test_phase_d_workspace_ask_in_chat_link_emits_ctx_type_ctx_id():
    """Workspace's "Use in Chat" CTA must emit canonical params.

    E.3 RUNTIME DRAWER FIX (2026-05-26): the legacy inline
    JournalDrawer on Workspace.jsx (with `journal-drawer-continue-chat`
    testid) was archived. Workspace now mounts the universal
    DocumentDrawer, whose "Use in Chat" CTA carries the canonical
    `?ctx_type=document&ctx_id=` URL. We now assert against the
    universal drawer instead of the archived legacy one.
    """
    drawer_src = (REPO / "frontend" / "src" / "components" / "documents" / "DocumentDrawer.jsx").read_text("utf-8")
    # Universal drawer's Chat CTA testid.
    assert 'data-testid="drawer-cta-use-in-chat"' in drawer_src, (
        "Universal DocumentDrawer must expose `drawer-cta-use-in-chat`."
    )
    # MUST emit canonical form via the buildChatUrl helper.
    assert "/app/chat?ctx_type=document&ctx_id=" in drawer_src, (
        "DocumentDrawer 'Use in Chat' CTA must emit canonical "
        "ctx_type/ctx_id URL params."
    )
    # MUST NOT emit legacy form anywhere in the drawer.
    assert "/app/chat?doc=" not in drawer_src, (
        "DocumentDrawer must not emit legacy `?doc=` URL form."
    )


def test_phase_d_document_summary_card_emits_ctx_type_ctx_id():
    """DocumentSummaryCard.jsx::continueInChat must emit canonical
    params, not the legacy ?doc= form."""
    src = (REPO / "frontend" / "src" / "components" / "documents" / "DocumentSummaryCard.jsx").read_text("utf-8")
    fn = src.split("const continueInChat")[1].split("};")[0]
    # Strip line comments.
    code_lines = [ln for ln in fn.splitlines() if not ln.lstrip().startswith("//")]
    code_only = "\n".join(code_lines)
    assert "ctx_type=document&ctx_id=" in code_only
    assert "?doc=" not in code_only, (
        "DocumentSummaryCard.continueInChat must NOT emit ?doc="
    )


def test_phase_d_ned_meeting_ask_chat_emits_ctx_type_ctx_id():
    """NedMeeting.jsx::askChatAboutPaper must emit canonical params,
    not the legacy ?doc_id= form."""
    src = (REPO / "frontend" / "src" / "pages" / "ned" / "NedMeeting.jsx").read_text("utf-8")
    fn = src.split("const askChatAboutPaper")[1].split("};")[0]
    # Strip JS line comments so the test doesn't get tripped up by
    # commit-notes that mention the legacy URL form.
    code_lines = [ln for ln in fn.splitlines() if not ln.lstrip().startswith("//")]
    code_only = "\n".join(code_lines)
    assert "ctx_type=document&ctx_id=" in code_only
    assert "doc_id=" not in code_only, (
        "NedMeeting.askChatAboutPaper must NOT emit ?doc_id="
    )


def test_phase_d_solva_session_accepts_ctx_type_ctx_id_alias():
    """SolvaSession.jsx must accept ctx_type/ctx_id as a canonical
    alias for the legacy seed_kind/seed_id pair. The takeToSolva
    helper now emits the canonical form."""
    src = (REPO / "frontend" / "src" / "pages" / "SolvaSession.jsx").read_text("utf-8")
    # Both query-param forms must be read on mount.
    assert 'searchParams.get("ctx_type")' in src
    assert 'searchParams.get("ctx_id")' in src
    assert 'searchParams.get("seed_kind")' in src  # alias retained
    assert 'searchParams.get("seed_id")' in src   # alias retained


def test_phase_d_no_legacy_chat_doc_url_in_active_code():
    """Sweep — no production frontend file emits `/app/chat?doc=` or
    `/app/chat?doc_id=` anymore. The Chat receiver still SUPPORTS those
    forms for backwards compat, but no NEW handoff code should emit
    them. This is the canonical-form invariant."""
    import os
    fe = REPO / "frontend" / "src"
    offenders = []
    for root, _, files in os.walk(fe):
        for f in files:
            if not (f.endswith(".jsx") or f.endswith(".js")):
                continue
            # Test files + e2e fixtures may reference legacy URLs as
            # part of regression coverage — exclude them.
            if "__tests__" in root or f.startswith("test_"):
                continue
            path = Path(root) / f
            txt = path.read_text(encoding="utf-8", errors="ignore")
            # Strip line-comments + block-comments so we don't catch
            # legacy URLs documented in JSDoc / inline comments.
            cleaned_lines = []
            for ln in txt.splitlines():
                stripped = ln.lstrip()
                if stripped.startswith("//") or stripped.startswith("*"):
                    continue
                cleaned_lines.append(ln)
            cleaned = "\n".join(cleaned_lines)
            if "/app/chat?doc=" in cleaned or "/app/chat?doc_id=" in cleaned:
                offenders.append(str(path.relative_to(REPO)))
            # Also check inline `?doc=` next to /app/chat patterns.
            if "navigate(`/app/chat?doc=" in cleaned:
                offenders.append(str(path.relative_to(REPO)))
    assert not offenders, (
        f"Legacy /app/chat?doc= URLs still present in: {offenders}\n"
        f"Phase D.3 post-test fix requires canonical "
        f"/app/chat?ctx_type=document&ctx_id=… across all surfaces."
    )


def test_phase_d_no_legacy_solva_seed_url_emitted_in_active_code():
    """Sweep — no production frontend file emits `?seed_kind=` /
    `?seed_id=` for Solva navigations anymore. takeToSolva is the
    sole helper and it now emits canonical params. Work-studio
    handoffs are excluded (Phase E still owns that surface)."""
    import os
    fe = REPO / "frontend" / "src"
    offenders = []
    for root, _, files in os.walk(fe):
        for f in files:
            if not (f.endswith(".jsx") or f.endswith(".js")):
                continue
            if "__tests__" in root or f.startswith("test_"):
                continue
            path = Path(root) / f
            rel = str(path.relative_to(REPO))
            txt = path.read_text(encoding="utf-8", errors="ignore")
            # Strip comments.
            cleaned_lines = []
            for ln in txt.splitlines():
                stripped = ln.lstrip()
                if stripped.startswith("//") or stripped.startswith("*"):
                    continue
                cleaned_lines.append(ln)
            cleaned = "\n".join(cleaned_lines)
            # Solva navigations only.
            for marker in (
                "/app/solva?seed_kind=",
                "/app/solva/session/new?seed_kind=",
                "navigate(`/app/solva?seed_kind=",
            ):
                if marker in cleaned:
                    offenders.append(f"{rel} ({marker})")
            # The takeToSolva helper itself must not emit the legacy
            # URL pattern (we already check this in a separate test,
            # but it's worth catching here to make the sweep complete).
            if rel.endswith("takeToSolva.js") and "seed_kind: String(kind)" in cleaned:
                offenders.append(f"{rel} (seed_kind in URLSearchParams)")
    assert not offenders, (
        f"Legacy Solva seed_kind/seed_id URLs still emitted in: {offenders}"
    )


def test_phase_d_handoff_actions_doc_describes_canonical_url():
    """HandoffActions.jsx header docstring must reference the
    canonical `?ctx_type=…&ctx_id=…` URL so future devs maintaining
    the file know the contract."""
    src = (REPO / "frontend" / "src" / "components" / "shell" / "HandoffActions.jsx").read_text("utf-8")
    header = src.split("export default")[0]
    assert "ctx_type=document&ctx_id=" in header, (
        "HandoffActions.jsx header docstring must reference the canonical "
        "?ctx_type=document&ctx_id=… URL contract"
    )


def test_phase_d_post_test_fixes_logged_in_home_cleanup_log():
    """HOME_CLEANUP_LOG.md must contain the 'Phase D — post-test fixes'
    subsection listing every surface updated + the before/after URL
    pattern."""
    log = (REPO / "memory" / "sprints" / "HOME_CLEANUP_LOG.md").read_text("utf-8")
    assert "Phase D — post-test fixes" in log
    # Each updated surface must be enumerated.
    for surface in (
        "HandoffActions.jsx",
        "takeToSolva.js",
        "Workspace.jsx",
        "DocumentSummaryCard.jsx",
        "NedMeeting.jsx",
        "SolvaSession.jsx",
    ):
        assert surface in log, (
            f"Phase D post-test fix log must enumerate '{surface}'"
        )
    # The before/after URL contract must be documented.
    assert "?doc=" in log and "ctx_type=document&ctx_id=" in log
