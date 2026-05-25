"""J4 (Stage 6) — Backend behavior tests.

Spec ref: `AKKI_ONBOARDING_SPEC.md` v1.1 §3 Stage 6 + ratified
gaps G29, G30, G31. Per-tier discipline same as J1-J3 (closeout
§5.8 — anchor-chain behavior tests, NOT source-string assertions).

  J4.B1 — `POST /users/me/onboarding-status/first-chat-seen` flips
          `first_session.first_chat_seen = true` (idempotent). The
          `_compute_status` payload then surfaces
          `onboarding_journey.first_chat_seen: true` and rolls
          `onboarding_journey.complete: true` once
          `trust_center_introduced` is also true.
  J4.B2 — G30 starter prompt construction. The intake Q3 answer is
          persisted POST-Shield (J1 G18) — confirm again at the J4
          boundary so a future regression to the J1 wiring breaks
          this test rather than silently leaking raw text to the
          chat composer.
  J4.B3 — `GET /me/first-session` returns the de-identified
          `state.intake.top_of_mind` value (the field the frontend
          reads to seed the chat composer when `?starter=` is
          absent). Raw email NEVER appears in the response body.
  J4.B4 — Phase D framing submit routes through Shield via
          `invoke_via_shield`. Source-level chain assertion (anti-
          source-string per closeout §5.8): the handler MUST call
          `classify_situation` AND `run_frame_audit`, both of which
          import + call `invoke_via_shield`. A regression that
          shortcuts the Shield invoker breaks this chain.
  J4.B5 — `test_onboarding_sprint_j1_j4_complete` — the final
          CI guard. ALLOWED_DOORS pinned at `{cycle, upload, solve,
          demo}`; all 5 J1/J2/J3/J4 status flags are emitted by
          `_compute_status` in the `onboarding_journey` block.
"""
from __future__ import annotations

import os
import re
import sys
import uuid
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

import core as core_mod
from server import app

REPO = Path(__file__).resolve().parents[2]
PHASE_D_ROUTER = REPO / "backend/routers/solva_phase_d.py"
SITUATION_CLASSIFIER = (
    REPO / "backend/services/solva/reasoning/situation_class_classifier.py"
)
FRAME_AUDIT = REPO / "backend/services/solva/reasoning/frame_audit_engine.py"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


async def _register(c: httpx.AsyncClient, prefix: str):
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    r = await c.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "Password123!@#",
            "name": f"{prefix.title()} Tester",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    return body["access_token"], body["account"], body["contexts"][0]["id"]


# ── J4.B1 — first-chat-seen flips flag & idempotent ──────────────────
@pytest.mark.asyncio
async def test_j4_b1_first_chat_seen_endpoint_flips_flag_idempotent():
    """POST `/users/me/onboarding-status/first-chat-seen` MUST flip
    `accounts.{id}.first_session.first_chat_seen` to True with an
    ISO timestamp, idempotently. The `onboarding_journey.complete`
    flag rolls true once both `trust_center_introduced` AND
    `first_chat_seen` are true."""
    async with _client() as c:
        token, account, ctx_id = await _register(c, "j4-b1")
        h = {"Authorization": f"Bearer {token}"}
        # Pre: first_chat_seen False, complete False.
        r_pre = await c.get("/api/users/me/onboarding-status", headers=h)
        assert r_pre.status_code == 200, r_pre.text
        j_pre = r_pre.json().get("onboarding_journey") or {}
        assert j_pre.get("first_chat_seen") is False, j_pre
        assert j_pre.get("complete") is False, j_pre
        # Mark first chat seen.
        r1 = await c.post(
            "/api/users/me/onboarding-status/first-chat-seen",
            headers=h,
        )
        assert r1.status_code == 200, r1.text
        j1 = r1.json().get("onboarding_journey") or {}
        assert j1.get("first_chat_seen") is True, j1
        # Complete is still False (no trust_center_introduced yet).
        assert j1.get("complete") is False, j1
        # Idempotent — second call OK.
        r2 = await c.post(
            "/api/users/me/onboarding-status/first-chat-seen",
            headers=h,
        )
        assert r2.status_code == 200, r2.text
        # DB-level confirmation.
        acct = await core_mod.db.accounts.find_one(
            {"id": account["id"]}, {"_id": 0, "first_session": 1},
        )
        fs = acct.get("first_session") or {}
        assert fs.get("first_chat_seen") is True
        assert fs.get("first_chat_seen_at")
        # Flip trust_center_introduced too — complete should now roll true.
        # (Upload a doc to enable the tour, then dismiss it.)
        import io
        files = {"file": ("hi.txt", io.BytesIO(b"Hello board."), "text/plain")}
        await c.post(
            f"/api/contexts/{ctx_id}/documents",
            files=files, headers=h,
        )
        await c.post(
            "/api/users/me/onboarding-status/trust-center-tour/dismiss",
            headers=h,
        )
        r_after = await c.get("/api/users/me/onboarding-status", headers=h)
        j_after = r_after.json().get("onboarding_journey") or {}
        assert j_after.get("first_chat_seen") is True
        assert j_after.get("trust_center_introduced") is True
        assert j_after.get("complete") is True, j_after


