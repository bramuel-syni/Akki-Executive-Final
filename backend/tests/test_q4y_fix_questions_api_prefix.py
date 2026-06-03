"""Q4Y-FIX (2026-02 fork-resume) — Source-text lockdown that the
`/api/api/me/questions` double-prefix typo never regresses.

Root cause (cited):
  • `frontend/src/pages/Questions.jsx:456` originally called
    `api.get("/api/me/questions", ...)`.
  • `frontend/src/lib/api.js:45-49` sets axios `baseURL = "/api"`.
  • Axios prepends baseURL to non-absolute URLs → actual request
    URL was `/api/api/me/questions` → HTTP 404 → page rendered
    empty state silently (catch block swallows the error).

Git blame (cited): `c0feb6790` (2026-05-12, Patch 14 — the page's
original implementation). Single-line outlier; every other
`api.get()` call in the codebase uses the bare-path form.

Fix: drop the redundant `/api/` prefix on the offending caller.

This test is a SOURCE-TEXT lockdown — assert that no
`api.get("/api/...")` (or other axios verb) caller in the
codebase regresses to the doubled-prefix shape. If anyone ever
re-introduces the typo on any page, this test fails with a
precise file:line citation.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent.parent
FE_SRC = REPO / "frontend" / "src"
QUESTIONS_PAGE = FE_SRC / "pages" / "Questions.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════
# The specific regression guard
# ═════════════════════════════════════════════════════════════════════
def test_q4y_fix_questions_page_uses_bare_me_questions_path():
    """The /me/questions caller on the Questions page MUST use the
    bare-path form (`api.get("/me/questions", …)`) — the axios
    `baseURL` already prepends `/api`. The legacy form
    `api.get("/api/me/questions", …)` produced the doubled
    `/api/api/me/questions` 404 that silently broke the page."""
    src = _read(QUESTIONS_PAGE)
    # Negative — the regressed form must NOT be present.
    assert 'api.get("/api/me/questions"' not in src, (
        "Questions.jsx regressed to the doubled-/api form on the "
        "/me/questions caller. The axios baseURL already prepends "
        "/api — use api.get(\"/me/questions\", ...)."
    )
    # Positive — the fixed form must be present (otherwise the
    # endpoint isn't called at all, which is also a regression).
    assert 'api.get("/me/questions"' in src


# ═════════════════════════════════════════════════════════════════════
# Repo-wide guard against the same root-cause class
# ═════════════════════════════════════════════════════════════════════
def test_q4y_fix_no_doubled_api_prefix_repo_wide():
    """Sweep every .js/.jsx file under frontend/src and confirm no
    axios verb call carries a leading `/api/` URL. The axios client
    `baseURL` is `/api`; passing `"/api/..."` produces the doubled-
    prefix 404 class that Q4Y-FIX repairs.

    Whitelist: literal `BASE_URL`/`API_BASE` documentation strings
    in `frontend/src/lib/api.js` (the helpers that DEFINE the
    baseURL itself). Comments are also allowed.
    """
    pattern = re.compile(r'\bapi\.(get|post|put|patch|delete)\(\s*["\']/api/')
    offenders: list[str] = []
    for path in FE_SRC.rglob("*.js*"):
        if path.suffix not in (".js", ".jsx"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            if pattern.search(line):
                offenders.append(
                    f"{path.relative_to(REPO)}:{lineno}: {line.strip()}"
                )
    assert offenders == [], (
        "Regression — at least one frontend caller passes a leading "
        "/api/ to an axios verb (the axios client's baseURL already "
        "prepends /api, producing /api/api/...). Offenders:\n  "
        + "\n  ".join(offenders)
    )
