"""Track A Phase 3 — Solva narration + Bug #30 lockdowns.

R4 (≤10 tests). Strategy:
  - Mock Shield's `invoke()` for tests 1, 2, 4, 7 so the narration
    pipeline is deterministic and free of external dependencies.
  - Tests 3 + 9 exercise the citation_resolver + voice_lint inline.
  - Tests 5 + 6 hit the forecaster fix directly.
  - Tests 8 + 10 exercise tenant scope + regression on Phase 1/2
    endpoints.

Test inventory (9 of ≤10; #10 = voice-lint delegated to scripts):
 1. Synthesize endpoint returns headline + observations + citations,
    tenant-scoped
 2. Idempotent: re-call same Analysis → cached narration (same key)
 3. Citation resolver: out-of-range indices dropped
 4. Refuse-to-decide: empty deterministic output → empty narration
 5. Bug #30: workbook with 1 date + 3 numeric cols picks highest-
    variance numeric pair
 6. Bug #30: workbook with 1 date + 1 numeric still works
 7. Tenant scope on synthesize
 8. Phase 1 + 2 regressions (exports + objective + notes still work)
 9. Voice-lint applied: narration containing banned voice is dropped
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport

import server  # noqa: F401
from server import app
from tests.fixtures.workbook_sample import build_sample_csv, build_sample_xlsx


@pytest.fixture
def transport():
    return ASGITransport(app=app)


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


async def _seed_multi(ac: AsyncClient, headers: Dict[str, str], *, ctx: str) -> str:
    fd = [
        ("files", ("a.csv", build_sample_csv(), "text/csv")),
        ("files", ("b.csv", build_sample_csv(), "text/csv")),
    ]
    r = await ac.post(
        "/api/workbook/upload-multi",
        files=fd, data={"context_id": ctx}, headers=headers,
    )
    assert r.status_code == 200
    return r.json()["id"]


def _shield_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"response": json.dumps(payload), "trust_receipt": {}, "audit_id": "test"}


# ─── Tests 1 + 2 — happy-path synthesize + idempotency ─────────


@pytest.mark.asyncio
async def test_synthesize_returns_narration_payload(transport, monkeypatch):
    from services.solva_v2 import analyze_narration as narr

    fake = _shield_response({
        "headline": "Q3 actuals trended higher than the plan.",
        "observations": [
            {
                "tab": "what_changed",
                "title": "Top-of-funnel growth held",
                "body": "Visits climbed 8% sequentially across the three sampled weeks.",
                "evidence_citation_indices": [0],
            },
        ],
    })
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=fake))

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi(ac, admin, ctx="tap3-ok-" + uuid.uuid4().hex[:6])
        r = await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["headline"].startswith("Q3 actuals")
        assert isinstance(body["observations"], list)
        assert isinstance(body.get("citations"), list)
        assert body["refused"] is False


# ─── R3 BLOCKER regression — fenced JSON from Claude ──────────


@pytest.mark.asyncio
async def test_synthesize_handles_fenced_json_from_claude(transport, monkeypatch):
    """R3 BLOCKER regression (2026-06-04).

    The previous test bench monkey-patched shield_invoke to return
    BARE JSON. The live Claude Sonnet wire response wraps the JSON
    in ```json … ``` markdown fences AND occasionally prepends a
    leading prose line. The parser must accept both shapes, OR the
    synthesize endpoint refuses with `llm_returned_non_json` even on
    a perfectly-good narration (the exact failure mode that broke
    J19 + J20).

    The fenced sample below is the literal wire format Claude
    returns. The test asserts the parser handles it and the
    synthesize endpoint populates a non-empty headline."""
    from services.solva_v2 import analyze_narration as narr

    fenced_wire = (
        "Here's the synthesis:\n"
        "```json\n"
        '{"headline": "Top-line growth slowed across three regions.", '
        '"observations": [ '
        '{"tab": "what_changed", "title": "Three regions slowed", '
        '"body": "EMEA, APAC, and LATAM grew at half the prior quarter pace.", '
        '"evidence_citation_indices": [0]} ]}\n'
        "```"
    )
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value={
        "response": fenced_wire,
        "trust_receipt": {}, "audit_id": "test-fenced",
    }))

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi(ac, admin, ctx="tap3-fence-" + uuid.uuid4().hex[:6])
        r = await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("refused") is False, (
            f"Parser refused fenced Claude output: {body.get('refusal_reason')!r}"
        )
        assert body["headline"] == "Top-line growth slowed across three regions."
        titles = [o["title"] for o in body.get("observations") or []]
        assert "Three regions slowed" in titles


@pytest.mark.asyncio
async def test_synthesize_idempotent_cache_key(transport, monkeypatch):
    from services.solva_v2 import analyze_narration as narr
    call_count = {"n": 0}
    async def _stub(**_kw):
        call_count["n"] += 1
        return _shield_response({
            "headline": "Cached read.",
            "observations": [
                {"tab": "what_changed", "title": "Stable", "body": "Run rate held flat.",
                 "evidence_citation_indices": [0]},
                # R3v3: each non-empty deterministic block requires its
                # matching tab; include all three so no retry fires and
                # the idempotency assertion holds.
                {"tab": "whats_likely_next", "title": "Trend extends",
                 "body": "If the pattern holds, next quarter clears prior plan.",
                 "evidence_citation_indices": [0]},
                {"tab": "whats_odd", "title": "Refund spike", "body": "One month broke pattern.",
                 "evidence_citation_indices": [0]},
            ],
        })
    monkeypatch.setattr(narr, "shield_invoke", _stub)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi(ac, admin, ctx="tap3-cache-" + uuid.uuid4().hex[:6])
        r1 = await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        r2 = await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        assert r1.json()["cache_key"] == r2.json()["cache_key"]
        # LLM called only the FIRST time — second call is a cache hit.
        assert call_count["n"] == 1


# ─── Test 3 — citation_resolver drops out-of-range refs ────────


@pytest.mark.asyncio
async def test_citation_resolver_drops_out_of_range(transport, monkeypatch):
    from services.solva_v2 import analyze_narration as narr

    # Index 99 is hallucinated; index 0 is valid.
    fake = _shield_response({
        "headline": "Cited correctly.",
        "observations": [
            {"tab": "what_changed", "title": "Good", "body": "Real.",
             "evidence_citation_indices": [0]},
            {"tab": "what_changed", "title": "Bad", "body": "Hallucinated cite.",
             "evidence_citation_indices": [99]},
        ],
    })
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=fake))

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi(ac, admin, ctx="tap3-cit-" + uuid.uuid4().hex[:6])
        r = await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        obs = r.json()["observations"]
        titles = [o["title"] for o in obs]
        assert "Good" in titles
        assert "Bad" not in titles, (
            "citation_resolver did not drop the out-of-range observation."
        )


# ─── Test 4 — refuse-to-decide: empty deterministic → empty narration ──


@pytest.mark.asyncio
async def test_refuse_to_decide_when_no_evidence(transport, monkeypatch):
    """Synthesize on an Analysis whose blobs were already purged
    must return an empty narration WITHOUT invoking the LLM."""
    from services.solva_v2 import analyze_narration as narr
    spy = AsyncMock(return_value=_shield_response({"headline": "BOGUS", "observations": []}))
    monkeypatch.setattr(narr, "shield_invoke", spy)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi(ac, admin, ctx="tap3-empty-" + uuid.uuid4().hex[:6])
        # Purge blobs first.
        await ac.post(f"/api/workbook/v2/analyses/{aid}/session-close", headers=admin)
        r = await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        assert r.status_code == 200
        body = r.json()
        assert body["refused"] is True
        assert body["headline"] == ""
        # LLM not invoked.
        spy.assert_not_called()


# ─── Tests 5 + 6 — Bug #30 forecaster auto-picker ──────────────


def test_forecast_autopicker_prefers_highest_variance_numeric():
    from services.workbook_analyzer import autopick_forecast_columns
    from services.workbook_analyzer.schema import WorkbookSheet, WorkbookColumn

    sheet = WorkbookSheet(
        name="Q3",
        n_rows=10, n_columns=4,
        header_row_index=1,
        columns=[
            WorkbookColumn(name="Date", letter="A", kind="date", non_null_count=10, null_count=0, sample_values=["2026-01-01"]),
            WorkbookColumn(name="Low",  letter="B", kind="numeric", non_null_count=10, null_count=0, sample_values=[1, 2, 3]),
            WorkbookColumn(name="Hi",   letter="C", kind="numeric", non_null_count=10, null_count=0, sample_values=[10, 50, 100]),
            WorkbookColumn(name="Med",  letter="D", kind="numeric", non_null_count=10, null_count=0, sample_values=[5, 10, 15]),
        ],
    )
    pick = autopick_forecast_columns(sheets=[sheet])
    assert pick is not None
    assert pick["date_column"] == "Date"
    # Highest variance is Hi (spread 90).
    assert pick["value_column"] == "Hi"


def test_forecast_autopicker_single_numeric_still_works():
    from services.workbook_analyzer import autopick_forecast_columns
    from services.workbook_analyzer.schema import WorkbookSheet, WorkbookColumn

    # Track A Phase 4 (2026-06-04) — autopicker density gate raised
    # the absolute non-null floor from 3 to 6 (Tightening 1 approved).
    # This regression test now uses 10 non-nulls to satisfy the gate
    # while still exercising the "single numeric column wins"
    # behaviour the test was originally locking down.
    sheet = WorkbookSheet(
        name="S",
        n_rows=10, n_columns=2,
        header_row_index=1,
        columns=[
            WorkbookColumn(name="Date", letter="A", kind="date",    non_null_count=10, null_count=0, sample_values=["2026-01-01"]),
            WorkbookColumn(name="Val",  letter="B", kind="numeric", non_null_count=10, null_count=0, minv=1.0, maxv=100.0, sample_values=[1, 2, 3]),
        ],
    )
    pick = autopick_forecast_columns(sheets=[sheet])
    assert pick is not None
    assert pick["value_column"] == "Val"
    # No-date sheet returns None.
    sheet.columns[0].kind = "categorical"
    pick = autopick_forecast_columns(sheets=[sheet])
    assert pick is None


# ─── Test 7 — tenant scope on synthesize ────────────────────────


@pytest.mark.asyncio
async def test_cross_tenant_synthesize_404(transport, monkeypatch):
    from services.solva_v2 import analyze_narration as narr
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=_shield_response({
        "headline": "x", "observations": [],
    })))
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi(ac, admin, ctx="tap3-tn-" + uuid.uuid4().hex[:6])
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        viewer = await _csrf_login(ac, "viewer@akki.ai", "Viewer2026!")
        r = await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=viewer)
        assert r.status_code == 404


# ─── Test 8 — Phase 1 + 2 regressions still pass ───────────────


@pytest.mark.asyncio
async def test_phase_1_and_2_regressions_still_pass(transport, monkeypatch):
    """Synthesize → drawer reads detail → exports + notes + objective
    all still functional on the same Analysis."""
    from services.solva_v2 import analyze_narration as narr
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=_shield_response({
        "headline": "Reg passed.",
        "observations": [{"tab": "what_changed", "title": "T", "body": "B",
                          "evidence_citation_indices": [0]}],
    })))
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi(ac, admin, ctx="tap3-reg-" + uuid.uuid4().hex[:6])
        # Synthesize first.
        await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        # Phase 2: objective patch
        r = await ac.patch(
            f"/api/workbook/v2/analyses/{aid}/objective",
            json={"objective": "Why?"}, headers=admin,
        )
        assert r.status_code == 200
        # Phase 2: note append
        r = await ac.post(
            f"/api/workbook/v2/analyses/{aid}/notes",
            json={"body": "noted"}, headers=admin,
        )
        assert r.status_code == 200
        # Phase 1: each export
        for ext in ("xlsx", "docx", "pptx"):
            r = await ac.get(
                f"/api/workbook/analyses/{aid}/report.{ext}", headers=admin,
            )
            assert r.status_code == 200
            assert r.content[:4] == b"PK\x03\x04"
        # Read picks up everything.
        # Phase 6 — top-level `notes` BC mirror REMOVED from API
        # response; consumers read `notes_history[]` directly.
        r = await ac.get(f"/api/workbook/v2/analyses/{aid}", headers=admin)
        body = r.json()
        assert body["headline"] == "Reg passed."
        assert body["objective"] == "Why?"
        assert len(body["notes_history"]) >= 1
        assert "notes" not in body
        assert "notes_updated_at" not in body
        assert "narration" not in body


# ─── Test 9 — voice-lint drops banned-voice observations ───────


@pytest.mark.asyncio
async def test_voice_lint_drops_banned_voice_observations(transport, monkeypatch):
    """If the LLM emits an observation whose body uses 'should',
    'recommend', etc., the voice-lint guard drops that observation
    before persistence."""
    from services.solva_v2 import analyze_narration as narr
    fake = _shield_response({
        "headline": "Clean headline.",
        "observations": [
            {"tab": "what_changed", "title": "Clean", "body": "Variance held steady.",
             "evidence_citation_indices": [0]},
            {"tab": "what_changed", "title": "Banned", "body": "I recommend you investigate.",
             "evidence_citation_indices": [0]},
            {"tab": "what_changed", "title": "Should-er", "body": "You should look at row 5.",
             "evidence_citation_indices": [0]},
        ],
    })
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=fake))
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi(ac, admin, ctx="tap3-vl-" + uuid.uuid4().hex[:6])
        r = await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        bodies = [o["body"] for o in r.json()["observations"]]
        assert "Variance held steady." in bodies
        assert "I recommend you investigate." not in bodies, (
            "voice-lint did not drop the 'recommend' observation"
        )
        assert "You should look at row 5." not in bodies, (
            "voice-lint did not drop the 'should' observation"
        )