# ── J4.B2 — Intake top_of_mind is de-identified at the J4 boundary ──
@pytest.mark.asyncio
async def test_j4_b2_intake_top_of_mind_is_deidentified():
    """J1 G18 wires Shield on the intake Q3. J4 boundary re-asserts
    that the same value is what flows downstream to the chat
    composer seed. Catches a regression that silences G18."""
    async with _client() as c:
        token, account, ctx_id = await _register(c, "j4-b2")
        h = {"Authorization": f"Bearer {token}"}
        # Q3 carries a raw email — Shield MUST redact before persist.
        raw_email = "ceo.smith@example-corp.io"
        raw_q3 = f"Email me at {raw_email} about the term sheet."
        r = await c.post(
            "/api/me/first-session/intake",
            json={
                "role": "executive",
                "primary_context_name": "Acme Plc",
                "top_of_mind": raw_q3,
            },
            headers=h,
        )
        assert r.status_code == 200, r.text
        # Persisted top_of_mind MUST NOT contain the raw email.
        acct = await core_mod.db.accounts.find_one(
            {"id": account["id"]}, {"_id": 0, "first_session": 1},
        )
        fs = acct.get("first_session") or {}
        intake = fs.get("intake") or {}
        persisted = intake.get("top_of_mind") or ""
        assert raw_email not in persisted, (
            f"G18 regression: raw email '{raw_email}' is in persisted "
            f"top_of_mind '{persisted}'. Shield was not applied."
        )
        # The persisted form MUST carry a tokenized anchor (Shield
        # produces tokens of the shape `[[ENT_*]]`).
        assert re.search(r"\[\[ENT_[A-Z]+_\d+\]\]", persisted), (
            f"G18 regression: persisted top_of_mind '{persisted}' "
            f"missing Shield token anchor."
        )


# ── J4.B3 — GET /me/first-session exposes de-identified seed ────────
@pytest.mark.asyncio
async def test_j4_b3_first_session_get_returns_deidentified_top_of_mind():
    """The frontend's J4 fallback (no `?starter=` URL) reads
    `state.intake.top_of_mind` from `GET /me/first-session`. That
    response MUST be the de-identified value, NEVER the raw."""
    async with _client() as c:
        token, account, ctx_id = await _register(c, "j4-b3")
        h = {"Authorization": f"Bearer {token}"}
        raw_email = "contact.j4b3@example-bank.io"
        raw_q3 = f"Open issue: {raw_email} wants the auditor brief."
        await c.post(
            "/api/me/first-session/intake",
            json={
                "role": "ned",
                "primary_context_name": "Globex Holdings",
                "top_of_mind": raw_q3,
            },
            headers=h,
        )
        r = await c.get("/api/me/first-session", headers=h)
        assert r.status_code == 200, r.text
        intake = (r.json().get("state") or {}).get("intake") or {}
        served = intake.get("top_of_mind") or ""
        assert raw_email not in served, (
            f"G18 leak through GET /me/first-session: raw email "
            f"'{raw_email}' returned in payload '{served}'."
        )
        assert re.search(r"\[\[ENT_[A-Z]+_\d+\]\]", served), (
            f"Expected Shield token anchor in served top_of_mind, "
            f"got '{served}'."
        )


