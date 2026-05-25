"""T1.6 — Add to Cycle wire format (G1 ratified, 24 May 2026).

Spec contract: `/app/memory/AKKI_PRODUCT_SPEC.md` v1.1 §4.A → D6 +
§6 → G1.

Frontend (DocumentRoutingActions.jsx) POSTs:

    POST /api/contexts/{cid}/cycle/contributions?cycle_id=<selected>
    body = { cycle_id, kind: "document", source_doc_id, title }

`agenda_item_id` and `team_member_id` are intentionally omitted — the
document attaches at the cycle root with no agenda-item / contributor
binding (Select-Cycle-only modal per D6).

This test exercises the backend ContributionIn schema directly to
prove that:
  (a) the G1 payload is accepted as-is (200/201) and a contribution
      row lands in `db.cycle_contributions` against the resolved
      agenda for the selected cycle;
  (b) the `cycle_id` query param routes the contribution to the
      correct cycle's agenda (multi-cycle resolution);
  (c) the QA-2026-05-16-021 invariant (at-least-one of
      body_text/source_doc_id) still rejects a malformed payload with
      no source_doc_id and no body_text → 422.

T1.6 also requires the frontend to surface 400/422/423 with
human-readable toasts. That branch is covered by frontend E2E.
"""
from __future__ import annotations

import os
import sys
import uuid

import httpx
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

import core as core_mod
from server import app


def _acc(prefix: str) -> dict:
    uid = uuid.uuid4().hex[:10]
    return {
        "id": f"{prefix}-{uid}",
        "email": f"{prefix}-{uid}@example.com",
        "display_name": prefix.title(),
        "name": prefix.title(),
    }


@pytest.fixture(scope="module")
def env() -> dict:
    return {
        "owner": _acc("t1-g1-owner"),
        "ctx": f"ctx-t1-g1-{uuid.uuid4().hex[:10]}",
    }


async def _seed(env: dict) -> None:
    db = core_mod.db
    cid = env["ctx"]
    # `contexts` is keyed by `id`, not `context_id`; everything else
    # scopes by `context_id`. Idempotent reseed so the same env can be
    # reused across multiple tests in this module.
    await db.contexts.delete_many({"id": cid})
    for c in (
        "memberships", "cycles", "cycle_agendas",
        "cycle_team", "cycle_contributions",
    ):
        await getattr(db, c).delete_many({"context_id": cid})
    await db.accounts.update_one(
        {"id": env["owner"]["id"]},
        {"$set": env["owner"]},
        upsert=True,
    )
    await db.contexts.insert_one({
        "id": cid, "name": "T1 G1 Co",
        "owner_account_id": env["owner"]["id"],
        "type": "executive_enterprise",
    })
    await db.memberships.update_one(
        {"context_id": cid, "account_id": env["owner"]["id"]},
        {"$set": {
            "context_id": cid,
            "account_id": env["owner"]["id"],
            "role": "executive", "sub_role": "admin", "status": "active",
        }},
        upsert=True,
    )


def _auth(account: dict) -> None:
    async def _o():
        return account
    app.dependency_overrides[core_mod.get_current_account] = _o


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


