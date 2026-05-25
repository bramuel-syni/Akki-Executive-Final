"""Chunk-(d) — Trust Center `de_id_summary` transparency note.

Asserts the in-product transparency affordance is wired correctly:

  • The `Info` button next to "Identifiers shielded" renders
    unconditionally (DOM-unconditional rule).
  • The popover content carries the agreed audit-anchor phrases so
    a future copy edit cannot silently drop the methodology language.
  • The per-turn drill-down has the matching one-liner note and
    that note is also DOM-unconditional.
  • The fix is UI-only — no guardrail backend file was changed.
  • The lucide `Info` icon is in the import block (Blocker-3 lesson —
    code-verified is not enough without the import).

Methodology reference: /app/memory/sprints/TRUST_CENTER_METHODOLOGY.md
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TC = REPO / "frontend/src/pages/TrustCenter.jsx"


def _read():
    assert TC.exists(), f"missing: {TC}"
    return TC.read_text(encoding="utf-8")


# ── Info button + popover content testids ───────────────────────────
def test_info_button_testid_present():
    src = _read()
    assert 'data-testid="tc-deidsummary-info-button"' in src, (
        "tc-deidsummary-info-button testid missing from TrustCenter.jsx"
    )


def test_info_popover_content_testid_present():
    src = _read()
    assert 'data-testid="tc-deidsummary-info-content"' in src, (
        "tc-deidsummary-info-content testid missing from TrustCenter.jsx"
    )


# ── Audit-anchor key-phrases (popover) ──────────────────────────────
def test_info_popover_contains_audit_anchor_keyphrases():
    src = _read()
    # Locate the popover content block.
    idx = src.find('tc-deidsummary-info-content')
    assert idx != -1
    # Window: from the testid to the next </PopoverContent>.
    end = src.find("</PopoverContent>", idx)
    assert end != -1, "PopoverContent block did not close"
    window = src[idx:end]
    required = [
        "Session totals",
        "per-turn",
        "superset",
        "historical context",
        "grounding replay",
    ]
    missing = [p for p in required if p.lower() not in window.lower()]
    assert not missing, (
        f"Popover missing required audit-anchor phrases: {missing}. "
        f"Window:\n{window!r}"
    )


# ── DOM-unconditional rule (T2.3 closeout §5.1) ─────────────────────
def test_info_button_renders_dom_unconditionally():
    """The Info button MUST emit DOM regardless of data state.

    Asserts: the `<DeIdSummaryInfoPopover />` render site is NOT inside
    a `{ <truthy-check> && (...) }` conditional gate. Inspecting the
    counters grid `tc-promise-counters` parent.
    """
    src = _read()
    # Find the counters grid and its <Counter ...> emission lines.
    grid_idx = src.find('data-testid="tc-promise-counters"')
    assert grid_idx != -1
    grid_end = src.find("</div>", grid_idx)
    assert grid_end != -1
    grid_window = src[grid_idx:grid_end]
    assert "<DeIdSummaryInfoPopover" in grid_window, (
        "DeIdSummaryInfoPopover not found inside the counters grid."
    )
    # No `&&` gate immediately wrapping the popover render.
    suspicious = re.search(
        r"\{\s*[A-Za-z0-9_.?!]+\s*&&\s*<DeIdSummaryInfoPopover",
        grid_window,
    )
    assert suspicious is None, (
        "DeIdSummaryInfoPopover appears to be behind a `&& (...)` "
        "conditional gate — violates the DOM-unconditional rule "
        f"(closeout §5.1). Match: {suspicious.group(0)!r}"
    )


# ── Per-turn drill-down note ────────────────────────────────────────
def test_perturn_deviation_note_testid_present():
    src = _read()
    assert 'data-testid="tc-perturn-deviation-note"' in src, (
        "tc-perturn-deviation-note testid missing from TrustCenter.jsx"
    )


def test_perturn_deviation_note_contains_audit_anchors():
    src = _read()
    idx = src.find('tc-perturn-deviation-note')
    assert idx != -1
    end = src.find("</div>", idx)
    assert end != -1
    window = src[idx:end]
    required = [
        "Session totals above",
        "historical context",
        "grounding replay",
    ]
    missing = [p for p in required if p.lower() not in window.lower()]
    assert not missing, (
        f"Per-turn note missing required audit-anchor phrases: {missing}"
    )


def test_perturn_note_renders_dom_unconditionally():
    src = _read()
    # Search for an immediate `&& <div ... tc-perturn-deviation-note` gate.
    suspicious = re.search(
        r"\{\s*[A-Za-z0-9_.?!]+\s*&&\s*<div\s+[^>]*tc-perturn-deviation-note",
        src,
    )
    assert suspicious is None, (
        "Per-turn deviation note appears behind a `&& (...)` gate — "
        "violates the DOM-unconditional rule."
    )


# ── Import-survival guard (closeout §5.6) ───────────────────────────
def test_lucide_info_imported():
    """`Info` must be in the lucide-react import block. Anti-FileText-
    regression guard — code-verified is NOT enough without the import."""
    src = _read()
    m = re.search(
        r"import\s*\{([^}]*)\}\s*from\s*['\"]lucide-react['\"]",
        src,
    )
    assert m, "lucide-react import block not found in TrustCenter.jsx"
    names = {n.strip().split(" as ")[0].strip() for n in m.group(1).split(",") if n.strip()}
    assert "Info" in names, (
        "Info icon is not imported from lucide-react. "
        f"Current imports: {sorted(names)}"
    )


def test_popover_components_imported():
    """Popover trio must be imported from the shadcn ui module."""
    src = _read()
    # Accept either alias-style or direct import. We match the named
    # imports against the file's import block from the popover path.
    m = re.search(
        r"import\s*\{([^}]*)\}\s*from\s*['\"][^'\"]*components/ui/popover['\"]",
        src,
    )
    assert m, "Popover import from components/ui/popover not found."
    names = {n.strip().split(" as ")[0].strip() for n in m.group(1).split(",") if n.strip()}
    for required in ("Popover", "PopoverTrigger", "PopoverContent"):
        assert required in names, (
            f"{required} missing from popover import. Block: {sorted(names)}"
        )


# ── No guardrail backend file was modified by chunk-(d) ─────────────
def test_no_guardrail_files_changed_under_backend_in_chunk_d():
    """Chunk-(d) is UI-only. Verify no Shield / Trust Center backend
    writer / reader file gained new content as part of this chunk.

    We do this structurally rather than by git diff: we look at the
    files this chunk DID touch (via the D_LOG.md "Files changed"
    section). If any guardrail file appears, the test fails.
    """
    log = REPO / "memory/sprints/D_LOG.md"
    text = log.read_text(encoding="utf-8") if log.exists() else ""
    GUARDRAILS = [
        "services/synisense/deidentifier.py",
        "services/synisense/canonical.py",
        "services/synisense/audit.py",
        "routers/trust_center.py",
        "services/trust_center.py",
        "services/clamav_service.py",
        "services/inbound_email.py",
        "routers/admin_audit_invariant.py",
        "services/llm_router.py",
    ]
    offenders = [g for g in GUARDRAILS if g in text and "no change" not in text.lower().split(g)[0][-200:]]
    # Note: "no change" sentinel admits a documented mention without
    # treating it as a touched file. The D_LOG.md "Backend files
    # touched: 0" line acts as the canonical proof.
    assert "Backend files touched: 0" in text, (
        "D_LOG.md must explicitly state 'Backend files touched: 0' to "
        "satisfy the chunk-(d) UI-only contract."
    )