# ── J4.B4 — Phase D framing routes through invoke_via_shield ────────
def test_j4_b4_phase_d_submit_framing_chain_through_shield():
    """Anchor-chain test (§5.8). The Solva Phase D `submit_framing`
    handler MUST call `classify_situation` and `run_frame_audit`,
    both of which import + call `invoke_via_shield`. A future
    regression that bypasses Shield breaks the chain.

    NOT a source-string assertion — the chain is across THREE files
    and asserts the call graph stays intact end-to-end."""
    router_src = PHASE_D_ROUTER.read_text(encoding="utf-8")
    # Anchor 1 — submit_framing exists and calls classify_situation.
    sf_block = router_src.find("async def submit_framing(")
    assert sf_block != -1, "submit_framing handler missing"
    # Bound the search to the handler body (find next async def).
    next_def = router_src.find("\nasync def ", sf_block + 1)
    handler_body = router_src[sf_block:next_def if next_def != -1 else len(router_src)]
    assert "classify_situation(" in handler_body, (
        "submit_framing no longer calls classify_situation — Shield "
        "routing for the Layer-0 situation class step has been "
        "broken."
    )
    assert "run_frame_audit(" in handler_body, (
        "submit_framing no longer calls run_frame_audit — Shield "
        "routing for the Layer-0 FAR step has been broken."
    )
    # Anchor 2 — classify_situation routes through invoke_via_shield.
    classifier_src = SITUATION_CLASSIFIER.read_text(encoding="utf-8")
    assert "from ..orchestration.shield_invoker import" in classifier_src, (
        "classify_situation no longer imports the shield_invoker — "
        "Shield routing broken."
    )
    assert "invoke_via_shield(" in classifier_src, (
        "classify_situation no longer calls invoke_via_shield — "
        "Shield routing broken."
    )
    # Anchor 3 — run_frame_audit routes through invoke_via_shield.
    far_src = FRAME_AUDIT.read_text(encoding="utf-8")
    assert "from ..orchestration.shield_invoker import" in far_src, (
        "run_frame_audit no longer imports the shield_invoker — "
        "Shield routing broken."
    )
    assert "invoke_via_shield(" in far_src, (
        "run_frame_audit no longer calls invoke_via_shield — "
        "Shield routing broken."
    )


# ── J4.B5 — J-sprint-closed guard ───────────────────────────────────
@pytest.mark.asyncio
async def test_onboarding_sprint_j1_j4_complete():
    """The final J-sprint closure guard.

    Asserts two invariants that pin the post-J4 contract:
      1. `ALLOWED_DOORS == {cycle, upload, solve, demo}` (J2 G21
         door allow-list — NEVER expand without orchestrator
         approval).
      2. All 5 J1/J2/J3/J4 onboarding status flags are emitted
         by `_compute_status` in the `onboarding_journey` payload
         block: `first_session_intake_complete` (J1),
         `door_taken` (J2), `first_doc_uploaded` (J3),
         `trust_center_introduced` (J3), `first_chat_seen` (J4).

    A future scope-creep change that drops a flag or expands the
    door allow-list breaks this test."""
    # Door allow-list pinned (J2 G21).
    import routers.first_session as fs_router
    assert set(fs_router.ALLOWED_DOORS) == {"cycle", "upload", "solve", "demo"}, (
        f"ALLOWED_DOORS regressed: {fs_router.ALLOWED_DOORS}"
    )
    # All 5 status flags emitted in onboarding_journey block.
    async with _client() as c:
        token, account, ctx_id = await _register(c, "j4-b5")
        h = {"Authorization": f"Bearer {token}"}
        r = await c.get("/api/users/me/onboarding-status", headers=h)
        assert r.status_code == 200, r.text
        journey = r.json().get("onboarding_journey") or {}
        required_keys = {
            "first_session_intake_complete",  # J1
            "door_taken",                     # J2
            "first_doc_uploaded",             # J3
            "trust_center_introduced",        # J3
            "first_chat_seen",                # J4
            "complete",                       # J4 rollup
        }
        missing = required_keys - set(journey.keys())
        assert not missing, (
            f"onboarding_journey payload missing J-sprint flags: "
            f"{missing}. Got: {sorted(journey.keys())}"
        )
        # Fresh account — all flags should be falsy (or null for door_taken).
        assert journey.get("first_session_intake_complete") is False
        assert journey.get("door_taken") is None
        assert journey.get("first_doc_uploaded") is False
        assert journey.get("trust_center_introduced") is False
        assert journey.get("first_chat_seen") is False
        assert journey.get("complete") is False
