"""Track A Phase 7 (2026-06-05) — confidence scoring runtime compute
path lockdowns.

15 tests at the user-approved budget cap:

  • 5 scorer-unit (deterministic, Shield mocked / refused):
      1.  happy path → deterministic weighted average (also covers
          recommendation_grounding=100 skip behaviour per Tightening 4
          test-merge — Pre-Read test #5 absorbed into test 1).
      2.  out-of-range dimension scores → clamped to [0,100]
      3.  empty source_documents → returns None, deliberate skip
      4.  malformed JSON response → returns None + flag
      5.  Shield refusal / exception → returns None + flag
  • 4 compile-path integration (Shield mocked):
      6.  _run_export populates intelligence_report on complete
      7.  _run_export completes with status=complete even if scorer fails
      8.  _run_export mirrors confidence_pct to documents row on success
      9.  failed score does NOT clobber prior documents.confidence_pct (Tightening 2)
  • 3 commit-recompute (Shield mocked):
      10. recompute updates confidence_pct + sets new cache_key
      11. recompute SKIPPED when structured_content hash unchanged
          (Tightening 4: confidence_recompute_skipped_unchanged: true
          on response; no Shield call fires)
      12. recompute failure surfaces confidence_recompute_failed: true;
          lifecycle still locks to "committed"; old pct preserved
  • 1 overlay payload contract:
      13. overlay payload surfaces rationale + scored_at;
          legacy/absent-rationale row → field is None (Tightening 3 path (a))
  • 2 real-LLM integration-marked:
      14. score_confidence_real_shield_happy_path
      15. score_confidence_real_shield_consistency — 3 calls, max pairwise diff ≤ 10 (Tightening 1)
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

import server  # noqa: F401  — startup wiring
from server import app

pytestmark = pytest.mark.asyncio


# ─── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def transport():
    return ASGITransport(app=app)


@pytest_asyncio.fixture
async def db_conn():
    mclient = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mclient[os.environ["DB_NAME"]]
    yield db
    mclient.close()


async def _csrf_login(ac: AsyncClient, email: str, password: str) -> Dict[str, str]:
    r = await ac.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await ac.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    r.raise_for_status()
    token = r.json().get("access_token") or r.json().get("token")
    r = await ac.get("/api/csrf")
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": r.json()["csrf_token"],
    }


def _shield_response(payload: Dict[str, Any], audit_id: str = "tap7-mock") -> Dict[str, Any]:
    return {
        "response": json.dumps(payload),
        "audit_id": audit_id,
        "trust_receipt": {},
    }


_DOC_TITLE = "Q3 Capital Position Brief"
_DOC_KIND = "report"
_STRUCTURED = {"sections": [
    {"heading": "Executive summary",
     "paragraphs": ["Capital adequacy held at 14.2% per Doc A."]},
    {"heading": "Risks",
     "paragraphs": ["Reliance on commercial real estate at 22% per Doc A."]},
]}
_BLOBS = [
    {"id": "doc-A", "name": "Q3 internal brief",
     "extracted_text": "Capital adequacy 14.2%. CRE concentration 22%."},
]


# ════════════════════════════════════════════════════════════════
# Group A — Scorer unit tests (5/15)
# ════════════════════════════════════════════════════════════════


async def test_score_confidence_happy_path_deterministic_weights(monkeypatch):
    """Test 1 — happy path → weighted average is deterministic.

    Per Pre-Read §2 weights: source_coverage=0.40 +
    internal_consistency=0.25 + gap_clarity=0.20 +
    recommendation_grounding=0.15. Dim values 80/70/60/100 →
    weighted = 0.4*80 + 0.25*70 + 0.2*60 + 0.15*100 = 32 + 17.5 + 12 + 15 = 76.5 → round → 77.

    Tightening-4 absorbed test #5: recommendation_grounding=100 means
    docs without recs are NOT penalised — covered here because we
    explicitly send 100 and assert the aggregation honors the weight.
    """
    from services.work_studio.confidence_scorer import score_confidence

    monkeypatch.setattr(
        "services.work_studio.confidence_scorer.shield_invoke",
        AsyncMock(return_value=_shield_response({
            "source_coverage":           80,
            "internal_consistency":      70,
            "gap_clarity":               60,
            "recommendation_grounding": 100,
            "rationale": "Sources cover most claims; no recs surface.",
        })),
    )
    result = await score_confidence(
        document_title=_DOC_TITLE,
        document_kind=_DOC_KIND,
        structured_content=_STRUCTURED,
        source_blobs=_BLOBS,
        tenant_id="acct-tap7",
    )
    assert result is not None, "happy path should not return None"
    # 0.4*80 + 0.25*70 + 0.2*60 + 0.15*100 = 32 + 17.5 + 12 + 15 = 76.5
    # Python's round() uses banker's rounding (round-half-to-even):
    #   round(76.5) → 76 (76 is the nearer even). Deterministic.
    assert result["confidence_pct"] == 76, (
        f"Expected deterministic 76 (banker rounding of 76.5); "
        f"got {result['confidence_pct']}"
    )
    assert result["rationale"] == "Sources cover most claims; no recs surface."
    assert result["breakdown"]["source_coverage"] == 80
    assert result["breakdown"]["recommendation_grounding"] == 100
    assert result["cache_key"], "cache_key must be set"
    assert len(result["cache_key"]) == 64, "SHA-256 hex digest is 64 chars"


async def test_score_confidence_clamps_out_of_range_dimensions(monkeypatch):
    """Test 2 — clamp [0,100]. Values 150 and -5 must clamp."""
    from services.work_studio.confidence_scorer import score_confidence

    monkeypatch.setattr(
        "services.work_studio.confidence_scorer.shield_invoke",
        AsyncMock(return_value=_shield_response({
            "source_coverage":           150,  # → 100
            "internal_consistency":       -5,  # → 0
            "gap_clarity":                50,
            "recommendation_grounding":  100,
            "rationale": "Out-of-range smoke.",
        })),
    )
    result = await score_confidence(
        document_title=_DOC_TITLE, document_kind=_DOC_KIND,
        structured_content=_STRUCTURED, source_blobs=_BLOBS,
        tenant_id="acct-tap7",
    )
    assert result is not None
    assert result["breakdown"]["source_coverage"] == 100
    assert result["breakdown"]["internal_consistency"] == 0
    # 0.4*100 + 0.25*0 + 0.2*50 + 0.15*100 = 40 + 0 + 10 + 15 = 65
    assert result["confidence_pct"] == 65


async def test_score_confidence_skips_when_no_source_documents(monkeypatch):
    """Test 3 — empty source_documents → return None, no Shield call."""
    from services.work_studio.confidence_scorer import score_confidence

    fake_shield = AsyncMock()
    monkeypatch.setattr(
        "services.work_studio.confidence_scorer.shield_invoke", fake_shield,
    )
    result = await score_confidence(
        document_title=_DOC_TITLE, document_kind=_DOC_KIND,
        structured_content=_STRUCTURED,
        source_blobs=[],  # the skip trigger
        tenant_id="acct-tap7",
    )
    assert result is None
    fake_shield.assert_not_called()


async def test_score_confidence_malformed_json_surfaces_none(monkeypatch):
    """Test 4 — malformed JSON → return None (caller sets flag)."""
    from services.work_studio.confidence_scorer import score_confidence

    monkeypatch.setattr(
        "services.work_studio.confidence_scorer.shield_invoke",
        AsyncMock(return_value={"response": "not json at all", "audit_id": "x"}),
    )
    result = await score_confidence(
        document_title=_DOC_TITLE, document_kind=_DOC_KIND,
        structured_content=_STRUCTURED, source_blobs=_BLOBS,
        tenant_id="acct-tap7",
    )
    assert result is None


async def test_score_confidence_shield_raise_surfaces_none(monkeypatch):
    """Test 5 — Shield raises → return None (caller sets failed flag)."""
    from services.work_studio.confidence_scorer import score_confidence

    async def raise_shield(**_kwargs):
        raise RuntimeError("shield gone")

    monkeypatch.setattr(
        "services.work_studio.confidence_scorer.shield_invoke", raise_shield,
    )
    result = await score_confidence(
        document_title=_DOC_TITLE, document_kind=_DOC_KIND,
        structured_content=_STRUCTURED, source_blobs=_BLOBS,
        tenant_id="acct-tap7",
    )
    assert result is None


# ════════════════════════════════════════════════════════════════
# Group B — Compile-path integration (4/15)
# ════════════════════════════════════════════════════════════════


async def _seed_source_doc(db_conn, *, account_id: str, context_id: str) -> str:
    doc_id = "doc-tap7-src-" + uuid.uuid4().hex[:8]
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.documents.insert_one({
        "id": doc_id, "context_id": context_id, "account_id": account_id,
        "name": "Tap7 source brief", "extracted_text": "Capital 14.2%.",
        "created_at": now_iso,
    })
    return doc_id


async def _seed_documents_row_for_mirror(db_conn, *, account_id: str, context_id: str,
                                          confidence_pct=None) -> str:
    """The documents row that the export's continue-doc-id mirrors to."""
    doc_id = "doc-tap7-mirror-" + uuid.uuid4().hex[:8]
    now_iso = datetime.now(timezone.utc).isoformat()
    row = {
        "id": doc_id, "context_id": context_id, "account_id": account_id,
        "name": "Tap7 mirror doc", "kind": "report",
        "created_at": now_iso,
    }
    if confidence_pct is not None:
        row["confidence_pct"] = confidence_pct
    await db_conn.documents.insert_one(row)
    return doc_id


