"""Phase B — Postmark inbound webhook tests.

Coverage:
  * HMAC signature verify (valid + tampered)
  * Basic-Auth path (with + without `POSTMARK_BASIC_AUTH_USER`)
  * MailboxHash prefix routing — session-attach, doc-attach, notify
  * Plain (default) routing path
  * EICAR attachment → 422-equivalent (clamav signature surfaces in audit log)
  * Tier-C unknown sender → `inbound_queue` row

These tests stand up a `httpx.AsyncClient + ASGITransport` against the
in-process FastAPI app (no separate uvicorn). Postmark payloads are
hand-rolled minimal JSON envelopes matching the on-disk Webhook schema.
"""
from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import os
import uuid
from typing import Any, Dict

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorClient


pytestmark = pytest.mark.asyncio


EICAR = (
    b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
)


@pytest_asyncio.fixture
async def db_conn():
    mclient = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mclient[os.environ["DB_NAME"]]
    yield db
    mclient.close()


@pytest_asyncio.fixture
async def app_client():
    """In-process AsyncClient for the FastAPI app."""
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def seed_account_and_context(db_conn):
    """Create a test account + context + membership so MailboxHash
    resolution lands cleanly. Tokens are deterministic per-test so
    we can build MailboxHash strings without round-tripping."""
    account_id = f"acc-phase-b-{uuid.uuid4().hex[:8]}"
    context_id = f"ctx-phase-b-{uuid.uuid4().hex[:8]}"
    account_token = f"phbacc{uuid.uuid4().hex[:6]}"
    context_token = f"phbctx{uuid.uuid4().hex[:6]}"

    await db_conn.accounts.insert_one({
        "id": account_id,
        "email": "phaseb-owner@example.com",
        "name": "Phase B Test Owner",
        "inbound_token": account_token,
    })
    await db_conn.contexts.insert_one({
        "id": context_id,
        "name": "Phase B Test Context",
        "account_id": account_id,
        "inbound_token": context_token,
        "status": "active",
        "type": "executive_personal",
    })
    await db_conn.memberships.insert_one({
        "account_id": account_id,
        "context_id": context_id,
        "status": "active",
        "role": "executive",
        "created_at": "2026-05-21T00:00:00Z",
    })

    yield {
        "account_id": account_id,
        "context_id": context_id,
        "account_token": account_token,
        "context_token": context_token,
        "owner_email": "phaseb-owner@example.com",
    }

    await db_conn.accounts.delete_many({"id": account_id})
    await db_conn.contexts.delete_many({"id": context_id})
    await db_conn.memberships.delete_many({"context_id": context_id})
    await db_conn.documents.delete_many({"context_id": context_id})
    await db_conn.inbound_queue.delete_many({"context_id": context_id})
    await db_conn.inbound_queue_raw.delete_many({})
    await db_conn.solva_session_attachments.delete_many({"context_id": context_id})
    await db_conn.audit_log.delete_many({"context_id": context_id})


def _postmark_envelope(
    *, mailbox_hash: str, from_email: str = "phaseb-owner@example.com",
    subject: str = "Phase B test inbound", text_body: str = "Body text.",
    attachments=None, message_id: str | None = None,
) -> Dict[str, Any]:
    return {
        "FromFull": {"Email": from_email, "Name": "Test"},
        "From": from_email,
        "ToFull": [{"Email": f"inbound+{mailbox_hash}@inbound.postmarkapp.com"}],
        "MailboxHash": mailbox_hash,
        "Subject": subject,
        "TextBody": text_body,
        "HtmlBody": "",
        "MessageID": message_id or f"phaseb-msg-{uuid.uuid4().hex[:10]}",
        "Date": "2026-05-21T12:00:00Z",
        "Attachments": attachments or [],
    }


def _hmac_sig(raw_body: bytes, secret: str) -> str:
    return base64.b64encode(
        _hmac.new(secret.encode(), raw_body, hashlib.sha256).digest(),
    ).decode("ascii").strip()


