"""Debt closure (W1-W4) wire + live tests — 2026-05-26.

Covers the 4 in-flight workstreams that close out the F.6 batch:

  W1 — SendGrid migration (replaces Postmark)
       - Postmark inbound returns 410 with migration note
       - SendGrid inbound endpoint exists + accepts multipart/form-data
       - SendGrid HTTP Basic Auth enforcement when env vars set
       - email_service routes to SendGrid when SENDGRID_API_KEY set
       - task_inbound_emails rows carry `provider: "sendgrid"`

  W2 — Solva briefing deck fires on URL-driven entry
       - SolvaLanding reads `?submodule=` and auto-opens the deck
       - The route preserves URL params on close → phase-d/session/new

  W3 — Related-docs typing (explicit attachment + canonical lineage)
       - `document_attachments` collection + POST/DELETE endpoints
       - `documents.parent_doc_id` lineage walk (ancestors + descendants)
       - content_similarity gap_reason references Phase G

  W4 — Inline-comment span resolution on circulation comments
       - POST /api/tasks/circulation/{token}/comment accepts `span`
       - span persists with start/end/text
       - frontend TaskDrawer renders span quote above comment
"""
from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
FE   = REPO / "frontend" / "src"
BE   = REPO / "backend"

INBOUND_ROUTER  = BE / "routers" / "inbound_email.py"
DOCUMENTS_ROUTER = BE / "routers" / "documents.py"
TASKS_ROUTER    = BE / "routers" / "tasks.py"
COMPILE_SVC     = BE / "services" / "tasks" / "compile_service.py"
EMAIL_SVC       = BE / "email_service.py"
CONTRIB_SVC     = BE / "services" / "tasks" / "contributor_invitation_service.py"

SOLVA_LANDING   = FE / "components" / "solva" / "SolvaLanding.jsx"
DOC_DRAWER      = FE / "components" / "documents" / "DocumentDrawer.jsx"
TASK_DRAWER     = FE / "components" / "tasks" / "TaskDrawer.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════
# W1 — SendGrid migration
# ═════════════════════════════════════════════════════════════════════
def test_w1_inbound_router_defines_sendgrid_endpoint():
    src = _read(INBOUND_ROUTER)
    assert '@router.post("/sendgrid")' in src
    assert "async def receive_sendgrid_inbound" in src
    # SendGrid multipart adapter helper.
    assert "async def _sendgrid_form_to_payload" in src
    # Provider-agnostic dispatcher extracted out of the legacy handler.
    assert "async def _dispatch_inbound_payload" in src


def test_w1_postmark_inbound_returns_410_with_migration_note():
    src = _read(INBOUND_ROUTER)
    # The Postmark route still exists but returns 410.
    block = src.split('@router.post("/postmark")')[1].split("\nasync def _dispatch_inbound_payload")[0]
    assert "status_code=410" in block
    assert "endpoint_retired" in block
    assert "migration" in block
    # Refers user to SendGrid Inbound Parse.
    assert "sendgrid" in block.lower()


def test_w1_email_service_supports_sendgrid_provider():
    src = _read(EMAIL_SVC)
    # Provider selection function + SendGrid send helper present.
    assert "def _provider()" in src
    assert "_sendgrid_send" in src
    assert "SENDGRID_API_KEY" in src
    assert "SENDGRID_FROM_EMAIL" in src
    # Resend retained as legacy fallback.
    assert "import resend" in src


def test_w1_contributor_service_uses_inbound_domain_env():
    src = _read(CONTRIB_SVC)
    # SendGrid Inbound Parse domain env var is the preferred reader.
    assert "SENDGRID_INBOUND_DOMAIN" in src
    # Reply-to format still task-<token>@<domain>.
    assert 'f"task-{token}@{_INBOUND_DOMAIN}"' in src


def test_w1_requirements_includes_sendgrid():
    req = (BE / "requirements.txt").read_text("utf-8")
    assert "sendgrid==" in req


