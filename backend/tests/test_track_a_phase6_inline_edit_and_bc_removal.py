"""Track A Phase 6 (2026-06-04) — Document Review Drawer inline editing
+ Revise-with-AI restoration + BC mirror removal lockdowns.

Scope (12 tests; FE Playwright lives in /tmp/phase6_*.py):
  • 4 BC mirror removal end-to-end:
      - synthesize does NOT write top-level `narration` on the DB row
      - notes POST does NOT write top-level `notes` / `notes_updated_at`
      - GET /v2/analyses strips legacy top-level mirrors for legacy rows
      - listing endpoint's note_count reads from notes_history only
  • 2 commit-path regression (BC removal doesn't ripple into commit):
      - commit still locks lifecycle_state to "committed"
      - commit still creates a pre-commit snapshot
  • 3 narration-regression:
      - synthesize fresh row → no top-level narration key on DB
      - notes POST fresh row → no top-level notes/notes_updated_at keys
      - GET response shape contract: no BC mirrors leak
  • 1 deterministic snapshot test (Tightening 4 reallocation):
      - /revise creates the pre-revision snapshot BEFORE Shield call
        (Shield monkeypatched to raise; snapshot still exists)
  • 2 BE integration-marked real-LLM Revise (Tightening 4):
      - happy path: real Shield round-trip returns diff with section_diffs
      - refusal: source_document_ids=[] → 412, Shield NOT called

Real-LLM tests are opt-in via `pytest -m integration`. The default
sweep deselects them.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

import server  # noqa: F401  — ensures app startup wiring (mongo client etc.)
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
    assert token
    r = await ac.get("/api/csrf")
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": r.json()["csrf_token"],
    }


def _shield_ok(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"response": json.dumps(payload), "trust_receipt": {}, "audit_id": "t"}


def _build_24mo_xlsx() -> bytes:
    from datetime import date
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Monthly"
    ws.append(["month", "actual_sales"])
    for i in range(24):
        m = i % 12 + 1
        y = 2024 + (i // 12)
        ws.append([date(y, m, 28), 10000 + i * 220])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _seed_analysis(ac: AsyncClient, headers: Dict[str, str], *, ctx: str) -> str:
    fd = [
        ("files", (
            "monthly.xlsx", _build_24mo_xlsx(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )),
    ]
    r = await ac.post(
        "/api/workbook/upload-multi",
        files=fd, data={"context_id": ctx}, headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


_OK_NARRATION = {
    "headline": "Top-line growth held across all periods.",
    "observations": [
        {"tab": "what_changed", "title": "Steady growth",
         "body": "Monthly run rate climbed across the sampled periods.",
         "evidence_citation_indices": [0]},
    ],
}


# ─── BC mirror removal — 4 tests ───────────────────────────────


async def test_synthesize_does_not_write_top_level_narration(transport, monkeypatch):
    """Phase 6 — synthesize endpoint MUST NOT write top-level
    `narration` on the analyses row. The runs[-1] entry is the
    canonical source."""
    from services.solva_v2 import analyze_narration as narr
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=_shield_ok(_OK_NARRATION)))

    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_analysis(
            ac, admin, ctx="tap6-bc-narr-" + uuid.uuid4().hex[:6],
        )
        r = await ac.post(
            f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin,
        )
        assert r.status_code == 200, r.text
        row = await db.analyses.find_one({"id": aid}, {"_id": 0})
        # Phase 6 contract: top-level mirror gone, runs[-1] populated.
        assert "narration" not in row, (
            f"Expected no top-level 'narration' key after Phase 6 BC "
            f"removal; got keys: {sorted(row.keys())}"
        )
        runs = row.get("runs") or []
        assert len(runs) == 1, f"runs missing; row keys = {sorted(row.keys())}"
        assert runs[-1]["headline"] == _OK_NARRATION["headline"]


async def test_notes_post_does_not_write_top_level_notes(transport):
    """Phase 6 — notes POST MUST NOT write top-level `notes` or
    `notes_updated_at` mirrors. notes_history[-1] is canonical."""
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_analysis(
            ac, admin, ctx="tap6-bc-notes-" + uuid.uuid4().hex[:6],
        )
        r = await ac.post(
            f"/api/workbook/v2/analyses/{aid}/notes",
            json={"body": "Phase 6 note."}, headers=admin,
        )
        assert r.status_code == 200, r.text
        row = await db.analyses.find_one({"id": aid}, {"_id": 0})
        assert "notes" not in row, (
            f"Expected no top-level 'notes' key; got: {sorted(row.keys())}"
        )
        assert "notes_updated_at" not in row, (
            f"Expected no top-level 'notes_updated_at' key; got: {sorted(row.keys())}"
        )
        history = row.get("notes_history") or []
        assert len(history) == 1
        assert history[-1]["body"] == "Phase 6 note."


async def test_get_analysis_strips_legacy_bc_mirrors_for_legacy_rows(
    transport, db_conn,
):
    """Legacy rows on the DB carrying pre-Phase-6 mirror fields
    MUST be stripped by the GET endpoint before returning. The
    user's contract: "API response shape drops. No derived BC field
    on the API as a fallback." We strip on read."""
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")

        # Find the admin's account_id.
        admin_row = await db_conn.accounts.find_one(
            {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "default_context_id": 1},
        )
        admin_id = admin_row["id"]

        # Hand-write a legacy-shape analysis row carrying all three
        # top-level BC mirror fields.
        legacy_aid = "ana-legacy-" + uuid.uuid4().hex[:10]
        legacy_ctx = admin_row.get("default_context_id") or "ctx-legacy-tap6"
        now_iso = datetime.now(timezone.utc).isoformat()
        legacy_row = {
            "id": legacy_aid,
            "account_id": admin_id,
            "context_id": legacy_ctx,
            "title": "Legacy doc",
            "status": "ready",
            "sources": [],
            "objective": "legacy",
            "observations": [],
            # Top-level BC mirrors that pre-Phase-6 synthesize wrote.
            "narration": {"headline": "legacy headline", "refused": False},
            "notes": "legacy note text",
            "notes_updated_at": now_iso,
            "notes_history": [
                {"id": "note-legacy", "body": "legacy note text",
                 "created_at": now_iso, "author_account_id": admin_id},
            ],
            "runs": [
                {"run_id": "run-legacy", "created_at": now_iso,
                 "headline": "legacy headline", "observations": [],
                 "citations": [], "cache_key": "legacy", "refused": False,
                 "triggered_by_account_id": admin_id},
            ],
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        await db_conn.analyses.insert_one(dict(legacy_row))
        try:
            r = await ac.get(f"/api/workbook/v2/analyses/{legacy_aid}", headers=admin)
            assert r.status_code == 200, r.text
            body = r.json()
            assert "narration" not in body, (
                f"GET response leaked top-level 'narration'; keys: {sorted(body.keys())}"
            )
            assert "notes" not in body, (
                f"GET response leaked top-level 'notes'; keys: {sorted(body.keys())}"
            )
            assert "notes_updated_at" not in body, (
                f"GET response leaked 'notes_updated_at'; keys: {sorted(body.keys())}"
            )
            # Canonical sources still surface.
            assert body.get("notes_history") and body["notes_history"][-1]["body"] == "legacy note text"
            assert body.get("runs") and body["runs"][-1]["headline"] == "legacy headline"
        finally:
            await db_conn.analyses.delete_one({"id": legacy_aid})


async def test_listing_note_count_reads_from_notes_history_only(transport, db_conn):
    """Legacy row in DB has only top-level `notes` (no notes_history).
    Listing endpoint MUST return note_count=0 — no BC fallback to
    `r.get("notes")` (which was dropped in Phase 6)."""
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")

        admin_row = await db_conn.accounts.find_one(
            {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "default_context_id": 1},
        )
        admin_id = admin_row["id"]

        legacy_aid = "ana-listing-legacy-" + uuid.uuid4().hex[:10]
        now_iso = datetime.now(timezone.utc).isoformat()
        await db_conn.analyses.insert_one({
            "id": legacy_aid,
            "account_id": admin_id,
            "context_id": admin_row.get("default_context_id") or "ctx-listing-tap6",
            "title": "Pre-Phase-6 legacy",
            "status": "ready",
            "sources": [],
            "objective": "",
            # Only the BC mirror, no notes_history → listing must
            # NOT count this as 1 note.
            "notes": "would-have-been-counted-pre-phase-6",
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        try:
            r = await ac.get("/api/workbook/v2/analyses", headers=admin)
            assert r.status_code == 200, r.text
            rows = r.json()
            mine = [x for x in rows if x["id"] == legacy_aid]
            assert mine, "legacy row not surfaced by listing"
            assert mine[0]["note_count"] == 0, (
                f"Phase 6 listing must drop the BC fallback to top-level "
                f"'notes'; got note_count = {mine[0]['note_count']}"
            )
        finally:
            await db_conn.analyses.delete_one({"id": legacy_aid})


# ─── Commit-path regression — 2 tests ─────────────────────────


async def test_commit_still_locks_lifecycle_after_bc_removal(transport, db_conn):
    """Phase 6 BC mirror work touches `routers/workbook_analysis.py`,
    NOT the Work Studio commit path — but pin this so a future
    accidental shared-helper edit doesn't ripple."""
    # Work Studio commit endpoint = POST /api/contexts/{cid}/work-studio/documents/{aid}/commit
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        admin_row = await db_conn.accounts.find_one(
            {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "default_context_id": 1},
        )
        admin_id = admin_row["id"]
        cid = admin_row.get("default_context_id") or "ctx-tap6-commit"

        aid = "tap6-commit-" + uuid.uuid4().hex[:10]
        now_iso = datetime.now(timezone.utc).isoformat()
        await db_conn.work_studio_exports.insert_one({
            "id": aid,
            "account_id": admin_id,
            "context_id": cid,
            "kind": "report",
            "lifecycle_state": "draft",
            "structured_content": {"sections": [{"heading": "Test", "paragraphs": ["body"]}]},
            "source_document_ids": [],
            "intelligence_report": None,
            "legacy": False,
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        try:
            r = await ac.post(
                f"/api/contexts/{cid}/work-studio/documents/{aid}/commit",
                headers=admin,
            )
            assert r.status_code == 200, r.text
            assert r.json()["lifecycle_state"] == "committed"
            row = await db_conn.work_studio_exports.find_one({"id": aid}, {"_id": 0})
            assert row["lifecycle_state"] == "committed"
        finally:
            await db_conn.work_studio_exports.delete_one({"id": aid})
            await db_conn.work_studio_artefact_versions.delete_many({"artefact_id": aid})


async def test_commit_still_fires_pre_commit_snapshot_after_bc_removal(transport, db_conn):
    """Pre-commit snapshot path on POST /commit must fire after
    Phase 6 BC mirror removal."""
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        admin_row = await db_conn.accounts.find_one(
            {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "default_context_id": 1},
        )
        admin_id = admin_row["id"]
        cid = admin_row.get("default_context_id") or "ctx-tap6-commit-snap"

        aid = "tap6-commit-snap-" + uuid.uuid4().hex[:10]
        now_iso = datetime.now(timezone.utc).isoformat()
        await db_conn.work_studio_exports.insert_one({
            "id": aid,
            "account_id": admin_id,
            "context_id": cid,
            "kind": "report",
            "lifecycle_state": "draft",
            "structured_content": {"sections": [{"heading": "Snap", "paragraphs": ["yes"]}]},
            "source_document_ids": [],
            "legacy": False,
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        try:
            r = await ac.post(
                f"/api/contexts/{cid}/work-studio/documents/{aid}/commit",
                headers=admin,
            )
            assert r.status_code == 200, r.text
            snap_id = r.json()["pre_commit_snapshot_id"]
            snap = await db_conn.work_studio_artefact_versions.find_one(
                {"id": snap_id, "artefact_id": aid}, {"_id": 0},
            )
            assert snap is not None, "pre-commit snapshot was not created"
            assert snap.get("pre_commit") is True
            assert snap.get("label") == "Pre-commit"
        finally:
            await db_conn.work_studio_exports.delete_one({"id": aid})
            await db_conn.work_studio_artefact_versions.delete_many({"artefact_id": aid})


# ─── Narration regression — 3 tests ───────────────────────────


async def test_synthesize_fresh_row_has_no_top_level_narration(transport, monkeypatch):
    """A fresh synthesize on a brand-new analysis MUST NOT leave
    top-level `narration` on the DB row."""
    from services.solva_v2 import analyze_narration as narr
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=_shield_ok(_OK_NARRATION)))

    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_analysis(
            ac, admin, ctx="tap6-fresh-narr-" + uuid.uuid4().hex[:6],
        )
        await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        row = await db.analyses.find_one({"id": aid}, {"_id": 0})
        assert "narration" not in row


async def test_notes_post_fresh_row_has_no_top_level_notes_or_notes_updated_at(transport):
    """A fresh notes POST on a brand-new analysis MUST NOT leave
    top-level `notes` or `notes_updated_at` on the DB row."""
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_analysis(
            ac, admin, ctx="tap6-fresh-notes-" + uuid.uuid4().hex[:6],
        )
        await ac.post(
            f"/api/workbook/v2/analyses/{aid}/notes",
            json={"body": "Fresh note."}, headers=admin,
        )
        row = await db.analyses.find_one({"id": aid}, {"_id": 0})
        assert "notes" not in row
        assert "notes_updated_at" not in row


async def test_get_response_shape_contract_no_bc_mirrors_leak(transport, monkeypatch):
    """End-to-end response shape contract: synthesize + notes →
    GET /v2/analyses/{aid} returns NO top-level BC mirror keys."""
    from services.solva_v2 import analyze_narration as narr
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=_shield_ok(_OK_NARRATION)))

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_analysis(
            ac, admin, ctx="tap6-resp-shape-" + uuid.uuid4().hex[:6],
        )
        await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        await ac.post(
            f"/api/workbook/v2/analyses/{aid}/notes",
            json={"body": "Shape note."}, headers=admin,
        )
        r = await ac.get(f"/api/workbook/v2/analyses/{aid}", headers=admin)
        assert r.status_code == 200, r.text
        body = r.json()
        # No BC mirrors on the API surface.
        for forbidden in ("narration", "notes", "notes_updated_at"):
            assert forbidden not in body, (
                f"GET /v2/analyses leaked '{forbidden}'; keys: {sorted(body.keys())}"
            )
        # Canonical sources present.
        assert body.get("runs"), "runs missing on response"
        assert body.get("notes_history"), "notes_history missing on response"
        assert body["runs"][-1]["headline"] == _OK_NARRATION["headline"]
        assert body["notes_history"][-1]["body"] == "Shape note."


# ─── Pre-revision snapshot is deterministic (Tightening 4) ────


async def test_revise_creates_pre_revision_snapshot_before_shield_call(
    transport, db_conn, monkeypatch,
):
    """The pre-revision auto-save snapshot is created BEFORE the
    Shield call fires. If Shield raises, the snapshot still exists.
    This is deterministic — no LLM needed."""
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        admin_row = await db_conn.accounts.find_one(
            {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "default_context_id": 1},
        )
        admin_id = admin_row["id"]
        cid = admin_row.get("default_context_id") or "ctx-tap6-revise-snap"

        # Seed a work_studio_exports row WITH at least one source doc.
        source_doc_id = "doc-tap6-source-" + uuid.uuid4().hex[:8]
        now_iso = datetime.now(timezone.utc).isoformat()
        await db_conn.documents.insert_one({
            "id": source_doc_id, "context_id": cid, "account_id": admin_id,
            "name": "Tap6 source", "extracted_text": "Capital adequacy = 14.2%.",
            "created_at": now_iso,
        })

        aid = "tap6-rev-snap-" + uuid.uuid4().hex[:10]
        await db_conn.work_studio_exports.insert_one({
            "id": aid,
            "account_id": admin_id,
            "context_id": cid,
            "kind": "report",
            "lifecycle_state": "draft",
            "structured_content": {"sections": [{"heading": "Original", "paragraphs": ["body"]}]},
            "source_document_ids": [source_doc_id],
            "legacy": False,
            "created_at": now_iso,
            "updated_at": now_iso,
        })

        # Monkeypatch shield_invoke to raise — proves the snapshot
        # exists BEFORE the LLM call would have fired.
        import routers.work_studio_overlay as router_mod

        async def angry_shield(**kwargs):
            raise RuntimeError("Phase 6 lockdown — Shield should not be needed")

        monkeypatch.setattr(router_mod, "shield_invoke", angry_shield)

        try:
            try:
                r = await ac.post(
                    f"/api/contexts/{cid}/work-studio/documents/{aid}/revise",
                    json={"instruction": "Tighten the summary.",
                          "scope": "entire", "tone": "formal"},
                    headers=admin,
                )
                # Shield raises → either propagates as a RuntimeError (httpx)
                # or surfaces as a 5xx — either way the snapshot has ALREADY
                # been created at L465-472 BEFORE the shield_invoke call at
                # L484. The pre-revision snapshot is deterministic.
                assert r.status_code >= 500, (
                    f"Expected 5xx (or exception) after Shield raises; "
                    f"got {r.status_code}: {r.text}"
                )
            except RuntimeError as exc:
                # ASGI transport surfaced the raw exception; that's fine —
                # the snapshot was already created before the raise.
                assert "Shield should not be needed" in str(exc)
            snap = await db_conn.work_studio_artefact_versions.find_one(
                {"artefact_id": aid, "label": "Auto-save (before AI revision)"},
                {"_id": 0},
            )
            assert snap is not None, (
                "Pre-revision snapshot must be created BEFORE the Shield "
                "call fires; it was missing after Shield raised."
            )
        finally:
            await db_conn.documents.delete_one({"id": source_doc_id})
            await db_conn.work_studio_exports.delete_one({"id": aid})
            await db_conn.work_studio_artefact_versions.delete_many({"artefact_id": aid})


# ─── Integration-marked real-LLM Revise (Tightening 4) ────────


@pytest.mark.integration
async def test_revise_happy_path_real_shield_round_trip(transport, db_conn):
    """Real `shield_invoke` round-trip. Run with `pytest -m integration`.

    Constructs a real work_studio_exports row with one source doc,
    fires POST /revise, asserts that the diff returned contains at
    least one section_diff entry. No mocks."""
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        admin_row = await db_conn.accounts.find_one(
            {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "default_context_id": 1},
        )
        admin_id = admin_row["id"]
        cid = admin_row.get("default_context_id") or "ctx-tap6-rev-real"

        source_doc_id = "doc-tap6-rev-real-" + uuid.uuid4().hex[:8]
        now_iso = datetime.now(timezone.utc).isoformat()
        await db_conn.documents.insert_one({
            "id": source_doc_id, "context_id": cid, "account_id": admin_id,
            "name": "Bank brief", "extracted_text":
                "Capital adequacy ratio stood at 14.2% at quarter-end. "
                "CET1 was 12.8%. Liquidity coverage ratio 134%.",
            "created_at": now_iso,
        })

        aid = "tap6-rev-real-" + uuid.uuid4().hex[:10]
        await db_conn.work_studio_exports.insert_one({
            "id": aid,
            "account_id": admin_id,
            "context_id": cid,
            "kind": "report",
            "lifecycle_state": "draft",
            "structured_content": {"sections": [
                {"heading": "Executive summary",
                 "paragraphs": ["The bank's Q3 capital position was within thresholds."]},
                {"heading": "Capital position",
                 "paragraphs": ["Capital adequacy ratio held above the 13% floor at quarter-end."]},
            ]},
            "source_document_ids": [source_doc_id],
            "legacy": False,
            "created_at": now_iso,
            "updated_at": now_iso,
        })

        try:
            r = await ac.post(
                f"/api/contexts/{cid}/work-studio/documents/{aid}/revise",
                json={"instruction": "Tighten the executive summary; surface CET1 explicitly.",
                      "scope": "entire", "tone": "concise"},
                headers=admin,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("diff"), "diff missing on /revise response"
            section_diffs: List[Dict[str, Any]] = body["diff"].get("section_diffs") or []
            assert len(section_diffs) >= 1, (
                f"Expected at least one section_diff entry; got: {section_diffs}"
            )
            # Audit id from Shield.
            assert body.get("audit_id"), "audit_id missing"
            # Pre-revision snapshot fired.
            assert body.get("pre_revision_snapshot_id")
        finally:
            await db_conn.documents.delete_one({"id": source_doc_id})
            await db_conn.work_studio_exports.delete_one({"id": aid})
            await db_conn.work_studio_artefact_versions.delete_many({"artefact_id": aid})


@pytest.mark.integration
async def test_revise_refusal_path_412_no_source_docs_no_shield_call(
    transport, db_conn, monkeypatch,
):
    """source_document_ids=[] → 412 Refused, NO Shield call fires.
    Integration-marked because the refusal logic itself runs in the
    same router that the real-LLM tests exercise — keeps both under
    `-m integration` so they run together."""
    import routers.work_studio_overlay as router_mod
    shield_call_count = {"n": 0}

    async def sentinel_shield(**kwargs):
        shield_call_count["n"] += 1
        return {"response": '{"sections":[],"change_notes":[]}', "audit_id": "should-not-fire"}

    monkeypatch.setattr(router_mod, "shield_invoke", sentinel_shield)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        admin_row = await db_conn.accounts.find_one(
            {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "default_context_id": 1},
        )
        admin_id = admin_row["id"]
        cid = admin_row.get("default_context_id") or "ctx-tap6-rev-refusal"

        aid = "tap6-rev-refusal-" + uuid.uuid4().hex[:10]
        now_iso = datetime.now(timezone.utc).isoformat()
        await db_conn.work_studio_exports.insert_one({
            "id": aid,
            "account_id": admin_id,
            "context_id": cid,
            "kind": "report",
            "lifecycle_state": "draft",
            "structured_content": {"sections": [{"heading": "x", "paragraphs": ["y"]}]},
            "source_document_ids": [],  # the refusal trigger
            "legacy": False,
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        try:
            r = await ac.post(
                f"/api/contexts/{cid}/work-studio/documents/{aid}/revise",
                json={"instruction": "Anything.", "scope": "entire", "tone": "formal"},
                headers=admin,
            )
            assert r.status_code == 412, r.text
            assert shield_call_count["n"] == 0, (
                f"Shield must NOT be called on refusal; got "
                f"{shield_call_count['n']} call(s)"
            )
        finally:
            await db_conn.work_studio_exports.delete_one({"id": aid})
            await db_conn.work_studio_artefact_versions.delete_many({"artefact_id": aid})
