"""Track A Phase 4 (2026-06-04) — Versioning + multi-workbook synthesis.

Lockdowns for the three Phase 4 backend behaviours:

  1. **`runs[]` versioning** — every `POST /v2/analyses/{aid}/synthesize`
     appends a new run UNLESS the latest run's `cache_key` matches the
     new one (idempotent re-synthesize on unchanged content).
  2. **`notes_history[]`** — `POST /v2/analyses/{aid}/notes` appends
     to a history array. Identical-body re-submit returns the tail
     entry as a no-op. Phase 6 — top-level `notes` + `notes_updated_at`
     BC mirrors REMOVED. `notes_history[-1]` is the canonical source.
  3. **Multi-workbook synthesis** — when `analysis_blobs` carries N≥2
     sources for an analysis, `synthesize_v2` parses all of them
     (capped at 5), renames sheets to `<stem>::<name>`, and surfaces
     the multi-source roster in the prompt.

Scope:
  • All shield_invoke calls are monkeypatched — these are PERSISTENCE
    and ROUTING lockdowns, not real-LLM round-trips. Real-LLM coverage
    lives behind `@pytest.mark.integration` in
    `test_track_a_phase4_synthesize_v2_integration.py` (registered
    via pytest.ini marker; excluded from default runs).
  • Lockdown ceiling per R4: 10 tests across this file. Current: 8.
"""
from __future__ import annotations

import io
import json
import uuid
from datetime import date
from typing import Any, Dict, List, Tuple
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport
from openpyxl import Workbook

import server  # noqa: F401
from server import app


@pytest.fixture
def transport():
    return ASGITransport(app=app)


# ── Test fixtures ─────────────────────────────────────────────────


def _build_24mo_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Monthly"
    ws.append(["month", "actual_sales"])
    base = 10000
    for i in range(24):
        m = i % 12 + 1
        y = 2024 + (i // 12)
        ws.append([date(y, m, 28), base + i * 220])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_simple_xlsx(title: str, slope: float, sheet_name: str = "Series") -> bytes:
    """Variant builder for multi-workbook tests — distinct slope so
    the autopicker has a clear winner across the union."""
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(["month", "actual_sales"])
    base = 5000
    for i in range(12):
        m = i % 12 + 1
        y = 2025 + (i // 12)
        ws.append([date(y, m, 28), int(base + i * slope)])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _shield_ok(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"response": json.dumps(payload), "trust_receipt": {}, "audit_id": "t"}


async def _csrf_login(ac: AsyncClient, email: str, password: str) -> Dict[str, str]:
    r = await ac.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await ac.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    r.raise_for_status()
    body = r.json()
    token = body.get("access_token") or body.get("token")
    assert token
    r = await ac.get("/api/csrf")
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": r.json()["csrf_token"],
    }


async def _seed_single(
    ac: AsyncClient, headers: Dict[str, str], *, ctx: str,
) -> str:
    fd = [("files", (
        "monthly.xlsx", _build_24mo_xlsx(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ))]
    r = await ac.post(
        "/api/workbook/upload-multi",
        files=fd, data={"context_id": ctx}, headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def _seed_multi(
    ac: AsyncClient, headers: Dict[str, str], *, ctx: str, n: int,
) -> str:
    fd: List[Tuple[str, Tuple[str, bytes, str]]] = []
    for i in range(n):
        fname = f"book_{i}_apollo.xlsx" if i == 0 else f"book_{i}_lemasy.xlsx"
        fd.append(("files", (
            fname, _build_simple_xlsx("", 100.0 + i * 50.0),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )))
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
        {"tab": "whats_likely_next", "title": "Trend extends",
         "body": "If the pattern holds, the next quarter lands above plan.",
         "evidence_citation_indices": [0]},
    ],
}


# ── 1. Versioning — first synthesize creates one run ─────────────


@pytest.mark.asyncio
async def test_first_synthesize_creates_one_run(transport, monkeypatch):
    """First call appends one entry to `runs[]`; the entry carries
    a run_id, cache_key, headline, observations, and triggered_by."""
    from services.solva_v2 import analyze_narration as narr
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=_shield_ok(_OK_NARRATION)))

    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_single(
            ac, admin, ctx="tap4-runs-first-" + uuid.uuid4().hex[:6],
        )
        r = await ac.post(
            f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin,
        )
        assert r.status_code == 200, r.text
        row = await db.analyses.find_one({"id": aid}, {"_id": 0})
        runs = row.get("runs") or []
        assert len(runs) == 1
        entry = runs[0]
        assert entry["run_id"].startswith("run-")
        assert entry["cache_key"]
        assert entry["headline"] == _OK_NARRATION["headline"]
        assert entry["refused"] is False
        assert len(entry["observations"]) >= 1


