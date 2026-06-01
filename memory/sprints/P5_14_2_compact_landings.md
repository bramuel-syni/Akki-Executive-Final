# Phase P5.14.2 — Compact landings hotfix (2026-02)

## What shipped

Two user-reported regressions closed in a single hotfix dispatch
ahead of resuming Phase P5.15. **No P5.15 files touched** — the
hotfix and the in-flight Ideas-by-Akki work stay separable so
this can ship cleanly on its own.

### Bug 1 — Portfolio divider misplaced (P5.14.1 deferred item, NOW RESOLVED)

The `portfolio-landing` wrapper in `ContextPortfolio.jsx` had
`className="akki-w-medium px-8 pt-10 pb-12 flex gap-10"` — no
`position: relative`. The absolute-positioned `portfolio-vertical-divider`
below it carries `style={{ right: 'calc(340px + 40px + 32px)' }}`,
i.e. it was meant to anchor 412 px from the wrapper's outer right
edge. Without a positioned ancestor, that 412 px instead resolved
against the **viewport**.

Live DOM measurement at 1280×800 (`/tmp/p5_14_2_before/probe_results.json`):

| Viewport     | wrap.right | listing.right | divider.left | rail.left | Effect                              |
|--------------|-----------:|--------------:|-------------:|----------:|-------------------------------------|
| 1280×800 ❌  | 1240       | 828           | **868**      | 884       | divider hugs rail (16 px gap)       |
| 1024×768 ❌  | 1024       | 612           | 611          | 668       | divider sits at listing's right edge|

**Fix:** add `relative` to the wrapper. Single-token diff:

```diff
- className="akki-w-medium px-8 pt-10 pb-12 flex gap-10"
+ className="akki-w-medium px-8 pt-10 pb-12 flex gap-10 relative"
```

Post-fix at 1280×800: `divider.left=827`, `listing.right=828`,
`rail.left=884` — divider sits one pixel inside the listing's
right edge, well within the `lg:pr-10` + `gap-10` alley between
content and rail.

### Bug 2 — Solva landing top-heavy

At 1280×800 the picker grid's second row sat below the fold:

| Element          | BEFORE y-range | AFTER y-range |
|------------------|---------------:|--------------:|
| Trust banner     | 184→233        | 184→217       |
| H1 "Solva"       | 377→422        | 269→309       |
| Subtitle         | 422→450        | 309→335       |
| Cards row 1      | 526→693        | 373→539       |
| Cards row 2      | **717→862** ❌ | 563→708 ✅    |

Three trims applied:

1. `SolvaApp.jsx` trust banner — `mb-6 mt-4 ... px-4 py-2 text-sm`
   → `mb-3 mt-2 ... px-3 py-1.5 text-xs`. Banner footprint dropped
   from ≈ 90 px to ≈ 50 px vertical real estate.
2. `SolvaLanding.jsx` outer padding — `120px 24px 80px`
   → `40px 24px 60px` (compact-like-Home target: Home uses `pt-10` = 40 px).
3. `SolvaLanding.jsx` subtitle gap — `0 0 64px 0` → `0 0 28px 0`;
   h1 bottom margin `0 0 12px 0` → `0 0 8px 0`; h1 fontSize 44 → 40.

Above-fold proof at 1280×800: `document.elementFromPoint(centerX, 750)`
now returns the `<button data-testid="solva-not-sure-link">` —
i.e. there is usable surface BEYOND the picker cards above the
fold. Pre-fix the same probe sat inside the `solva-picker-grid`
midway through card row 2.

## Discipline gates

- **v1 byte-identical guard:** 4/4 green (`pytest tests/test_solva_v1_unchanged.py`).
- **Voice-lint:** clean across customer-copy surfaces.
- **P5.14.2 lockdown:** 6/6 green (`pytest tests/test_phase_p5_14_2_compact_landings.py`).
- **Combined sweep:** 10/10 (P5.14.2 + v1 byte-identical).

## Raw Playwright traces

- BEFORE: `/tmp/p5_14_2_before_trace.py` → `/tmp/p5_14_2_before/`
  - `probe_results.json` — DOM bounding-rects per viewport.
  - `portfolio_<viewport>.jpg` and `solva_<viewport>.jpg` at 1280×800 / 1024×768 / 820×1180 / 414×896.
- AFTER: `/tmp/p5_14_2_after_trace.py` → `/tmp/p5_14_2_after/`
  - Same shape; `portfolio.wrap_position` flips `static` → `relative`
    on every viewport; `solva.allCardsAboveFold` flips `False` → `True`
    at 1280×800 and 1024×768.

## What this fix DOES NOT touch

- Any P5.15 file (Ideas by Akki backend services, router, frontend
  components). Hotfix is committable as its own change.
- Solva v1 reasoning, voice, or schema code.
- The h1 mobile breakpoint (still `font-size: 32px` for ≤640 via
  the existing `<style>` block).
- Recent Sessions / disambiguator / briefing deck behaviour.
- The 414×896 mobile fold — 4 single-column 188-px cards naturally
  exceed an 896 viewport when the topbar (64) + banner (50) + h1
  (40) + subtitle (28) consume the top 182 px. Mobile scrolling
  remains; user directive was 1280×800 above-fold which is now met.

## Linked items

- **P5.14.1 deferred item:** "`position: relative` polish on
  `portfolio-landing` wrapper" — **NOW RESOLVED**; the divider
  bug user re-reported is the exact pathology that polish item
  named.

## Next

Resume Phase P5.15 — Pulse · Ideas by Akki (6-step finish plan
ratified pre-pivot). Scheduler module, scheduler pytest, raw
Playwright trace, voice-lint, byte-identical guard, phase memo.
