#!/usr/bin/env python3
"""Phase D evidence PNG exporter.

Generates the AKKI bank-QA evidence pack PNG artefacts into
`/app/memory/bank_qa_evidence/png/`. Two output families:

  1. `architecture.png` — Shield gateway architecture diagram (the
     "consumer → Shield → cloud LLM → consumer" picture from
     `BANK_QA_EVIDENCE_PACK/02_ARCHITECTURE_DIAGRAM.md`). Drawn with
     PIL primitives so the build has no graphviz/mermaid dependency.

  2. `ui_<slug>.png` — A pack of headless-Playwright screenshots of
     the public-website surface (no auth required). Six routes by
     default; pass `--ui-only` or `--diagram-only` to constrain.

Idempotent: re-runs overwrite. The `evidence-pngs` Makefile target
calls this script. Pass `--check` to validate that the output files
exist without regenerating (useful in CI).

Usage:
    python scripts/generate_evidence_pngs.py
    python scripts/generate_evidence_pngs.py --diagram-only
    python scripts/generate_evidence_pngs.py --ui-only
    python scripts/generate_evidence_pngs.py --check
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path("/app/memory/bank_qa_evidence/png")

# ---------------------------------------------------------------------------
# 1. Architecture diagram
# ---------------------------------------------------------------------------
# Layout: top row = 8 consumer routers feeding into the central Shield
# block; the Shield block then talks to the cloud-LLM trio on the right;
# Mongo + APScheduler + audit log sit at the bottom.

_BG = (12, 16, 22)                 # near-black, matches CLI palette
_INK = (236, 240, 244)             # off-white
_DIM = (140, 152, 168)             # secondary text
_ROUTER_FILL = (38, 52, 74)
_ROUTER_EDGE = (96, 124, 168)
_SHIELD_FILL = (88, 52, 24)        # warm amber for the gatekeeper
_SHIELD_EDGE = (240, 168, 64)
_LLM_FILL = (24, 56, 48)
_LLM_EDGE = (96, 188, 152)
_STORE_FILL = (28, 28, 60)
_STORE_EDGE = (140, 140, 220)
_ARROW = (160, 180, 210)
_TITLE = (252, 252, 252)


def _font(size: int):
    """Try DejaVuSans (present on the prod image + dev container);
    fall back to PIL default."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def _rect(draw: ImageDraw.ImageDraw, xy, fill, outline, width=2, radius=10):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _arrow(draw: ImageDraw.ImageDraw, start, end, colour=_ARROW, width=2):
    draw.line([start, end], fill=colour, width=width)
    # Tiny arrowhead — triangle aimed at `end`.
    import math
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    tip_len = 10
    a1 = angle + math.radians(150)
    a2 = angle - math.radians(150)
    p1 = (end[0] + tip_len * math.cos(a1), end[1] + tip_len * math.sin(a1))
    p2 = (end[0] + tip_len * math.cos(a2), end[1] + tip_len * math.sin(a2))
    draw.polygon([end, p1, p2], fill=colour)


def _centered_text(draw, xy_box, text, font, fill):
    """Render `text` centred in the rectangle `xy_box`. Supports
    newline-delimited multi-line strings."""
    lines = text.split("\n")
    bbox_h = sum(font.getbbox(line)[3] - font.getbbox(line)[1] + 4 for line in lines)
    box_w = xy_box[2] - xy_box[0]
    box_h = xy_box[3] - xy_box[1]
    cy = xy_box[1] + (box_h - bbox_h) / 2
    for line in lines:
        bbox = font.getbbox(line)
        line_w = bbox[2] - bbox[0]
        line_h = bbox[3] - bbox[1]
        cx = xy_box[0] + (box_w - line_w) / 2
        draw.text((cx, cy), line, font=font, fill=fill)
        cy += line_h + 4