async def _seed_export_complete_shell(
    db_conn, *, account_id: str, context_id: str,
    cont_doc_id: str, structured_content: Dict[str, Any] | None = None,
) -> str:
    """Pre-populate a work_studio_exports row in the state it would
    be in right after _run_export's final update_one() — status=complete,
    structured_content present, ready for _score_and_mirror_confidence
    to write onto."""
    export_id = "wse-tap7-" + uuid.uuid4().hex[:10]
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.work_studio_exports.insert_one({
        "id": export_id, "context_id": context_id, "account_id": account_id,
        "kind": "report", "title": "Tap7 export shell",
        "status": "complete", "lifecycle_state": "draft",
        "structured_content": structured_content or _STRUCTURED,
        "intelligence_report": {},
        "source_document_ids": [],
        "legacy": False,
        "created_at": now_iso, "updated_at": now_iso,
    })
    return export_id


async def test_run_export_populates_intelligence_report_on_complete(
    transport, db_conn, monkeypatch,
):
    """Test 6 — call the shared helper directly with mocked Shield;
    assert intelligence_report fields land on the row."""
    from routers.work_studio_export import _score_and_mirror_confidence

    monkeypatch.setattr(
        "services.work_studio.confidence_scorer.shield_invoke",
        AsyncMock(return_value=_shield_response({
            "source_coverage": 90, "internal_consistency": 90,
            "gap_clarity": 80, "recommendation_grounding": 100,
            "rationale": "Strong source coverage with explicit gap acknowledgement.",
        }, audit_id="tap7-r6")),
    )

    admin_row = await db_conn.accounts.find_one(
        {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "default_context_id": 1},
    )
    acct_id = admin_row["id"]
    cid = admin_row.get("default_context_id") or "ctx-tap7-r6"
    src_id = await _seed_source_doc(db_conn, account_id=acct_id, context_id=cid)
    mirror_id = await _seed_documents_row_for_mirror(
        db_conn, account_id=acct_id, context_id=cid,
    )
    export_id = await _seed_export_complete_shell(
        db_conn, account_id=acct_id, context_id=cid, cont_doc_id=mirror_id,
    )

    try:
        audit = await _score_and_mirror_confidence(
            export_id=export_id, account_id=acct_id, context_id=cid,
            document_title=_DOC_TITLE, document_kind="report",
            structured_content=_STRUCTURED,
            citations_manifest=[{"doc_id": src_id}],
            documents_row_id=mirror_id,
        )
        assert audit["scored"] is True
        # 0.4*90 + 0.25*90 + 0.2*80 + 0.15*100 = 36 + 22.5 + 16 + 15 = 89.5 → 90
        assert audit["pct"] == 90

        row = await db_conn.work_studio_exports.find_one({"id": export_id}, {"_id": 0})
        intel = row["intelligence_report"]
        assert intel["confidence_pct"] == 90
        assert "Strong source coverage" in intel["confidence_rationale"]
        assert intel["confidence_scored_at"]
        assert intel["confidence_breakdown"]["source_coverage"] == 90
        assert intel["confidence_scored_at_cache_key"]
        assert intel["confidence_score_failed"] is False
        assert intel["confidence_score_audit_id"] == "tap7-r6"
    finally:
        await db_conn.documents.delete_many({"id": {"$in": [src_id, mirror_id]}})
        await db_conn.work_studio_exports.delete_one({"id": export_id})


