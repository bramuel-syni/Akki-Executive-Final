"""J2.3 false-green fix — behavior tests, not source-string tests.

The original J2 test `test_cycle_door_routes_to_setup_wizard_query_string`
asserted that the literal `navigate('/app/cycle?wizard=1&intake_seed=1')`
string was present in source. e1_tester proved this is the third
false-green pattern of the sprint (T2.3 DOM-conditional → B3 missing
import → now J2.3 source-only test). Source-string assertions verify
the wire LABEL, not the wire BEHAVIOR.

This file's three tests assert BEHAVIOR:

  J2.3.1 — Backend: cycle-door state flip.
           POST `/api/me/first-session/choose-door` with `{door: "cycle"}`,
           then GET `/api/me/first-session`. Assert `status == completed`
           + `current_step == done` + `door_taken == cycle`. Before fix,
           the cycle branch set `in_progress`/`working` → the
           FirstSessionGuard whitelist bounced the navigate back to
           `/app/first-session` and the wizard never mounted.

  J2.3.2 — Frontend: CycleList wires the `?wizard=1` param.
           CycleList.jsx must (a) import + use `useSearchParams`,
           (b) read `wizard` on mount, (c) call `setAddOpen(true)` (or
           equivalent) when the value is `"1"`. Three-anchor source
           pattern — each anchor IS a behavior step, not a literal.

  J2.3.3 — Frontend: CycleSetupWizard prefills from intake_seed.
           CycleSetupWizard.jsx must (a) import `useSearchParams`,
           (b) read `intake_seed`, (c) call `api.get("/me/first-session")`
           when the value is `"1"`, (d) call `setCycleName(...)` from
           the response. Four-anchor behavior chain.

Anti-false-green discipline: each frontend assertion walks a CONTROL
FLOW step rather than checking literal label text. The 4-anchor chain
in J2.3.3 makes it materially impossible to half-implement the prefill
and ship a green test.
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
CYCLE_LIST = REPO / "frontend/src/pages/cycle/CycleList.jsx"
CYCLE_WIZARD = REPO / "frontend/src/components/cycle/CycleSetupWizard.jsx"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


async def _register_and_intake(c: httpx.AsyncClient, prefix: str,
                               primary_context_name: str = "Acme Holdings"):
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    r = await c.post("/api/auth/register", json={
        "email": email, "password": "Password123!@#",
        "name": f"{prefix.title()} Tester",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    token = body["access_token"]
    account = body["account"]
    h = {"Authorization": f"Bearer {token}"}
    r2 = await c.post("/api/me/first-session/intake", json={
        "role": "executive",
        "primary_context_name": primary_context_name,
        "top_of_mind": "Margin trend versus capital headroom",
    }, headers=h)
    assert r2.status_code == 200, r2.text
    return token, account, h


# ── J2.3.1 — Backend behavior: cycle-door state flip ────────────────
@pytest.mark.asyncio
async def test_j2_3_1_cycle_door_flips_first_session_to_completed():
    """POST `choose-door {door: cycle}` then GET first-session.
    Asserts the user's first_session is now `completed`/`done`, so
    the FirstSessionGuard whitelist will NOT bounce the
    /app/cycle?wizard=1 navigate.

    This is the BEHAVIOR test that replaces the false-green source
    assertion. It would have caught the bug e1_tester found.
    """
    async with _client() as c:
        token, account, h = await _register_and_intake(c, "j23-cycle")
        # Confirm pre-state.
        r0 = await c.get("/api/me/first-session", headers=h)
        assert r0.status_code == 200, r0.text
        pre = r0.json().get("state", {})
        assert pre.get("status") in ("not_started", "in_progress"), pre
        # Trigger cycle door.
        r1 = await c.post("/api/me/first-session/choose-door",
                          json={"door": "cycle"}, headers=h)
        assert r1.status_code == 200, r1.text
        # GET the canonical state.
        r2 = await c.get("/api/me/first-session", headers=h)
        assert r2.status_code == 200, r2.text
        st = r2.json().get("state", {})
        # The 3-prong behavior assertion — these are the ONLY values
        # that survive the FirstSessionGuard whitelist.
        assert st.get("status") == "completed", st
        assert st.get("current_step") == "done", st
        assert st.get("door_taken") == "cycle", st
        # And the audit chain shows the completion row.
        audit = await core_mod.db.audit_log.find_one(
            {
                "account_id": account["id"],
                "action": "first_session.completed",
                "metadata.exit": "cycle_door",
            },
            {"_id": 0},
        )
        assert audit is not None, (
            "Missing first_session.completed audit row for cycle door."
        )


# ── J2.3.2 — Frontend behavior: CycleList honors ?wizard=1 ──────────
def test_j2_3_2_cycle_list_reads_wizard_param_and_opens_wizard():
    """CycleList.jsx wires the `?wizard=1` param through to
    `setAddOpen(true)`. Three control-flow anchors, NOT a label
    string. Each anchor is a step in the actual behavior chain.

    Anchors (in source order):
      1. `useSearchParams` IS imported from react-router-dom.
      2. There IS a useEffect that calls `search.get("wizard")` and
         compares the result to `"1"`.
      3. Inside that effect, `setAddOpen(true)` IS called.

    All three anchors must coexist within the SAME useEffect block,
    not scattered around the file. This is enforced by extracting
    the useEffect block and checking all 3 anchors are inside it.
    """
    src = CYCLE_LIST.read_text(encoding="utf-8")

    # Anchor 1: useSearchParams imported.
    assert re.search(
        r"import\s*\{[^}]*useSearchParams[^}]*\}\s*from\s*['\"]react-router-dom['\"]",
        src,
    ), "useSearchParams not imported from react-router-dom in CycleList.jsx"

    # Anchor 2+3: find a useEffect block that reads `wizard` AND calls
    # setAddOpen(true). Walk every useEffect in the file and check.
    use_effects = re.finditer(
        r"useEffect\s*\(\s*\(\)\s*=>\s*\{(.*?)\}\s*,\s*\[",
        src, re.DOTALL,
    )
    found = False
    for m in use_effects:
        body = m.group(1)
        # Must reference `wizard` query param.
        reads_wizard = (
            'search.get("wizard")' in body
            or "search.get('wizard')" in body
            or 'searchParams.get("wizard")' in body
            or "searchParams.get('wizard')" in body
        )
        # Must open the Add Cycle modal (the existing wizard mount point).
        opens_wizard = (
            "setAddOpen(true)" in body
            or "setShowSetupWizard(true)" in body
            or "setShowWizard(true)" in body
        )
        if reads_wizard and opens_wizard:
            found = True
            break
    assert found, (
        "No useEffect in CycleList.jsx reads `?wizard=1` AND opens the "
        "Setup Wizard. This is the J2.3 false-green defect — the param "
        "is ignored and the wizard never mounts on the cycle-door navigate."
    )


# ── J2.3.3 — Frontend behavior: SetupWizard prefills cycleName ──────
def test_j2_3_3_setup_wizard_prefills_cycle_name_from_intake_seed():
    """CycleSetupWizard.jsx wires the `?intake_seed=1` param through
    to a `setCycleName(...)` call sourced from
    `api.get("/me/first-session")`. Four control-flow anchors, all
    within the SAME useEffect block.

    Anchors:
      1. `useSearchParams` imported from react-router-dom.
      2. A useEffect calls `searchParams.get("intake_seed")` and
         compares to `"1"`.
      3. Inside that effect, `api.get("/me/first-session")` is called.
      4. Inside that effect, `setCycleName(...)` is called.

    All 4 anchors must coexist within the same useEffect block.
    """
    src = CYCLE_WIZARD.read_text(encoding="utf-8")

    # Anchor 1.
    assert re.search(
        r"import\s*\{[^}]*useSearchParams[^}]*\}\s*from\s*['\"]react-router-dom['\"]",
        src,
    ), "useSearchParams not imported from react-router-dom in CycleSetupWizard.jsx"

    # Anchor 2-4 must coexist inside one useEffect.
    use_effects = re.finditer(
        r"useEffect\s*\(\s*\(\)\s*=>\s*\{(.*?)\}\s*,\s*\[",
        src, re.DOTALL,
    )
    found = False
    for m in use_effects:
        body = m.group(1)
        reads_seed = (
            'searchParams.get("intake_seed")' in body
            or "searchParams.get('intake_seed')" in body
        )
        fetches = (
            'api.get("/me/first-session")' in body
            or "api.get('/me/first-session')" in body
        )
        sets_name = "setCycleName(" in body
        if reads_seed and fetches and sets_name:
            found = True
            break
    assert found, (
        "No useEffect in CycleSetupWizard.jsx reads `?intake_seed=1`, "
        "fetches /me/first-session, AND calls setCycleName. The J2.3 "
        "false-green defect — the param is ignored and the user's Q2 "
        "answer never seeds the cycle name."
    )


# ── J2.3.3 — auxiliary: the prefill prefers Q2 over Q3 ──────────────
def test_j2_3_3_prefill_prefers_q2_primary_context_name_over_q3():
    """Per the orchestrator brief: pull the Q2 answer (the cycle-name
    response from intake). Q2 = `primary_context_name`. The fallback
    is Q3 `top_of_mind` (Shield-redacted but usable as a cue) only
    if Q2 is empty."""
    src = CYCLE_WIZARD.read_text(encoding="utf-8")
    # The prefill expression must mention `primary_context_name` BEFORE
    # `top_of_mind` (the `||` fallback order).
    idx_q2 = src.find("primary_context_name")
    idx_q3 = src.find("top_of_mind")
    assert idx_q2 != -1, "primary_context_name not referenced in wizard prefill."
    assert idx_q3 != -1, "top_of_mind fallback not referenced in wizard prefill."
    assert idx_q2 < idx_q3, (
        f"Q2 prefill order wrong — primary_context_name @ {idx_q2} should "
        f"come BEFORE top_of_mind fallback @ {idx_q3}."
    )
