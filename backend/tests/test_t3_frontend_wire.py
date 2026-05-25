"""T3 frontend wire-checks.

Static file-source assertions covering:
  T3.1 — AddToWorkStudioModal spec verbatim + 5 type cards + G8 routing
  T3.2 — AddToCycleModal extracted; HandoffActions uses it for documents
  T3.3 — Work Studio kind-aware routing (Board/Committee → page;
         Minutes/Deck/Report → drawer) + dedicated page registered
  T3.4 — Compile modal inline upload prompt + nested modal + G9 verbatim
         toast wording (ClamAV and generic)

T2.3 lesson: every spec-required section / control must emit DOM
unconditionally; only its internal content is data-conditional.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    p = REPO / rel
    assert p.exists(), f"missing source file: {rel}"
    return p.read_text(encoding="utf-8")


# ── T3.1 — AddToWorkStudioModal ───────────────────────────────────────
def test_t3_1_add_to_work_studio_modal_renders_five_types_in_spec_order():
    src = _read("frontend/src/components/shared/AddToWorkStudioModal.jsx")
    block = src[src.find("ARTEFACT_TYPES"):]
    # Spec D5 verbatim label order: Board Pack · Minutes · Committee Pack · Deck · Report
    seq = ["Board Pack", "Minutes", "Committee Pack", "Deck", "Report"]
    last = -1
    for lbl in seq:
        i = block.find(f'label: "{lbl}"')
        assert i != -1, f"D5 type card '{lbl}' missing"
        assert i > last, f"D5 type card '{lbl}' is out of spec order"
        last = i


def test_t3_1_add_to_work_studio_modal_uses_verbatim_copy():
    src = _read("frontend/src/components/shared/AddToWorkStudioModal.jsx")
    # Title
    assert "<DialogTitle>Add to Work Studio</DialogTitle>" in src
    # Supporting text — spec D5 step 1.
    assert "Choose the artefact type for this document." in src
    # CTA pattern — "Add document ({Type})"
    assert "`Add document (${labelFor(selectedKind)})`" in src
    # Success toast verbatim per D5 step 3.
    assert "Your document has been added to Work Studio as a ${labelFor(selectedKind)}." in src
    # Failure toast verbatim.
    assert "We couldn't add this document to Work Studio. Please try again." in src


def test_t3_1_add_to_work_studio_cta_disabled_until_selection():
    src = _read("frontend/src/components/shared/AddToWorkStudioModal.jsx")
    # The submit button must remain disabled when selectedKind is empty.
    assert "disabled={working || !selectedKind}" in src


def test_t3_1_doc_routing_actions_mounts_the_modal():
    src = _read("frontend/src/components/documents/DocumentRoutingActions.jsx")
    assert "AddToWorkStudioModal" in src
    assert "AddToCycleModal" in src
    # The old simple navigation must be gone from runtime code. Strip
    # comments first so historical references in doc-comments don't
    # trigger a false-negative.
    import re as _re
    runtime = _re.sub(r"/\*.*?\*/", "", src, flags=_re.DOTALL)
    runtime = _re.sub(r"//.*$", "", runtime, flags=_re.MULTILINE)
    assert 'navigate("/app/work-studio?from_doc=' not in runtime
    assert 'navigate(`/app/work-studio?from_doc=' not in runtime


# ── T3.2 — AddToCycleModal extracted and reused ───────────────────────
def test_t3_2_add_to_cycle_modal_extracted_to_shared_component():
    p = REPO / "frontend/src/components/shared/AddToCycleModal.jsx"
    assert p.exists()
    src = p.read_text()
    # G1 verbatim wire format.
    assert 'cycle_id: selectedCycleId' in src
    assert 'kind: "document"' in src
    assert "/cycle/contributions?cycle_id=" in src
    # D6 verbatim success/failure toasts.
    assert "Your document has been added to Cycle Manager in " in src
    assert "We couldn't add this document to the cycle. Please try again." in src
    # Status-aware failure paths.
    assert "423" in src and "422" in src and "400" in src


def test_t3_2_handoff_actions_uses_modal_for_document_kind():
    src = _read("frontend/src/components/shell/HandoffActions.jsx")
    assert "AddToCycleModal" in src
    # The document branch must short-circuit to opening the modal,
    # NOT posting to /questions silently.
    assert 'if (kind === "document"' in src
    # The /questions POST is preserved for other kinds.
    assert "/questions" in src


# ── T3.3 — Work Studio kind-aware routing + dedicated page ────────────
def test_t3_3_workstudio_routes_board_and_committee_to_page():
    src = _read("frontend/src/pages/WorkStudio.jsx")
    block = src[src.find("onOpenDocument={(aid, exportKind)"):]
    assert "cycle_board_pack" in block[:1500]
    assert "cycle_committee_pack" in block[:1500]
    assert "/app/work-studio/document/" in block[:1500]


def test_t3_3_dedicated_page_route_registered():
    src = _read("frontend/src/App.js")
    assert 'path="/app/work-studio/document/:artefactId"' in src
    # Route element must be the dedicated page, NOT WorkStudio itself.
    page_route_block = src[src.find('path="/app/work-studio/document/:artefactId"'):]
    page_route_block = page_route_block[:200]
    assert "WorkStudioDocumentPage" in page_route_block


def test_t3_3_dedicated_page_component_exists():
    p = REPO / "frontend/src/pages/WorkStudioDocumentPage.jsx"
    assert p.exists()
    src = p.read_text()
    # The page wraps DocumentOverlay and includes a back-to-Work-Studio
    # affordance (data-testid surfaced for the tester).
    assert "DocumentOverlay" in src
    assert "work-studio-document-page-back" in src


# ── T3.4 — Compile modal inline upload + G9 verbatim toasts ───────────
def test_t3_4_compile_modal_renders_inline_upload_prompt_unconditionally():
    src = _read("frontend/src/components/work_studio/CompilationWizard.jsx")
    # The W8 verbatim inline copy must be present.
    assert "Can't find your document? Upload it here." in src
    # The prompt container has a stable testid and is NOT gated by a
    # data conditional (T2.3 DOM-unconditional rule). Inspect the JSX
    # between the previous closing tag and our testid — there must be
    # no `&&` (conditional render) just before the opening `<div`.
    idx = src.find('data-testid="wizard-source-upload-prompt"')
    assert idx != -1
    # Walk back to find the most recent `<div` that owns this testid.
    div_open = src.rfind("<div", 0, idx)
    assert div_open != -1
    # The 200 chars before that <div must not contain a conditional
    # render `&& (` — strip block comments first so doc-comments above
    # the div don't trigger a false positive.
    import re as _re
    prior = src[max(0, div_open - 400):div_open]
    prior_no_comments = _re.sub(r"/\*.*?\*/", "", prior, flags=_re.DOTALL)
    # Skip whitespace at the end then check.
    tail = prior_no_comments.rstrip()
    assert not tail.endswith("&& ("), (
        "Inline upload prompt must emit DOM unconditionally. The 400 "
        f"chars before the <div end with: {tail[-100:]!r}"
    )


def test_t3_4_compile_modal_has_nested_upload_modal():
    src = _read("frontend/src/components/work_studio/CompilationWizard.jsx")
    # Nested modal sits OUTSIDE the parent DialogContent so closing
    # it doesn't dismiss the parent Compile modal.
    assert 'data-testid="wizard-source-upload-modal"' in src
    assert 'data-testid="wizard-source-upload-input"' in src
    assert 'data-testid="wizard-source-upload-cancel"' in src


def test_t3_4_compile_modal_g9_toasts_verbatim():
    src = _read("frontend/src/components/work_studio/CompilationWizard.jsx")
    # G9 ratified ClamAV reject — verbatim.
    assert (
        "We couldn't upload that file. It was rejected by virus scanning."
    ) in src
    # G9 ratified generic failure — verbatim.
    assert "Upload failed. Please try again." in src


def test_t3_4_upload_failure_only_closes_nested_modal():
    src = _read("frontend/src/components/work_studio/CompilationWizard.jsx")
    # The failure branch must call setUploadOpen(false) inside the catch
    # block (not setOpen(false) which would close the wizard).
    block = src[src.find("} catch (err)"):]
    # The catch path closes ONLY the nested upload modal.
    assert "setUploadOpen(false)" in block[:1500]
    # The catch path must NOT close the parent Compile modal.
    assert "onClose()" not in block[:1500]
