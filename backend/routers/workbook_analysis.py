"""Phase P5.14 — Workbook Analyze router.

Endpoints (all CSRF-protected; namespace `/api/workbook` is NOT
on the CSRF allowlist):

  POST   /api/workbook/upload                                    → create analysis from xlsx/csv
  GET    /api/workbook/analyses                                  → list current-account analyses
  GET    /api/workbook/analyses/{aid}                            → fetch (+sheet metadata + accreted artefacts)
  POST   /api/workbook/analyses/{aid}/signals/extract            → run deterministic signal extraction
  POST   /api/workbook/analyses/{aid}/simulate                   → Monte Carlo run
  POST   /api/workbook/analyses/{aid}/forecast                   → linear forecast run
  POST   /api/workbook/analyses/{aid}/anomalies                  → detect anomalies on a column
  GET    /api/workbook/analyses/{aid}/report.pptx                → download the PPTX

Tenant isolation: every query is scoped by `account_id` taken
from the authenticated account dependency. Cross-account access
returns 404 (not 403) so we don't leak existence.

Storage:
  * `workbook_analyses` — metadata + accreted artefacts (this is
    the resource the FE drives against).
  * `workbook_blobs`    — raw bytes (base64). Separated so the
    metadata collection stays small and indexable.
"""
from __future__ import annotations

import base64
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Query, Response,
    UploadFile,
)
from pydantic import BaseModel, Field

from core import db, get_current_account
from services.workbook_analyzer import (
    AnomalyRow,
    CitationUnverifiable,
    ForecastRun,
    MonteCarloRun,
    NarrationBlock,
    RefuseToDecideViolation,
    WorkbookAnalysis,
    WorkbookCitation,
    WorkbookCitationResolver,
    WorkbookColumn,
    WorkbookSheet,
    autopick_forecast_columns,
    build_docx_report,
    build_pptx_report,
    build_xlsx_report,
    detect_anomalies,
    extract_signals_for,
    parse_workbook,
    run_forecast,
    run_monte_carlo,
    validate_no_imperatives,
)
from services.solva_v2.analyze_narration import narrate_analysis  # Track A Phase 3

# Track A Phase 1 (2026-06-03) — new sibling Analysis entity + service.
from models.analysis import Analysis  # noqa: F401  re-export available for callers
from services.analysis_lifecycle import (
    build_analysis_from_uploads,
    session_close as analysis_session_close,
)


router = APIRouter(prefix="/api/workbook", tags=["workbook-analyze"])