# ── 1. G1 happy path: payload is accepted and lands as a doc contribution ──
@pytest.mark.asyncio
async def test_g1_wire_format_accepted_and_persists(env):
    await _seed(env)
    _auth(env["owner"])
    cid = env["ctx"]
    async with _client() as c:
        cyc = (await c.post(
            f"/api/contexts/{cid}/cycles",
            json={"title": "Q1 G1 Cycle"},
        )).json()
        cycle_id = cyc["id"]
        # G1 verbatim payload — no agenda_item_id, no team_member_id,
        # no body_text. The frontend always supplies the cycle_id both
        # in the body and the query string.
        payload = {
            "cycle_id": cycle_id,
            "kind": "document",
            "source_doc_id": f"doc-{uuid.uuid4().hex[:10]}",
            "title": "Q1 Board Pack.pdf",
        }
        r = await c.post(
            f"/api/contexts/{cid}/cycle/contributions",
            params={"cycle_id": cycle_id},
            json=payload,
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "document"
    assert body["source_doc_id"] == payload["source_doc_id"]
    assert body["title"] == payload["title"]
    assert body["agenda_item_id"] is None
    assert body["team_member_id"] is None
    # Persisted row in `cycle_contributions` against the right cycle.
    row = await core_mod.db.cycle_contributions.find_one(
        {"id": body["id"]}, {"_id": 0},
    )
    assert row is not None
    assert row["context_id"] == cid
    assert row["cycle_id"] == cycle_id
    assert row["source_doc_id"] == payload["source_doc_id"]


# ── 2. The cycle_id query param actually selects the right cycle ──────
@pytest.mark.asyncio
async def test_g1_query_param_routes_to_correct_cycle(env):
    _auth(env["owner"])
    cid = env["ctx"]
    async with _client() as c:
        cyc_a = (await c.post(
            f"/api/contexts/{cid}/cycles",
            json={"title": "Cycle A"},
        )).json()
        cyc_b = (await c.post(
            f"/api/contexts/{cid}/cycles",
            json={"title": "Cycle B"},
        )).json()
        payload = {
            "cycle_id": cyc_b["id"],
            "kind": "document",
            "source_doc_id": f"doc-{uuid.uuid4().hex[:8]}",
            "title": "Routed to B.pdf",
        }
        r = await c.post(
            f"/api/contexts/{cid}/cycle/contributions",
            params={"cycle_id": cyc_b["id"]},
            json=payload,
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cycle_id"] == cyc_b["id"], (
        f"contribution routed to wrong cycle: got {body['cycle_id']}, "
        f"expected {cyc_b['id']} (other was {cyc_a['id']})"
    )


# ── 3. Empty source_doc_id + empty body_text still 422s (QA-2026-05-16-021) ──
@pytest.mark.asyncio
async def test_g1_empty_payload_still_rejected_with_422(env):
    _auth(env["owner"])
    cid = env["ctx"]
    async with _client() as c:
        cyc = (await c.post(
            f"/api/contexts/{cid}/cycles",
            json={"title": "Empty-Reject"},
        )).json()
        bad_payload = {
            "cycle_id": cyc["id"],
            "kind": "document",
            "source_doc_id": None,
            "title": "Empty pack",
        }
        r = await c.post(
            f"/api/contexts/{cid}/cycle/contributions",
            params={"cycle_id": cyc["id"]},
            json=bad_payload,
        )
    assert r.status_code == 422, r.text
    # The error references the invariant id so the frontend can map it
    # to a specific human toast if needed.
    assert "QA-2026-05-16-021" in r.text


# ── 4. Cycles listing returns both active + draft for the dropdown ────
@pytest.mark.asyncio
async def test_cycles_list_filterable_active_and_draft_for_modal(env):
    await _seed(env)
    _auth(env["owner"])
    cid = env["ctx"]
    async with _client() as c:
        # Seed two drafts and activate one of them so we get one
        # active and one draft.
        d1 = (await c.post(
            f"/api/contexts/{cid}/cycles",
            json={"title": "Filter Draft"},
        )).json()
        a1 = (await c.post(
            f"/api/contexts/{cid}/cycles",
            json={"title": "Filter Active Source"},
        )).json()
        await c.post(
            f"/api/contexts/{cid}/cycle/agenda",
            params={"cycle_id": a1["id"]},
            json={"title": "Filter Demo", "items": [{"label": "Item"}]},
        )
        await c.post(f"/api/contexts/{cid}/cycles/{a1['id']}/activate")

        # The frontend modal issues two parallel calls (status=active,
        # status=draft, page_size=60) and merges. Replicate here.
        active = (await c.get(
            f"/api/contexts/{cid}/cycles",
            params={"status": "active", "page_size": 60},
        )).json()
        draft = (await c.get(
            f"/api/contexts/{cid}/cycles",
            params={"status": "draft", "page_size": 60},
        )).json()

    active_titles = {row["title"] for row in active["cycles"]}
    draft_titles = {row["title"] for row in draft["cycles"]}
    assert len(active["cycles"]) >= 1, active
    assert d1["title"] in draft_titles, draft_titles
    # No completed leak in either list.
    for row in active["cycles"]:
        assert row["status"] == "active"
    for row in draft["cycles"]:
        assert row["status"] == "draft"
    # No title can be in both lists at once.
    assert active_titles.isdisjoint(draft_titles), (
        active_titles & draft_titles
    )
