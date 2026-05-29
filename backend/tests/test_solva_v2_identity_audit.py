"""Solva v2 — Slice 2b identity audit guard (2026-05-29).

This test exists to prevent future regression of the Solva-identity
audit pass. The user's directive was explicit:

    "You are not making Solva Solve. You are borrowing from Solve."

Solva v2 borrows the STRUCTURAL pattern from the SOLVE upstream
methodology (verbatim-quote evidence, probability-weighted scenarios,
sensitivity analysis, methodological honesty, decision logic,
sequenced recommendations with cluster derivation). It does NOT
borrow the identity / brand / vocabulary.

This guard scans the v2 code paths for any reintroduced "SOLVE" or
"Solve" string occurrence. The audit baseline is ZERO matches; any
match in v2 code paths is a regression that must be fixed before
slice close.

WHAT THIS GUARDS:
  • backend/services/solva_v2/ — schemas, prompts, payload builder
  • frontend/src/components/solva/artefact_v2/ — slide templates
  • backend/routers/solva_v2_artefact.py — artefact endpoint

WHAT THIS DOES NOT GUARD:
  • Solva engine names like `solve_v2.reflection` SURFACE tags — those
    are internal Mongo audit-log routing keys and renaming them would
    break stored historical data. The audit log is INTERNAL — never
    user-facing — so the SURFACE tag does not affect product identity.
  • The `services/solva/` (v3) tree, which already uses canonical Solva
    naming and is not part of this slice's scope.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]

# Scan scope — v2 code paths only.
SCAN_PATHS = [
    REPO / "backend" / "services" / "solva_v2",
    REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2",
    REPO / "backend" / "routers" / "solva_v2_artefact.py",
]

# Files to scan (recursive).
SCAN_GLOBS = ("*.py", "*.jsx", "*.tsx", "*.js", "*.ts")

# Whitelisted lines — must contain ALL of:
#   - the line is genuinely about referencing the SURFACE tag
#     (internal Mongo audit-log routing), NOT about product naming.
#
# Format: (path_substring, line_substring_match). If a file path matches
# the path_substring AND the line contains the line_substring_match, the
# match is whitelisted. Used sparingly — every entry MUST be justified.
WHITELISTED = (
    # "solve_v2.<engine>" SURFACE tags are internal Mongo audit-log
    # routing keys used by the engine modules to identify themselves
    # in the reasoning_audit_log collection. They are NOT user-facing
    # and renaming them would break stored historical data. The audit
    # log is internal.
    ("services/solva_v2/engines/", 'SURFACE = "solve_v2.'),
)


def _collect_files():
    paths = []
    for base in SCAN_PATHS:
        if base.is_file():
            paths.append(base)
            continue
        if base.is_dir():
            for glob in SCAN_GLOBS:
                paths.extend(p for p in base.rglob(glob) if "__pycache__" not in p.parts)
    return paths


def _is_whitelisted(path: Path, line: str) -> bool:
    rel = str(path.relative_to(REPO))
    for path_sub, line_sub in WHITELISTED:
        if path_sub in rel and line_sub in line:
            return True
    return False


# Audit pattern. Word-boundary regex catching:
#   SOLVE (uppercase product brand)
#   Solve (titlecase product brand)
# Does NOT match: solve_v2 (internal tag, see whitelist), .solve(),
# "solving", "solver" etc — those are verb/method names not brand.
SOLVE_BRAND = re.compile(r"\b(SOLVE|Solve)\b")


# Exception sites — comments / strings where the brand reference is
# DELIBERATE: e.g., the audit test fixture itself. These are tagged by
# a magic marker in the source line: `# SOLVE-AUDIT-WHITELIST` (line
# comment for .py) or `// SOLVE-AUDIT-WHITELIST` (line comment for .jsx).
WHITELIST_MARKER = "SOLVE-AUDIT-WHITELIST"


def test_zero_solve_brand_in_v2_code_paths():
    """No file in the v2 code paths may contain a `SOLVE` / `Solve`
    word match. The audit log SURFACE tags `solve_v2.<engine>` are
    whitelisted via the WHITELISTED table because they are internal
    Mongo audit-log routing keys, not user-facing brand."""
    offenders = []
    for path in _collect_files():
        try:
            src = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(src.splitlines(), 1):
            if WHITELIST_MARKER in line:
                continue
            if SOLVE_BRAND.search(line):
                if _is_whitelisted(path, line):
                    continue
                offenders.append(
                    f"{path.relative_to(REPO)}:{n}: {line.strip()[:140]}"
                )
    assert not offenders, (
        "Solva-identity audit regression — `SOLVE` / `Solve` found in v2 "
        "code paths. Solva borrows STRUCTURE from SOLVE, not IDENTITY. "
        "Replace with Solva-canonical terms. Offenders:\n  "
        + "\n  ".join(offenders)
    )


def test_method_tag_default_is_solva_branded():
    """The cover-slide method_tag default MUST resolve to a Solva
    identity, NOT a SOLVE identity."""
    schema = REPO / "backend" / "services" / "solva_v2" / "artefact_schema.py"
    src = schema.read_text(encoding="utf-8")
    assert 'default="SOLVA · SESSION OUTPUT · CONFIDENTIAL"' in src, (
        "Cover.method_tag default must be 'SOLVA · SESSION OUTPUT · "
        "CONFIDENTIAL' (Solva-canonical), not 'SOLVE'."
    )


def test_footer_template_default_is_solva_branded():
    """The footer-template default MUST start with 'Solva Session Output'."""
    schema = REPO / "backend" / "services" / "solva_v2" / "artefact_schema.py"
    src = schema.read_text(encoding="utf-8")
    assert "Solva Session Output · Confidential" in src, (
        "FooterTemplate.template default must read 'Solva Session "
        "Output · Confidential · ...', not 'Solve Session Output'."
    )


def test_method_one_liner_uses_canonical_5_layer_naming():
    """The cover-slide method default MUST use Solva's canonical
    5-layer naming (Frame Audit · Surface · Depth · Synthesis · Reflection),
    not SOLVE's 4-layer naming (Surface · Depth · Synthesis · Reflection)
    or a fabricated alternative."""
    schema = REPO / "backend" / "services" / "solva_v2" / "artefact_schema.py"
    src = schema.read_text(encoding="utf-8")
    assert "Solva 5-layer pass" in src, (
        "CoverSlide.method default must reference 'Solva 5-layer pass'."
    )
    # The 5 canonical layer names must appear in the default.
    for layer_name in ("frame audit", "surface", "depth", "synthesis", "reflection"):
        assert layer_name in src.lower(), (
            f"CoverSlide.method default must reference the canonical "
            f"layer name {layer_name!r}."
        )


def test_prompts_reference_solva_diagnostic_not_solve():
    """Every v2 prompt that names the diagnostic identity must say
    'Solva diagnostic' or 'Solva 5-layer pass', never 'SOLVE'."""
    prompts = REPO / "backend" / "services" / "solva_v2" / "v2_prompts.py"
    src = prompts.read_text(encoding="utf-8")
    # The audit ensures these phrases exist (positive evidence).
    assert "Solva diagnostic" in src, (
        "v2_prompts.py must reference 'Solva diagnostic' in the prompt "
        "headers. The SOLVE branding leak has been corrected."
    )
    assert "Solva 5-layer pass" in src, (
        "v2_prompts.py must reference 'Solva 5-layer pass' in the "
        "header docstring."
    )


def test_slide_shell_footer_jsx_carries_solva_brand():
    """The SlideShell footer JSX must render 'Solva Session Output',
    not 'Solve Session Output'."""
    shell = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "SlideShell.jsx"
    src = shell.read_text(encoding="utf-8")
    assert "Solva Session Output" in src
    assert "Solve Session Output" not in src


def test_section_divider_footer_jsx_carries_solva_brand():
    """The SectionDivider footer JSX must render 'Solva Session Output'."""
    div = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "SectionDivider.jsx"
    src = div.read_text(encoding="utf-8")
    assert "Solva Session Output" in src
    assert "Solve Session Output" not in src


def test_inputs_range_uses_canonical_solva_layer_numbering():
    """Solva's canonical layer numbering is Layer 0 (frame audit)
    through Layer 4 (reflection). The legacy '1 to 5' numbering was a
    SOLVE leak."""
    pb = REPO / "backend" / "services" / "solva_v2" / "payload_builder.py"
    src = pb.read_text(encoding="utf-8")
    assert "Layer 1 to Layer 5" not in src, (
        "payload_builder._inputs_range must use Solva's canonical "
        "0-4 layer numbering, not the SOLVE-leaked 1-5 numbering."
    )
    assert "Layer 0 (frame audit) to Layer 4 (reflection)" in src