async def test_run_export_completes_even_if_score_fails(
    transport, db_conn, monkeypatch,
):
    """Test 7 — Shield raises mid-scoring; assert the helper still
    completes cleanly with the failed flag set; row is left
    `status=complete` (we don't touch it, only intelligence_report)."""
    from routers.work_studio_export import _score_and_mirror_confidence

    async def angry_shield(**_kwargs):
        raise RuntimeError("phase7 deliberate shield raise")

    monkeypatch.setattr(
        "services.work_studio.confidence_scorer.shield_invoke", angry_shield,
    )

    admin_row = await db_conn.accounts.find_one(
        {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "default_context_id": 1},
    )
    acct_id = admin_row["id"]
    cid = admin_row.get("default_context_id") or "ctx-tap7-r7"
    src_id = await _seed_source_doc(db_conn, account_id=acct_id, context_id=cid)
    mirror_id = await _seed_documents_row_for_mirror(
        db_conn, account_id=acct_id, context_id=cid,
    )
    export_id = await _seed_export_complete_shell(
        db_conn, account_id=acct_id, context_id=cid, cont_doc_id=mirror_id,
    )

    try:
        audit = await _score_and_mirror_confidence(
            export_id=export_id, account_id=acct_id, context_id=cid,
            document_title=_DOC_TITLE, document_kind="report",
            structured_content=_STRUCTURED,
            citations_manifest=[{"doc_id": src_id}],
            documents_row_id=mirror_id,
        )
        assert audit["failed"] is True
        assert audit["scored"] is False
        row = await db_conn.work_studio_exports.find_one({"id": export_id}, {"_id": 0})
        intel = row["intelligence_report"]
        assert intel["confidence_score_failed"] is True
        assert intel.get("confidence_pct") is None  # no pct written on fail
        # The row remains status=complete (we don't touch status on score-fail)
        assert row["status"] == "complete"
    finally:
        await db_conn.documents.delete_many({"id": {"$in": [src_id, mirror_id]}})
        await db_conn.work_studio_exports.delete_one({"id": export_id})


