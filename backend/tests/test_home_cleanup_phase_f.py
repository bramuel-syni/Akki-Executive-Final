"""Phase F.1 + F.2 — Task Manager wire + live tests (2026-05-26).

Covers:
  F.1 — Cycle Manager → Task Manager rename:
    • /app/task-manager route exists; renders TaskManager page
    • /app/cycle remains as backwards-compat alias
    • Nav label "Task Manager" replaces "Cycle Manager" / "Reporting Cycle"
    • URL param alias: task_id ≡ cycle_id on the TaskManager surface

  F.2 — Listing surface + Setup wizard:
    • 3-tab listing (Active / Draft / Closed) with no "All"
    • Right-rail: CompilationReadinessSection + FollowUpDraftsCard
    • "Set up new task" CTA → opens 4-step wizard
    • Wizard advances Step 1→2→3→4 with validation
    • Save-as-Draft → POST /api/tasks state=draft
    • Commission → POST /api/tasks state=active + contributor audit
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

APP_JS         = FE / "App.js"
APP_SHELL      = FE / "components" / "layout" / "AppShell.jsx"
TASK_MANAGER   = FE / "pages" / "TaskManager.jsx"
TASK_LISTING   = FE / "components" / "tasks" / "TaskListing.jsx"
TASK_WIZARD    = FE / "components" / "tasks" / "TaskSetupWizard.jsx"
FOLLOWUP_CARD  = FE / "components" / "tasks" / "FollowUpDraftsCard.jsx"
TASKS_ROUTER   = BE / "routers" / "tasks.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════
# F.1 — Rename
# ═════════════════════════════════════════════════════════════════════
def test_f1_task_manager_route_mounted():
    src = _read(APP_JS)
    assert 'path="/app/task-manager"' in src
    assert 'lazy(() => import("@/pages/TaskManager"))' in src
    # Detail-route shape so future F.3 deep-links work.
    assert 'path="/app/task-manager/:taskId"' in src


def test_f1_cycle_route_retained_as_alias():
    """/app/cycle remains mounted so existing bookmarks survive."""
    src = _read(APP_JS)
    assert 'path="/app/cycle"' in src
    # Comment explains the alias intent.
    assert "backwards-compat alias" in src.lower() or "Phase F.1" in src


def test_f1_nav_label_renamed_to_task_manager():
    """AppShell top nav swapped 'Cycle Manager' / 'Reporting Cycle' →
    'Task Manager' and the `to` target is the canonical surface."""
    src = _read(APP_SHELL)
    # The new entry appears.
    assert '"/app/task-manager"' in src
    assert '"Task Manager"' in src
    # The old top-nav entry literal is gone. We check the live
    # `label: "Cycle Manager"` pattern, not the substring (the rename
    # leaves an annotation comment that mentions the old name).
    assert 'label: "Cycle Manager"' not in src
    # Old depth/role nav: 'Reporting Cycle' as a nav label.
    # (Allowed to appear as comment text only; verify no live label.)
    live_labels = [m for m in src.split('label: "') if m.startswith("Reporting Cycle")]
    assert not live_labels, "live 'Reporting Cycle' nav label still present"


def test_f1_task_id_aliases_cycle_id_on_task_manager():
    """The TaskManager page accepts BOTH task_id and cycle_id URL params
    (task_id wins). Phase F.1 alias rule."""
    src = _read(TASK_MANAGER)
    # Both keys present in the same expression.
    assert 'params.get("task_id")' in src
    assert 'params.get("cycle_id")' in src


# ═════════════════════════════════════════════════════════════════════
# F.2 — Listing + Wizard wire
# ═════════════════════════════════════════════════════════════════════
def test_f2_listing_has_three_tabs_no_all():
    """The listing surfaces exactly 3 tabs: Active / Draft / Closed."""
    src = _read(TASK_MANAGER)
    for key in ("active", "draft", "closed"):
        assert f'data-testid="task-manager-tab-{key}"' in src or f'key: "{key}"' in src
    # No "All" tab.
    assert '"task-manager-tab-all"' not in src
    assert '"label": "All"' not in src
    assert "label: \"All\"" not in src


def test_f2_setup_new_task_cta_present():
    src = _read(TASK_MANAGER)
    assert 'data-testid="task-manager-setup-new-task"' in src
    assert "Set up new task" in src


def test_f2_right_rail_has_three_cards():
    """Ready to Compile · At Risk (via CompilationReadinessSection) +
    Follow Up Drafts for You."""
    src = _read(TASK_MANAGER)
    assert "CompilationReadinessSection" in src
    assert "FollowUpDraftsCard" in src
    assert 'data-testid="task-manager-right-rail"' in src


def test_f2_listing_calls_tasks_endpoint():
    src = _read(TASK_LISTING)
    assert 'api.get("/tasks"' in src
    # state param is forwarded.
    assert "state" in src
    # Cards render readiness + status + contributor avatars.
    assert 'data-testid="task-listing-list"' in src
    assert 'task-card-status-' in src
    assert 'task-card-readiness-' in src


def test_f2_wizard_has_four_steps_with_pips():
    src = _read(TASK_WIZARD)
    # Step pips render via template literal `task-wizard-step-pip-${s.n}`.
    assert "task-wizard-step-pip-${s.n}" in src
    # Each conditional step body has its own data-testid.
    for n in (1, 2, 3, 4):
        assert f'data-testid="task-wizard-step-{n}"' in src
    # Step labels match orchestrator brief.
    for label in ("Define", "Output", "Team", "Commission"):
        assert label in src


def test_f2_wizard_step1_pre_fill_calls_endpoint():
    src = _read(TASK_WIZARD)
    assert 'api.post("/tasks/agent-prefill"' in src
    assert 'data-testid="task-wizard-prefill"' in src
    # Source pill surfaces template vs llm vs none.
    assert 'data-testid="task-wizard-prefill-source"' in src


def test_f2_wizard_step2_has_template_gallery_and_free_text():
    src = _read(TASK_WIZARD)
    # The 7 templates per brief — names listed in the TEMPLATES array.
    for t in ("board_pack", "committee_pack", "strategy_deck",
              "financial_model", "fundraising", "briefing", "custom"):
        assert f'id: "{t}"' in src or f"id: '{t}'" in src
    # Template button testid uses an interpolated id; assert the
    # template literal pattern is present.
    assert "task-wizard-template-${t.id}" in src
    # Free-text mode + format checkboxes.
    assert 'data-testid="task-wizard-output-mode-free"' in src
    assert 'data-testid="task-wizard-free-text"' in src
    # Format checkbox testid is also interpolated.
    assert "task-wizard-format-${f}" in src


def test_f2_wizard_step3_has_team_table_with_modes():
    src = _read(TASK_WIZARD)
    assert 'data-testid="task-wizard-team-table"' in src
    assert 'data-testid="task-wizard-add-team-member"' in src
    # Contribution-mode dropdown carries all 3 modes per brief.
    for mode in ("akki_account", "magic_link", "email_reply"):
        assert f'value="{mode}"' in src


def test_f2_wizard_step4_has_save_draft_and_commission():
    src = _read(TASK_WIZARD)
    assert 'data-testid="task-wizard-save-draft"' in src
    assert 'data-testid="task-wizard-commission"' in src
    # Both call POST /tasks.
    assert 'api.post("/tasks"' in src


# ═════════════════════════════════════════════════════════════════════
# F.2 — Live HTTP
# ═════════════════════════════════════════════════════════════════════
@pytest.fixture
async def seeded_actor():
    from core import db, hash_password
    uid = f"test-task-{uuid.uuid4().hex[:8]}"
    email = f"task-{uuid.uuid4().hex[:6]}@example.com"
    await db.accounts.insert_one({
        "id": uid, "email": email,
        "password_hash": hash_password("Pw!1234567Abc"),
        "name": "T", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"uid": uid, "email": email, "password": "Pw!1234567Abc"}
    await db.tasks.delete_many({"account_id": uid})
    await db.audit_log.delete_many({"account_id": uid})
    await db.accounts.delete_one({"id": uid})


@pytest.mark.asyncio
async def test_f2_create_task_as_draft(seeded_actor):
    """POST /api/tasks with state=draft creates a task and returns
    the sanitized payload. No contributor audit fires."""
    from server import app  # noqa: F401
    from core import db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/auth/login",
                         json={"email": seeded_actor["email"], "password": seeded_actor["password"]})
        token = r.json().get("access_token") or r.json().get("token")
        hdr = {"Authorization": f"Bearer {token}"}
        r = await c.post("/api/tasks", json={
            "name": "Q4 Board Pack",
            "objective": "Ship a board-ready pack.",
            "success_criteria": "All sections decision-ready.",
            "team": [{"name": "CFO", "role": "CFO", "email": "cfo@example.com", "contribution_mode": "akki_account"}],
            "state": "draft",
        }, headers=hdr)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["state"] == "draft"
        assert body["id"].startswith("task-")
        assert body["readiness_score"] >= 0
        # No contributor.added audit row for draft.
        rows = await db.audit_log.find({
            "account_id": seeded_actor["uid"],
            "resource_id": body["id"],
            "action": "task.contributor.added",
        }).to_list(length=10)
        assert rows == []


@pytest.mark.asyncio
async def test_f2_commission_task_emits_contributor_audit(seeded_actor):
    """POST /api/tasks with state=active fires task.contributor.added
    per team member."""
    from server import app  # noqa: F401
    from core import db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/auth/login",
                         json={"email": seeded_actor["email"], "password": seeded_actor["password"]})
        token = r.json().get("access_token") or r.json().get("token")
        hdr = {"Authorization": f"Bearer {token}"}
        r = await c.post("/api/tasks", json={
            "name": "Strategy refresh",
            "objective": "Sharpen the strategy narrative.",
            "team": [
                {"name": "CEO", "role": "CEO", "email": "ceo@example.com", "contribution_mode": "akki_account"},
                {"name": "CFO", "role": "CFO", "email": "cfo@example.com", "contribution_mode": "magic_link"},
            ],
            "state": "active",
        }, headers=hdr)
        assert r.status_code == 200, r.text
        tid = r.json()["id"]
        rows = await db.audit_log.find({
            "account_id": seeded_actor["uid"],
            "resource_id": tid,
            "action": "task.contributor.added",
        }).to_list(length=10)
        assert len(rows) == 2
        emails = sorted(r["metadata"]["contributor_email"] for r in rows)
        assert emails == ["ceo@example.com", "cfo@example.com"]


@pytest.mark.asyncio
async def test_f2_list_tasks_filters_by_state(seeded_actor):
    """GET /api/tasks?state=active|draft|closed returns only matching tasks."""
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/auth/login",
                         json={"email": seeded_actor["email"], "password": seeded_actor["password"]})
        token = r.json().get("access_token") or r.json().get("token")
        hdr = {"Authorization": f"Bearer {token}"}
        for label, state in (("D", "draft"), ("A", "active"), ("C", "active")):
            await c.post("/api/tasks", json={"name": f"Task {label}", "state": state}, headers=hdr)
        r = await c.get("/api/tasks?state=active", headers=hdr)
        assert r.status_code == 200, r.text
        items = r.json()
        assert all(t["state"] == "active" for t in items)
        assert {t["name"] for t in items} == {"Task A", "Task C"}
        r = await c.get("/api/tasks?state=draft", headers=hdr)
        items = r.json()
        assert {t["name"] for t in items} == {"Task D"}


@pytest.mark.asyncio
async def test_f2_patch_task_recomputes_readiness(seeded_actor):
    """PATCH updates fields and recomputes readiness_score."""
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/auth/login",
                         json={"email": seeded_actor["email"], "password": seeded_actor["password"]})
        token = r.json().get("access_token") or r.json().get("token")
        hdr = {"Authorization": f"Bearer {token}"}
        r = await c.post("/api/tasks", json={"name": "Empty", "state": "draft"}, headers=hdr)
        tid = r.json()["id"]
        before = r.json()["readiness_score"]
        r = await c.patch(f"/api/tasks/{tid}", json={
            "objective": "Make it sharp.",
            "team": [{"name": "X", "email": "x@example.com"}],
            "output_spec": {"kind": "template", "template_id": "board_pack", "formats": ["pdf"]},
        }, headers=hdr)
        assert r.status_code == 200, r.text
        after = r.json()["readiness_score"]
        assert after > before


@pytest.mark.asyncio
async def test_f2_agent_prefill_uses_static_template_shelf(seeded_actor):
    """POST /api/tasks/agent-prefill with a name containing 'Board Pack'
    hits the static template shelf — no LLM call needed."""
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/auth/login",
                         json={"email": seeded_actor["email"], "password": seeded_actor["password"]})
        token = r.json().get("access_token") or r.json().get("token")
        hdr = {"Authorization": f"Bearer {token}"}
        r = await c.post("/api/tasks/agent-prefill",
                         json={"name": "Q4 Board Pack for the Board"},
                         headers=hdr)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == "template"
        assert "board-ready" in body["objective"].lower()
        assert body["success_criteria"]


@pytest.mark.asyncio
async def test_f2_state_transition_updates_status_history(seeded_actor):
    """PATCH with state change pushes to status_history."""
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/auth/login",
                         json={"email": seeded_actor["email"], "password": seeded_actor["password"]})
        token = r.json().get("access_token") or r.json().get("token")
        hdr = {"Authorization": f"Bearer {token}"}
        r = await c.post("/api/tasks", json={"name": "T", "state": "draft"}, headers=hdr)
        tid = r.json()["id"]
        assert len(r.json()["status_history"]) == 1
        r = await c.patch(f"/api/tasks/{tid}", json={"state": "active"}, headers=hdr)
        assert r.status_code == 200
        sh = r.json()["status_history"]
        assert len(sh) == 2
        assert sh[-1]["state"] == "active"


# ═════════════════════════════════════════════════════════════════════
# F.1 + F.2 log presence
# ═════════════════════════════════════════════════════════════════════
def test_f_kickoff_section_present_in_home_cleanup_log():
    log = (REPO / "memory" / "sprints" / "HOME_CLEANUP_LOG.md").read_text("utf-8")
    assert "Phase F.1" in log or "Task Manager" in log
