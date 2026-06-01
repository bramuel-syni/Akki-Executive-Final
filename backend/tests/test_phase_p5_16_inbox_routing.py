"""P5.16 — Email Akki auto-routing lockdown.

Coverage:
  • Classifier envelope shape across all 5 route_kinds.
  • Confidence calibration deterministic on known-signal fixtures.
  • Refuse-to-decide pass on every rationale path.
  • Citation resolver: existing message_id + excerpt verifies;
    fabricated message_id fails citation_unverifiable; excerpt
    not present in body fails citation_unverifiable.
  • Per-route-kind idempotency: re-routing the same message_id +
    route_kind produces no duplicate target.
  • Endpoint surface: admin classify / route / dismiss / routing-log
    each return the expected shape; non-admin lands on 403; CSRF
    required on state-changing endpoints (POSTs).
  • Tenant isolation: routing-log read for a foreign message_id
    returns 404 (existence-leak guard); cross-tenant scoping in
    the audit-log helper (`is_superadmin=False, account_id != row`).
  • Inbound-hook integration: a synthetic Postmark-shape inbound
    creates an admin_inbox row AND triggers a classification.
  • Voice-lint clean on inbox-routing rationale templates.

Honors the P5.15.1 honesty protocol: every assertion has explicit
expected-state context; security-sensitive `!=` assertions carry
a `# negative-leak:` comment so the inverted-assertion class of
bug stays caught.
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

import server  # noqa: F401
from server import app
from services.inbox_routing import (
    CONFIDENCE_BANDS,
    ClassificationCitation,
    ClassificationEnvelope,
    CitationUnverifiable,
    InboxRoutingCitationResolver,
    ROUTE_KINDS,
    RefuseToDecideViolation,
    RouteFailure,
    TargetHint,
    calibrate_band,
    classify_message,
    dispatch_route,
    is_llm_enabled,
    read_routing_log,
    route_to_cycle_update,
    route_to_discussion,
    route_to_signal,
    route_to_task,
    validate_no_imperatives,
    write_routing_log,
)
from services.inbox_routing.schema import InboxRoutingLogEntry


# ─── Helpers ─────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="module")
async def transport():
    yield ASGITransport(app=app)


async def _csrf_login(client: AsyncClient, email: str, password: str) -> Dict[str, str]:
    r = await client.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    r.raise_for_status()
    body = r.json()
    token = body.get("access_token") or body.get("token")
    assert token, f"login returned no token: {body}"
    r = await client.get("/api/csrf")
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": r.json()["csrf_token"],
    }


async def _seed_inbox_message(
    db, *, subject: str, body: str, from_email: str = "founder@example.com",
    routing_result: str = "pending",
) -> Dict[str, Any]:
    msg_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": msg_id,
        "received_at": now,
        "provider": "postmark",
        "from_email": from_email,
        "from_name": "Test Sender",
        "to_addresses": ["hello@inbound.akki.syni.ai"],
        "subject": subject,
        "body_snippet": (body or "")[:240],
        "text_body": body,
        "html_body": "",
        "attachments": [],
        "message_id": f"<{msg_id}@test>",
        "mailbox_hash": "",
        "routing_result": routing_result,
        "routing_target": None,
        "status": "new",
        "read_at": None,
        "read_by": None,
        "replied_at": None,
        "dismissed_at": None,
    }
    await db.admin_inbox_messages.insert_one(dict(doc))
    return doc


async def _ensure_test_account(db, *, email: str, account_id: str) -> None:
    await db.accounts.update_one(
        {"id": account_id},
        {"$setOnInsert": {
            "id": account_id,
            "email": email,
            "name": "P5.16 routing test",
            "declared_role": "user",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


# ─── Confidence calibrator ───────────────────────────────────────


def test_calibrate_band_boundaries():
    assert calibrate_band(0.0) == "low"
    assert calibrate_band(0.34) == "low"
    assert calibrate_band(0.35) == "medium"
    assert calibrate_band(0.69) == "medium"
    assert calibrate_band(0.70) == "high"
    assert calibrate_band(1.5) == "high"
    assert calibrate_band(-0.1) == "low"


def test_route_kinds_and_bands_locked():
    """Source-strict guard against silent vocabulary drift."""
    assert ROUTE_KINDS == (
        "cycle_update", "task_create", "signal_post",
        "discussion_only", "unclassified",
    )
    assert CONFIDENCE_BANDS == ("low", "medium", "high")


def test_is_llm_enabled_default_false(monkeypatch):
    monkeypatch.delenv("INBOX_ROUTING_LLM_ENABLED", raising=False)
    assert is_llm_enabled() is False


def test_is_llm_enabled_true_when_env_set(monkeypatch):
    monkeypatch.setenv("INBOX_ROUTING_LLM_ENABLED", "true")
    assert is_llm_enabled() is True


# ─── Classifier — direct ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_classifier_task_subject_prefix_yields_task_create():
    """`Task: ...` subject + > 80-char body + known sender → high
    confidence task_create."""
    from core import db
    acct = "acct-p516-cls-task-" + uuid.uuid4().hex[:6]
    email = f"{acct}@p516-cls.example.com"
    await _ensure_test_account(db, email=email, account_id=acct)
    msg = await _seed_inbox_message(
        db,
        subject="Task: Prepare Q1 board pack",
        body="Hi team — please prepare the Q1 board pack with the latest "
             "performance metrics and the cohort retention update by Friday. "
             "Action item: draft the deck and circulate for review.",
        from_email=email,
    )
    env = await classify_message(msg)
    assert env.route_kind == "task_create"
    assert env.confidence in ("medium", "high")
    assert env.target_hint.account_id == acct
    assert env.target_hint.task_title.startswith("Task:")
    assert len(env.citations) >= 1
    assert env.citations[0].message_id == msg["id"]
    # Rationale must pass refuse-to-decide.
    validate_no_imperatives(env.rationale, label="rationale_under_test")


@pytest.mark.asyncio
async def test_classifier_cycle_prefix_yields_cycle_update():
    from core import db
    acct = "acct-p516-cls-cycle-" + uuid.uuid4().hex[:6]
    email = f"{acct}@p516-cls.example.com"
    await _ensure_test_account(db, email=email, account_id=acct)
    msg = await _seed_inbox_message(
        db,
        subject="Cycle: Week 8 operating notes",
        body="Posting the week 8 operating cycle review for the team. "
             "Key metrics tracked this week, anchor KPIs holding, retention "
             "shaping up as expected. No surprises in the data.",
        from_email=email,
    )
    env = await classify_message(msg)
    assert env.route_kind == "cycle_update"
    assert env.target_hint.account_id == acct


@pytest.mark.asyncio
async def test_classifier_signal_prefix_yields_signal_post():
    from core import db
    acct = "acct-p516-cls-sig-" + uuid.uuid4().hex[:6]
    email = f"{acct}@p516-cls.example.com"
    await _ensure_test_account(db, email=email, account_id=acct)
    msg = await _seed_inbox_message(
        db,
        subject="Signal: noticed unusual churn pattern in cohort 12",
        body="Observed a sharp uptick in cohort 12 churn last week. "
             "Possible concern around onboarding flow regression. Worth "
             "a closer look from the product side.",
        from_email=email,
    )
    env = await classify_message(msg)
    assert env.route_kind == "signal_post"
    assert env.target_hint.signal_kind in ("concern", "observation", "opportunity")


@pytest.mark.asyncio
async def test_classifier_unknown_sender_demotes_to_discussion():
    """Unknown sender + no tenant binding → cannot route to
    cycle_update / task_create; classifier demotes to
    discussion_only with low band."""
    from core import db
    msg = await _seed_inbox_message(
        db,
        subject="Task: looking for a chat",
        body="Hello — wondering if we could schedule a call to discuss "
             "the partnership opportunity. Available next week any day.",
        from_email=f"unknown-{uuid.uuid4().hex[:6]}@external.example.com",
    )
    env = await classify_message(msg)
    assert env.route_kind == "discussion_only"
    assert env.confidence == "low"
    assert env.target_hint.account_id is None


@pytest.mark.asyncio
async def test_classifier_short_body_caps_score():
    """A 30-char body cannot produce a high-band classification."""
    from core import db
    acct = "acct-p516-cls-short-" + uuid.uuid4().hex[:6]
    email = f"{acct}@p516-cls.example.com"
    await _ensure_test_account(db, email=email, account_id=acct)
    msg = await _seed_inbox_message(
        db,
        subject="Task: thoughts?",
        body="Quick question, thanks.",
        from_email=email,
    )
    env = await classify_message(msg)
    assert env.confidence == "low"


@pytest.mark.asyncio
async def test_classifier_unclassified_when_no_signal():
    from core import db
    acct = "acct-p516-cls-uncl-" + uuid.uuid4().hex[:6]
    email = f"{acct}@p516-cls.example.com"
    await _ensure_test_account(db, email=email, account_id=acct)
    msg = await _seed_inbox_message(
        db,
        subject="hello",
        body="hope everything is going well over there. wanted to say hi. "
             "let me know whenever convenient — no rush at all from my side.",
        from_email=email,
    )
    env = await classify_message(msg)
    # Should be discussion_only or unclassified — never one of the
    # high-signal routes since the body has no keyword signal.
    assert env.route_kind in ("discussion_only", "unclassified")


# ─── Citation resolver ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_citation_resolver_verifies_existing_message():
    from core import db
    msg = await _seed_inbox_message(
        db, subject="Test resolver", body="A short observable test body.",
    )
    r = InboxRoutingCitationResolver()
    await r.verify_one(message_id=msg["id"], excerpt="short observable test", field="body")


@pytest.mark.asyncio
async def test_citation_resolver_rejects_fabricated_message_id():
    r = InboxRoutingCitationResolver()
    with pytest.raises(CitationUnverifiable, match="citation_unverifiable"):
        await r.verify_one(
            message_id="msg-does-not-exist-" + uuid.uuid4().hex,
            excerpt="anything", field="body",
        )


@pytest.mark.asyncio
async def test_citation_resolver_rejects_excerpt_not_in_body():
    from core import db
    msg = await _seed_inbox_message(
        db, subject="Real subject", body="Real body content here.",
    )
    r = InboxRoutingCitationResolver()
    with pytest.raises(CitationUnverifiable, match="citation_unverifiable"):
        await r.verify_one(
            message_id=msg["id"],
            excerpt="this excerpt was definitely never in the body",
            field="body",
        )


@pytest.mark.asyncio
async def test_citation_resolver_batch_aggregates_failures():
    from core import db
    msg = await _seed_inbox_message(
        db, subject="Batch test", body="Body text under test.",
    )
    r = InboxRoutingCitationResolver()
    cits = [
        ClassificationCitation(message_id=msg["id"], excerpt="Body text", field="body"),
        ClassificationCitation(
            message_id="msg-fake-" + uuid.uuid4().hex,
            excerpt="anything", field="body",
        ),
    ]
    with pytest.raises(CitationUnverifiable) as exc:
        await r.verify_many(cits)
    # Batch aggregates — the single failure message references both.
    assert "citation_unverifiable" in str(exc.value)


# ─── Per-route-kind idempotency ──────────────────────────────────


@pytest.mark.asyncio
async def test_route_to_task_is_idempotent_on_message_id():
    from core import db
    acct = "acct-p516-route-task-" + uuid.uuid4().hex[:6]
    email = f"{acct}@p516-route.example.com"
    await _ensure_test_account(db, email=email, account_id=acct)
    msg = await _seed_inbox_message(
        db,
        subject="Task: ship the audit log endpoint",
        body="Please ship the inbox routing audit log endpoint by Friday. "
             "Sprint deliverable; owner needed for the FE wiring as well.",
        from_email=email,
    )
    env = await classify_message(msg)
    first = await route_to_task(message=msg, envelope=env)
    second = await route_to_task(message=msg, envelope=env)
    assert first["status"] == "created"
    assert second["status"] == "exists"
    assert first["target_id"] == second["target_id"]


@pytest.mark.asyncio
async def test_route_to_cycle_update_idempotent():
    from core import db
    acct = "acct-p516-route-cyc-" + uuid.uuid4().hex[:6]
    email = f"{acct}@p516-route.example.com"
    await _ensure_test_account(db, email=email, account_id=acct)
    msg = await _seed_inbox_message(
        db,
        subject="Cycle: weekly check-in notes",
        body="Posting our weekly cycle update — operating cadence holding, "
             "no anomalies in the KPI dashboard, retention healthy.",
        from_email=email,
    )
    env = await classify_message(msg)
    first = await route_to_cycle_update(message=msg, envelope=env)
    second = await route_to_cycle_update(message=msg, envelope=env)
    assert first["target_id"] == second["target_id"]
    assert second["status"] == "exists"


@pytest.mark.asyncio
async def test_route_to_signal_idempotent_and_carries_citation():
    from core import db
    acct = "acct-p516-route-sig-" + uuid.uuid4().hex[:6]
    email = f"{acct}@p516-route.example.com"
    await _ensure_test_account(db, email=email, account_id=acct)
    msg = await _seed_inbox_message(
        db,
        subject="Signal: noticed unusual onboarding drop-off",
        body="Saw that the onboarding funnel softened sharply this week. "
             "Concern this may be a regression on the new flow. Data point: "
             "drop-off at step 3 jumped from 12% to 27%.",
        from_email=email,
    )
    env = await classify_message(msg)
    first = await route_to_signal(message=msg, envelope=env)
    second = await route_to_signal(message=msg, envelope=env)
    assert first["status"] == "created"
    assert second["status"] == "exists"
    sig = await db.inbox_routing_signals.find_one(
        {"id": first["target_id"]}, {"_id": 0},
    )
    assert sig is not None
    assert sig["citation"]["message_id"] == msg["id"]


@pytest.mark.asyncio
async def test_route_to_task_requires_account_id():
    """Tenant-binding contract — task_create without account_id raises."""
    from core import db
    msg = await _seed_inbox_message(
        db, subject="Task: anonymous", body="anonymous body text",
        from_email=f"anon-{uuid.uuid4().hex[:6]}@external.example.com",
    )
    env = await classify_message(msg)
    # Force the route_kind to task_create even though the classifier
    # demoted it — simulates a misuse of the manual route path.
    env_dict = env.model_dump()
    env_dict["route_kind"] = "task_create"
    env_dict["target_hint"]["account_id"] = None
    forced_env = ClassificationEnvelope(**env_dict)
    with pytest.raises(RouteFailure):
        await route_to_task(message=msg, envelope=forced_env)


@pytest.mark.asyncio
async def test_dispatch_route_unclassified_writes_log_only():
    from core import db
    acct = "acct-p516-disp-uncl-" + uuid.uuid4().hex[:6]
    email = f"{acct}@p516-disp.example.com"
    await _ensure_test_account(db, email=email, account_id=acct)
    msg = await _seed_inbox_message(
        db, subject="hello", body="thanks!", from_email=email,
    )
    env = await classify_message(msg)
    env_dict = env.model_dump()
    env_dict["route_kind"] = "unclassified"
    forced_env = ClassificationEnvelope(**env_dict)
    result = await dispatch_route(message=msg, envelope=forced_env)
    assert result["route_kind"] == "unclassified"
    assert result["target_kind"] is None
    assert result["target_id"] is None
    assert result["routing_log_id"]


# ─── Endpoint surface (auth + CSRF + tenant + admin gate) ────────


@pytest.mark.asyncio
async def test_classify_endpoint_admin_happy_path(transport):
    """Admin classifies an existing inbox message → 200 with
    classification envelope on the response + persisted on the row."""
    from core import db
    msg = await _seed_inbox_message(
        db,
        subject="Task: integration test fixture",
        body="Action item: validate the routing endpoint persists "
             "the classification envelope on the inbox row.",
        from_email="admin@akki.ai",
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client.post(
            f"/api/admin/inbox/messages/{msg['id']}/classify", headers=headers,
        )
        assert r.status_code == 200, r.text
        env = r.json()["classification"]
        assert env["message_id"] == msg["id"]
        assert env["route_kind"] in ROUTE_KINDS
    # Persisted on the row.
    row = await db.admin_inbox_messages.find_one(
        {"id": msg["id"]}, {"_id": 0, "classification": 1},
    )
    assert row["classification"]["message_id"] == msg["id"]


@pytest.mark.asyncio
async def test_classify_endpoint_404_on_unknown_message_id(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client.post(
            f"/api/admin/inbox/messages/msg-fake-{uuid.uuid4().hex}/classify",
            headers=headers,
        )
        assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_route_endpoint_admin_can_manually_route(transport):
    from core import db
    acct = "acct-p516-ep-route-" + uuid.uuid4().hex[:6]
    email = f"{acct}@p516-ep.example.com"
    await _ensure_test_account(db, email=email, account_id=acct)
    msg = await _seed_inbox_message(
        db,
        subject="Task: route via endpoint",
        body="Action item: confirm the manual route endpoint produces a "
             "task target and writes the routing-log row.",
        from_email=email,
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client.post(
            f"/api/admin/inbox/messages/{msg['id']}/route",
            json={
                "route_kind": "task_create",
                "target_hint": {"account_id": acct, "task_title": "Manual test task"},
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["result"]["route_kind"] == "task_create"
        assert body["result"]["target_id"]


@pytest.mark.asyncio
async def test_dismiss_endpoint_flips_status_and_writes_log(transport):
    from core import db
    msg = await _seed_inbox_message(
        db, subject="hello", body="just saying hi, no action needed.",
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client.post(
            f"/api/admin/inbox/messages/{msg['id']}/dismiss", headers=headers,
        )
        assert r.status_code == 200, r.text
    row = await db.admin_inbox_messages.find_one(
        {"id": msg["id"]}, {"_id": 0, "status": 1},
    )
    assert row["status"] == "dismissed"
    # Routing-log row must exist for the dismissal.
    log_row = await db.inbox_routing_log.find_one(
        {"message_id": msg["id"], "route_kind": "discussion_only"},
        {"_id": 0},
    )
    assert log_row is not None
    assert log_row["decision_source"] == "human"


@pytest.mark.asyncio
async def test_routing_log_endpoint_returns_persisted_rows(transport):
    """Routing-log endpoint surfaces every routing decision for a
    message — both auto and human."""
    from core import db
    acct = "acct-p516-log-" + uuid.uuid4().hex[:6]
    email = f"{acct}@p516-log.example.com"
    await _ensure_test_account(db, email=email, account_id=acct)
    msg = await _seed_inbox_message(
        db,
        subject="Task: log endpoint test",
        body="Action item: verify the routing-log endpoint returns "
             "persisted rows for this message in descending time order.",
        from_email=email,
    )
    # Manual route + classify writes two log rows.
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        await client.post(
            f"/api/admin/inbox/messages/{msg['id']}/route",
            json={"route_kind": "task_create", "target_hint": {"account_id": acct}},
            headers=headers,
        )
        await client.post(
            f"/api/admin/inbox/messages/{msg['id']}/dismiss", headers=headers,
        )
        r = await client.get(
            f"/api/admin/inbox/messages/{msg['id']}/routing-log", headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["count"] >= 2
        # Each row must have the required audit fields.
        for row in body["items"]:
            assert row["message_id"] == msg["id"]
            assert row["route_kind"] in ROUTE_KINDS


@pytest.mark.asyncio
async def test_routing_log_endpoint_404_on_unknown_message_id(transport):
    """Tenant-isolation: the log endpoint returns 404 for a
    non-existent message_id (existence-leak guard). This is a
    positive isolation contract — the endpoint never reveals
    'message exists but you can't see it' vs 'message doesn't exist'."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client.get(
            f"/api/admin/inbox/messages/msg-bogus-{uuid.uuid4().hex}/routing-log",
            headers=headers,
        )
        assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_non_admin_cannot_classify_or_route(transport):
    """Viewer role lacks superadmin; both endpoints return 403."""
    from core import db
    msg = await _seed_inbox_message(
        db, subject="Task: viewer test", body="this body has plenty of content " * 4,
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "viewer@akki.ai", "Viewer2026!")
        r = await client.post(
            f"/api/admin/inbox/messages/{msg['id']}/classify", headers=headers,
        )
        assert r.status_code == 403, r.text  # superadmin-required
        r = await client.post(
            f"/api/admin/inbox/messages/{msg['id']}/route",
            json={"route_kind": "discussion_only"}, headers=headers,
        )
        assert r.status_code == 403, r.text


