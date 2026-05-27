"""Phase F.5 — Contributor notification modes wire + live tests (2026-05-26).

Covers:
  • Mode 1 (Akki account) — invite email + audit row on commission
  • Mode 2 (magic link) — token persistence + public GET / upload /
    comment / submit endpoints work WITHOUT auth header
  • Mode 3 (email reply) — inbound webhook recognizes
    `task-<token>@...` MailboxHash, parses body + attachments,
    flips status, fires audit
  • Coexistence — `allow_email_reply` adds an email_reply email
    alongside the primary mode's email
  • Re-invite endpoint rotates the magic-link token
  • Enhancement 1 — Compile session pill on task cards
  • Enhancement 2 — `?compile_stage=` URL param opens Compile tab
  • ContributorPortal page exists + is mounted at /contribute/:token
  • Inbound email signature stripping heuristic
"""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
FE   = REPO / "frontend" / "src"
BE   = REPO / "backend"

CONTRIB_PORTAL  = FE / "pages" / "ContributorPortal.jsx"
APP_JS          = FE / "App.js"
TASK_DRAWER     = FE / "components" / "tasks" / "TaskDrawer.jsx"
TASK_LISTING    = FE / "components" / "tasks" / "TaskListing.jsx"
TASKS_ROUTER    = BE / "routers" / "tasks.py"
INBOUND_ROUTER  = BE / "routers" / "inbound_email.py"
INVITE_SVC      = BE / "services" / "tasks" / "contributor_invitation_service.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════
# Wire — frontend
# ═════════════════════════════════════════════════════════════════════
def test_f5_contributor_portal_page_exists():
    assert CONTRIB_PORTAL.exists()
    src = _read(CONTRIB_PORTAL)
    # Listens to /contribute/:token via useParams.
    assert "useParams" in src
    assert 'data-testid="contributor-portal"' in src
    # Calls the public endpoints.
    assert "/api/tasks/contribute/" in src
    assert "/upload" in src
    assert "/comment" in src
    assert "/submit" in src


def test_f5_contributor_portal_route_mounted_publicly_in_app_js():
    src = _read(APP_JS)
    assert 'path="/contribute/:token"' in src
    # No <Gated> wrapper — the portal is PUBLIC.
    portal_block = src.split('path="/contribute/:token"')[1].split("/>")[0]
    assert "Gated" not in portal_block
    assert "ContributorPortal" in portal_block


def test_f5_compile_session_pill_on_task_cards():
    """Enhancement #1 — Compile session pill renders on task cards
    when compile_session.active is true."""
    src = _read(TASK_LISTING)
    assert "compile_session?.active" in src
    assert "task-card-compile-pill-${t.id}" in src
    assert "Compile · " in src


def test_f5_needs_your_input_pill_on_task_cards():
    src = _read(TASK_LISTING)
    assert "task-card-needs-your-input-${t.id}" in src
    assert "Needs your input" in src
    # The pill activates for not_started OR in_progress.
    assert '["not_started", "in_progress"]' in src


def test_f5_resume_from_stage_url_param_in_task_drawer():
    """Enhancement #2 — ?compile_stage=<stage> auto-opens Compile tab."""
    src = _read(TASK_DRAWER)
    assert 'params.get("compile_stage")' in src
    # Only activates when the URL param matches the live session stage.
    assert "compileStageParam === sessionStage" in src
    assert 'setTab("compile")' in src


def test_f5_contributions_tab_highlights_your_row_and_has_real_reinvite():
    src = _read(TASK_DRAWER)
    # "Your contribution" label shows on the current-user row.
    assert "task-drawer-contributions-your-row-${i}" in src
    assert "Your contribution" in src
    # Re-invite button calls the real reinvite endpoint, not just a status PATCH.
    assert "/tasks/${task.id}/contributors/${encodeURIComponent(contributorId)}/reinvite" in src


# ═════════════════════════════════════════════════════════════════════
# Wire — backend
# ═════════════════════════════════════════════════════════════════════
def test_f5_invitation_service_has_three_mode_dispatchers():
    src = _read(INVITE_SVC)
    for fn in ("invite_akki_account", "invite_magic_link", "invite_email_reply", "fan_out_invitations"):
        assert f"async def {fn}" in src
    # Token mint helper exists.
    assert "async def mint_contributor_token" in src
    # 30-day default expiry per brief.
    assert "CONTRIB_TOKEN_TTL_DAYS = 30" in src


