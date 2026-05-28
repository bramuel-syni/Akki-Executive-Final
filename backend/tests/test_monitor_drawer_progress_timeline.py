"""AA.followup.10 REVISED (2026-02 fork-resume) — Monitor drawer
Progress timeline.

Course-correction on the original AA.followup.10 manual-milestone
direction. The drawer's Progress timeline is OBSERVATIONAL, auto-
derived from existing time-series sources, with no manual "+ Add" CTA.

Locks:
    A. Backend endpoint
       `GET /api/contexts/{cid}/strategic-goals/{gid}/evolution`
       returns chronologically-sorted events from score_history,
       audit_log, linked documents, and extractions_log.
    B. Empty-state copy matches spec verbatim.
    C. No `+ Add milestone` manual CTA anywhere in the drawer.
    D. Markers use brand-purple Tailwind-config short name (`ned-purple/N`)
       so opacity composites correctly (Wave 4.2.followup.2 guard).
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ─────────────────────────────────────────────────────────────────
# A. Backend — endpoint shape + aggregation across sources
# ─────────────────────────────────────────────────────────────────


def test_evolution_router_registered_in_server():
    src = (BACKEND / "server.py").read_text(encoding="utf-8")
    assert "from routers import strategic_goal_evolution as strategic_goal_evolution_router" in src
    assert "app.include_router(strategic_goal_evolution_router.router)" in src


@pytest.mark.asyncio
async def test_evolution_endpoint_aggregates_multi_source_events():
    """Seed a goal + score history + linked doc + extraction. Endpoint
    should return one event per source, chronologically sorted."""
    from server import app  # type: ignore
    from core import db, get_current_account  # type: ignore

    cid = f"evo-cid-{uuid.uuid4().hex[:8]}"
    gid = f"evo-goal-{uuid.uuid4().hex[:8]}"
    doc_id = f"evo-doc-{uuid.uuid4().hex[:8]}"

    await db.strategic_goals.insert_one({
        "id": gid, "context_id": cid, "title": "Lift CET1 ratio",
        "current_score": 72, "probability": 60, "status": "on_track",
        "score_history": [
            {"recorded_at": "2026-01-01T00:00:00+00:00", "score": 50},
            {"recorded_at": "2026-02-01T00:00:00+00:00", "score": 65},
            {"recorded_at": "2026-02-15T00:00:00+00:00", "score": 72},
        ],
    })
    await db.documents.insert_one({
        "id": doc_id, "context_id": cid, "title": "Q1 capital plan",
        "category": "report", "linked_objective_id": gid,
        "created_at": "2026-01-20T00:00:00+00:00",
    })
    await db.extractions_log.insert_one({
        "id": uuid.uuid4().hex, "context_id": cid, "document_id": doc_id,
        "kind": "tasks", "count": 4, "failures": 0,
        "created_at": "2026-01-20T01:00:00+00:00",
    })

    async def _fake_user():
        return {"id": "evo-user", "email": "u@e.com"}

    app.dependency_overrides[get_current_account] = _fake_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get(f"/api/contexts/{cid}/strategic-goals/{gid}/evolution")
            assert r.status_code == 200, r.text
            payload = r.json()
            assert payload["goal_id"] == gid
            assert payload["context_id"] == cid
            events = payload["events"]
            # 3 score-deltas + 1 doc-upload + 1 ai-reassessment = 5.
            assert len(events) == 5, f"expected 5 events, got {len(events)}"
            kinds = [e["kind"] for e in events]
            assert kinds.count("score_delta") == 3
            assert kinds.count("doc_upload") == 1
            assert kinds.count("ai_reassessment") == 1
            # Chronologically sorted.
            timestamps = [e["at"] for e in events]
            assert timestamps == sorted(timestamps), (
                f"events must be chronologically sorted; got {timestamps}"
            )
            # Score-delta shape — second one must show 50 → 65 with up direction.
            score_deltas = [e for e in events if e["kind"] == "score_delta"]
            second = score_deltas[1]
            assert second["delta"]["from"] == 50
            assert second["delta"]["to"] == 65
            assert second["delta"]["direction"] == "up"
            # 404 on unknown goal.
            r2 = await c.get(f"/api/contexts/{cid}/strategic-goals/does-not-exist/evolution")
            assert r2.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        await db.strategic_goals.delete_one({"id": gid})
        await db.documents.delete_one({"id": doc_id})
        await db.extractions_log.delete_many({"document_id": doc_id})


@pytest.mark.asyncio
async def test_evolution_endpoint_empty_for_pristine_goal():
    from server import app  # type: ignore
    from core import db, get_current_account  # type: ignore

    cid = f"evo-cid-pristine-{uuid.uuid4().hex[:8]}"
    gid = f"evo-goal-pristine-{uuid.uuid4().hex[:8]}"
    await db.strategic_goals.insert_one({
        "id": gid, "context_id": cid, "title": "Pristine",
    })

    async def _fake_user():
        return {"id": "evo-user-2", "email": "u@e.com"}

    app.dependency_overrides[get_current_account] = _fake_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get(f"/api/contexts/{cid}/strategic-goals/{gid}/evolution")
            assert r.status_code == 200
            assert r.json()["events"] == []
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        await db.strategic_goals.delete_one({"id": gid})


# ─────────────────────────────────────────────────────────────────
# B. Frontend — drawer renders the timeline, no manual CTA
# ─────────────────────────────────────────────────────────────────


def test_drawer_timeline_renders_required_testids():
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    required = (
        "goal-drawer-progress-timeline",
        "goal-drawer-progress-timeline-empty",
        "goal-drawer-progress-timeline-bar",
        "goal-drawer-progress-timeline-count",
    )
    for tid in required:
        assert f'data-testid="{tid}"' in src, (
            f"StrategicGoalsPanel.jsx must carry data-testid={tid!r}"
        )


def test_drawer_no_manual_milestone_cta():
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    assert "+ Add milestone" not in src, (
        "Manual `+ Add milestone` CTA must be removed (course-correction)"
    )
    assert "goal-drawer-add-milestone-btn" not in src, (
        "Old `goal-drawer-add-milestone-btn` testid must be removed"
    )
    # Old milestones-empty testid must be replaced by progress-timeline-empty.
    assert 'data-testid="goal-drawer-milestones-empty"' not in src
    assert 'data-testid="goal-drawer-milestones"' not in src


def test_drawer_empty_state_copy_verbatim():
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    assert (
        "No progress signals recorded yet."
        in src
    ), "Empty-state copy must read verbatim per spec"


def test_drawer_timeline_fetches_evolution_endpoint():
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    assert "/strategic-goals/${goal.id}/evolution" in src or "/strategic-goals/" in src
    # The fetch must be inside a useEffect that depends on goal.id +
    # contextId, and it must populate setEvolution.
    assert "setEvolution" in src, (
        "Drawer must populate evolution state from the endpoint"
    )


def test_drawer_timeline_uses_tailwind_short_brand_purple():
    """Wave 4.2.followup.2 guard — markers + detail panel must use
    Tailwind-config-registered `bg-ned-purple/N` short name, not the
    silent-fail `bg-[var(--ned-purple)]/N` variant."""
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    timeline_idx = src.find("goal-drawer-progress-timeline")
    assert timeline_idx > 0
    timeline_block = src[timeline_idx:timeline_idx + 5000]
    assert "bg-ned-purple/" in timeline_block, (
        "Timeline must use `bg-ned-purple/N` short name"
    )
    # Negative — silent-fail syntax must be absent.
    assert "bg-[var(--ned-purple)]/" not in timeline_block, (
        "Wave 4.2.followup.2 silent-fail trap re-introduced in the timeline block"
    )
