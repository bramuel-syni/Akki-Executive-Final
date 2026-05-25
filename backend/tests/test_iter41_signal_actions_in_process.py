"""Iter-41 — Signal actions / Pulse Resolved (in-process rewrite).

Hardening Step 4 (2026-05-25). Replaces the archived
`test_iter41_signal_actions.py` E2E shell. Same invariants, in-
process httpx ASGI pattern.

Anti-source-string-assertion discipline (closeout §5.8): each test
asserts a CONTROL-FLOW CHAIN — POST → response → Mongo projection
→ summary recompute — not a literal source match.

Coverage:
  s41.A — GET recommendations returns the bucket + 3 next-step
          suggestions for the signal's tone.
  s41.B — POST action with action_type=acted persists a row +
          surfaces in the summary as `acted: True`.
  s41.C — POST action with action_type=shared + recipients
          surfaces in the summary as `shared_count: N`.
  s41.D — GET actions returns most-recent-first ordering AND the
          summary fields are correctly recomputed.
  s41.E — 404 on POST against an unknown signal_id (RBAC integrity).
  s41.F — Pydantic validation rejects `action_type` outside
          {acted, shared} with 422.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

import core as core_mod
from server import app


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


async def _register(c, prefix: str):
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    r = await c.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "Password123!@#",
            "name": f"{prefix.title()} Tester",
            "role": "executive",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    return body["access_token"], body["account"], body["contexts"][0]["id"]


async def _seed_signal(ctx_id: str, *, kind: str = "risk",
                       headline: str = "Test risk surface") -> str:
    """Insert a minimal `signals` row tagged to the context so the
    /recommendations and /actions endpoints have something to look up."""
    sid = str(uuid.uuid4())
    await core_mod.db.signals.insert_one({
        "id": sid,
        "context_id": ctx_id,
        "kind": kind,
        "tone": kind,
        "headline": headline,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return sid


# ── s41.A — recommendations bucket + 3 suggestions ──────────────────
@pytest.mark.asyncio
async def test_s41_a_get_recommendations_returns_bucket_and_three():
    """Anchor chain: seed a `risk` signal → GET recommendations →
    response carries `bucket: "risk"` AND exactly 3 recommendation
    entries each with `label` + `note`."""
    async with _client() as c:
        token, _, ctx_id = await _register(c, "s41-a")
        sid = await _seed_signal(ctx_id, kind="risk")
        h = {"Authorization": f"Bearer {token}"}
        r = await c.get(
            f"/api/contexts/{ctx_id}/signals/{sid}/recommendations",
            headers=h,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("bucket") == "risk", body
        recs = body.get("recommendations") or []
        assert len(recs) == 3, f"Expected 3 recs, got {len(recs)}: {recs}"
        for rec in recs:
            assert rec.get("label"), rec
            assert rec.get("note"), rec


# ── s41.B — POST action=acted persists + summary rolls forward ─────
@pytest.mark.asyncio
async def test_s41_b_post_acted_persists_and_summarises():
    """Anchor chain: POST action_type=acted with recommendation_idx
    → 200 → row in `signal_actions` collection → GET /actions
    summary.acted is True AND summary.last_acted_label resolves
    from the recommendation templates."""
    async with _client() as c:
        token, _, ctx_id = await _register(c, "s41-b")
        sid = await _seed_signal(ctx_id, kind="risk")
        h = {"Authorization": f"Bearer {token}"}
        r = await c.post(
            f"/api/contexts/{ctx_id}/signals/{sid}/actions",
            json={"action_type": "acted", "recommendation_idx": 0},
            headers=h,
        )
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["action_type"] == "acted"
        assert doc["recommendation_idx"] == 0
        # Label was resolved from the template because the client
        # didn't echo it back.
        assert doc.get("recommendation_label"), doc
        # GET /actions surfaces the summary fields.
        rs = await c.get(
            f"/api/contexts/{ctx_id}/signals/{sid}/actions", headers=h,
        )
        assert rs.status_code == 200, rs.text
        summary = rs.json()["summary"]
        assert summary["acted"] is True
        assert summary["last_acted_label"] == doc["recommendation_label"]


# ── s41.C — POST action=shared + recipients aggregation ────────────
@pytest.mark.asyncio
async def test_s41_c_post_shared_aggregates_recipients():
    """Anchor chain: POST action_type=shared with 2 recipients →
    GET /actions summary.shared_count == 2 AND summary.shared_with
    is a deduplicated sorted list."""
    async with _client() as c:
        token, _, ctx_id = await _register(c, "s41-c")
        sid = await _seed_signal(ctx_id, kind="opportunity")
        h = {"Authorization": f"Bearer {token}"}
        r = await c.post(
            f"/api/contexts/{ctx_id}/signals/{sid}/actions",
            json={
                "action_type": "shared",
                "recipients": ["chair@board.com", "audit@board.com"],
                "note": "Sharing for awareness",
            },
            headers=h,
        )
        assert r.status_code == 200, r.text
        # Share to one of the same emails again → dedup keeps count at 2.
        await c.post(
            f"/api/contexts/{ctx_id}/signals/{sid}/actions",
            json={
                "action_type": "shared",
                "recipients": ["chair@board.com"],
            },
            headers=h,
        )
        rs = await c.get(
            f"/api/contexts/{ctx_id}/signals/{sid}/actions", headers=h,
        )
        assert rs.status_code == 200, rs.text
        summary = rs.json()["summary"]
        assert summary["shared_count"] == 2, summary
        assert summary["shared_with"] == sorted(["chair@board.com",
                                                  "audit@board.com"])


# ── s41.D — GET actions returns most-recent-first ──────────────────
@pytest.mark.asyncio
async def test_s41_d_actions_list_orders_most_recent_first():
    """Anchor chain: 2 actions POSTed sequentially → GET /actions
    returns actions[0].created_at >= actions[1].created_at."""
    async with _client() as c:
        token, _, ctx_id = await _register(c, "s41-d")
        sid = await _seed_signal(ctx_id, kind="risk")
        h = {"Authorization": f"Bearer {token}"}
        for label in ("first", "second"):
            r = await c.post(
                f"/api/contexts/{ctx_id}/signals/{sid}/actions",
                json={"action_type": "acted",
                      "recommendation_label": label},
                headers=h,
            )
            assert r.status_code == 200, r.text
        rs = await c.get(
            f"/api/contexts/{ctx_id}/signals/{sid}/actions", headers=h,
        )
        actions = rs.json()["actions"]
        assert len(actions) == 2
        # First in list is the most recent ("second" label).
        assert actions[0]["recommendation_label"] == "second", actions
        assert actions[1]["recommendation_label"] == "first", actions
        # Timestamp ordering reflects insertion order.
        assert actions[0]["created_at"] >= actions[1]["created_at"]


# ── s41.E — 404 on unknown signal ──────────────────────────────────
@pytest.mark.asyncio
async def test_s41_e_post_action_unknown_signal_returns_404():
    """Anchor chain: POST action against a context the caller is
    a member of BUT a signal_id that doesn't exist → 404 (RBAC
    integrity, not silent-success)."""
    async with _client() as c:
        token, _, ctx_id = await _register(c, "s41-e")
        h = {"Authorization": f"Bearer {token}"}
        r = await c.post(
            f"/api/contexts/{ctx_id}/signals/00000000-no-such/actions",
            json={"action_type": "acted"},
            headers=h,
        )
        assert r.status_code == 404, r.text


# ── s41.F — Pydantic validation rejects bogus action_type ──────────
@pytest.mark.asyncio
async def test_s41_f_invalid_action_type_returns_422():
    """Anchor chain: POST with action_type=`deleted` (not in the
    `^(acted|shared)$` pattern) → 422 Pydantic error."""
    async with _client() as c:
        token, _, ctx_id = await _register(c, "s41-f")
        sid = await _seed_signal(ctx_id)
        h = {"Authorization": f"Bearer {token}"}
        r = await c.post(
            f"/api/contexts/{ctx_id}/signals/{sid}/actions",
            json={"action_type": "deleted"},
            headers=h,
        )
        assert r.status_code == 422, r.text