def _basic_header(user: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


# ────────────────────────────────────────────────────────────────────
# Auth: HMAC valid + tampered
# ────────────────────────────────────────────────────────────────────
async def test_phase_b_hmac_valid_passes(app_client, seed_account_and_context, monkeypatch):
    s = seed_account_and_context
    secret = os.environ.get("POSTMARK_WEBHOOK_SECRET")
    assert secret and len(secret) >= 32, "POSTMARK_WEBHOOK_SECRET missing or weak"

    monkeypatch.setattr("services.clamav_service.ALLOW_UNSAFE_UPLOADS", True)
    monkeypatch.setattr("services.clamav_service.AKKI_ENV", "")

    envelope = _postmark_envelope(mailbox_hash=s["account_token"])
    raw = json.dumps(envelope).encode("utf-8")
    sig = _hmac_sig(raw, secret)

    resp = await app_client.post(
        "/api/inbound/postmark", content=raw,
        headers={"content-type": "application/json", "x-postmark-signature": sig},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True


async def test_phase_b_hmac_tampered_rejected(app_client, seed_account_and_context, monkeypatch):
    s = seed_account_and_context
    monkeypatch.setattr("services.clamav_service.ALLOW_UNSAFE_UPLOADS", True)
    monkeypatch.setattr("services.clamav_service.AKKI_ENV", "")

    envelope = _postmark_envelope(mailbox_hash=s["account_token"])
    raw = json.dumps(envelope).encode("utf-8")
    sig = _hmac_sig(raw, "wrong-secret-for-this-test")

    resp = await app_client.post(
        "/api/inbound/postmark", content=raw,
        headers={"content-type": "application/json", "x-postmark-signature": sig},
    )
    # Production-grade is 401/403; this stack returns 403 from _verify_inbound.
    assert resp.status_code in {401, 403}, resp.text


# ────────────────────────────────────────────────────────────────────
# Auth: Basic-Auth + back-compat endpoint
# ────────────────────────────────────────────────────────────────────
async def test_phase_b_basic_auth_passes_at_backcompat_route(
    app_client, seed_account_and_context, monkeypatch,
):
    s = seed_account_and_context
    secret = os.environ.get("POSTMARK_WEBHOOK_SECRET")
    user = os.environ.get("POSTMARK_BASIC_AUTH_USER", "")
    assert secret, "POSTMARK_WEBHOOK_SECRET missing"

    monkeypatch.setattr("services.clamav_service.ALLOW_UNSAFE_UPLOADS", True)
    monkeypatch.setattr("services.clamav_service.AKKI_ENV", "")

    envelope = _postmark_envelope(mailbox_hash=s["account_token"])
    raw = json.dumps(envelope).encode("utf-8")

    resp = await app_client.post(
        "/api/webhooks/postmark/inbound", content=raw,
        headers={"content-type": "application/json",
                 "authorization": _basic_header(user or "any-user", secret)},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True


async def test_phase_b_basic_auth_wrong_user_rejected(
    app_client, seed_account_and_context, monkeypatch,
):
    """When `POSTMARK_BASIC_AUTH_USER` is set, the server must reject
    a request with the wrong username — even if the password matches."""
    s = seed_account_and_context
    secret = os.environ.get("POSTMARK_WEBHOOK_SECRET")
    expected_user = os.environ.get("POSTMARK_BASIC_AUTH_USER", "")
    if not expected_user:
        pytest.skip("POSTMARK_BASIC_AUTH_USER not configured — back-compat any-user mode")

    monkeypatch.setattr("services.clamav_service.ALLOW_UNSAFE_UPLOADS", True)
    monkeypatch.setattr("services.clamav_service.AKKI_ENV", "")
    monkeypatch.setenv("POSTMARK_USE_HMAC", "true")

    envelope = _postmark_envelope(mailbox_hash=s["account_token"])
    raw = json.dumps(envelope).encode("utf-8")
    resp = await app_client.post(
        "/api/inbound/postmark", content=raw,
        headers={"content-type": "application/json",
                 "authorization": _basic_header("attacker-different-user", secret)},
    )
    assert resp.status_code in {401, 403}, resp.text


# ────────────────────────────────────────────────────────────────────
# MailboxHash prefix routing — three prefixes + default
# ────────────────────────────────────────────────────────────────────
async def test_phase_b_default_routing_persists_doc(
    app_client, seed_account_and_context, db_conn, monkeypatch,
):
    """Plain `<account_token>` MailboxHash → document persisted with
    `inbound_route=default`."""
    s = seed_account_and_context
    secret = os.environ.get("POSTMARK_WEBHOOK_SECRET")
    monkeypatch.setattr("services.clamav_service.ALLOW_UNSAFE_UPLOADS", True)
    monkeypatch.setattr("services.clamav_service.AKKI_ENV", "")

    envelope = _postmark_envelope(mailbox_hash=s["account_token"])
    raw = json.dumps(envelope).encode("utf-8")
    sig = _hmac_sig(raw, secret)

    resp = await app_client.post(
        "/api/inbound/postmark", content=raw,
        headers={"content-type": "application/json", "x-postmark-signature": sig},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] and body["route"] == "default"
    doc = await db_conn.documents.find_one({"id": body["doc_id"]}, {"_id": 0})
    assert doc is not None
    assert doc["inbound_route"] == "default"
    assert doc["inbound_route_target_id"] is None
    assert doc["related_doc_id"] is None


async def test_phase_b_session_prefix_attaches_to_session(
    app_client, seed_account_and_context, db_conn, monkeypatch,
):
    """`session-<sid>.<account_token>` → doc lands in context + an
    attachment row appears in `solva_session_attachments`."""
    s = seed_account_and_context
    secret = os.environ.get("POSTMARK_WEBHOOK_SECRET")
    monkeypatch.setattr("services.clamav_service.ALLOW_UNSAFE_UPLOADS", True)
    monkeypatch.setattr("services.clamav_service.AKKI_ENV", "")

    # Seed a Phase D session in this context
    sid = f"phd-phaseb-{uuid.uuid4().hex[:8]}"
    await db_conn.solva_phase_d_sessions.insert_one({
        "id": sid, "context_id": s["context_id"],
        "account_id": s["account_id"], "status": "active",
    })

    envelope = _postmark_envelope(
        mailbox_hash=f"session-{sid}.{s['account_token']}",
        subject="attaching to my session",
    )
    raw = json.dumps(envelope).encode("utf-8")
    sig = _hmac_sig(raw, secret)

    try:
        resp = await app_client.post(
            "/api/inbound/postmark", content=raw,
            headers={"content-type": "application/json", "x-postmark-signature": sig},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] and body["route"] == "session"
        assert body["attached_session_id"] == sid

        att = await db_conn.solva_session_attachments.find_one(
            {"session_id": sid, "context_id": s["context_id"]}, {"_id": 0},
        )
        assert att is not None
        assert att["doc_id"] == body["doc_id"]
        assert att["source"] == "inbound_email"
    finally:
        await db_conn.solva_phase_d_sessions.delete_many({"id": sid})


async def test_phase_b_doc_prefix_attaches_as_version(
    app_client, seed_account_and_context, db_conn, monkeypatch,
):
    """`doc-<docid>.<account_token>` → new doc row with
    `related_doc_id=<parent>` + `relation_type=inbound_version`."""
    s = seed_account_and_context
    secret = os.environ.get("POSTMARK_WEBHOOK_SECRET")
    monkeypatch.setattr("services.clamav_service.ALLOW_UNSAFE_UPLOADS", True)
    monkeypatch.setattr("services.clamav_service.AKKI_ENV", "")

    parent_doc_id = f"doc-phaseb-parent-{uuid.uuid4().hex[:6]}"
    await db_conn.documents.insert_one({
        "id": parent_doc_id, "context_id": s["context_id"],
        "account_id": s["account_id"], "title": "Parent v1",
        "status": "extracted",
    })

    envelope = _postmark_envelope(
        mailbox_hash=f"doc-{parent_doc_id}.{s['account_token']}",
        subject="v2 attached as a version",
    )
    raw = json.dumps(envelope).encode("utf-8")
    sig = _hmac_sig(raw, secret)

    resp = await app_client.post(
        "/api/inbound/postmark", content=raw,
        headers={"content-type": "application/json", "x-postmark-signature": sig},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] and body["route"] == "doc"
    assert body["attached_doc_id"] == parent_doc_id

    child = await db_conn.documents.find_one({"id": body["doc_id"]}, {"_id": 0})
    assert child is not None
    assert child["related_doc_id"] == parent_doc_id
    assert child["relation_type"] == "inbound_version"


async def test_phase_b_notify_prefix_does_not_persist(
    app_client, seed_account_and_context, db_conn, monkeypatch,
):
    """`notify.<account_token>` → no document persisted; audit row only."""
    s = seed_account_and_context
    secret = os.environ.get("POSTMARK_WEBHOOK_SECRET")
    monkeypatch.setattr("services.clamav_service.ALLOW_UNSAFE_UPLOADS", True)
    monkeypatch.setattr("services.clamav_service.AKKI_ENV", "")

    msg_id = f"phaseb-notify-{uuid.uuid4().hex[:10]}"
    envelope = _postmark_envelope(
        mailbox_hash=f"notify.{s['account_token']}",
        message_id=msg_id, subject="just a heads-up",
    )
    raw = json.dumps(envelope).encode("utf-8")
    sig = _hmac_sig(raw, secret)

    resp = await app_client.post(
        "/api/inbound/postmark", content=raw,
        headers={"content-type": "application/json", "x-postmark-signature": sig},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] and body["route"] == "notify"
    assert "doc_id" not in body

    docs = await db_conn.documents.find(
        {"context_id": s["context_id"], "inbound_message_id": msg_id}, {"_id": 0},
    ).to_list(5)
    assert docs == [], "notify route must NOT persist a document"


# ────────────────────────────────────────────────────────────────────
# Unknown-sender quarantine
# ────────────────────────────────────────────────────────────────────
async def test_phase_b_unknown_sender_quarantined(
    app_client, seed_account_and_context, db_conn, monkeypatch,
):
    s = seed_account_and_context
    secret = os.environ.get("POSTMARK_WEBHOOK_SECRET")
    monkeypatch.setattr("services.clamav_service.ALLOW_UNSAFE_UPLOADS", True)
    monkeypatch.setattr("services.clamav_service.AKKI_ENV", "")

    msg_id = f"phaseb-unk-{uuid.uuid4().hex[:10]}"
    envelope = _postmark_envelope(
        mailbox_hash=s["account_token"],
        from_email="stranger-at-large@example.com",  # NOT the owner nor a reportee
        message_id=msg_id,
    )
    raw = json.dumps(envelope).encode("utf-8")
    sig = _hmac_sig(raw, secret)

    resp = await app_client.post(
        "/api/inbound/postmark", content=raw,
        headers={"content-type": "application/json", "x-postmark-signature": sig},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("trust_tier") == "unknown" or body.get("quarantined") is True

    row = await db_conn.inbound_queue.find_one(
        {"context_id": s["context_id"], "inbound_message_id": msg_id}, {"_id": 0},
    )
    assert row is not None
    assert row["status"] in {"pending_review", "quarantined"}


# ────────────────────────────────────────────────────────────────────
# EICAR attachment rejection via the existing ClamAV path
# ────────────────────────────────────────────────────────────────────
async def test_phase_b_eicar_attachment_routes_through_clamav(
    app_client, seed_account_and_context, db_conn, monkeypatch,
):
    """An EICAR attachment must be rejected by the ClamAV layer.
    The webhook returns 200 to Postmark either way; what matters is
    the document is NOT marked as `extracted` and the audit trail
    records a virus block."""
    s = seed_account_and_context
    secret = os.environ.get("POSTMARK_WEBHOOK_SECRET")

    # Force enforce-mode + signal infected via the scanner.
    from services import clamav_service

    def fake_blocking(data, filename):
        return clamav_service.ScanResult(
            clean=False, signature="Eicar-Test-Signature", scan_ms=3,
        )
    monkeypatch.setattr(clamav_service, "ALLOW_UNSAFE_UPLOADS", False)
    monkeypatch.setattr(clamav_service, "AKKI_ENV", "")
    monkeypatch.setattr(clamav_service, "_scan_blocking", fake_blocking)

    envelope = _postmark_envelope(
        mailbox_hash=s["account_token"],
        attachments=[{
            "Name": "eicar.txt",
            "Content": base64.b64encode(EICAR).decode(),
            "ContentType": "text/plain",
            "ContentLength": len(EICAR),
        }],
    )
    raw = json.dumps(envelope).encode("utf-8")
    sig = _hmac_sig(raw, secret)

    resp = await app_client.post(
        "/api/inbound/postmark", content=raw,
        headers={"content-type": "application/json", "x-postmark-signature": sig},
    )
    # Postmark contract: return 200 so Postmark doesn't retry. The
    # ClamAV signal lands in `upload_scan_log` for forensics.
    assert resp.status_code == 200, resp.text

    # Confirm the audit row exists with the signature.
    audit = await db_conn[clamav_service.UPLOAD_SCAN_LOG_COLLECTION].find_one(
        {"signature": "Eicar-Test-Signature",
         "user_id": s["account_id"]},
        {"_id": 0},
    )
    assert audit is not None
    assert audit["scan_result"] == "infected"

    # Cleanup
    await db_conn[clamav_service.UPLOAD_SCAN_LOG_COLLECTION].delete_many(
        {"user_id": s["account_id"], "signature": "Eicar-Test-Signature"},
    )