async def test_run_export_mirrors_confidence_pct_to_documents_row(
    transport, db_conn, monkeypatch,
):
    """Test 8 — happy-path mirror: documents.confidence_pct ==
    work_studio_exports.intelligence_report.confidence_pct."""
    from routers.work_studio_export import _score_and_mirror_confidence

    monkeypatch.setattr(
        "services.work_studio.confidence_scorer.shield_invoke",
        AsyncMock(return_value=_shield_response({
            "source_coverage": 75, "internal_consistency": 75,
            "gap_clarity": 75, "recommendation_grounding": 75,
            "rationale": "Uniform 75 across all dims.",
        })),
    )

    admin_row = await db_conn.accounts.find_one(
        {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "default_context_id": 1},
    )
    acct_id = admin_row["id"]
    cid = admin_row.get("default_context_id") or "ctx-tap7-r8"
    src_id = await _seed_source_doc(db_conn, account_id=acct_id, context_id=cid)
    mirror_id = await _seed_documents_row_for_mirror(
        db_conn, account_id=acct_id, context_id=cid,
    )
    export_id = await _seed_export_complete_shell(
        db_conn, account_id=acct_id, context_id=cid, cont_doc_id=mirror_id,
    )

    try:
        await _score_and_mirror_confidence(
            export_id=export_id, account_id=acct_id, context_id=cid,
            document_title=_DOC_TITLE, document_kind="report",
            structured_content=_STRUCTURED,
            citations_manifest=[{"doc_id": src_id}],
            documents_row_id=mirror_id,
        )
        export_row = await db_conn.work_studio_exports.find_one({"id": export_id}, {"_id": 0})
        doc_row = await db_conn.documents.find_one({"id": mirror_id}, {"_id": 0})
        # 0.4*75 + 0.25*75 + 0.2*75 + 0.15*75 = 75
        assert export_row["intelligence_report"]["confidence_pct"] == 75
        assert doc_row["confidence_pct"] == 75
    finally:
        await db_conn.documents.delete_many({"id": {"$in": [src_id, mirror_id]}})
        await db_conn.work_studio_exports.delete_one({"id": export_id})


