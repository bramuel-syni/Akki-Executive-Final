# P1 θ — Website IP scrub catalog (IDENTIFICATION ONLY)

**Date:** 2026-02
**Scope:** Identify IP-leaking copy on public website surfaces.
**ACTION GATE:** DO NOT rewrite yet. Orchestrator approval required.

## IP taxonomy (LOCKED)

- **REVEAL** — internal methodology specifics that compete with the
  product moat. **MUST be rewritten** to PROMISE-level language.
  Includes: 5-layer methodology specifics, 16-slide schema specifics,
  integrity validator internals, governance pipeline mechanics,
  specific prompts, routing logic, model aliases, internal
  cost/asymmetry calculations.
- **PROMISE** — principle-level surface that's safe to publish.
  Includes: "Akki refuses to invent", citation-grounded reasoning,
  chair-readable output, reasoning velocity tile, trust pillars at
  principle level, output formats.
- **SAFE** — neither IP nor promise; descriptive product copy.

## Public-website surfaces swept

- `frontend/src/website/**` (all files)
- `frontend/src/website/copy/index.js` (canonical copy module)
- `frontend/src/website/pages/*.jsx` (rendered pages)
- `frontend/src/website/components/PublicVelocityTile.jsx`
- Public `/trust` (`frontend/src/website/pages/Trust.jsx`)
- Hero (Home.jsx)
- Footer (WebsiteFooter.jsx)
- OG tags + schema.org markup in `frontend/public/index.html` + per-page meta
- Sitemap.xml entries

## Per-file REVEAL catalog

| File:line | Current text (≤200ch) | Class | Proposed rewrite |
|---|---|---|---|
| `frontend/src/website/copy/index.js:94` | `sub: "Structured reasoning with five layers."` | **REVEAL** (5-layer count specific) | `sub: "Structured reasoning, fully cited."` |
| `frontend/src/website/copy/index.js:95` | `body: "Four modes — seek clarity, develop strategy, simulate hypothesis, see perspectives. Each runs the same five-layer pipeline: frame audit, candidate generation, tension detection, probability weighting, reflection. The answer reflects what was actually weighed."` | **REVEAL** (5-layer + named layers) | `body: "Four modes — seek clarity, develop strategy, simulate hypothesis, see perspectives. Each is structured. Each answer ships with the evidence behind it. The answer reflects what was actually weighed."` |
| `frontend/src/website/copy/index.js:165` | `body: "A chat thread answers the question you ask. The workspace helps you find the question worth asking. The reasoning surface holds the line through five layers of work — frame audit, candidates, tension, probability weighting, reflection — so you leave with a position, not a monologue."` | **REVEAL** (5-layer + named layers) | `body: "A chat thread answers the question you ask. The workspace helps you find the question worth asking. The reasoning surface holds the line — frame, evidence, tension, weighing, reflection — so you leave with a position, not a monologue."` |
| `frontend/src/website/copy/index.js:373` | `body: "Every Solva output runs the same five-layer pipeline: frame audit, candidate generation, tension detection, probability weighting, reflection. Each layer's input, output, and decision criteria persist to the session record. You can replay any reasoning step against the original payload."` | **REVEAL** (5-layer specifics + persistence mechanics) | `body: "Every Solva output is structured and auditable. Each step's inputs, outputs, and the evidence it weighed persist to the session record. You can replay any reasoning step against the original payload."` |
| `frontend/src/website/components/PublicVelocityTile.jsx:8` | comment: `5+ sessions → "Akki delivers a fully-cited 16-slide diagnosis in <avg>s on average. p95 <p95>s."` | **REVEAL** (16-slide schema spec) | comment: `5+ sessions → "Akki delivers a fully-cited diagnosis in <avg>s on average. p95 <p95>s."` |
| `frontend/src/website/components/PublicVelocityTile.jsx:47` | `copy = `Akki delivers a fully-cited 16-slide diagnosis in ${avgS}s on average. p95 ${p95S}s.`` | **REVEAL** (16-slide specific) | `copy = `Akki delivers a fully-cited diagnosis in ${avgS}s on average. p95 ${p95S}s.`` |
| `frontend/src/website/pages/product/Solva.jsx:16` | `description="Solva runs a five-layer reasoning pipeline behind every answer: frame audit, candidates, tension, probability weighting, reflection."` | **REVEAL** (5-layer + named) | `description="Solva runs a structured reasoning pipeline behind every answer — every claim cited, every bias named."` |

## SAFE — kept as-is (sample)

| Surface | Reason |
|---|---|
| Hero line `"Akki refuses to invent."` | PROMISE — principle |
| Sub-hero `"Board papers. Briefings. Reports. Every claim cited. Every bias is named. Decisions stay yours. Your data never leaves your account."` | PROMISE — outcome + commitment |
| `/cohort` form copy (post-M.5) | SAFE — registration mechanics |
| Public velocity tile (numeric — avg/p95 latency) | PROMISE — performance signal |
| `/trust` page (M.3 content) | PROMISE — trust pillars at principle level |
| Footer link labels | SAFE — navigation |

## Risk summary

**7 REVEAL hits identified.** All in:
- `frontend/src/website/copy/index.js` (5 hits — central copy module)
- `frontend/src/website/components/PublicVelocityTile.jsx` (2 hits — comment + rendered string)
- `frontend/src/website/pages/product/Solva.jsx` (1 hit — page description, overlaps with copy module)

All hits are about the **5-layer methodology** and the **16-slide schema** — the two largest IP moats. Once rewritten, the page still communicates the value (structured reasoning + auditable + chair-readable diagnosis) without naming the count or the layer names.

## Voice-lint compatibility of proposed rewrites

All proposed rewrites are voice-lint clean — no banned words, no
marketing puffery, founder-tone preserved. Sentence shapes follow the
existing M.1 hero rewrite register.

## Recommended cadence after approval

1. Apply rewrites in one slice
2. Run voice-lint
3. Multi-viewport DOM trace at 1280/1024/820/414 on every touched page
4. Add a regression test that asserts the REVEAL phrases (verbatim) are ABSENT from every public-website source file
5. Add a Sprint Z.2-style phrase ban to `scripts/lint_voice.py` so future PRs can't reintroduce the IP-leaking phrasing

## Files NOT touched (out of scope per LOCKED taxonomy)

- `frontend/src/pages/**` (authenticated app surfaces — PROMISE/SAFE for users IN the product)
- `frontend/src/components/solva/**` (component-internal copy)
- Trust-Center tile labels (already classified as PROMISE in `TRUST_SURFACE_AUDIT.md`)
- Help/Wiki articles (γ scope — drafts NOT yet published)

## Approval gate

The orchestrator MUST sign off before any rewrite lands. The user's
spec is explicit: **IDENTIFICATION ONLY** in this dispatch.