def test_f5_tasks_router_has_all_contributor_endpoints():
    src = _read(TASKS_ROUTER)
    assert '@router.get("/tasks/contribute/{token}")' in src
    assert '@router.post("/tasks/contribute/{token}/upload")' in src
    assert '@router.post("/tasks/contribute/{token}/comment")' in src
    assert '@router.post("/tasks/contribute/{token}/submit")' in src
    assert '@router.post("/tasks/{task_id}/contributors/{contributor_id}/reinvite")' in src


def test_f5_public_contributor_endpoints_have_no_auth_dependency():
    src = _read(TASKS_ROUTER)
    for path in (
        '/tasks/contribute/{token}")',
        '/tasks/contribute/{token}/upload")',
        '/tasks/contribute/{token}/comment")',
        '/tasks/contribute/{token}/submit")',
    ):
        block = src.split(path)[1].split("@router")[0]
        # No `Depends(get_current_account)` in the signature.
        assert "get_current_account" not in block, f"{path} should be PUBLIC"


def test_f5_inbound_webhook_recognises_task_token_prefix():
    src = _read(INBOUND_ROUTER)
    assert "_handle_task_contributor_reply" in src
    assert 'mailbox_hash.startswith("task-")' in src
    # Strip signature heuristic present.
    assert "_strip_email_signature" in src
    # Submitted_via_email audit fires.
    assert "task.contribution.submitted_via_email" in src
    # Inbound log written.
    assert "task_inbound_emails" in src


def test_f5_signature_stripping_drops_common_quoted_history():
    """The heuristic strips '>' lines, '-- ' sig delimiters, and
    'On <date> wrote:' forwards."""
    src = _read(INBOUND_ROUTER)
    # Extract the def block by start + delimiter to the next async-def.
    body = src.split("def _strip_email_signature(")[1]
    body = "def _strip_email_signature(" + body.split("async def _handle_task_contributor_reply")[0]
    ns: dict = {}
    exec(body, ns)
    strip = ns["_strip_email_signature"]
    sig_body = (
        "Here is my contribution to the board pack.\n"
        "Numbers are reconciled.\n"
        "\n"
        "-- \n"
        "Adel Kareem · CFO\n"
        "Phone: +254 700 000 000\n"
    )
    cleaned = strip(sig_body)
    assert "Here is my contribution" in cleaned
    assert "Adel Kareem" not in cleaned
    assert "+254" not in cleaned
    fwd_body = (
        "Replying with the model attached.\n\n"
        "On Mon, Apr 1 2026 cfo@example.com wrote:\n"
        "> Could you send the model?\n"
    )
    cleaned2 = strip(fwd_body)
    assert "Replying with the model attached." in cleaned2
    assert "Could you send the model?" not in cleaned2