@pytest.mark.asyncio
async def test_w1_postmark_endpoint_live_returns_410():
    """Live HTTP: POST to /api/inbound/postmark must return 410 with
    the migration-note body."""
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/inbound/postmark", json={"test": "ignored"})
    assert r.status_code == 410, r.text
    body = r.json()
    assert body.get("ok") is False
    assert body.get("error") == "endpoint_retired"
    assert body.get("migration", {}).get("to", "").endswith("/api/inbound/sendgrid (SendGrid Inbound Parse multipart/form-data)")


@pytest.mark.asyncio
async def test_w1_sendgrid_endpoint_accepts_multipart_and_routes_dispatch(monkeypatch):
    """Live HTTP: SendGrid endpoint accepts multipart/form-data with
    `to`, `from`, `subject`, `text`, attachments and dispatches via
    the internal worker. Send a payload addressed to an unknown
    `task-<token>` so the handler returns ok=False (token unknown)
    but proves the multipart adapter + dispatch chain works."""
    from server import app  # noqa: F401
    from core import db

    inbound_domain = (
        os.environ.get("SENDGRID_INBOUND_DOMAIN")
        or os.environ.get("CYCLE_REPLY_DOMAIN")
        or "akki.syni.ai"
    )
    bogus_token = "w1bogus" + uuid.uuid4().hex[:16]
    fields = {
        "from":      "alien@nowhere.test",
        "to":        f"task-{bogus_token}@{inbound_domain}",
        "subject":   "Re: W1 test",
        "text":      "hi",
        "html":      "",
        "attachments": "0",
    }
    # F.6 W1 — Basic Auth header when configured.
    _auth_user = os.environ.get("SENDGRID_INBOUND_AUTH_USERNAME", "").strip()
    _auth_pw   = os.environ.get("SENDGRID_INBOUND_AUTH_PASSWORD", "").strip()
    _sg_headers = {}
    if _auth_user and _auth_pw:
        _sg_headers["authorization"] = "Basic " + base64.b64encode(
            f"{_auth_user}:{_auth_pw}".encode("utf-8")
        ).decode("ascii")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/inbound/sendgrid", data=fields, headers=_sg_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    # Token doesn't exist → error surface honestly.
    assert body.get("ok") is False
    assert body.get("error") == "token_unknown_or_expired"
    # Forensic row written with provider=sendgrid.
    inb = await db.task_inbound_emails.find_one(
        {"parse_status": "token_unknown_or_expired", "from": "alien@nowhere.test"},
        sort=[("received_at", -1)],
    )
    assert inb is not None
    assert inb.get("provider") == "sendgrid"


@pytest.mark.asyncio
async def test_w1_sendgrid_endpoint_enforces_basic_auth_when_configured(monkeypatch):
    """When SENDGRID_INBOUND_AUTH_USERNAME + PASSWORD are set, the
    endpoint requires matching Basic auth and rejects mismatches."""
    from server import app  # noqa: F401
    monkeypatch.setenv("SENDGRID_INBOUND_AUTH_USERNAME", "sg-user")
    monkeypatch.setenv("SENDGRID_INBOUND_AUTH_PASSWORD", "sg-pass-123")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Wrong credentials → 401.
        bad = base64.b64encode(b"sg-user:wrong-pw").decode("ascii")
        r = await c.post(
            "/api/inbound/sendgrid",
            data={"to": "x@y.com", "from": "x@y.com", "subject": "x",
                  "text": "", "html": "", "attachments": "0"},
            headers={"authorization": f"Basic {bad}"},
        )
        assert r.status_code == 401
        # Correct credentials → 200 (token-unknown but adapter ran).
        good = base64.b64encode(b"sg-user:sg-pass-123").decode("ascii")
        r = await c.post(
            "/api/inbound/sendgrid",
            data={"to": "task-nope@whatever", "from": "x@y.com",
                  "subject": "x", "text": "", "html": "", "attachments": "0"},
            headers={"authorization": f"Basic {good}"},
        )
        assert r.status_code == 200