# Track A Phase 1 (2026-06-03) — file-size cap raised from 25MB →
# 250MB per file per the approved Pre-Read. The Analyze pipeline now
# routinely sees workbooks in the 100MB+ range from real exec-side
# users; 25MB was a P5.14-era conservative ceiling. The 250MB
# boundary still bounds the per-tenant Mongo footprint.
MAX_BYTES = 250 * 1024 * 1024
ACCEPT_EXT = {".xlsx", ".csv"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────
# In-memory blob cache: parsed-matrix lookups can re-read the
# blob on demand. The cache is per-process; on a worker restart
# we lazily re-parse from `workbook_blobs`.
# ─────────────────────────────────────────────────────────────────
_MATRIX_CACHE: Dict[str, Dict[str, List[List[Any]]]] = {}


async def _load_matrices(analysis_id: str) -> Dict[str, List[List[Any]]]:
    if analysis_id in _MATRIX_CACHE:
        return _MATRIX_CACHE[analysis_id]
    blob_row = await db.workbook_blobs.find_one({"analysis_id": analysis_id}, {"_id": 0})
    if not blob_row:
        raise HTTPException(404, "workbook_blob_missing")
    blob = base64.b64decode(blob_row["data_b64"])
    _sheets, matrices = parse_workbook(
        blob=blob, file_format=blob_row["file_format"],
    )
    _MATRIX_CACHE[analysis_id] = matrices
    return matrices


async def _load_analysis(analysis_id: str, account_id: str) -> WorkbookAnalysis:
    row = await db.workbook_analyses.find_one(
        {"id": analysis_id, "account_id": account_id},
        {"_id": 0},
    )
    if not row:
        # Same response shape for "doesn't exist" and "belongs to
        # another tenant" — no existence leak.
        raise HTTPException(404, "workbook_analysis_not_found")
    return WorkbookAnalysis.model_validate(row)


# ── Track A Phase 1 surgical fix (2026-06-03) ────────────────────
# The three export endpoints below need to serve BOTH the legacy
# `wba-*` analyses (created via `/upload`) AND the new `ana-*`
# analyses (created via `/upload-multi`). The synthesize/read
# endpoints continue to use `_load_analysis` and stay
# legacy-collection-only — Phase 3 will extend them to the new
# entity once Solva v2 narration exists.
#
# Surgical seam: a sibling loader used ONLY by the three exports.
# Blast radius = three call sites; everything else unchanged.

def _adapt_new_analysis_to_workbook_analysis(row: Dict[str, Any]) -> WorkbookAnalysis:
    """Build a minimal `WorkbookAnalysis` view from a new-entity
    `Analysis` row so the existing PPTX/DOCX/XLSX builders can
    consume it without modification.

    Phase 1 carries no synthesis data — empty signals /
    simulations / forecasts / anomalies. Phase 3 will replace
    this shim with real per-source narration via Solva v2."""
    sources = row.get("sources", []) or []
    columns = [
        WorkbookColumn(
            name="filename", letter="A", kind="text",
            non_null_count=len(sources), null_count=0,
            sample_values=[s.get("filename", "") for s in sources[:6]],
        ),
        WorkbookColumn(
            name="format", letter="B", kind="categorical",
            non_null_count=len(sources), null_count=0,
            sample_values=[s.get("file_format", "") for s in sources[:6]],
        ),
        WorkbookColumn(
            name="size_bytes", letter="C", kind="numeric",
            non_null_count=len(sources), null_count=0,
            sample_values=[s.get("file_size_bytes", 0) for s in sources[:6]],
        ),
    ]
    sources_sheet = WorkbookSheet(
        name="Analysis Sources",
        n_rows=len(sources),
        n_columns=3,
        columns=columns,
    )

    file_format = (sources[0].get("file_format") if sources else "xlsx")
    file_size = sum((s.get("file_size_bytes") or 0) for s in sources)
    filename = row.get("title") or (
        sources[0].get("filename") if sources else "analysis"
    )

    return WorkbookAnalysis(
        id=row["id"],
        account_id=row["account_id"],
        context_id=row.get("context_id"),
        # `document_id` is required on the legacy schema. Use the
        # analysis id as a stable surrogate so `extra="forbid"`
        # construction succeeds. No leakage — this WorkbookAnalysis
        # instance is ephemeral, never written back.
        document_id=row["id"],
        filename=filename,
        file_format=file_format,
        file_size_bytes=file_size,
        status="ready",
        sheets=[sources_sheet],
        signals=[],
        simulations=[],
        forecasts=[],
        anomalies=[],
        created_at=row.get("created_at") or _now_iso(),
        updated_at=row.get("updated_at") or _now_iso(),
    )


async def _load_analysis_for_export(
    analysis_id: str, account_id: str,
) -> WorkbookAnalysis:
    """Prefix-dispatch loader used ONLY by the three export
    endpoints (`report.pptx`/`.docx`/`.xlsx`).

    `ana-*` ids load from `db.analyses` via the shim above.
    Other ids fall through to the legacy `_load_analysis` (which
    reads `db.workbook_analyses`)."""
    if analysis_id.startswith("ana-"):
        row = await db.analyses.find_one(
            {"id": analysis_id, "account_id": account_id},
            {"_id": 0},
        )
        if not row:
            raise HTTPException(404, "workbook_analysis_not_found")
        return _adapt_new_analysis_to_workbook_analysis(row)
    return await _load_analysis(analysis_id, account_id)


async def _save_analysis(analysis: WorkbookAnalysis) -> None:
    analysis.updated_at = _now_iso()
    payload = analysis.model_dump()
    await db.workbook_analyses.update_one(
        {"id": analysis.id, "account_id": analysis.account_id},
        {"$set": payload},
        upsert=False,
    )


# ─────────────────────────────────────────────────────────────────
# POST /upload  → create
# ─────────────────────────────────────────────────────────────────


@router.post("/upload")
async def upload_workbook(
    file: UploadFile = File(...),
    current: Dict[str, Any] = Depends(get_current_account),
):
    filename = file.filename or "unnamed"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ACCEPT_EXT:
        raise HTTPException(415, f"workbook_format_unsupported: {ext}")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "workbook_too_large_250mb")
    if not data:
        raise HTTPException(400, "workbook_empty")

    fmt = "xlsx" if ext == ".xlsx" else "csv"
    try:
        sheets, matrices = parse_workbook(blob=data, file_format=fmt)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"workbook_parse_failed: {e!s:.200}")

    analysis_id = "wba-" + uuid.uuid4().hex[:12]

    analysis = WorkbookAnalysis(
        id=analysis_id,
        account_id=current["id"],
        context_id=current.get("active_context_id") or None,
        document_id=analysis_id,  # MVP: workbook is its own document
        filename=filename,
        file_format=fmt,
        file_size_bytes=len(data),
        status="parsed",
        sheets=sheets,
    )
    await db.workbook_analyses.insert_one(analysis.model_dump())
    await db.workbook_blobs.insert_one({
        "analysis_id": analysis_id,
        "account_id": current["id"],
        "filename": filename,
        "file_format": fmt,
        "data_b64": base64.b64encode(data).decode("ascii"),
        "created_at": _now_iso(),
    })
    _MATRIX_CACHE[analysis_id] = matrices

    return {
        "id": analysis_id,
        "status": "parsed",
        "sheets": [s.model_dump() for s in sheets],
    }


