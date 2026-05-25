"""T1 frontend wire-check tests.

Static text/source checks that prove the T1 UI invariants are in place
without having to run a browser.

T1.4 — Generate Brief
  • `ReadingTopBar.jsx` must NOT carry the `akki-overline` class on the
    Generate-Brief button (it overrides `text-white` against the accent
    fill and was the root cause of the visibility regression).
  • `ReadingView.jsx` `handleGenerateBrief` must surface the G3-ratified
    failure copy verbatim: "We couldn't generate a brief from this
    document. Please try again."

T1.5 — All documents routing
  • `HeroDocActions.jsx`'s "All documents" link must point at
    `/app/workspace` (the canonical Document Journal listing per D2),
    not the previous `/app/work-studio` target.
  • `/app/workspace` must be a route registered in App.js.

T1.6 — Add to Cycle
  • `DocumentRoutingActions.jsx` must POST the G1 verbatim payload —
    cycle_id in both the body and the query string — and must list
    Active + Draft cycles from the cycles endpoint.

These are file-source assertions; they are deliberately blunt so the
contract stays human-readable and grep-friendly.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    p = REPO / rel
    assert p.exists(), f"missing source file: {rel}"
    return p.read_text(encoding="utf-8")


# ── T1.4 ────────────────────────────────────────────────────────────
def test_t1_4_generate_brief_button_does_not_use_akki_overline():
    src = _read("frontend/src/components/reading/ReadingTopBar.jsx")
    # Locate the Generate-Brief button block (testid is the anchor).
    idx = src.find('data-testid="reading-generate-brief-btn"')
    assert idx != -1, "Generate Brief button testid missing"
    # Extract the `className="..."` attribute value on the same <Button>.
    open_idx = src.rfind("<Button", 0, idx)
    close_idx = src.find(">", idx)
    assert open_idx != -1 and close_idx != -1
    block = src[open_idx:close_idx]
    import re as _re
    m = _re.search(r'className\s*=\s*"([^"]+)"', block)
    assert m, "className attribute not found on Generate Brief button"
    classes = m.group(1)
    assert "akki-overline" not in classes, (
        "akki-overline forces color: var(--oxblood), overriding text-white "
        "on the accent fill — this is the T1.4 visibility regression."
    )
    assert "text-white" in classes
    assert "uppercase" in classes  # we kept the visual look via tailwind utility


def test_t1_4_generate_brief_failure_toast_is_g3_verbatim():
    src = _read("frontend/src/pages/ReadingView.jsx")
    assert (
        "We couldn't generate a brief from this document. Please try again."
        in src
    ), "T1.4 G3-ratified failure copy is missing or paraphrased."
    # Old copy must be gone so the regression can't sneak back in.
    assert "AKKI couldn’t draft a briefing right now" not in src


# ── T1.5 ────────────────────────────────────────────────────────────
def test_t1_5_all_documents_routes_to_workspace_not_work_studio():
    src = _read("frontend/src/components/home/HeroDocActions.jsx")
    # The All documents Link should point at /app/workspace.
    assert 'to="/app/workspace"' in src
    # And must not retain the previous /app/work-studio target.
    assert 'to="/app/work-studio"' not in src


def test_t1_5_workspace_route_is_registered():
    src = _read("frontend/src/App.js")
    assert 'path="/app/workspace"' in src, (
        "Document Journal listing route is not registered."
    )


# ── T1.6 ────────────────────────────────────────────────────────────
def test_t1_6_doc_routing_uses_g1_payload_shape():
    src = _read("frontend/src/components/documents/DocumentRoutingActions.jsx")
    # G1 wire format: body carries cycle_id + kind:"document" +
    # source_doc_id + title; same cycle_id is also passed as query.
    assert 'cycle_id: selectedCycleId' in src
    assert 'kind: "document"' in src
    assert 'source_doc_id: doc?.id' in src
    assert 'title: doc?.name' in src
    # Endpoint + query param.
    assert "/cycle/contributions?cycle_id=" in src


def test_t1_6_modal_lists_active_and_draft_cycles():
    src = _read("frontend/src/components/documents/DocumentRoutingActions.jsx")
    # Two parallel GETs by status, then merge — this is how the modal
    # populates the Select Cycle dropdown.
    assert 'status: "active"' in src
    assert 'status: "draft"' in src
    # Old agenda-picker path must be gone.
    assert "/cycle/agenda" not in src


def test_t1_6_modal_surfaces_human_readable_error_toasts():
    src = _read("frontend/src/components/documents/DocumentRoutingActions.jsx")
    # 423 cycle locked, 422 validation, 400 generic — each with a
    # bespoke copy. Plus the D6 generic failure copy.
    assert "423" in src
    assert "422" in src
    assert "400" in src
    assert (
        "We couldn't add this document to the cycle. Please try again."
        in src
    )
    # D6 success toast (verbatim).
    assert "Your document has been added to Cycle Manager in " in src
