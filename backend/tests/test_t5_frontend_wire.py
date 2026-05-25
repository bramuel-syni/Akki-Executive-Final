"""T5 frontend wire-checks.

Covers C1 / C2 (G4) / C3 (G5) / C5 (G6 parity) / C6 / C7 / C8.

T2.3 lesson — every spec-required section must emit DOM unconditionally;
only its internal content flips on data state.
"""
from __future__ import annotations

import re as _re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    p = REPO / rel
    assert p.exists(), f"missing source file: {rel}"
    return p.read_text(encoding="utf-8")


# ── C1 — Landing ─────────────────────────────────────────────────────
def test_t5_c1_landing_button_is_add_cycle():
    src = _read("frontend/src/pages/cycle/CycleList.jsx")
    # Pre-T5 label was "Add Agenda"; spec C1 step 2 requires "Add Cycle".
    runtime = _re.sub(r"/\*.*?\*/", "", src, flags=_re.DOTALL)
    runtime = _re.sub(r"//.*$", "", runtime, flags=_re.MULTILINE)
    assert ">Add Cycle</" in runtime or ">\n      Add Cycle\n" in runtime or \
           "Add Cycle" in runtime, "Add Cycle label missing on landing CTA"
    # The old "Add Agenda" string must be gone from runtime code.
    assert " Add Agenda</" not in runtime


def test_t5_c1_landing_side_panel_renders_two_cards():
    src = _read("frontend/src/pages/cycle/CycleList.jsx")
    # Side panel cards per spec C1 step 5 / C6 + C7 entry points.
    assert "cycle-list-side-panel-ready" in src
    assert "cycle-list-side-panel-drafts" in src
    # Verbatim card titles per spec.
    assert "Ready to Compile" in src
    assert "Drafts Waiting for You" in src
    # View More links route to the two journals.
    assert "/app/cycle/ready" in src
    assert "/app/cycle/drafts" in src


# ── C2 / G4 — Wizard Step 1 validation ───────────────────────────────
def test_t5_c2_g4_wizard_step_1_all_four_fields_required():
    p = REPO / "frontend/src/components/cycle/CycleSetupWizard.jsx"
    assert p.exists(), "CycleSetupWizard missing"
    src = p.read_text()
    # The four labelled fields must all be present.
    for label in ("Cycle Name", "Objectives / Agenda",
                  "Required Compilation Readiness Score", "Due Date"):
        assert label in src, f"C2 field label missing: {label}"
    # Next is disabled until step1Valid is true.
    assert "disabled={!step1Valid}" in src
    # step1Valid composition references all four fields + isFutureDate.
    block = src[src.find("const step1Valid"):src.find("const step1Valid") + 600]
    assert "cycleName.trim()" in block
    assert "objectives.trim()" in block
    assert "READINESS_OPTIONS.includes(readiness)" in block
    assert "isFutureDate(dueDate)" in block


def test_t5_c2_g4_readiness_options_are_five():
    src = _read("frontend/src/components/cycle/CycleSetupWizard.jsx")
    # Spec C2 step 3 — five fixed options.
    assert "READINESS_OPTIONS = [80, 85, 90, 95, 100]" in src
    # Verbatim helper copy per spec C2 step 3.
    assert (
        "This is the readiness percentage you feel comfortable compiling a draft document from."
    ) in src


def test_t5_c2_g4_validation_banner_emits_unconditionally():
    src = _read("frontend/src/components/cycle/CycleSetupWizard.jsx")
    # The validation banner uses data-testid="cycle-wizard-step-1-validation"
    # and renders unconditionally inside the Step 1 block.
    idx = src.find('data-testid="cycle-wizard-step-1-validation"')
    assert idx != -1
    # Walk back; the immediately-preceding <div is unconditional.
    div_open = src.rfind("<div", 0, idx)
    assert div_open != -1
    prior = src[max(0, div_open - 300):div_open]
    tail = _re.sub(r"/\*.*?\*/", "", prior, flags=_re.DOTALL).rstrip()
    assert not tail.endswith("&& ("), (
        f"G4 validation banner is gated by a conditional render. "
        f"Tail: {tail[-100:]!r}"
    )


# ── C3 / G5 — Wizard Step 2 email regex + dupe block ─────────────────
def test_t5_c3_g5_email_regex_present():
    src = _read("frontend/src/components/cycle/CycleSetupWizard.jsx")
    # The G5 ratified regex — the spec wording is `^[^\s@]+@[^\s@]+\.[^\s@]+$`.
    assert "EMAIL_RE" in src
    assert r"/^[^\s@]+@[^\s@]+\.[^\s@]+$/" in src