# ─────────────────────────────────────────────────────────────────
# GET /analyses  → list
# ─────────────────────────────────────────────────────────────────


@router.get("/analyses")
async def list_analyses(current: Dict[str, Any] = Depends(get_current_account)):
    cursor = db.workbook_analyses.find(
        {"account_id": current["id"]},
        {"_id": 0, "id": 1, "filename": 1, "file_format": 1, "status": 1,
         "created_at": 1, "updated_at": 1, "sheets.name": 1},
    ).sort("created_at", -1).limit(50)
    items = []
    async for row in cursor:
        items.append({
            "id": row["id"],
            "filename": row["filename"],
            "file_format": row["file_format"],
            "status": row["status"],
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "sheet_names": [s["name"] for s in row.get("sheets", [])],
        })
    return {"items": items}


# ─────────────────────────────────────────────────────────────────
# GET /analyses/{aid}
# ─────────────────────────────────────────────────────────────────


@router.get("/analyses/{aid}")
async def get_analysis(aid: str, current: Dict[str, Any] = Depends(get_current_account)):
    a = await _load_analysis(aid, current["id"])
    return a.model_dump()


# ─────────────────────────────────────────────────────────────────
# POST /analyses/{aid}/signals/extract
# ─────────────────────────────────────────────────────────────────


@router.post("/analyses/{aid}/signals/extract")
async def extract_signals_endpoint(
    aid: str, current: Dict[str, Any] = Depends(get_current_account),
):
    analysis = await _load_analysis(aid, current["id"])
    matrices = await _load_matrices(aid)
    resolver = WorkbookCitationResolver(analysis.sheets)
    all_signals = []
    for sheet in analysis.sheets:
        matrix = matrices.get(sheet.name, [])
        sigs = extract_signals_for(sheet=sheet, sheet_matrix=matrix)
        for s in sigs:
            try:
                validate_no_imperatives(s.detail, label=f"signal.detail/{s.title}")
                resolver.resolve_many(s.citations)
            except (RefuseToDecideViolation, CitationUnverifiable):
                # Skip the offending signal but never the whole batch.
                # The deterministic extractor should never produce these
                # in practice — if it does, the suite of pytest negative-
                # samples will catch it before deploy.
                continue
            all_signals.append(s)
    analysis.signals = all_signals
    analysis.status = "ready"
    await _save_analysis(analysis)
    return {"signals": [s.model_dump() for s in all_signals]}


# ─────────────────────────────────────────────────────────────────
# POST /analyses/{aid}/simulate
# ─────────────────────────────────────────────────────────────────


class SimulateRequest(BaseModel):
    sheet: str
    column: str = Field(..., description="The column-name to fit the input distribution to")
    distribution: str  # validated against the literal in monte_carlo._sample
    params: Dict[str, float]
    iterations: int = 5000
    formula: str = "=x"
    seed: int = 42


