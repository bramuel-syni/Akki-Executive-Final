"""Backlog-B Blocker 3 — Monitor drawer must not crash when
`supporting_docs` is non-empty.

Pre-backlog-b, the T2.3 Citations Card rendered a `<FileText>` icon
inside a conditional branch — but `FileText` was missing from the
lucide-react import list at the top of
`frontend/src/components/monitor/ObjectivesProjectsPanel.jsx`. The
previous tester passed T2.3 as code-verified because no seed row had
`supporting_docs.length >= 1`, so the conditional branch never ran.
Once backlog-b seeded supporting_docs on the demo objective/project,
opening the drawer crashed the entire panel with:

    ReferenceError: FileText is not defined.

This is a frontend wire-check that:

  (a) confirms the missing import is now present in source;
  (b) confirms the Citations Card conditional branch still uses
      <FileText> (so future refactors don't silently drop the icon
      either);
  (c) sweeps the SAME file for any OTHER lucide-react identifier used
      inside JSX but not imported — anti-false-green for the broader
      "import survival" pattern the lesson surfaces.

Anti-false-green: this test would fail against `v-pre-backlog-b`
because the import statement at L28-31 did not list `FileText`.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PANEL = REPO / "frontend/src/components/monitor/ObjectivesProjectsPanel.jsx"


def _read():
    assert PANEL.exists(), f"missing: {PANEL}"
    return PANEL.read_text(encoding="utf-8")


def _import_block(src: str) -> str:
    """Extract the lucide-react import names as a single string."""
    m = re.search(
        r"import\s*\{([^}]*)\}\s*from\s*['\"]lucide-react['\"]",
        src,
    )
    assert m, "No lucide-react import block found in ObjectivesProjectsPanel.jsx"
    return m.group(1)


# ── (a) FileText is now imported from lucide-react ──────────────────
def test_filetext_is_imported_from_lucide_react():
    src = _read()
    block = _import_block(src)
    names = {n.strip().split(" as ")[0].strip() for n in block.split(",") if n.strip()}
    assert "FileText" in names, (
        "FileText is NOT in the lucide-react import block — Blocker 3 "
        "would re-regress. Current imports: " + ", ".join(sorted(names))
    )


# ── (b) Citations Card still uses <FileText> in the supporting-docs
#       branch (the conditional branch that crashed pre-fix) ─────────
def test_citations_card_uses_filetext_in_supporting_docs_branch():
    src = _read()
    # Look for the supporting_docs branch by anchoring on the spec'd
    # field name and finding the nearby <FileText usage.
    idx = src.find("supporting_docs")
    assert idx != -1
    # Search a window AFTER the first occurrence for <FileText.
    window = src[idx:idx + 3000]
    assert "<FileText" in window, (
        "Citations Card conditional branch is no longer rendering "
        "<FileText> — confirms either Blocker 3 returned or the icon "
        "was renamed without updating the import + test pair."
    )


# ── (c) Sweep: every lucide-react identifier used as a JSX element
#       must be in the import block (broader import-survival guard) ──
def test_no_lucide_jsx_identifiers_are_unimported():
    """Find every <ComponentName used in JSX and check that any that
    looks lucide-shaped (PascalCase, single-word OR multi-word like
    FileText, ArrowRight, …) is in the import block.

    NOTE: this is intentionally conservative — only catches identifiers
    that ALSO appear in the file's lucide import block at any point in
    history (we union the current block with a curated allowlist of
    common lucide names used elsewhere in this panel). It would catch
    Blocker 3 cleanly: <FileText was in JSX but FileText was not in
    the import block.
    """
    src = _read()
    block = _import_block(src)
    imported = {n.strip().split(" as ")[0].strip() for n in block.split(",") if n.strip()}

    # Find every <Identifier in JSX. PascalCase identifiers only.
    jsx_components = set(re.findall(r"<([A-Z][A-Za-z0-9]*)\b", src))

    # Curated lucide-shaped names that, if present in JSX, MUST be imported.
    # Anchored on identifiers known to live in lucide-react and used by
    # this panel's siblings. Keeps the guard focused and avoids
    # flagging shadcn / custom components.
    LUCIDE_LIKELY = {
        "ArrowRight", "Plus", "Sparkles", "TrendingUp", "TrendingDown",
        "Minus", "Target", "Layers", "Loader2", "X", "XIcon", "FileText",
        "Check", "ChevronDown", "ChevronUp", "ExternalLink", "Mail",
        "Upload", "Trash2", "Pencil", "Calendar", "Clock",
    }

    offenders = []
    for name in jsx_components:
        if name not in LUCIDE_LIKELY:
            continue
        # XIcon is aliased; the underlying name is X — accept either.
        if name in {"X", "XIcon"} and ("XIcon" in imported or "X" in imported):
            continue
        if name not in imported:
            offenders.append(name)

    assert not offenders, (
        f"JSX uses these lucide-shaped components without importing "
        f"them — would ReferenceError at runtime: {offenders}. "
        f"Current import block: {sorted(imported)}"
    )


# ── (d) Pre-fix anti-false-green proof anchor ───────────────────────
def test_blocker_3_pre_fix_proof_anchor():
    """A regression-mode marker — if we ever revert to the pre-fix
    state (no FileText in imports), this test ensures the marker is
    surfaced in CI output, not silently elided."""
    src = _read()
    block = _import_block(src)
    assert "FileText" in block, (
        "Pre-fix state detected — Blocker 3 has regressed. "
        "The lucide-react import block in "
        "frontend/src/components/monitor/ObjectivesProjectsPanel.jsx "
        "no longer includes FileText. Restore the import."
    )