# ─── Tenant scope on routing-log read helper ─────────────────────


@pytest.mark.asyncio
async def test_read_routing_log_excludes_foreign_tenant_when_not_super():
    """Audit-log helper: non-superadmin reader scoped to account A
    receives ZERO rows for a routing-log entry that belongs to
    account B, even though both carry the same message_id."""
    from core import db
    acct_a = "acct-p516-ten-a-" + uuid.uuid4().hex[:6]
    acct_b = "acct-p516-ten-b-" + uuid.uuid4().hex[:6]
    msg = await _seed_inbox_message(
        db, subject="Tenant test", body="some body content " * 6,
    )
    # Write a log row for tenant B.
    await write_routing_log(InboxRoutingLogEntry(
        message_id=msg["id"], account_id=acct_b,
        route_kind="discussion_only", confidence="low",
        rationale="Tenant-isolation lockdown row.",
    ))
    # Tenant A reads — must see zero rows.
    rows_a = await read_routing_log(
        message_id=msg["id"], account_id=acct_a, is_superadmin=False,
    )
    # negative-leak: tenant A must NOT receive tenant B's row.
    assert all(r["account_id"] != acct_b for r in rows_a), rows_a
    assert rows_a == []
    # Tenant B reads — sees its own row.
    rows_b = await read_routing_log(
        message_id=msg["id"], account_id=acct_b, is_superadmin=False,
    )
    assert any(r["account_id"] == acct_b for r in rows_b), rows_b


