"""Chunk 7 — fixes for the 6 P0 findings from the 16-May QA report.

Regression coverage for:
  · QA-2026-05-16-005 — Add to Cycle Pydantic shape (cycle_manager.ContributionIn)
  · QA-2026-05-16-006 — Take into Solva intake-seed shape (solva_v2.StartV2In)
  · QA-2026-05-16-007 — signals parser robustness against truncated JSON
  · QA-2026-05-16-012 — Archive route (frontend nav target verified server-side
                        via the dedicated `/api/chats/archived` listing surface)
  · QA-2026-05-16-043 — committee_pack accepted as enhance kind
  · QA-2026-05-16-047 — manual obj/proj default = not_started + no-data path

Each test references the spec anchor in `qa_reports/QA_REPORT_16MAY2026.md`.
"""
from __future__ import annotations

import io
import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from server import app


pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────
# Fixtures (ephemeral account + context — matches phase_f1 pattern).
# ─────────────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def db_conn():
    mclient = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mclient[os.environ["DB_NAME"]]
    yield db
    mclient.close()


@pytest_asyncio.fixture
async def client():
    # Mock Shield so we don't burn the LLM budget on parser tests.
    os.environ["SYNISENSE_LLM_MODE"] = "mock"
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.update(saved)


@pytest_asyncio.fixture
async def authed(db_conn):
    suffix = uuid.uuid4().hex[:8]
    email = f"qa7-{suffix}@example.com"
    password = "Chunk7-2026!"
    account_id = f"acc-qa7-{suffix}"
    context_id = f"ctx-qa7-{suffix}"
    from core import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "Chunk7 Probe", "role": "executive", "verified": True,
        "session_version": 0, "created_at": now_iso, "is_superadmin": False,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "Chunk7 Context", "created_at": now_iso,
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}",
        "context_id": context_id, "account_id": account_id,
        "status": "active", "sub_role": "owner", "created_at": now_iso,
    })
    yield {"email": email, "password": password,
           "account_id": account_id, "context_id": context_id}
    await db_conn.accounts.delete_one({"id": account_id})
    await db_conn.contexts.delete_one({"id": context_id})
    await db_conn.memberships.delete_many({"account_id": account_id})
    await db_conn.documents.delete_many({"context_id": context_id})
    await db_conn.objectives.delete_many({"context_id": context_id})
    await db_conn.projects.delete_many({"context_id": context_id})
    await db_conn.cycle_contributions.delete_many({"context_id": context_id})
    await db_conn.cycle_agendas.delete_many({"context_id": context_id})


async def _login(c: AsyncClient, email: str, password: str):
    r = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    token = body.get("access_token") or body.get("token") or body.get("session_token")
    assert token, f"no token in login response: {body!r}"
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-005 — Add to Cycle payload shape
# ─────────────────────────────────────────────────────────────────────
async def test_qa_005_add_to_cycle_accepts_document_kind_without_team_member(
    client, authed,
):
    """Spec anchor: qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-005

    Before: backend `ContributionIn` required `agenda_item_id` AND
    `team_member_id`, and rejected `kind="contribution"`. The Document
    Journal -> Add to Cycle flow doesn't have those at the entry
    point — it errored with HTTP 422.

    After: the schema accepts a minimal doc-attached payload
    {kind:"document", source_doc_id} with agenda_item_id and
    team_member_id both optional.
    """
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    payload = {
        "kind": "document",
        "title": "Chunk 7 regression doc",
        "source_doc_id": str(uuid.uuid4()),
        "body_text": "Pasted body text for the contribution.",
    }
    r = await client.post(
        f"/api/contexts/{cid}/cycle/contributions",
        json=payload, headers=headers,
    )
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["kind"] == "document"
    assert rec["source_doc_id"] == payload["source_doc_id"]
    # agenda_item_id / team_member_id are both None in this minimal flow.
    assert rec.get("agenda_item_id") is None
    assert rec.get("team_member_id") is None


