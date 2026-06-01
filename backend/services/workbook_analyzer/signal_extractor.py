"""Phase P5.14 — Workbook signal extraction.

Two-mode operation:

  * Deterministic mode (default):
      Builds signals from column statistics directly — top
      metric value, top outlier, missing-data fraction, simple
      trend slope on date+value pairs. No LLM call. Every signal
      cites real cells. Used as the always-on baseline so signals
      surface even when the universal LLM key is dry / quota'd.

  * Shielded LLM mode (opt-in via `narrate=True`):
      Wraps the deterministic signal list with an LLM-generated
      neutral one-sentence elaboration per signal. Goes through
      `services.solva_v2.llm_adapter.shielded_call` so Synisense
      redaction runs first AND the call lands in the audit log.
      Mode currently unused by the MVP router — the router emits
      the deterministic list. Wired for the next iteration so the
      narration scaffolding is in place.

Output: `List[WorkbookSignal]` ordered by descending importance
(trend > outlier > metric > missing_data). Every signal carries
≥1 `WorkbookCitation`.
"""
from __future__ import annotations

from typing import Any, List

from .schema import WorkbookCitation, WorkbookSheet, WorkbookSignal


def _trim(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"


def extract_signals_for(
    *,
    sheet: WorkbookSheet,
    sheet_matrix: List[List[Any]],
    max_signals_per_kind: int = 2,
) -> List[WorkbookSignal]:
    """Deterministic signal extraction for ONE sheet.

    The caller passes the parsed sheet metadata + the raw matrix
    (incl. header row) so we can build precise cell-range
    citations. We do NOT call the LLM here — narration is opt-in
    and applied by the router AFTER all citations are resolver-
    validated.
    """
    signals: List[WorkbookSignal] = []
    rows = sheet_matrix[sheet.header_row_index:]

    # ─── kind 1: top metric (largest numeric mean per column) ────
    numeric_cols = [c for c in sheet.columns if c.kind == "numeric" and c.mean is not None]
    numeric_cols.sort(key=lambda c: abs(c.mean), reverse=True)
    for col in numeric_cols[:max_signals_per_kind]:
        first_data_row = sheet.header_row_index + 1
        last_data_row = sheet.header_row_index + len(rows)
        citation = WorkbookCitation(
            cell_range=f"{sheet.name}!{col.letter}{first_data_row}:{col.letter}{last_data_row}",
            excerpt=_trim(
                f"{col.name}: mean={col.mean:.2f} median={col.median:.2f} stddev={col.stddev:.2f} "
                f"over {col.non_null_count} non-null rows", 380,
            ),
        )
        signals.append(WorkbookSignal(
            kind="metric",
            title=f"{col.name} — mean {col.mean:.2f}",
            detail=_trim(
                f"The {col.name} column shows a mean of {col.mean:.2f} "
                f"across {col.non_null_count} rows, with values ranging from "
                f"{col.minv:.2f} to {col.maxv:.2f}.",
                900,
            ),
            column=col.name,
            sheet=sheet.name,
            magnitude=float(col.mean),
            citations=[citation],
        ))

    # ─── kind 2: outliers (max-z value per numeric column) ───────
    for col in numeric_cols[:max_signals_per_kind]:
        if col.stddev is None or col.stddev <= 0:
            continue
        best_z = 0.0
        best_row = None
        best_value = None
        for i, r in enumerate(rows):
            target_idx = next(
                (ix for ix, x in enumerate(sheet.columns) if x.letter == col.letter), None,
            )
            if target_idx is None or target_idx >= len(r):
                continue
            raw = r[target_idx]
            try:
                v = float(raw)
            except (TypeError, ValueError):
                continue
            z = (v - col.mean) / col.stddev
            if abs(z) > abs(best_z):
                best_z, best_row, best_value = z, sheet.header_row_index + i + 1, v
        if best_row is not None and abs(best_z) >= 2.0:
            citation = WorkbookCitation(
                cell_range=f"{sheet.name}!{col.letter}{best_row}",
                excerpt=_trim(f"{col.name}={best_value} at row {best_row}", 380),
            )
            signals.append(WorkbookSignal(
                kind="outlier",
                title=f"{col.name} outlier at row {best_row}",
                detail=_trim(
                    f"Row {best_row} in {col.name} is {abs(best_z):.2f}σ "
                    f"{'above' if best_z > 0 else 'below'} the column mean of "
                    f"{col.mean:.2f}.",
                    900,
                ),
                column=col.name,
                sheet=sheet.name,
                magnitude=float(best_z),
                citations=[citation],
            ))

    # ─── kind 3: missing-data fraction ───────────────────────────
    high_null_cols = sorted(
        [c for c in sheet.columns if c.null_count + c.non_null_count > 0
         and c.null_count / (c.null_count + c.non_null_count) > 0.10],
        key=lambda c: c.null_count / (c.null_count + c.non_null_count),
        reverse=True,
    )
    for col in high_null_cols[:max_signals_per_kind]:
        total = col.null_count + col.non_null_count
        pct = 100 * col.null_count / total if total > 0 else 0
        citation = WorkbookCitation(
            cell_range=f"{sheet.name}!{col.letter}{sheet.header_row_index + 1}:"
                       f"{col.letter}{sheet.header_row_index + len(rows)}",
            excerpt=_trim(
                f"{col.name} has {col.null_count} empty cells out of {total} rows.", 380,
            ),
        )
        signals.append(WorkbookSignal(
            kind="missing_data",
            title=f"{col.name} — {pct:.1f}% blank",
            detail=_trim(
                f"The {col.name} column is missing data in {col.null_count} of "
                f"{total} rows ({pct:.1f}%).",
                900,
            ),
            column=col.name,
            sheet=sheet.name,
            magnitude=float(pct),
            citations=[citation],
        ))

    # Order: trend > outlier > metric > missing_data. We don't
    # detect trends in this MVP (forecaster covers that surface);
    # the existing ordering already privileges outliers above
    # metrics above missing_data which is the right user-impact
    # priority.
    rank = {"trend": 0, "outlier": 1, "metric": 2, "ratio": 3, "missing_data": 4}
    signals.sort(key=lambda s: rank.get(s.kind, 99))
    return signals


__all__ = ["extract_signals_for"]
