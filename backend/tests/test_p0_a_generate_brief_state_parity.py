"""P0-A — Generate Brief state-read parity lockdown.

The drawer's Signals tab renders `intel?.key_signals` from
`db.document_intelligence`. The brief-generate endpoint at
`POST /api/contexts/{cid}/documents/{doc_id}/briefings/generate`
historically only filtered `db.signals` by `sources.doc_id`, producing
a stale "No signals to brief on yet for this document" 400 even when
the drawer was rendering signals.

Invariant locked here:

  len(document_intelligence.key_signals) > 0  ⇒
  briefings/generate MUST NOT 400 with `"No signals to brief on yet"`.

The fix promotes `document_intelligence.key_signals` into proper
`db.signals` rows on-demand with stable id
`sig:from_intel:{doc_id}:{idx}` — idempotent across re-clicks.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import server  # noqa: F401
from server import app


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
    r = await client.get("/api/csrf")
    return {"Authorization": f"Bearer {token}",
            "X-CSRF-Token": r.json()["csrf_token"]}


async def _ensure_account_and_context(db, *, email: str):
    """Set up an account + context + active membership the
    `require_context_membership` guard will accept."""
    from core import hash_password
    acct = await db.accounts.find_one({"email": email}, {"_id": 0})
    if not acct:
        acct = {
            "id": "acct-p0a-" + uuid.uuid4().hex[:10],
            "email": email, "name": "P0-A test account",
            "password_hash": hash_password("P0aTest!"),
            "declared_role": "user",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.accounts.insert_one(dict(acct))
    ctx_id = "ctx-p0a-" + uuid.uuid4().hex[:10]
    ctx = {
        "id": ctx_id,
        "name": "P0-A test context",
        "owner_account_id": acct["id"],
        "type": "company",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.contexts.insert_one(dict(ctx))
    await db.memberships.insert_one({
        "id": "mem-p0a-" + uuid.uuid4().hex[:10],
        "account_id": acct["id"],
        "context_id": ctx_id,
        "role": "founder",
        "sub_role": "owner",
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return acct, ctx


# ── Logical assertion: intel.key_signals > 0 ⇒ brief MUST NOT 400 ─


@pytest.mark.asyncio
async def test_brief_generate_falls_through_to_document_intelligence_when_db_signals_empty(transport):
    """Core invariant.

    Seed: 1 doc, 1 `document_intelligence` row with 3 `key_signals`,
    ZERO `db.signals` rows whose `sources.doc_id` matches the doc.

    Assert:
      * Endpoint returns 202 (not 400).
      * Response body carries a `job_id`.
      * `db.signals` now has at least 3 rows with `sources.doc_id ==
        doc_id` and stable id prefix `sig:from_intel:{doc_id}:`.
      * Promotion is idempotent — a second call does NOT duplicate.
    """
    from core import db
    email = f"p0a-fallthrough-{uuid.uuid4().hex[:6]}@example.com"
    acct, ctx = await _ensure_account_and_context(db, email=email)

    doc_id = "doc-p0a-" + uuid.uuid4().hex[:10]
    await db.documents.insert_one({
        "id": doc_id,
        "context_id": ctx["id"],
        "name": "P0-A test document",
        "extracted_text": "Body content for the P0-A intelligence seed.",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.document_intelligence.insert_one({
        "doc_id": doc_id,
        "context_id": ctx["id"],
        "doc_hash": "hash-fallthrough",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "key_signals": [
            {"type": "risk",        "value": "Q4 forecast slips on capex",       "source_span": "P3", "confidence": 0.82},
            {"type": "opportunity", "value": "Subscription mix +14% YoY",         "source_span": "P5", "confidence": 0.71},
            {"type": "gap",         "value": "No mention of regulatory exposure", "source_span": "P9", "confidence": 0.55},
        ],
    })
    # Pre-condition: NO db.signals rows match this doc.
    pre_count = await db.signals.count_documents({
        "context_id": ctx["id"],
        "status": "active",
        "sources.doc_id": doc_id,
    })
    assert pre_count == 0, "test setup error — db.signals already has rows"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login(client, email=email, password="P0aTest!")
        r = await client.post(
            f"/api/contexts/{ctx['id']}/documents/{doc_id}/briefings/generate",
            headers=hdrs,
        )

    # Invariant 1 — must NOT 400.
    assert r.status_code != 400, (
        f"brief-generate 400 despite document_intelligence having "
        f"key_signals: {r.status_code} {r.text}"
    )
    # Invariant 2 — must return 202 with job_id.
    assert r.status_code == 202, (r.status_code, r.text)
    body = r.json()
    assert body.get("job_id"), body

    # Invariant 3 — db.signals NOW has the promoted rows.
    promoted = await db.signals.find(
        {
            "context_id": ctx["id"],
            "status": "active",
            "sources.doc_id": doc_id,
        },
        {"_id": 0, "id": 1, "type": 1, "headline": 1, "promoted_from": 1},
    ).to_list(20)
    assert len(promoted) == 3, promoted
    for p in promoted:
        assert p["id"].startswith(f"sig:from_intel:{doc_id}:"), p
        assert p.get("promoted_from") == "document_intelligence", p

    # Invariant 4 — idempotency. Re-invoking does not duplicate.
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login(client, email=email, password="P0aTest!")
        r2 = await client.post(
            f"/api/contexts/{ctx['id']}/documents/{doc_id}/briefings/generate",
            headers=hdrs,
        )
    assert r2.status_code == 202, (r2.status_code, r2.text)
    post_count = await db.signals.count_documents({
        "context_id": ctx["id"],
        "status": "active",
        "sources.doc_id": doc_id,
    })
    assert post_count == 3, f"idempotency violated: {post_count} rows after re-invoke"


@pytest.mark.asyncio
async def test_brief_generate_still_400s_when_intelligence_and_db_signals_both_empty(transport):
    """The fallthrough must NOT mask the genuine-zero case.

    Seed: 1 doc, NO document_intelligence row, NO db.signals.
    Assert: endpoint still returns 400 with the existing copy.
    """
    from core import db
    email = f"p0a-empty-{uuid.uuid4().hex[:6]}@example.com"
    acct, ctx = await _ensure_account_and_context(db, email=email)
    doc_id = "doc-p0a-empty-" + uuid.uuid4().hex[:10]
    await db.documents.insert_one({
        "id": doc_id,
        "context_id": ctx["id"],
        "name": "P0-A empty doc",
        "extracted_text": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login(client, email=email, password="P0aTest!")
        r = await client.post(
            f"/api/contexts/{ctx['id']}/documents/{doc_id}/briefings/generate",
            headers=hdrs,
        )
    assert r.status_code == 400, (r.status_code, r.text)
    detail = (r.json().get("detail") or "")
    assert "No signals to brief on yet" in detail, detail


@pytest.mark.asyncio
async def test_brief_generate_uses_existing_db_signals_when_present(transport):
    """When `db.signals` already has rows matching `sources.doc_id`,
    do NOT promote intelligence — preserve the pre-existing path."""
    from core import db
    email = f"p0a-existing-{uuid.uuid4().hex[:6]}@example.com"
    acct, ctx = await _ensure_account_and_context(db, email=email)
    doc_id = "doc-p0a-existing-" + uuid.uuid4().hex[:10]
    await db.documents.insert_one({
        "id": doc_id,
        "context_id": ctx["id"],
        "name": "P0-A existing-signals doc",
        "extracted_text": "Body.",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # Pre-existing workspace signal scoped to this doc.
    sig_id = "sig-p0a-existing-" + uuid.uuid4().hex[:10]
    await db.signals.insert_one({
        "id": sig_id,
        "context_id": ctx["id"],
        "type": "risk",
        "headline": "Existing signal",
        "summary": "Existing signal body",
        "confidence": "high",
        "sources": [{"doc_id": doc_id, "doc_name": "P0-A existing-signals doc", "data_trust": "verified"}],
        "references": [],
        "data_trust": "verified",
        "generated_by": acct["id"],
        "state": "active", "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # Plus intelligence too — to prove we PREFER the existing.
    await db.document_intelligence.insert_one({
        "doc_id": doc_id,
        "context_id": ctx["id"],
        "doc_hash": "hash-existing",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "key_signals": [
            {"type": "risk", "value": "Should NOT be promoted", "source_span": "P1", "confidence": 0.9},
        ],
    })

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login(client, email=email, password="P0aTest!")
        r = await client.post(
            f"/api/contexts/{ctx['id']}/documents/{doc_id}/briefings/generate",
            headers=hdrs,
        )
    assert r.status_code == 202, (r.status_code, r.text)
    # Verify NO promotion happened — only the original signal exists.
    rows = await db.signals.find(
        {"context_id": ctx["id"], "sources.doc_id": doc_id},
        {"_id": 0, "id": 1, "promoted_from": 1},
    ).to_list(10)
    ids = [r["id"] for r in rows]
    assert sig_id in ids
    promoted = [r for r in rows if r.get("promoted_from") == "document_intelligence"]
    assert promoted == [], f"intelligence should NOT have been promoted: {promoted}"
