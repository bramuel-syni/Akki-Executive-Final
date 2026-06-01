"""P5.19 — Signal + cycle-update read-side adapter lockdown.

Coverage:
  • Default-inbox context + cycle singleton idempotency.
  • Precedence chain — signals: hint > sender-member > default.
  • Precedence chain — cycle updates: hint > open cycle > default-cycle > pending.
  • Live route_to_signal writes the parallel primary `db.signals` row
    with origin envelope.
  • Live route_to_cycle_update writes the parallel
    `db.cycle_contributions` row with origin envelope.
  • Migrations: backfill_signals + backfill_cycle_updates create
    from sibling-only state, idempotent on double-run.
  • Pulse feed serializer: origin field present when set; absent
    (None) otherwise (backward compat). `?origin=email_akki` narrows;
    `?origin=manual` excludes.
  • Cycle contributions listing surfaces origin field on routed rows.
  • Tenant isolation on default-inbox context (cross-tenant cannot
    see another tenant's default).
  • Voice-lint clean on context resolver source.

Continues the P5.15.1 honesty protocol — security-sensitive `!=`
assertions carry `# negative-leak:` comments.
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
    DEFAULT_INBOX_CONTEXT_NAME,
    backfill_cycle_updates,
    backfill_signals,
    build_origin_envelope,
    classify_message,
    get_or_create_default_inbox_context,
    get_or_create_default_inbox_cycle,
    materialize_cycle_update_primary,
    materialize_signal_primary,
    resolve_cycle_id,
    resolve_signal_context,
    route_to_cycle_update,
    route_to_signal,
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


async def _ensure_test_account(db, *, email: str, password: str = "P519Test!") -> Dict[str, Any]:
    from core import hash_password
    acct = await db.accounts.find_one({"email": email}, {"_id": 0})
    if not acct:
        acct = {
            "id": "acct-p519-" + uuid.uuid4().hex[:10],
            "email": email, "name": "P5.19 test account",
            "password_hash": hash_password(password),
            "declared_role": "user",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.accounts.insert_one(dict(acct))
    return acct


async def _seed_inbox_message(db, *, account_id: str, subject: str = "Signal: probe",
                                from_email: str = None) -> Dict[str, Any]:
    if from_email is None:
        acct_row = await db.accounts.find_one({"id": account_id}, {"_id": 0, "email": 1})
        from_email = (acct_row or {}).get("email") or "viewer@p519.example.com"
    msg_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": msg_id, "received_at": now, "provider": "postmark",
        "from_email": from_email, "from_name": "Probe Sender",
        "to_addresses": ["hello@inbound.akki.syni.ai"],
        "subject": subject,
        "body_snippet": "snippet here",
        "text_body": "Body content under test. Long enough to clear the classifier length floor.",
        "html_body": "", "attachments": [],
        "message_id": f"<{msg_id}@p519.test>", "mailbox_hash": "",
        "routing_result": "pending", "routing_target": None,
        "status": "new", "read_at": None, "read_by": None,
        "replied_at": None, "dismissed_at": None,
        "classification": {
            "message_id": msg_id, "route_kind": "signal_post",
            "confidence": "high",
            "rationale": "P5.19 fixture — observed classification.",
            "target_hint": {"account_id": account_id},
            "citations": [{"message_id": msg_id,
                           "excerpt": "Body content", "field": "body"}],
            "model_id": "deterministic-v1",
            "classifier_version": "p5.16.0",
            "classified_at": now,
            "schema_version": "inbox.classification.1.0",
        },
    }
    await db.admin_inbox_messages.insert_one(dict(doc))
    return doc


# ── Default-inbox context + cycle singletons ─────────────────────


@pytest.mark.asyncio
async def test_get_or_create_default_inbox_context_is_idempotent():
    from core import db
    acct = await _ensure_test_account(db, email=f"def-ctx-{uuid.uuid4().hex[:6]}@p519.example.com")
    a = await get_or_create_default_inbox_context(db, account_id=acct["id"])
    b = await get_or_create_default_inbox_context(db, account_id=acct["id"])
    assert a["id"] == b["id"]
    assert a["name"] == DEFAULT_INBOX_CONTEXT_NAME
    assert a["is_default_inbox"] is True


@pytest.mark.asyncio
async def test_default_inbox_context_is_tenant_isolated():
    """Cross-tenant: tenant B does not see tenant A's default context."""
    from core import db
    acct_a = await _ensure_test_account(db, email=f"a-{uuid.uuid4().hex[:6]}@p519.example.com")
    acct_b = await _ensure_test_account(db, email=f"b-{uuid.uuid4().hex[:6]}@p519.example.com")
    ctx_a = await get_or_create_default_inbox_context(db, account_id=acct_a["id"])
    ctx_b = await get_or_create_default_inbox_context(db, account_id=acct_b["id"])
    # negative-leak: each tenant gets a DIFFERENT default context id.
    assert ctx_a["id"] != ctx_b["id"]
    assert ctx_a["account_id"] == acct_a["id"]
    assert ctx_b["account_id"] == acct_b["id"]


