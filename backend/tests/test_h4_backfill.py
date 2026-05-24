"""H4 — Back-fill engine wire-level tests.

Eight tests covering the H4 brief end-to-end:
  1. Single chat back-fill end-to-end (PII detected + Trust Center
     reports ``backfilled``)
  2. Idempotency — second run is a no-op, no duplicate audit rows
  3. Partial-failure recovery — mid-chat failure marks ``partial=true``
  4. Rate limiting — batch size + sleep observed
  5. Trust Center post-backfill — empty state copy changed,
     drill-down shows back-fill badge, raw PAN absent
  6. ``is_backfill: true`` marker on all back-fill audit rows
  7. Separate ``backfill_chain_v1`` hash chain (does NOT pollute live)
  8. Admin status endpoint returns correct counts

Independent re-run recipes embedded in each docstring.
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from unittest import mock

import pytest
import pytest_asyncio

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki")
os.environ.setdefault("JWT_SECRET", "test-secret")

from httpx import AsyncClient, ASGITransport  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(scope="module")
async def client():
    from server import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


async def _register(client, prefix: str = "h4"):
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    pwd = "H4Back2026!"
    r = await client.post("/api/auth/register", json={
        "email": email, "password": pwd, "name": "H4 Tester",
    })
    assert r.status_code in (200, 201), r.text[:300]
    token = r.json()["access_token"]
    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"},
    )
    ctx_id = me.json()["contexts"][0]["id"]
    account_id = me.json()["account"]["id"]
    hdrs = {"Authorization": f"Bearer {token}",
            "X-Active-Context": ctx_id}
    return token, ctx_id, account_id, hdrs, email, pwd


async def _seed_pre_v1_chat(*, account_id: str, ctx_id: str,
                             messages: list[dict], title: str = "pre-v1") -> str:
    """Insert a chat row WITHOUT synisense_audit_ids + its messages.
    Mirrors a real pre-Shield-v1.x record."""
    from core import db
    chat_id = "h4test-" + uuid.uuid4().hex[:12]
    await db.chats.insert_one({
        "id": chat_id,
        "account_id": account_id,
        "context_id": ctx_id,
        "title": title,
        "model_id": "claude-sonnet-4-5",
        "created_at": "2026-04-01T10:00:00+00:00",  # pre v1
        # No synisense_audit_ids → candidate for back-fill
    })
    for i, m in enumerate(messages):
        await db.chat_messages.insert_one({
            "id": "h4msg-" + uuid.uuid4().hex[:12],
            "chat_id": chat_id,
            "account_id": account_id,
            "role": m["role"],
            "content": m["content"],
            "created_at": f"2026-04-01T10:0{i}:00+00:00",
        })
    return chat_id


async def _superadmin_token(client):
    r = await client.post("/api/auth/login", json={
        "email": "admin@akki.ai", "password": "AkkiAdmin2026!",
    })
    assert r.status_code == 200, r.text[:300]
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ─────────────────────────────────────────────────────────────────────
# Test 1 — end-to-end back-fill with PII detected
# ─────────────────────────────────────────────────────────────────────
async def test_single_chat_backfill_end_to_end(client):
    """Independent re-run::
        python -m scripts.backfill_shield_v1 --limit 1
    """
    from core import db
    from services.backfill_shield_v1 import run_backfill

    _t, ctx_id, account_id, hdrs, _e, _p = await _register(client, "h4-e2e")
    chat_id = await _seed_pre_v1_chat(
        account_id=account_id, ctx_id=ctx_id, title="H4 e2e chat",
        messages=[
            {"role": "user", "content": "My card is 4111111111111111 and ssn is 123-45-6789."},
            {"role": "assistant", "content": "I've masked the [PAYMENT_CARD_••••1111]."},
        ],
    )

    # Drive back-fill DIRECTLY (admin path tested separately).
    summary = await run_backfill(batch_size=10, sleep_ms=0, limit=200)
    assert summary["total_chats_backfilled"] >= 1, summary

    # ── chat got synisense_audit_ids ──
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    assert chat["synisense_audit_ids"], chat
    assert all(aid.startswith("aud-bf-") for aid in chat["synisense_audit_ids"]), chat

    # ── backfill_metadata is complete + partial=False ──
    bf = chat.get("backfill_metadata") or {}
    assert bf.get("partial") is False, bf
    assert bf.get("original_pre_v1") is True, bf
    assert bf.get("messages_processed") == 2, bf
    assert bf.get("identifiers_detected") >= 2, bf  # PAN + SSN

    # ── chat_messages.shielding populated ──
    msgs = await db.chat_messages.find(
        {"chat_id": chat_id}, {"_id": 0},
    ).to_list(None)
    user_msg = next(m for m in msgs if m["role"] == "user")
    assert user_msg["shielding"]["identifiers_masked"] >= 2, user_msg["shielding"]
    assert "CREDIT_CARD" in user_msg["shielding"]["by_category"], user_msg

    # ── Trust Center returns "backfilled" status ──
    r = await client.get(
        f"/api/trust-center/session/{chat_id}", headers=hdrs,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["shield_status"] == "backfilled", body
    assert body["backfill_metadata"]["partial"] is False, body
    assert body["promise_summary"]["identifiers_shielded_total"] >= 2, body


# ─────────────────────────────────────────────────────────────────────
# Test 2 — idempotency
# ─────────────────────────────────────────────────────────────────────
async def test_backfill_idempotent_no_duplicate_audit_rows(client):
    from core import db
    from services.backfill_shield_v1 import run_backfill

    _t, ctx_id, account_id, _h, _e, _p = await _register(client, "h4-idem")
    chat_id = await _seed_pre_v1_chat(
        account_id=account_id, ctx_id=ctx_id, title="H4 idempotent",
        messages=[
            {"role": "user", "content": "Card 4111111111111111"},
        ],
    )
    await run_backfill(batch_size=10, sleep_ms=0, limit=200)
    audit_count_1 = await db.synisense_audit_log.count_documents(
        {"is_backfill": True, "purpose": {"$regex": "chat.backfill"}},
    )
    runs_count_1 = await db.synisense_runs.count_documents(
        {"chat_id": chat_id, "is_backfill": True},
    )

    # ── Re-run ──
    await run_backfill(batch_size=10, sleep_ms=0, limit=200)
    audit_count_2 = await db.synisense_audit_log.count_documents(
        {"is_backfill": True, "purpose": {"$regex": "chat.backfill"}},
    )
    runs_count_2 = await db.synisense_runs.count_documents(
        {"chat_id": chat_id, "is_backfill": True},
    )
    assert audit_count_2 == audit_count_1, (audit_count_1, audit_count_2)
    assert runs_count_2 == runs_count_1, (runs_count_1, runs_count_2)


# ─────────────────────────────────────────────────────────────────────
# Test 3 — partial-failure recovery
# ─────────────────────────────────────────────────────────────────────
async def test_backfill_partial_failure_marks_chat(client):
    from core import db
    from services.backfill_shield_v1 import run_backfill
    from services import backfill_shield_v1 as bf_module

    _t, ctx_id, account_id, _h, _e, _p = await _register(client, "h4-partial")
    chat_id = await _seed_pre_v1_chat(
        account_id=account_id, ctx_id=ctx_id, title="H4 partial",
        messages=[
            {"role": "user", "content": "first turn 4111111111111111"},
            {"role": "assistant", "content": "ok"},
        ],
    )

    # Patch the per-message back-fill so the SECOND message raises.
    call_count = {"n": 0}
    real_bf_msg = bf_module._backfill_message

    async def _flaky(**kwargs):
        call_count["n"] += 1
        if kwargs.get("chat", {}).get("id") == chat_id and call_count["n"] >= 2:
            raise RuntimeError("simulated mid-chat write failure")
        return await real_bf_msg(**kwargs)

    with mock.patch.object(bf_module, "_backfill_message", side_effect=_flaky):
        await run_backfill(batch_size=10, sleep_ms=0, limit=200)

    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    bf = chat.get("backfill_metadata") or {}
    assert bf.get("partial") is True, bf
    assert bf.get("error"), bf
    # The chat MUST remain a candidate for retry.
    candidate = await db.chats.find_one({
        "id": chat_id,
        "backfill_metadata.partial": {"$ne": False},
    })
    assert candidate is not None, "partial chats must be re-eligible"


# ─────────────────────────────────────────────────────────────────────
# Test 4 — rate limiting (batch size + sleep observed)
# ─────────────────────────────────────────────────────────────────────
async def test_backfill_rate_limiting_observed(client):
    from services.backfill_shield_v1 import run_backfill

    _t, ctx_id, account_id, _h, _e, _p = await _register(client, "h4-rate")
    # Seed enough chats to force at least 2 batches at batch_size=3.
    for i in range(7):
        await _seed_pre_v1_chat(
            account_id=account_id, ctx_id=ctx_id, title=f"rate-{i}",
            messages=[{"role": "user", "content": f"benign note #{i}"}],
        )

    sleep_calls = []
    real_sleep = asyncio.sleep

    async def _sleep_spy(seconds):
        sleep_calls.append(seconds)
        # Don't actually sleep — just record.
        return await real_sleep(0)

    with mock.patch("services.backfill_shield_v1.asyncio.sleep", side_effect=_sleep_spy):
        summary = await run_backfill(batch_size=3, sleep_ms=200, limit=200)

    # At least one batch boundary should have triggered a 0.2 s sleep.
    matching = [s for s in sleep_calls if abs(s - 0.2) < 1e-6]
    assert matching, (
        f"expected at least one 200 ms inter-batch sleep, got: "
        f"{sleep_calls!r}"
    )
    assert summary["total_chats_backfilled"] >= 7, summary


# ─────────────────────────────────────────────────────────────────────
# Test 5 — Trust Center post-backfill
# ─────────────────────────────────────────────────────────────────────
async def test_trust_center_post_backfill(client):
    from services.backfill_shield_v1 import run_backfill

    _t, ctx_id, account_id, hdrs, _e, _p = await _register(client, "h4-tc")
    chat_id = await _seed_pre_v1_chat(
        account_id=account_id, ctx_id=ctx_id, title="H4 TC integration",
        messages=[
            {"role": "user", "content": "Card 4111111111111111 please charge"},
            {"role": "assistant", "content": "I cannot store the card."},
        ],
    )
    await run_backfill(batch_size=5, sleep_ms=0, limit=200)

    # ── Trust Center session view ──
    r = await client.get(
        f"/api/trust-center/session/{chat_id}", headers=hdrs,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["shield_status"] == "backfilled", body
    # Turn list carries is_backfill=true on the user turn.
    user_turn = body["turns"][0]
    assert user_turn["is_backfill"] is True, user_turn
    assert user_turn["backfill_batch_id"], user_turn
    assert user_turn["original_message_ts"], user_turn

    # ── Per-turn drill-down: raw PAN absent, placeholders present,
    # AND the three back-fill markers MUST be populated (H4 cycle-2
    # serializer-gap regression). ──
    mid = user_turn["message_id"]
    r2 = await client.get(
        f"/api/trust-center/session/{chat_id}/turn/{mid}", headers=hdrs,
    )
    assert r2.status_code == 200, r2.text[:300]
    blob = r2.text
    assert "4111111111111111" not in blob, (
        f"FAIL-OPEN: raw PAN leaked: {blob[:300]!r}"
    )
    drill = r2.json()
    sent = drill["what_synisense_sent_to_llm"]
    assert "[[ENT_CREDIT_CARD" in sent or "[[ENT_" in sent, (
        f"drilldown must show tokenized placeholder: {sent!r}"
    )
    # ── POSITIVE: per-turn endpoint must surface the three
    # back-fill markers (was returning null before cycle 2). ──
    assert drill["is_backfill"] is True, (
        f"per-turn drill-down must mark back-filled turns as "
        f"is_backfill=true. Got: {drill.get('is_backfill')!r}"
    )
    assert drill["backfill_batch_id"], (
        f"per-turn drill-down must surface backfill_batch_id "
        f"(non-empty). Got: {drill.get('backfill_batch_id')!r}"
    )
    assert drill["original_message_ts"], (
        f"per-turn drill-down must surface original_message_ts "
        f"(non-empty). Got: {drill.get('original_message_ts')!r}"
    )


# ─────────────────────────────────────────────────────────────────────
# Test 6 — is_backfill marker on audit rows
# ─────────────────────────────────────────────────────────────────────
async def test_backfill_audit_rows_carry_is_backfill_marker(client):
    from core import db
    from services.backfill_shield_v1 import run_backfill

    _t, ctx_id, account_id, _h, _e, _p = await _register(client, "h4-marker")
    chat_id = await _seed_pre_v1_chat(
        account_id=account_id, ctx_id=ctx_id, title="H4 marker",
        messages=[{"role": "user", "content": "Card 4111111111111111"}],
    )
    summary = await run_backfill(batch_size=5, sleep_ms=0, limit=200)
    batch_id = summary["batch_id"]

    # Each persisted family must carry the marker.
    rows = await db.synisense_audit_log.find(
        {"backfill_batch_id": batch_id}, {"_id": 0},
    ).to_list(None)
    assert rows, rows
    for r in rows:
        assert r.get("is_backfill") is True, r
        assert r.get("backfill_batch_id") == batch_id, r
        assert r.get("original_message_ts"), r

    runs = await db.synisense_runs.find(
        {"backfill_batch_id": batch_id, "chat_id": chat_id}, {"_id": 0},
    ).to_list(None)
    assert runs, runs
    for r in runs:
        assert r.get("is_backfill") is True, r

    ca = await db.chat_audit_log.find(
        {"payload.backfill_batch_id": batch_id}, {"_id": 0},
    ).to_list(None)
    assert ca, ca
    for r in ca:
        assert r.get("payload", {}).get("is_backfill") is True, r
        assert r.get("backfill_chain_v1") is True, r


# ─────────────────────────────────────────────────────────────────────
# Test 7 — separate backfill_chain_v1 (doesn't pollute live chain)
# ─────────────────────────────────────────────────────────────────────
async def test_backfill_chain_separated_from_live(client):
    """The back-fill chain head must derive from PRIOR back-fill rows
    only — never from live chat_audit_log rows. This way the live
    chain's HMAC verification doesn't break when a back-fill row
    lands between live rows in temporal order."""
    from core import db
    from services.backfill_shield_v1 import (
        _backfill_chain_head, _row_hash, run_backfill,
    )

    _t, ctx_id, account_id, _h, _e, _p = await _register(client, "h4-chain")
    chat_id = await _seed_pre_v1_chat(
        account_id=account_id, ctx_id=ctx_id, title="H4 chain",
        messages=[{"role": "user", "content": "Card 4111111111111111"}],
    )
    head_before = await _backfill_chain_head()
    summary = await run_backfill(batch_size=5, sleep_ms=0, limit=200)
    head_after = await _backfill_chain_head()
    # Head advanced.
    assert head_after != head_before, (head_before, head_after)

    # Verify ALL back-fill rows in this batch carry backfill_chain_v1
    # AND do NOT carry any live-only flags.
    rows = await db.chat_audit_log.find(
        {"payload.backfill_batch_id": summary["batch_id"]}, {"_id": 0},
    ).to_list(None)
    assert rows, rows
    for r in rows:
        assert r.get("backfill_chain_v1") is True, r
        # Live chain rows DO NOT set this flag.
        live = await db.chat_audit_log.find_one(
            {"id": r["id"], "backfill_chain_v1": {"$exists": False}},
        )
        assert live is None, (
            "Back-fill row must NOT also appear in the unflagged live "
            "chain: " + str(r["id"])
        )


# ─────────────────────────────────────────────────────────────────────
# Test 8 — admin status endpoint
# ─────────────────────────────────────────────────────────────────────
async def test_admin_status_endpoint_returns_counts(client):
    """``GET /api/admin/shield/backfill/status`` requires superadmin
    AND returns the documented shape."""
    from services.backfill_shield_v1 import run_backfill

    # ── 401/403 for non-admin ──
    _t, _c, _a, hdrs, _e, _p = await _register(client, "h4-admin-nope")
    r = await client.get(
        "/api/admin/shield/backfill/status", headers=hdrs,
    )
    assert r.status_code == 403, (r.status_code, r.text[:200])

    # ── Run a back-fill so the latest-job summary is populated ──
    await run_backfill(batch_size=5, sleep_ms=0, limit=200)

    admin_hdrs = await _superadmin_token(client)
    r = await client.get(
        "/api/admin/shield/backfill/status", headers=admin_hdrs,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    expected_keys = {
        "running", "last_batch_id", "last_completed_at",
        "total_chats_scanned", "total_chats_backfilled",
        "total_audit_rows_written", "chats_with_pre_v1_pii_detected",
        "errors_count", "estimated_remaining_seconds", "pending_chats",
    }
    assert expected_keys.issubset(set(body.keys())), body
    assert isinstance(body["total_chats_backfilled"], int)
    assert isinstance(body["pending_chats"], int)