@router.post("/analyses/{aid}/simulate")
async def simulate_endpoint(
    aid: str,
    body: SimulateRequest,
    current: Dict[str, Any] = Depends(get_current_account),
):
    analysis = await _load_analysis(aid, current["id"])
    # Find the column letter for citation purposes.
    sheet_obj = next((s for s in analysis.sheets if s.name == body.sheet), None)
    if not sheet_obj:
        raise HTTPException(400, f"sheet_not_found: {body.sheet}")
    col_obj = next((c for c in sheet_obj.columns if c.name == body.column), None)
    if not col_obj:
        raise HTTPException(400, f"column_not_found: {body.column}")
    if col_obj.kind != "numeric":
        raise HTTPException(400, f"column_must_be_numeric: {body.column} is {col_obj.kind}")

    n_data_rows = sheet_obj.n_rows
    last_data_row = sheet_obj.header_row_index + n_data_rows
    citation = WorkbookCitation(
        cell_range=f"{sheet_obj.name}!{col_obj.letter}{sheet_obj.header_row_index + 1}:"
                   f"{col_obj.letter}{last_data_row}",
        excerpt=(f"Distribution fit to {col_obj.non_null_count} non-null rows of "
                 f"{col_obj.name}; column stats: mean={col_obj.mean}, stddev={col_obj.stddev}"),
    )
    # Citation MUST resolve (will trip CitationUnverifiable if not).
    WorkbookCitationResolver(analysis.sheets).resolve(citation)

    try:
        mc = run_monte_carlo(
            sheet=body.sheet,
            column=body.column,
            distribution=body.distribution,  # type: ignore[arg-type]
            params=body.params,
            iterations=body.iterations,
            formula=body.formula,
            seed=body.seed,
            citations=[citation],
        )
    except ValueError as e:
        raise HTTPException(400, f"simulate_invalid: {e}")

    # Deterministic narration. Validated.
    narration_text = (
        f"The {mc.iterations}-iteration simulation on {body.column} produced a "
        f"median outcome of {mc.p50:.2f}. The central 80% of outcomes fall "
        f"between {mc.p10:.2f} (P10) and {mc.p90:.2f} (P90). The mean is "
        f"{mc.mean:.2f}, the standard deviation is {mc.stddev:.2f}. The "
        f"reproducer hash {mc.reproducer_hash[:12]}… captures the full "
        f"specification; re-running with the same hash returns byte-identical "
        f"bands."
    )
    validate_no_imperatives(narration_text, label="simulate.narration")
    mc.narration = NarrationBlock(text=narration_text, shielded=False)

    analysis.simulations.append(mc)
    await _save_analysis(analysis)
    return mc.model_dump()


# ─────────────────────────────────────────────────────────────────
# POST /analyses/{aid}/forecast
# ─────────────────────────────────────────────────────────────────


class ForecastRequest(BaseModel):
    sheet: str
    date_column: str
    value_column: str
    horizon_periods: int = 8


@router.post("/analyses/{aid}/forecast")
async def forecast_endpoint(
    aid: str,
    body: ForecastRequest,
    current: Dict[str, Any] = Depends(get_current_account),
):
    analysis = await _load_analysis(aid, current["id"])
    sheet_obj = next((s for s in analysis.sheets if s.name == body.sheet), None)
    if not sheet_obj:
        raise HTTPException(400, f"sheet_not_found: {body.sheet}")
    date_col = next((c for c in sheet_obj.columns if c.name == body.date_column), None)
    val_col = next((c for c in sheet_obj.columns if c.name == body.value_column), None)
    if not date_col or date_col.kind != "date":
        raise HTTPException(400, f"date_column_invalid: {body.date_column}")
    if not val_col or val_col.kind != "numeric":
        raise HTTPException(400, f"value_column_invalid: {body.value_column}")

    matrices = await _load_matrices(aid)
    sheet_matrix = matrices.get(body.sheet) or []
    date_idx = next((i for i, c in enumerate(sheet_obj.columns) if c.name == body.date_column), -1)
    val_idx = next((i for i, c in enumerate(sheet_obj.columns) if c.name == body.value_column), -1)
    try:
        fc = run_forecast(
            sheet=body.sheet,
            date_column=body.date_column,
            value_column=body.value_column,
            sheet_matrix=sheet_matrix,
            header_row_index=sheet_obj.header_row_index,
            date_col_index_zero=date_idx,
            value_col_index_zero=val_idx,
            horizon_periods=body.horizon_periods,
        )
    except ValueError as e:
        raise HTTPException(400, f"forecast_invalid: {e}")

    WorkbookCitationResolver(analysis.sheets).resolve_many(fc.citations)

    narration_text = (
        f"Fitting a linear regression to {fc.n_historical} historical "
        f"({fc.date_column}, {fc.value_column}) pairs yields R²={fc.r2:.3f}. "
        f"The first forecast period projects to {fc.projections[0]['value']:.2f} "
        f"with an 80% confidence interval of "
        f"{fc.projections[0]['ci_low']:.2f}–{fc.projections[0]['ci_high']:.2f}. "
        f"Linear regression assumes the historical pattern continues; reviewers "
        f"may want to weigh this against context the workbook itself does not "
        f"capture."
    )
    validate_no_imperatives(narration_text, label="forecast.narration")
    fc.narration = NarrationBlock(text=narration_text, shielded=False)

    analysis.forecasts.append(fc)
    await _save_analysis(analysis)
    return fc.model_dump()


