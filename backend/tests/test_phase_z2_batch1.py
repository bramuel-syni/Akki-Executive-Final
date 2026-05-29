"""Phase Z2 Batch 1 (2026-02 fork-resume v2) — source-strict lockdown.

Locks the Z2.1 + Z2.4 surface changes:

  Z2.1 — Edit-event modal date picker has an Apply button INSIDE a
         popover that commits selection + closes the popover. The
         native `<input type="datetime-local">` trigger is gone.
  Z2.4 — Open Questions empty state has a "Run Solva on a document"
         CTA that navigates to the Solva landing route (/app/solva).
         New empty-state copy passes the WEBSITE_BRIEF_V3 ban list.

Discipline: copy is verbatim-locked here so future agents cannot
silently rewrite the founder-visible strings without dispatching a
new copy phase. Voice-lint guard re-runs the ban list against the
new strings.
"""
from __future__ import annotations
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"
EVENTS_JSX = FRONTEND / "pages" / "Events.jsx"
QUESTIONS_JSX = FRONTEND / "pages" / "Questions.jsx"


# ─── WEBSITE_BRIEF_V3 §1.3 ban list (verbatim) ─────────────────────────
# Used to lockdown-lint any new user-visible copy.
BANNED_WORDS = [
    "leverage",      # as verb
    "empower",
    "empowering",
    "AI-powered",
    "AI-driven",
    "insights",
    "dashboard",
    "game-changer",
    "game-changing",
    "synergy",
    "synergistic",
    "unlock",        # metaphor
    "unlocking",
    "supercharge",
    "supercharged",
    "seamless",
    "revolutionary",
    "revolutionise",
    "cutting-edge",
    "disrupt",
    "disruptive",
    "frictionless",
]


def _voice_lint(snippet: str) -> list[str]:
    """Return any banned terms found in `snippet` (case-insensitive)."""
    lc = snippet.lower()
    hits = []
    for w in BANNED_WORDS:
        if w.lower() in lc:
            hits.append(w)
    return hits


# ─── Z2.1 — Date-picker popover + Apply ────────────────────────────────


def test_z2_1_native_datetime_local_input_removed():
    """The two native `datetime-local` inputs must be gone from the
    Add/Edit event modal — they are replaced by the popover picker."""
    src = EVENTS_JSX.read_text(encoding="utf-8")
    # Strip JSX comments (the `/* ... */` block in the helper docstring
    # legitimately mentions the type as part of its rationale).
    no_block_comments = []
    in_block = False
    for ln in src.splitlines():
        stripped = ln.strip()
        if not in_block and "/*" in stripped:
            in_block = True
        if in_block:
            if "*/" in stripped:
                in_block = False
            continue
        no_block_comments.append(ln)
    body = "\n".join(no_block_comments)
    # Allowed: HTML5 `type="time"` input INSIDE the popover (Apply
    # picker's time-of-day control) is fine.
    # FORBIDDEN: `type="datetime-local"` anywhere in non-comment JSX.
    assert 'type="datetime-local"' not in body, (
        "Native <input type=\"datetime-local\"> must be replaced by "
        "the DateTimeApplyPicker popover."
    )


def test_z2_1_apply_picker_component_exists():
    src = EVENTS_JSX.read_text(encoding="utf-8")
    assert "function DateTimeApplyPicker(" in src, \
        "DateTimeApplyPicker helper component must exist in Events.jsx"
    # Wired in both start and end slots
    assert 'testidPrefix="event-modal-start"' in src
    assert 'testidPrefix="event-modal-end"' in src


def test_z2_1_apply_button_inside_popover():
    """The Apply button MUST live inside <PopoverContent>, not on the
    modal footer. Verified via testid prefix `*-popover-apply`."""
    src = EVENTS_JSX.read_text(encoding="utf-8")
    assert '`${testidPrefix}-popover-apply`' in src, \
        "Apply button testid must be derived inside the popover"
    assert "PopoverContent" in src and "PopoverTrigger" in src
    # Cancel-inside-popover (closes without committing) must also exist
    assert '`${testidPrefix}-popover-cancel`' in src


def test_z2_1_apply_commits_and_closes():
    """The apply() function must call onChange + setOpen(false)."""
    src = EVENTS_JSX.read_text(encoding="utf-8")
    # Look for the apply body
    assert "onChange(_toNaiveLocal(pendingDate, pendingTime));" in src
    assert "setOpen(false);" in src


# ─── Z2.4 — Open Questions empty-state CTA ─────────────────────────────


def test_z2_4_empty_state_has_run_solva_cta():
    src = QUESTIONS_JSX.read_text(encoding="utf-8")
    assert 'data-testid="questions-empty-run-solva"' in src, \
        "Empty state CTA testid missing"
    # CTA copy verbatim
    assert "Run Solva on a document" in src


def test_z2_4_cta_navigates_to_solva_landing():
    src = QUESTIONS_JSX.read_text(encoding="utf-8")
    assert 'navigate("/app/solva")' in src, \
        "Empty state CTA must navigate to /app/solva"


def test_z2_4_empty_state_subtext_verbatim():
    src = QUESTIONS_JSX.read_text(encoding="utf-8")
    assert "Solva reads what you brought and surfaces the questions worth raising." in src


def test_z2_4_empty_state_copy_passes_voice_lint():
    """New empty-state copy must pass WEBSITE_BRIEF_V3 §1.3 ban list."""
    new_copy_strings = [
        "Run Solva on a document",
        "Solva reads what you brought and surfaces the questions worth raising.",
    ]
    for s in new_copy_strings:
        hits = _voice_lint(s)
        assert not hits, f"Voice-lint failed for {s!r}: banned terms {hits}"


def test_z2_4_cta_only_renders_on_open_filter():
    """The Run-Solva CTA must not appear on the Answered filter empty
    state — only on Open / All. Locked via the conditional guard."""
    src = QUESTIONS_JSX.read_text(encoding="utf-8")
    assert '{filter !== "answered" && (' in src, (
        "Answered-branch must NOT render the Run-Solva CTA."
    )