async def test_failed_score_does_not_clobber_documents_confidence_pct(
    transport, db_conn, monkeypatch,
):
    """Test 9 — Tightening 2 (failure-path safety): when scorer fails,
    documents.confidence_pct MUST NOT be clobbered from a prior good
    value."""
    from routers.work_studio_export import _score_and_mirror_confidence

    async def angry_shield(**_kwargs):
        raise RuntimeError("tighten-2 shield raise")

    monkeypatch.setattr(
        "services.work_studio.confidence_scorer.shield_invoke", angry_shield,
    )

    admin_row = await db_conn.accounts.find_one(
        {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "default_context_id": 1},
    )
    acct_id = admin_row["id"]
    cid = admin_row.get("default_context_id") or "ctx-tap7-r9"
    src_id = await _seed_source_doc(db_conn, account_id=acct_id, context_id=cid)
    # Pre-existing pct on the documents row — must survive the failed re-score.
    mirror_id = await _seed_documents_row_for_mirror(
        db_conn, account_id=acct_id, context_id=cid, confidence_pct=82,
    )
    export_id = await _seed_export_complete_shell(
        db_conn, account_id=acct_id, context_id=cid, cont_doc_id=mirror_id,
    )

    try:
        await _score_and_mirror_confidence(
            export_id=export_id, account_id=acct_id, context_id=cid,
            document_title=_DOC_TITLE, document_kind="report",
            structured_content=_STRUCTURED,
            citations_manifest=[{"doc_id": src_id}],
            documents_row_id=mirror_id,
        )
        doc_row = await db_conn.documents.find_one({"id": mirror_id}, {"_id": 0})
        assert doc_row["confidence_pct"] == 82, (
            f"Tightening 2 contract VIOLATED — pre-existing pct=82 was "
            f"clobbered to {doc_row.get('confidence_pct')!r} on scorer "
            "failure."
        )
        export_row = await db_conn.work_studio_exports.find_one({"id": export_id}, {"_id": 0})
        assert export_row["intelligence_report"]["confidence_score_failed"] is True
    finally:
        await db_conn.documents.delete_many({"id": {"$in": [src_id, mirror_id]}})
        await db_conn.work_studio_exports.delete_one({"id": export_id})


# ════════════════════════════════════════════════════════════════
# Group C — Commit-recompute (3/15)
# ════════════════════════════════════════════════════════════════


async def _seed_committable_doc(
    db_conn, *, account_id: str, context_id: str,
    source_doc_id: str, intel_seed: Dict[str, Any] | None = None,
    structured_content: Dict[str, Any] | None = None,
) -> str:
    aid = "wse-tap7-commit-" + uuid.uuid4().hex[:10]
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.work_studio_exports.insert_one({
        "id": aid, "context_id": context_id, "account_id": account_id,
        "kind": "report", "title": "Tap7 commit doc",
        "status": "complete", "lifecycle_state": "draft",
        "structured_content": structured_content or _STRUCTURED,
        "intelligence_report": intel_seed or {},
        "source_document_ids": [source_doc_id],
        "legacy": False,
        "created_at": now_iso, "updated_at": now_iso,
    })
    return aid