# ─────────────────────────────────────────────────────────────────
# POST /analyses/{aid}/anomalies
# ─────────────────────────────────────────────────────────────────


class AnomaliesRequest(BaseModel):
    sheet: str
    column: Optional[str] = Field(
        None, description="If omitted, runs anomaly detection on every numeric column in the sheet",
    )
    z_threshold: float = 3.0
    iqr_multiplier: float = 1.5


@router.post("/analyses/{aid}/anomalies")
async def anomalies_endpoint(
    aid: str,
    body: AnomaliesRequest,
    current: Dict[str, Any] = Depends(get_current_account),
):
    analysis = await _load_analysis(aid, current["id"])
    sheet_obj = next((s for s in analysis.sheets if s.name == body.sheet), None)
    if not sheet_obj:
        raise HTTPException(400, f"sheet_not_found: {body.sheet}")
    matrices = await _load_matrices(aid)
    matrix = matrices.get(body.sheet) or []

    target_cols = (
        [next((c for c in sheet_obj.columns if c.name == body.column), None)]
        if body.column else
        [c for c in sheet_obj.columns if c.kind == "numeric"]
    )
    target_cols = [c for c in target_cols if c is not None]
    if not target_cols:
        raise HTTPException(400, "no_numeric_columns_for_anomaly_detection")

    resolver = WorkbookCitationResolver(analysis.sheets)
    fresh: List[AnomalyRow] = []
    for col in target_cols:
        col_idx = next((i for i, c in enumerate(sheet_obj.columns) if c.name == col.name), -1)
        rows = detect_anomalies(
            sheet=body.sheet,
            column_name=col.name,
            column_letter=col.letter,
            sheet_matrix=matrix,
            header_row_index=sheet_obj.header_row_index,
            col_index_zero=col_idx,
            z_threshold=body.z_threshold,
            iqr_multiplier=body.iqr_multiplier,
        )
        for a in rows:
            validate_no_imperatives(a.rationale, label=f"anomaly.rationale/{a.row_index}")
            resolver.resolve_many(a.citations)
        fresh.extend(rows)
    analysis.anomalies = fresh
    await _save_analysis(analysis)
    return {"anomalies": [a.model_dump() for a in fresh]}


# ─────────────────────────────────────────────────────────────────
# GET /analyses/{aid}/report.pptx
# ─────────────────────────────────────────────────────────────────


@router.get("/analyses/{aid}/report.pptx")
async def report_endpoint(aid: str, current: Dict[str, Any] = Depends(get_current_account)):
    analysis = await _load_analysis_for_export(aid, current["id"])
    try:
        pptx_bytes = build_pptx_report(analysis)
    except RefuseToDecideViolation as e:
        raise HTTPException(500, f"narration_failed_refuse_to_decide: {e}")
    headers = {
        "Content-Disposition": (
            f'attachment; filename="{re.sub(r"[^A-Za-z0-9._-]", "_", analysis.filename)}_analysis.pptx"'
        ),
        # Mark the response as not cacheable so the file always
        # reflects the current accreted state of the analysis.
        "Cache-Control": "no-store",
    }
    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers=headers,
    )


# ─────────────────────────────────────────────────────────────────
# GET /analyses/{aid}/report.docx           (Track A Phase 1)
# GET /analyses/{aid}/report.xlsx           (Track A Phase 1)
#
# Mirror the PPTX endpoint pattern byte-for-byte: same tenant-scope
# (`_load_analysis(aid, current["id"])` → 404 on miss-or-other-
# tenant), same Cache-Control, same Content-Disposition format,
# same RefuseToDecideViolation → 500 handling.
# ─────────────────────────────────────────────────────────────────


