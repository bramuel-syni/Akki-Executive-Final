"""Phase P2 C.3 — Wiki article authoring lockdown.

Verifies:
  • All 16 published articles are present in the manifest
  • Every article body matches the locked shell (4 mandatory sections)
  • Every "How to use it" section has a `**Worked example.**` marker
  • Admin-only articles carry `adminOnly: true`
  • Voice-lint clean across `wiki/content/**.md`
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
WIKI_DIR = REPO / "frontend" / "src" / "website" / "wiki" / "content"
INDEX_FILE = REPO / "frontend" / "src" / "website" / "wiki" / "index.js"

EXPECTED_SLUGS = {
    # Work Studio
    "work-studio-chat", "work-studio-compile",
    "work-studio-tasks", "work-studio-documents",
    # Solva
    "solva-overview", "solva-modes", "solva-confidence",
    # Trust
    "trust-center", "trust-pillars", "audit-trail",
    # Account
    "account-auth", "mfa", "cohort",
    # Admin
    "admin-users", "admin-cohort-applications", "admin-prompt-tuning",
}


def _index_text() -> str:
    return INDEX_FILE.read_text(encoding="utf-8")


def test_c3_all_expected_slugs_registered():
    txt = _index_text()
    for slug in EXPECTED_SLUGS:
        assert f'slug: "{slug}"' in txt, f"slug missing from manifest: {slug}"


def test_c3_admin_articles_marked_adminonly():
    txt = _index_text()
    # The admin block must mark every admin-* article with adminOnly: true.
    for slug in ("admin-users", "admin-cohort-applications", "admin-prompt-tuning"):
        # Extract the line for this slug, ensure adminOnly: true present.
        m = re.search(rf'{{.*slug: "{slug}".*?}}', txt, re.DOTALL)
        assert m, f"no manifest entry for {slug}"
        assert "adminOnly: true" in m.group(0), f"{slug} not marked adminOnly"


def test_c3_locked_shell_present_in_every_article():
    """Every article must have all four mandatory sections."""
    for md in WIKI_DIR.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        assert "## What it does" in text, f"missing 'What it does' in {md}"
        assert "## How to use it" in text, f"missing 'How to use it' in {md}"
        assert "## Common questions" in text, f"missing 'Common questions' in {md}"
        assert "## Troubleshooting" in text, f"missing 'Troubleshooting' in {md}"


def test_c3_worked_example_marker_present_in_every_article():
    """Every 'How to use it' must include a Worked example."""
    for md in WIKI_DIR.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        assert "**Worked example.**" in text, f"missing 'Worked example.' in {md}"


def test_c3_voice_lint_includes_wiki_content():
    """Voice-lint scans the wiki content directory and finds zero hits."""
    import subprocess
    proc = subprocess.run(
        ["python3", str(REPO / "scripts" / "lint_voice.py")],
        capture_output=True, text=True, cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_c3_categories_helper_partitions_correctly():
    """The categoriesFor() helper groups + sorts as expected. We can't
    run JS in pytest, but we can confirm the manifest has the right
    shape by reading the export."""
    txt = _index_text()
    # Each entry carries category + order; spot-check the
    # multi-article Work Studio set is sorted ascending by order.
    ws_entries = re.findall(r'slug: "(work-studio-[^"]+)".*?order: (\d+)', txt)
    assert len(ws_entries) >= 4
    orders = [int(o) for _, o in ws_entries]
    assert orders == sorted(orders), f"Work Studio order not ascending: {orders}"