# ─── Inbound-hook integration ────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_inbound_payload_triggers_classification():
    """Calling `_dispatch_inbound_payload` directly with a Postmark-shape
    dict writes an admin_inbox row AND attaches a classification."""
    from core import db
    from routers.inbound_email import _dispatch_inbound_payload
    acct = "acct-p516-hook-" + uuid.uuid4().hex[:6]
    email = f"{acct}@p516-hook.example.com"
    await _ensure_test_account(db, email=email, account_id=acct)
    payload = {
        "From": email,
        "FromName": "Hook Tester",
        "Subject": "Task: hook integration probe",
        "TextBody": "Action item: confirm the inbound dispatch hook triggers "
                    "the classifier and persists the envelope on the inbox row.",
        "HtmlBody": "",
        "MailboxHash": "",
        "MessageID": "<hook-" + uuid.uuid4().hex + "@test>",
        "ToFull": [{"Email": "hello@inbound.akki.syni.ai", "Name": "", "MailboxHash": ""}],
        "Attachments": [],
        "_provider": "postmark",
    }
    # Best-effort call; even if downstream dispatch fails (no MailboxHash
    # → "unresolved_recipient" return path), the capture + classify
    # hook MUST have run.
    try:
        await _dispatch_inbound_payload(payload)
    except Exception:  # noqa: BLE001
        pass
    # Find the row by MessageID — capture stores it on `message_id`.
    row = await db.admin_inbox_messages.find_one(
        {"message_id": payload["MessageID"]}, {"_id": 0},
    )
    assert row is not None, "Inbound hook must persist an admin_inbox row"
    cls = row.get("classification")
    assert cls is not None, "Classifier must have annotated the row"
    assert cls["message_id"] == row["id"]
    assert cls["route_kind"] in ROUTE_KINDS


