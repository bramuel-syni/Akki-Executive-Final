"""AA.followup.5 (2026-02 fork-resume) — monitor_v2 owner-role retrofit.

Locks two invariants:
    1. `routers/monitor_v2.py::CANONICAL_OWNER_ROLES` matches the
       AA-slice-1 `TIOwnerRole` enum (9 tokens, no "CCO" / "Audit
       Committee" / "Risk Committee", adds "CHRO" / "CMO" / "OTHER").
    2. The idempotent migration script canonicalises legacy values
       correctly and is a true no-op on a second run.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"

# Ensure backend modules importable.
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ─────────────────────────────────────────────────────────────────
# A. Constant swap — monitor_v2.CANONICAL_OWNER_ROLES now matches
#    the AA-slice-1 TIOwnerRole enum.
# ─────────────────────────────────────────────────────────────────


def test_aa_f5_canonical_matches_ti_owner_role_enum():
    from routers.monitor_v2 import CANONICAL_OWNER_ROLES  # type: ignore
    expected = (
        "CEO", "CFO", "COO", "CRO", "CTO", "CHRO", "CMO", "CIO", "OTHER",
    )
    assert CANONICAL_OWNER_ROLES == expected, (
        f"monitor_v2.CANONICAL_OWNER_ROLES must equal the AA-slice-1 "
        f"TIOwnerRole enum after the retrofit. Got "
        f"{CANONICAL_OWNER_ROLES!r}."
    )


def test_aa_f5_legacy_tokens_no_longer_in_monitor_v2_constant():
    """Legacy tokens that were in the original 7-tuple must be gone."""
    from routers.monitor_v2 import CANONICAL_OWNER_ROLES  # type: ignore
    for legacy in ("CCO", "Audit Committee", "Risk Committee"):
        assert legacy not in CANONICAL_OWNER_ROLES, (
            f"Legacy token {legacy!r} must be removed from "
            f"monitor_v2.CANONICAL_OWNER_ROLES after AA.followup.5."
        )


def test_aa_f5_new_tokens_present_in_monitor_v2_constant():
    from routers.monitor_v2 import CANONICAL_OWNER_ROLES  # type: ignore
    for added in ("CHRO", "CMO", "OTHER"):
        assert added in CANONICAL_OWNER_ROLES, (
            f"New token {added!r} must be in "
            f"monitor_v2.CANONICAL_OWNER_ROLES after AA.followup.5."
        )


def test_aa_f5_canonical_tuple_matches_tasks_initiatives_literal():
    """The monitor_v2 canonical tuple and the tasks_initiatives
    `TIOwnerRole` Literal MUST stay in lockstep. This guards future
    drift between the two source-of-truths."""
    from routers.monitor_v2 import CANONICAL_OWNER_ROLES  # type: ignore

    # Read the source — TIOwnerRole is a Literal[...] which Python
    # serialises as `Literal["CEO", ...]`. Use `typing.get_args` to
    # extract the literal tokens.
    import typing

    ti_module = importlib.import_module("routers.tasks_initiatives")
    ti_enum = getattr(ti_module, "TIOwnerRole")
    ti_tokens = tuple(typing.get_args(ti_enum))
    assert set(CANONICAL_OWNER_ROLES) == set(ti_tokens), (
        "monitor_v2.CANONICAL_OWNER_ROLES and "
        "tasks_initiatives.TIOwnerRole must contain the SAME tokens "
        "(order may differ). monitor_v2 has "
        f"{set(CANONICAL_OWNER_ROLES)!r}, tasks_initiatives has "
        f"{set(ti_tokens)!r}."
    )


# ─────────────────────────────────────────────────────────────────
# B. Migration script — canonicalisation logic + idempotency.
# ─────────────────────────────────────────────────────────────────


def test_aa_f5_migration_canonicalises_legacy_synonyms():
    from scripts.migrate_aa_followup_5_owner_roles import _canonicalize  # type: ignore

    # Already-canonical (uppercase): no-op.
    for tok in ("CEO", "CFO", "COO", "CRO", "CTO", "CHRO", "CMO", "CIO", "OTHER"):
        assert _canonicalize(tok) == tok

    # Lowercase / mixed-case: uppercased to canonical.
    assert _canonicalize("ceo") == "CEO"
    assert _canonicalize("Ceo") == "CEO"

    # Legacy synonyms: remapped to OTHER.
    assert _canonicalize("CCO") == "OTHER"
    assert _canonicalize("Audit Committee") == "OTHER"
    assert _canonicalize("Risk Committee") == "OTHER"

    # Unknown → OTHER.
    assert _canonicalize("Some Random Role") == "OTHER"

    # None / empty → None (preserves null nullability).
    assert _canonicalize(None) is None
    assert _canonicalize("") is None
    assert _canonicalize("   ") is None


def test_aa_f5_migration_is_idempotent():
    """A row already at its canonical value should stay put."""
    from scripts.migrate_aa_followup_5_owner_roles import _canonicalize  # type: ignore
    for tok in ("CEO", "CFO", "COO", "CRO", "CTO", "CHRO", "CMO", "CIO", "OTHER"):
        first = _canonicalize(tok)
        second = _canonicalize(first)
        assert first == second == tok, (
            f"Idempotency broken at {tok!r}: first={first!r}, second={second!r}"
        )


def test_aa_f5_migration_handles_legacy_remap_idempotently():
    """Running the migration twice on a legacy value must produce the
    same OTHER token both times (not flap)."""
    from scripts.migrate_aa_followup_5_owner_roles import _canonicalize  # type: ignore
    for legacy in ("CCO", "Audit Committee", "Risk Committee", "old-cco"):
        first = _canonicalize(legacy)
        second = _canonicalize(first)
        assert first == second == "OTHER", (
            f"Legacy {legacy!r} should canonicalise to OTHER twice; "
            f"got first={first!r}, second={second!r}."
        )


def test_aa_f5_migration_script_has_dry_run_default():
    """The migration script must be dry-run by default (no --apply)."""
    src = (BACKEND / "scripts" / "migrate_aa_followup_5_owner_roles.py").read_text(encoding="utf-8")
    assert "--apply" in src, "Migration script must expose --apply flag"
    assert "apply_changes: bool" in src or "apply_changes=" in src, (
        "Migration script must thread an apply_changes flag through"
    )
    assert "DRY-RUN" in src, "Migration script must announce DRY-RUN mode"