# ═════════════════════════════════════════════════════════════════════
# W2 — Solva briefing deck on task surfaces
# ═════════════════════════════════════════════════════════════════════
def test_w2_solva_landing_reads_url_submodule_on_mount():
    """SolvaLanding has an effect on mount that reads `?submodule=`
    from the URL, looks up the area via SUBMODULE_TO_AREA, and opens
    the briefing deck."""
    src = _read(SOLVA_LANDING)
    assert "useLocation" in src
    # The W2 marker comment is present.
    assert "F.6 W2" in src
    # The effect reads the submodule URL param.
    assert 'sp.get("submodule")' in src
    # And resolves it to a briefing area + opens the deck.
    assert "SUBMODULE_TO_AREA[submodule]" in src
    assert "setBriefingOpen(true)" in src
    # On close it routes to phase-d/session/new preserving the URL search.
    assert "/app/solva/phase-d/session/new${card.__urlSearch}" in src


# ═════════════════════════════════════════════════════════════════════
# W3 — Related-docs typing (explicit attachment + canonical lineage)
# ═════════════════════════════════════════════════════════════════════
def test_w3_documents_router_defines_attachment_endpoints():
    src = _read(DOCUMENTS_ROUTER)
    assert '@router.post("/documents/{doc_id}/attachments")' in src
    assert '@router.delete("/documents/{doc_id}/attachments/{attachment_id}")' in src
    assert "document_attachments" in src
    assert "AttachmentCreateBody" in src


def test_w3_documents_router_defines_lineage_endpoint():
    src = _read(DOCUMENTS_ROUTER)
    assert '@router.patch("/documents/{doc_id}/lineage")' in src
    assert "parent_doc_id" in src
    assert "version_label" in src
    # Cycle-detection on parent assignment.
    assert "lineage cycle detected" in src


def test_w3_related_endpoint_flips_gaps_to_available():
    src = _read(DOCUMENTS_ROUTER)
    block = src.split("async def list_related_documents(")[1].split("\n\n\n")[0]
    # explicit_attachment + canonical_lineage are no longer marked
    # `available: False`. content_similarity IS the remaining gap.
    assert '"explicit_attachment":  {"available": True' in block
    assert '"canonical_lineage":    {"available": True' in block
    assert '"content_similarity":   {"available": False' in block
    assert "Phase G" in block


def test_w3_documentdrawer_renders_attach_affordance():
    src = _read(DOC_DRAWER)
    # Inline form for creating attachments.
    assert 'data-testid="drawer-related-attach-open"' in src
    assert 'data-testid="drawer-related-attach-target-input"' in src
    assert 'data-testid="drawer-related-attach-submit"' in src
    assert 'data-testid="drawer-related-attach-cancel"' in src
    # Group order: metadata_match first, content_similarity last.
    assert (
        '"metadata_match", "explicit_attachment",' in src
        and '"canonical_lineage", "content_similarity"' in src
    )


