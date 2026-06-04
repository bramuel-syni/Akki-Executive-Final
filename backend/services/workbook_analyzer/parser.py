"""Phase P5.14 — Workbook parser.

xlsx via openpyxl, csv via stdlib. Detects:

  * header row (first non-empty row; user can override at upload)
  * column letters (Excel A1)
  * column kinds (numeric / date / categorical / text) via
    sample-based type inference
  * numeric column stats (min/max/mean/median/stddev/null-count)
  * a representative ≤6-value sample for the preview card

Constraints:
  * Pure-Python, no pandas dependency (numpy only for stats).
  * Reads the workbook bytes into an in-memory BytesIO — the
    caller passes raw `bytes` so the tenant's file is never
    written to a shared filesystem location.
  * Returns a list of `WorkbookSheet` plus the raw row matrix
    (sheet_name → list[list]) for downstream signal/anomaly
    consumers. The raw matrix is NOT persisted to Mongo — only
    sheet metadata is. The matrix lives in memory for the
    duration of the analysis run.
"""
from __future__ import annotations

import csv
import io
import re
import statistics
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import openpyxl

from .schema import ColumnKind, WorkbookColumn, WorkbookSheet


_NUMERIC_RE = re.compile(r"^-?\d+(\.\d+)?$")


def _column_letter(idx_zero: int) -> str:
    """0-indexed → Excel column letter. 0→A, 25→Z, 26→AA, …"""
    n = idx_zero + 1
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def _coerce_value(raw: Any) -> Tuple[Any, ColumnKind]:
    """Best-effort scalar typing. Returns `(coerced, kind)`."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, "text"  # caller treats None as a null cell
    if isinstance(raw, (datetime, date)):
        return raw, "date"
    if isinstance(raw, bool):
        return raw, "categorical"
    if isinstance(raw, (int, float)):
        return float(raw), "numeric"
    s = str(raw).strip()
    if _NUMERIC_RE.match(s):
        try:
            return float(s), "numeric"
        except ValueError:
            pass
    # Try ISO date.
    # Track A Phase 3 R3v5 (2026-06-04) — added %Y-%m and %Y/%m so
    # monthly series like "2024-01" classify as `kind="date"`.
    # strptime defaults the missing day to 1, so the resulting
    # `date(2024,1,1)` works with `_to_ordinal` untouched. Net
    # effect: the J19 happy-path workbook (Month/Sales) now reaches
    # the autopicker → run_forecast → forecast block → narration.
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m", "%Y/%m"):
        try:
            return datetime.strptime(s, fmt).date(), "date"
        except ValueError:
            continue
    return s, "text"


def _infer_column_kind(values: List[Any]) -> ColumnKind:
    """Majority vote over coerced kinds. Ties favour `numeric` →
    `date` → `categorical` → `text`."""
    counts: Dict[ColumnKind, int] = {"numeric": 0, "date": 0, "categorical": 0, "text": 0}
    distinct: set = set()
    for v in values:
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        _, k = _coerce_value(v)
        counts[k] = counts.get(k, 0) + 1
        if k in ("text", "categorical"):
            distinct.add(str(v).strip())
    # Promote text → categorical if low cardinality.
    if counts["text"] > 0 and counts["numeric"] == 0 and counts["date"] == 0:
        if 0 < len(distinct) <= max(8, int(0.4 * counts["text"])):
            counts["categorical"] = counts["text"]
            counts["text"] = 0
    # Pick the winner with the priority tie-break.
    priority = ("numeric", "date", "categorical", "text")
    return max(priority, key=lambda k: counts[k])


def _numeric_only(values: List[Any]) -> List[float]:
    out: List[float] = []
    for v in values:
        if v is None:
            continue
        coerced, kind = _coerce_value(v)
        if kind == "numeric" and coerced is not None:
            out.append(float(coerced))
    return out


def _build_column(
    name: str, letter: str, values: List[Any],
) -> WorkbookColumn:
    null_count = sum(1 for v in values if v is None or (isinstance(v, str) and not v.strip()))
    non_null = [v for v in values if not (v is None or (isinstance(v, str) and not v.strip()))]
    kind = _infer_column_kind(non_null)
    sample_values = non_null[:6]

    minv = maxv = mean = median = stddev = None
    if kind == "numeric":
        nums = _numeric_only(non_null)
        if nums:
            minv = float(min(nums))
            maxv = float(max(nums))
            mean = float(statistics.fmean(nums))
            median = float(statistics.median(nums))
            stddev = float(statistics.pstdev(nums)) if len(nums) > 1 else 0.0

    return WorkbookColumn(
        name=name,
        letter=letter,
        kind=kind,
        non_null_count=len(non_null),
        null_count=null_count,
        minv=minv,
        maxv=maxv,
        mean=mean,
        median=median,
        stddev=stddev,
        sample_values=[
            v.isoformat() if isinstance(v, (datetime, date)) else (
                float(v) if isinstance(v, (int, float)) else str(v)
            )
            for v in sample_values
        ],
    )


def _build_sheet(name: str, rows: List[List[Any]], header_row_index: int = 1) -> Tuple[WorkbookSheet, List[List[Any]]]:
    """Returns (metadata, raw_matrix). raw_matrix includes the header
    row at index 0 so downstream consumers can address rows by their
    original 1-indexed sheet row using `row_index - 1`."""
    if not rows:
        return WorkbookSheet(name=name, n_rows=0, n_columns=0, columns=[]), []

    header = rows[header_row_index - 1] if len(rows) >= header_row_index else rows[0]
    data = rows[header_row_index:]
    n_cols = max(len(header), max((len(r) for r in data), default=0))

    columns: List[WorkbookColumn] = []
    for ci in range(n_cols):
        raw_name = (header[ci] if ci < len(header) else None) or f"Column_{_column_letter(ci)}"
        col_name = str(raw_name).strip() or f"Column_{_column_letter(ci)}"
        col_letter = _column_letter(ci)
        col_values = [row[ci] if ci < len(row) else None for row in data]
        columns.append(_build_column(col_name, col_letter, col_values))

    return (
        WorkbookSheet(
            name=name,
            n_rows=len(data),
            n_columns=n_cols,
            header_row_index=header_row_index,
            columns=columns,
        ),
        rows,
    )


def _parse_xlsx(blob: bytes, max_rows_per_sheet: int = 20_000) -> Tuple[List[WorkbookSheet], Dict[str, List[List[Any]]]]:
    wb = openpyxl.load_workbook(filename=io.BytesIO(blob), read_only=True, data_only=True)
    sheets: List[WorkbookSheet] = []
    matrices: Dict[str, List[List[Any]]] = {}
    try:
        for ws in wb.worksheets:
            rows: List[List[Any]] = []
            for r in ws.iter_rows(values_only=True):
                rows.append(list(r))
                if len(rows) >= max_rows_per_sheet:
                    break
            sheet, matrix = _build_sheet(ws.title, rows)
            sheets.append(sheet)
            matrices[ws.title] = matrix
    finally:
        wb.close()
    return sheets, matrices


def _parse_csv(blob: bytes, max_rows: int = 50_000) -> Tuple[List[WorkbookSheet], Dict[str, List[List[Any]]]]:
    text = blob.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows: List[List[Any]] = []
    for r in reader:
        rows.append(list(r))
        if len(rows) >= max_rows:
            break
    sheet, matrix = _build_sheet("Sheet1", rows)
    return [sheet], {"Sheet1": matrix}


def parse_workbook(
    *,
    blob: bytes,
    file_format: str,
) -> Tuple[List[WorkbookSheet], Dict[str, List[List[Any]]]]:
    """Parse a workbook blob.

    Returns: `(sheet_metadata, sheet_name -> raw_matrix)`. The
    raw matrix is the full 2D row x col list including the header
    row at position 0 — downstream code uses it to compute exact
    cell-range citations (the row index in the matrix is 0-based;
    the corresponding 1-based sheet row is `matrix_index + 1`).
    """
    fmt = (file_format or "").lower()
    if fmt == "xlsx":
        return _parse_xlsx(blob)
    if fmt == "csv":
        return _parse_csv(blob)
    raise ValueError(f"workbook_parser: unsupported file_format={file_format!r}")


__all__ = ["parse_workbook"]
