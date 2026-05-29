"""Solva v2 — Slice 2a source-strict render contract tests.

Locks the DOM selector contract the frontend slides expose to e1_tester.
Slice 2b will add runtime multi-viewport probes; this slice asserts the
JSX source carries the required data-attributes + testids.

Why source-strict for Slice 2a:
  • The slides are pure JSX templates — their data-attrs are bytes in
    the source. Asserting them at runtime via Playwright introduces
    a full browser dependency for what is fundamentally a source
    contract.
  • Runtime probes belong in Slice 2b, which adds the remaining 9
    slide kinds + the multi-viewport sweep. By then the surface is
    complete enough to justify the Playwright run.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
V2_DIR = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2"
SHELL = V2_DIR / "SlideShell.jsx"
DIVIDER = V2_DIR / "SectionDivider.jsx"
ORCH = V2_DIR / "SolvaArtefactV2.jsx"
SLIDES = V2_DIR / "slides"


# ─────────────────────────────────────────────────────────────────
# A. SlideShell contract — locked DOM attributes
# ─────────────────────────────────────────────────────────────────


def test_shell_root_carries_required_data_attributes():
    src = SHELL.read_text(encoding="utf-8")
    for attr in (
        'data-solva-v2-slide="true"',
        "data-solva-v2-slide-kind={kind}",
        "data-solva-v2-slide-number={String(number)}",
        'data-solva-v2-slide-footer="true"',
    ):
        assert attr in src, f"SlideShell must declare {attr!r}"


def test_shell_footer_template_matches_locked_string():
    src = SHELL.read_text(encoding="utf-8")
    assert "Solve Session Output" in src
    assert "Confidential" in src
    assert "{contextName}" in src or "{contextName}" in src  # template var
    # Per-slide pagination format n / total
    assert "String(number).padStart(2," in src
    assert "String(total).padStart(2," in src


def test_shell_supports_print_break_per_page():
    src = SHELL.read_text(encoding="utf-8")
    # Tailwind print: variant on break-after-page or break-before-page.
    assert "print:break-after-page" in src or "print:break-before-page" in src, (
        "SlideShell must emit `print:break-after-page` so browser "
        "print-to-PDF produces one slide per page."
    )


# ─────────────────────────────────────────────────────────────────
# B. SectionDivider contract
# ─────────────────────────────────────────────────────────────────


def test_section_divider_does_not_carry_slide_attributes():
    """SectionDividers are NOT slides — they are visual separators
    between narrative arcs. They MUST NOT carry the `data-solva-v2-
    slide` attribute or the `data-solva-v2-slide-kind` attribute,
    because doing so pollutes the locked 13-kind inventory."""
    raw = DIVIDER.read_text(encoding="utf-8")
    # Strip block comments + line comments before contract checks so
    # the explanatory docstring (which references the forbidden
    # attribute names) doesn't trip the guard.
    code = re.sub(r"/\*[\s\S]*?\*/", "", raw)
    code = re.sub(r"//[^\n]*", "", code)
    assert 'data-solva-v2-slide="true"' not in code, (
        "SectionDivider must NOT carry `data-solva-v2-slide=\"true\"`. "
        "Section dividers are visual separators, not slides, and "
        "would pollute the 13-kind inventory."
    )
    assert "data-solva-v2-slide-kind" not in code, (
        "SectionDivider must NOT carry `data-solva-v2-slide-kind`. "
        "Section dividers do not appear in the locked 13-kind enum."
    )
    # Divider-specific data-attrs for tester locator.
    assert 'data-solva-v2-section-divider="true"' in code, (
        "SectionDivider must declare `data-solva-v2-section-divider=\"true\"` "
        "so tests can locate it without polluting the kind enum."
    )
    assert "data-solva-v2-section-divider-number" in code
    assert 'data-solva-v2-section-divider-footer="true"' in code
    # Hairline element for visual continuity with sign-in divider.
    assert 'data-testid="solva-v2-section-divider-hairline"' in code


def test_section_divider_uses_rule_token_for_hairline():
    src = DIVIDER.read_text(encoding="utf-8")
    assert "bg-[var(--rule)]" in src, (
        "SectionDivider hairline must use the `--rule` token "
        "(same color as sign-in page divider, `rgb(184, 182, 175)`)."
    )


# ─────────────────────────────────────────────────────────────────
# C. Per-slide contract — kind values + testids
# ─────────────────────────────────────────────────────────────────


SLICE_2A_SLIDES = {
    "CoverSlide.jsx":             {"kind": "cover",             "extra_testids": ["solva-v2-cover-method-tag", "solva-v2-cover-title", "solva-v2-cover-prepared-for"]},
    "HeadlineSlide.jsx":          {"kind": "headline",          "extra_testids": ["solva-v2-headline-intro", "solva-v2-headline-findings"]},
    "TensionsOverviewSlide.jsx":  {"kind": "tensions_overview", "extra_testids": ["solva-v2-tensions-list"]},
    "PathwaySlide.jsx":           {"kind": "pathway",           "extra_testids": ["solva-v2-pathway-list"]},
}

# Slice 2b — the 9 remaining slide kinds completing the 15-element deck.
SLICE_2B_SLIDES = {
    "PerTensionSlide.jsx":             {"kind": "per_tension",                  "extra_testids": []},
    "ScenariosOverviewSlide.jsx":      {"kind": "scenarios_overview",           "extra_testids": ["solva-v2-scenarios-list"]},
    "PerScenarioConfidenceTable.jsx":  {"kind": "per_scenario_table",           "extra_testids": ["solva-v2-confidence-table"]},
    "SensitivitySlide.jsx":            {"kind": "sensitivity",                  "extra_testids": ["solva-v2-sensitivity-list"]},
    "ReflectionSlide.jsx":             {"kind": "reflection",                   "extra_testids": ["solva-v2-reflection-title", "solva-v2-reflection-questions"]},
    "DecisionLogicSlide.jsx":          {"kind": "decision_logic",               "extra_testids": ["solva-v2-decision-list"]},
    "RiskMitigationSlide.jsx":         {"kind": "risk_mitigation",              "extra_testids": ["solva-v2-risk-list"]},
    "MethodologicalHonestySlide.jsx":  {"kind": "methodological_honesty",       "extra_testids": ["solva-v2-honesty-is", "solva-v2-honesty-is-not", "solva-v2-honesty-confidence-pct"]},
    "InClosingSlide.jsx":              {"kind": "in_closing",                   "extra_testids": ["solva-v2-closing-reframing", "solva-v2-closing-final"]},
}

ALL_SLIDES = {**SLICE_2A_SLIDES, **SLICE_2B_SLIDES}


def test_each_slide_exists():
    for name in ALL_SLIDES:
        path = SLIDES / name
        assert path.is_file(), f"Slide template {name} must exist."


def test_each_slide_passes_correct_kind_to_shell():
    for name, spec in ALL_SLIDES.items():
        src = (SLIDES / name).read_text(encoding="utf-8")
        # SlideShell `kind=` prop must carry the locked enum value.
        match = re.search(r'kind="([^"]+)"', src)
        assert match, f"{name}: must pass a `kind=...` prop to SlideShell"
        assert match.group(1) == spec["kind"], (
            f"{name} must pass kind={spec['kind']!r} to SlideShell, "
            f"got {match.group(1)!r}"
        )


def test_each_slide_emits_its_locked_testids():
    for name, spec in ALL_SLIDES.items():
        src = (SLIDES / name).read_text(encoding="utf-8")
        for tid in spec["extra_testids"]:
            assert tid in src, f"{name} must emit data-testid={tid!r}"


def test_each_slide_imports_shell_from_relative_path():
    """Every slide MUST consume SlideShell from the locked relative
    path — prevents future agents from spinning off a divergent shell."""
    for name in ALL_SLIDES:
        src = (SLIDES / name).read_text(encoding="utf-8")
        assert 'import SlideShell from "../SlideShell"' in src, (
            f"{name} must import SlideShell from '../SlideShell'."
        )


# ─────────────────────────────────────────────────────────────────
# D. Orchestrator contract — feature flag fetch + slide composition
# ─────────────────────────────────────────────────────────────────


def test_orchestrator_fetches_from_v2_payload_endpoint():
    src = ORCH.read_text(encoding="utf-8")
    assert "/solva/sessions/${sessionId}/v2/payload" in src, (
        "Orchestrator must fetch from `/solva/sessions/{sid}/v2/payload`."
    )


def test_orchestrator_handles_integrity_failed_422():
    """The backend returns HTTP 422 when integrity validators block —
    orchestrator MUST render an integrity-review placeholder, NOT
    silently fall back to v1."""
    src = ORCH.read_text(encoding="utf-8")
    assert "integrity_failed" in src
    assert 'data-testid="solva-v2-integrity-failed"' in src
    # The placeholder must surface the offender list so the founder
    # sees the system being honest about its own constraint.
    assert "blocking_offenders" in src


def test_orchestrator_root_carries_required_attribute():
    src = ORCH.read_text(encoding="utf-8")
    assert 'data-testid="solva-v2-artefact-root"' in src
    assert "data-solva-v2-schema-version=" in src


def test_orchestrator_composes_all_slide_kinds():
    """Verify the orchestrator composes a slides[] entry for each of
    the 13 locked slide kinds. Section dividers are NOT slides and
    appear with kind: "section_divider" + isSectionDivider:true so the
    orchestrator can interleave them between narrative arcs without
    polluting the 13-kind inventory."""
    raw = ORCH.read_text(encoding="utf-8")
    # Strip block + line comments so docstring references to
    # forbidden / renamed kinds don't trip the guard.
    src = re.sub(r"/\*[\s\S]*?\*/", "", raw)
    src = re.sub(r"//[^\n]*", "", src)
    for slide_kind in (
        "cover",
        "headline",
        "tensions_overview",
        "per_tension",
        "scenarios_overview",
        "per_scenario_table",
        "sensitivity",
        "reflection",
        "pathway",
        "decision_logic",
        "risk_mitigation",
        "methodological_honesty",
        "in_closing",
    ):
        assert f'kind: "{slide_kind}"' in src, (
            f"Orchestrator must compose a slides entry with kind={slide_kind!r}."
        )
    # Section dividers — interleaved with a single `kind: "section_divider"`
    # value PLUS `isSectionDivider: true` flag so they don't enter the
    # slide-kind inventory.
    assert 'kind: "section_divider"' in src, (
        "Orchestrator must use kind: \"section_divider\" (singular) "
        "for visual separators, not arc-specific kinds."
    )
    assert "isSectionDivider: true" in src, (
        "Section divider entries must carry `isSectionDivider: true` "
        "so the orchestrator can exclude them from the slide-kind "
        "inventory and slide-count attribute."
    )
    # The arc-specific divider kinds from the prior implementation must
    # be removed — they were a contract violation.
    for forbidden in (
        "section_divider_tensions",
        "section_divider_scenarios",
        "section_divider_reflection",
        "section_divider_pathway",
        "section_divider_honesty",
    ):
        assert forbidden not in src, (
            f"Forbidden arc-specific divider kind {forbidden!r} found "
            "— dividers must use the singular 'section_divider' kind."
        )
    # Per_scenario_confidence_table was the wrong KIND VALUE — must
    # be removed. We check for `kind: "per_scenario_confidence_table"`
    # specifically (not the bare substring) so the legitimate Pydantic
    # field name `payload.per_scenario_confidence_table` (which the
    # backend still uses) doesn't trip the guard.
    assert 'kind: "per_scenario_confidence_table"' not in src, (
        "Old kind VALUE 'per_scenario_confidence_table' must be renamed "
        "to 'per_scenario_table' (the locked enum value)."
    )
    # Slice 2b removed the backlog hint placeholder.
    assert "slice_2b_backlog_hint" not in src


# ─────────────────────────────────────────────────────────────────
# E. Wave 4.2.followup.2 compliance on v2 source
# ─────────────────────────────────────────────────────────────────


def test_no_silent_fail_opacity_syntax_in_v2_components():
    """Wave 4.2.followup.2 — `bg-[var(--HEX-VAR)]/N` is the silent-fail
    trap. Every v2 component MUST use Tailwind-config short names
    (`bg-ned-purple/N`) instead."""
    bad = re.compile(r"(bg|border|text|ring)-\[var\(--[a-z-]+\)\]/\d+")
    offenders = []
    for path in V2_DIR.rglob("*.jsx"):
        src = path.read_text(encoding="utf-8")
        for n, line in enumerate(src.splitlines(), 1):
            if bad.search(line):
                offenders.append(f"{path.relative_to(REPO)}:{n}: {line.strip()[:120]}")
    assert not offenders, "Wave 4.2.followup.2 silent-fail syntax found:\n" + "\n".join(offenders)


def test_no_invalid_opacity_step_in_v2_components():
    """Every brand-utility opacity step must be a valid Tailwind step
    (10, 15, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 95, 100, 0, 5)."""
    valid = {"0", "5", "10", "15", "20", "25", "30", "40",
             "50", "60", "70", "75", "80", "90", "95", "100"}
    pat = re.compile(r"\b(?:bg|border|text|ring)-(?:ned-purple|brand-[a-z]+)/(\d+)\b")
    offenders = []
    for path in V2_DIR.rglob("*.jsx"):
        src = path.read_text(encoding="utf-8")
        for m in pat.finditer(src):
            if m.group(1) not in valid:
                offenders.append(f"{path.relative_to(REPO)}: `{m.group(0)}` step `/{m.group(1)}` invalid")
    assert not offenders, "\n".join(offenders)


# ─────────────────────────────────────────────────────────────────
# F. Frontend feature-flag helper contract
# ─────────────────────────────────────────────────────────────────


def test_frontend_feature_flag_helper_truth_table():
    """Spec the truth table — frontend reads ONLY from
    account.feature_flags.solva_v2; env layer is NOT readable from
    frontend at runtime."""
    flag_path = REPO / "frontend" / "src" / "lib" / "solvaV2FeatureFlag.js"
    assert flag_path.is_file(), "frontend feature flag helper must exist"
    src = flag_path.read_text(encoding="utf-8")
    assert "solvaV2EnabledFor" in src
    assert "account.feature_flags" in src or "feature_flags" in src
    # Must NOT execute process.env at runtime — strip comments first
    # so the explanatory disclaimer that mentions process.env doesn't
    # trip the guard. Block comments first, then line comments.
    code = re.sub(r"/\*[\s\S]*?\*/", "", src)
    code = re.sub(r"//[^\n]*", "", code)
    assert "process.env" not in code, (
        "Feature flag helper code must NOT execute `process.env` "
        "at runtime — defeats per-account override capability."
    )


def test_solva_session_wires_v2_via_feature_flag():
    """SolvaSession.jsx must check `solvaV2EnabledFor(account)` and
    swap between v2 and v1 — not hardcode either."""
    page_path = REPO / "frontend" / "src" / "pages" / "SolvaSession.jsx"
    src = page_path.read_text(encoding="utf-8")
    assert "solvaV2EnabledFor(account)" in src, (
        "SolvaSession.jsx must gate v2/v1 swap behind the feature flag."
    )
    assert "<SolvaArtefactV2" in src
    assert "<SolvaArtefact" in src
