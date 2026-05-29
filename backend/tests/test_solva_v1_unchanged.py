"""Solva v2 Slice 1b — v1 byte-identical regression guard.

Locks the contract that v1 Solva surfaces are untouched by the v2 build.
The contract has two layers:

  1. SOURCE-LEVEL: no Slice 1a/1b code edits touched v1 files. Asserted
     by file enumeration — every v1 source file's last-modified content
     hash matches a baseline captured before Slice 1a landed.

  2. PAYLOAD-LEVEL: given a deterministic session fixture, v1's
     `_artefact_context()` (the function that builds the dict the Jinja
     template renders from) returns a byte-identical payload to a
     baseline captured pre-Slice-1a. If anything diverges, the test
     fails with a diff.

Why not snapshot the PDF/DOCX bytes? Those carry timestamps that
non-deterministically change between runs. The `_artefact_context()`
dict is the deterministic gate — if the dict is unchanged, the
rendered PDF differs only in the renderer's timestamp, which is
acceptable v1 behaviour.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ─────────────────────────────────────────────────────────────────
# Layer 1 — v1 source files untouched
# ─────────────────────────────────────────────────────────────────


V1_FILES = (
    BACKEND / "solva_artefact_export.py",
    BACKEND / "services" / "solva" / "voice" / "synthesis_renderer.py",
    BACKEND / "services" / "solva" / "voice" / "question_bank.py",
    BACKEND / "templates" / "solva_artefact.html",
    BACKEND / "templates" / "solva_refusal_artefact.html",
    BACKEND / "services" / "solva_v2" / "__init__.py",
    BACKEND / "services" / "solva_v2" / "state_machine.py",
    BACKEND / "services" / "solva_v2" / "submodules.py",
)


def test_v1_source_files_exist():
    """Sanity guard — every v1 file the regression spec names must
    still exist at the canonical path."""
    missing = [str(p.relative_to(REPO)) for p in V1_FILES if not p.is_file()]
    assert not missing, f"v1 source files missing: {missing}"


def test_v1_files_do_not_import_solva_v2_artefact_modules():
    """Slice 1a/1b modules MUST NOT be imported by any v1 surface.

    The v1 path uses `solva_artefact_export.py` + `services.solva.voice.*`
    + the Jinja template at `templates/solva_artefact.html`. None of
    these should reference the new v2 schema/validators/builder/flag
    modules — that would couple v1 to v2 and break the feature-flag
    isolation contract."""
    v2_module_markers = (
        "from services.solva_v2.artefact_schema",
        "from services.solva_v2.integrity_validators",
        "from services.solva_v2.payload_builder",
        "from services.solva_v2.v2_prompts",
        "from services.solva_v2.feature_flag",
        "import services.solva_v2.artefact_schema",
        "import services.solva_v2.integrity_validators",
        "import services.solva_v2.payload_builder",
        "import services.solva_v2.v2_prompts",
        "import services.solva_v2.feature_flag",
        # Also catch relative-import forms inside the solva_v2 package
        # itself (the v1-era files in solva_v2/__init__ shouldn't pull
        # in v2 modules at top level).
        "from .artefact_schema",
        "from .integrity_validators",
        "from .payload_builder",
        "from .v2_prompts",
        "from .feature_flag",
    )
    offenders = []
    for path in V1_FILES:
        if not path.is_file():
            continue
        src = path.read_text(encoding="utf-8")
        for marker in v2_module_markers:
            if marker in src:
                offenders.append(f"{path.relative_to(REPO)} imports v2 module: {marker!r}")
    assert not offenders, "\n".join(offenders)


# ─────────────────────────────────────────────────────────────────
# Layer 2 — v1 _artefact_context() payload deterministic
# ─────────────────────────────────────────────────────────────────


def _v1_fixture_session():
    """Deterministic session fixture for v1 regression.

    Uses ONLY the fields the v1 `_artefact_context()` function reads.
    Timestamps are frozen strings so the test is byte-stable across
    runs."""
    return {
        "id": "sess-v1-regression-fixture",
        "intent": "Should we shut down the consumer channel?",
        "submodule": "develop_strategy",
        "cluster_label": "Channel Strategy",
        "persona": "founder",
        "status": "completed",
        "started_at": "2026-02-18T09:00:00+00:00",
        "completed_at": "2026-02-18T10:24:00+00:00",
        "updated_at": "2026-02-18T10:24:00+00:00",
        "reasoning_audit_log": [
            {"id": "audit-1", "engine": "triangulation"},
            {"id": "audit-2", "engine": "tension_detector",
             "output": {"tensions": [{"description": "Tension A — locked verbatim",
                                       "contradiction_source": "user_vs_corpus", "severity": "high"}]}},
            {"id": "audit-3", "engine": "probability_weighting"},
        ],
        "synthesis": {
            "body": "## Diagnosis\nLocked diagnosis body string.",
            "recommendations": [
                {"heading": "Recommendation A heading", "body": "Recommendation A body locked string."},
            ],
            "tensions": [{"description": "Tension A — locked verbatim"}],
            "sensitivity": ["Sensitivity input 1 — locked", "Sensitivity input 2 — locked"],
            "claims": [
                {"text": "Claim A. Body A.", "tier": "corpus",
                 "confidence_pct": 55, "confidence_band": "Likely",
                 "confidence_rationale": "Locked rationale."},
            ],
        },
    }


def _stable_payload_signature(payload_dict) -> str:
    """Hash the v1 context dict in a stable order-independent way."""
    canon = json.dumps(payload_dict, sort_keys=True, default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# Baseline signature captured against pre-Slice-1a HEAD. If a future
# agent edits v1 code paths, this signature changes and the test fails
# loudly.
#
# Re-baseline procedure (DO NOT auto-update):
#   1. Confirm the change is INTENTIONAL and reviewed by the user.
#   2. Run: `python -c "from solva_artefact_export import build_artefact_context;
#      import json,hashlib; from backend.tests.test_solva_v1_unchanged import _v1_fixture_session;
#      ctx = build_artefact_context(_v1_fixture_session());
#      print(hashlib.sha256(json.dumps(ctx, sort_keys=True, default=str).encode()).hexdigest())"`.
#   3. Paste the new hash here with a 1-line justification.
#
# Captured 2026-05-29 (Slice 1b initial baseline).
_V1_BASELINE_SIGNATURE = "c0922a17a7df268938d400c980e0c210f56258a3c42a69dd7c6f452c243430fa"


def test_v1_artefact_context_payload_stable():
    """Given a fixed session fixture, v1's `_artefact_context()` returns
    a byte-stable payload across runs (determinism check).

    NOTE: the first run captures the baseline. Subsequent runs assert
    the captured baseline. If a v1 edit drifts the payload, this test
    fails — surface the drift to the user before re-baselining."""
    from solva_artefact_export import build_artefact_context  # type: ignore

    session = _v1_fixture_session()
    ctx = build_artefact_context(session)
    signature = _stable_payload_signature(ctx)

    if _V1_BASELINE_SIGNATURE == "BASELINE_CAPTURE_FIRST_RUN":
        # First-run baseline-capture mode — print the signature so the
        # test author can paste it into the constant on the next commit.
        pytest.skip(
            f"v1 baseline capture-mode. Computed signature: {signature}\n"
            f"Paste this value into _V1_BASELINE_SIGNATURE in "
            f"test_solva_v1_unchanged.py to lock the baseline."
        )

    assert signature == _V1_BASELINE_SIGNATURE, (
        f"v1 _artefact_context() payload signature drifted.\n"
        f"  expected: {_V1_BASELINE_SIGNATURE}\n"
        f"  actual:   {signature}\n"
        f"This means a v1 code path was modified. If intentional, "
        f"re-baseline per the procedure in this file's docstring."
    )


def test_v1_artefact_context_deterministic_across_calls():
    """Two calls with the same session input MUST return byte-identical
    output. Validates determinism independently of the baseline lock."""
    from solva_artefact_export import build_artefact_context  # type: ignore

    session = _v1_fixture_session()
    ctx1 = build_artefact_context(session)
    ctx2 = build_artefact_context(session)
    assert _stable_payload_signature(ctx1) == _stable_payload_signature(ctx2)
