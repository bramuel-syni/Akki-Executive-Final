"""H3 — Trust Center v1 wire-level tests.

Validates the four ``/api/trust-center/*`` endpoints against the
exact scoping rules in the H3 brief:

  * (1) Owner can read their session.
  * (2) Cross-context request returns 403.
  * (3) Drill-down surfaces the tokenized prompt (NOT the raw PAN).
  * (4) Plaintext as owner returns plaintext + writes audit row.
  * (5) Plaintext as a different non-owner same-context user → 403.
  * (6) Plaintext as superadmin in context → 200 + audit row.
  * (7) Activity scoping — ?context_id=<other> → 0 rows.
  * (8) Pre-Shield-v1.x chat → shield_status=pre_shield_v1.

Independent re-run recipe is embedded in each test docstring.
"""
from __future__ import annotations

import os
import uuid

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


async def _register(client, email_prefix: str = "tc"):
    email = f"{email_prefix}-{uuid.uuid4().hex[:10]}@example.com"
    pwd = "TrustCenter2026!"
    r = await client.post("/api/auth/register", json={
        "email": email, "password": pwd, "name": "Trust Center Tester",
    })
    assert r.status_code in (200, 201), r.text[:300]
    token = r.json()["access_token"]
    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"},
    )
    ctx_id = me.json()["contexts"][0]["id"]
    account_id = me.json()["account"]["id"]
    hdrs = {
        "Authorization": f"Bearer {token}",
        "X-Active-Context": ctx_id,
    }
    return token, ctx_id, account_id, hdrs


async def _new_chat_with_pan_turn(client, hdrs, *, title: str = "tc test"):
    r = await client.post(
        "/api/chats",
        json={"title": title},
        headers=hdrs,
    )
    chat_id = r.json()["id"]
    # Use the SYNC endpoint — deterministic synisense_runs row.
    msg_resp = await client.post(
        f"/api/chats/{chat_id}/messages",
        json={"content": "My card is 4111111111111111 please charge it."},
        headers=hdrs, timeout=30.0,
    )
    assert msg_resp.status_code == 200, msg_resp.text[:300]
    body = msg_resp.json()
    user_message_id = body["user_message"]["id"]
    return chat_id, user_message_id


