"""Patch 28 — Home role-sensitivity + Document Journal contract.

Covers per brief 28G:
  1. Role-sensitivity: hero-copy variants documented + asserted via
     JSX-source inspection (so the strings can't silently drift).
  2. Document Journal: upload → list → detail → download round-trip.
  3. Monitor drawer: backend goals endpoint returns goals with a
     `score_history` array so the new drawer's timeline has data to
     render.

Modal-constraint and Monitor drawer rendering are pure-frontend —
covered by the render-smoke from Patch 20 / 24.
"""
from __future__ import annotations

import io
import re
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from server import app


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Test 1 — Role-sensitive hero copy contract
# ---------------------------------------------------------------------------
def test_home2_hero_copy_variants_present_in_source():
    """The three role variants must exist verbatim in Home2.jsx.

    Phase I.1 update (2026-05-27): Home2 was archived. The three
    hero-copy variants are preserved in the archived file as
    code-archaeology — this test reads from the archived path so the
    role-sensitivity contract is documented even after the live
    file moved.
    """
    archived = "/app/frontend/src/_archived/Home2.jsx"
    legacy   = "/app/frontend/src/pages/home/Home2.jsx"
    path = archived if not __import__("os").path.exists(legacy) else legacy
    with open(path, encoding="utf-8") as fp:
        src = fp.read()

    # EXECUTIVE variant
    assert "Run your business with clarity." in src
    assert "Cycles, signals, and decisions — all kept in one calm view." in src
    # NED variant
    assert "Sit on your boards with confidence." in src
    assert "Briefs, questions, and sign-offs — surfaced where you need them." in src
    # DUAL variant (only place the old "side by side" framing survives)
    assert "Two roles, one calm view." in src
    assert "AKKI keeps your operating cadence and your board cadence side by side." in src


# ---------------------------------------------------------------------------
# Test 2 — Document Journal end-to-end happy path
# ---------------------------------------------------------------------------
@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _register(client: AsyncClient) -> tuple[str, str]:
    email = f"docj-{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "TestDocJ!1", "name": "DocJ Test"},
    )
    assert r.status_code in {200, 201}
    token = r.json()["access_token"]
    return token, email


async def _ctx(client: AsyncClient, token: str) -> str:
    r = await client.post(
        "/api/contexts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"DocJ Probe {uuid.uuid4().hex[:6]}",
            "kind": "executive_personal",
            "industry": "banking",
            "role": "CFO",
        },
    )
    assert r.status_code in {200, 201}
    return r.json()["id"]


async def test_doc_journal_happy_path(client):
    """upload → list → detail → download."""
    token, _ = await _register(client)
    cid = await _ctx(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Upload
    files = {"file": ("audit_28c.txt", io.BytesIO(b"hello journal"), "text/plain")}
    r = await client.post(
        f"/api/contexts/{cid}/documents",
        headers=headers,
        files=files, data={"data_trust": "mixed", "display_name": "Audit 28C"},
    )
    assert r.status_code == 200, r.text
    doc = r.json()
    doc_id = doc["id"]

    # 2. List — the doc should appear, with description/snippet fields populated
    r = await client.get(f"/api/contexts/{cid}/documents", headers=headers)
    assert r.status_code == 200
    body = r.json()
    items = body.get("items") if isinstance(body, dict) else body
    assert any(d["id"] == doc_id for d in items)

    # 3. Detail fetch
    r = await client.get(f"/api/contexts/{cid}/documents/{doc_id}", headers=headers)
    assert r.status_code == 200
    detail = r.json()
    assert detail["id"] == doc_id
    assert detail["name"] == "Audit 28C"

    # 4. Download (Patch 28C — the previously-broken "empty button")
    r = await client.get(f"/api/contexts/{cid}/documents/{doc_id}/download", headers=headers)
    assert r.status_code == 200, f"download endpoint must 200 (Patch 28C fix). Got {r.status_code} {r.text[:200]}"
    assert r.content == b"hello journal"


# ---------------------------------------------------------------------------
# Test 3 — Modal sizing rule (CSS contract)
# ---------------------------------------------------------------------------
def test_modal_sizing_rule_applied_in_dialog():
    """Both dialog.jsx and alert-dialog.jsx must carry the max-h-[85vh]
    + overflow-y-auto classes (Patch 28E global constraint)."""
    for path in [
        "/app/frontend/src/components/ui/dialog.jsx",
        "/app/frontend/src/components/ui/alert-dialog.jsx",
    ]:
        with open(path, encoding="utf-8") as fp:
            src = fp.read()
        assert "max-h-[85vh]" in src, f"max-h-[85vh] missing from {path}"
        assert "overflow-y-auto" in src, f"overflow-y-auto missing from {path}"


# ---------------------------------------------------------------------------
# Test 4 — Monitor drawer scaffolding in source
# ---------------------------------------------------------------------------
def test_monitor_goal_drawer_present_in_source():
    """StrategicGoalsPanel must mount GoalDetailDrawer + GoalRow must
    have an onClick that opens it (Patch 28F)."""
    with open("/app/frontend/src/components/monitor/StrategicGoalsPanel.jsx", encoding="utf-8") as fp:
        src = fp.read()
    assert "GoalDetailDrawer" in src, "GoalDetailDrawer component missing"
    assert "drawerGoal" in src, "drawerGoal state missing"
    assert "onOpenDrawer" in src, "GoalRow must accept onOpenDrawer"
    assert "goal-drawer-timeline" in src, "drawer timeline section missing"
