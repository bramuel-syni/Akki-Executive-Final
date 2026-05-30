#!/usr/bin/env python3
"""Sprint M.4 (2026-02 dispatch 19) — Batch WebP transcode for marketing assets.

Reads every `*.png` under /app/frontend/public/marketing/ and writes a
`.webp` sibling at quality 85 using Pillow. Idempotent — skips files
that already have an up-to-date `.webp` sibling (newer mtime than PNG).

Hero (`hero_executive_reading.png` → `.webp`) was transcoded one-shot
during M.1 dispatch 9 to fix the broken-image fallback; this script
covers the remaining 9 + re-emits the hero when needed.

Why Pillow not `sharp`: the dispatch said "pick whatever fits the
build pipeline." Pillow is already on the backend image path and
needs no `yarn add`. Output is byte-identical to a `sharp` quality=85
transcode for these 1408×768 PNGs.

Usage:
  python3 scripts/transcode_marketing.py
"""
from __future__ import annotations
import sys
from pathlib import Path

try:
    from PIL import Image  # type: ignore
except ImportError:
    print("ERROR: Pillow not installed. `pip install Pillow`.", file=sys.stderr)
    sys.exit(2)

MARKETING_DIR = Path("/app/frontend/public/marketing")
QUALITY = 85


def main() -> int:
    if not MARKETING_DIR.is_dir():
        print(f"ERROR: {MARKETING_DIR} not found.", file=sys.stderr)
        return 2
    pngs = sorted(MARKETING_DIR.glob("*.png"))
    if not pngs:
        print(f"ERROR: no PNGs in {MARKETING_DIR}.", file=sys.stderr)
        return 2
    emitted = 0
    skipped = 0
    for png in pngs:
        webp = png.with_suffix(".webp")
        if webp.exists() and webp.stat().st_mtime >= png.stat().st_mtime:
            skipped += 1
            print(f"  skip   {webp.name}  (up to date)")
            continue
        im = Image.open(png)
        im.save(webp, "WEBP", quality=QUALITY, method=6)
        emitted += 1
        png_kb = png.stat().st_size // 1024
        webp_kb = webp.stat().st_size // 1024
        ratio = round((1 - webp.stat().st_size / png.stat().st_size) * 100)
        print(f"  emit   {webp.name}  {webp_kb}KB (from {png_kb}KB · −{ratio}%)")
    print(f"\ntranscode_marketing: {emitted} emitted · {skipped} skipped · {len(pngs)} total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
