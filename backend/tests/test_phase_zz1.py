"""Phase ZZ.1 (2026-02 fork-resume v2) — Synisense reidentification display fix.

The PerMessageSynisenseBadge previously rendered only the redaction
half of the round-trip ("N IDENTIFIERS REDACTED"). ZZ.1 makes the
full Synisense contract visible:

  Redact before the model sees the prompt
  Restore before the user sees the reply

The user now sees a single source-of-truth label that names both
halves: "N IDENTIFIERS PROTECTED · RESTORED ON YOUR VIEW".

Lockdown: copy verbatim; voice-clean; reidentified count exposed
through `data-identifiers-restored` attribute for downstream
analytics.
"""
from __future__ import annotations
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
BADGE = REPO / "frontend" / "src" / "components" / "chat" / "PerMessageSynisenseBadge.jsx"
SOLVA_V1_BADGE = REPO / "frontend" / "src" / "components" / "solva" / "artefact" / "PerSectionSynisenseBadge.jsx"


def test_zz_1_label_includes_restored_half():
    """The badge must surface BOTH halves of the round-trip in the
    user-visible label — not the redact half alone."""
    src = BADGE.read_text(encoding="utf-8")
    assert "PROTECTED · RESTORED ON YOUR VIEW" in src
    # Singular + plural variants both locked
    assert "1 IDENTIFIER PROTECTED · RESTORED ON YOUR VIEW" in src
    assert '${n} IDENTIFIERS PROTECTED · RESTORED ON YOUR VIEW' in src
    # The legacy "N IDENTIFIERS REDACTED" wording must NOT be the
    # primary label (allowed in tooltip + comments only).
    # Strip comments to check primary copy.
    no_comments = "\n".join(
        ln for ln in src.splitlines()
        if not ln.strip().startswith("*") and not ln.strip().startswith("//")
    )
    assert '"1 IDENTIFIER REDACTED"' not in no_comments
    assert '`${n} IDENTIFIERS REDACTED`' not in no_comments


def test_zz_1_tooltip_breakdown_includes_redacted_and_restored():
    """The tooltip should still expose per-layer breakdown PLUS the
    explicit Redacted/Restored split (so a curious user can verify
    the round-trip numerically)."""
    src = BADGE.read_text(encoding="utf-8")
    assert "Redacted before model:" in src
    assert "Restored on your view:" in src
    assert "Layer 1 regex" in src and "Layer 2 Presidio" in src and "Layer 3 fallback" in src


def test_zz_1_dom_data_attributes_for_downstream_analytics():
    src = BADGE.read_text(encoding="utf-8")
    assert "data-identifiers-redacted={n}" in src
    assert "data-identifiers-restored={n}" in src


def test_zz_1_solva_v1_badge_untouched():
    """v1 byte-identical guard — Solva v1 PerSectionSynisenseBadge
    must NOT have been edited as a side-effect."""
    src = SOLVA_V1_BADGE.read_text(encoding="utf-8")
    # The v1 label still uses the legacy REDACTED wording (it's
    # locked at byte-level; only the chat badge gets the round-trip
    # restatement).
    assert "IDENTIFIERS REDACTED" in src


def test_zz_1_voice_lint_on_new_label():
    """The new label is mechanical: PROTECTED · RESTORED ON YOUR
    VIEW — all voice-clean."""
    banned = ["leverage", "empower", "AI-powered", "AI-driven",
              "insights", "dashboard", "seamless", "revolutionary",
              "cutting-edge", "disrupt", "frictionless", "unlock",
              "supercharge", "synergy", "game-changer"]
    label = "IDENTIFIERS PROTECTED · RESTORED ON YOUR VIEW"
    for w in banned:
        assert w.lower() not in label.lower(), f"Banned word {w!r} in label"