def test_t5_c3_g5_duplicate_warning_verbatim():
    src = _read("frontend/src/components/cycle/CycleSetupWizard.jsx")
    # Verbatim G5 dupe warning.
    assert "This contributor is already on the team." in src
    # Duplicate detection blocks the add (findDuplicateOf must short-circuit).
    assert "findDuplicateOf" in src


def test_t5_c3_g5_contributor_fields_all_five():
    src = _read("frontend/src/components/cycle/CycleSetupWizard.jsx")
    # Five fields per spec C3: Name, Email, Role, "What is this person
    # contributing?", "Attach Agenda Item".
    for field in ("Name", "Email", "Role",
                  "What is this person contributing?",
                  "Attach Agenda Item"):
        assert field in src, f"C3 contributor field label missing: {field}"


# ── C4 — Submit wires through to cycle creation ──────────────────────
def test_t5_c4_review_project_brief_posts_to_cycles_endpoint():
    src = _read("frontend/src/components/cycle/CycleSetupWizard.jsx")
    # Final CTA label per spec.
    assert ">\n                Review Project Brief\n" in src or "Review Project Brief" in src
    # Submit posts to the existing /cycles endpoint.
    assert "/cycles" in src
    assert "api.post" in src


# ── C5 / G6 parity — Cycle Page Compile downloads ────────────────────
def test_t5_c5_g6_cycle_page_renders_three_download_buttons():
    src = _read("frontend/src/pages/Cycle.jsx")
    for testid in (
        "cycle-compile-download-docx",
        "cycle-compile-download-pdf",
        "cycle-compile-download-pptx",
    ):
        assert f'data-testid="{testid}"' in src, f"Missing button {testid}"
    # The legacy single "Download .docx" button must be gone from
    # runtime code (strip comments so doc references don't false-positive).
    runtime = _re.sub(r"/\*.*?\*/", "", src, flags=_re.DOTALL)
    runtime = _re.sub(r"//.*$", "", runtime, flags=_re.MULTILINE)
    assert " Download .docx\n" not in runtime
    assert '>Download .docx<' not in runtime


def test_t5_c5_g6_download_handler_hits_render_endpoint():
    src = _read("frontend/src/pages/Cycle.jsx")
    # Cycle.jsx downloadFormat() must call the /render endpoint.
    assert "/work-studio/documents/${out.export_id}/render" in src
    assert 'responseType: "blob"' in src


# ── C6 — Draft Journal page exists + spec scaffolding ─────────────────
def test_t5_c6_draft_journal_page_exists():
    p = REPO / "frontend/src/pages/cycle/CycleDraftJournal.jsx"
    assert p.exists()
    src = p.read_text()
    assert "cycle-draft-journal-header" in src
    assert "cycle-draft-journal-empty" in src
    # Spec C6 step 2 CTAs.
    assert "Approve and Send" in src
    assert ">\n                      <X" in src or "Decline" in src


def test_t5_c6_draft_journal_route_registered():
    src = _read("frontend/src/App.js")
    assert 'path="/app/cycle/drafts"' in src
    assert "CycleDraftJournal" in src


# ── C7 — Ready to Compile Journal page exists + route ─────────────────
def test_t5_c7_ready_journal_page_exists():
    p = REPO / "frontend/src/pages/cycle/CycleReadyJournal.jsx"
    assert p.exists()
    src = p.read_text()
    assert "cycle-ready-journal-header" in src
    assert "cycle-ready-journal-empty" in src
    assert "Ready to Compile" in src


def test_t5_c7_ready_journal_route_registered():
    src = _read("frontend/src/App.js")
    assert 'path="/app/cycle/ready"' in src
    assert "CycleReadyJournal" in src


# ── C8 — Status badges & filter tabs (lives on landing) ──────────────
def test_t5_c8_landing_filter_tabs_include_completed():
    """Spec C1 step 4 / C8: the four filter tabs are
    All / Active / Draft / Completed. Pre-T1.6 the tabs already shipped;
    this test just guards that Completed didn't regress."""
    src = _read("frontend/src/pages/cycle/CycleList.jsx")
    for label in ("all", "active", "draft", "completed"):
        # tabs are wired via a string list / status param.
        assert label in src.lower()
