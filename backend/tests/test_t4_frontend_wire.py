"""T4 frontend wire-checks.

T4.1 — Toolbar emits DOCX/PDF/PPTX buttons unconditionally (G6).
T4.2 — Refine failure toast verbatim G7.
T4.3 — W5 Committed state UI elements exist.
T4.4 — Enhance flow entry point + drawer exist.
T4.5 — Enhance Refine failure toast verbatim G10.

T2.3 lesson: every spec-required section emits DOM unconditionally;
only its internal content is data-conditional.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    p = REPO / rel
    assert p.exists(), f"missing source file: {rel}"
    return p.read_text(encoding="utf-8")


# ── T4.1 — Toolbar buttons (G6) ───────────────────────────────────────
def test_t4_1_compiled_doc_toolbar_renders_three_download_buttons():
    src = _read("frontend/src/components/work_studio/overlay/DocumentOverlay.jsx")
    # Three buttons, three testids, in DOCX → PDF → PPTX order.
    pos_docx = src.find('data-testid="document-overlay-download-docx-btn"')
    pos_pdf  = src.find('data-testid="document-overlay-download-pdf-btn"')
    pos_pptx = src.find('data-testid="document-overlay-download-pptx-btn"')
    assert pos_docx != -1, "DOCX download button missing"
    assert pos_pdf  != -1, "PDF download button missing"
    assert pos_pptx != -1, "PPTX download button missing"
    assert pos_docx < pos_pdf < pos_pptx, (
        "Download buttons must render in DOCX → PDF → PPTX order"
    )


def test_t4_1_download_buttons_hit_render_endpoint_per_format():
    src = _read("frontend/src/components/work_studio/overlay/DocumentOverlay.jsx")
    # The onDownload handler must take a `fmt` arg and POST to the
    # /render endpoint with the format query.
    assert "onDownload(\"docx\")" in src
    assert "onDownload(\"pdf\")" in src
    assert "onDownload(\"pptx\")" in src
    assert "/work-studio/documents/${artefactId}/render" in src
    assert 'responseType: "blob"' in src


def test_t4_1_toolbar_buttons_emit_dom_unconditionally():
    """Each download button must NOT be gated by a data conditional —
    they emit DOM regardless of artefact state (T2.3 rule).
    """
    src = _read("frontend/src/components/work_studio/overlay/DocumentOverlay.jsx")
    for testid in (
        "document-overlay-download-docx-btn",
        "document-overlay-download-pdf-btn",
        "document-overlay-download-pptx-btn",
    ):
        idx = src.find(f'data-testid="{testid}"')
        assert idx != -1
        # The button's parent <button> opens with no `&& (` gate
        # in the 400 chars before the opening tag.
        btn_open = src.rfind("<button", 0, idx)
        assert btn_open != -1
        import re as _re
        prior = src[max(0, btn_open - 400):btn_open]
        prior_no_comments = _re.sub(r"/\*.*?\*/", "", prior, flags=_re.DOTALL)
        tail = prior_no_comments.rstrip()
        assert not tail.endswith("&& ("), (
            f"{testid} is gated by a conditional render; T2.3 rule "
            f"requires unconditional DOM. Found tail: {tail[-100:]!r}"
        )


# ── T4.2 — G7 Refine failure toast verbatim ───────────────────────────
def test_t4_2_g7_revise_failure_copy_verbatim():
    src = _read("frontend/src/components/work_studio/overlay/DocumentOverlay.jsx")
    # Verbatim G7 string.
    assert (
        "We couldn't apply that refinement. Please try again."
    ) in src
    # The pre-T4 generic "Revision failed." string must be gone from
    # the catch handler (line-bound search to avoid hitting comments).
    # We accept it appearing in comments or docstrings.
    import re as _re
    runtime = _re.sub(r"/\*.*?\*/", "", src, flags=_re.DOTALL)
    runtime = _re.sub(r"//.*$", "", runtime, flags=_re.MULTILINE)
    assert 'apiErrorMessage(e, "Revision failed."' not in runtime


# ── T4.3 — W5 Committed state UI ──────────────────────────────────────
def test_t4_3_w5_committed_state_renders_create_new_version():
    src = _read("frontend/src/components/work_studio/overlay/DocumentOverlay.jsx")
    # Committed state surfaces a Create New Version affordance per
    # spec §4.C → W5 step 4.
    assert "Create New Version" in src or "create-new-version" in src.lower()


def test_t4_3_w5_committed_state_renders_lock_indicator():
    src = _read("frontend/src/components/work_studio/overlay/DocumentOverlay.jsx")
    # Lock badge / read-only marker per W5 step 1.
    assert "Lock" in src  # imported icon
    assert "committed" in src.lower()


# ── T4.4 — Enhance flow entry exists ──────────────────────────────────
def test_t4_4_w7_w9_enhance_modal_exists():
    p = REPO / "frontend/src/components/studio/EnhanceModal.jsx"
    assert p.exists(), "Enhance modal component missing — W9 entry path broken"


# ── T4.5 — G10 Refine failure toast verbatim ──────────────────────────
def test_t4_5_g10_enhance_refine_failure_copy_verbatim():
    src = _read("frontend/src/components/studio/EnhanceModal.jsx")
    # Verbatim G10 string.
    assert (
        "We couldn't refine this version. Please try again."
    ) in src
