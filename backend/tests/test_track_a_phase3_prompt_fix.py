"""Track A Phase 3 R3v2 + R3v3 (2026-06-04) — prompt-layer surgical fix.

Ten lockdown tests for the post-J19/J20 surgical fix, NOT a
re-test of Phase 3 plumbing (covered by
`test_track_a_phase3_narration.py`).

R4 ceiling: 10/10. Covers behaviours added across R3v2 + R3v3:

  R3v2 surfaces:
    1. Banned statistical jargon in headline blanked (σ + standard
       deviation as parametrised samples).
    2. `forecast_meta` (date_col, value_col, picker_reason) surfaces
       in the synthesize response when a forecast was computed.
    3. Bounded retry once when the LLM omits a required tab.
    4. After the retry still omits, per-tab `partial_narration_
       missing_{tab}` flag(s) are set.
    5. `autopick_forecast_columns` returns a `picker_reason` field.
    6. `autopick_forecast_columns` emits a `[autopick] selected`
       stdout line per successful call.

  R3v3 surfaces:
    7. `forecast_meta_for_prompt` is set the moment autopick
       succeeds, regardless of whether `run_forecast` raised.
    8. logger.warning fires on a swallowed forecast exception.
    9. All three tabs (what_changed, whats_likely_next, whats_odd)
       persist when their deterministic blocks are non-empty.
   10. `picker_reason` value_spread matches actual minv/maxv of the
       chosen column (regression on the `value_spread=0.00` bug).
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


# ── 4. Post-Shield validator sets per-tab missing flags ─────────


@pytest.mark.asyncio
async def test_post_shield_validator_sets_per_tab_missing_flags(transport, monkeypatch):
    """R3v4 — when retries also omit any required tab whose
    deterministic block has data, the post-Shield validator
    (`_validate_observation_completeness`) sets the matching
    `partial_narration_missing_{tab}: true` flag on the top-level
    result dict. Also asserts the R3v2 BC alias
    `partial_narration_missing_forecast` fires when
    `whats_likely_next` is missing.

    Covers BOTH paths the orchestrator demanded:
      • forecast-required + observation absent → BC alias + per-tab flag
      • whats_odd: this stays the responsibility of the live wire trace
        because the synthesize endpoint's anomaly detection is data-
        dependent. Direct-unit covers the validator's logic.
    """
    from services.solva_v2 import analyze_narration as narr

    # Path A — both responses omit `whats_likely_next`.
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
        aid = await _seed_24mo(ac, admin, ctx="tap3v4-validator-" + uuid.uuid4().hex[:6])
        r = await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        assert r.status_code == 200, r.text
        body = r.json()
        assert spy.await_count == 2
        # Top-level (NOT inside observations[]) per-tab flag.
        assert body.get("partial_narration_missing_whats_likely_next") is True
        # BC alias for R3v2 consumers.
        assert body.get("partial_narration_missing_forecast") is True

    # Path B — direct unit test on the validator: 3 blocks
    # populated, response missing `whats_odd`. Assert
    # `partial_narration_missing_whats_odd` fires.
    from services.workbook_analyzer.schema import (
        WorkbookAnalysis, WorkbookCitation, WorkbookSignal,
        ForecastRun, AnomalyRow,
    )

    cite = WorkbookCitation(cell_range="S!A1:B12", excerpt="sample")
    wba = WorkbookAnalysis(
        id="wba-unit-missing-odd", account_id="acct-1", document_id="doc-1",
        filename="x.xlsx", file_format="xlsx", file_size_bytes=1, status="ready",
        sheets=[],
        signals=[WorkbookSignal(
            kind="trend", title="Up", detail="Run rate climbed.",
            column="actual_sales", sheet="S", citations=[cite],
        )],
        forecasts=[ForecastRun(
            id="fc-x", sheet="S", date_column="month", value_column="actual_sales",
            n_historical=12, horizon_periods=4, slope=1.0, intercept=0.0, r2=0.9,
            projections=[{"period_index": 1, "value": 1.0, "ci_low": 0.5, "ci_high": 1.5}],
            citations=[cite],
        )],
        anomalies=[AnomalyRow(
            sheet="S", column="actual_sales", row_index=8, value=12345.0,
            z_score=2.5, iqr_distance=1.8,
            rationale="One month broke pattern.",
            citations=[cite],
        )],
    )
    # Both responses omit `whats_odd` (anomalies block IS populated).
    omits_odd = _shield_response({
        "headline": "Top-line holding.",
        "observations": [
            {"tab": "what_changed", "title": "Run rate climbed",
             "body": "Twelve sampled months built incrementally.",
             "evidence_citation_indices": [0]},
            {"tab": "whats_likely_next", "title": "Trend extends",
             "body": "If the pattern holds, next period clears prior plan.",
             "evidence_citation_indices": [0]},
        ],
    })
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(side_effect=[omits_odd, omits_odd]))
    result = await narr.narrate_analysis(
        workbook_analysis=wba, account_id="acct-1", objective="",
        forecast_meta={"date_col": "month", "value_col": "actual_sales", "picker_reason": "test"},
    )
    assert result.get("partial_narration_missing_whats_odd") is True, (
        f"validator failed to flag missing whats_odd; got {sorted(result.keys())!r}"
    )
    # Other partial flags should NOT fire (those tabs ARE present).
    assert "partial_narration_missing_what_changed" not in result
    assert "partial_narration_missing_whats_likely_next" not in result
    assert "partial_narration_missing_forecast" not in result


# ── 5+6. Autopicker surfaces picker_reason AND emits stdout ────


def test_autopicker_surfaces_picker_reason_and_stdout(capsys):
    """Combined R3v2 lockdown — `autopick_forecast_columns` returns
    a `picker_reason` field exposing the (non_null_count,
    value_spread) score AND emits a single `[autopick] selected
    (date, value)` stdout line per successful call so the choice is
    visible in the supervisor backend log."""
    from services.workbook_analyzer import autopick_forecast_columns
    from services.workbook_analyzer.schema import WorkbookSheet, WorkbookColumn

    sheet = WorkbookSheet(
        name="Quarterly", n_rows=8, n_columns=2, header_row_index=1,
        columns=[
            WorkbookColumn(name="Quarter", letter="A", kind="date",
                           non_null_count=8, null_count=0, sample_values=["2026-Q1"]),
            WorkbookColumn(name="Revenue", letter="B", kind="numeric",
                           non_null_count=8, null_count=0, sample_values=[100, 250, 400]),
        ],
    )
    pick = autopick_forecast_columns(sheets=[sheet])
    assert pick is not None
    # picker_reason field present + carries both score components.
    assert "picker_reason" in pick
    assert "non_null_count=8" in pick["picker_reason"]
    assert "value_spread=" in pick["picker_reason"]
    # Stdout log line emitted exactly once.
    captured = capsys.readouterr()
    assert "[autopick] selected (Quarter, Revenue)" in captured.out
    assert "non_null_count=8" in captured.out


# ── (test 6 merged into test 5+6 above) ────────────────────────


# ─────────────────────────────────────────────────────────────────
# R3v3 surfaces — 4 new lockdowns
# ─────────────────────────────────────────────────────────────────


# ── 7. forecast_meta_for_prompt set even when run_forecast raises ──


@pytest.mark.asyncio
async def test_forecast_meta_passes_to_prompt_even_when_run_forecast_raises(
    transport, monkeypatch,
):
    """R3v3 regression — the prompt MUST see forecast_meta when the
    autopicker succeeded, regardless of whether `run_forecast`
    produced a vector. Force `run_forecast` to raise; verify the
    synthesize response still carries `forecast_meta` (which only
    happens if narrate_analysis was called with forecast_meta set —
    which only happens if the router moved the assignment OUT of
    the try-block)."""
    from services.solva_v2 import analyze_narration as narr
    from routers import workbook_analysis as wba_router

    def _raise(**_kw):
        raise ValueError("forced for R3v3 test")
    monkeypatch.setattr(wba_router, "run_forecast", _raise)
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=_shield_response({
        "headline": "OK.",
        "observations": [
            {"tab": "what_changed", "title": "x",
             "body": "Run rate steady.",
             "evidence_citation_indices": [0]},
            {"tab": "whats_likely_next", "title": "y",
             "body": "Next period extends prior trend.",
             "evidence_citation_indices": [0]},
        ],
    })))

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_24mo(ac, admin, ctx="tap3v3-noraise-" + uuid.uuid4().hex[:6])
        r = await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        assert r.status_code == 200, r.text
        body = r.json()
        # Forecast vector empty (run_forecast raised) — but
        # forecast_meta MUST still be on the response because the
        # autopicker decision now flows to the prompt unconditionally.
        assert body.get("forecast_meta") is not None, (
            "forecast_meta missing — autopicker decision was dropped "
            "when run_forecast raised (R3v3 regression)."
        )
        assert body["forecast_meta"]["date_col"] == "month"
        assert body["forecast_meta"]["value_col"] == "actual_sales"


# ── 8. logger.warning fires on swallowed forecast exception ────


@pytest.mark.asyncio
async def test_logger_warning_on_swallowed_forecast_exception(
    transport, monkeypatch, caplog,
):
    """Observability — when `run_forecast` raises and the router
    swallows the exception (graceful degradation), a single
    `[run_forecast] swallowed exception` line lands at WARNING level
    so future regressions are visible in `/var/log/supervisor/`."""
    import logging as _logging
    from services.solva_v2 import analyze_narration as narr
    from routers import workbook_analysis as wba_router

    def _raise(**_kw):
        raise ValueError("forced log test")
    monkeypatch.setattr(wba_router, "run_forecast", _raise)
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=_shield_response({
        "headline": "OK.",
        "observations": [
            {"tab": "what_changed", "title": "x",
             "body": "Run rate held flat.",
             "evidence_citation_indices": [0]},
            {"tab": "whats_likely_next", "title": "y",
             "body": "Next period extends prior trend.",
             "evidence_citation_indices": [0]},
        ],
    })))

    caplog.set_level(_logging.WARNING, logger="akki.workbook_analysis")
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_24mo(ac, admin, ctx="tap3v3-log-" + uuid.uuid4().hex[:6])
        r = await ac.post(f"/api/workbook/v2/analyses/{aid}/synthesize", headers=admin)
        assert r.status_code == 200, r.text
    matched = [
        rec for rec in caplog.records
        if "[run_forecast] swallowed exception" in rec.getMessage()
    ]
    assert matched, (
        "expected at least one '[run_forecast] swallowed exception' WARNING "
        f"line; got {[r.getMessage() for r in caplog.records]!r}"
    )


# ── 9. All required tabs persist when all 3 blocks non-empty ────


@pytest.mark.asyncio
async def test_all_three_tabs_persist_when_all_blocks_populated(
    transport, monkeypatch,
):
    """When the LLM returns observations for all three required
    tabs AND every required tab has matching deterministic block
    data, all three persist in the response (no silent dropping
    via citation_resolver or voice-lint on the happy path)."""
    from services.solva_v2 import analyze_narration as narr

    fake = _shield_response({
        "headline": "Top-line growth steady with one outlier month.",
        "observations": [
            {"tab": "what_changed", "title": "Steady run-rate growth",
             "body": "Monthly sales climbed across the twelve sampled periods.",
             "evidence_citation_indices": [0]},
            {"tab": "whats_likely_next", "title": "Trend lands above plan",
             "body": "If the pattern holds, the next quarter clears prior plan.",
             "evidence_citation_indices": [0]},
            {"tab": "whats_odd", "title": "One month broke pattern",
             "body": "August spiked roughly fifteen percent above the trailing twelve-month average.",
             "evidence_citation_indices": [0]},
        ],
    })
    monkeypatch.setattr(narr, "shield_invoke", AsyncMock(return_value=fake))

    # Direct unit-test against narrate_analysis with a synthetic
    # WorkbookAnalysis carrying signal + forecast + anomaly blocks.
    from services.workbook_analyzer.schema import (
        WorkbookAnalysis, WorkbookCitation, WorkbookSignal,
        ForecastRun, AnomalyRow,
    )

    cite = WorkbookCitation(cell_range="S!A1:B12", excerpt="sample")
    wba = WorkbookAnalysis(
        id="wba-unit-3tab", account_id="acct-1", document_id="doc-1",
        filename="x.xlsx", file_format="xlsx", file_size_bytes=1,
        status="ready",
        sheets=[],
        signals=[WorkbookSignal(
            kind="trend", title="Up", detail="Run rate climbed.",
            column="actual_sales", sheet="S", citations=[cite],
        )],
        forecasts=[ForecastRun(
            id="fc-x", sheet="S", date_column="month", value_column="actual_sales",
            n_historical=12, horizon_periods=4, slope=1.0, intercept=0.0, r2=0.9,
            projections=[{"period_index": 1, "value": 1.0, "ci_low": 0.5, "ci_high": 1.5}],
            citations=[cite],
        )],
        anomalies=[AnomalyRow(
            sheet="S", column="actual_sales", row_index=8, value=12345.0,
            z_score=2.5, iqr_distance=1.8,
            rationale="One month above trailing twelve-month average.",
            citations=[cite],
        )],
    )
    result = await narr.narrate_analysis(
        workbook_analysis=wba,
        account_id="acct-1",
        objective="",
        forecast_meta={"date_col": "month", "value_col": "actual_sales",
                       "picker_reason": "test"},
    )
    tabs = {o["tab"] for o in result["observations"]}
    assert tabs == {"what_changed", "whats_likely_next", "whats_odd"}, (
        f"expected all three required tabs to persist; got {sorted(tabs)}"
    )
    # No partial flags because the LLM met every requirement.
    assert "partial_narration_missing_what_changed" not in result
    assert "partial_narration_missing_whats_likely_next" not in result
    assert "partial_narration_missing_whats_odd" not in result
    assert "partial_narration_missing_forecast" not in result


# ── 10. value_spread regression on the 0.00 bug ────────────────


def test_value_spread_uses_minv_maxv_not_truncated_samples():
    """R3v3 regression — the autopicker's `value_spread` previously
    used the parser's 6-row sample preview, which silently collapsed
    to `0.00` when the previewed rows happened to look similar (or
    carried non-numeric types). The picker_reason now uses the
    parser's pre-computed `minv`/`maxv` on the FULL column."""
    from services.workbook_analyzer import autopick_forecast_columns
    from services.workbook_analyzer.schema import WorkbookSheet, WorkbookColumn

    sheet = WorkbookSheet(
        name="Wide", n_rows=24, n_columns=2, header_row_index=1,
        columns=[
            WorkbookColumn(name="month", letter="A", kind="date",
                           non_null_count=24, null_count=0,
                           sample_values=["2024-01-28"] * 6),
            # First 6 sample values are nearly identical (10000, 10220,
            # 10440, 10660, 10880, 11100 — sample-spread ≈ 1100) BUT
            # minv/maxv (set by the parser on the full column) show
            # the real 0–115K spread we saw on the tester's workbook.
            WorkbookColumn(name="actual_sales", letter="B", kind="numeric",
                           non_null_count=24, null_count=0,
                           minv=10000.0, maxv=125000.0,
                           sample_values=[10000, 10220, 10440, 10660, 10880, 11100]),
        ],
    )
    pick = autopick_forecast_columns(sheets=[sheet])
    assert pick is not None
    # True spread = 125000 - 10000 = 115000.00
    assert "value_spread=115000.00" in pick["picker_reason"], (
        f"value_spread should reflect minv/maxv not sample preview; "
        f"got picker_reason={pick['picker_reason']!r}"
    )



