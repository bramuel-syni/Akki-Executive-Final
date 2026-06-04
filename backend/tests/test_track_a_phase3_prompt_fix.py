"""Track A Phase 3 R3v2 (2026-06-04) — prompt-layer surgical fix.

Six lockdown tests for the post-J19/J20 surgical fix, NOT a
re-test of Phase 3 plumbing (covered by
`test_track_a_phase3_narration.py`).

R4 ceiling: 6/10. This file ONLY covers behaviours added in the
2026-06-04T05 dispatch:

  1. Banned statistical jargon in headline blanked (σ + standard
     deviation as parametrised samples).
  2. `forecast_meta` (date_col, value_col, picker_reason) surfaces
     in the synthesize response when a forecast was computed.
  3. Bounded retry once when the LLM omits `whats_likely_next`.
  4. After the retry still omits, `partial_narration_missing_forecast:
     true` is set on the response.
  5. `autopick_forecast_columns` returns a `picker_reason` field.
  6. `autopick_forecast_columns` emits a `[autopick] selected` stdout
     line per successful call.
"""
from __future__ import annotations

import io
import json
import uuid
from datetime import date
from typing import Any, Dict
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


def _build_24mo_csv() -> bytes:
    """Build a 24-month CSV the tester used: month-end dates +
    monthly actual sales. Mimics the J19/J20 input shape."""
    rows = ["month,actual_sales"]
    base = 10000
    for i in range(24):
        m = i % 12 + 1
        y = 2024 + (i // 12)
        d = f"{y}-{m:02d}-28"
        # Modest growth + small noise so the autopicker scores high.
        v = base + i * 220 + (1500 if i == 17 else 0)
        rows.append(f"{d},{v}")
    return ("\n".join(rows) + "\n").encode("utf-8")


def _build_24mo_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Monthly"
    ws.append(["month", "actual_sales"])
    base = 10000
    for i in range(24):
        m = i % 12 + 1
        y = 2024 + (i // 12)
        ws.append([date(y, m, 28), base + i * 220 + (1500 if i == 17 else 0)])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


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


async def _seed_24mo(ac: AsyncClient, headers: Dict[str, str], *, ctx: str) -> str:
    fd = [("files", ("monthly.xlsx", _build_24mo_xlsx(),
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    r = await ac.post(
        "/api/workbook/upload-multi",
        files=fd, data={"context_id": ctx}, headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _shield_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"response": json.dumps(payload), "trust_receipt": {}, "audit_id": "test"}


# ── 1. Banned statistical jargon in headline ─────────────────────


@pytest.mark.parametrize("bad_headline", [
    "Revenue ran 2.11σ above the mean across the trade book.",
    "Q1 actual sales standard deviation widened 14% YoY.",
    "Pricing-power variance lifted three regions above plan.",
    "January readings sit in the 95th percentile of the prior twelve months.",
])
@pytest.mark.asyncio
async def test_banned_jargon_in_headline_blanked(transport, monkeypatch, bad_headline):
    """The McKinsey-tone headline must never carry σ / standard
    deviation / variance / percentile. Sources tab keeps the raw
    stats. On hit: blank the headline (NOT the whole narration —
    observations still render)."""
    from services.solva_v2 import analyze_narration as narr

    fake = _shield_response({
        "headline": bad_headline,
        "observations": [
            {"tab": "what_changed", "title": "Top-line moved",
             "body": "Twelve-month run rate lifted three points across the book.",
             "evidence_citation_indices": [0]},
        ],
    })
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=fake))

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_24mo(ac, admin, ctx="tap3v2-jargon-" + uuid.uuid4().hex[:6])
        r = await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        assert r.status_code == 200, r.text
        body = r.json()
        # Banned-jargon headline → blanked.
        assert body["headline"] == "", (
            f"banned-jargon headline survived: {body['headline']!r}"
        )
        # Observations preserved (drop is headline-only).
        titles = [o["title"] for o in body.get("observations") or []]
        assert "Top-line moved" in titles


# ── 2. forecast_meta surfaces in response ────────────────────────


@pytest.mark.asyncio
async def test_forecast_meta_surfaces_in_response(transport, monkeypatch):
    """When a forecast is computed, the synthesize response carries
    `forecast_meta: {date_col, value_col, picker_reason}` so the
    FE drawer can show the autopicker's choice."""
    from services.solva_v2 import analyze_narration as narr

    fake = _shield_response({
        "headline": "Top-line growth held through Q3.",
        "observations": [
            {"tab": "what_changed", "title": "Steady growth",
             "body": "Monthly run rate climbed across the twelve sampled periods.",
             "evidence_citation_indices": [0]},
            {"tab": "whats_likely_next", "title": "Trend extends",
             "body": "If the pattern holds, the next quarter lands four points above plan.",
             "evidence_citation_indices": [0]},
        ],
    })
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=fake))

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_24mo(ac, admin, ctx="tap3v2-fmeta-" + uuid.uuid4().hex[:6])
        r = await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        assert r.status_code == 200, r.text
        body = r.json()
        fm = body.get("forecast_meta")
        assert fm is not None, "forecast_meta missing from response"
        assert fm.get("date_col") == "month"
        assert fm.get("value_col") == "actual_sales"
        assert isinstance(fm.get("picker_reason"), str)
        assert "non_null_count" in fm["picker_reason"]


# ── 3. Bounded retry once when whats_likely_next missing ────────


@pytest.mark.asyncio
async def test_bounded_retry_when_whats_likely_next_omitted(transport, monkeypatch):
    """If the LLM's first response carries a forecast input but no
    `whats_likely_next` observation, narrate_analysis bounded-
    retries (max 1) with a stern reminder. Verify shield_invoke was
    called exactly twice and the retry's narration is the one that
    persists."""
    from services.solva_v2 import analyze_narration as narr

    first = _shield_response({
        "headline": "Growth steady.",
        "observations": [
            {"tab": "what_changed", "title": "Only what_changed",
             "body": "Run rate held flat sequentially.",
             "evidence_citation_indices": [0]},
        ],
    })
    retry = _shield_response({
        "headline": "Growth steady, forecast extends.",
        "observations": [
            {"tab": "what_changed", "title": "Only what_changed",
             "body": "Run rate held flat sequentially.",
             "evidence_citation_indices": [0]},
            {"tab": "whats_likely_next", "title": "Forecast on after retry",
             "body": "If the pattern holds, the next quarter clears prior plan.",
             "evidence_citation_indices": [0]},
        ],
    })
    spy = AsyncMock(side_effect=[first, retry])
    monkeypatch.setattr(narr, "shield_invoke", spy)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_24mo(ac, admin, ctx="tap3v2-retry-" + uuid.uuid4().hex[:6])
        r = await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        assert r.status_code == 200, r.text
        body = r.json()
        assert spy.await_count == 2, (
            f"expected 2 shield_invoke calls (1 + 1 retry); got {spy.await_count}"
        )
        titles = [o["title"] for o in body.get("observations") or []]
        assert "Forecast on after retry" in titles
        # Retry succeeded → partial flag NOT set.
        assert "partial_narration_missing_forecast" not in body


# ── 4. partial_narration_missing_forecast flag when retry also fails ──


@pytest.mark.asyncio
async def test_partial_flag_when_retry_also_omits_forecast(transport, monkeypatch):
    """If BOTH the first call AND the retry omit
    `whats_likely_next`, the response carries
    `partial_narration_missing_forecast: true` so the FE can render
    a 'forecast not narrated' surface."""
    from services.solva_v2 import analyze_narration as narr

    missing = _shield_response({
        "headline": "Still missing forecast.",
        "observations": [
            {"tab": "what_changed", "title": "What changed only",
             "body": "Run rate flat for twelve months.",
             "evidence_citation_indices": [0]},
        ],
    })
    spy = AsyncMock(side_effect=[missing, missing])
    monkeypatch.setattr(narr, "shield_invoke", spy)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_24mo(ac, admin, ctx="tap3v2-partial-" + uuid.uuid4().hex[:6])
        r = await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        assert r.status_code == 200, r.text
        body = r.json()
        assert spy.await_count == 2
        assert body.get("partial_narration_missing_forecast") is True


# ── 5. Autopicker picker_reason surfacing ───────────────────────


def test_autopicker_returns_picker_reason():
    """`autopick_forecast_columns` now returns a `picker_reason`
    field exposing the (non_null_count, value_spread) score so the
    synthesize endpoint can surface the choice to the user."""
    from services.workbook_analyzer import autopick_forecast_columns
    from services.workbook_analyzer.schema import WorkbookSheet, WorkbookColumn

    sheet = WorkbookSheet(
        name="Quarterly", n_rows=8, n_columns=3, header_row_index=1,
        columns=[
            WorkbookColumn(name="Quarter", letter="A", kind="date",
                           non_null_count=8, null_count=0, sample_values=["2026-Q1"]),
            WorkbookColumn(name="Revenue", letter="B", kind="numeric",
                           non_null_count=8, null_count=0, sample_values=[100, 250, 400]),
        ],
    )
    pick = autopick_forecast_columns(sheets=[sheet])
    assert pick is not None
    assert "picker_reason" in pick
    assert "non_null_count=8" in pick["picker_reason"]
    assert "value_spread=" in pick["picker_reason"]


# ── 6. Autopicker emits stdout log line ─────────────────────────


def test_autopicker_emits_stdout_log_line(capsys):
    """Single `[autopick] selected (date, value)` line emitted per
    successful call so the choice is visible in the supervisor
    backend log + headless harness output."""
    from services.workbook_analyzer import autopick_forecast_columns
    from services.workbook_analyzer.schema import WorkbookSheet, WorkbookColumn

    sheet = WorkbookSheet(
        name="X", n_rows=5, n_columns=2, header_row_index=1,
        columns=[
            WorkbookColumn(name="D", letter="A", kind="date",
                           non_null_count=5, null_count=0, sample_values=["2026-01-01"]),
            WorkbookColumn(name="V", letter="B", kind="numeric",
                           non_null_count=5, null_count=0, sample_values=[1, 9, 50]),
        ],
    )
    autopick_forecast_columns(sheets=[sheet])
    captured = capsys.readouterr()
    assert "[autopick] selected (D, V)" in captured.out
    assert "non_null_count=5" in captured.out
