"""Phase H.4.1 surface-mount sweep — CI guard (2026-05-27).

Verifies every artefact-bearing surface POSTs to `/me/recent-views`
with the three enriched fields (`artefact_id`, `artefact_kind`,
`deep_link`) so the Portfolio Landing "Where you left off" resume
card can deep-link straight back into the artefact.

Audited surfaces:
  1. WorkStudioDocumentPage (page mount)
  2. DocumentDrawer        (drawer artefact open)
  3. TaskDrawer            (drawer artefact open)
  4. Chat.jsx              (active conversation mount)
  5. SolvaSession.jsx      (session mount)
  6. Pulse.jsx             (surface mount)

Locks in:
  T1.  Shared hook `useTrackRecentView` exists at lib/recentViews.js
       with the 6 enrichment params (surfacePath, label, contextId,
       artefactId, artefactKind, deepLink).
  T2.  Each audited surface imports the hook.
  T3.  Each audited surface invokes the hook with `artefactKind`
       matching the expected kind ("document", "task", "chat",
       "solva_session", "pulse").
  T4.  Each audited surface threads a `deepLink` that includes the
       artefact id query/path (so the resume card jumps straight
       into the artefact, not the surface index).
  T5.  No surface posts a recent-view without the enrichment fields
       — i.e. the hook is the only call path; raw `api.post` to
       `/me/recent-views` is forbidden in the frontend.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FE = REPO / "frontend" / "src"

HOOK_FILE         = FE / "lib" / "recentViews.js"
WS_DOC_PAGE       = FE / "pages" / "WorkStudioDocumentPage.jsx"
DOC_DRAWER        = FE / "components" / "documents" / "DocumentDrawer.jsx"
TASK_DRAWER       = FE / "components" / "tasks" / "TaskDrawer.jsx"
CHAT_PAGE         = FE / "pages" / "Chat.jsx"
SOLVA_SESSION     = FE / "pages" / "SolvaSession.jsx"
PULSE_PAGE        = FE / "pages" / "Pulse.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── T1. Shared hook contract ──────────────────────────────────────
def test_h4_sweep_hook_exists_and_declares_six_params():
    src = _read(HOOK_FILE)
    assert "export function useTrackRecentView" in src
    # Six params surfaced.
    for param in (
        "surfacePath",
        "label",
        "contextId",
        "artefactId",
        "artefactKind",
        "deepLink",
    ):
        assert param in src, f"hook missing param `{param}`"
    # Backend route used.
    assert '"/me/recent-views"' in src
    # POST body keys (JS object-shorthand — `surface_path: …`).
    for key in (
        "surface_path:",
        "label",
        "context_id:",
        "artefact_id:",
        "artefact_kind:",
        "deep_link:",
    ):
        assert key in src, f"hook POST body missing key `{key}`"


# ── T2 / T3 / T4. Each surface imports + uses the hook with the
# correct kind + a deep_link that includes the artefact id ────────

_SURFACES = [
    {
        "path":  WS_DOC_PAGE,
        "kind":  "document",
        "deep_link_marker": "/app/documents/",
    },
    {
        "path":  DOC_DRAWER,
        "kind":  "document",
        "deep_link_marker": "/app/work-studio?doc_id=",
    },
    {
        "path":  TASK_DRAWER,
        "kind":  "task",
        "deep_link_marker": "/app/task-manager?task_id=",
    },
    {
        "path":  CHAT_PAGE,
        "kind":  "chat",
        "deep_link_marker": "/app/chat?chat_id=",
    },
    {
        "path":  SOLVA_SESSION,
        "kind":  "solva_session",
        "deep_link_marker": "/app/solva/session/",
    },
    {
        "path":  PULSE_PAGE,
        "kind":  "pulse",
        "deep_link_marker": "/app/pulse",
    },
]


def test_h4_sweep_each_surface_imports_hook():
    for s in _SURFACES:
        src = _read(s["path"])
        assert 'from "@/lib/recentViews"' in src, (
            f"{s['path'].name} must import from @/lib/recentViews"
        )
        assert "useTrackRecentView" in src, (
            f"{s['path'].name} must invoke useTrackRecentView"
        )


def test_h4_sweep_each_surface_threads_artefact_kind():
    for s in _SURFACES:
        src = _read(s["path"])
        # The kind must appear as a string literal next to artefactKind.
        m = re.search(
            r'artefactKind\s*:\s*"([^"]+)"',
            src,
        )
        assert m, f"{s['path'].name} missing `artefactKind: \"…\"`"
        assert m.group(1) == s["kind"], (
            f"{s['path'].name} artefactKind=`{m.group(1)}`, "
            f"expected `{s['kind']}`."
        )


def test_h4_sweep_each_surface_threads_deep_link_with_artefact_id():
    for s in _SURFACES:
        src = _read(s["path"])
        assert s["deep_link_marker"] in src, (
            f"{s['path'].name} missing deep-link marker "
            f"`{s['deep_link_marker']}` — the resume card must jump "
            "straight back into the artefact."
        )


# ── T5. No raw POST to /me/recent-views outside the hook ──────────
def test_h4_sweep_raw_post_forbidden_outside_hook():
    """The only place that calls POST /me/recent-views is the shared
    hook. If a surface bypasses the hook, a raw `api.post("/me/recent-views"` would
    show up — fail loud if so."""
    offenders = []
    for path in FE.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".js", ".jsx", ".ts", ".tsx"}:
            continue
        rel = path.relative_to(FE).as_posix()
        if rel == "lib/recentViews.js":
            continue
        if rel.startswith("_archived/"):
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r'api\.post\s*\(\s*["\']/me/recent-views', text):
            offenders.append(rel)
    assert not offenders, (
        "Raw POST /me/recent-views outside the hook: "
        f"{offenders}. Use useTrackRecentView instead."
    )
