"""Phase B P0 — chat consumer surface fix regression tests.

Locks the 3 defects e1_tester T2 caught on 2026-05-13:
1. `NameError: name 'account_id' is not defined` on the migrated chat
   send path — chat send now reaches Shield.
2. `chats.synisense_audit_ids` array missing — chat send now $pushes
   the Shield audit_id onto the session document on every turn.
3. Legacy chat-router de-id pipeline divergence — only Synisense
   Shield runs; the chat router no longer calls `syn_run` /
   `_syn_shield`.
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from server import app


@pytest_asyncio.fixture
async def db_conn():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    yield db
    client.close()


@pytest_asyncio.fixture
async def client():
    os.environ["SYNISENSE_LLM_MODE"] = "mock"  # hermetic — no live LLM
    saved_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.update(saved_overrides)


@pytest_asyncio.fixture
async def chat_user(db_conn):
    """Authenticated account + active context + chat ready to receive
    messages."""
    suffix = uuid.uuid4().hex[:8]
    email = f"chatfix-{suffix}@example.com"
    password = "ChatFix2026!"
    account_id = f"acc-chatfix-{suffix}"
    context_id = f"ctx-chatfix-{suffix}"
    chat_id = f"cht-{uuid.uuid4().hex}"
    from core import hash_password
    now = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "Chat Fix Probe", "role": "executive", "verified": True,
        "session_version": 0, "created_at": now,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "ChatFix Context", "created_at": now,
    })
    await db_conn.chats.insert_one({
        "id": chat_id, "account_id": account_id, "context_id": context_id,
        "title": "Phase B fix test chat", "model_id": "gemini-2.5-flash",
        "shielding_policy": "always", "status": "active",
        "created_at": now, "updated_at": now,
    })
    yield {"email": email, "password": password,
           "account_id": account_id, "context_id": context_id,
           "chat_id": chat_id}
    await db_conn.accounts.delete_one({"id": account_id})
    await db_conn.contexts.delete_one({"id": context_id})
    await db_conn.chats.delete_one({"id": chat_id})
    await db_conn.chat_messages.delete_many({"chat_id": chat_id})
    await db_conn.synisense_audit_log.delete_many({"tenant_id": account_id})


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {
        "Authorization": f"Bearer {r.json()['access_token']}",
    }


# ═════════════════════════════════════════════════════════════════════
# Defect 1 + Defect 2 — chat send reaches Shield + audit_id is pushed.
# ═════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_chat_send_reaches_shield(client, db_conn, chat_user):
    """User authenticates, POSTs a chat message containing PII,
    asserts:
    - HTTP 200 (NOT mode=error).
    - chat.synisense_audit_ids array grew by exactly 1.
    - GET /api/v1/shield/audit/{audit_id} returns the row with
      consumer_id='chat' AND purpose starting 'chat.'.
    """
    auth = await _login(client, chat_user["email"], chat_user["password"])
    headers = {**auth, "X-Active-Context": chat_user["context_id"]}

    r = await client.post(
        f"/api/chats/{chat_user['chat_id']}/messages",
        headers=headers,
        json={
            "content": "Wire $50,000 to John Smith on 2026-01-15. "
                       "Contact: john.smith@example.com.",
            "acknowledge_unshielded": False,
        },
    )
    # Surface defect 1 directly if it returns: NameError would
    # produce an explicit `(LLM error: NameError: ...)` body.
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
    body = r.json()
    assistant_msg = (body.get("assistant") or {}).get("content") or ""
    assert "NameError" not in assistant_msg, (
        "Defect 1 regression — chat reply leaks NameError: " + assistant_msg[:160]
    )
    assert "(LLM error" not in assistant_msg, (
        "chat reply still in error mode: " + assistant_msg[:160]
    )

    # Defect 2: chat.synisense_audit_ids must have grown by exactly 1.
    chat_row = await db_conn.chats.find_one(
        {"id": chat_user["chat_id"]}, {"_id": 0, "synisense_audit_ids": 1},
    )
    audit_ids = chat_row.get("synisense_audit_ids") or []
    assert len(audit_ids) == 1, (
        f"chat.synisense_audit_ids should hold exactly 1 audit_id; got {audit_ids!r}"
    )
    audit_id = audit_ids[0]
    assert audit_id.startswith("aud-"), f"bad audit_id shape: {audit_id!r}"

    # The audit row is retrievable through the Shield API, scoped to
    # this user, with consumer_id='chat' and a chat.* purpose.
    aud = await client.get(f"/api/v1/shield/audit/{audit_id}", headers=auth)
    assert aud.status_code == 200, aud.text
    aud_body = aud.json()
    assert aud_body["consumer_id"] == "chat", aud_body
    assert aud_body["purpose"].startswith("chat."), aud_body


@pytest.mark.asyncio
async def test_chat_send_pushes_one_audit_id_per_turn(client, db_conn, chat_user):
    """Two sends → exactly two entries in synisense_audit_ids."""
    auth = await _login(client, chat_user["email"], chat_user["password"])
    headers = {**auth, "X-Active-Context": chat_user["context_id"]}
    for i, content in enumerate(["First turn.", "Second turn."]):
        r = await client.post(
            f"/api/chats/{chat_user['chat_id']}/messages",
            headers=headers,
            json={"content": content, "acknowledge_unshielded": False},
        )
        assert r.status_code == 200, r.text
    chat_row = await db_conn.chats.find_one(
        {"id": chat_user["chat_id"]}, {"_id": 0, "synisense_audit_ids": 1},
    )
    audit_ids = chat_row.get("synisense_audit_ids") or []
    assert len(audit_ids) == 2, f"expected 2 audit ids, got {audit_ids!r}"
    # Unique.
    assert len(set(audit_ids)) == 2, "audit_ids must be unique per turn"


# ═════════════════════════════════════════════════════════════════════
# Defect 3 — no secondary de-id pipeline in the chat router.
# ═════════════════════════════════════════════════════════════════════
def test_no_secondary_deid_in_chat_router():
    """Statically asserts the chat router no longer calls the legacy
    Phase 12.1 `syn_run` de-id pipeline as the PRIMARY de-id source.

    H2.5 update (2026-05-24): the original Phase-B contract said
    Synisense Shield is the *single* de-id source. That holds today
    for the sync path (which calls `shield.client.invoke()`). The
    streaming path, however, writes a `chat_audit_log` row BEFORE the
    LLM round-trip and needs an authoritative detection count at that
    point — without it the chat_audit row reported
    `identifiers_detected=0` while the downstream Shield audit (run
    inside `prepare_for_streaming`) reported the real counts, creating
    a CROSS-AUDIT-ROW CONTRADICTION (caught by e1_tester independent
    verification). The streaming path therefore now calls
    `_syn_shield(text)` ONCE at message ingress, with the result
    feeding both the chat_audit row AND the downstream Shield audit
    via `prepare_for_streaming`. This is one detection step, two
    consistent audit writes — not "double de-id".

    The forbidden patterns below are tightened to catch new
    introductions of the legacy `syn_run` entry point (the still-bad
    pattern) WITHOUT flagging the legitimate ingress-time
    `_syn_shield(...)` call introduced by H2.5.
    """
    p = "/app/backend/routers/chat.py"
    text = open(p, encoding="utf-8").read()

    # Walk every executable (non-comment, non-docstring) line and
    # check no forbidden call patterns survive in the chat router.
    forbidden = [
        # The legacy three-layer pipeline entry-point.
        re.compile(r"^\s*from\s+services\.synisense\s+import\s+run\s+as\s+syn_run", re.M),
        re.compile(r"(?<!\.)\bsyn_run\s*\(", re.M),
        # Note (H2.5): `_syn_shield(...)` is NO LONGER forbidden in the
        # chat router — see docstring. It is the audit-integrity
        # primitive used at streaming ingress.
    ]
    violations = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for pat in forbidden:
            if pat.search(line):
                violations.append(f"chat.py:{line_no}  {line.strip()[:120]}")
    assert not violations, (
        "Defect 3 regression — legacy `syn_run` pipeline re-appeared "
        "in routers/chat.py. Shield is the single CALL pipeline; "
        "`_syn_shield(text)` is the explicit-by-design audit-integrity "
        "pre-pass added by H2.5 (see test_h2_5_shield_uniformity.py)."
        "\n\n" + "\n".join(violations)
    )

    # Positive control: Shield IS the de-id pipeline now.
    assert "from services.synisense.shield.client import invoke as shield_invoke" in text, (
        "chat.py should import shield_invoke for its de-id+LLM path"
    )
    assert 'purpose="chat.standard_response"' in text, (
        "chat.py standard-response Shield purpose missing"
    )


def test_chat_router_does_not_construct_local_masker():
    """Sanity grep — no Presidio analyzer / spaCy nlp / regex masker
    instantiations live inside `routers/chat.py`. Shield owns those."""
    p = "/app/backend/routers/chat.py"
    text = open(p, encoding="utf-8").read()
    # Looking for direct instantiation of an analyzer / pipeline.
    bad = [
        "AnalyzerEngine(", "PresidioEngine(", "spacy.load(",
    ]
    for hit in bad:
        # Ignore comment-only mentions.
        for line in text.splitlines():
            if hit in line and not line.lstrip().startswith("#"):
                raise AssertionError(
                    f"chat.py constructs a local masker ({hit!r}) — "
                    "Shield is the only de-id pipeline post-Phase B."
                )
