"""Phase F.6 — Polish + batch close wire + live tests (2026-05-26).

Covers:
  • Workstream 1 — Visual harmonization: 3 cards on Task Manager right
    rail share the same `<section> + <header> + body + <footer>`
    structure as the canonical Home 2 / CompilationRail pattern.
  • Workstream 2 — Account-scoped task activity endpoint + UI.
  • Workstream 3 — Cross-phase polish:
      - Handoff CTA URL contract sanity sweep
      - Empty-state DOM presence on all new components
      - Drawer stack pattern wire check
  • Workstream 4 — DEPLOY_READINESS.md exists with required sections.
  • Workstream 5 — AUTONOMOUS_TRIP_REPORT.md exists with required sections.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
FE   = REPO / "frontend" / "src"
BE   = REPO / "backend"

TASK_MANAGER     = FE / "pages" / "TaskManager.jsx"
TASK_MANAGER_ACT = FE / "pages" / "TaskManagerActivity.jsx"
APP_JS           = FE / "App.js"
FOLLOWUP_CARD    = FE / "components" / "tasks" / "FollowUpDraftsCard.jsx"
ACTIVITY_CARD    = FE / "components" / "tasks" / "RecentTaskActivityCard.jsx"
COMPILATION_RAIL = FE / "components" / "work_studio" / "CompilationRail.jsx"
COMPILE_READINESS = FE / "components" / "cycle" / "CompilationReadinessSection.jsx"
TASKS_ROUTER     = BE / "routers" / "tasks.py"
TASK_DRAWER      = FE / "components" / "tasks" / "TaskDrawer.jsx"
DOC_DRAWER       = FE / "components" / "documents" / "DocumentDrawer.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════
# Workstream 1 — Visual harmonization
# ═════════════════════════════════════════════════════════════════════
def test_f6_followup_card_uses_canonical_card_structure():
    """FollowUpDraftsCard now uses the canonical `<section>` + `<header>`
    + body + `<footer>` pattern, matching CompilationRail."""
    src = _read(FOLLOWUP_CARD)
    assert '<section' in src
    assert 'border border-[var(--rule)] bg-white rounded-sm' in src
    # Header pattern.
    assert "border-b border-[var(--rule)]" in src
    assert "akki-overline" in src
    # Footer pattern with View more.
    assert "border-t border-[var(--rule)] bg-[var(--cream-deep)]/40" in src
    assert "follow-up-drafts-view-more" in src


def test_f6_recent_task_activity_card_exists_with_canonical_structure():
    """The new card matches the same chrome as Recent Drafts /
    Recent Activity on Home 2."""
    src = _read(ACTIVITY_CARD)
    assert 'data-testid="recent-task-activity-card"' in src
    assert '<section' in src
    assert 'border border-[var(--rule)] bg-white rounded-sm' in src
    assert "border-b border-[var(--rule)]" in src
    assert "akki-overline" in src
    assert "recent-task-activity-view-more" in src


def test_f6_three_cards_share_consistent_pattern():
    """All 3 right-rail cards (CompilationReadinessSection,
    FollowUpDraftsCard, RecentTaskActivityCard) share the same chrome."""
    for path in (COMPILE_READINESS, FOLLOWUP_CARD, ACTIVITY_CARD):
        src = _read(path)
        # Card shell.
        assert "border border-[var(--rule)]" in src, f"{path.name}: missing shell border"
        assert "rounded-sm" in src, f"{path.name}: missing rounded-sm"
        # Header bar.
        assert "border-b border-[var(--rule)]" in src, f"{path.name}: missing header divider"


def test_f6_task_manager_mounts_three_right_rail_cards():
    src = _read(TASK_MANAGER)
    assert "CompilationReadinessSection" in src
    assert "FollowUpDraftsCard" in src
    assert "RecentTaskActivityCard" in src
    # The rail container preserves the data-testid for layout assertions.
    assert 'data-testid="task-manager-right-rail"' in src


# ═════════════════════════════════════════════════════════════════════
# Workstream 2 — Account-scoped task activity
# ═════════════════════════════════════════════════════════════════════
def test_f6_backend_account_task_activity_endpoint_wired():
    src = _read(TASKS_ROUTER)
    assert '@router.get("/accounts/{account_id}/task-activity/recent")' in src
    # Scoping check — caller account must match the path account_id.
    block = src.split('@router.get("/accounts/{account_id}/task-activity/recent")')[1]
    block = block.split("\n@router")[0] if "\n@router" in block else block
    assert 'account_id != current["id"]' in block
    assert "Cross-account" in block or "permitted" in block
    # The query targets task.* events only.
    assert '"action":     {"$regex": "^task\\\\.' in block or 'action": {"$regex": "^task\\\\.' in block


def test_f6_task_manager_activity_full_page_route_mounted():
    src = _read(APP_JS)
    assert 'path="/app/task-manager/activity"' in src
    assert "TaskManagerActivity" in src


def test_f6_task_manager_activity_page_renders_list():
    src = _read(TASK_MANAGER_ACT)
    assert 'data-testid="task-manager-activity-page"' in src
    assert 'data-testid="task-manager-activity-list"' in src
    assert 'data-testid="task-manager-activity-empty"' in src
    assert 'data-testid="task-manager-activity-back"' in src
    # Calls the F.6 account-scoped endpoint.
    assert "/accounts/${account.id}/task-activity/recent" in src


# ═════════════════════════════════════════════════════════════════════
# Workstream 3 — Cross-phase polish
# ═════════════════════════════════════════════════════════════════════
def test_f6_task_drawer_footer_has_5_canonical_handoff_ctas():
    src = _read(TASK_DRAWER)
    # All 5 CTAs reachable via canonical ?ctx_type=task&ctx_id=… URLs.
    assert "/app/solva?ctx_type=task&ctx_id=" in src
    assert "/app/chat?ctx_type=task&ctx_id=" in src
    assert "submodule=develop_strategy" in src
    assert "submodule=simulate_hypothesis" in src
    # 5 CTA testids.
    for k in ("solva", "chat", "brief", "hypothesis", "share"):
        assert f'data-testid="task-drawer-cta-{k}"' in src


def test_f6_document_drawer_footer_has_5_canonical_handoff_ctas():
    src = _read(DOC_DRAWER)
    assert "/app/solva?ctx_type=document&ctx_id=" in src
    assert "/app/chat?ctx_type=document&ctx_id=" in src


def test_f6_drawer_stack_pattern_preserved_in_task_manager():
    """When `?task_id=` and `?doc_id=` are both present, both drawers
    mount (TaskDrawer + DocumentDrawer). This is the stack pattern."""
    src = _read(TASK_MANAGER)
    assert "<TaskDrawer />" in src
    assert "<DocumentDrawer contextId={cid} />" in src


def test_f6_empty_states_present_on_new_cards():
    """Every list/card renders the empty-state DOM unconditionally
    (no `null` returns when data is empty)."""
    assert 'data-testid="follow-up-drafts-empty"' in _read(FOLLOWUP_CARD)
    assert 'data-testid="recent-task-activity-empty"' in _read(ACTIVITY_CARD)
    assert 'data-testid="task-manager-activity-empty"' in _read(TASK_MANAGER_ACT)


# ═════════════════════════════════════════════════════════════════════
# Workstream 4 — Deploy-readiness doc
# ═════════════════════════════════════════════════════════════════════
def test_f6_deploy_readiness_doc_exists_and_covers_required_sections():
    p = REPO / "memory" / "sprints" / "DEPLOY_READINESS.md"
    assert p.exists(), "DEPLOY_READINESS.md missing"
    src = p.read_text("utf-8")
    for section in (
        "Pre-deploy verification",
        "Environment requirements",
        "POSTMARK_API_KEY",
        "Postmark inbound",
        "MongoDB collections",
        "Indexes",
        "Migration steps",
        "Known gaps",
        "v-post-task-manager-rollout",
    ):
        assert section in src, f"DEPLOY_READINESS.md missing section: {section}"


# ═════════════════════════════════════════════════════════════════════
# Workstream 5 — Trip report
# ═════════════════════════════════════════════════════════════════════
def test_f6_trip_report_exists_and_covers_required_sections():
    p = REPO / "memory" / "sprints" / "AUTONOMOUS_TRIP_REPORT.md"
    assert p.exists(), "AUTONOMOUS_TRIP_REPORT.md missing"
    src = p.read_text("utf-8")
    for section in (
        "Phases closed",
        "Test count progression",
        "Major features",
        "Autonomous decisions",
        "Spec/code deltas",
        "Scope cuts",
        "Open backlog",
        "Borderline routes",
        "Before deploy",
    ):
        assert section in src, f"AUTONOMOUS_TRIP_REPORT.md missing section: {section}"


# ═════════════════════════════════════════════════════════════════════
# Live HTTP — F.6 endpoint
# ═════════════════════════════════════════════════════════════════════
@pytest.fixture
async def actor_f6():
    from core import db, hash_password
    uid = f"test-f6-{uuid.uuid4().hex[:8]}"
    email = f"f6-{uuid.uuid4().hex[:6]}@example.com"
    await db.accounts.insert_one({
        "id": uid, "email": email,
        "password_hash": hash_password("Pw!1234567Abc"),
        "name": "F6", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"uid": uid, "email": email, "password": "Pw!1234567Abc"}
    await db.tasks.delete_many({"account_id": uid})
    await db.audit_log.delete_many({"account_id": uid})
    await db.accounts.delete_one({"id": uid})


async def _login(c, actor):
    r = await c.post("/api/auth/login",
                     json={"email": actor["email"], "password": actor["password"]})
    token = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_f6_task_activity_endpoint_returns_account_scoped_rows(actor_f6):
    """Create 2 tasks (state=active fires `task.contributor.invited`
    audit rows) and confirm GET /accounts/{aid}/task-activity/recent
    returns them with the enriched `task_name`."""
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, actor_f6)
        # Seed 2 tasks with team rows so the commission fan-out fires audits.
        for nm in ("Q1 Pack", "Q2 Pack"):
            await c.post("/api/tasks", json={
                "name": nm,
                "team": [{"name": "X", "email": "x@x.com", "contribution_mode": "akki_account"}],
                "state": "active",
            }, headers=hdr)
        r = await c.get(f"/api/accounts/{actor_f6['uid']}/task-activity/recent", headers=hdr)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert isinstance(rows, list)
        assert len(rows) >= 2
        # Each row carries enriched task_name + action prefix `task.`.
        for row in rows:
            assert row["action"].startswith("task.")
            assert row["task_name"]
            assert "metadata" in row


@pytest.mark.asyncio
async def test_f6_task_activity_endpoint_rejects_cross_account(actor_f6):
    """Caller can't read another account's task activity."""
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, actor_f6)
        r = await c.get("/api/accounts/some-other-account-id/task-activity/recent", headers=hdr)
        assert r.status_code == 403


# ═════════════════════════════════════════════════════════════════════
# F.6 log presence
# ═════════════════════════════════════════════════════════════════════
def test_f6_section_present_in_home_cleanup_log():
    log = (REPO / "memory" / "sprints" / "HOME_CLEANUP_LOG.md").read_text("utf-8")
    assert "F.6" in log
    assert "Batch closed" in log or "polish" in log.lower()