# ─────────────────────────────────────────────────────────────────────
# Test 1 — Owner can read their session
# ─────────────────────────────────────────────────────────────────────
async def test_session_owner_can_read(client):
    """Independent re-run::
        curl "$API/api/trust-center/session/$CHAT" \\
            -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
        # expect: 200 + promise_summary populated
    """
    _t, ctx_id, account_id, hdrs = await _register(client)
    chat_id, _ = await _new_chat_with_pan_turn(client, hdrs)
    r = await client.get(
        f"/api/trust-center/session/{chat_id}", headers=hdrs,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["chat_id"] == chat_id
    assert body["shield_status"] == "active"
    summary = body["promise_summary"]
    assert summary["identifiers_shielded_total"] >= 1, summary
    assert "CREDIT_CARD" in summary["by_class"], summary
    assert body["turns"], body
    # The promise statement must be honest — not marketing prose.
    assert "0%" in summary["your_data_exposure_pct"], summary


# ─────────────────────────────────────────────────────────────────────
# Test 2 — Cross-context request returns 403
# ─────────────────────────────────────────────────────────────────────
async def test_session_cross_context_returns_403(client):
    """Independent re-run: create a chat as user A in context A; call
    Trust Center with user B's token (who is in context B). Expect 403."""
    _t1, _c1, _a1, hdrs_a = await _register(client, "tc-a")
    chat_id, _ = await _new_chat_with_pan_turn(client, hdrs_a)

    _t2, _c2, _a2, hdrs_b = await _register(client, "tc-b")
    r = await client.get(
        f"/api/trust-center/session/{chat_id}", headers=hdrs_b,
    )
    assert r.status_code == 403, (r.status_code, r.text[:300])
    assert "don't have access" in r.text or "owner" in r.text


# ─────────────────────────────────────────────────────────────────────
# Test 3 — Drill-down surfaces tokenized prompt (NOT raw PAN)
# ─────────────────────────────────────────────────────────────────────
async def test_turn_drilldown_shows_tokenized_not_raw(client):
    """Independent re-run::
        curl "$API/api/trust-center/session/$CHAT/turn/$MID" \\
            -H "Authorization: Bearer $TOKEN" | grep -c "4111111111111111"
        # expect: 0
    """
    _t, _c, _a, hdrs = await _register(client)
    chat_id, mid = await _new_chat_with_pan_turn(client, hdrs)
    r = await client.get(
        f"/api/trust-center/session/{chat_id}/turn/{mid}",
        headers=hdrs,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    # The 4-row evidence shape.
    assert "what_you_sent_sha256" in body
    assert "what_synisense_sent_to_llm" in body
    assert "what_llm_returned" in body
    assert "what_you_saw" in body
    # CRITICAL: raw PAN MUST NOT appear in any field of this response.
    blob = r.text
    assert "4111111111111111" not in blob, (
        f"FAIL-OPEN: raw PAN leaked in Trust Center drill-down: "
        f"{blob[:400]!r}"
    )
    # The hash MUST be present + 64 hex chars.
    sha = body["what_you_sent_sha256"]
    assert len(sha) == 64 and all(c in "0123456789abcdef" for c in sha), sha
    # The CREDIT_CARD redaction must be visible.
    classes = [r["class"] for r in body["redactions"]]
    assert "CREDIT_CARD" in classes, body["redactions"]


# ─────────────────────────────────────────────────────────────────────
# Test 4 — Plaintext as owner: 200 + plaintext + audit row written
# ─────────────────────────────────────────────────────────────────────
async def test_plaintext_owner_returns_text_and_audits(client):
    """The plaintext endpoint is the ONLY surface that returns raw
    text. It MUST also write an audit row for the view event itself.

    Independent re-run::
        curl "$API/api/trust-center/session/$CHAT/turn/$MID/plaintext" \\
            -H "Authorization: Bearer $TOKEN"
        # Then verify the audit row exists in Mongo:
        # db.chat_audit_log.find({action:'trust_center.plaintext_viewed'})
    """
    from core import db

    _t, _c, account_id, hdrs = await _register(client)
    chat_id, mid = await _new_chat_with_pan_turn(client, hdrs)
    before = await db.chat_audit_log.count_documents(
        {"chat_id": chat_id, "action": "trust_center.plaintext_viewed"},
    )
    r = await client.get(
        f"/api/trust-center/session/{chat_id}/turn/{mid}/plaintext",
        headers=hdrs,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert "4111111111111111" in body["plaintext"], body
    assert body["audit_logged"] is True, body
    after = await db.chat_audit_log.count_documents(
        {"chat_id": chat_id, "action": "trust_center.plaintext_viewed"},
    )
    assert after == before + 1, (
        f"audit row missing: before={before}, after={after}"
    )


# ─────────────────────────────────────────────────────────────────────
# Test 5 — Plaintext as non-owner same-context user → 403
# ─────────────────────────────────────────────────────────────────────
async def test_plaintext_non_owner_same_context_returns_403(client):
    """Even members of the same context cannot read another user's
    plaintext unless they're a context superadmin. This test creates
    two members of the SAME context and asserts user-B is denied
    on user-A's chat plaintext."""
    from core import db

    _t_a, ctx_id, acct_a, hdrs_a = await _register(client, "tc-share-a")
    chat_id, mid = await _new_chat_with_pan_turn(client, hdrs_a)

    # Register user B and grant them membership in user A's context
    # WITHOUT admin privileges.
    _t_b, _ctx_b, acct_b, hdrs_b = await _register(client, "tc-share-b")
    await db.memberships.insert_one({
        "id": "m-" + uuid.uuid4().hex,
        "account_id": acct_b,
        "context_id": ctx_id,
        "status": "active",
        "sub_role": "member",  # NOT admin
    })
    # Override the Active-Context header so user B's call lands on
    # user A's context.
    hdrs_b["X-Active-Context"] = ctx_id

    r = await client.get(
        f"/api/trust-center/session/{chat_id}/turn/{mid}/plaintext",
        headers=hdrs_b,
    )
    assert r.status_code == 403, (r.status_code, r.text[:300])
    assert "owner" in r.text or "superadmin" in r.text


# ─────────────────────────────────────────────────────────────────────
# Test 6 — Plaintext as superadmin in context: 200 + audit row
# ─────────────────────────────────────────────────────────────────────
async def test_plaintext_superadmin_in_context_returns_text(client):
    """A user with ``sub_role=admin`` membership in the chat's context
    can read plaintext + the access is itself audit-logged."""
    from core import db

    _t_a, ctx_id, _a_a, hdrs_a = await _register(client, "tc-supa-a")
    chat_id, mid = await _new_chat_with_pan_turn(client, hdrs_a)

    _t_b, _ctx_b, acct_b, hdrs_b = await _register(client, "tc-supa-b")
    await db.memberships.insert_one({
        "id": "m-" + uuid.uuid4().hex,
        "account_id": acct_b,
        "context_id": ctx_id,
        "status": "active",
        "sub_role": "admin",  # IS context admin
    })
    hdrs_b["X-Active-Context"] = ctx_id

    before = await db.chat_audit_log.count_documents(
        {"chat_id": chat_id, "action": "trust_center.plaintext_viewed"},
    )
    r = await client.get(
        f"/api/trust-center/session/{chat_id}/turn/{mid}/plaintext",
        headers=hdrs_b,
    )
    assert r.status_code == 200, (r.status_code, r.text[:300])
    body = r.json()
    assert body["viewer_id"] == acct_b, body
    after = await db.chat_audit_log.count_documents(
        {"chat_id": chat_id, "action": "trust_center.plaintext_viewed"},
    )
    assert after == before + 1, (before, after)


# ─────────────────────────────────────────────────────────────────────
# Test 7 — Activity scoping: ?context_id=<other> → 403 or 0 rows
# ─────────────────────────────────────────────────────────────────────
async def test_activity_cross_context_returns_403(client):
    """User in context A requesting activity scoped to context B (which
    they're not a member of) must get a 403."""
    _t_a, _c_a, _a_a, hdrs_a = await _register(client, "tc-act-a")
    _t_b, ctx_b, _a_b, _h_b = await _register(client, "tc-act-b")

    r = await client.get(
        f"/api/trust-center/activity?context_id={ctx_b}",
        headers=hdrs_a,
    )
    assert r.status_code == 403, (r.status_code, r.text[:300])


async def test_activity_no_leakage_across_contexts(client):
    """Without explicit context filter, activity returns ONLY rows from
    contexts the caller is a member of. User A creates a turn in
    context A; user B (different context) sees zero rows from chat A."""
    _t_a, _c_a, _a_a, hdrs_a = await _register(client, "tc-leak-a")
    chat_id, _mid = await _new_chat_with_pan_turn(client, hdrs_a, title="leak-test")

    _t_b, _c_b, _a_b, hdrs_b = await _register(client, "tc-leak-b")
    r = await client.get("/api/trust-center/activity", headers=hdrs_b)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    chat_ids_in_resp = {row.get("chat_id") for row in body.get("rows", [])}
    assert chat_id not in chat_ids_in_resp, (
        f"LEAK: user B saw user A's chat ({chat_id}) in activity rows: "
        f"{chat_ids_in_resp}"
    )


# ─────────────────────────────────────────────────────────────────────
# Test 8 — Pre-Shield-v1.x chat → shield_status="pre_shield_v1"
# ─────────────────────────────────────────────────────────────────────
async def test_pre_shield_v1_chat_returns_empty_state(client):
    """Chats without ``synisense_audit_ids`` are pre-instrumentation.
    Trust Center returns an empty-state shell with a documented
    caveat — UI keys off ``shield_status`` to render the back-fill
    notice."""
    from core import db

    _t, _ctx, account_id, hdrs = await _register(client, "tc-pre")
    # Insert a chat manually WITHOUT synisense_audit_ids (simulates
    # a pre-2026-02 row).
    pre_chat_id = "pre-" + uuid.uuid4().hex
    await db.chats.insert_one({
        "id": pre_chat_id,
        "account_id": account_id,
        "context_id": _ctx,
        "title": "Pre-Shield-v1.x conversation",
        "model_id": "claude-sonnet-4-5",
        "synisense_audit_ids": [],
    })
    r = await client.get(
        f"/api/trust-center/session/{pre_chat_id}", headers=hdrs,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["shield_status"] == "pre_shield_v1", body
    assert body["promise_summary"] is None, body
    assert any("predates Shield" in c for c in body["caveats"]), body["caveats"]
