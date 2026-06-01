"""P5.17 — Upstream read-side adapter lockdown.

Coverage:
  • `origin` field on `tasks` serializer — present when set,
    absent (null) otherwise.
  • `?origin=email_akki` narrows the list; `?origin=manual` excludes.
  • Live route_to_task writes the parallel primary `tasks` row with
    origin envelope (no separate backfill needed for fresh routes).
  • Migration idempotency — running `backfill_tasks` twice produces
    zero net writes the second time.
  • Migration honours existing primary row — no duplicate created.
  • Non-admin preview endpoint:
      - 404 on missing message
      - 404 on cross-tenant (existence-leak guard)
      - 200 with sanitized payload when tenant matches
      - source_view_log row written on the 200 path
      - superadmin sees any message
  • Backward compat: tasks without origin still list cleanly.
  • Voice-lint clean on adapter source.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

import server  # noqa: F401
from server import app
from services.inbox_routing import (
    ORIGIN_EMAIL_AKKI,
    backfill_tasks,
    build_origin_envelope,
    is_email_akki_origin,
    classify_message,
    route_to_task,
)
from services.inbox_routing.schema import (
    ClassificationEnvelope,
    InboxRoutingLogEntry,
    TargetHint,
)
from services.inbox_routing.audit_log import write_routing_log


@pytest_asyncio.fixture(scope="module")
async def transport():
    yield ASGITransport(app=app)


async def _csrf_login(client: AsyncClient, email: str, password: str) -> Dict[str, str]:
    r = await client.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await client.post(
        "/api/auth/login", json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    r.raise_for_status()
    body = r.json()
    token = body.get("access_token") or body.get("token")
    assert token
    r = await client.get("/api/csrf")
    return {"Authorization": f"Bearer {token}",
            "X-CSRF-Token": r.json()["csrf_token"]}


async def _ensure_test_account(db, *, email: str, password: str = "P517Test!") -> Dict[str, Any]:
    from core import hash_password
    acct = await db.accounts.find_one({"email": email}, {"_id": 0})
    if not acct:
        acct = {
            "id": "acct-p517-" + uuid.uuid4().hex[:10],
            "email": email,
            "name": "P5.17 test account",
            "password_hash": hash_password(password),
            "declared_role": "user",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.accounts.insert_one(dict(acct))
    return acct


async def _seed_inbox_message(db, *, account_id: str, subject: str = "Task: probe",
                                from_email: str = None) -> Dict[str, Any]:
    """Inserts an admin_inbox_messages row with a classification that
    pins the routing target to `account_id`. `from_email` defaults
    to the account's own email so the live classifier resolves the
    same tenant when re-classifying."""
    # Resolve from_email from the account if not provided so the
    # classifier's sender-tier lookup matches.
    if from_email is None:
        acct_row = await db.accounts.find_one({"id": account_id}, {"_id": 0, "email": 1})
        from_email = (acct_row or {}).get("email") or "viewer@p517.example.com"
    msg_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": msg_id,
        "received_at": now,
        "provider": "postmark",
        "from_email": from_email,
        "from_name": "Probe Sender",
        "to_addresses": ["hello@inbound.akki.syni.ai"],
        "subject": subject,
        "body_snippet": "body snippet here",
        "text_body": "Body content under test. Long enough to clear the classifier length floor.",
        "html_body": "",
        "attachments": [],
        "message_id": f"<{msg_id}@p517.test>",
        "mailbox_hash": "",
        "routing_result": "pending",
        "routing_target": None,
        "status": "new",
        "read_at": None,
        "read_by": None,
        "replied_at": None,
        "dismissed_at": None,
        # The classification pinning is what allows the non-admin
        # preview endpoint to recognise the message as belonging to
        # this tenant.
        "classification": {
            "message_id": msg_id,
            "route_kind": "task_create",
            "confidence": "high",
            "rationale": "P5.17 fixture — observed classification fixed for the test.",
            "target_hint": {"account_id": account_id, "task_title": subject},
            "citations": [{"message_id": msg_id, "excerpt": "Body content", "field": "body"}],
            "model_id": "deterministic-v1",
            "classifier_version": "p5.16.0",
            "classified_at": now,
            "schema_version": "inbox.classification.1.0",
        },
    }
    await db.admin_inbox_messages.insert_one(dict(doc))
    return doc


# ─── Adapter pure helpers ────────────────────────────────────────


def test_build_origin_envelope_shape():
    env = build_origin_envelope(
        message_id="msg-abc", confidence_band="high", decision_source="auto",
    )
    assert env["source"] == "email_akki"
    assert env["message_id"] == "msg-abc"
    assert env["confidence_band"] == "high"
    assert env["decision_source"] == "auto"
    assert env["routed_at"]


def test_is_email_akki_origin_helper():
    assert is_email_akki_origin(None) is False
    assert is_email_akki_origin({}) is False
    assert is_email_akki_origin({"source": "manual"}) is False
    assert is_email_akki_origin({"source": "email_akki", "message_id": "m"}) is True


# ─── Live route_to_task writes the parallel primary row ──────────


@pytest.mark.asyncio
async def test_route_to_task_persists_origin_in_primary_collection():
    """P5.16 route_to_task now ALSO writes a `tasks` row carrying
    the origin envelope. Live route + read against `tasks` proves
    the integration end-to-end."""
    from core import db
    acct = await _ensure_test_account(db, email=f"route-{uuid.uuid4().hex[:6]}@p517.example.com")
    msg = await _seed_inbox_message(db, account_id=acct["id"])
    env = await classify_message(msg)
    await route_to_task(message=msg, envelope=env)
    primary = await db.tasks.find_one(
        {"account_id": acct["id"], "origin.message_id": msg["id"]},
        {"_id": 0},
    )
    assert primary is not None, "route_to_task must write a primary tasks row"
    assert primary["origin"]["source"] == "email_akki"
    assert primary["state"] == "draft"


# ─── Migration idempotency + backfill ────────────────────────────


@pytest.mark.asyncio
async def test_backfill_creates_primary_row_when_only_sibling_exists():
    """Seed: sibling-only state (inbox_routing_tasks + log row, no
    primary tasks row). Backfill MUST create exactly one primary
    row tagged with the right origin envelope."""
    from core import db
    acct = await _ensure_test_account(db, email=f"backfill-{uuid.uuid4().hex[:6]}@p517.example.com")
    msg = await _seed_inbox_message(db, account_id=acct["id"], subject="Task: backfill probe")
    # Sibling row only — skip the live route_to_task helper so we
    # can simulate "P5.16-only state".
    sibling_id = "tsk-" + uuid.uuid4().hex[:12]
    await db.inbox_routing_tasks.insert_one({
        "id": sibling_id,
        "account_id": acct["id"],
        "source": "inbox_routing",
        "source_message_id": msg["id"],
        "title": "Task: backfill probe",
        "body_snippet": "snippet",
        "due_hint": None,
        "from_email": msg["from_email"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "draft",
    })
    await write_routing_log(InboxRoutingLogEntry(
        message_id=msg["id"], account_id=acct["id"],
        route_kind="task_create", confidence="medium",
        target_kind="task", target_id=sibling_id,
        rationale="Sibling-only probe row for backfill.",
        decision_source="auto",
    ))
    # First backfill — creates.
    first = await backfill_tasks(db)
    assert first["scanned"] >= 1
    primary = await db.tasks.find_one(
        {"account_id": acct["id"], "origin.message_id": msg["id"]},
        {"_id": 0, "origin": 1, "state": 1},
    )
    assert primary is not None
    assert primary["origin"]["source"] == "email_akki"
    assert primary["origin"]["confidence_band"] == "medium"


@pytest.mark.asyncio
async def test_backfill_is_idempotent_on_double_run():
    """Second backfill run must produce ZERO net writes."""
    from core import db
    # Run backfill twice in succession against the current db state.
    first = await backfill_tasks(db)
    pre_count = await db.tasks.count_documents({"origin.source": "email_akki"})
    second = await backfill_tasks(db)
    post_count = await db.tasks.count_documents({"origin.source": "email_akki"})
    # negative-leak: post_count must NOT exceed pre_count after a
    # supposedly idempotent re-run.
    assert post_count == pre_count, (
        f"Second backfill leaked writes: pre={pre_count} post={post_count}"
    )
    # Counter shape sanity — second run reports `exists` >= `created`
    # since every primary row exists by now.
    assert second["created"] == 0, second
    assert second["exists"] >= first.get("created", 0)


# ─── Listing endpoint: origin field + filter ─────────────────────


@pytest.mark.asyncio
async def test_tasks_list_includes_origin_field_when_present(transport):
    from core import db
    # Use admin's account — admin is allowed to call /api/tasks.
    admin = await db.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0})
    assert admin
    # Insert a tagged task row.
    msg_id = uuid.uuid4().hex
    env = build_origin_envelope(message_id=msg_id, confidence_band="high")
    task_id = "tsk-" + uuid.uuid4().hex[:12]
    await db.tasks.insert_one({
        "id": task_id, "account_id": admin["id"], "context_id": None,
        "name": "P5.17 listing probe", "state": "draft",
        "team": [], "objective": "", "success_criteria": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status_history": [], "origin": env, "readiness_score": 0,
    })
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client.get("/api/tasks?state=draft", headers=headers)
        assert r.status_code == 200, r.text
        tasks = r.json()
        # Find our seeded task.
        seeded = next((t for t in tasks if t["id"] == task_id), None)
        assert seeded is not None, "seeded task must be visible in listing"
        assert seeded["origin"]["source"] == "email_akki"
        assert seeded["origin"]["message_id"] == msg_id


@pytest.mark.asyncio
async def test_tasks_list_origin_filter_narrows_to_email_akki(transport):
    from core import db
    admin = await db.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0})
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client.get("/api/tasks?origin=email_akki", headers=headers)
        assert r.status_code == 200, r.text
        tasks = r.json()
        # Every returned row must carry the email_akki origin.
        for t in tasks:
            assert t.get("origin", {}).get("source") == "email_akki", t.get("id")


@pytest.mark.asyncio
async def test_tasks_list_origin_manual_excludes_email_akki(transport):
    from core import db
    admin = await db.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0})
    # Insert a non-origin task so the manual filter has something to return.
    manual_id = "tsk-" + uuid.uuid4().hex[:12]
    await db.tasks.insert_one({
        "id": manual_id, "account_id": admin["id"], "context_id": None,
        "name": "P5.17 manual task", "state": "draft",
        "team": [], "objective": "", "success_criteria": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status_history": [], "readiness_score": 0,
        # NO origin field — represents a manually-created task.
    })
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client.get("/api/tasks?origin=manual", headers=headers)
        assert r.status_code == 200, r.text
        tasks = r.json()
        # No task in the result may carry an email_akki origin.
        for t in tasks:
            assert (t.get("origin") or {}).get("source") != "email_akki", t


# ─── Backward compat: no origin on old rows still serializes cleanly ──


@pytest.mark.asyncio
async def test_tasks_without_origin_render_origin_null(transport):
    from core import db
    admin = await db.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0})
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client.get("/api/tasks", headers=headers)
        assert r.status_code == 200, r.text
        for t in r.json():
            # Every task must have the `origin` key in the serializer
            # (None for backward-compat rows; dict for email_akki rows).
            assert "origin" in t, t.get("id")


# ─── Preview endpoint: tenant scope + 404 / 200 + source_view_log ──


@pytest.mark.asyncio
async def test_preview_endpoint_404_on_missing_message(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "viewer@akki.ai", "Viewer2026!")
        r = await client.get(
            f"/api/inbox/messages/msg-fake-{uuid.uuid4().hex}/preview",
            headers=headers,
        )
        assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_preview_endpoint_404_on_cross_tenant():
    """Tenant A owns the message classification; tenant B receives 404."""
    from core import db
    acct_a = await _ensure_test_account(db, email=f"tenant-a-{uuid.uuid4().hex[:6]}@p517.example.com")
    acct_b = await _ensure_test_account(db, email=f"tenant-b-{uuid.uuid4().hex[:6]}@p517.example.com",
                                         password="P517Test!")
    msg = await _seed_inbox_message(db, account_id=acct_a["id"])
    transport_ = ASGITransport(app=app)
    async with AsyncClient(transport=transport_, base_url="http://test") as client:
        headers = await _csrf_login(client, acct_b["email"], "P517Test!")
        r = await client.get(
            f"/api/inbox/messages/{msg['id']}/preview", headers=headers,
        )
        # negative-leak: cross-tenant access MUST 404 (never 403 or 200).
        assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_preview_endpoint_200_when_tenant_matches_writes_audit_row(transport):
    from core import db
    acct = await _ensure_test_account(
        db, email=f"tenant-own-{uuid.uuid4().hex[:6]}@p517.example.com", password="P517Test!",
    )
    msg = await _seed_inbox_message(db, account_id=acct["id"])
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, acct["email"], "P517Test!")
        r = await client.get(
            f"/api/inbox/messages/{msg['id']}/preview", headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()["item"]
        assert body["id"] == msg["id"]
        assert body["from_email"] == msg["from_email"]
        assert body["classification"]["route_kind"] == "task_create"
    # source_view_log row written.
    log_row = await db.source_view_log.find_one(
        {"message_id": msg["id"], "account_id": acct["id"]},
        {"_id": 0, "surface": 1},
    )
    assert log_row is not None
    assert log_row["surface"] == "inbox.message_preview"


@pytest.mark.asyncio
async def test_preview_endpoint_superadmin_sees_any_message(transport):
    """Admin@akki.ai is superadmin → bypasses tenant gate."""
    from core import db
    other = await _ensure_test_account(
        db, email=f"someone-else-{uuid.uuid4().hex[:6]}@p517.example.com",
    )
    msg = await _seed_inbox_message(db, account_id=other["id"])
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client.get(
            f"/api/inbox/messages/{msg['id']}/preview", headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()["item"]
        assert body["id"] == msg["id"]


# ─── Voice-lint + source-strict ──────────────────────────────────


def test_origin_chip_module_voice_lint_clean():
    src = Path("/app/frontend/src/components/origin/OriginChip.jsx").read_text(encoding="utf-8")
    banned = ["seamless", "AI-powered", "transform", "harness", "leverage"]
    for bad in banned:
        assert re.search(re.escape(bad), src, re.IGNORECASE) is None, bad


def test_source_message_modal_voice_lint_clean():
    src = Path("/app/frontend/src/components/origin/SourceMessageModal.jsx").read_text(encoding="utf-8")
    banned = ["seamless", "AI-powered", "transform", "harness", "leverage"]
    for bad in banned:
        assert re.search(re.escape(bad), src, re.IGNORECASE) is None, bad


def test_preview_endpoint_registered_in_server():
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert "inbox_message_preview_router" in src
    assert "P5.17" in src