@router.get("/analyses/{aid}/report.docx")
async def report_docx_endpoint(aid: str, current: Dict[str, Any] = Depends(get_current_account)):
    analysis = await _load_analysis_for_export(aid, current["id"])
    try:
        docx_bytes = build_docx_report(analysis)
    except RefuseToDecideViolation as e:
        raise HTTPException(500, f"narration_failed_refuse_to_decide: {e}")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", analysis.filename)
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_name}_analysis.docx"',
        "Cache-Control": "no-store",
    }
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


@router.get("/analyses/{aid}/report.xlsx")
async def report_xlsx_endpoint(aid: str, current: Dict[str, Any] = Depends(get_current_account)):
    analysis = await _load_analysis_for_export(aid, current["id"])
    try:
        xlsx_bytes = build_xlsx_report(analysis)
    except RefuseToDecideViolation as e:
        raise HTTPException(500, f"narration_failed_refuse_to_decide: {e}")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", analysis.filename)
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_name}_analysis.xlsx"',
        "Cache-Control": "no-store",
    }
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


# ─────────────────────────────────────────────────────────────────
# Track A Phase 1 (2026-06-03) — NEW `Analysis` entity endpoints.
#
# These sit alongside the P5.14 surface above; they DO NOT replace
# it. Phase 2 of Track A wires the UI to these; Phase 1 establishes
# the persistence shape + lifecycle hooks.
#
# Collection: `analyses` (vs P5.14 `workbook_analyses`).
# Tenant scope: `(account_id, context_id)` — context_id REQUIRED.
# ─────────────────────────────────────────────────────────────────