async def test_qa_005_old_buggy_payload_still_rejected_but_with_clear_message(
    client, authed,
):
    """The fix is additive: invalid `kind` values (the original bug
    sent `"contribution"`) MUST still be rejected by Pydantic so we
    don't silently accept garbage. The error must be 422, not 500."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    r = await client.post(
        f"/api/contexts/{cid}/cycle/contributions",
        json={"kind": "contribution", "title": "should fail"},
        headers=headers,
    )
    assert r.status_code == 422, r.text


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-006 — Take into Solva payload shape
# ─────────────────────────────────────────────────────────────────────
async def test_qa_006_take_into_solva_uses_intake_seed_not_attached_document_id(
    client, authed,
):
    """Spec anchor: qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-006

    The DocumentRoutingActions frontend previously sent
    `{submodule, framing_text, attached_document_id}` — none of
    which match the backend `StartV2In` schema. After the Chunk 7
    fix it sends `{submodule, intent, intake_seed:{kind,id}}` which
    is the canonical shape. We assert the canonical shape is
    accepted here so any future regression toward the buggy shape
    fails fast.
    """
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    doc_id = str(uuid.uuid4())
    intent = (
        "Work this question against the uploaded document: what should "
        "a sharp non-executive notice on a careful read?"
    )
    r = await client.post(
        "/api/solva/v2/sessions",
        json={
            "submodule": "seek_clarity",
            "intent": intent,
            "context_id": cid,
            "intake_seed": {"kind": "document", "id": doc_id},
        },
        headers=headers,
    )
    # Acceptable terminal states: 200 (created), or 422 ONLY if the
    # validation message is unrelated to our shape (e.g. an unrelated
    # field default became required). The old buggy shape returned
    # `intent: Field required` — that MUST not happen.
    assert r.status_code in (200, 201), r.text
    if r.status_code in (200, 201):
        body = r.json()
        # Session object lives at top level or under `session`.
        sess = body.get("session") or body
        assert sess.get("id"), body


async def test_qa_006_old_buggy_payload_still_rejected(client, authed):
    """The pre-fix frontend sent `framing_text` + `attached_document_id`
    instead of `intent`/`intake_seed`. Confirm that shape still
    rejects with 422 so a regression to the old payload fails
    cleanly rather than silently dropping the doc anchor."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    r = await client.post(
        "/api/solva/v2/sessions",
        json={
            "submodule": "seek_clarity",
            "framing_text": "no intent field",
            "attached_document_id": "anything",
            "context_id": cid,
        },
        headers=headers,
    )
    assert r.status_code == 422, r.text
    detail = r.json().get("detail") or []
    assert any(
        (isinstance(d, dict) and d.get("loc", [None, None])[-1] == "intent")
        for d in detail
    ), r.text


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-007 — JSON parser robustness (signals)
# ─────────────────────────────────────────────────────────────────────
def test_qa_007_parse_json_response_strips_code_fence_and_trailing_commentary():
    """Spec anchor: qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-007

    Real Claude responses wrap JSON in ```json …``` fences AND
    sometimes add a trailing "Let me know if you need…" line after
    the closing fence. parse_json_response must handle both."""
    from llm_service import parse_json_response
    raw = (
        '```json\n'
        '{"signals":[{"type":"risk","headline":"H","summary":"S",'
        '"confidence":"high","doc_ids":["a"]}]}\n'
        '```\n'
        'Let me know if you would like more detail.'
    )
    parsed = parse_json_response(raw)
    assert isinstance(parsed, dict)
    assert isinstance(parsed["signals"], list)
    assert parsed["signals"][0]["type"] == "risk"


def test_qa_007_parse_json_response_recovers_truncated_array():
    """When the provider hits max_tokens mid-string, we get a
    truncated JSON like `{"signals":[{...complete...},{incomplete...`.
    The recovery path should return the complete signals only, never
    None — that way the user at least sees the signals that DID land
    instead of a generic toast."""
    from llm_service import parse_json_response
    truncated = (
        '```json\n'
        '{"signals":[\n'
        '  {"type":"risk","headline":"Provisioning coverage at 41% '
        'breaches regulatory minimum","summary":"Provisioning '
        'coverage fell to 41% [doc:abc].","confidence":"high",'
        '"doc_ids":["abc"]},\n'
        '  {"type":"gap","headline":"Succession plan missing",'
        '"summary":"No succession plan for the CFO seat'  # truncated
    )
    parsed = parse_json_response(truncated)
    assert isinstance(parsed, dict), f"parser returned {type(parsed).__name__}"
    sigs = parsed.get("signals")
    assert isinstance(sigs, list)
    # We keep only the first (fully balanced) object; the second is
    # truncated mid-string and is discarded.
    assert len(sigs) == 1
    assert sigs[0]["type"] == "risk"
    assert sigs[0]["headline"].startswith("Provisioning coverage")


