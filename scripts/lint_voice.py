"""Sprint M.0b voice lint — customer-copy banned-vocab scanner.

Source of truth for customer-facing copy:
  • `services/two_pass.py::BANNED_WORDS` (LLM-output ban list)
  • PLUS the "Late additions" from `docs/WEBSITE_BRIEF_V3.md §1.3.1`
    which apply ONLY to customer-facing surfaces (website, marketing
    pages, alt text, marketing docs). Internal LLM voice can still
    use the late additions (e.g. "senior" as audience descriptor).

Targets scanned by default:
  • `frontend/src/pages/marketing/**/*.jsx`
  • `frontend/src/components/marketing/**/*.jsx`
  • `frontend/src/website/**/*.jsx`
  • `docs/marketing_assets.md` (if it exists)
  • Any explicit path passed on the command line.

Usage:
  python scripts/lint_voice.py [extra_paths...]
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
from typing import List, Tuple

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))
from services.two_pass import BANNED_WORDS  # noqa: E402

LATE_ADDITIONS = ["senior"]
ALL_BANNED = list(BANNED_WORDS) + list(LATE_ADDITIONS)
_RE = re.compile(
    "(" + "|".join(r"\b" + re.escape(w) + r"\b" for w in ALL_BANNED) + ")",
    re.IGNORECASE,
)

DEFAULT_TARGETS = [
    REPO / "frontend" / "src" / "pages" / "marketing",
    REPO / "frontend" / "src" / "components" / "marketing",
    REPO / "frontend" / "src" / "website",
    REPO / "docs" / "marketing_assets.md",
]


def _scan_file(path: Path) -> List[Tuple[int, str, str]]:
    hits: List[Tuple[int, str, str]] = []
    if not path.exists():
        return hits
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return hits
    for i, line in enumerate(text.splitlines(), 1):
        for m in _RE.finditer(line):
            hits.append((i, m.group(1), line.strip()[:140]))
    return hits


def scan(targets: List[Path]) -> List[Tuple[Path, int, str, str]]:
    out: List[Tuple[Path, int, str, str]] = []
    for t in targets:
        if t.is_dir():
            for f in t.rglob("*.jsx"):
                out.extend((f,) + h for h in _scan_file(f))
            for f in t.rglob("*.js"):
                out.extend((f,) + h for h in _scan_file(f))
            for f in t.rglob("*.md"):
                out.extend((f,) + h for h in _scan_file(f))
        elif t.is_file():
            out.extend((t,) + h for h in _scan_file(t))
    return out


def main() -> int:
    extras = [Path(p) for p in sys.argv[1:]]
    hits = scan(DEFAULT_TARGETS + extras)
    if not hits:
        print("voice_lint: clean across customer-copy surfaces.")
        return 0
    for path, lineno, word, snippet in hits:
        print(f"{path.relative_to(REPO)}:{lineno}  banned={word!r}  {snippet}")
    print(f"\nvoice_lint: {len(hits)} hit(s).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
