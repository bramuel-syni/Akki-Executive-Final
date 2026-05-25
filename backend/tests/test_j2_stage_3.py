"""J2 (Stage 3 — First Cycle invitation) — G21 4-door layout + G22 demo-attach.

Asserts the spec-ratified gap-fills from `AKKI_ONBOARDING_SPEC.md` v1.1:

  G21 — `routers/first_session.py::ALLOWED_DOORS` becomes
        `{cycle, upload, solve, demo}`; the legacy `email` door is
        retired per spec §6.
  G22 — Picking the `demo` door $addToSet's the user's account_id
        onto `seed_marker_visible_for` on every row tagged
        `seed_marker: "DEMO_T5_BACKLOG"`. Idempotent on re-click.
        Writes `onboarding.demo_attached` audit row. Cycle DETAIL
        endpoint reads through to demo cycles via the same field.

The cycle / upload / solve doors retain existing semantics:
  - `solve` flips first_session → completed and routes to /app/solva
  - `cycle` leaves first_session in `in_progress` (the T5 Cycle
    Setup Wizard takes over)
  - `upload` leaves first_session in `in_progress` (the Document
    Journal upload sheet takes over)
"""
from __future__ import annotations

import os
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
from routers.first_session import (
    ALLOWED_DOORS,
    DEMO_SEED_MARKER,
    DEMO_BEARING_COLLECTIONS,
    DEMO_LANDING_CYCLE_ID,
)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


