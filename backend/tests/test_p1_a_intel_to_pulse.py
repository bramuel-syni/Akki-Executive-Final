"""P1-A — Pulse Signals stream surfaces document-level extracted signals.

Spec invariant: when a document has `document_intelligence.key_signals`,
those signals MUST appear on the Pulse Signals feed for the same
context, without requiring the user to click "Generate Brief".

This is enforced by the shared helper
`services.documents.intelligence_service.promote_intelligence_signals_to_pulse`
which runs at two sites:
  • Eager — `routers/documents.py::regenerate_document_intelligence`
    `_run()` background task, immediately after the intelligence
    envelope is written to `document_intelligence`.
  • Lazy — `routers/documents.py::generate_briefing_from_document`
    fallthrough when `db.signals` is empty for the doc.

Both call sites use the SAME stable id scheme
`sig:from_intel:{doc_id}:{idx}` so re-runs are idempotent and the
two paths NEVER produce duplicate rows.

Tests below assert end-to-end on the real Pulse feed endpoint —
`GET /api/contexts/{cid}/pulse/feed` (`routers/pulse.py:177`).
No mocks of the read path. No DOM-presence shortcuts.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import server  # noqa: F401
from server import app


@pytest_asyncio.fixture(scope="module")
async def transport():
    yield ASGITransport(app=app)


async def _csrf_login(client: AsyncClient, *, email: str, password: str) -> Dict[str, str]:
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


async def _seed_account_and_context(db, *, email: str, ctx_name: str = "P1-A Test Context"):
    from core import hash_password
    aid = "acct-p1a-" + uuid.uuid4().hex[:10]
    cid = "ctx-p1a-" + uuid.uuid4().hex[:10]
    now = datetime.now(timezone.utc).isoformat()
    email_lc = email.lower()
    await db.accounts.insert_one({
        "id": aid, "email": email_lc, "email_lc": email_lc,
        "name": "P1-A tester",
        "password_hash": hash_password("P1aTest!"),
        "declared_role": "user",
        "first_session": {"status": "completed", "current_step": "done"},
        "created_at": now,
    })
    await db.contexts.insert_one({
        "id": cid, "name": ctx_name,
        "owner_account_id": aid, "type": "company",
        "created_at": now,
    })
    await db.memberships.insert_one({
        "id": "mem-p1a-" + uuid.uuid4().hex[:10],
        "account_id": aid, "context_id": cid,
        "role": "founder", "sub_role": "owner",
        "status": "active", "created_at": now,
    })
    return aid, cid


async def _seed_doc_with_intel_signals(
    db, *, context_id: str, signals: List[Dict[str, Any]],
) -> str:
    doc_id = "doc-p1a-" + uuid.uuid4().hex[:10]
    now = datetime.now(timezone.utc).isoformat()
    await db.documents.insert_one({
        "id": doc_id, "context_id": context_id,
        "name": "P1-A test document.pdf",
        "extracted_text": "Body content for the P1-A intelligence seed.",
        "created_at": now,
    })
    await db.document_intelligence.insert_one({
        "doc_id": doc_id, "context_id": context_id,
        "doc_hash": "p1a-hash-" + uuid.uuid4().hex[:8],
        "generated_at": now,
        "key_signals": signals,
    })
    return doc_id


# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_promote_helper_writes_pulse_compatible_rows(transport):
    """Direct unit test of the shared helper.

    Promoting 3 key_signals must produce 3 rows in `db.signals`
    whose shape matches what Pulse's serializer reads.
    """
    from core import db
    from services.documents.intelligence_service import (
        promote_intelligence_signals_to_pulse,
    )

    cid = "ctx-p1a-helper-" + uuid.uuid4().hex[:6]
    doc_id = "doc-p1a-helper-" + uuid.uuid4().hex[:6]
    aid = "acct-p1a-helper-" + uuid.uuid4().hex[:6]
    doc = {"id": doc_id, "name": "Helper test doc"}
    sigs = [
        {"type": "risk",        "value": "Q4 forecast slips on capex.",      "source_span": "P3", "confidence": 0.82},
        {"type": "opportunity", "value": "Subscription mix +14% YoY.",        "source_span": "P5", "confidence": 0.71},
        {"type": "kpi",         "value": "Gross margin 38% (was 41%).",       "source_span": "P9", "confidence": 0.55},
    ]
    promoted = await promote_intelligence_signals_to_pulse(
        db, doc=doc, context_id=cid, account_id=aid, key_signals=sigs,
    )
    assert len(promoted) == 3
    for idx, sid in enumerate(promoted):
        assert sid == f"sig:from_intel:{doc_id}:{idx}", promoted

    rows = await db.signals.find(
        {"context_id": cid, "sources.doc_id": doc_id},
        {"_id": 0},
    ).to_list(20)
    assert len(rows) == 3
    by_id = {r["id"]: r for r in rows}
    # Pulse serializer reads: headline, summary, type, confidence,
    # sources, references|sources, state OR status. All present.
    for r in rows:
        assert r["context_id"] == cid
        assert r["promoted_from"] == "document_intelligence"
        assert r["state"] == "active"
        assert r["status"] == "active"
        assert r["headline"], r
        assert r["summary"], r
        assert r["type"] in ("risk", "opportunity", "observation"), r
        assert r["confidence"] in ("high", "medium", "low"), r
        assert r["sources"][0]["doc_id"] == doc_id


@pytest.mark.asyncio
async def test_pulse_feed_surfaces_promoted_intelligence_signals(transport):
    """End-to-end. After promoting, `GET /pulse/feed` must return
    the same N cards with matching headlines.
    """
    from core import db
    from services.documents.intelligence_service import (
        promote_intelligence_signals_to_pulse,
    )

    email = f"p1a-e2e-{uuid.uuid4().hex[:6]}@example.com"
    aid, cid = await _seed_account_and_context(db, email=email)
    doc_id = await _seed_doc_with_intel_signals(db, context_id=cid, signals=[])

    sigs = [
        {"type": "risk",        "value": "Cash runway shrinks by Q3.",   "source_span": "P2", "confidence": "high"},
        {"type": "opportunity", "value": "New region pilot is converting.", "source_span": "P4", "confidence": 0.65},
    ]
    await promote_intelligence_signals_to_pulse(
        db, doc={"id": doc_id, "name": "P1-A E2E doc"},
        context_id=cid, account_id=aid, key_signals=sigs,
    )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login(client, email=email, password="P1aTest!")
        r = await client.get(f"/api/contexts/{cid}/pulse/feed", headers=hdrs)
    assert r.status_code == 200, (r.status_code, r.text)
    body = r.json()
    headlines = [card.get("headline") for card in body.get("cards", [])]
    assert "Cash runway shrinks by Q3." in headlines, headlines
    assert "New region pilot is converting." in headlines, headlines
    # Both cards carry the source doc reference.
    for card in body["cards"]:
        if card["headline"] in (
            "Cash runway shrinks by Q3.",
            "New region pilot is converting.",
        ):
            refs = card.get("references") or []
            assert any(r.get("doc_id") == doc_id for r in refs), card


@pytest.mark.asyncio
async def test_idempotent_no_duplicates_across_callers(transport):
    """Eager + lazy promotion of the same doc must NOT produce
    duplicate rows. Stable id `sig:from_intel:{doc_id}:{idx}` ensures
    the second call upserts in-place.
    """
    from core import db
    from services.documents.intelligence_service import (
        promote_intelligence_signals_to_pulse,
    )

    cid = "ctx-p1a-idem-" + uuid.uuid4().hex[:6]
    doc_id = "doc-p1a-idem-" + uuid.uuid4().hex[:6]
    aid = "acct-p1a-idem-" + uuid.uuid4().hex[:6]
    sigs = [
        {"type": "risk", "value": "Sig A",   "confidence": 0.8},
        {"type": "risk", "value": "Sig B",   "confidence": 0.5},
    ]
    doc = {"id": doc_id, "name": "Idem doc"}

    # First caller (e.g. extraction-time eager promotion).
    p1 = await promote_intelligence_signals_to_pulse(
        db, doc=doc, context_id=cid, account_id=aid, key_signals=sigs,
    )
    assert len(p1) == 2
    # Second caller (e.g. Brief-click lazy promotion).
    p2 = await promote_intelligence_signals_to_pulse(
        db, doc=doc, context_id=cid, account_id=aid, key_signals=sigs,
    )
    assert p1 == p2
    rows = await db.signals.find(
        {"context_id": cid, "sources.doc_id": doc_id},
        {"_id": 0, "id": 1, "created_at": 1},
    ).to_list(10)
    assert len(rows) == 2, f"idempotency violated: got {len(rows)} rows after 2 calls"


@pytest.mark.asyncio
async def test_idempotency_preserves_original_created_at(transport):
    """Re-running promotion must NOT reset `created_at`. Pulse sorts
    by recency, so refreshing the timestamp would silently push old
    signals back to the top on every re-extraction."""
    from core import db
    from services.documents.intelligence_service import (
        promote_intelligence_signals_to_pulse,
    )

    cid = "ctx-p1a-time-" + uuid.uuid4().hex[:6]
    doc_id = "doc-p1a-time-" + uuid.uuid4().hex[:6]
    aid = "acct-p1a-time-" + uuid.uuid4().hex[:6]
    doc = {"id": doc_id, "name": "Time-stamp doc"}
    sigs = [{"type": "risk", "value": "Time invariant test.", "confidence": "high"}]

    await promote_intelligence_signals_to_pulse(
        db, doc=doc, context_id=cid, account_id=aid, key_signals=sigs,
    )
    first_doc = await db.signals.find_one(
        {"id": f"sig:from_intel:{doc_id}:0"}, {"_id": 0, "created_at": 1},
    )
    first_ts = first_doc["created_at"]

    # Wait for clock advance and re-run.
    import asyncio
    await asyncio.sleep(0.05)
    await promote_intelligence_signals_to_pulse(
        db, doc=doc, context_id=cid, account_id=aid, key_signals=sigs,
    )
    second_doc = await db.signals.find_one(
        {"id": f"sig:from_intel:{doc_id}:0"}, {"_id": 0, "created_at": 1},
    )
    assert first_ts == second_doc["created_at"], (
        "created_at mutated on re-run — Pulse recency sort would silently shuffle"
    )


@pytest.mark.asyncio
async def test_tenant_scoping_no_cross_context_leak(transport):
    """Promoting to context A must NOT surface signals in Pulse's
    feed for context B. Pulse filters by `context_id` — assert via
    the live read path, not the write side.
    """
    from core import db
    from services.documents.intelligence_service import (
        promote_intelligence_signals_to_pulse,
    )

    email_a = f"p1a-tenA-{uuid.uuid4().hex[:6]}@example.com"
    aid_a, cid_a = await _seed_account_and_context(db, email=email_a, ctx_name="Context A")
    # Independent tenant B with its own account.
    email_b = f"p1a-tenB-{uuid.uuid4().hex[:6]}@example.com"
    aid_b, cid_b = await _seed_account_and_context(db, email=email_b, ctx_name="Context B")
    doc_id_a = await _seed_doc_with_intel_signals(db, context_id=cid_a, signals=[])

    await promote_intelligence_signals_to_pulse(
        db, doc={"id": doc_id_a, "name": "Context A doc"},
        context_id=cid_a, account_id=aid_a,
        key_signals=[
            {"type": "risk", "value": "TENANT A SECRET SIGNAL", "confidence": "high"},
        ],
    )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login as B; read B's feed.
        hdrs = await _csrf_login(client, email=email_b, password="P1aTest!")
        r = await client.get(f"/api/contexts/{cid_b}/pulse/feed", headers=hdrs)
        assert r.status_code == 200, (r.status_code, r.text)
        headlines_b = [c.get("headline") for c in r.json().get("cards", [])]
        assert "TENANT A SECRET SIGNAL" not in headlines_b, headlines_b
    # And just to prove the seed worked: A still sees its own.
    # Separate AsyncClient (fresh cookie jar) — auth cookies from
    # B's session would otherwise stomp on A's login.
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs_a = await _csrf_login(client, email=email_a, password="P1aTest!")
        r = await client.get(f"/api/contexts/{cid_a}/pulse/feed", headers=hdrs_a)
        assert r.status_code == 200
        headlines_a = [c.get("headline") for c in r.json().get("cards", [])]
        assert "TENANT A SECRET SIGNAL" in headlines_a, headlines_a


@pytest.mark.asyncio
async def test_empty_key_signals_is_noop(transport):
    """Empty input must NOT write anything. Defensive — protects
    against any future caller passing an empty list."""
    from core import db
    from services.documents.intelligence_service import (
        promote_intelligence_signals_to_pulse,
    )
    cid = "ctx-p1a-noop-" + uuid.uuid4().hex[:6]
    doc = {"id": "doc-p1a-noop-" + uuid.uuid4().hex[:6], "name": "Noop"}
    out = await promote_intelligence_signals_to_pulse(
        db, doc=doc, context_id=cid, account_id="acct-noop", key_signals=[],
    )
    assert out == []
    rows = await db.signals.count_documents({"context_id": cid})
    assert rows == 0
