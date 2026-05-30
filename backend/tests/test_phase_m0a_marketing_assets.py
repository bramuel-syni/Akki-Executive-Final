"""Sprint M.0a — Marketing asset mirror presence + sanity tests.

Source of truth: `docs/marketing_assets.md` slug table. The Sprint
M.1 hero rewrite consumes these PNGs from `/marketing/<slug>.png`.

Tests:
  * All 10 slug files exist under /app/frontend/public/marketing/.
  * Each file is a valid PNG (signature check).
  * Each file is at least 50KB (defensive against silent download
    failures that produce 0-byte or HTML-error-page files).
  * Each file's intrinsic dimensions are 1408×768 (native @2x size).
  * marketing_assets.md catalogues every slug and is voice-lint clean.
"""
from __future__ import annotations
import struct
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
MARKETING_DIR = REPO / "frontend" / "public" / "marketing"
DOC = REPO / "docs" / "marketing_assets.md"

SLUGS = [
    "hero_executive_reading",
    "editorial_conversation_oblique",
    "south_asian_executive_portrait",
    "modern_vault_detail",
    "secure_archive_corridor",
    "cohort_peer_group",
    "empty_boardroom_set",
    "modern_library_interior",
    "boardroom_flatlay",
    "hands_annotated_report",
]


def _png_dims(path: Path) -> tuple[int, int] | None:
    """Read PNG IHDR width/height. Returns None if not a valid PNG."""
    with open(path, "rb") as f:
        sig = f.read(8)
        if sig != b"\x89PNG\r\n\x1a\n":
            return None
        f.seek(16)
        w = struct.unpack(">I", f.read(4))[0]
        h = struct.unpack(">I", f.read(4))[0]
        return (w, h)


def test_m0a_all_ten_slugs_present():
    missing = [s for s in SLUGS if not (MARKETING_DIR / f"{s}.png").exists()]
    assert not missing, f"Missing marketing assets: {missing}"


def test_m0a_size_sanity_above_50kb():
    too_small = [
        s for s in SLUGS
        if (MARKETING_DIR / f"{s}.png").stat().st_size < 50_000
    ]
    assert not too_small, (
        f"Suspiciously small files (likely failed download or HTML error): "
        f"{too_small}"
    )


def test_m0a_files_are_valid_pngs():
    bad = []
    for s in SLUGS:
        dims = _png_dims(MARKETING_DIR / f"{s}.png")
        if dims is None:
            bad.append(s)
    assert not bad, f"Files failing PNG signature check: {bad}"


def test_m0a_native_dimensions_1408x768():
    wrong = []
    for s in SLUGS:
        dims = _png_dims(MARKETING_DIR / f"{s}.png")
        if dims != (1408, 768):
            wrong.append((s, dims))
    assert not wrong, (
        f"Assets not at native 1408×768 — re-download required: {wrong}"
    )


def test_m0a_doc_lists_every_slug():
    doc = DOC.read_text(encoding="utf-8")
    missing_from_doc = [s for s in SLUGS if f"`{s}`" not in doc]
    assert not missing_from_doc, (
        f"Slugs absent from docs/marketing_assets.md: {missing_from_doc}"
    )


def test_m0a_doc_is_voice_clean():
    """marketing_assets.md must pass the voice lint scanner."""
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from lint_voice import scan
    hits = scan([DOC])
    assert not hits, (
        f"voice-lint failures in docs/marketing_assets.md: "
        f"{[(str(p.relative_to(REPO)), ln, w) for p, ln, w, _ in hits]}"
    )