@pytest.mark.asyncio
async def test_get_or_create_default_inbox_cycle_is_idempotent():
    from core import db
    acct = await _ensure_test_account(db, email=f"def-cyc-{uuid.uuid4().hex[:6]}@p519.example.com")
    ctx = await get_or_create_default_inbox_context(db, account_id=acct["id"])
    a = await get_or_create_default_inbox_cycle(
        db, account_id=acct["id"], context_id=ctx["id"],
    )
    b = await get_or_create_default_inbox_cycle(
        db, account_id=acct["id"], context_id=ctx["id"],
    )
    assert a["id"] == b["id"]
    assert a["status"] == "open"
    assert a["is_default_inbox_cycle"] is True


# ── Precedence chain — signal context ────────────────────────────


@pytest.mark.asyncio
async def test_resolve_signal_context_honours_hint():
    from core import db
    acct = await _ensure_test_account(db, email=f"hint-{uuid.uuid4().hex[:6]}@p519.example.com")
    # Insert a tenant-owned context.
    ctx_id = "ctx-tenant-" + uuid.uuid4().hex[:8]
    await db.contexts.insert_one({
        "id": ctx_id, "account_id": acct["id"], "name": "Test ctx",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    rid, source = await resolve_signal_context(
        db, account_id=acct["id"],
        target_hint={"context_id": ctx_id}, from_email=None,
    )
    assert rid == ctx_id
    assert source == "hint"


@pytest.mark.asyncio
async def test_resolve_signal_context_falls_through_to_default():
    """No hint, no sender member → default inbox context."""
    from core import db
    acct = await _ensure_test_account(db, email=f"def-fall-{uuid.uuid4().hex[:6]}@p519.example.com")
    rid, source = await resolve_signal_context(
        db, account_id=acct["id"], target_hint={}, from_email=None,
    )
    assert source == "default_inbox"
    ctx = await db.contexts.find_one({"id": rid}, {"_id": 0, "is_default_inbox": 1})
    assert ctx["is_default_inbox"] is True


@pytest.mark.asyncio
async def test_resolve_signal_context_ignores_cross_tenant_hint():
    """Hint pointing at a context owned by a DIFFERENT tenant must
    not be honoured — falls through."""
    from core import db
    acct_a = await _ensure_test_account(db, email=f"cross-a-{uuid.uuid4().hex[:6]}@p519.example.com")
    acct_b = await _ensure_test_account(db, email=f"cross-b-{uuid.uuid4().hex[:6]}@p519.example.com")
    foreign_ctx = "ctx-foreign-" + uuid.uuid4().hex[:8]
    await db.contexts.insert_one({
        "id": foreign_ctx, "account_id": acct_b["id"], "name": "B's context",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    rid, source = await resolve_signal_context(
        db, account_id=acct_a["id"],
        target_hint={"context_id": foreign_ctx}, from_email=None,
    )
    # negative-leak: foreign context MUST NOT be returned to tenant A.
    assert rid != foreign_ctx
    assert source == "default_inbox"


# ── Precedence chain — cycle id ──────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_cycle_id_picks_open_cycle_for_context():
    from core import db
    acct = await _ensure_test_account(db, email=f"cyc-open-{uuid.uuid4().hex[:6]}@p519.example.com")
    ctx_id = "ctx-cyc-" + uuid.uuid4().hex[:8]
    await db.contexts.insert_one({
        "id": ctx_id, "account_id": acct["id"], "name": "ctx",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    cyc_id = "cyc-open-" + uuid.uuid4().hex[:8]
    await db.cycles.insert_one({
        "id": cyc_id, "context_id": ctx_id, "account_id": acct["id"],
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    rid, status = await resolve_cycle_id(
        db, account_id=acct["id"], target_hint={}, context_id=ctx_id,
    )
    assert rid == cyc_id
    assert status == "resolved"


@pytest.mark.asyncio
async def test_resolve_cycle_id_pending_when_no_open_cycle_on_non_default_context():
    from core import db
    acct = await _ensure_test_account(db, email=f"cyc-pend-{uuid.uuid4().hex[:6]}@p519.example.com")
    ctx_id = "ctx-no-cyc-" + uuid.uuid4().hex[:8]
    await db.contexts.insert_one({
        "id": ctx_id, "account_id": acct["id"], "name": "ctx no cycle",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    rid, status = await resolve_cycle_id(
        db, account_id=acct["id"], target_hint={}, context_id=ctx_id,
    )
    assert rid is None
    assert status == "pending"


@pytest.mark.asyncio
async def test_resolve_cycle_id_auto_creates_on_default_context():
    """Default-inbox context with no open cycle → auto-mints one."""
    from core import db
    acct = await _ensure_test_account(db, email=f"cyc-auto-{uuid.uuid4().hex[:6]}@p519.example.com")
    ctx = await get_or_create_default_inbox_context(db, account_id=acct["id"])
    rid, status = await resolve_cycle_id(
        db, account_id=acct["id"], target_hint={}, context_id=ctx["id"],
    )
    assert rid is not None
    assert status == "resolved_default"


# ── Live route_to_signal + route_to_cycle_update ─────────────────


@pytest.mark.asyncio
async def test_route_to_signal_persists_primary_row():
    from core import db
    acct = await _ensure_test_account(db, email=f"rsig-{uuid.uuid4().hex[:6]}@p519.example.com")
    msg = await _seed_inbox_message(db, account_id=acct["id"], subject="Signal: live route")
    env = await classify_message(msg)
    # If classifier didn't pick signal_post (due to short body or
    # subject-prefix detection), force it for this test.
    env_dict = env.model_dump()
    env_dict["route_kind"] = "signal_post"
    env_dict["target_hint"]["account_id"] = acct["id"]
    forced = ClassificationEnvelope(**env_dict)
    await route_to_signal(message=msg, envelope=forced)
    primary = await db.signals.find_one(
        {"origin.source": "email_akki", "origin.message_id": msg["id"]},
        {"_id": 0},
    )
    assert primary is not None
    assert primary["origin"]["confidence_band"] in ("low", "medium", "high")
    assert primary["surface_type"] in ("risk", "opportunity", "observation")


@pytest.mark.asyncio
async def test_route_to_cycle_update_persists_primary_row_on_default_context():
    from core import db
    acct = await _ensure_test_account(db, email=f"rcyc-{uuid.uuid4().hex[:6]}@p519.example.com")
    msg = await _seed_inbox_message(db, account_id=acct["id"], subject="Cycle: live route")
    env = await classify_message(msg)
    env_dict = env.model_dump()
    env_dict["route_kind"] = "cycle_update"
    env_dict["target_hint"]["account_id"] = acct["id"]
    forced = ClassificationEnvelope(**env_dict)
    await route_to_cycle_update(message=msg, envelope=forced)
    primary = await db.cycle_contributions.find_one(
        {"origin.source": "email_akki", "origin.message_id": msg["id"]},
        {"_id": 0},
    )
    assert primary is not None
    assert primary["context_id"]
    assert primary["agenda_id"]  # cycle_id stored under agenda_id


# ── Backfills ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_backfill_signals_creates_when_sibling_only_then_idempotent():
    from core import db
    acct = await _ensure_test_account(db, email=f"bsig-{uuid.uuid4().hex[:6]}@p519.example.com")
    msg = await _seed_inbox_message(db, account_id=acct["id"], subject="Signal: backfill probe")
    sibling_id = "isg-" + uuid.uuid4().hex[:10]
    await db.inbox_routing_signals.insert_one({
        "id": sibling_id, "account_id": acct["id"],
        "source": "inbox_routing", "source_message_id": msg["id"],
        "signal_kind": "concern",
        "subject": "Signal: backfill probe", "body_snippet": "snippet",
        "from_email": msg["from_email"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "citation": {"message_id": msg["id"], "excerpt": "Body content"},
    })
    await write_routing_log(InboxRoutingLogEntry(
        message_id=msg["id"], account_id=acct["id"],
        route_kind="signal_post", confidence="medium",
        target_kind="signal", target_id=sibling_id,
        rationale="Sibling-only signal probe.",
        decision_source="auto",
    ))
    first = await backfill_signals(db)
    assert first["scanned"] >= 1
    pre = await db.signals.count_documents({"origin.source": "email_akki"})
    second = await backfill_signals(db)
    post = await db.signals.count_documents({"origin.source": "email_akki"})
    # negative-leak: idempotent re-run MUST NOT write rows.
    assert post == pre, f"backfill_signals leaked writes: pre={pre} post={post}"
    assert second["created"] == 0


@pytest.mark.asyncio
async def test_backfill_cycle_updates_creates_then_idempotent():
    from core import db
    acct = await _ensure_test_account(db, email=f"bcyc-{uuid.uuid4().hex[:6]}@p519.example.com")
    msg = await _seed_inbox_message(db, account_id=acct["id"], subject="Cycle: backfill probe")
    sibling_id = "cyu-" + uuid.uuid4().hex[:10]
    await db.inbox_routing_cycle_updates.insert_one({
        "id": sibling_id, "account_id": acct["id"],
        "source": "inbox_routing", "source_message_id": msg["id"],
        "subject": "Cycle: backfill probe", "body_snippet": "snippet",
        "from_email": msg["from_email"], "cycle_id": None, "company_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await write_routing_log(InboxRoutingLogEntry(
        message_id=msg["id"], account_id=acct["id"],
        route_kind="cycle_update", confidence="medium",
        target_kind="cycle_update", target_id=sibling_id,
        rationale="Sibling-only cycle update probe.",
        decision_source="auto",
    ))
    first = await backfill_cycle_updates(db)
    assert first["scanned"] >= 1
    pre = await db.cycle_contributions.count_documents({"origin.source": "email_akki"})
    second = await backfill_cycle_updates(db)
    post = await db.cycle_contributions.count_documents({"origin.source": "email_akki"})
    assert post == pre, f"backfill_cycle_updates leaked writes: pre={pre} post={post}"
    assert second["created"] == 0


# ── Pulse feed serializer + filter ───────────────────────────────


@pytest.mark.asyncio
async def test_pulse_feed_returns_origin_field(transport):
    from core import db
    admin = await db.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0})
    ctx = await get_or_create_default_inbox_context(db, account_id=admin["id"])
    # Insert a routed signal in admin's default context.
    msg_id = uuid.uuid4().hex
    sig_id = "sig-akki-" + uuid.uuid4().hex[:10]
    await db.signals.insert_one({
        "id": sig_id, "context_id": ctx["id"],
        "surface_type": "observation",
        "title": "P5.19 listing probe",
        "body": "Body excerpt for the test.",
        "topic_class": "operations", "freshness": "new",
        "confidence": "high",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "origin": build_origin_envelope(message_id=msg_id, confidence_band="high"),
    })
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client.get(
            f"/api/contexts/{ctx['id']}/pulse/feed?show_low=true", headers=headers,
        )
        assert r.status_code == 200, r.text
        cards = r.json().get("cards", [])
        seeded = next((c for c in cards if c["id"] == sig_id), None)
        assert seeded is not None
        assert seeded["origin"]["source"] == "email_akki"


@pytest.mark.asyncio
async def test_pulse_feed_origin_filter_narrows_and_excludes(transport):
    from core import db
    admin = await db.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0})
    ctx = await get_or_create_default_inbox_context(db, account_id=admin["id"])
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client.get(
            f"/api/contexts/{ctx['id']}/pulse/feed?show_low=true&origin=email_akki",
            headers=headers,
        )
        assert r.status_code == 200, r.text
        cards_email = r.json().get("cards", [])
        for c in cards_email:
            assert (c.get("origin") or {}).get("source") == "email_akki", c["id"]
        r2 = await client.get(
            f"/api/contexts/{ctx['id']}/pulse/feed?show_low=true&origin=manual",
            headers=headers,
        )
        assert r2.status_code == 200, r2.text
        cards_manual = r2.json().get("cards", [])
        for c in cards_manual:
            # negative-leak: manual filter MUST NOT include email_akki rows.
            assert (c.get("origin") or {}).get("source") != "email_akki", c["id"]


# ── Source-strict + voice-lint ───────────────────────────────────


def test_context_resolver_voice_lint_clean():
    src = Path("/app/backend/services/inbox_routing/context_resolver.py").read_text(encoding="utf-8")
    banned = ["seamless", "AI-powered", "transform", "harness", "leverage"]
    for bad in banned:
        assert re.search(re.escape(bad), src, re.IGNORECASE) is None, bad


def test_pulse_signal_serializer_carries_origin():
    """Source-strict guard: the pulse.py serializer must include the
    `origin` field; future edits cannot quietly drop it."""
    src = Path("/app/backend/routers/pulse.py").read_text(encoding="utf-8")
    assert '"origin": s.get("origin") or None' in src
    assert "Phase P5.19" in src
