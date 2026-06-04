"""Track A Phase 4 (2026-06-04) — Forecaster noisy-drift tuning.

Lockdowns for two tuning surfaces introduced in Phase 4:

  1. **Autopick density gate** — `autopick_forecast_columns` rejects
     (date, numeric) pairs whose numeric column has either
     `non_null_count < _AUTOPICK_MIN_NON_NULL_COUNT` (6) OR
     `non_null_count / n_rows < _AUTOPICK_MIN_NON_NULL_RATIO` (0.30).
     Picker emits a `[autopick] rejected ...` line per skipped pair.

  2. **Low-R² safety-net flag** — when the engine fits the autopicked
     model and returns R² below `_FORECAST_LOW_R2_THRESHOLD` (0.30),
     `narrate_analysis` sets
     `partial_narration_missing_forecast_low_signal: true` on the
     result dict. The forecast block is preserved (not dropped).

Scope:
  • Lockdowns are purely **unit-level** — no `shield_invoke` call,
    no FastAPI surface. Phase 4 integration tests live separately in
    `test_track_a_phase4_synthesize_v2.py` (multi-workbook).
  • Density gate counts (Tightening 4): six (3 density-PASS + 3
    density-REJECT). Low-R² flag: three (high-R² no flag + low-R²
    flag fires + r2=None safe).
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from services.workbook_analyzer.forecaster import (
    _AUTOPICK_MIN_NON_NULL_COUNT,
    _AUTOPICK_MIN_NON_NULL_RATIO,
    _FORECAST_LOW_R2_THRESHOLD,
    autopick_forecast_columns,
)
from services.workbook_analyzer.schema import WorkbookColumn, WorkbookSheet


# ── Test fixtures ─────────────────────────────────────────────────


def _col(
    name: str,
    kind: str,
    *,
    non_null: int,
    minv: float = 0.0,
    maxv: float = 100.0,
) -> WorkbookColumn:
    return WorkbookColumn(
        name=name,
        letter="A",
        kind=kind,  # type: ignore[arg-type]
        non_null_count=non_null,
        null_count=0,
        minv=minv if kind == "numeric" else None,
        maxv=maxv if kind == "numeric" else None,
        sample_values=[],
    )


def _sheet(name: str, n_rows: int, cols: List[WorkbookColumn]) -> WorkbookSheet:
    return WorkbookSheet(name=name, n_rows=n_rows, n_columns=len(cols), columns=cols)


# ── Density gate — PASS path ──────────────────────────────────────


def test_autopick_passes_dense_numeric_column():
    """Numeric column with 30%+ density + ≥6 non-nulls is selected."""
    sheet = _sheet(
        "Sheet1", n_rows=20,
        cols=[
            _col("Date", "date", non_null=20),
            _col("Sales", "numeric", non_null=10, minv=10, maxv=200),
        ],
    )
    pick = autopick_forecast_columns(sheets=[sheet])
    assert pick is not None
    assert pick["date_column"] == "Date"
    assert pick["value_column"] == "Sales"


def test_autopick_passes_at_density_floor():
    """`non_null == _AUTOPICK_MIN_NON_NULL_COUNT` AND density at the
    `_AUTOPICK_MIN_NON_NULL_RATIO` floor → still picks."""
    # 6 non-nulls / 20 rows = 0.30 — exactly at the floor.
    sheet = _sheet(
        "Sheet1", n_rows=20,
        cols=[
            _col("Date", "date", non_null=20),
            _col("Sales", "numeric",
                 non_null=_AUTOPICK_MIN_NON_NULL_COUNT,
                 minv=0, maxv=50),
        ],
    )
    pick = autopick_forecast_columns(sheets=[sheet])
    assert pick is not None
    assert pick["value_column"] == "Sales"


def test_autopick_prefers_higher_density_when_tied():
    """When two numeric columns both pass density, the higher-density
    one wins (score = (non_null_count, spread))."""
    sheet = _sheet(
        "Sheet1", n_rows=20,
        cols=[
            _col("Date", "date", non_null=20),
            _col("Sparse", "numeric", non_null=10, minv=0, maxv=100),
            _col("Dense", "numeric", non_null=18, minv=0, maxv=100),
        ],
    )
    pick = autopick_forecast_columns(sheets=[sheet])
    assert pick is not None
    assert pick["value_column"] == "Dense"


# ── Density gate — REJECT path ────────────────────────────────────


def test_autopick_rejects_sparse_below_absolute_floor(capsys):
    """non_null < 6 → rejected even at 100% density."""
    sheet = _sheet(
        "Sheet1", n_rows=5,
        cols=[
            _col("Date", "date", non_null=5),
            _col("Sales", "numeric", non_null=5, minv=0, maxv=100),
        ],
    )
    pick = autopick_forecast_columns(sheets=[sheet])
    assert pick is None
    out = capsys.readouterr().out
    assert "[autopick] rejected" in out
    assert "non_null 5" in out


def test_autopick_rejects_below_density_ratio(capsys):
    """non_null=10 of 100 = 0.10 density (< 0.30) → rejected."""
    sheet = _sheet(
        "Sheet1", n_rows=100,
        cols=[
            _col("Date", "date", non_null=100),
            _col("Sparse", "numeric", non_null=10, minv=0, maxv=100),
        ],
    )
    pick = autopick_forecast_columns(sheets=[sheet])
    assert pick is None
    out = capsys.readouterr().out
    assert "[autopick] rejected" in out
    assert "density 0.10" in out


def test_autopick_rejects_just_below_density_floor(capsys):
    """Right at the boundary: density 0.29 (just below 0.30) →
    rejected. Confirms `<` (strict) comparison, not `≤`."""
    sheet = _sheet(
        "Sheet1", n_rows=100,
        cols=[
            _col("Date", "date", non_null=100),
            _col("Edge", "numeric", non_null=29, minv=0, maxv=100),
        ],
    )
    pick = autopick_forecast_columns(sheets=[sheet])
    assert pick is None


# ── Low-R² safety-net flag ────────────────────────────────────────
# narrate_analysis sets `partial_narration_missing_forecast_low_signal`
# when `forecast_meta.r2 < _FORECAST_LOW_R2_THRESHOLD`. We test the
# behaviour in isolation by exercising the result-construction surface.


@pytest.mark.asyncio
async def test_low_r2_flag_fires_on_noisy_fit(monkeypatch):
    """R² below threshold → flag fires on the result dict."""
    from services.solva_v2 import analyze_narration as an
    from services.workbook_analyzer.schema import (
        WorkbookAnalysis,
        WorkbookCitation,
        WorkbookSignal,
    )

    wa = WorkbookAnalysis(
        id="wba-test", account_id="acc-x", document_id="doc-x",
        filename="t.xlsx", file_format="xlsx", file_size_bytes=1,
        status="ready",
        signals=[WorkbookSignal(
            kind="trend", title="t", detail="d",
            column="c", sheet="s",
            citations=[WorkbookCitation(cell_range="s!A1:B2", excerpt="e")],
        )],
    )

    async def fake_invoke(**_kw):
        import json
        return {"response": json.dumps({
            "headline": "Bottom line.",
            "observations": [{
                "tab": "what_changed",
                "title": "T",
                "body": "Plain English.",
                "evidence_citation_indices": [0],
            }],
        })}

    monkeypatch.setattr(an, "shield_invoke", fake_invoke)
    result = await an.narrate_analysis(
        workbook_analysis=wa, account_id="acc-x",
        forecast_meta=[{
            "date_col": "Date", "value_col": "Sales",
            "picker_reason": "test", "r2": 0.10,  # noisy
        }],
    )
    assert result.get("partial_narration_missing_forecast_low_signal") is True
    # Track A Phase 4 iter-2 — forecast_meta is a List (Tightening 1).
    assert isinstance(result["forecast_meta"], list)
    assert result["forecast_meta"][0]["r2"] == 0.10  # preserved


@pytest.mark.asyncio
async def test_low_r2_flag_not_fired_on_clean_fit(monkeypatch):
    """R² above threshold → flag NOT set."""
    from services.solva_v2 import analyze_narration as an
    from services.workbook_analyzer.schema import (
        WorkbookAnalysis,
        WorkbookCitation,
        WorkbookSignal,
    )

    wa = WorkbookAnalysis(
        id="wba-test", account_id="acc-x", document_id="doc-x",
        filename="t.xlsx", file_format="xlsx", file_size_bytes=1,
        status="ready",
        signals=[WorkbookSignal(
            kind="trend", title="t", detail="d",
            column="c", sheet="s",
            citations=[WorkbookCitation(cell_range="s!A1:B2", excerpt="e")],
        )],
    )

    async def fake_invoke(**_kw):
        import json
        return {"response": json.dumps({
            "headline": "Bottom line.",
            "observations": [{
                "tab": "what_changed",
                "title": "T",
                "body": "Plain English.",
                "evidence_citation_indices": [0],
            }],
        })}

    monkeypatch.setattr(an, "shield_invoke", fake_invoke)
    result = await an.narrate_analysis(
        workbook_analysis=wa, account_id="acc-x",
        forecast_meta=[{
            "date_col": "Date", "value_col": "Sales",
            "picker_reason": "test", "r2": 0.85,  # clean
        }],
    )
    assert "partial_narration_missing_forecast_low_signal" not in result


@pytest.mark.asyncio
async def test_low_r2_flag_safe_when_r2_none(monkeypatch):
    """`r2 is None` (engine failed to fit) → flag NOT set (R3v5
    safety-net `partial_narration_missing_whats_likely_next` covers
    the "no fit at all" case)."""
    from services.solva_v2 import analyze_narration as an
    from services.workbook_analyzer.schema import (
        WorkbookAnalysis,
        WorkbookCitation,
        WorkbookSignal,
    )

    wa = WorkbookAnalysis(
        id="wba-test", account_id="acc-x", document_id="doc-x",
        filename="t.xlsx", file_format="xlsx", file_size_bytes=1,
        status="ready",
        signals=[WorkbookSignal(
            kind="trend", title="t", detail="d",
            column="c", sheet="s",
            citations=[WorkbookCitation(cell_range="s!A1:B2", excerpt="e")],
        )],
    )

    async def fake_invoke(**_kw):
        import json
        return {"response": json.dumps({
            "headline": "Bottom line.",
            "observations": [{
                "tab": "what_changed",
                "title": "T",
                "body": "Plain English.",
                "evidence_citation_indices": [0],
            }],
        })}

    monkeypatch.setattr(an, "shield_invoke", fake_invoke)
    result = await an.narrate_analysis(
        workbook_analysis=wa, account_id="acc-x",
        forecast_meta=[{
            "date_col": "Date", "value_col": "Sales",
            "picker_reason": "test",  # r2 absent
        }],
    )
    assert "partial_narration_missing_forecast_low_signal" not in result


# ── Threshold constant sanity ─────────────────────────────────────


def test_threshold_constants_documented_at_expected_values():
    """Document the canonical thresholds so a silent constant
    change requires a deliberate test-update."""
    assert _AUTOPICK_MIN_NON_NULL_COUNT == 6
    assert abs(_AUTOPICK_MIN_NON_NULL_RATIO - 0.30) < 1e-9
    assert abs(_FORECAST_LOW_R2_THRESHOLD - 0.30) < 1e-9
