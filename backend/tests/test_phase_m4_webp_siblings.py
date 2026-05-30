"""Sprint M.4 (2026-02 fork-resume v3 dispatch 19) — WebP siblings
lockdown for the 10 marketing assets.

Coverage:
  * Every PNG in /frontend/public/marketing/ has a `.webp` sibling.
  * Each WebP is a valid WebP file (RIFF/WEBP signature).
  * WebP dimensions match the PNG (1408×768).
  * WebP is materially smaller than the PNG (>40% reduction — Pillow
    quality=85 reliably produces 90%+ reductions; 40% guards against
    accidentally writing lossless mode).
  * marketing_assets.md catalogues every WebP sibling with the `✓` marker.
  * transcode_marketing.py is idempotent (skip-when-newer logic).
  * marketing-assets-guard CI workflow invokes this test alongside M.0a.
"""
from __future__ import annotations
import struct
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
MARKETING_DIR = REPO / "frontend" / "public" / "marketing"
DOC = REPO / "docs" / "marketing_assets.md"
WORKFLOW = REPO / ".github" / "workflows" / "marketing-assets-guard.yml"
SCRIPT = REPO / "scripts" / "transcode_marketing.py"

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


def _is_webp(path: Path) -> tuple[bool, int, int]:
    """Return (valid, width, height) by parsing the WebP VP8 / VP8L / VP8X header."""
    with open(path, "rb") as f:
        head = f.read(30)
    if head[:4] != b"RIFF" or head[8:12] != b"WEBP":
        return (False, 0, 0)
    chunk = head[12:16]
    if chunk == b"VP8 ":  # lossy
        w = struct.unpack("<H", head[26:28])[0] & 0x3FFF
        h = struct.unpack("<H", head[28:30])[0] & 0x3FFF
        return (True, w, h)
    if chunk == b"VP8L":  # lossless
        b0, b1, b2, b3 = head[21], head[22], head[23], head[24]
        w = ((b1 & 0x3F) << 8 | b0) + 1
        h = ((b3 & 0x0F) << 10 | b2 << 2 | (b1 & 0xC0) >> 6) + 1
        return (True, w, h)
    if chunk == b"VP8X":  # extended — read canvas dims from bytes 24-29
        with open(path, "rb") as f:
            f.seek(24)
            data = f.read(6)
        w = (data[0] | data[1] << 8 | data[2] << 16) + 1
        h = (data[3] | data[4] << 8 | data[5] << 16) + 1
        return (True, w, h)
    return (False, 0, 0)


# ── WebP siblings present + valid ─────────────────────────────────────


def test_m4_all_webp_siblings_present():
    missing = [s for s in SLUGS if not (MARKETING_DIR / f"{s}.webp").exists()]
    assert not missing, f"Missing WebP siblings: {missing}"


def test_m4_all_webps_are_valid_signature():
    bad = []
    for s in SLUGS:
        valid, _w, _h = _is_webp(MARKETING_DIR / f"{s}.webp")
        if not valid:
            bad.append(s)
    assert not bad, f"WebPs failing signature check: {bad}"


def test_m4_all_webps_match_png_dimensions():
    wrong = []
    for s in SLUGS:
        _valid, w, h = _is_webp(MARKETING_DIR / f"{s}.webp")
        if (w, h) != (1408, 768):
            wrong.append((s, (w, h)))
    assert not wrong, f"WebP dimensions mismatch — must match PNG 1408×768: {wrong}"


def test_m4_webps_materially_smaller_than_pngs():
    """WebP must be at least 40% smaller than the PNG (Pillow q=85
    reliably produces 90%+; this threshold guards against an
    accidental lossless mode or copy-of-PNG-as-WebP bug)."""
    bad = []
    for s in SLUGS:
        png = MARKETING_DIR / f"{s}.png"
        webp = MARKETING_DIR / f"{s}.webp"
        ratio = 1.0 - (webp.stat().st_size / png.stat().st_size)
        if ratio < 0.40:
            bad.append((s, f"{ratio:.0%}"))
    assert not bad, f"WebPs not materially smaller than PNGs: {bad}"


# ── Doc + script source-strict ────────────────────────────────────────


def test_m4_doc_lists_every_webp_sibling():
    doc = DOC.read_text(encoding="utf-8")
    for s in SLUGS:
        line = f"`/marketing/{s}.png`"
        assert line in doc, f"Slug missing from doc: {s}"
    # Doc records the WebP-sibling column for all 10 rows.
    assert doc.count("`.webp` ✓") >= 10


def test_m4_transcode_script_idempotent():
    src = SCRIPT.read_text(encoding="utf-8")
    # Idempotency guard: WebP exists AND mtime >= PNG mtime → skip.
    assert "webp.exists() and webp.stat().st_mtime >= png.stat().st_mtime" in src
    assert "QUALITY = 85" in src


# ── CI guard extension ────────────────────────────────────────────────


def test_m4_ci_workflow_invokes_m4_pytest():
    src = WORKFLOW.read_text(encoding="utf-8")
    assert "test_phase_m4_webp_siblings.py" in src
    assert "Pillow" in src  # for WebP signature parsing in CI
    # transcode script edits also trigger the guard.
    assert '"scripts/transcode_marketing.py"' in src
    # No `|| true` swallow.
    assert "|| true" not in src
