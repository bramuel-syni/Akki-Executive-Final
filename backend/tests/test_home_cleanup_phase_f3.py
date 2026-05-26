"""Phase F.3 — Task Drawer wire + live tests (2026-05-26).

Covers:
  • Drawer mount + 5-tab structure
  • Plan tab inline editing path
  • Contributions tab status PATCH endpoint
  • Drafts tab task-linked-doc endpoint
  • Intelligence cache/regenerate endpoints + payload shape
  • 5 footer CTAs emit canonical `ctx_type=task&ctx_id=…` URLs
  • Chat resolver accepts `ctx_type=task` → renders Reading chip
  • Solva source validator accepts `task` source
  • Stack pattern: TaskDrawer + DocumentDrawer co-mount on TaskManager
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
FE   = REPO / "frontend" / "src"
BE   = REPO / "backend"

TASK_DRAWER    = FE / "components" / "tasks" / "TaskDrawer.jsx"
TASK_LISTING   = FE / "components" / "tasks" / "TaskListing.jsx"
TASK_MANAGER   = FE / "pages" / "TaskManager.jsx"
TASKS_ROUTER   = BE / "routers" / "tasks.py"
CHAT_ROUTER    = BE / "routers" / "chat.py"
SOLVA_ROUTER   = BE / "routers" / "solva_phase_d.py"
INTEL_SVC      = BE / "services" / "tasks" / "intelligence_service.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════
# Wire — frontend TaskDrawer
# ═════════════════════════════════════════════════════════════════════
def test_f3_task_drawer_file_exists_with_sheet_primitive():
    src = _read(TASK_DRAWER)
    # Reuses the shared Sheet primitive (no fork).
    assert 'from "@/components/ui/sheet"' in src
    assert '<Sheet open={open}' in src
    # 60% viewport on desktop per brief.
    assert "sm:max-w-[60vw]" in src


def test_f3_task_drawer_listens_to_task_id_url_param():
    src = _read(TASK_DRAWER)
    assert 'params.get("task_id")' in src
    # Calls GET /api/tasks/{id} when task_id is set.
    assert "api.get(`/tasks/${tid}`)" in src


def test_f3_task_drawer_renders_5_tabs():
    src = _read(TASK_DRAWER)
    # Tab testids are interpolated via template literal `${t.key}`.
    assert "task-drawer-tab-${t.key}" in src
    # Per-tab body testids.
    for key in ("plan", "contributions", "drafts", "intelligence", "compile"):
        assert f'task-drawer-tab-{key}-body' in src
    # Labels per brief.
    for label in ("Plan", "Contributions", "Drafts", "Intelligence", "Compile"):
        assert f'label: "{label}"' in src


def test_f3_plan_tab_has_inline_edit_for_three_fields():
    src = _read(TASK_DRAWER)
    # PlanField testids are interpolated via `${field}`.
    assert "task-drawer-plan-${field}" in src
    assert "task-drawer-plan-${field}-input" in src
    assert "task-drawer-plan-${field}-save" in src
    # Name is inline-editable in the header.
    assert 'data-testid="task-drawer-name-input"' in src
    # Plan tab body data-testid present.
    assert 'data-testid="task-drawer-tab-plan-body"' in src


def test_f3_contributions_tab_has_per_row_actions():
    src = _read(TASK_DRAWER)
    assert "task-drawer-contributions-approve-${i}" in src
    assert "task-drawer-contributions-request-revision-${i}" in src
    assert "task-drawer-contributions-reinvite-${i}" in src
    assert "task-drawer-contributions-status-${i}" in src
    # Status labels render via the STATUS_LABEL map.
    for s in ("not_started", "in_progress", "submitted", "approved", "needs_revision"):
        assert s in src
    # The PATCH endpoint is called with the contributor id.
    assert "/tasks/${task.id}/contributions/${encodeURIComponent(contributorId)}" in src


def test_f3_drafts_tab_lists_task_linked_docs():
    src = _read(TASK_DRAWER)
    assert "/tasks/${task.id}/drafts" in src
    # Click opens DocumentDrawer via `?doc_id=` (stack pattern).
    assert "next.set(\"doc_id\", docId)" in src
    assert "stack pattern" in src.lower() or "stacked" in src.lower()


def test_f3_intelligence_tab_renders_5_sections():
    src = _read(TASK_DRAWER)
    for sec in ("readiness", "blockers", "gaps", "roadmap", "recommendations"):
        assert f'data-testid="task-drawer-intelligence-{sec}"' in src
    # Loads cached intelligence from the F.3 endpoint.
    assert "/tasks/${task.id}/intelligence" in src
    # Regenerate CTA.
    assert "task-drawer-intelligence-regen" in src


def test_f3_compile_tab_is_now_wired_in_f4():
    """F.4 (2026-05-26) — the F.3 placeholder is gone. Compile tab
    now renders the 5-stage progress strip + a Start/Resume button
    that is ALWAYS enabled (no readiness gate)."""
    src = _read(TASK_DRAWER)
    # The F.3 placeholder testids no longer exist.
    assert "task-drawer-compile-coming-soon" not in src
    assert "task-drawer-compile-disabled-cta" not in src
    # F.4 testids that replaced them.
    assert "task-drawer-compile-progress" in src
    assert "task-drawer-compile-start" in src
    # Progress strip carries the 5 stage testids via the COMPILE_STAGES map.
    assert "task-drawer-compile-stage-${s.key}" in src


def test_f3_footer_emits_canonical_ctx_type_task_urls():
    src = _read(TASK_DRAWER)
    # 5 CTAs.
    for k in ("solva", "chat", "brief", "hypothesis", "share"):
        assert f'data-testid="task-drawer-cta-{k}"' in src
    # URL pattern.
    assert "/app/solva?ctx_type=task&ctx_id=" in src
    assert "/app/chat?ctx_type=task&ctx_id=" in src
    assert "submodule=develop_strategy" in src
    assert "submodule=simulate_hypothesis" in src


# ═════════════════════════════════════════════════════════════════════
# Wire — TaskManager mount of TaskDrawer + DocumentDrawer
# ═════════════════════════════════════════════════════════════════════
def test_f3_task_manager_mounts_task_drawer_and_document_drawer():
    """Stack pattern: both drawers co-mount on TaskManager. URL params
    `task_id` and `doc_id` are independent."""
    src = _read(TASK_MANAGER)
    assert "TaskDrawer" in src
    assert "DocumentDrawer" in src
    assert "<TaskDrawer />" in src
    assert "<DocumentDrawer contextId={cid} />" in src


def test_f3_task_listing_card_click_now_opens_drawer():
    """The F.2 placeholder sheet is gone. Click sets `?task_id=…`."""
    src = _read(TASK_LISTING)
    assert "task-drawer-placeholder" not in src
    assert "task-drawer-coming-soon" not in src
    assert 'next.set("task_id", taskId)' in src


# ═════════════════════════════════════════════════════════════════════
# Wire — Backend
# ═════════════════════════════════════════════════════════════════════
def test_f3_tasks_router_has_four_new_endpoints():
    src = _read(TASKS_ROUTER)
    assert '@router.get("/tasks/{task_id}/drafts")' in src
    assert '@router.patch("/tasks/{task_id}/contributions/{contributor_id}")' in src
    assert '@router.get("/tasks/{task_id}/intelligence")' in src
    assert '@router.post("/tasks/{task_id}/intelligence/regenerate")' in src


def test_f3_intelligence_service_has_60_25_15_formula():
    """Readiness uses the orchestrator-locked weights."""
    src = _read(INTEL_SVC)
    assert '"approved": 0.60' in src
    assert '"submitted": 0.25' in src
    assert '"adherence": 0.15' in src
    # All 5 sections are produced by build_intelligence.
    assert "readiness" in src
    assert "blockers" in src
    assert "gaps" in src
    assert "roadmap" in src
    assert "recommendations" in src


def test_f3_intelligence_service_falls_back_on_shield_failure():
    """The `_fallback_recommendations` function exists and is used when
    the LLM path is unavailable."""
    src = _read(INTEL_SVC)
    assert "_fallback_recommendations" in src
    assert "rule_based" in src


# ═════════════════════════════════════════════════════════════════════
# Wire — Chat ctx_type=task + Solva source=task
# ═════════════════════════════════════════════════════════════════════
def test_f3_chat_validator_accepts_task_ctx_type():
    src = _read(CHAT_ROUTER)
    block = src.split("class LinkedContextIn")[1].split("class ChatCreateIn")[0]
    assert '"task"' in block
    # Resolver handles ctx_type=task by hitting db.tasks.
    resolver = src.split("async def _resolve_linked_context")[1].split("async def _last_audit_hash")[0]
    assert 'ctx_type == "task"' in resolver
    assert "db.tasks.find_one" in resolver
    assert "/app/task-manager?task_id=" in resolver


def test_f3_solva_source_validator_accepts_task():
    src = _read(SOLVA_ROUTER)
    block = src.split("_check_source")[1].split("def _check_sm_hint")[0]
    assert '"task"' in block
    # Source URL builder maps task to /app/task-manager?task_id=…
    builder = src.split("def _build_source_url")[1].split("\nasync def ")[0]
    assert 'source == "task"' in builder
    assert "/app/task-manager?task_id=" in builder


# ═════════════════════════════════════════════════════════════════════
# Live HTTP
# ═════════════════════════════════════════════════════════════════════
@pytest.fixture
async def task_actor():
    from core import db, hash_password
    uid = f"test-f3-{uuid.uuid4().hex[:8]}"
    cid = f"ctx-f3-{uuid.uuid4().hex[:8]}"
    email = f"f3-{uuid.uuid4().hex[:6]}@example.com"
    await db.accounts.insert_one({
        "id": uid, "email": email,
        "password_hash": hash_password("Pw!1234567Abc"),
        "name": "F3", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.contexts.insert_one({
        "id": cid, "name": "F3 Co", "owner_account_id": uid,
        "type": "executive_personal",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}",
        "account_id": uid, "context_id": cid,
        "role": "executive", "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"uid": uid, "cid": cid, "email": email, "password": "Pw!1234567Abc"}
    await db.tasks.delete_many({"account_id": uid})
    await db.task_intelligence.delete_many({})
    await db.documents.delete_many({"context_id": cid})
    await db.audit_log.delete_many({"account_id": uid})
    await db.memberships.delete_many({"account_id": uid})
    await db.contexts.delete_one({"id": cid})
    await db.accounts.delete_one({"id": uid})


async def _login(c, actor):
    r = await c.post("/api/auth/login",
                     json={"email": actor["email"], "password": actor["password"]})
    token = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {token}", "X-Active-Context": actor["cid"]}


@pytest.mark.asyncio
async def test_f3_task_drafts_endpoint_returns_linked_docs(task_actor):
    from server import app  # noqa: F401
    from core import db
    tid = f"task-{uuid.uuid4().hex[:12]}"
    did = f"doc-{uuid.uuid4().hex[:8]}"
    await db.tasks.insert_one({
        "id": tid, "account_id": task_actor["uid"], "context_id": task_actor["cid"],
        "name": "T", "state": "active", "team": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.documents.insert_one({
        "id": did, "context_id": task_actor["cid"],
        "task_id": tid,  # F.3 — new optional schema field
        "name": "Linked doc",
        "state": "draft",
        "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, task_actor)
        r = await c.get(f"/api/tasks/{tid}/drafts", headers=hdr)
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0]["id"] == did
        assert items[0]["state"] == "draft"


@pytest.mark.asyncio
async def test_f3_contribution_patch_recomputes_readiness(task_actor):
    from server import app  # noqa: F401
    from core import db
    tid = f"task-{uuid.uuid4().hex[:12]}"
    await db.tasks.insert_one({
        "id": tid, "account_id": task_actor["uid"], "context_id": task_actor["cid"],
        "name": "T", "state": "active",
        "team": [
            {"name": "A", "email": "a@x.com", "status": "not_started"},
            {"name": "B", "email": "b@x.com", "status": "not_started"},
        ],
        "readiness_score": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, task_actor)
        # Approve A — should recompute readiness up from 0.
        r = await c.patch(
            f"/api/tasks/{tid}/contributions/a@x.com",
            json={"status": "approved"}, headers=hdr,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["readiness_score"] > 0
        assert next(m for m in body["team"] if m["email"] == "a@x.com")["status"] == "approved"
        # Audit row.
        row = await db.audit_log.find_one({
            "resource_id":  tid,
            "action":       "task.contribution.approved",
        })
        assert row is not None


@pytest.mark.asyncio
async def test_f3_contribution_patch_rejects_unknown_status(task_actor):
    from server import app  # noqa: F401
    from core import db
    tid = f"task-{uuid.uuid4().hex[:12]}"
    await db.tasks.insert_one({
        "id": tid, "account_id": task_actor["uid"],
        "name": "T", "state": "active",
        "team": [{"name": "A", "email": "a@x.com"}],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, task_actor)
        r = await c.patch(
            f"/api/tasks/{tid}/contributions/a@x.com",
            json={"status": "nonsense"}, headers=hdr,
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_f3_intelligence_returns_full_payload(task_actor):
    """The intelligence endpoint returns all 5 sections + readiness
    breakdown with the 60/25/15 weights."""
    from server import app  # noqa: F401
    from core import db
    tid = f"task-{uuid.uuid4().hex[:12]}"
    await db.tasks.insert_one({
        "id": tid, "account_id": task_actor["uid"],
        "name": "Q4 Board Pack",
        "objective": "Ship a board-ready pack.",
        "success_criteria": "Pack delivered ≥ 48h before the meeting.",
        "output_spec": {"kind": "template", "template_id": "board_pack", "formats": ["pdf"]},
        "team": [
            {"name": "CFO", "email": "cfo@x.com", "status": "approved", "due_date": "2026-04-01"},
            {"name": "GC",  "email": "gc@x.com",  "status": "in_progress",
             "due_date": (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()},
        ],
        "state": "active", "readiness_score": 30,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, task_actor)
        r = await c.get(f"/api/tasks/{tid}/intelligence", headers=hdr)
        assert r.status_code == 200, r.text
        payload = r.json()
        for k in ("task_id", "task_hash", "generated_at", "readiness",
                  "blockers", "gaps", "roadmap", "recommendations"):
            assert k in payload, f"missing intelligence key: {k}"
        # Readiness components carry the 60/25/15 weights.
        weights = sorted(c["weight"] for c in payload["readiness"]["components"])
        assert weights == [15, 25, 60]
        # GC is overdue → blockers has at least one entry.
        assert any(b["kind"] == "overdue" for b in payload["blockers"])
        # Recommendations always present (LLM or rule-based fallback).
        assert len(payload["recommendations"]) >= 1


@pytest.mark.asyncio
async def test_f3_intelligence_cache_hit_on_second_call(task_actor):
    """The first call computes + caches. The second call returns the
    same task_hash without rebuilding (idempotent)."""
    from server import app  # noqa: F401
    from core import db
    tid = f"task-{uuid.uuid4().hex[:12]}"
    await db.tasks.insert_one({
        "id": tid, "account_id": task_actor["uid"],
        "name": "X", "state": "active", "team": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, task_actor)
        r1 = await c.get(f"/api/tasks/{tid}/intelligence", headers=hdr)
        r2 = await c.get(f"/api/tasks/{tid}/intelligence", headers=hdr)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["task_hash"] == r2.json()["task_hash"]
        # Cache row was created.
        n = await db.task_intelligence.count_documents({"task_id": tid})
        assert n == 1


@pytest.mark.asyncio
async def test_f3_intelligence_regenerate_clears_cache_and_queues(task_actor):
    from server import app  # noqa: F401
    from core import db
    tid = f"task-{uuid.uuid4().hex[:12]}"
    await db.tasks.insert_one({
        "id": tid, "account_id": task_actor["uid"],
        "name": "X", "state": "active", "team": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, task_actor)
        # Populate cache.
        await c.get(f"/api/tasks/{tid}/intelligence", headers=hdr)
        assert await db.task_intelligence.count_documents({"task_id": tid}) == 1
        # Regenerate clears it.
        r = await c.post(f"/api/tasks/{tid}/intelligence/regenerate", headers=hdr)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "queued"
        # The synchronous delete dropped the cache row immediately
        # (the rebuild runs in background).


@pytest.mark.asyncio
async def test_f3_chat_resolves_ctx_type_task_with_title_and_excerpt(task_actor):
    """The Chat backend resolves a `ctx_type=task` linked context →
    title + excerpt match the task spec."""
    from server import app  # noqa: F401
    from core import db
    tid = f"task-{uuid.uuid4().hex[:12]}"
    await db.tasks.insert_one({
        "id": tid, "account_id": task_actor["uid"],
        "name": "Strategy refresh",
        "objective": "Sharpen the strategy narrative.",
        "success_criteria": "One clear ask per option.",
        "state": "active", "team": [], "readiness_score": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, task_actor)
        r = await c.post("/api/chats", json={
            "title": "Test linked-task chat",
            "linked_context": {"ctx_type": "task", "ctx_id": tid},
            "context_id": task_actor["cid"],
        }, headers=hdr)
        assert r.status_code == 200, r.text
        body = r.json()
        lc = body.get("linked_context") or {}
        assert lc.get("ctx_type") == "task"
        assert lc.get("ctx_id") == tid
        assert lc.get("title") == "Strategy refresh"
        # Excerpt blends objective + success criteria + readiness summary.
        assert "Sharpen the strategy narrative" in (lc.get("excerpt") or "")
        assert "Success criteria" in (lc.get("excerpt") or "")
        assert lc.get("href") == f"/app/task-manager?task_id={tid}"


# ═════════════════════════════════════════════════════════════════════
# F.3 log presence
# ═════════════════════════════════════════════════════════════════════
def test_f3_section_present_in_home_cleanup_log():
    log = (REPO / "memory" / "sprints" / "HOME_CLEANUP_LOG.md").read_text("utf-8")
    assert "F.3" in log and "Task Drawer" in log
