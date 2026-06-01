"""Phase P5.14 — workbook_cell citation resolver.

A `WorkbookCitation` carries an Excel-A1 `cell_range` like
`"Revenue!A2:C12"` or a single cell `"Revenue!B14"`. The resolver
validates:

  1. The sheet name resolves to a parsed sheet in the analysis.
  2. The top-left cell row/col is within the sheet's bounds.
  3. The bottom-right cell row/col is within the sheet's bounds.
  4. Top-left ≤ bottom-right in both axes.

Anything that fails any of these trips `CitationUnverifiable` —
the workbook-analyzer analogue of Solva v2's `citation_unverifiable`
failure reason. The router runs every citation through this
resolver before persisting a signal / forecast / anomaly /
simulation. Fabricated ranges therefore never make it to disk.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .schema import WorkbookCitation, WorkbookSheet


class CitationUnverifiable(ValueError):
    """Raised when a `WorkbookCitation` cannot be resolved against
    the analysis's parsed sheets. Message format mirrors Solva v2's
    `citation_unverifiable` so the UI / pytest assertions can rely
    on a stable error string prefix."""
    pass


_A1_RE = re.compile(r"^([A-Z]+)([0-9]+)$")


def _col_letters_to_index(letters: str) -> int:
    """A → 1, Z → 26, AA → 27. 1-indexed."""
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def _split_a1(a1: str) -> tuple[int, int]:
    """`A2` → (1, 2). 1-indexed (col, row). Raises on bad format."""
    m = _A1_RE.match(a1.strip())
    if not m:
        raise CitationUnverifiable(
            f"citation_unverifiable: cell '{a1!r}' is not a valid A1 reference"
        )
    col = _col_letters_to_index(m.group(1))
    row = int(m.group(2))
    if row < 1 or col < 1:
        raise CitationUnverifiable(
            f"citation_unverifiable: cell {a1!r} has non-positive row/col"
        )
    return col, row


@dataclass
class ParsedRange:
    sheet: str
    top_col: int
    top_row: int
    bot_col: int
    bot_row: int


def parse_cell_range(cell_range: str) -> ParsedRange:
    """Parse an Excel-A1 cell-range string."""
    if "!" not in cell_range:
        raise CitationUnverifiable(
            f"citation_unverifiable: cell_range {cell_range!r} missing sheet (expected '<sheet>!<TL>[:<BR>]')"
        )
    sheet, ref = cell_range.split("!", 1)
    sheet = sheet.strip()
    if not sheet:
        raise CitationUnverifiable(
            f"citation_unverifiable: cell_range {cell_range!r} has empty sheet name"
        )
    if ":" in ref:
        tl, br = ref.split(":", 1)
    else:
        tl = br = ref
    tl_col, tl_row = _split_a1(tl)
    br_col, br_row = _split_a1(br)
    if br_col < tl_col or br_row < tl_row:
        raise CitationUnverifiable(
            f"citation_unverifiable: cell_range {cell_range!r} has bottom-right before top-left"
        )
    return ParsedRange(sheet, tl_col, tl_row, br_col, br_row)


class WorkbookCitationResolver:
    """Sync resolver. Constructed once per analysis with the parsed
    sheet metadata. Use `resolve()` to validate a citation; use
    `resolve_many()` to validate a list (collects failures and
    raises a single `CitationUnverifiable` carrying all of them
    for ergonomic upstream error rendering)."""

    def __init__(self, sheets: Sequence[WorkbookSheet]) -> None:
        self._index = {s.name: (s.n_rows + s.header_row_index, s.n_columns) for s in sheets}

    def resolve(self, citation: WorkbookCitation) -> ParsedRange:
        rng = parse_cell_range(citation.cell_range)
        if rng.sheet not in self._index:
            raise CitationUnverifiable(
                f"citation_unverifiable: cell_range {citation.cell_range!r} "
                f"references sheet {rng.sheet!r} which does not exist in this workbook"
            )
        bound_rows, bound_cols = self._index[rng.sheet]
        if rng.bot_row > bound_rows:
            raise CitationUnverifiable(
                f"citation_unverifiable: cell_range {citation.cell_range!r} "
                f"references row {rng.bot_row} (sheet has {bound_rows} rows)"
            )
        if rng.bot_col > bound_cols:
            raise CitationUnverifiable(
                f"citation_unverifiable: cell_range {citation.cell_range!r} "
                f"references column index {rng.bot_col} (sheet has {bound_cols} columns)"
            )
        return rng

    def resolve_many(self, citations: Iterable[WorkbookCitation]) -> List[ParsedRange]:
        out: List[ParsedRange] = []
        failures: List[str] = []
        for c in citations:
            try:
                out.append(self.resolve(c))
            except CitationUnverifiable as e:
                failures.append(str(e))
        if failures:
            raise CitationUnverifiable(
                "citation_unverifiable_batch:\n  - " + "\n  - ".join(failures)
            )
        return out


__all__ = [
    "CitationUnverifiable",
    "ParsedRange",
    "WorkbookCitationResolver",
    "parse_cell_range",
]