def render_architecture_diagram(out_path: Path) -> None:
    """Render the Shield-architecture PNG. Canvas is 1600×1000 so the
    rendered file is comfortable to embed in a slide deck without
    pixelation on a 2x display."""
    W, H = 1600, 1000
    img = Image.new("RGB", (W, H), _BG)
    draw = ImageDraw.Draw(img)

    title_font = _font(34)
    label_font = _font(20)
    caption_font = _font(16)

    draw.text((40, 30), "AKKI -- Synisense Shield Gateway", font=title_font, fill=_TITLE)
    draw.text((40, 75), "Consumer -> Shield -> Cloud LLM -> Consumer (CI-enforced exclusivity)",
              font=caption_font, fill=_DIM)

    # ── 8 router boxes across two rows of 4 ──
    router_labels = [
        "Chat router",
        "Solva Phase D",
        "Work Studio",
        "Document Journal",
        "Cycle Manager",
        "Monitor",
        "Pulse",
        "News / RSS",
    ]
    box_w, box_h = 250, 70
    margin_x = 40
    gap_x = (W - 2 * margin_x - 4 * box_w) // 3
    row1_y, row2_y = 130, 230

    router_xy = []  # bottom-centre of each router → arrow start
    for i, label in enumerate(router_labels):
        col = i % 4
        row_y = row1_y if i < 4 else row2_y
        x0 = margin_x + col * (box_w + gap_x)
        y0 = row_y
        _rect(draw, (x0, y0, x0 + box_w, y0 + box_h), _ROUTER_FILL, _ROUTER_EDGE)
        _centered_text(draw, (x0, y0, x0 + box_w, y0 + box_h),
                       label, label_font, _INK)
        router_xy.append((x0 + box_w // 2, y0 + box_h))

    # ── Central Shield block ──
    shield_x0, shield_y0 = 220, 360
    shield_x1, shield_y1 = 1080, 640
    _rect(draw, (shield_x0, shield_y0, shield_x1, shield_y1),
          _SHIELD_FILL, _SHIELD_EDGE, width=3, radius=14)

    # Shield header
    draw.text((shield_x0 + 24, shield_y0 + 18),
              "services.synisense.shield.llm_router",
              font=_font(24), fill=_TITLE)
    draw.text((shield_x0 + 24, shield_y0 + 56),
              "THE ONLY MODULE THAT ISSUES LLM CALLS -- CI-ENFORCED",
              font=caption_font, fill=(248, 200, 120))

    # Shield internal steps
    steps = [
        "1. Validate purpose in ALLOWED_PURPOSES",
        "2. Validate tenant_id == account_id",
        "3. De-identify(text):  regex -> spaCy NER (en_core_web_trf) -> tenant Presidio recog.",
        "4. Issue redacted prompt to cloud LLM (OpenAI / Anthropic / Gemini)",
        "5. Re-identify(response) with per-request reidentification_map",
        "6. Emit trust-receipt (signed HMAC, append-only audit row)",
    ]
    step_y = shield_y0 + 100
    for line in steps:
        draw.text((shield_x0 + 36, step_y), line, font=label_font, fill=_INK)
        step_y += 32

    # ── Cloud LLM trio on the right ──
    llm_labels = ["OpenAI\nGPT family", "Anthropic\nClaude family", "Google\nGemini family"]
    llm_x = shield_x1 + 80
    llm_w, llm_h = 220, 90
    llm_gap = 30
    for i, label in enumerate(llm_labels):
        y0 = shield_y0 + 20 + i * (llm_h + llm_gap)
        _rect(draw, (llm_x, y0, llm_x + llm_w, y0 + llm_h),
              _LLM_FILL, _LLM_EDGE)
        _centered_text(draw, (llm_x, y0, llm_x + llm_w, y0 + llm_h),
                       label, label_font, _INK)
        # Arrow Shield → LLM
        _arrow(draw, (shield_x1, y0 + llm_h // 2), (llm_x, y0 + llm_h // 2))
        # Arrow LLM → Shield (return path)
        _arrow(draw, (llm_x, y0 + llm_h // 2 + 4), (shield_x1, y0 + llm_h // 2 + 4),
               colour=(96, 188, 152, 180))

    # ── Router → Shield arrows ──
    for rx, ry in router_xy:
        _arrow(draw, (rx, ry), (rx, shield_y0), colour=_ARROW)

    # ── Storage row at the bottom ──
    storage_y = 700
    storage_h = 110
    storage = [
        ("MongoDB\n(per-tenant collections)",  60, 540),
        ("APScheduler\n(in-process cron, hourly)", 620, 380),
        ("Audit log\n(SHA-256-chained, immutable)", 1020, 540),
    ]
    for label, x0, w in storage:
        _rect(draw, (x0, storage_y, x0 + w, storage_y + storage_h),
              _STORE_FILL, _STORE_EDGE)
        _centered_text(draw, (x0, storage_y, x0 + w, storage_y + storage_h),
                       label, label_font, _INK)
        # Arrow from shield bottom to storage top
        _arrow(draw,
               (x0 + w // 2, shield_y1),
               (x0 + w // 2, storage_y),
               colour=(140, 140, 220))

    # ── Footer caption ──
    footer = (
        "Tenant isolation: every LLM call carries `tenant_id`; the Shield rejects "
        "cross-tenant access and signs the trust-receipt with a per-tenant HKDF-derived key."
    )
    draw.text((40, H - 50), footer, font=caption_font, fill=_DIM)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG", optimize=True)
    print(f"  wrote {out_path}")


# ---------------------------------------------------------------------------
# 2. UI screenshot pack (Playwright)
# ---------------------------------------------------------------------------
# Public-website routes, no auth needed. The site is served by the
# React dev server on localhost:3000; in the prod image it is served
# by the same FastAPI container behind nginx, but the contract is the
# same set of public routes.

_UI_ROUTES = [
    ("home",          "/"),
    ("trust",         "/trust"),
    ("solva",         "/solva"),
    ("akki_chat",     "/akki-chat"),
    ("work_studio",   "/work-studio"),
    ("methodology",   "/methodology"),
]


def render_ui_screenshots(out_dir: Path, base_url: str) -> None:
    """Open each route in a headless Chromium and save a PNG."""
    from playwright.sync_api import sync_playwright

    # Auto-locate the installed Chromium headless-shell binary. The
    # pre-built dev container may have a slightly older version than
    # the pinned Playwright build asks for; we fall back to whatever
    # `headless_shell` we can find under /pw-browsers/.
    exec_path = None
    pw_root = Path("/pw-browsers")
    if pw_root.exists():
        for shell in sorted(pw_root.glob("chromium_headless_shell-*/chrome-linux/headless_shell"),
                            reverse=True):
            exec_path = str(shell)
            break
        if exec_path is None:
            for shell in sorted(pw_root.glob("chromium-*/chrome-linux/headless_shell"),
                                reverse=True):
                exec_path = str(shell)
                break

    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        launch_kwargs = {"headless": True}
        if exec_path:
            launch_kwargs["executable_path"] = exec_path
        browser = p.chromium.launch(**launch_kwargs)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        for slug, path in _UI_ROUTES:
            url = base_url.rstrip("/") + path
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
                # Give the SPA a chance to paint after networkidle.
                page.wait_for_timeout(800)
                target = out_dir / f"ui_{slug}.png"
                page.screenshot(path=str(target), full_page=False)
                print(f"  wrote {target}")
            except Exception as exc:  # noqa: BLE001
                print(f"  WARN: failed {url} -> {exc}", file=sys.stderr)
        ctx.close()
        browser.close()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagram-only", action="store_true")
    parser.add_argument("--ui-only", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="Verify outputs exist; do not regenerate.")
    parser.add_argument("--base-url", default=os.environ.get(
        "EVIDENCE_BASE_URL", "http://localhost:3000",
    ), help="Frontend base URL for UI screenshots.")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    expected = [OUT_DIR / "architecture.png"]
    for slug, _ in _UI_ROUTES:
        expected.append(OUT_DIR / f"ui_{slug}.png")

    if args.check:
        missing = [p for p in expected if not p.exists()]
        if missing:
            print(f"MISSING evidence PNGs ({len(missing)}):", file=sys.stderr)
            for p in missing:
                print(f"  {p}", file=sys.stderr)
            return 1
        print(f"OK — {len(expected)} evidence PNGs present at {OUT_DIR}")
        return 0

    do_diagram = not args.ui_only
    do_ui = not args.diagram_only

    if do_diagram:
        print("Generating architecture diagram …")
        render_architecture_diagram(OUT_DIR / "architecture.png")

    if do_ui:
        print(f"Generating UI screenshots (base_url={args.base_url}) …")
        render_ui_screenshots(OUT_DIR, args.base_url)

    print(f"Done — {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
