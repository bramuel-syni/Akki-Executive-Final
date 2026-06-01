"""Phase P5.14 — Workbook analyzer Pydantic models.

Mongo collection: `workbook_analyses`.

A `WorkbookAnalysis` is created at upload time and accreted with
sheet/signal/simulation/forecast/anomaly entries as the user
drives the Analyze tab. Every numerical claim — signal, forecast
projection, anomaly score — carries one or more `WorkbookCitation`
entries pointing back to specific cells in the parsed workbook.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────
# Citation
# ─────────────────────────────────────────────────────────────────

CellRangePattern = r"^[^!]+![A-Z]+[0-9]+(:[A-Z]+[0-9]+)?$"


class WorkbookCitation(BaseModel):
    """One pointer into a cell or contiguous cell-range of the
    analysed workbook.

    `cell_range` shape: `"<sheet_name>!<TL>:<BR>"` (Excel A1 form)
    or a single cell `"<sheet_name>!<TL>"`. The resolver validates
    that the sheet exists AND the row/col range is within the
    parsed sheet bounds. Fabricated ranges trip
    `citation_unverifiable`.
    """
    source_kind: Literal["workbook_cell"] = "workbook_cell"
    cell_range: str = Field(
        ..., min_length=3, pattern=CellRangePattern,
        description="Excel-A1 reference: '<sheet>!<topleft>[:<bottomright>]'",
    )
    excerpt: str = Field(
        ..., min_length=1, max_length=400,
        description="Short observational excerpt of the cell content (verbatim or summarised numeric)",
    )


# ─────────────────────────────────────────────────────────────────
# Parsed workbook
# ─────────────────────────────────────────────────────────────────

ColumnKind = Literal["numeric", "date", "categorical", "text"]


class WorkbookColumn(BaseModel):
    name: str = Field(..., min_length=1)
    letter: str = Field(..., min_length=1, description="Excel column letter A/B/AA/…")
    kind: ColumnKind = Field(..., description="Inferred kind — user may override")
    non_null_count: int = Field(..., ge=0)
    null_count: int = Field(..., ge=0)
    # Numeric-only stats (None for non-numeric).
    minv: Optional[float] = None
    maxv: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    stddev: Optional[float] = None
    sample_values: List[Any] = Field(default_factory=list, description="First ≤6 non-null values for preview")


class WorkbookSheet(BaseModel):
    name: str
    n_rows: int = Field(..., ge=0)
    n_columns: int = Field(..., ge=0)
    header_row_index: int = Field(default=1, ge=1, description="1-indexed header row")
    columns: List[WorkbookColumn] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────
# Signals
# ─────────────────────────────────────────────────────────────────


SignalKind = Literal["trend", "outlier", "metric", "ratio", "missing_data"]


class WorkbookSignal(BaseModel):
    kind: SignalKind
    title: str = Field(..., min_length=1, max_length=120)
    detail: str = Field(..., min_length=1, max_length=1000, description="Observational; refuse-to-decide validated")
    column: str = Field(..., description="Source column name")
    sheet: str = Field(..., description="Source sheet name")
    magnitude: Optional[float] = Field(None, description="Effect-size if applicable (e.g. % change, z-score)")
    citations: List[WorkbookCitation] = Field(..., min_length=1)


# ─────────────────────────────────────────────────────────────────
# Monte Carlo
# ─────────────────────────────────────────────────────────────────

DistributionKind = Literal["normal", "lognormal", "uniform", "triangular"]


class MonteCarloRun(BaseModel):
    id: str
    sheet: str
    column: str = Field(..., description="Input column the distribution was fit to")
    distribution: DistributionKind
    params: Dict[str, float] = Field(..., description="Distribution params — see monte_carlo.py for schema per kind")
    formula: str = Field(default="=x", description="Output formula. Default '=x' = identity over the input column")
    iterations: int = Field(..., ge=1000, le=10000)
    seed: int = Field(..., ge=0, description="numpy default_rng seed — full reproducibility")
    # Result bands
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    mean: float
    stddev: float
    histogram_bins: List[float] = Field(..., min_length=50, max_length=50, description="50-bucket histogram counts")
    histogram_edges: List[float] = Field(..., min_length=51, max_length=51)
    reproducer_hash: str = Field(..., description="sha256 of (column, dist, params, formula, iterations, seed)")
    narration: Optional["NarrationBlock"] = Field(None, description="LLM narration of the bands — observational")
    citations: List[WorkbookCitation] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ─────────────────────────────────────────────────────────────────
# Forecast
# ─────────────────────────────────────────────────────────────────


class ForecastRun(BaseModel):
    id: str
    sheet: str
    date_column: str
    value_column: str
    method: Literal["linear_regression"] = "linear_regression"
    n_historical: int
    horizon_periods: int = Field(..., ge=1, le=12)
    slope: float
    intercept: float
    r2: float = Field(..., ge=0.0, le=1.0)
    projections: List[Dict[str, float]] = Field(..., description="[{period_index, value, ci_low, ci_high}]")
    narration: Optional["NarrationBlock"] = None
    citations: List[WorkbookCitation] = Field(..., min_length=1)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ─────────────────────────────────────────────────────────────────
# Anomaly
# ─────────────────────────────────────────────────────────────────


class AnomalyRow(BaseModel):
    sheet: str
    column: str
    row_index: int = Field(..., ge=1, description="1-indexed row in the original sheet")
    value: float
    z_score: float
    iqr_distance: float = Field(..., description="(value - q3) / IQR if positive; (q1 - value) / IQR if negative")
    rationale: str = Field(..., min_length=1, description="Observational read, evidence-grounded")
    citations: List[WorkbookCitation] = Field(..., min_length=1)


# ─────────────────────────────────────────────────────────────────
# Narration block (shared)
# ─────────────────────────────────────────────────────────────────


class NarrationBlock(BaseModel):
    """An LLM-generated observational paragraph attached to a
    simulation / forecast / anomaly. The producer MUST pass the
    string through `refuse_to_decide.validate_no_imperatives`
    before persisting."""
    text: str = Field(..., min_length=1, max_length=2400)
    shielded: bool = Field(default=True, description="True iff the producer routed through services.solva_v2.llm_adapter.shielded_call")
    synisense_run_id: Optional[str] = None
    model_id: Optional[str] = None
    bias_chips: List[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────
# Root analysis document
# ─────────────────────────────────────────────────────────────────


class WorkbookAnalysis(BaseModel):
    """The root persisted document. Stored in
    `workbook_analyses` keyed on `id`. All cross-cutting tenant
    scoping rides on `account_id` (required) and `context_id`
    (optional — analyses can be account-scoped without a
    context)."""
    model_config = ConfigDict(extra="forbid")

    id: str
    account_id: str
    context_id: Optional[str] = None
    document_id: str = Field(..., description="Foreign key into the existing `documents` collection")
    filename: str
    file_format: Literal["xlsx", "csv"]
    file_size_bytes: int = Field(..., ge=0)

    status: Literal[
        "uploaded", "parsing", "parsed", "extracting", "ready",
        "failed",
    ] = "uploaded"
    failure_reason: Optional[str] = None

    sheets: List[WorkbookSheet] = Field(default_factory=list)
    signals: List[WorkbookSignal] = Field(default_factory=list)
    simulations: List[MonteCarloRun] = Field(default_factory=list)
    forecasts: List[ForecastRun] = Field(default_factory=list)
    anomalies: List[AnomalyRow] = Field(default_factory=list)

    schema_version: str = "workbook.analyze.1.0"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# Resolve forward refs.
MonteCarloRun.model_rebuild()
ForecastRun.model_rebuild()


__all__ = [
    "ColumnKind",
    "DistributionKind",
    "SignalKind",
    "WorkbookCitation",
    "WorkbookColumn",
    "WorkbookSheet",
    "WorkbookSignal",
    "MonteCarloRun",
    "ForecastRun",
    "AnomalyRow",
    "NarrationBlock",
    "WorkbookAnalysis",
    "CellRangePattern",
]
