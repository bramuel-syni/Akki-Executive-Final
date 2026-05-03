"""Phase 12.2 closeout — regression tests for the three production bugs.

BUG 1 — governance synisense rollup must include account-scoped runs.
BUG 2 — first-accept must persist `synisense_version >= 1`.
BUG 3 — chat synisense_stats.version must be threaded from the engine.

Implementation note: Motor pins its event loop on first I/O. We therefore
spin up a fresh `AsyncIOMotorClient` inside every `asyncio.run()` call so
that pre-amble inserts, the synchronous HTTP assertion in between, and
the post-amble cleanup each run cleanly without loop conflicts.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")

BACKEND = os.environ.get("AKKI_BACKEND_URL", "http://localhost:8001")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.session()
    r = s.post(
        f"{BACKEND}/api/auth/login",
        json={"email": "admin@akki.ai", "password": "AkkiAdmin2026!"},
        timeout=10,
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        pytest.skip("login did not return access_token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def _run_db(coro_factory):
    """Execute a one-shot DB coroutine with a fresh Motor client.

    `coro_factory` is a callable taking a Motor database handle and
    returning the coroutine to await. We open + close the client per
    call so Motor binds to the loop created by this `asyncio.run`.
    """
    async def _runner():
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            db = cli[os.environ["DB_NAME"]]
            return await coro_factory(db)
        finally:
            cli.close()
    return asyncio.run(_runner())


# ---------------------------------------------------------------------------
# BUG 1 — governance rollup now reads account-scoped + context-scoped runs
# ---------------------------------------------------------------------------
def test_governance_rollup_picks_up_synthetic_run(admin_session):
    """Insert a synthetic synisense_runs row scoped to admin's
    account+context, then assert the governance synisense block reflects
    it. The user's BUG 1 was that ungrounded chat runs (with empty
    context_id) were never reflected in the rollup. The fix is an
    `$or` on context_id ∈ ctx_ids OR account_id == current.id.
    """
    me = admin_session.get(f"{BACKEND}/api/auth/me", timeout=10).json()
    # /auth/me returns {account: {...}, contexts: [...]}; account_id is on account.
    account_id = me.get("account", {}).get("id") or me.get("id")
    assert account_id, me

    contexts_resp = admin_session.get(f"{BACKEND}/api/contexts", timeout=10).json()
    ctx_list = (
        contexts_resp.get("items")
        if isinstance(contexts_resp, dict)
        else contexts_resp
    ) or []
    ctx_id = ctx_list[0].get("id") if ctx_list else ""

    now = datetime.now(timezone.utc)
    synthetic_id = f"closeout-bug1-{uuid.uuid4().hex[:8]}"

    _run_db(lambda db: db.synisense_runs.insert_one({
        "id": synthetic_id,
        "context_id": ctx_id,
        "surface": "chat",
        "mode": "redact",
        "ts": now,
        "account_id": account_id,
        "input_sha256": "test" * 16,
        "spans": [
            {"start": 0, "end": 5, "entity_type": "EMAIL_ADDRESS",
             "source": "regex", "confidence": 1.0},
            {"start": 6, "end": 12, "entity_type": "DEAL_CODENAME",
             "source": "presidio", "confidence": 0.85},
        ],
        "stats": {"elapsed_ms": 5, "regex_hits": 1, "presidio_hits": 1,
                  "llm_hits": 0, "llm_calls": 0},
        "shield_map_id": None,
        "synisense_version": "12.1.0",
    }))

    try:
        body = admin_session.get(f"{BACKEND}/api/me/governance", timeout=10).json()
        syn = body.get("synisense", {})
        assert syn.get("active") is True, syn
        assert syn.get("last_run_at"), syn
        assert syn.get("spans_redacted_7d", 0) >= 2, syn
        hist = syn.get("entity_histogram_7d", {}) or {}
        assert "EMAIL_ADDRESS" in hist, hist
        assert "DEAL_CODENAME" in hist, hist
    finally:
        _run_db(lambda db: db.synisense_runs.delete_one({"id": synthetic_id}))


def test_governance_rollup_picks_up_ungrounded_chat_run(admin_session):
    """Variant: explicitly insert a row with empty context_id (the
    ungrounded-chat case the original filter missed) and assert it's
    still reflected via the account_id $or branch."""
    me = admin_session.get(f"{BACKEND}/api/auth/me", timeout=10).json()
    account_id = me.get("account", {}).get("id") or me.get("id")
    assert account_id, me

    now = datetime.now(timezone.utc)
    synthetic_id = f"closeout-bug1-ungrounded-{uuid.uuid4().hex[:8]}"

    _run_db(lambda db: db.synisense_runs.insert_one({
        "id": synthetic_id,
        "context_id": "",  # the precise shape that triggered the bug
        "surface": "chat",
        "mode": "redact",
        "ts": now,
        "account_id": account_id,
        "input_sha256": "x" * 64,
        "spans": [{"start": 0, "end": 5, "entity_type": "PHONE_NUMBER",
                   "source": "regex", "confidence": 1.0}],
        "stats": {"elapsed_ms": 3, "regex_hits": 1, "presidio_hits": 0,
                  "llm_hits": 0, "llm_calls": 0},
        "shield_map_id": None,
    }))
    try:
        syn = admin_session.get(
            f"{BACKEND}/api/me/governance", timeout=10,
        ).json().get("synisense", {})
        hist = syn.get("entity_histogram_7d", {}) or {}
        assert "PHONE_NUMBER" in hist, hist
    finally:
        _run_db(lambda db: db.synisense_runs.delete_one({"id": synthetic_id}))


# ---------------------------------------------------------------------------
# BUG 2 — first-accept persists synisense_version
# ---------------------------------------------------------------------------
def test_synisense_accept_persists_version(admin_session):
    """Pick any briefing the admin owns, touch a block so the save path
    fires Synisense, call /synisense-accept, then re-fetch and assert
    `synisense_version >= 1` is present and `synisense_first_accept_at`
    is populated.
    """
    rows = _run_db(lambda db: db.briefings.find(
        {}, {"_id": 0, "id": 1, "context_id": 1},
    ).to_list(1))
    if not rows:
        pytest.skip("no briefings seeded — backfill should have populated some")
    target = rows[0]
    aid = target["id"]

    # Touch an existing block so the save path runs and Synisense fires.
    blocks_now = admin_session.get(
        f"{BACKEND}/api/studio/briefing/{aid}/blocks", timeout=10,
    ).json()
    block_list = blocks_now.get("blocks") or []
    if block_list:
        bid = block_list[0]["id"]
        admin_session.patch(
            f"{BACKEND}/api/studio/briefing/{aid}/blocks/{bid}",
            json={"content": block_list[0].get("content") or {"text": "Refreshed"}},
            timeout=30,
        )

    # Hit /synisense-accept.
    r = admin_session.post(
        f"{BACKEND}/api/studio/briefing/{aid}/synisense-accept", timeout=10,
    )
    assert r.status_code == 200, r.text[:300]
    accept_body = r.json()
    assert accept_body["ok"] is True
    assert accept_body.get("synisense_first_accept_at")

    # Re-fetch the artefact and assert version is set.
    art = _run_db(lambda db: db.briefings.find_one(
        {"id": aid},
        {"_id": 0, "synisense_version": 1, "synisense_first_accept_at": 1},
    ))
    assert art and art.get("synisense_version") and int(art["synisense_version"]) >= 1, art
    assert art.get("synisense_first_accept_at"), art


def test_public_read_serves_redacted_body_not_original(admin_session):
    """Phase 12.2 closeout BUG 2 follow-on — the public-read endpoint
    must project from `body_redacted`, never from the original
    `opening_paragraph` / `items[]`. Insert PII in a fresh block, accept,
    mint a share token, hit `/api/public/studio/read/{token}` without
    auth, and assert the response carries redaction tokens (`[EMAIL_1]`
    etc.) rather than the original PII strings.
    """
    rows = _run_db(lambda db: db.briefings.find(
        {}, {"_id": 0, "id": 1, "context_id": 1},
    ).to_list(1))
    if not rows:
        pytest.skip("no briefings seeded")
    target = rows[0]
    aid = target["id"]
    cid = target["context_id"]

    pii_email = f"closeout-{uuid.uuid4().hex[:6]}@firstnationalbank.co.ke"
    pii_phone = "+44 20 7123 4567"
    add_block = admin_session.post(
        f"{BACKEND}/api/studio/briefing/{aid}/blocks",
        json={"kind": "paragraph", "content": {
            "text": f"Project Falcon contact: {pii_email}; phone {pii_phone}.",
        }},
        timeout=30,
    )
    assert add_block.status_code in (200, 201), add_block.text[:300]
    admin_session.post(
        f"{BACKEND}/api/studio/briefing/{aid}/synisense-accept", timeout=10,
    ).raise_for_status()

    share_resp = admin_session.post(
        f"{BACKEND}/api/contexts/{cid}/studio/briefing/{aid}/share-email",
        json={
            "to_email": "closeout-chair@example.com",
            "to_name": "Closeout Chair",
            "message": "regression test",
        },
        timeout=15,
    )
    share_resp.raise_for_status()
    tracked = share_resp.json().get("tracked_url")
    assert tracked, share_resp.json()
    token = tracked.rsplit("/", 1)[-1]

    # Hit public-read with NO session (no cookies, no auth header).
    public_resp = requests.get(
        f"{BACKEND}/api/public/studio/read/{token}", timeout=15,
    )
    assert public_resp.status_code == 200, (public_resp.status_code, public_resp.text[:300])
    body = public_resp.json()
    body_text = public_resp.text  # for substring grepping below

    # Originals must NOT appear anywhere in the response payload.
    for needle in (pii_email, pii_phone, "Project Falcon"):
        assert needle not in body_text, f"un-redacted PII '{needle}' leaked"

    # Redacted projection must be present in the briefing surface.
    op = (body.get("content") or {}).get("opening_paragraph") or ""
    assert "[EMAIL_1]" in op or "[EMAIL" in op, op
    assert "[PHONE_1]" in op or "[PHONE" in op, op

    # Denylist keys must not appear at any depth.
    for k in ("shield_map", "encrypted_original", "dek_wrapped",
              "dek_nonce", "envelope", "original_payload"):
        assert f'"{k}"' not in body_text, f"denylisted key '{k}' present"


# ---------------------------------------------------------------------------
# BUG 3 — chat synisense_stats.version threaded from the engine
# ---------------------------------------------------------------------------
def test_chat_synisense_stats_version_populated(admin_session):
    chat = admin_session.post(
        f"{BACKEND}/api/chats",
        json={"title": "closeout bug3", "model_id": "claude-sonnet-4-5"},
        timeout=10,
    ).json()
    cid = chat["id"]
    msg = admin_session.post(
        f"{BACKEND}/api/chats/{cid}/messages",
        json={"content": "Phone +44 20 7123 4567 about Project Wolf."},
        timeout=60,
    ).json()
    user_stats = (msg.get("user_message") or {}).get("synisense_stats") or {}
    asst_stats = (msg.get("assistant_message") or {}).get("synisense_stats") or {}
    assert user_stats.get("version"), user_stats
    assert asst_stats.get("version"), asst_stats
    # Engine version is the package's `12.1.0`-style string today.
    assert isinstance(asst_stats["version"], str)
    assert "." in asst_stats["version"]
