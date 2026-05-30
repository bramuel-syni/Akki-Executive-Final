"""Phase P2 C.1 — IP scrub lockdown.

Verifies the 7 REVEAL phrases from `P1_theta_ip_scrub_catalog.md`
are absent from public website source files post-rewrite.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

BANNED_REVEALS = [
    # 5-layer / 5-layer-pipeline phrasings
    "five-layer pipeline",
    "five layers of work",
    "Structured reasoning with five layers",
    "Five reasoning layers, each auditable",
    # 16-slide specific
    "fully-cited 16-slide diagnosis",
    "16-slide diagnosis",
    # Per-layer name leakage (canonical sequences)
    "frame audit, candidate generation, tension detection, probability weighting, reflection",
    "frame audit, candidates, tension, probability weighting, reflection",
]


def _scan(file_path: Path) -> list[str]:
    text = file_path.read_text(encoding="utf-8")
    return [b for b in BANNED_REVEALS if b in text]


def test_c1_copy_index_clean():
    p = REPO / "frontend" / "src" / "website" / "copy" / "index.js"
    hits = _scan(p)
    assert hits == [], f"IP-reveal phrases still present in {p}: {hits}"


def test_c1_public_velocity_tile_clean():
    p = REPO / "frontend" / "src" / "website" / "components" / "PublicVelocityTile.jsx"
    hits = _scan(p)
    assert hits == [], f"IP-reveal phrases still present in {p}: {hits}"


def test_c1_solva_product_page_clean():
    p = REPO / "frontend" / "src" / "website" / "pages" / "product" / "Solva.jsx"
    hits = _scan(p)
    assert hits == [], f"IP-reveal phrases still present in {p}: {hits}"


def test_c1_promise_level_replacement_present():
    """The PROMISE-level replacements landed verbatim."""
    p = REPO / "frontend" / "src" / "website" / "copy" / "index.js"
    text = p.read_text()
    assert "Structured reasoning, fully cited." in text
    assert "Structured reasoning, every step auditable." in text


def test_c1_voice_lint_still_clean():
    """Running the project voice-lint over the touched files yields zero hits."""
    import subprocess
    proc = subprocess.run(
        ["python3", str(REPO / "scripts" / "lint_voice.py")],
        capture_output=True, text=True, cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "voice_lint: clean" in proc.stdout
