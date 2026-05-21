# Phase E — `/help` route (FE markdown render + `/api/help/features`) — DONE (2026-02)

Anchor for the Phase E execution. Exposes the canonical
`AKKI_FEATURES_AND_FUNCTIONALITY.md` document inside the app at
`/help` and over the API at `/api/help/features`.

## Final state

| Acceptance criterion | Status |
|---|---|
| Backend route `GET /api/help/features` | ✅ JSON envelope (`title`, `last_modified`, `word_count`, `char_count`, `markdown`) |
| Backend route `GET /api/help/features.md` (download/share) | ✅ raw `text/markdown` Content-Type, inline disposition |
| Frontend `/help` route | ✅ wired in `App.js` (lazy-loaded, public) |
| Markdown rendered with proper typography | ✅ react-markdown + remark-gfm + rehype-highlight, custom `components` map |
| No raw `fetch()` in the new page | ✅ uses `@/lib/api` axios client (LINT_API_CLIENT_RULE.md compliant) |
| Data-testids on key elements | ✅ `help-features-page`, `help-features-title`, `help-features-content`, `help-features-error`, `help-features-loading`, `help-features-last-modified`, `help-features-brand-home`, `help-features-download-md` |
| Backend tests | ✅ 4/4 green (`tests/test_phase_e_help_features.py`) |
| Full backend suite | ✅ **876 passed, 500 skipped, 0 failed** (was 872 in Phase C; +4 new Phase E tests) |
| Live preview render | ✅ verified at `https://akki-executive.preview.emergentagent.com/help` — 10 H2 + 25 H3 rendered, no errors |

## Files touched

| File | Action |
|------|--------|
| `backend/routers/help.py` | NEW (Phase E router) |
| `backend/server.py` | NEW import + `app.include_router(help_router.router)` |
| `backend/tests/test_phase_e_help_features.py` | NEW (4 tests) |
| `frontend/src/pages/HelpFeatures.jsx` | NEW (page component) |
| `frontend/src/App.js` | NEW lazy import + `<Route path="/help" .../>` |

## Frontend design notes

The page styling intentionally matches the existing website-shell
look (cream `#f5f0e6` background, serif `font-medium` headings,
`max-w-3xl` reading column). It sits alongside `/trust` and
`/methodology` in the public-website nav (the header link reads "Help"
with `aria-current="page"`).

`react-markdown` is used with a custom `components` map rather than
Tailwind's `@tailwindcss/typography` plugin — typography is not in the
project's dependency tree and adding it for one page would be heavy.
The custom map handles H2/H3/H4, lists, blockquotes, tables, inline
code, fenced code blocks, links (external link → new tab + rel
noopener), and horizontal rules.

The first H1 in the markdown body is intentionally hidden because the
page already shows the title above the rule, large.

## Backend route shape

```jsonc
GET /api/help/features → 200 OK
{
  "title":         "AKKI — Features & Functionality",
  "last_modified": "2026-05-21T19:22:23.829152+00:00",
  "char_count":    25678,
  "word_count":    3611,
  "markdown":      "# AKKI — Features & Functionality\n\n…"
}

GET /api/help/features.md → 200 OK
Content-Type: text/markdown; charset=utf-8
Content-Disposition: inline; filename="AKKI_FEATURES_AND_FUNCTIONALITY.md"
<full markdown body, 25678 bytes>
```

Both endpoints are no-auth (mirrors `/api/product-features` /
`/api/product-features.md` — product overview content, not gated).

## Test coverage

`tests/test_phase_e_help_features.py` — 4 in-process httpx tests:
1. JSON envelope completeness + sanity ranges (`>1 KB`, `>100 words`).
2. Title is the markdown body's first H1.
3. `.md` endpoint serves correct content-type + raw body.
4. Endpoint is open (no Authorization header required → 200).

## Autonomous sprint — phases A→E status

Phase A (ClamAV gap-fill)  — DONE
Phase B (Postmark inbound) — DONE
Phase C (spaCy trf + 5 quarantine refactors + dep-override leak) — DONE
Phase D (PNG evidence pack + `make evidence-pngs`) — DONE
Phase E (/help route + /api/help/features) — DONE ← THIS DOC
Phase F (chat boundary removal) — DONE

The autonomous-sprint loop is complete. Subsequent work picks up
from the backlog in `BACKLOG.md` (Phase G items only — already filed
G-001 through G-005, AWAITING_PO).