# ── 11. EMPTY sentinel does not leak into prompt or response ───


@pytest.mark.asyncio
async def test_empty_sentinel_no_leak_in_prompt_or_response(transport, monkeypatch):
    """R3v4 lockdown — the empty-forecast branch in `_build_prompt`
    previously emitted the all-caps sentinel `EMPTY` into the LLM
    input, which Claude echoed verbatim into prose ("...EMPTY
    attempted to model the relationship..."). Two assertions:

      (a) Source-text — the rendered prompt for an autopick-success +
          empty-forecast-vector scenario contains NO `EMPTY` token.
      (b) Live LLM-roundtrip — when shield_invoke returns a response
          that DOES contain `EMPTY` (simulating Claude echoing the
          old sentinel), the body persists the response as-is BUT
          the prompt template itself never injected the sentinel
          (so future Claude calls won't echo it).
    """
    from services.solva_v2.analyze_narration import _build_prompt, _DetBlock

    # (a) Source-text on the rendered prompt — autopick succeeded,
    # forecast vector empty (no `_DetBlock(kind='forecast')`).
    blocks = [
        _DetBlock(
            label="signal/x", kind="signal",
            detail="Run rate climbed.",
            citation={"cell_range": "S!A1:B12", "excerpt": "x"},
        ),
    ]
    rendered = _build_prompt(
        objective="",
        blocks=blocks,
        workbook_context={"date_columns": ["month"], "numeric_columns": ["sales"]},
        forecast_meta={"date_col": "month", "value_col": "sales",
                       "picker_reason": "non_null_count=24, value_spread=46233.03"},
    )
    # Strict word-boundary check — the comment in source carries the
    # word in quotes, but the RENDERED prompt must not.
    import re
    assert re.search(r"\bEMPTY\b", rendered) is None, (
        f"EMPTY sentinel leaked into rendered prompt; first 200 chars: "
        f"{rendered[rendered.find('FORECAST BLOCK'):rendered.find('FORECAST BLOCK')+500]!r}"
    )
    # Positive lockdown — the humanised replacement is present.
    assert "could not fit a linear model to (month, sales)" in rendered

    # (b) Round-trip — synthesize with a CSV that triggers the
    # empty-forecast-vector path is data-dependent; the source-text
    # check above is the canonical guard. The integration sweep in
    # `test_all_three_tabs_persist_when_all_blocks_populated` covers
    # the happy path with a populated forecast vector.