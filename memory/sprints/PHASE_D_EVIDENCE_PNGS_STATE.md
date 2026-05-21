# Phase D — PNG evidence exports auto-generation — DONE (2026-02)

Anchor for the Phase D execution. Generates the bank-QA evidence-pack
PNG artefacts on demand and provides a `make evidence-pngs` workflow.

## Final state

| Acceptance criterion | Status |
|---|---|
| `/app/memory/bank_qa_evidence/png/` directory created | ✅ |
| Architecture diagram PNG (no graphviz/mermaid dep) | ✅ `architecture.png`, 51 KB, 1600×1000 |
| Headless UI screenshot pack | ✅ 6 routes, 60-480 KB each, 1440×900 |
| `make evidence-pngs` target works | ✅ + 3 sub-targets (`-diagram`, `-ui`, `-check`) |
| `make evidence-pngs-check` CI-friendly guard | ✅ returns rc=0 + count when all 7 PNGs present; rc=1 + list when any missing |
| Re-runs are idempotent | ✅ outputs overwrite |

## Output inventory

```
/app/memory/bank_qa_evidence/png/
├── architecture.png        51 KB   1600x1000   Shield gateway architecture
├── ui_akki_chat.png        59 KB   1440x900    /akki-chat website page
├── ui_home.png            479 KB   1440x900    / homepage hero
├── ui_methodology.png      84 KB   1440x900    /methodology
├── ui_solva.png            59 KB   1440x900    /solva product page
├── ui_trust.png            63 KB   1440x900    /trust shield value-prop
└── ui_work_studio.png      61 KB   1440x900    /work-studio product page
```

7 PNGs total.

## How it works

`scripts/generate_evidence_pngs.py` is a single self-contained Python
script with two responsibilities:

### 1. Architecture diagram (PIL primitives)

Draws the "consumer → Shield → cloud LLM → consumer" picture from
`BANK_QA_EVIDENCE_PACK/02_ARCHITECTURE_DIAGRAM.md` using only
rounded rectangles, lines, arrowheads, and DejaVuSans text. This
removes the need for a graphviz / mermaid / pandoc system dep so the
diagram regenerates cleanly on the dev container, the prod image, and
CI runners alike.

Palette: near-black background, off-white ink, warm-amber Shield
block (highlighted as the central trust boundary), green LLM
provider boxes, indigo storage boxes. 8 routers feed in; 3 LLM
providers fan out on the right; MongoDB / APScheduler / Audit log
sit at the bottom.

### 2. UI screenshot pack (Playwright)

Headless Chromium opens 6 public-website routes (`/`, `/trust`,
`/solva`, `/akki-chat`, `/work-studio`, `/methodology`), waits for
`networkidle` + 800 ms paint settle, and snapshots at 1440×900. No
auth needed — these are pre-login pages.

The script auto-discovers the installed Chromium headless-shell
binary under `/pw-browsers/` rather than assuming the exact pinned
version, so a slightly-stale dev container still works without
re-running `playwright install`.

## CLI surface

```
make evidence-pngs            # full regen (diagram + UI pack)
make evidence-pngs-diagram    # diagram only (~1s)
make evidence-pngs-ui         # UI screenshots only (~25s)
make evidence-pngs-check      # CI guard — returns rc=1 if any expected PNG is missing
```

Environment override:
```
EVIDENCE_BASE_URL=https://staging.akki.ai make evidence-pngs-ui
```

Default base URL is `http://localhost:3000` (dev container) and the
script accepts `--base-url` or the `EVIDENCE_BASE_URL` env variable
to point at any other deployment.

## Files touched

| File | Action |
|------|--------|
| `scripts/generate_evidence_pngs.py` | NEW (PIL diagram renderer + Playwright UI capture) |
| `Makefile` | NEW (top-level Makefile with `evidence-pngs*` targets) |
| `memory/bank_qa_evidence/png/architecture.png` | NEW (51 KB) |
| `memory/bank_qa_evidence/png/ui_home.png` | NEW (479 KB) |
| `memory/bank_qa_evidence/png/ui_trust.png` | NEW (63 KB) |
| `memory/bank_qa_evidence/png/ui_solva.png` | NEW (59 KB) |
| `memory/bank_qa_evidence/png/ui_akki_chat.png` | NEW (59 KB) |
| `memory/bank_qa_evidence/png/ui_work_studio.png` | NEW (61 KB) |
| `memory/bank_qa_evidence/png/ui_methodology.png` | NEW (84 KB) |

## Next phase

Phase E — `/help` route. Render `AKKI_FEATURES_AND_FUNCTIONALITY.md`
in the FE, served by `GET /api/help/features` in BE.