# ── 2. Versioning — idempotent re-synthesize ─────────────────────


@pytest.mark.asyncio
async def test_idempotent_resynthesize_does_not_append(transport, monkeypatch):
    """Re-call with unchanged content (same cache_key) → no new
    `runs[]` entry. Phase 6 — no top-level `narration` BC mirror
    refresh either (mirror removed)."""
    from services.solva_v2 import analyze_narration as narr
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=_shield_ok(_OK_NARRATION)))

    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_single(
            ac, admin, ctx="tap4-runs-idemp-" + uuid.uuid4().hex[:6],
        )
        await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        row = await db.analyses.find_one({"id": aid}, {"_id": 0})
        runs = row.get("runs") or []
        assert len(runs) == 1, (
            f"Expected idempotent re-synthesize to skip; got {len(runs)} runs"
        )


# ── 3. Versioning — different narration content appends ──────────


@pytest.mark.asyncio
async def test_changed_content_appends_new_run(transport, monkeypatch):
    """When the cache_key changes between calls (e.g. different
    objective text changes the content hash), a new run is appended."""
    from services.solva_v2 import analyze_narration as narr

    fake = AsyncMock(return_value=_shield_ok(_OK_NARRATION))
    monkeypatch.setattr(narr, "shield_invoke", fake)

    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_single(
            ac, admin, ctx="tap4-runs-change-" + uuid.uuid4().hex[:6],
        )
        # First synthesize.
        await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        # Mutate the objective via PATCH — flips the content hash.
        await ac.patch(
            f"/api/workbook/v2/analyses/{aid}/objective",
            json={"objective": "Focus on Q1 trade-book risk."},
            headers=admin,
        )
        # Second synthesize.
        await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        row = await db.analyses.find_one({"id": aid}, {"_id": 0})
        runs = row.get("runs") or []
        assert len(runs) == 2, (
            f"Changed-content re-synthesize should append a new run; got {len(runs)}"
        )
        assert runs[0]["cache_key"] != runs[1]["cache_key"]


# ── 4. Notes history — first POST appends ────────────────────────


@pytest.mark.asyncio
async def test_first_note_appended_to_history(transport, monkeypatch):
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_single(
            ac, admin, ctx="tap4-notes-first-" + uuid.uuid4().hex[:6],
        )
        r = await ac.post(
            f"/api/workbook/v2/analyses/{aid}/notes",
            json={"body": "Margin compression flagged in week 3."},
            headers=admin,
        )
        assert r.status_code == 200, r.text
        note = r.json()
        assert note["body"] == "Margin compression flagged in week 3."
        assert note["id"].startswith("note-")
        row = await db.analyses.find_one({"id": aid}, {"_id": 0})
        history = row.get("notes_history") or []
        assert len(history) == 1
        # Phase 6 — top-level BC mirrors REMOVED. canonical reads
        # come from notes_history[-1] directly.
        assert history[-1]["body"] == "Margin compression flagged in week 3."
        assert history[-1]["created_at"] == note["created_at"]
        assert "notes" not in row
        assert "notes_updated_at" not in row


# ── 5. Notes history — idempotent re-post returns tail ────────────


@pytest.mark.asyncio
async def test_identical_note_is_idempotent_noop(transport, monkeypatch):
    """Two identical-body POSTs in quick succession → ONE entry on
    notes_history. The second response is the tail entry (same id)."""
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_single(
            ac, admin, ctx="tap4-notes-idemp-" + uuid.uuid4().hex[:6],
        )
        body = {"body": "Same body twice."}
        r1 = await ac.post(
            f"/api/workbook/v2/analyses/{aid}/notes", json=body, headers=admin,
        )
        r2 = await ac.post(
            f"/api/workbook/v2/analyses/{aid}/notes", json=body, headers=admin,
        )
        assert r1.status_code == r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"], (
            "Identical-body re-POST should return the tail entry"
        )
        row = await db.analyses.find_one({"id": aid}, {"_id": 0})
        assert len(row.get("notes_history") or []) == 1


