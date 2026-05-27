"""Two surgical bugfixes shipped 2026-05-27. CI guards locked here.

BUG #1 — work_studio_exports.id vs documents.id mismatch
  When a Work Studio "exported artefact" card was opened via the
  Universal Document Drawer's `?doc_id=` URL contract, the
  `GET /contexts/{cid}/documents/{doc_id}` endpoint 404'd because the
  id came from `work_studio_exports`, not `documents`. Only 18 of 391
  exports had a `documents` mirror (created by the Continue-in-chat
  flow at work_studio_export.py:941, back-ref via
  `documents.work_studio_export_id`). The fix adds a resolver chain
  inside the GET endpoint:
    (1) Direct hit on `documents.id`.
    (2) Reverse-lookup via `documents.work_studio_export_id`.
    (3) Synthesise a documents-shaped payload from `work_studio_exports`.

BUG #2 — Quartz Africa + East African RSS 403s (Cloudflare block)
  Two tier-1 Africa feeds in `data/news_sources.json` were returning
  403 on every fetch from inside the pod. Fix:
    - Set `enabled: false` on `quartz-africa` + `the-east-african`.
    - Add `capital-fm-business` as replacement (verified HTTP 200,
      valid RSS, 10 items, on a probe fetch before commit).
    - `citizen-digital` was specified in the brief but has NO working
      RSS feed (all URL variants 500 or return HTML); flagged to user.

Locks:
  B1.a — resolver chain present at line of `get_document_detail`
  B1.b — `_synthesize_doc_from_export` helper exists + carries
         the required fields the Drawer reads
  B1.c — live integration: a `work_studio_exports` row opened via
         GET `/documents/{export_id}` returns 200 with synthesised shape
  B1.d — live integration: an export with a documents mirror returns
         the mirror's payload (not the synthesis)
  B1.e — live integration: an unknown id still returns 404

  B2.a — `quartz-africa` is enabled=false
  B2.b — `the-east-african` is enabled=false
  B2.c — `capital-fm-business` is present + enabled=true + uses
         the verified URL
  B2.d — `load_sources()` filters out the disabled entries
  B2.e — Enabled count is exactly 14 (was 16, -2 disabled, +1 added,
         original count -1 — locks the math)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
DOCUMENTS_PY = REPO / "backend" / "routers" / "documents.py"
NEWS_SOURCES = REPO / "backend" / "data" / "news_sources.json"


# ═════════════════════════════════════════════════════════════════════
# BUG #1 — work_studio_exports resolver
# ═════════════════════════════════════════════════════════════════════

def test_bug1_B1a_resolver_chain_present_in_get_endpoint():
    """Source-strict guard: the GET endpoint must contain all 3 lookup
    paths (direct doc id, reverse-lookup via work_studio_export_id,
    synthesis from work_studio_exports)."""
    src = DOCUMENTS_PY.read_text(encoding="utf-8")
    # Direct find_one on documents
    assert 'db.documents.find_one' in src
    # Reverse-lookup branch
    assert '"work_studio_export_id": doc_id' in src, (
        "Resolver must reverse-lookup via documents.work_studio_export_id"
    )
    # Synthesis branch
    assert "db.work_studio_exports.find_one" in src
    assert "_synthesize_doc_from_export" in src, (
        "Synthesis helper must be invoked from the resolver"
    )


def test_bug1_B1b_synthesize_helper_returns_required_fields():
    """The synthesised payload must carry every field the Universal
    Document Drawer reads. Run the helper against a hand-rolled row
    and assert shape."""
    from routers.documents import _synthesize_doc_from_export
    row = {
        "id": "exp-test-1",
        "context_id": "ctx-1",
        "account_id": "acc-1",
        "kind": "report",
        "output_format": "docx",
        "status": "complete",
        "structured_content": {
            "title": "Q3 risk posture",
            "sections": [
                {"heading": "Summary", "body": "Three risks tracked."},
            ],
        },
        "file_name": "q3-risk-posture.docx",
        "sensitivity_band": "internal",
        "created_at": "2026-01-01T00:00:00+00:00",
        "completed_at": "2026-01-01T00:01:00+00:00",
        "lifecycle_state": "committed",
        "description_chars": 5, "objective_chars": 10, "scope_chars": 15,
    }
    out = _synthesize_doc_from_export(row)
    # Identity + URL contract
    assert out["id"] == "exp-test-1"
    assert out["context_id"] == "ctx-1"
    # Title resolution prefers structured_content.title
    assert out["name"] == "Q3 risk posture"
    # Drawer-critical fields
    assert out["doc_type"] == "work_studio_artefact"
    assert out["state"] == "committed"
    assert out["origin"] == "akki_generated"
    assert "Summary" in out["extracted_text"]
    assert "Three risks tracked." in out["extracted_text"]
    assert out["work_studio_export_id"] == "exp-test-1"
    assert out["_synthesized_from"] == "work_studio_export"
    # Mime type derived from output_format
    assert out["mime_type"].startswith("application/vnd.openxmlformats-officedocument.wordprocessingml")
    # Sensitivity surfaced
    assert out["sensitivity_band"] == "internal"
    assert out["sensitivity_label"] == "INTERNAL"


def test_bug1_B1b_synthesize_helper_fallback_title():
    """When structured_content has no title, fall back to file_name
    (stripped of extension) → kind-derived label."""
    from routers.documents import _synthesize_doc_from_export
    out = _synthesize_doc_from_export({
        "id": "x", "context_id": "c", "kind": "minutes", "output_format": "pdf",
        "structured_content": None, "file_name": "audit-2025-meeting.pdf",
        "lifecycle_state": "draft",
    })
    assert out["name"] == "audit-2025-meeting"
    assert out["state"] == "draft"

    out2 = _synthesize_doc_from_export({
        "id": "y", "context_id": "c", "kind": "deck", "output_format": "pptx",
        "structured_content": None, "file_name": None,
    })
    assert out2["name"] == "Deck"  # kind-derived ("deck" → "Deck")


# ─────────────────────────────────────────────────────────────────────
# Live integration tests for the resolver chain
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
async def bug1_actor():
    from core import db, hash_password
    uid = f"bug1-{uuid.uuid4().hex[:8]}"
    email = f"bug1-{uuid.uuid4().hex[:6]}@ex.com"
    pw = "Bug1!1234567Pw"
    cid = f"bug1-ctx-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.accounts.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(pw),
        "name": "Bug1 Tester", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False, "created_at": now_iso,
    })
    await db.contexts.insert_one({
        "id": cid, "name": "Bug1 Co", "owner_account_id": uid,
        "context_status": "active", "industry": "tech", "created_at": now_iso,
    })
    await db.memberships.insert_one({
        "id": f"m-{uuid.uuid4().hex[:8]}", "account_id": uid, "context_id": cid,
        "role": "owner", "status": "active", "created_at": now_iso,
    })
    yield {"uid": uid, "email": email, "password": pw, "cid": cid}
    await db.accounts.delete_one({"id": uid})
    await db.contexts.delete_one({"id": cid})
    await db.memberships.delete_many({"account_id": uid})


async def _login(client, email, password):
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_bug1_B1c_live_export_no_mirror_returns_synthesis(bug1_actor):
    """Live integration: seed a work_studio_exports row with NO
    documents mirror, GET /documents/{export_id} → 200 + synthesised
    shape carrying `_synthesized_from`."""
    from core import db
    from server import app  # noqa: F401
    export_id = f"exp-{uuid.uuid4().hex[:8]}"
    await db.work_studio_exports.insert_one({
        "id":              export_id,
        "context_id":      bug1_actor["cid"],
        "account_id":      bug1_actor["uid"],
        "kind":            "report",
        "output_format":   "docx",
        "status":          "complete",
        "structured_content": {"title": "Bug1 test report",
                               "sections": [{"heading": "S1", "body": "body of section."}]},
        "lifecycle_state": "committed",
        "created_at":      datetime.now(timezone.utc).isoformat(),
        "completed_at":    datetime.now(timezone.utc).isoformat(),
        "sensitivity_band": "internal",
    })
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            tok = await _login(c, bug1_actor["email"], bug1_actor["password"])
            r = await c.get(
                f"/api/contexts/{bug1_actor['cid']}/documents/{export_id}",
                headers={"Authorization": f"Bearer {tok}"},
            )
            assert r.status_code == 200, r.text
            j = r.json()
            assert j["id"] == export_id
            assert j["name"] == "Bug1 test report"
            assert j["_synthesized_from"] == "work_studio_export"
            assert j["work_studio_export_id"] == export_id
            assert j["state"] == "committed"
            assert j["origin"] == "akki_generated"
            assert "body of section" in j.get("extracted_text", "")
    finally:
        await db.work_studio_exports.delete_one({"id": export_id})


@pytest.mark.asyncio
async def test_bug1_B1d_live_export_with_mirror_returns_mirror(bug1_actor):
    """Live integration: seed a work_studio_exports row PLUS a
    documents mirror via back-ref. GET /documents/{export_id} must
    return the MIRROR'S payload (not the synthesis), proving the
    reverse-lookup branch takes priority over synthesis."""
    from core import db
    from server import app  # noqa: F401
    export_id = f"exp-{uuid.uuid4().hex[:8]}"
    doc_id    = f"doc-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.work_studio_exports.insert_one({
        "id": export_id, "context_id": bug1_actor["cid"],
        "account_id": bug1_actor["uid"], "kind": "brief",
        "output_format": "docx", "status": "complete",
        "structured_content": {"title": "Synthesis title (should NOT win)"},
        "lifecycle_state": "committed", "created_at": now_iso,
    })
    await db.documents.insert_one({
        "id": doc_id, "context_id": bug1_actor["cid"],
        "name": "Mirror title (should win)",
        "doc_type": "work_studio_artefact",
        "work_studio_export_id": export_id,
        "status": "extracted", "created_at": now_iso, "updated_at": now_iso,
        "extracted_text": "mirror body", "data_trust": "trusted",
    })
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            tok = await _login(c, bug1_actor["email"], bug1_actor["password"])
            r = await c.get(
                f"/api/contexts/{bug1_actor['cid']}/documents/{export_id}",
                headers={"Authorization": f"Bearer {tok}"},
            )
            assert r.status_code == 200, r.text
            j = r.json()
            assert j["id"] == doc_id, (
                f"Mirror lookup must take priority over synthesis. "
                f"Got id={j.get('id')}, expected {doc_id}"
            )
            assert j["name"] == "Mirror title (should win)"
            assert j.get("_synthesized_from") is None, (
                "Mirror return must NOT carry the synthesis marker"
            )
    finally:
        await db.work_studio_exports.delete_one({"id": export_id})
        await db.documents.delete_one({"id": doc_id})


@pytest.mark.asyncio
async def test_bug1_B1e_unknown_id_still_returns_404(bug1_actor):
    """Regression: an id that's neither a document nor an export still
    returns 404 — resolver chain doesn't silently succeed."""
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login(c, bug1_actor["email"], bug1_actor["password"])
        r = await c.get(
            f"/api/contexts/{bug1_actor['cid']}/documents/no-such-id",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════
# BUG #2 — News feed config (Quartz/EastAfrican 403s)
# ═════════════════════════════════════════════════════════════════════

def _load_sources_raw():
    return json.loads(NEWS_SOURCES.read_text(encoding="utf-8"))


def test_bug2_B2a_quartz_africa_disabled():
    raw = _load_sources_raw()
    src = next((s for s in raw["sources"] if s["id"] == "quartz-africa"), None)
    assert src is not None, "quartz-africa entry must remain in config (disabled, not removed)"
    assert src.get("enabled") is False, "quartz-africa must be enabled:false (Cloudflare 403)"


def test_bug2_B2b_the_east_african_disabled():
    raw = _load_sources_raw()
    src = next((s for s in raw["sources"] if s["id"] == "the-east-african"), None)
    assert src is not None, "the-east-african entry must remain in config (disabled, not removed)"
    assert src.get("enabled") is False, "the-east-african must be enabled:false (Cloudflare 403)"


def test_bug2_B2c_capital_fm_business_present_and_verified():
    raw = _load_sources_raw()
    src = next((s for s in raw["sources"] if s["id"] == "capital-fm-business"), None)
    assert src is not None, "capital-fm-business replacement entry must exist"
    assert src.get("enabled") is True
    assert src["url"] == "https://www.capitalfm.co.ke/business/feed/", (
        "URL must match the verified-200 probe path. If you change this URL, "
        "re-run a probe fetch from inside the pod and update the test."
    )
    assert "KE" in src.get("regions", [])


def test_bug2_B2c2_kbc_business_present_and_verified():
    """User-approved follow-up replacement after Citizen Digital was
    found to have no working RSS endpoint."""
    raw = _load_sources_raw()
    src = next((s for s in raw["sources"] if s["id"] == "kbc-business"), None)
    assert src is not None, "kbc-business follow-up replacement entry must exist"
    assert src.get("enabled") is True
    assert src["url"] == "https://www.kbc.co.ke/category/business/feed/", (
        "URL must match the verified-200 probe path. If you change this URL, "
        "re-run a probe fetch from inside the pod and update the test."
    )
    assert "KE" in src.get("regions", [])


def test_bug2_B2d_load_sources_filters_disabled():
    """The aggregator's loader must exclude the disabled entries."""
    from services.news_aggregator import load_sources
    sources = load_sources()
    ids = [s["id"] for s in sources]
    assert "quartz-africa" not in ids, (
        "load_sources() must filter out enabled:false entries"
    )
    assert "the-east-african" not in ids, (
        "load_sources() must filter out enabled:false entries"
    )
    assert "capital-fm-business" in ids, (
        "Capital FM Business must surface to the aggregator"
    )
    assert "kbc-business" in ids, (
        "KBC Business must surface to the aggregator"
    )


def test_bug2_B2e_enabled_count_locked():
    """Locks the math: 17 total entries, 2 disabled, 15 enabled.
    Original config had 16 entries (15 enabled); the bugfix disabled 2
    and added 2 (capital-fm-business + kbc-business after user approved
    KBC as the second replacement). If this test fails after a future
    config change, update the count explicitly here so the surface is
    intentional."""
    raw = _load_sources_raw()
    total = len(raw["sources"])
    enabled = sum(1 for s in raw["sources"] if s.get("enabled", True))
    assert total == 17, f"Expected 17 total entries; got {total}"
    assert enabled == 15, f"Expected 15 enabled entries; got {enabled}"