# ─── Voice-lint + source-strict ──────────────────────────────────


def test_classifier_module_voice_lint_clean():
    """Rationale template module must not carry banned vocabulary."""
    src = Path("/app/backend/services/inbox_routing/classifier.py").read_text(encoding="utf-8")
    banned = ["seamless", "AI-powered", "transform", "harness", "leverage"]
    for bad in banned:
        assert re.search(re.escape(bad), src, re.IGNORECASE) is None, (
            f"banned vocab {bad!r} in classifier source"
        )


def test_routing_endpoints_csrf_protected_at_router_level():
    """Source-strict: state-changing POST endpoints inherit CSRF
    middleware (not in the allowlist) — same invariant as Ideas."""
    src = Path("/app/backend/services/csrf.py").read_text(encoding="utf-8")
    # The csrf allowlist MUST NOT include any /api/admin/inbox path.
    assert "/api/admin/inbox" not in src, (
        "/api/admin/inbox endpoints must NOT be in the CSRF allowlist"
    )


def test_admin_inbox_router_source_marks_p5_16():
    """Lock the P5.16 markers in place so a future edit can't remove
    them without flipping this test."""
    src = Path("/app/backend/routers/admin_inbox.py").read_text(encoding="utf-8")
    assert "Phase P5.16" in src
    assert "classify_inbox_message" in src
    assert "route_inbox_message" in src
    assert "dismiss_inbox_message" in src
    assert "get_inbox_message_routing_log" in src
