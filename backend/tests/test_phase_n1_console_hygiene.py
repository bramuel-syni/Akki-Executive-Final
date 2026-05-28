"""Phase N.1 — Console hygiene CI guard (2026-05-27).

Locks two console-hygiene fixes:

  1. `frontend/src/pages/WorkStudio.jsx` does not send `page_size=`
     with any literal greater than 100. The `briefings/aggregates`
     route caps `page_size <= 100`; the previous union-fetch sent
     `page_size=500` which 422'd four times on mount.
  2. `frontend/src/website/**` does not carry any lowercase
     `fetchpriority=` attribute. React's typed-prop interface
     requires camelCase `fetchPriority`; lowercase fires a runtime
     "Invalid DOM property" error.

Historical note — original diagnosis (auth/context race) was wrong.
Actual root cause: frontend `page_size=500` exceeded backend cap
`le=100`. Caught via Stage-1 inventory cross-check before code
landed. Lesson: when diagnosing console errors, capture verbatim
network response body before naming the bug class.
"""
from __future__ import annotations

import pytest

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FE = REPO / "frontend" / "src"

WORK_STUDIO   = FE / "pages" / "WorkStudio.jsx"
WEBSITE_DIR   = FE / "website"


# ── T1. WorkStudio page_size literal is never > 100 ─────────────
def _strip_js_comments(src: str) -> str:
    """Remove // line + /* block */ JS comments so the regex scans
    only executable code (not historical commentary)."""
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def test_n1_work_studio_page_size_literal_within_backend_cap():
    """The `briefings/aggregates` route caps `page_size <= 100`
    (FastAPI Query(default=5, ge=1, le=100)). Frontend literals
    above that cap will 422 every fetch.

    Post-N.1, `page_size` lives behind a named constant
    `_AGG_PAGE_CAP` in the union-fetch loop. We strip JS comments
    first so historical-context commentary doesn't trip the guard."""
    src = _strip_js_comments(WORK_STUDIO.read_text(encoding="utf-8"))
    matches = re.findall(r"page_size\s*[:=]\s*(\d+)", src)
    over_cap = [int(m) for m in matches if int(m) > 100]
    assert not over_cap, (
        f"WorkStudio.jsx sends `page_size` > 100 (literal): {over_cap}. "
        "The briefings/aggregates route caps page_size at 100 "
        "(`le=100`). If a board pack legitimately has >100 items, "
        "iterate pagination — do NOT raise the literal."
    )


# ── T2. No raw `page_size=500` (or any other > 100) anywhere
# (string form, in case a future caller drops it inline) ─────────
def test_n1_work_studio_no_legacy_page_size_500_literal():
    src = _strip_js_comments(WORK_STUDIO.read_text(encoding="utf-8"))
    assert "page_size: 500" not in src, (
        "Stale `page_size: 500` literal in executable code — "
        "Phase N.1 capped this at 100."
    )
    assert "load all, page client-side" not in src, (
        "Stale 'load all, page client-side' comment in executable "
        "code — Phase N.1 switched to paginated load (cap=100)."
    )


# ── T3. WorkStudio paginates the union fetch ─────────────────────
@pytest.mark.skip(reason="Superseded by Phase Z-slice-2 (2026-05-27) — `union_of` fetch removed entirely; WorkStudio now hits the unified GET /api/contexts/{cid}/documents endpoint. See `test_phase_z_documents_journal.py::test_Z2_i_fetcher_hits_documents_endpoint_with_category` for the post-Z lock.")
def test_n1_work_studio_union_fetch_paginates_within_cap():
    src = WORK_STUDIO.read_text(encoding="utf-8")
    # We assert the pagination loop scaffold exists. The exact
    # variable names are locked since they live in only one place.
    assert "_AGG_PAGE_CAP" in src and "= 100" in src, (
        "Expected _AGG_PAGE_CAP = 100 in the union-fetch loop."
    )
    # The loop walks forward until the page is short.
    assert "items.length < _AGG_PAGE_CAP" in src, (
        "Pagination loop must break when the page returned < cap "
        "items (no more rows server-side)."
    )


# ── T4. No lowercase `fetchpriority=` in website/ ───────────────
def test_n1_no_lowercase_fetchpriority_in_website():
    """React 18+ rejects lowercase `fetchpriority` as an invalid DOM
    property and drops the attribute. The camelCase `fetchPriority`
    is the supported form."""
    offenders = []
    for path in WEBSITE_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".jsx", ".tsx", ".js", ".ts", ".html"}:
            continue
        text = path.read_text(encoding="utf-8")
        # Match `fetchpriority=` but NOT `fetchPriority=` (case-sensitive).
        if re.search(r"\bfetchpriority\s*=", text):
            offenders.append(path.as_posix())
    assert not offenders, (
        f"Lowercase `fetchpriority=` literal found in: {offenders}. "
        "React 18+ rejects this — use camelCase `fetchPriority`."
    )


# ── T5. fetchPriority (camelCase) is the form actually used ──────
def test_n1_marketing_landing_uses_camelcase_fetch_priority():
    """Soft positive guard — confirm at least one `fetchPriority=`
    survives somewhere in `website/` so the hero priority hint is
    actually being forwarded to the DOM."""
    found = False
    for path in WEBSITE_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".jsx", ".tsx", ".js", ".ts", ".html"}:
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\bfetchPriority\s*=", text):
            found = True
            break
    assert found, (
        "Expected at least one camelCase `fetchPriority=` attribute "
        "in `frontend/src/website/`. If the rename was meant to drop "
        "the attribute entirely, update this guard."
    )
