"""Phase P5.10 (2026-02) — Audit-panel direct-linkage regression.

User-reported production bug: after a single cancelled chat turn,
every subsequent turn in the same chat shows "Audit data isn't
available for this message yet" in the Synisense audit panel.

Root cause: the audit-panel endpoint resolved each message's audit
by indexing into `chats.synisense_audit_ids[]` at the position the
message occupied in the chronologically-sorted assistant_msgs
array. The cancel path inserted an assistant_msgs row but did NOT
push a placeholder id, so every turn AFTER a cancellation was
off-by-one. Two-cancellation chats were off-by-two, and so on.

Fix: store the Shield audit_id directly on the chat_messages
assistant row (`shield_audit_id` field), and have the audit-panel
resolver prefer the direct linkage. The positional index remains
as a fallback for legacy rows.

Tests below seed chat_messages + chats rows directly to exercise
the resolver without standing up the full stream + Shield
pipeline (which requires a real Anthropic key and an SSE round-
trip — out of scope for unit-level coverage).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pymongo

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from server import app  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _dbc():
    return pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _seed_chat_with_messages(
    *,
    account_id: str,
    turns: list,
) -> str:
    """Seed one chat + N assistant messages + corresponding
    `synisense_audit_log` rows and `synisense_audit_ids` on the chat.

    `turns` is a list of dicts: {direct_audit_id, push_to_chat_array,
    cancelled}. `direct_audit_id=None` means the assistant message
    has NO direct linkage (legacy row). `push_to_chat_array=False`
    means the chat's audit_ids array gets no entry for that turn
    (simulating the cancel-without-push pre-fix state).
    """
    dbc = _dbc()
    chat_id = uuid.uuid4().hex
    audit_ids_pushed = []
    msg_ids = []
    now_base = datetime.now(timezone.utc)

    for i, t in enumerate(turns):
        msg_id = uuid.uuid4().hex
        msg_ids.append(msg_id)
        # Insert the audit row in synisense_audit_log so the resolver
        # can return it.
        direct_audit_id = t.get("direct_audit_id")
        if direct_audit_id:
            dbc.synisense_audit_log.insert_one({
                "audit_id": direct_audit_id, "tenant_id": account_id,
                "purpose": "test", "purpose_label": "Test",
                "consumer": "p5.10-test", "outcome": t.get("outcome", "ok"),
                "scores": {}, "shielding": {}, "provider": {},
            })
        # Insert the assistant chat_messages row.
        dbc.chat_messages.insert_one({
            "id": msg_id, "chat_id": chat_id, "account_id": account_id,
            "role": "assistant",
            "content": f"turn-{i}",
            "created_at": (now_base + timedelta(seconds=i)).isoformat(),
            "mode": "cancelled" if t.get("cancelled") else "live",
            "cancelled": bool(t.get("cancelled")),
            "shield_audit_id": direct_audit_id,
        })
        if t.get("push_to_chat_array"):
            audit_ids_pushed.append(direct_audit_id or f"legacy-{i}")

    dbc.chats.insert_one({
        "id": chat_id, "account_id": account_id,
        "synisense_audit_ids": audit_ids_pushed,
        "protective_layer_events": [],
        "created_at": now_base.isoformat(),
    })
    return chat_id, msg_ids


def _http_get_audit_panel(*, chat_id: str, message_id: str, account_id: str):
    """Hit the endpoint with a synthetic auth context. We swap the
    `get_current_account` dep for a function that returns the test
    account, so the endpoint's auth gate doesn't block the test."""
    from core import get_current_account
    app.dependency_overrides[get_current_account] = lambda: {
        "id": account_id, "email": "test@test", "is_superadmin": False,
    }
    async def _do():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            return await ac.get(
                f"/api/chats/{chat_id}/audit-panel",
                params={"message_id": message_id},
            )
    try:
        return _run(_do())
    finally:
        app.dependency_overrides.pop(get_current_account, None)


# ─── Direct linkage takes precedence over positional index ────────────
def test_p5_10_audit_panel_uses_direct_shield_audit_id():
    account_id = f"acc-p5-10-direct-{uuid.uuid4().hex[:6]}"
    chat_id, msg_ids = _seed_chat_with_messages(
        account_id=account_id,
        turns=[
            {"direct_audit_id": f"AUDIT-A-{uuid.uuid4().hex[:6]}",
             "push_to_chat_array": True},
            {"direct_audit_id": f"AUDIT-B-{uuid.uuid4().hex[:6]}",
             "push_to_chat_array": True},
        ],
    )

    # Look up audit for the 2nd turn. With direct linkage, the
    # resolver should return AUDIT-B (the one on the chat_messages row).
    r = _http_get_audit_panel(chat_id=chat_id, message_id=msg_ids[1], account_id=account_id)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["audit_id"].startswith("AUDIT-B"), (
        f"expected AUDIT-B (direct linkage) but got {body['audit_id']!r}"
    )


# ─── The fix: cancellation does NOT cascade to next-turn audit ────────
def test_p5_10_cancelled_turn_does_not_break_next_turn_audit():
    """The user-reported bug. Pre-fix scenario:
      - Turn 1 cancelled — assistant row inserted, NO push to audit_ids[]
      - Turn 2 succeeded — assistant row inserted, push to audit_ids[]
        ⇒ positional resolver gives Turn 2 the audit_ids[0] which is wrong.
    With the fix:
      - Turn 1 carries shield_audit_id=AUDIT-CANCEL on the row
      - Turn 2 carries shield_audit_id=AUDIT-T2 on the row
      ⇒ both resolve correctly via direct linkage regardless of how
        many pushes landed on audit_ids[].
    """
    account_id = f"acc-p5-10-cascade-{uuid.uuid4().hex[:6]}"
    chat_id, msg_ids = _seed_chat_with_messages(
        account_id=account_id,
        turns=[
            # Turn 1: CANCELLED — simulates pre-P5.10 cancel-path (no push).
            # But carries the new direct shield_audit_id field (post-P5.10).
            {"direct_audit_id": f"AUDIT-CANCEL-{uuid.uuid4().hex[:6]}",
             "push_to_chat_array": False, "cancelled": True,
             "outcome": "cancelled"},
            # Turn 2: SUCCEEDED — pushes to audit_ids[] AND direct linkage.
            {"direct_audit_id": f"AUDIT-T2-{uuid.uuid4().hex[:6]}",
             "push_to_chat_array": True},
        ],
    )

    # The cancelled turn now resolves via direct linkage.
    r1 = _http_get_audit_panel(chat_id=chat_id, message_id=msg_ids[0], account_id=account_id)
    assert r1.status_code == 200, r1.text
    assert r1.json()["audit_id"].startswith("AUDIT-CANCEL"), (
        "cancelled turn's audit should resolve via direct linkage; "
        f"got {r1.json()['audit_id']!r}"
    )

    # The next turn resolves to its OWN audit, not the cancelled one's.
    r2 = _http_get_audit_panel(chat_id=chat_id, message_id=msg_ids[1], account_id=account_id)
    assert r2.status_code == 200, r2.text
    assert r2.json()["audit_id"].startswith("AUDIT-T2"), (
        "subsequent successful turn must resolve to its own audit_id, "
        "not inherit the cancelled turn's. "
        f"got {r2.json()['audit_id']!r}"
    )


# ─── Legacy positional fallback still works for pre-P5.10 rows ────────
def test_p5_10_legacy_positional_fallback_when_direct_link_missing():
    """A pre-P5.10 chat_messages row has no `shield_audit_id` field.
    The resolver must fall back to positional indexing for it."""
    account_id = f"acc-p5-10-legacy-{uuid.uuid4().hex[:6]}"
    dbc = _dbc()
    chat_id = uuid.uuid4().hex
    msg_id = uuid.uuid4().hex
    legacy_audit_id = f"AUDIT-LEGACY-{uuid.uuid4().hex[:6]}"
    dbc.synisense_audit_log.insert_one({
        "audit_id": legacy_audit_id, "tenant_id": account_id,
        "purpose": "test", "purpose_label": "Test",
        "consumer": "p5.10-legacy", "outcome": "ok",
        "scores": {}, "shielding": {}, "provider": {},
    })
    now = datetime.now(timezone.utc)
    # Note: NO shield_audit_id field on the row — simulates legacy.
    dbc.chat_messages.insert_one({
        "id": msg_id, "chat_id": chat_id, "account_id": account_id,
        "role": "assistant", "content": "legacy turn",
        "created_at": now.isoformat(),
        "mode": "live",
    })
    dbc.chats.insert_one({
        "id": chat_id, "account_id": account_id,
        "synisense_audit_ids": [legacy_audit_id],
        "protective_layer_events": [],
    })

    r = _http_get_audit_panel(chat_id=chat_id, message_id=msg_id, account_id=account_id)
    assert r.status_code == 200, r.text
    assert r.json()["audit_id"] == legacy_audit_id, (
        f"positional fallback should still resolve legacy rows; got {r.json()['audit_id']!r}"
    )


# ─── 404 when message_id genuinely doesn't exist ──────────────────────
def test_p5_10_404_when_message_id_missing():
    account_id = f"acc-p5-10-404-{uuid.uuid4().hex[:6]}"
    chat_id = uuid.uuid4().hex
    _dbc().chats.insert_one({
        "id": chat_id, "account_id": account_id,
        "synisense_audit_ids": [], "protective_layer_events": [],
    })

    r = _http_get_audit_panel(
        chat_id=chat_id, message_id="nonexistent-id-xxxxx",
        account_id=account_id,
    )
    assert r.status_code == 404, r.text


# ─── User-role messages get 404 (not silently mistaken for audit) ─────
def test_p5_10_user_role_message_returns_404():
    """Audit panel is for assistant messages only. A user-role
    message_id must 404."""
    account_id = f"acc-p5-10-userrole-{uuid.uuid4().hex[:6]}"
    chat_id = uuid.uuid4().hex
    user_msg_id = uuid.uuid4().hex
    _dbc().chat_messages.insert_one({
        "id": user_msg_id, "chat_id": chat_id, "account_id": account_id,
        "role": "user", "content": "the user's prompt",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _dbc().chats.insert_one({
        "id": chat_id, "account_id": account_id,
        "synisense_audit_ids": [], "protective_layer_events": [],
    })

    r = _http_get_audit_panel(
        chat_id=chat_id, message_id=user_msg_id, account_id=account_id,
    )
    assert r.status_code == 404, r.text