# ═════════════════════════════════════════════════════════════════════
# Live HTTP — Mode 1 + Mode 2 + Re-invite
# ═════════════════════════════════════════════════════════════════════
@pytest.fixture
async def task_owner():
    from core import db, hash_password
    uid = f"test-f5-{uuid.uuid4().hex[:8]}"
    cid = f"ctx-f5-{uuid.uuid4().hex[:8]}"
    email = f"f5-{uuid.uuid4().hex[:6]}@example.com"
    await db.accounts.insert_one({
        "id": uid, "email": email,
        "password_hash": hash_password("Pw!1234567Abc"),
        "name": "F5", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.contexts.insert_one({
        "id": cid, "name": "F5 Co", "owner_account_id": uid,
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
    await db.task_contributor_tokens.delete_many({"task_account_id": uid})
    await db.task_inbound_emails.delete_many({})
    await db.documents.delete_many({"context_id": cid})
    await db.audit_log.delete_many({"account_id": uid})
    await db.memberships.delete_many({"account_id": uid})
    await db.contexts.delete_one({"id": cid})
    await db.accounts.delete_one({"id": uid})


async def _login(c, actor):
    r = await c.post("/api/auth/login",
                     json={"email": actor["email"], "password": actor["password"]})
    token = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_f5_commission_mode1_akki_writes_invited_audit_only(task_owner):
    """Mode 1 (`akki_account`) — invitation fan-out fires; no
    magic-link token is created (the contributor uses their account)."""
    from server import app  # noqa: F401
    from core import db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, task_owner)
        r = await c.post("/api/tasks", json={
            "name": "F.5 Mode1",
            "team": [{"name": "User1", "email": "user1@example.com", "contribution_mode": "akki_account"}],
            "state": "active",
        }, headers=hdr)
        assert r.status_code == 200, r.text
        tid = r.json()["id"]
        # Audit row fired with channel="akki_account".
        row = await db.audit_log.find_one({
            "resource_id": tid, "action": "task.contributor.invited",
            "metadata.contributor_email": "user1@example.com",
        })
        assert row is not None
        assert "akki_account" in (row.get("metadata", {}).get("channels") or [])
        # No magic-link token for this contributor.
        n = await db.task_contributor_tokens.count_documents({"task_id": tid})
        assert n == 0


@pytest.mark.asyncio
async def test_f5_commission_mode2_magic_link_mints_token(task_owner):
    """Mode 2 — magic-link token is minted, persisted, has 30-day expiry."""
    from server import app  # noqa: F401
    from core import db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, task_owner)
        r = await c.post("/api/tasks", json={
            "name": "F.5 Mode2",
            "team": [{"name": "Ext", "email": "ext@external.com", "contribution_mode": "magic_link"}],
            "state": "active",
        }, headers=hdr)
        assert r.status_code == 200, r.text
        tid = r.json()["id"]
        token_row = await db.task_contributor_tokens.find_one({"task_id": tid, "used": False})
        assert token_row is not None
        assert token_row["contributor_email"] == "ext@external.com"
        # 30-day expiry roughly.
        exp = datetime.fromisoformat(token_row["expires_at"].replace("Z", "+00:00"))
        delta_days = (exp - datetime.now(timezone.utc)).days
        assert 28 <= delta_days <= 30


@pytest.mark.asyncio
async def test_f5_mode2_public_endpoints_work_without_auth(task_owner):
    """No Bearer header anywhere — token alone authenticates."""
    from server import app  # noqa: F401
    from core import db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, task_owner)
        r = await c.post("/api/tasks", json={
            "name": "F.5 Mode2 Live",
            "objective": "Demo.",
            "team": [{"name": "Ext", "email": "ext@external.com",
                      "contribution_mode": "magic_link",
                      "contribution": "section a"}],
            "state": "active",
        }, headers=hdr)
        tid = r.json()["id"]
        token_row = await db.task_contributor_tokens.find_one({"task_id": tid, "used": False})
        token = token_row["token"]

        # 1. GET — public landing
        r = await c.get(f"/api/tasks/contribute/{token}")
        assert r.status_code == 200, r.text
        view = r.json()
        assert view["task"]["name"] == "F.5 Mode2 Live"
        assert view["contributor_email"] == "ext@external.com"
        assert view["your_status"] == "not_started"

        # 2. POST upload — multipart
        files = {"file": ("contribution.txt", b"My section content.", "text/plain")}
        r = await c.post(f"/api/tasks/contribute/{token}/upload", files=files)
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        did = r.json()["doc_id"]

        # 3. POST comment
        r = await c.post(f"/api/tasks/contribute/{token}/comment",
                          json={"comment": "I had to assume FX is frozen."})
        assert r.status_code == 200

        # 4. POST submit — flips status
        r = await c.post(f"/api/tasks/contribute/{token}/submit", json={})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        # Status reflected on the task.
        t = await db.tasks.find_one({"id": tid})
        mem = next(m for m in t["team"] if m["email"] == "ext@external.com")
        assert mem["status"] == "submitted"
        # Audit row.
        row = await db.audit_log.find_one({"resource_id": tid, "action": "task.contribution.submitted"})
        assert row is not None
        assert row["metadata"]["via"] == "magic_link"
        # Doc linked to task with contributor_token set.
        d = await db.documents.find_one({"id": did})
        assert d["task_id"] == tid
        assert d["contributor_token"] == token
        assert d["origin"] == "magic_link"


@pytest.mark.asyncio
async def test_f5_expired_token_returns_410(task_owner):
    """A token past its expiry returns 410 Gone, not 404."""
    from server import app  # noqa: F401
    from core import db
    t_id = await _seed_task(db, task_owner)
    expired_token = "expired-" + uuid.uuid4().hex
    await db.task_contributor_tokens.insert_one({
        "id": str(uuid.uuid4()), "token": expired_token,
        "task_id": t_id, "task_account_id": task_owner["uid"],
        "contributor_email": "ext@external.com",
        "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "used": False, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/tasks/contribute/{expired_token}")
        assert r.status_code == 410


@pytest.mark.asyncio
async def test_f5_reinvite_rotates_magic_link_token(task_owner):
    """Re-invite on a magic_link contributor mints a new token AND
    invalidates the old one."""
    from server import app  # noqa: F401
    from core import db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, task_owner)
        r = await c.post("/api/tasks", json={
            "name": "F.5 Reinvite",
            "team": [{"name": "Ext", "email": "ext@external.com", "contribution_mode": "magic_link"}],
            "state": "active",
        }, headers=hdr)
        tid = r.json()["id"]
        old = await db.task_contributor_tokens.find_one({"task_id": tid, "used": False})
        old_token = old["token"]
        # Re-invite.
        r = await c.post(f"/api/tasks/{tid}/contributors/ext@external.com/reinvite", headers=hdr)
        assert r.status_code == 200, r.text
        # Old token should now be marked used; a NEW one is active.
        new = await db.task_contributor_tokens.find_one({"task_id": tid, "used": False})
        old_after = await db.task_contributor_tokens.find_one({"token": old_token})
        assert new is not None
        assert new["token"] != old_token
        assert old_after["used"] is True
        assert old_after.get("revoked_reason") == "rotated_on_reinvite"


@pytest.mark.asyncio
async def test_f5_allow_email_reply_fans_out_two_emails(task_owner):
    """Coexistence — a magic_link contributor with allow_email_reply=True
    gets BOTH an email_reply email AND the magic-link email."""
    from server import app  # noqa: F401
    from core import db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, task_owner)
        r = await c.post("/api/tasks", json={
            "name": "F.5 Coexist",
            "team": [{"name": "Ext", "email": "ext@external.com",
                      "contribution_mode": "magic_link",
                      "allow_email_reply": True}],
            "state": "active",
        }, headers=hdr)
        assert r.status_code == 200, r.text
        tid = r.json()["id"]
        row = await db.audit_log.find_one({
            "resource_id": tid, "action": "task.contributor.invited",
        })
        assert row is not None
        channels = row["metadata"].get("channels") or []
        assert "magic_link" in channels
        assert "email_reply_fallback" in channels