def test_qa_007_parse_json_response_falls_through_on_total_garbage():
    """If the response is genuinely unparseable (no JSON at all),
    parse_json_response returns None — preserves the existing
    contract for the worker's HTTPException path."""
    from llm_service import parse_json_response
    assert parse_json_response("just some prose, no json here") is None
    assert parse_json_response("") is None
    assert parse_json_response("```json\nthis is not json\n```") is None


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-012 — Archive chat → dedicated page
# ─────────────────────────────────────────────────────────────────────
async def test_qa_012_archived_chats_listing_endpoint_present(client, authed):
    """Spec anchor: qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-012

    The Archive button now navigates to `/app/chats/archived`
    (a frontend route that already exists). The page calls
    `GET /api/chats/archived` to load the list. We verify the
    endpoint exists and returns a list shape so a regression that
    removes the backend support fails this test.
    """
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get("/api/chats/archived", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    # The contract is `{"items": [...]}` (see frontend/pages/ArchivedChats.jsx).
    assert "items" in body, body
    assert isinstance(body["items"], list)


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-043 — committee_pack accepted as enhance kind
# ─────────────────────────────────────────────────────────────────────
def _make_docx_bytes(text: str) -> bytes:
    """Build a real DOCX in-memory."""
    from docx import Document as DocxDocument
    doc = DocxDocument()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


async def test_qa_043_committee_pack_enhance_kind_accepted(client, authed):
    """Spec anchor: qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-043

    Pre-fix: `_ENHANCE_KINDS = ("deck", "report", "minutes")` —
    `committee_pack` returned `400 Unknown enhance kind`. After the
    fix the upload is accepted and a job row exists with the same
    shape as the other kinds.
    """
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    docx = _make_docx_bytes(
        "Audit committee pack — QA Chunk 7 regression.\n"
        "This is the source document used to verify Committee Pack "
        "is now a first-class enhance kind."
    )
    files = {"file": ("source.docx", docx,
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"instructions": "Tighten the wording for the audit committee.",
            "output_format": "auto"}
    r = await client.post(
        f"/api/contexts/{cid}/work-studio/enhance/committee_pack",
        files=files, data=data, headers=headers,
    )
    # Either 200 (kicked off; worker may fail later because of mock LLM,
    # but the kind guard must let us through) or 200 + status="failed"
    # if a downstream guard catches it. The pre-fix behaviour was 400.
    assert r.status_code in (200, 202), r.text
    body = r.json()
    assert body.get("kind") == "committee_pack"


async def test_qa_043_unknown_enhance_kind_still_rejected(client, authed):
    """A genuinely unknown kind must still 400 — the fix didn't open
    the door to arbitrary strings."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    docx = _make_docx_bytes("Test content")
    files = {"file": ("x.docx", docx,
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"instructions": "no-op", "output_format": "auto"}
    r = await client.post(
        f"/api/contexts/{cid}/work-studio/enhance/totally_made_up",
        files=files, data=data, headers=headers,
    )
    assert r.status_code == 400, r.text
    assert "Unknown enhance kind" in r.text


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-047 — Manual obj/proj default status + no-data path
# ─────────────────────────────────────────────────────────────────────
async def test_qa_047_manual_objective_defaults_to_not_started(client, authed):
    """Spec anchor: qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-047

    The pre-fix create modal pushed `rag_status` in {green/amber/red}
    with `amber` as the default — and the backend Pydantic default
    was `green`. The QA report observed the surface render "Off
    Track" (red) at creation, which the spec calls out as a
    misrepresentation of performance.

    After the fix:
      · `rag_status` defaults to `not_started` on the backend.
      · `score` defaults to 0 (not 50 mid-band).
      · `achieved` is also a valid status — Akki may assign it.
    """
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    r = await client.post(
        f"/api/contexts/{cid}/monitor/objective",
        json={"title": "Q3 — improve provisioning coverage to 50%"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    obj = r.json()
    assert obj["rag_status"] == "not_started"
    assert obj["score"] == 0
    assert obj["source"] == "manual"


async def test_qa_047_manual_project_accepts_extended_statuses(client, authed):
    """Either status value `achieved` or `not_started` must round-trip
    through the create endpoint without a Pydantic 422."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    for status in ("not_started", "achieved"):
        r = await client.post(
            f"/api/contexts/{cid}/monitor/project",
            json={"title": f"Test project — {status}", "rag_status": status},
            headers=headers,
        )
        assert r.status_code == 200, f"{status}: {r.text}"
        assert r.json()["rag_status"] == status


async def test_qa_047_update_status_returns_no_data_when_signals_and_docs_empty(
    client, authed,
):
    """When there are no engine signals and no documents for the
    context, update-status MUST return `{no_data: true, message}`
    instead of burning a Shield call and inventing a status. The
    frontend uses this to render the "No relevant documents..."
    copy + Document Journal link."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    # Create a fresh objective with zero signals + zero documents.
    create = await client.post(
        f"/api/contexts/{cid}/monitor/objective",
        json={"title": "Empty-context objective for -047"},
        headers=headers,
    )
    assert create.status_code == 200, create.text
    obj_id = create.json()["id"]

    r = await client.post(
        f"/api/contexts/{cid}/monitor/objective/{obj_id}/update-status",
        json={}, headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("no_data") is True, body
    assert body.get("status") == "no_data"
    assert "no relevant documents or data" in (body.get("message") or "").lower()