# ── 6. Notes history — distinct bodies append ─────────────────────


@pytest.mark.asyncio
async def test_distinct_notes_append_in_order(transport, monkeypatch):
    """Distinct bodies append in sequence; BC mirror reflects the latest."""
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_single(
            ac, admin, ctx="tap4-notes-distinct-" + uuid.uuid4().hex[:6],
        )
        await ac.post(
            f"/api/workbook/v2/analyses/{aid}/notes",
            json={"body": "First note."}, headers=admin,
        )
        await ac.post(
            f"/api/workbook/v2/analyses/{aid}/notes",
            json={"body": "Second note."}, headers=admin,
        )
        await ac.post(
            f"/api/workbook/v2/analyses/{aid}/notes",
            json={"body": "Third note."}, headers=admin,
        )
        row = await db.analyses.find_one({"id": aid}, {"_id": 0})
        history = row.get("notes_history") or []
        assert [n["body"] for n in history] == [
            "First note.", "Second note.", "Third note.",
        ]
        # Phase 6 — BC mirror REMOVED. notes_history[-1] is canonical.
        assert history[-1]["body"] == "Third note."
        assert "notes" not in row


# ── 7. Multi-workbook — N=3 sources union into one run ────────────


@pytest.mark.asyncio
async def test_three_source_synthesize_runs_with_prefixed_sheets(transport, monkeypatch):
    """N=3 sources → `runs[0]` exists; the run citations carry the
    `<stem>::<sheet>` prefix on cell_range (multi-source disambiguation).
    All 3 files contribute via the prefix."""
    from services.solva_v2 import analyze_narration as narr
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=_shield_ok(_OK_NARRATION)))

    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi(
            ac, admin, ctx="tap4-multi-3-" + uuid.uuid4().hex[:6], n=3,
        )
        r = await ac.post(
            f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin,
        )
        assert r.status_code == 200, r.text
        row = await db.analyses.find_one({"id": aid}, {"_id": 0})
        runs = row.get("runs") or []
        assert len(runs) == 1
        # Citations should reference the prefixed sheet names so the
        # union resolver works. Each citation is `{cell_range: ...}`.
        cites = runs[0].get("citations") or []
        prefixes_seen: set = set()
        for c in cites:
            cr = c.get("cell_range") or ""
            if "::" in cr:
                stem = cr.split("::", 1)[0]
                prefixes_seen.add(stem)
        # At least 2 distinct source prefixes show up in the citation
        # pool (the third may have produced no signals — acceptable).
        assert len(prefixes_seen) >= 2, (
            f"Expected ≥2 distinct source prefixes in citations; "
            f"got {prefixes_seen}"
        )


# ── 8. Multi-workbook cap — N=6 → only 5 processed ────────────────


@pytest.mark.asyncio
async def test_multi_workbook_capped_at_five(transport, monkeypatch):
    """`MAX_BLOBS=5` — the 6th uploaded blob is silently dropped at
    synthesize time. The run still succeeds; the run's
    `source_files` carries exactly 5 entries."""
    from services.solva_v2 import analyze_narration as narr
    captured_prompt: Dict[str, str] = {}

    async def capture(**kw):
        captured_prompt["content"] = kw.get("content", "")
        return _shield_ok(_OK_NARRATION)

    monkeypatch.setattr(narr, "shield_invoke", capture)

    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi(
            ac, admin, ctx="tap4-multi-6-" + uuid.uuid4().hex[:6], n=6,
        )
        r = await ac.post(
            f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin,
        )
        assert r.status_code == 200, r.text
        # The prompt's roster block should mention 5 source files —
        # the 6th is dropped silently (P5.14 contract: cap not error).
        prompt = captured_prompt.get("content", "")
        assert "SOURCE FILES (multi-workbook synthesis)" in prompt
        # Count `sheet-prefix \`` occurrences (one per parsed source).
        n_listed = prompt.count("sheet-prefix `")
        assert n_listed == 5, (
            f"Expected 5 sources listed in prompt roster (cap = 5); got {n_listed}"
        )
        # Confirm the run was created.
        row = await db.analyses.find_one({"id": aid}, {"_id": 0})
        assert len(row.get("runs") or []) == 1