@pytest.fixture
async def w3_actor():
    from core import db, hash_password
    uid = f"test-w3-{uuid.uuid4().hex[:8]}"
    email = f"w3-{uuid.uuid4().hex[:6]}@example.com"
    pw = "Pw!1234567Abc"
    await db.accounts.insert_one({
        "id": uid, "email": email,
        "password_hash": hash_password(pw),
        "name": "W3", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    cid = f"ctx-w3-{uuid.uuid4().hex[:8]}"
    await db.contexts.insert_one({
        "id": cid, "name": "W3 ctx", "owner_account_id": uid,
        "type": "executive_personal",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.memberships.insert_one({
        "id": f"mem-w3-{uuid.uuid4().hex[:8]}",
        "account_id": uid, "context_id": cid,
        "role": "executive", "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"uid": uid, "email": email, "password": pw, "cid": cid}
    await db.memberships.delete_many({"account_id": uid})
    await db.contexts.delete_one({"id": cid})
    await db.documents.delete_many({"context_id": cid})
    await db.document_attachments.delete_many(
        {"$or": [{"source_doc_id": {"$regex": "^doc-w3-"}}, {"target_doc_id": {"$regex": "^doc-w3-"}}]}
    )
    await db.accounts.delete_one({"id": uid})


async def _login(c, actor):
    r = await c.post("/api/auth/login",
                     json={"email": actor["email"], "password": actor["password"]})
    token = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {token}", "X-Active-Context": actor["cid"]}


@pytest.mark.asyncio
async def test_w3_explicit_attachment_create_persists_and_surfaces_in_related(w3_actor):
    """Create an attachment via POST and verify it surfaces in the
    Related endpoint with the correct directionality + note."""
    from server import app  # noqa: F401
    from core import db
    d_src = f"doc-w3-src-{uuid.uuid4().hex[:8]}"
    d_tgt = f"doc-w3-tgt-{uuid.uuid4().hex[:8]}"
    for did in (d_src, d_tgt):
        await db.documents.insert_one({
            "id": did, "context_id": w3_actor["cid"],
            "name": f"Doc {did[-4:]}", "doc_type": "memo",
            "status": "ready",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, w3_actor)
        r = await c.post(
            f"/api/documents/{d_src}/attachments",
            json={"target_doc_id": d_tgt, "note": "primary reference"},
            headers=hdr,
        )
        assert r.status_code == 200, r.text
        att = r.json()
        assert att["source_doc_id"] == d_src
        assert att["target_doc_id"] == d_tgt
        assert att["note"] == "primary reference"

        # Related endpoint surfaces it on the source side.
        r = await c.get(
            f"/api/contexts/{w3_actor['cid']}/documents/{d_src}/related",
            headers=hdr,
        )
        assert r.status_code == 200, r.text
        groups = r.json()["groups"]
        assert groups["explicit_attachment"]["available"] is True
        items = groups["explicit_attachment"]["items"]
        assert any(i["id"] == d_tgt and i["note"] == "primary reference"
                   and i["direction"] == "outgoing" for i in items)

        # Surfaces symmetrically on the target side.
        r = await c.get(
            f"/api/contexts/{w3_actor['cid']}/documents/{d_tgt}/related",
            headers=hdr,
        )
        items = r.json()["groups"]["explicit_attachment"]["items"]
        assert any(i["id"] == d_src and i["direction"] == "incoming" for i in items)


@pytest.mark.asyncio
async def test_w3_canonical_lineage_walks_ancestors_and_descendants(w3_actor):
    """Build doc-A → doc-B → doc-C via parent_doc_id and verify the
    lineage walk surfaces ancestors of C and descendants of A."""
    from server import app  # noqa: F401
    from core import db
    a = f"doc-w3-A-{uuid.uuid4().hex[:8]}"
    b = f"doc-w3-B-{uuid.uuid4().hex[:8]}"
    c_doc = f"doc-w3-C-{uuid.uuid4().hex[:8]}"
    await db.documents.insert_one({
        "id": a, "context_id": w3_actor["cid"], "name": "A v1",
        "doc_type": "memo", "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.documents.insert_one({
        "id": b, "context_id": w3_actor["cid"], "name": "B v2",
        "doc_type": "memo", "status": "ready", "parent_doc_id": a,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.documents.insert_one({
        "id": c_doc, "context_id": w3_actor["cid"], "name": "C v3",
        "doc_type": "memo", "status": "ready", "parent_doc_id": b,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, w3_actor)
        # Ancestors of C → B then A.
        r = await c.get(
            f"/api/contexts/{w3_actor['cid']}/documents/{c_doc}/related",
            headers=hdr,
        )
        items = r.json()["groups"]["canonical_lineage"]["items"]
        anc_ids = [i["id"] for i in items if i.get("lineage") == "ancestor"]
        assert anc_ids[:2] == [b, a]
        # Descendants of A → B (depth=1; deeper descendants out of scope).
        r = await c.get(
            f"/api/contexts/{w3_actor['cid']}/documents/{a}/related",
            headers=hdr,
        )
        items = r.json()["groups"]["canonical_lineage"]["items"]
        desc_ids = [i["id"] for i in items if i.get("lineage") == "descendant"]
        assert b in desc_ids


@pytest.mark.asyncio
async def test_w3_lineage_patch_endpoint_rejects_self_parent_and_cycles(w3_actor):
    """PATCH /lineage rejects self-parent and ancestor-as-parent."""
    from server import app  # noqa: F401
    from core import db
    a = f"doc-w3-A-{uuid.uuid4().hex[:8]}"
    b = f"doc-w3-B-{uuid.uuid4().hex[:8]}"
    await db.documents.insert_one({
        "id": a, "context_id": w3_actor["cid"], "name": "A",
        "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.documents.insert_one({
        "id": b, "context_id": w3_actor["cid"], "name": "B", "parent_doc_id": a,
        "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, w3_actor)
        # Self-parent → 400.
        r = await c.patch(f"/api/documents/{a}/lineage",
                          json={"parent_doc_id": a}, headers=hdr)
        assert r.status_code == 400
        # Cycle (A.parent = B, but B.parent = A) → 400.
        r = await c.patch(f"/api/documents/{a}/lineage",
                          json={"parent_doc_id": b}, headers=hdr)
        assert r.status_code == 400


# ═════════════════════════════════════════════════════════════════════
# W4 — Inline-comment span resolution
# ═════════════════════════════════════════════════════════════════════
def test_w4_tasks_router_circulation_comment_accepts_span():
    src = _read(TASKS_ROUTER)
    # Span model + payload field present.
    assert "class _CirculationSpan" in src
    assert "span:    Optional[_CirculationSpan]" in src
    # Endpoint passes span dict to the service.
    assert "span=span_dict" in src


def test_w4_compile_service_persists_comment_span():
    src = _read(COMPILE_SVC)
    # Service accepts `span` kwarg and merges into the comment dict.
    assert "span: Optional[Dict[str, Any]] = None" in src
    assert 'cmt["span"]' in src
    # Audit metadata flags inline.
    assert '"inline": bool(cmt.get("span"))' in src


def test_w4_taskdrawer_renders_span_quote_in_circulation_comments():
    src = _read(TASK_DRAWER)
    # Stage 3 review surface renders the span quote above the comment.
    assert "task-drawer-compile-comment-span-badge-${c.id}" in src
    assert "task-drawer-compile-comment-span-quote-${c.id}" in src


@pytest.fixture
async def w4_actor():
    from core import db, hash_password
    uid = f"test-w4-{uuid.uuid4().hex[:8]}"
    email = f"w4-{uuid.uuid4().hex[:6]}@example.com"
    pw = "Pw!1234567Abc"
    await db.accounts.insert_one({
        "id": uid, "email": email,
        "password_hash": hash_password(pw),
        "name": "W4", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"uid": uid, "email": email, "password": pw}
    await db.tasks.delete_many({"account_id": uid})
    await db.task_circulation_tokens.delete_many({"task_account_id": uid})
    await db.audit_log.delete_many({"account_id": uid})
    await db.accounts.delete_one({"id": uid})


@pytest.mark.asyncio
async def test_w4_circulation_comment_persists_span(w4_actor):
    """Seed a task + circulation token, POST a comment with a span,
    confirm it persists with start/end/text and audit row records
    `inline: true`."""
    from server import app  # noqa: F401
    from core import db

    tid = f"tw4-{uuid.uuid4().hex[:10]}"
    token = "w4tok" + uuid.uuid4().hex[:20]
    await db.tasks.insert_one({
        "id": tid, "account_id": w4_actor["uid"], "name": "W4 task",
        "state": "active",
        "compile_session": {
            "current_stage": "circulation",
            "circulation": {"comments": [], "sent_status": []},
        },
        "team": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.task_circulation_tokens.insert_one({
        "id": str(uuid.uuid4()), "token": token,
        "task_id": tid, "task_account_id": w4_actor["uid"],
        "reviewer_email": "rev@external.test",
        "draft_artefact_ids": [],
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "used": False, "created_at": datetime.now(timezone.utc).isoformat(),
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            f"/api/tasks/circulation/{token}/comment",
            json={
                "comment": "This section needs revision.",
                "span": {"start": 120, "end": 142, "text": "the pricing model is wrong"},
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["inline"] is True

    # Span persisted on the task.
    t = await db.tasks.find_one({"id": tid})
    comments = t["compile_session"]["circulation"]["comments"]
    assert len(comments) == 1
    assert comments[0]["span"] == {"start": 120, "end": 142, "text": "the pricing model is wrong"}

    # Audit row flags inline=true.
    audit = await db.audit_log.find_one({
        "resource_id": tid,
        "action": "task.compile.circulation.comment_received",
    })
    assert audit is not None
    assert audit["metadata"].get("inline") is True


@pytest.mark.asyncio
async def test_w4_circulation_comment_without_span_remains_general(w4_actor):
    """Backwards compat — omit `span` and the comment persists as
    a general / whole-document note. `inline: false` in the response."""
    from server import app  # noqa: F401
    from core import db

    tid = f"tw4g-{uuid.uuid4().hex[:10]}"
    token = "w4gtok" + uuid.uuid4().hex[:20]
    await db.tasks.insert_one({
        "id": tid, "account_id": w4_actor["uid"], "name": "W4 general",
        "state": "active",
        "compile_session": {
            "current_stage": "circulation",
            "circulation": {"comments": [], "sent_status": []},
        },
        "team": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.task_circulation_tokens.insert_one({
        "id": str(uuid.uuid4()), "token": token,
        "task_id": tid, "task_account_id": w4_actor["uid"],
        "reviewer_email": "rev2@external.test",
        "draft_artefact_ids": [],
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "used": False, "created_at": datetime.now(timezone.utc).isoformat(),
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            f"/api/tasks/circulation/{token}/comment",
            json={"comment": "Overall this looks good."},
        )
        assert r.status_code == 200
        assert r.json()["inline"] is False

    t = await db.tasks.find_one({"id": tid})
    comments = t["compile_session"]["circulation"]["comments"]
    assert len(comments) == 1
    assert "span" not in comments[0]


# ═════════════════════════════════════════════════════════════════════
# Doc presence — W5 documentation closures
# ═════════════════════════════════════════════════════════════════════
def test_w5_home_cleanup_log_records_sendgrid_section():
    log = (REPO / "memory" / "sprints" / "HOME_CLEANUP_LOG.md").read_text("utf-8")
    assert "SendGrid" in log
    assert "Debt closure" in log or "W1" in log


def test_w5_home_cleanup_log_tracks_phase_f7_cycles_retirement():
    log = (REPO / "memory" / "sprints" / "HOME_CLEANUP_LOG.md").read_text("utf-8")
    assert "Phase F.7" in log
    assert "cycles" in log.lower() and "retire" in log.lower()


def test_w5_home_cleanup_log_tracks_phase_g_embeddings():
    log = (REPO / "memory" / "sprints" / "HOME_CLEANUP_LOG.md").read_text("utf-8")
    assert "Phase G" in log
    assert "embedding" in log.lower()


def test_w5_autonomous_decisions_log_records_acid_acceptance():
    decisions = (REPO / "memory" / "sprints" / "AUTONOMOUS_DECISIONS_LOG.md").read_text("utf-8")
    assert "ACID" in decisions or "Motor lacks" in decisions
    assert "accepted as production approach" in decisions.lower()


def test_w5_autonomous_decisions_log_records_sendgrid_migration():
    decisions = (REPO / "memory" / "sprints" / "AUTONOMOUS_DECISIONS_LOG.md").read_text("utf-8")
    assert "SendGrid" in decisions