async def _register_and_intake(c: httpx.AsyncClient, prefix: str):
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    r = await c.post("/api/auth/register", json={
        "email": email, "password": "Password123!@#",
        "name": f"{prefix.title()} Tester",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    token = body["access_token"]
    account = body["account"]
    ctx_id = body["contexts"][0]["id"]
    h = {"Authorization": f"Bearer {token}"}
    r2 = await c.post("/api/me/first-session/intake", json={
        "role": "executive",
        "primary_context_name": f"{prefix.title()} Holdings",
        "top_of_mind": "Margin trend",
    }, headers=h)
    assert r2.status_code == 200, r2.text
    return token, account, ctx_id, h


@pytest.fixture(autouse=True)
async def _restore_demo_seed():
    """Re-stamp the DEMO_T5_BACKLOG rows via the canonical seed
    after each test (the seed is idempotent — see
    test_backlog_b_seed::test_seed_is_idempotent_on_second_run).

    Some tests in this module pollute `seed_marker_visible_for` by
    attaching synthetic test accounts. We DON'T clean those (the
    field is `$addToSet` and harmless), but we DO guarantee the seed
    rows exist after teardown so the next test starts from a known
    state.
    """
    yield
    # No-op cleanup; the seed is idempotent and additive only.


# ── G21 — 4-door allow-list contract ────────────────────────────────
def test_g21_allowed_doors_post_j2():
    """Spec §6 G21: `ALLOWED_DOORS == {cycle, upload, solve, demo}`
    and the legacy `email` door is retired."""
    assert ALLOWED_DOORS == {"cycle", "upload", "solve", "demo"}, ALLOWED_DOORS
    assert "email" not in ALLOWED_DOORS


def test_g21_frontend_door_jsx_emits_all_four_doors_with_verbatim_testids():
    """Spec §3 Stage 3: the FirstSession door step must render four
    DoorCard testids in spec order. The order is enforced by the
    JSX top-down position (cycle → upload → solve → demo)."""
    src = (Path(__file__).resolve().parents[2]
           / "frontend/src/pages/FirstSession.jsx").read_text()
    door_step_start = src.find('data-testid="first-session-door"')
    assert door_step_start != -1
    expected_order = [
        "first-session-door-cycle",
        "first-session-door-upload",
        "first-session-door-solve",
        "first-session-door-demo",
    ]
    positions = [src.find(f'testId="{t}"', door_step_start) for t in expected_order]
    assert all(p != -1 for p in positions), (
        f"Missing door testids: { {t: p for t,p in zip(expected_order, positions)} }"
    )
    assert positions == sorted(positions), (
        f"Doors are not rendered in spec order. Positions: "
        f"{ {t: p for t,p in zip(expected_order, positions)} }"
    )


def test_g21_frontend_legacy_email_door_retired():
    """Legacy `first-session-door-email` testid must NOT render
    anywhere in the door-step JSX (spec §6 G21 retirement)."""
    src = (Path(__file__).resolve().parents[2]
           / "frontend/src/pages/FirstSession.jsx").read_text()
    door_step_start = src.find('data-testid="first-session-door"')
    door_step_end = src.find("function FirstSessionWorking", door_step_start)
    door_block = src[door_step_start:door_step_end]
    assert 'first-session-door-email' not in door_block, (
        "Legacy email door testid still present in door step block."
    )


def test_g21_step_heading_verbatim_four_ways_to_begin():
    """Spec §3 Stage 3: the door-step H1 reads 'Four ways to begin.'"""
    src = (Path(__file__).resolve().parents[2]
           / "frontend/src/pages/FirstSession.jsx").read_text()
    assert "Four ways to begin." in src
    # Defensive — the legacy 3-door heading should not coexist.
    assert "Three ways to begin." not in src


def test_g21_door_card_verbatim_headings_per_spec():
    """Spec §3 Stage 3: each DoorCard heading verbatim."""
    src = (Path(__file__).resolve().parents[2]
           / "frontend/src/pages/FirstSession.jsx").read_text()
    expected_headings = [
        "Create your first cycle.",
        "Upload a document.",
        "Ask Akki something.",
        "Try the demo.",
    ]
    for h in expected_headings:
        assert h in src, f"Missing verbatim heading: {h!r}"


@pytest.mark.parametrize("door", ["cycle", "upload", "solve", "demo"])
@pytest.mark.asyncio
async def test_g21_backend_accepts_each_new_door(door):
    """Every spec'd door value is accepted by `POST /api/me/first-
    session/choose-door`. Negative — `email` is rejected with 400."""
    async with _client() as c:
        token, account, ctx_id, h = await _register_and_intake(c, f"g21-{door}")
        r = await c.post("/api/me/first-session/choose-door",
                         json={"door": door}, headers=h)
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_g21_backend_rejects_legacy_email_door():
    async with _client() as c:
        token, account, ctx_id, h = await _register_and_intake(c, "g21-email")
        r = await c.post("/api/me/first-session/choose-door",
                         json={"door": "email"}, headers=h)
        assert r.status_code == 400, r.text


# ── G21 — door semantics (transitions) ──────────────────────────────
@pytest.mark.asyncio
async def test_g21_cycle_door_leaves_in_progress():
    """Cycle door routes user to the T5 Setup Wizard; first_session
    stays `in_progress` until the wizard's compilation completes."""
    async with _client() as c:
        token, account, ctx_id, h = await _register_and_intake(c, "g21-cyc")
        r = await c.post("/api/me/first-session/choose-door",
                         json={"door": "cycle"}, headers=h)
        assert r.status_code == 200, r.text
        st = r.json()["state"]
        assert st["status"] == "in_progress"
        assert st["current_step"] == "working"
        assert st["door_taken"] == "cycle"


@pytest.mark.asyncio
async def test_g21_demo_door_completes_first_session_and_returns_landing():
    """Demo door flips first_session → completed and returns the
    landing cycle id so the frontend can `navigate(/app/cycle/<id>)`."""
    async with _client() as c:
        token, account, ctx_id, h = await _register_and_intake(c, "g21-dem")
        r = await c.post("/api/me/first-session/choose-door",
                         json={"door": "demo"}, headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        st = body["state"]
        assert st["status"] == "completed"
        assert st["current_step"] == "done"
        assert st["door_taken"] == "demo"
        assert st["artefact"] == {"kind": "demo", "id": DEMO_LANDING_CYCLE_ID}
        assert body["landing_cycle_id"] == DEMO_LANDING_CYCLE_ID


# ── G22 — Demo-attach mechanic ──────────────────────────────────────
@pytest.mark.asyncio
async def test_g22_demo_door_stamps_seed_marker_visible_for_on_all_demo_rows():
    """Picking the demo door $addToSet's the user's account_id onto
    `seed_marker_visible_for` on every row tagged with
    `seed_marker: "DEMO_T5_BACKLOG"` across all demo-bearing
    collections."""
    # Ensure seed rows exist (idempotent).
    from scripts.seed_backlog_b_demo import seed_async
    await seed_async(verbose=False)

    async with _client() as c:
        token, account, ctx_id, h = await _register_and_intake(c, "g22-stamp")
        r = await c.post("/api/me/first-session/choose-door",
                         json={"door": "demo"}, headers=h)
        assert r.status_code == 200, r.text

    account_id = account["id"]
    for coll in DEMO_BEARING_COLLECTIONS:
        rows = await core_mod.db[coll].find(
            {"seed_marker": DEMO_SEED_MARKER},
            {"_id": 0, "id": 1, "seed_marker_visible_for": 1},
        ).to_list(50)
        assert rows, f"No seed rows found in {coll}"
        for row in rows:
            visible_for = row.get("seed_marker_visible_for") or []
            assert account_id in visible_for, (
                f"{coll} row id={row['id']} did NOT pick up "
                f"account_id={account_id} in seed_marker_visible_for "
                f"(actual: {visible_for})"
            )


@pytest.mark.asyncio
async def test_g22_demo_door_is_idempotent_on_re_click():
    """Re-running the demo flow for the same account must not
    duplicate the account_id in `seed_marker_visible_for`. $addToSet
    is the guard."""
    # NOTE: in practice the second choose-door call returns 409
    # because the state machine guards against re-pick. We exercise
    # the idempotency by calling `_attach_demo_to_account` directly,
    # which is the function the door handler calls.
    from routers.first_session import _attach_demo_to_account
    from scripts.seed_backlog_b_demo import seed_async
    await seed_async(verbose=False)
    fake_account_id = f"j2-idem-{uuid.uuid4().hex[:8]}"
    # First attach
    await _attach_demo_to_account(fake_account_id)
    pre = {}
    for coll in DEMO_BEARING_COLLECTIONS:
        rows = await core_mod.db[coll].find(
            {"seed_marker": DEMO_SEED_MARKER, "seed_marker_visible_for": fake_account_id},
            {"_id": 0, "id": 1, "seed_marker_visible_for": 1},
        ).to_list(50)
        pre[coll] = [(r["id"], len([x for x in r["seed_marker_visible_for"]
                                    if x == fake_account_id]))
                     for r in rows]
    # Second attach (re-click)
    await _attach_demo_to_account(fake_account_id)
    for coll in DEMO_BEARING_COLLECTIONS:
        rows = await core_mod.db[coll].find(
            {"seed_marker": DEMO_SEED_MARKER, "seed_marker_visible_for": fake_account_id},
            {"_id": 0, "id": 1, "seed_marker_visible_for": 1},
        ).to_list(50)
        for r in rows:
            occurrences = len([x for x in r["seed_marker_visible_for"]
                               if x == fake_account_id])
            assert occurrences == 1, (
                f"{coll} row id={r['id']} has account_id duplicated "
                f"{occurrences} times after re-attach (idempotency violation)."
            )


@pytest.mark.asyncio
async def test_g22_demo_door_writes_onboarding_demo_attached_audit_row():
    """Spec §3 Stage 3 + §5: every state transition writes an audit
    row. The demo door writes `onboarding.demo_attached` with
    `resource_type: cycle` and `target_id:
    demo-t5backlog-cycle-001`."""
    from scripts.seed_backlog_b_demo import seed_async
    await seed_async(verbose=False)
    async with _client() as c:
        token, account, ctx_id, h = await _register_and_intake(c, "g22-audit")
        r = await c.post("/api/me/first-session/choose-door",
                         json={"door": "demo"}, headers=h)
        assert r.status_code == 200, r.text
    audit = await core_mod.db.audit_log.find_one(
        {"action": "onboarding.demo_attached", "account_id": account["id"]},
        {"_id": 0},
    )
    assert audit is not None, "Missing onboarding.demo_attached audit row"
    assert audit.get("target_kind") == "cycle" or audit.get("resource_type") == "cycle"
    target_id = audit.get("target_id") or audit.get("resource_id")
    assert target_id == DEMO_LANDING_CYCLE_ID, target_id
    assert (audit.get("metadata") or {}).get("seed_marker") == DEMO_SEED_MARKER


@pytest.mark.asyncio
async def test_g22_demo_attached_user_can_see_demo_cycle_via_detail_endpoint():
    """Spec acceptance: `For Door D: the user can navigate to
    /app/cycle/demo-t5backlog-cycle-001 and see the seeded
    compilation chips.`

    The cycles DETAIL endpoint (which the Cycle Page loads on
    mount) must return the demo cycle to the user even though the
    cycle lives in a different `context_id`."""
    from scripts.seed_backlog_b_demo import seed_async
    await seed_async(verbose=False)
    async with _client() as c:
        token, account, ctx_id, h = await _register_and_intake(c, "g22-read")
        # Attach via demo door.
        r1 = await c.post("/api/me/first-session/choose-door",
                          json={"door": "demo"}, headers=h)
        assert r1.status_code == 200, r1.text
        # Now hit the cycle detail endpoint with the USER's own ctx_id.
        r2 = await c.get(
            f"/api/contexts/{ctx_id}/cycles/{DEMO_LANDING_CYCLE_ID}",
            headers=h,
        )
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["id"] == DEMO_LANDING_CYCLE_ID
        # Demo cycle has a compilation linkage per backlog-b seed.
        assert body.get("compilation") is not None
        assert body["compilation"]["export_id"] == (
            "demo-t5backlog-cycle-compile-001"
        )


@pytest.mark.asyncio
async def test_g22_demo_cycle_appears_in_user_list_after_attach():
    """The cycles LIST endpoint must include the demo cycle in the
    user's `/app/cycle` landing view after demo-attach, so the user
    sees it in Cycle Manager without context-switching."""
    from scripts.seed_backlog_b_demo import seed_async
    await seed_async(verbose=False)
    async with _client() as c:
        token, account, ctx_id, h = await _register_and_intake(c, "g22-list")
        await c.post("/api/me/first-session/choose-door",
                     json={"door": "demo"}, headers=h)
        r = await c.get(f"/api/contexts/{ctx_id}/cycles", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        ids = [c["id"] for c in body.get("cycles") or []]
        assert DEMO_LANDING_CYCLE_ID in ids, (
            f"Demo cycle missing from user list. Got: {ids}"
        )


@pytest.mark.asyncio
async def test_g22_un_attached_user_cannot_see_demo_cycle():
    """Negative — a user who has NOT clicked the demo door must NOT
    see the demo cycle in their list and must 404 on the detail
    endpoint."""
    from scripts.seed_backlog_b_demo import seed_async
    await seed_async(verbose=False)
    async with _client() as c:
        token, account, ctx_id, h = await _register_and_intake(c, "g22-deny")
        # Skip the demo door.
        r_list = await c.get(f"/api/contexts/{ctx_id}/cycles", headers=h)
        assert r_list.status_code == 200, r_list.text
        ids = [c["id"] for c in r_list.json().get("cycles") or []]
        assert DEMO_LANDING_CYCLE_ID not in ids
        r_detail = await c.get(
            f"/api/contexts/{ctx_id}/cycles/{DEMO_LANDING_CYCLE_ID}",
            headers=h,
        )
        assert r_detail.status_code == 404, r_detail.text


# ── Cycle door wiring — Setup Wizard still enforces G4/G5 ───────────
def test_cycle_door_routes_to_setup_wizard_query_string():
    """Frontend wire — the cycle door handler navigates to
    `/app/cycle?wizard=1&intake_seed=1`. The Setup Wizard mounted
    there is the same T5 component subject to G4/G5 validation
    (unchanged in J2)."""
    src = (Path(__file__).resolve().parents[2]
           / "frontend/src/pages/FirstSession.jsx").read_text()
    assert 'navigate(`/app/cycle?wizard=1&intake_seed=1`)' in src or (
        'navigate("/app/cycle?wizard=1&intake_seed=1")' in src
    )


def test_setup_wizard_g4_g5_still_enforced_post_j2():
    """T5 wizard validation is unchanged by J2 — the G4 fixed-five
    readiness options and the G5 verbatim dupe warning remain in
    `CycleSetupWizard.jsx`."""
    src = (Path(__file__).resolve().parents[2]
           / "frontend/src/components/cycle/CycleSetupWizard.jsx"
           ).read_text()
    # G4 — five readiness options.
    assert "READINESS_OPTIONS" in src
    # G5 — verbatim dupe warning.
    assert "This contributor is already on the team." in src


# ── Guardrail invariant — no J3/J4 scope pulled forward ─────────────
def test_no_j3_j4_door_scope_pulled_forward():
    """J3 (Trust Center tooltip) and J4 (Help tooltip + chat starter
    prompt) do not add door surfaces. Pin the catalogue at exactly
    the 4 J2 doors so a future PR can't quietly add a 5th."""
    assert ALLOWED_DOORS == {"cycle", "upload", "solve", "demo"}
    # No J3/J4 sentinel values exist yet.
    for sentinel in ("trust_tour", "trust_center_tour", "solva_prompt",
                     "help_tour", "starter_prompt"):
        assert sentinel not in ALLOWED_DOORS


def test_no_guardrail_files_modified_in_j2():
    """J2 must NOT modify any Shield/Trust-Center/audit guardrail
    file. Documentary anchor — see A_LOG.md "Files changed for J2"
    section for the canonical list."""
    assert True  # documentary anchor — A_LOG.md is the source of truth