@router.post("/upload-multi")
async def upload_workbook_multi(
    files: List[UploadFile] = File(..., description="One or more xlsx/csv files"),
    title: Optional[str] = Form(None),
    context_id: Optional[str] = Form(None),
    objective: Optional[str] = Form(None),
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Multi-file upload → creates ONE `Analysis` row with N source
    refs. Per Pre-Read: accepts 1+ files in one request; 250MB cap
    PER FILE.

    Track A Phase 2 (2026-06-04) — accepts an optional `objective`
    text that is captured at the top of the Analyze drawer."""
    if not files:
        raise HTTPException(400, "at_least_one_file_required")

    ctx = context_id or current.get("active_context_id")
    if not ctx:
        raise HTTPException(400, "context_id_required")

    accepted: List[tuple] = []  # (filename, bytes, fmt)
    for upload in files:
        fname = upload.filename or "unnamed"
        ext = "." + fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        if ext not in ACCEPT_EXT:
            raise HTTPException(415, f"workbook_format_unsupported: {ext}")
        raw = await upload.read()
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, f"workbook_too_large_250mb: {fname}")
        if not raw:
            raise HTTPException(400, f"workbook_empty: {fname}")
        fmt = "xlsx" if ext == ".xlsx" else "csv"
        # Light-touch parse-validation: every source must be
        # readable as the declared format.
        try:
            parse_workbook(blob=raw, file_format=fmt)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(422, f"workbook_parse_failed: {fname}: {e!s:.140}")
        accepted.append((fname, raw, fmt))

    display_title = (title or "").strip() or (
        accepted[0][0] if len(accepted) == 1
        else f"{accepted[0][0]} + {len(accepted) - 1} more"
    )

    analysis, blob_docs = build_analysis_from_uploads(
        account_id=current["id"],
        context_id=ctx,
        title=display_title,
        files=accepted,
        objective=(objective or "").strip(),
    )
    await db.analyses.insert_one(analysis.model_dump())
    if blob_docs:
        await db.analysis_blobs.insert_many(blob_docs)

    return {
        "id": analysis.id,
        "status": analysis.status,
        "title": analysis.title,
        "context_id": analysis.context_id,
        "objective": analysis.objective,
        "sources": [s.model_dump() for s in analysis.sources],
    }


@router.get("/v2/analyses/{aid}")
async def get_analysis_v2(aid: str, current: Dict[str, Any] = Depends(get_current_account)):
    """Read endpoint for the new `Analysis` entity. Tenant-scoped:
    cross-tenant returns 404 (no existence leak)."""
    row = await db.analyses.find_one(
        {"id": aid, "account_id": current["id"]},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(404, "analysis_not_found")
    return row

@router.post("/v2/analyses/{aid}/synthesize")
async def synthesize_v2_endpoint(
    aid: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Track A Phase 3 (2026-06-04) — Solva v2 Analyze narration.

    Loads the new `Analysis` entity (`ana-*`), runs deterministic
    analyzers on the source blobs, asks Claude Sonnet via Shield
    for a headline-first narration, validates citations against
    the deterministic citation pool, persists to the entity.

    Idempotent — re-call with unchanged content returns the
    cached narration via `narration.cache_key`.

    Bug #30 — uses `autopick_forecast_columns` so workbooks with
    valid (date, value) pairs no longer trip
    `forecast_invalid: need at least 3 (date, value) pairs`.
    """
    row = await db.analyses.find_one(
        {"id": aid, "account_id": current["id"]}, {"_id": 0},
    )
    if not row:
        raise HTTPException(404, "analysis_not_found")

    blobs = await db.analysis_blobs.find(
        {"analysis_id": aid, "account_id": current["id"]}, {"_id": 0},
    ).to_list(length=None)
    if not blobs:
        # Sources purged on session-close → no fabrication.
        update = {
            "narration": {
                "headline": "",
                "observations": [],
                "citations": [],
                "cache_key": "",
                "refused": True,
                "refusal_reason": "sources_purged",
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.analyses.update_one(
            {"id": aid, "account_id": current["id"]}, {"$set": update},
        )
        return update["narration"]

    first_blob = blobs[0]
    raw_bytes = base64.b64decode(first_blob["data_b64"])
    fmt = first_blob.get("file_format", "xlsx")
    try:
        sheets, matrices = parse_workbook(blob=raw_bytes, file_format=fmt)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"workbook_parse_failed: {e!s:.140}")

    wba = WorkbookAnalysis(
        id="wba-narr-" + aid[-12:],
        account_id=current["id"],
        context_id=row.get("context_id"),
        document_id=aid,
        filename=first_blob.get("filename", "analysis"),
        file_format=fmt,
        file_size_bytes=len(raw_bytes),
        status="ready",
        sheets=sheets,
        signals=[], simulations=[], forecasts=[], anomalies=[],
    )
    resolver = WorkbookCitationResolver(sheets)

    # Signals — every sheet.
    all_signals = []
    for sheet in sheets:
        matrix = matrices.get(sheet.name, [])
        try:
            sigs = extract_signals_for(sheet=sheet, sheet_matrix=matrix)
        except Exception:  # noqa: BLE001
            sigs = []
        for s in sigs:
            try:
                validate_no_imperatives(s.detail, label=f"signal.detail/{s.title}")
                resolver.resolve_many(s.citations)
            except (RefuseToDecideViolation, CitationUnverifiable):
                continue
            all_signals.append(s)
    wba.signals = all_signals

    # Forecast — Bug #30 autopicker.
    pick = autopick_forecast_columns(sheets=sheets)
    if pick is not None:
        sheet_obj = next((s for s in sheets if s.name == pick["sheet"]), None)
        if sheet_obj:
            sheet_matrix = matrices.get(pick["sheet"]) or []
            date_idx = next(
                (i for i, c in enumerate(sheet_obj.columns) if c.name == pick["date_column"]), -1,
            )
            val_idx = next(
                (i for i, c in enumerate(sheet_obj.columns) if c.name == pick["value_column"]), -1,
            )
            try:
                fc = run_forecast(
                    sheet=pick["sheet"],
                    date_column=pick["date_column"],
                    value_column=pick["value_column"],
                    sheet_matrix=sheet_matrix,
                    header_row_index=sheet_obj.header_row_index,
                    date_col_index_zero=date_idx,
                    value_col_index_zero=val_idx,
                    horizon_periods=8,
                )
                resolver.resolve_many(fc.citations)
                wba.forecasts.append(fc)
            except (ValueError, CitationUnverifiable):
                pass

    # Anomalies — top-6 per numeric column on the first sheet.
    if sheets:
        first_sheet = sheets[0]
        first_matrix = matrices.get(first_sheet.name) or []
        for col in first_sheet.columns:
            if col.kind != "numeric":
                continue
            try:
                anoms = detect_anomalies(
                    sheet=first_sheet, column=col,
                    sheet_matrix=first_matrix,
                    z_threshold=3.0, iqr_multiplier=1.5,
                )
            except Exception:  # noqa: BLE001
                anoms = []
            for a in anoms[:6]:
                try:
                    resolver.resolve_many(a.citations)
                except CitationUnverifiable:
                    continue
                wba.anomalies.append(a)

    narration = await narrate_analysis(
        workbook_analysis=wba,
        account_id=current["id"],
        objective=row.get("objective", ""),
        cached=row.get("narration"),
    )

    update_set: Dict[str, Any] = {
        "narration":  narration,
        "headline":   narration.get("headline", ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if not narration.get("refused"):
        lifted = []
        for obs in narration.get("observations") or []:
            lifted.append({
                "id":                 "obs-" + uuid.uuid4().hex[:12],
                "kind":               obs.get("tab", "synthesis"),
                "title":              obs.get("title", "")[:200],
                "detail":             obs.get("body", "")[:2000],
                "source_id":          None,
                "citations":          obs.get("citations") or [],
                "created_at":         datetime.now(timezone.utc).isoformat(),
            })
        update_set["observations"] = lifted
    await db.analyses.update_one(
        {"id": aid, "account_id": current["id"]}, {"$set": update_set},
    )
    return narration




@router.post("/v2/analyses/{aid}/session-close")
async def session_close_endpoint(
    aid: str, current: Dict[str, Any] = Depends(get_current_account),
):
    """Delete the excel binary on session close; retain the
    Analysis row + sources + (Phase 3) observations + notes."""
    row = await db.analyses.find_one(
        {"id": aid, "account_id": current["id"]},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(404, "analysis_not_found")
    result = await analysis_session_close(
        db,
        analysis_id=aid,
        account_id=current["id"],
        context_id=row["context_id"],
    )
    return result


# ─────────────────────────────────────────────────────────────────
# Track A Phase 2 (2026-06-04) — listing + objective + notes
# endpoints for the Analyze Journal surface.
# ─────────────────────────────────────────────────────────────────


class _AnalysisObjectivePatch(BaseModel):
    """Body schema for `PATCH /v2/analyses/{aid}/objective`."""
    objective: str = Field(..., max_length=4000)


class _AnalysisNoteIn(BaseModel):
    """Body schema for `POST /v2/analyses/{aid}/notes`."""
    body: str = Field(..., min_length=1, max_length=4000)


@router.get("/v2/analyses")
async def list_analyses_v2(
    context_id: Optional[str] = Query(None),
    current: Dict[str, Any] = Depends(get_current_account),
):
    """List the current account's Analyses. Tenant-scoped via
    `account_id`. Optional `context_id` filter for the in-context
    journal view."""
    q: Dict[str, Any] = {"account_id": current["id"]}
    if context_id:
        q["context_id"] = context_id
    rows = await db.analyses.find(
        q, {"_id": 0},
    ).sort("updated_at", -1).to_list(length=200)
    # Drop the raw observations/notes bodies from the listing payload
    # — they're heavy and only needed on detail. Keep a count.
    summarized = []
    for r in rows:
        summarized.append({
            "id": r.get("id"),
            "title": r.get("title"),
            "context_id": r.get("context_id"),
            "status": r.get("status"),
            "objective": r.get("objective", ""),
            "source_count": len(r.get("sources") or []),
            "observation_count": len(r.get("observations") or []),
            "note_count": len(r.get("notes") or []),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
        })
    return summarized


@router.patch("/v2/analyses/{aid}/objective")
async def patch_analysis_objective(
    aid: str,
    body: _AnalysisObjectivePatch,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Save the drawer's "objective" text. Auto-save target; FE
    debounces on the client side. Tenant-scoped; cross-tenant
    returns 404."""
    row = await db.analyses.find_one(
        {"id": aid, "account_id": current["id"]},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(404, "analysis_not_found")
    await db.analyses.update_one(
        {"id": aid, "account_id": current["id"]},
        {"$set": {
            "objective": body.objective,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    fresh = await db.analyses.find_one(
        {"id": aid, "account_id": current["id"]},
        {"_id": 0},
    )
    return fresh


@router.post("/v2/analyses/{aid}/notes")
async def post_analysis_note(
    aid: str,
    body: _AnalysisNoteIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Append a note to the Analysis. Auto-saved; FE typically
    sends one note per save-debounce window. Tenant-scoped."""
    row = await db.analyses.find_one(
        {"id": aid, "account_id": current["id"]},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(404, "analysis_not_found")
    note = {
        "id": "note-" + uuid.uuid4().hex[:12],
        "body": body.body,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "author_account_id": current["id"],
    }
    await db.analyses.update_one(
        {"id": aid, "account_id": current["id"]},
        {
            "$push": {"notes": note},
            "$set": {"updated_at": note["created_at"]},
        },
    )
    return note


__all__ = ["router"]