# ═════════════════════════════════════════════════════════════════════
# Live HTTP — Mode 3 (Postmark inbound webhook simulation)
# ═════════════════════════════════════════════════════════════════════
async def _seed_task(db, actor, **overrides):
    tid = f"task-{uuid.uuid4().hex[:12]}"
    base = {
        "id": tid, "account_id": actor["uid"], "context_id": actor["cid"],
        "name": "F.5 Inbound test",
        "team": [{"name": "Ext", "email": "ext@external.com",
                  "contribution_mode": "email_reply", "status": "not_started",
                  "contribution": "Section A"}],
        "state": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    await db.tasks.insert_one(base)
    return tid


@pytest.mark.asyncio
async def test_f5_inbound_webhook_ingests_email_reply(task_owner):
    """Build a SendGrid Inbound Parse multipart payload addressed to
    `task-<token>@inbound.<domain>`. The webhook parses body +
    attachments, creates a document, flips contributor status to
    submitted, fires the submitted_via_email audit."""
    from server import app  # noqa: F401
    from core import db
    import os

    # Seed task + token.
    tid = await _seed_task(db, task_owner)
    token = "f5live" + uuid.uuid4().hex[:18]
    await db.task_contributor_tokens.insert_one({
        "id": str(uuid.uuid4()), "token": token,
        "task_id": tid, "task_account_id": task_owner["uid"],
        "contributor_email": "ext@external.com",
        "contributor_id": "ext@external.com",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "used": False, "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Build SendGrid Inbound Parse multipart form fields.
    inbound_domain = (
        os.environ.get("SENDGRID_INBOUND_DOMAIN")
        or os.environ.get("CYCLE_REPLY_DOMAIN")
        or "akki.syni.ai"
    )
    att_content = b"My section A content. Numbers attached."
    fields = {
        "from":         "Ext User <ext@external.com>",
        "to":           f"task-{token}@{inbound_domain}",
        "subject":      "Re: Action requested — F.5 Inbound test",
        "text":         (
            "Here is my contribution.\n"
            "Numbers reconciled.\n"
            "\n"
            "-- \n"
            "Ext User\n"
            "Phone\n"
        ),
        "html":         "",
        "MessageID":    "msg-" + uuid.uuid4().hex,
        "attachments":  "1",
        "attachment-info": '{"attachment1": {"filename": "section_a.txt", "type": "text/plain"}}',
    }
    files = {
        "attachment1": ("section_a.txt", att_content, "text/plain"),
    }
    # F.6 W1 (2026-05-26) — Basic Auth header for SendGrid inbound
    # endpoint when SENDGRID_INBOUND_AUTH_* env vars are set.
    _auth_user = os.environ.get("SENDGRID_INBOUND_AUTH_USERNAME", "").strip()
    _auth_pw   = os.environ.get("SENDGRID_INBOUND_AUTH_PASSWORD", "").strip()
    _sg_headers = {}
    if _auth_user and _auth_pw:
        _sg_headers["authorization"] = "Basic " + base64.b64encode(
            f"{_auth_user}:{_auth_pw}".encode("utf-8")
        ).decode("ascii")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/inbound/sendgrid", data=fields, files=files, headers=_sg_headers)
        # We accept 200 OR 2xx — depends on the existing webhook's success shape.
        assert r.status_code in (200, 202, 204), r.text
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        # The handler returns `{ok: True, task_id: ..., doc_ids: [...]}`.
        if isinstance(body, dict) and body.get("ok") is True:
            assert body["task_id"] == tid
            assert len(body["doc_ids"]) == 1
    # Side-effects: doc created, status flipped, audit fired.
    d = await db.documents.find_one({"task_id": tid, "origin": "email_receipt"})
    assert d is not None
    assert d["contributor_token"] == token
    assert d["original_filename"] == "section_a.txt"
    assert d["source"]["sender"] == "ext@external.com"
    t = await db.tasks.find_one({"id": tid})
    assert next(m for m in t["team"] if m["email"] == "ext@external.com")["status"] == "submitted"
    audit = await db.audit_log.find_one({"resource_id": tid, "action": "task.contribution.submitted_via_email"})
    assert audit is not None
    # Inbound log row written.
    inbound = await db.task_inbound_emails.find_one({"task_id": tid})
    assert inbound is not None
    assert inbound["parse_status"] == "ingested"
    assert inbound.get("provider") == "sendgrid"


@pytest.mark.asyncio
async def test_f5_inbound_webhook_rejects_sender_mismatch(task_owner):
    """The webhook compares From: against token.contributor_email and
    rejects the mismatch (no doc created, no status flipped, but the
    inbound log row records the rejection for forensics)."""
    from server import app  # noqa: F401
    from core import db
    import os

    tid = await _seed_task(db, task_owner)
    token = "f5sm" + uuid.uuid4().hex[:20]
    await db.task_contributor_tokens.insert_one({
        "id": str(uuid.uuid4()), "token": token,
        "task_id": tid, "task_account_id": task_owner["uid"],
        "contributor_email": "ext@external.com",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "used": False, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    inbound_domain = (
        os.environ.get("SENDGRID_INBOUND_DOMAIN")
        or os.environ.get("CYCLE_REPLY_DOMAIN")
        or "akki.syni.ai"
    )
    fields = {
        "from":      "imposter@bad.com",
        "to":        f"task-{token}@{inbound_domain}",
        "subject":   "Re: Action",
        "text":      "I'm not who you think I am.",
        "html":      "",
        "MessageID": "msg-" + uuid.uuid4().hex,
        "attachments": "0",
    }
    _auth_user = os.environ.get("SENDGRID_INBOUND_AUTH_USERNAME", "").strip()
    _auth_pw   = os.environ.get("SENDGRID_INBOUND_AUTH_PASSWORD", "").strip()
    _sg_headers = {}
    if _auth_user and _auth_pw:
        _sg_headers["authorization"] = "Basic " + base64.b64encode(
            f"{_auth_user}:{_auth_pw}".encode("utf-8")
        ).decode("ascii")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/inbound/sendgrid", data=fields, headers=_sg_headers)
    # No doc created.
    d = await db.documents.find_one({"task_id": tid, "origin": "email_receipt"})
    assert d is None
    # Inbound log records the rejection.
    inbound = await db.task_inbound_emails.find_one({"task_id": tid})
    assert inbound is not None
    assert inbound["parse_status"] == "sender_mismatch"
    assert inbound.get("provider") == "sendgrid"


# ═════════════════════════════════════════════════════════════════════
# F.5 log presence
# ═════════════════════════════════════════════════════════════════════
def test_f5_section_present_in_home_cleanup_log():
    log = (REPO / "memory" / "sprints" / "HOME_CLEANUP_LOG.md").read_text("utf-8")
    assert "F.5" in log and "Contributor" in log