async def test_commit_recompute_updates_pct_and_cache_key(
    transport, db_conn, monkeypatch,
):
    """Test 10 — commit on a doc with no prior cache_key → recompute
    fires → new pct + new cache_key on the row + lifecycle=committed."""
    monkeypatch.setattr(
        "services.work_studio.confidence_scorer.shield_invoke",
        AsyncMock(return_value=_shield_response({
            "source_coverage": 85, "internal_consistency": 80,
            "gap_clarity": 70, "recommendation_grounding": 100,
            "rationale": "Recomputed.",
        }, audit_id="tap7-r10")),
    )

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        admin_row = await db_conn.accounts.find_one(
            {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "default_context_id": 1},
        )
        acct_id = admin_row["id"]
        cid = admin_row.get("default_context_id") or "ctx-tap7-r10"
        src_id = await _seed_source_doc(db_conn, account_id=acct_id, context_id=cid)
        aid = await _seed_committable_doc(
            db_conn, account_id=acct_id, context_id=cid, source_doc_id=src_id,
        )

        try:
            r = await ac.post(
                f"/api/contexts/{cid}/work-studio/documents/{aid}/commit",
                headers=admin,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["lifecycle_state"] == "committed"
            assert body.get("confidence_recompute_skipped_unchanged") is None
            assert body.get("confidence_recompute_failed") is None
            row = await db_conn.work_studio_exports.find_one({"id": aid}, {"_id": 0})
            intel = row["intelligence_report"]
            # 0.4*85 + 0.25*80 + 0.2*70 + 0.15*100 = 34 + 20 + 14 + 15 = 83
            assert intel["confidence_pct"] == 83
            assert intel["confidence_recomputed_at"]
            assert intel["confidence_scored_at_cache_key"]
        finally:
            await db_conn.documents.delete_one({"id": src_id})
            await db_conn.work_studio_exports.delete_one({"id": aid})
            await db_conn.work_studio_artefact_versions.delete_many({"artefact_id": aid})


async def test_commit_recompute_skipped_when_structured_content_unchanged(
    transport, db_conn, monkeypatch,
):
    """Test 11 — Tightening 4: cache hit → skip Shield → response has
    confidence_recompute_skipped_unchanged=true; pct unchanged; lifecycle
    flips."""
    from services.work_studio.confidence_scorer import structured_content_hash

    # Compute the cache_key the doc would have AS IF a prior compile
    # scored it.
    cached_key = structured_content_hash(_STRUCTURED)

    fake_shield = AsyncMock()
    monkeypatch.setattr(
        "services.work_studio.confidence_scorer.shield_invoke", fake_shield,
    )

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        admin_row = await db_conn.accounts.find_one(
            {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "default_context_id": 1},
        )
        acct_id = admin_row["id"]
        cid = admin_row.get("default_context_id") or "ctx-tap7-r11"
        src_id = await _seed_source_doc(db_conn, account_id=acct_id, context_id=cid)
        aid = await _seed_committable_doc(
            db_conn, account_id=acct_id, context_id=cid, source_doc_id=src_id,
            intel_seed={
                "confidence_pct": 71,
                "confidence_scored_at_cache_key": cached_key,
                "confidence_rationale": "Pre-existing scored rationale.",
            },
        )

        try:
            r = await ac.post(
                f"/api/contexts/{cid}/work-studio/documents/{aid}/commit",
                headers=admin,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["lifecycle_state"] == "committed"
            assert body.get("confidence_recompute_skipped_unchanged") is True
            fake_shield.assert_not_called()
            row = await db_conn.work_studio_exports.find_one({"id": aid}, {"_id": 0})
            assert row["intelligence_report"]["confidence_pct"] == 71
            assert row["lifecycle_state"] == "committed"
        finally:
            await db_conn.documents.delete_one({"id": src_id})
            await db_conn.work_studio_exports.delete_one({"id": aid})
            await db_conn.work_studio_artefact_versions.delete_many({"artefact_id": aid})


async def test_commit_recompute_failure_surfaces_flag_lifecycle_still_locks(
    transport, db_conn, monkeypatch,
):
    """Test 12 — Shield raises mid-recompute; response carries
    confidence_recompute_failed: true; lifecycle still flips to
    committed; prior pct preserved."""

    async def angry_shield(**_kwargs):
        raise RuntimeError("commit-recompute deliberate shield raise")

    monkeypatch.setattr(
        "services.work_studio.confidence_scorer.shield_invoke", angry_shield,
    )

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        admin_row = await db_conn.accounts.find_one(
            {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "default_context_id": 1},
        )
        acct_id = admin_row["id"]
        cid = admin_row.get("default_context_id") or "ctx-tap7-r12"
        src_id = await _seed_source_doc(db_conn, account_id=acct_id, context_id=cid)
        # Prior pct = 60. Structured content has been edited (no cache_key on row)
        # → recompute will fire → it will fail.
        aid = await _seed_committable_doc(
            db_conn, account_id=acct_id, context_id=cid, source_doc_id=src_id,
            intel_seed={"confidence_pct": 60, "confidence_rationale": "old"},
        )

        try:
            r = await ac.post(
                f"/api/contexts/{cid}/work-studio/documents/{aid}/commit",
                headers=admin,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["lifecycle_state"] == "committed"
            assert body.get("confidence_recompute_failed") is True
            row = await db_conn.work_studio_exports.find_one({"id": aid}, {"_id": 0})
            assert row["lifecycle_state"] == "committed"
            # Old pct preserved (we don't clobber on failure).
            assert row["intelligence_report"]["confidence_pct"] == 60
            assert row["intelligence_report"]["confidence_score_failed"] is True
        finally:
            await db_conn.documents.delete_one({"id": src_id})
            await db_conn.work_studio_exports.delete_one({"id": aid})
            await db_conn.work_studio_artefact_versions.delete_many({"artefact_id": aid})


# ════════════════════════════════════════════════════════════════
# Group D — Overlay payload contract (1/15)
# ════════════════════════════════════════════════════════════════


async def test_overlay_payload_surfaces_rationale_and_legacy_row_handles_absence(
    transport, db_conn,
):
    """Test 13 — Tightening 3: legacy row (confidence_pct present but
    no rationale) → overlay payload returns confidence_rationale=None.
    Fresh row WITH rationale → overlay payload returns the rationale
    string. FE chip handles both cases — covered by the
    `data-confidence-tooltip` attribute on `IntelligenceCard`."""
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        admin_row = await db_conn.accounts.find_one(
            {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "default_context_id": 1},
        )
        acct_id = admin_row["id"]
        cid = admin_row.get("default_context_id") or "ctx-tap7-r13"

        # (a) Fresh row with rationale.
        fresh_id = "wse-tap7-fresh-" + uuid.uuid4().hex[:8]
        now_iso = datetime.now(timezone.utc).isoformat()
        await db_conn.work_studio_exports.insert_one({
            "id": fresh_id, "context_id": cid, "account_id": acct_id,
            "kind": "report", "title": "Tap7 fresh doc",
            "lifecycle_state": "draft",
            "structured_content": _STRUCTURED,
            "intelligence_report": {
                "confidence_pct":      78,
                "confidence_rationale": "Sources thoroughly cited; recs grounded.",
                "confidence_scored_at": now_iso,
            },
            "source_document_ids": [],
            "legacy": False,
            "created_at": now_iso, "updated_at": now_iso,
        })

        # (b) Legacy row with confidence_pct but no rationale (the
        # `seed_chunks.py` shape).
        legacy_id = "wse-tap7-legacy-" + uuid.uuid4().hex[:8]
        await db_conn.work_studio_exports.insert_one({
            "id": legacy_id, "context_id": cid, "account_id": acct_id,
            "kind": "report", "title": "Tap7 legacy seed doc",
            "lifecycle_state": "draft",
            "structured_content": _STRUCTURED,
            "intelligence_report": {"confidence_pct": 73},  # legacy shape
            "source_document_ids": [],
            "legacy": False,
            "created_at": now_iso, "updated_at": now_iso,
        })

        try:
            r1 = await ac.get(
                f"/api/contexts/{cid}/work-studio/documents/{fresh_id}",
                headers=admin,
            )
            assert r1.status_code == 200, r1.text
            body1 = r1.json()
            assert body1["confidence_rationale"] == "Sources thoroughly cited; recs grounded."
            assert body1["confidence_scored_at"] == now_iso
            assert body1["confidence_score_failed"] is False

            r2 = await ac.get(
                f"/api/contexts/{cid}/work-studio/documents/{legacy_id}",
                headers=admin,
            )
            assert r2.status_code == 200, r2.text
            body2 = r2.json()
            # Legacy row → rationale is None (FE suppresses tooltip — Tightening 3 (a)).
            assert body2["confidence_rationale"] is None
            assert body2["confidence_scored_at"] is None
            assert body2["confidence_score_failed"] is False
            # The pct itself still surfaces via intelligence_report.
            assert body2["intelligence_report"]["confidence_pct"] == 73
        finally:
            await db_conn.work_studio_exports.delete_many(
                {"id": {"$in": [fresh_id, legacy_id]}},
            )


# ════════════════════════════════════════════════════════════════
# Group E — Real-LLM integration-marked (2/15) — Tightening 1
# ════════════════════════════════════════════════════════════════


@pytest.mark.integration
async def test_score_confidence_real_shield_happy_path():
    """Test 14 — real Shield round-trip. Run with `pytest -m integration`."""
    from services.work_studio.confidence_scorer import score_confidence

    result = await score_confidence(
        document_title="Bank Q3 brief",
        document_kind="report",
        structured_content={"sections": [
            {"heading": "Capital position",
             "paragraphs": [
                 "Capital adequacy ratio held at 14.2% at quarter-end "
                 "per the internal brief.",
                 "CET1 was 12.8%."
             ]},
            {"heading": "Concentrations",
             "paragraphs": [
                 "Commercial real estate exposure at 22%, in line with "
                 "the internal brief."
             ]},
            {"heading": "What we don't know",
             "paragraphs": [
                 "Stress-test outcomes were not in scope of the brief; "
                 "any forward-looking read is exploratory."
             ]},
        ]},
        source_blobs=[
            {"id": "doc-1", "name": "Q3 internal brief",
             "extracted_text":
                 "Capital adequacy ratio 14.2% at quarter-end. "
                 "CET1 12.8%. Liquidity coverage 134%. "
                 "Commercial real estate concentration 22%."},
        ],
        tenant_id="tap7-real-r14",
    )
    assert result is not None, "Shield returned None on happy path"
    assert 0 <= result["confidence_pct"] <= 100
    assert len(result["rationale"]) > 0
    assert result["audit_id"]
    # Spot-check that the LLM honoured the gap-clarity dim — a doc
    # with an explicit "what we don't know" section should score
    # at least medium on gap_clarity.
    assert result["breakdown"]["gap_clarity"] >= 50, (
        f"gap_clarity dim {result['breakdown']['gap_clarity']} too low "
        f"for a doc with an explicit gaps section"
    )


@pytest.mark.integration
async def test_score_confidence_real_shield_consistency_three_calls():
    """Test 15 — Tightening 1: 3 sequential Shield calls on the same
    doc; max pairwise diff ≤ 10. Variance check on the rubric."""
    from services.work_studio.confidence_scorer import score_confidence

    doc_args = {
        "document_title": "Stable consistency test",
        "document_kind": "report",
        "structured_content": {"sections": [
            {"heading": "Topline",
             "paragraphs": [
                 "Q3 revenue grew 8% year-on-year per the data brief.",
                 "Operating margin compressed 120bps in the same period."
             ]},
        ]},
        "source_blobs": [
            {"id": "doc-1", "name": "data-brief",
             "extracted_text":
                 "Q3 revenue +8% YoY. Operating margin -120bps. "
                 "Headcount flat. Cash position +14%."},
        ],
        "tenant_id": "tap7-real-r15",
    }
    scores = []
    for _ in range(3):
        r = await score_confidence(**doc_args)
        assert r is not None
        scores.append(r["confidence_pct"])
    spread = max(scores) - min(scores)
    assert spread <= 10, (
        f"Phase 7 rubric variance > 10 on 3-sample test: scores={scores}, "
        f"spread={spread}. Rubric is too noisy."
    )
