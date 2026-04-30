# Homepage Repositioning — Read-Only Audit

> Audit-only inventory of the current marketing site against the new homepage
> brief. **No code changes were made.** Cite-everything: every claim below
> is anchored to `file:line`. Where a current section has no clean home in
> the new structure it is flagged explicitly.

Files inspected (read-only):
- `/app/frontend/src/pages/Landing.jsx` (341 lines)
- `/app/frontend/src/pages/SolveLanding.jsx` (240 lines)
- `/app/frontend/src/pages/marketing/Features.jsx` (101 lines)
- `/app/frontend/src/pages/marketing/Security.jsx` (97 lines)
- `/app/frontend/src/pages/marketing/About.jsx` (46 lines)
- `/app/frontend/src/components/marketing/HeroSection.jsx` (111 lines)
- `/app/frontend/src/components/marketing/ThreePillars.jsx` (161 lines)
- `/app/frontend/src/components/marketing/EnterpriseFeature.jsx` (249 lines)
- `/app/frontend/src/components/marketing/MarketingShell.jsx` (104 lines)

Routing reference: `/app/frontend/src/App.js:69-90` (public routes).

---

## 1. Current `Landing.jsx` inventory (in render order)

| # | Section label | Lines | Components imported / source | Copy gist | Tokens / typography | Disposition |
|---|---|---|---|---|---|---|
| **0** | **Masthead / top nav** | `Landing.jsx:120-166` | `Logo` (`brand/Logo`), `Button` (`ui/button`), `useAuth`, `lucide-react: Sparkles, ArrowRight` | Logo · About · Features · Security Design · Exco360 · Akki Solve (anchor #solve-pillar) · Sign in · **Request access** | `bg-[var(--cream)]`, `border-[var(--rule)]`, mono-feel link `text-[13px]`, accent button `bg-[var(--accent)]` | **REPLACE with new copy** — nav labels and CTA must change to: Logo · Product · Methodology · Exco360 · Sign in · **Try the Sandbox** |
| **1** | **HeroSection** | `Landing.jsx:169` (one-liner — body in `components/marketing/HeroSection.jsx:24-110`) | `HeroSection` (`components/marketing/HeroSection`); inside: `Button`, `Quote`, `ArrowRight`, hero image from Unsplash | Overline "For seasoned and emerging executives and non-executive directors" + **metaphor headline "AKKI reads the pack so you can read the room."** + sub-head about preserving shareholder value + primary CTA "Try AKKI in 60 seconds" → /sandbox + sign-in/sign-up footer + right-rail NED quote + sepia boardroom photo | `akki-serif` 76px, `akki-overline`, `text-[var(--accent)]` italic span, NAVY `#0A1F44` on attribution chip, sepia/desaturated hero photo (filter: sepia(0.22)) | **REPLACE with new copy** — keep the component shell, swap to literal pain headline + add **"How AKKI thinks"** secondary CTA + add **trust strip** below CTAs. Remove the metaphor phrase "reads the pack / read the room" from the headline. |
| **2** | **First-run demo** ("What a first run looks like") | `Landing.jsx:172-189` (markup); `FirstRunDemo` component defined inline at `Landing.jsx:38-111` | Inline `FirstRunDemo` — pure CSS keyframes (no external lib); uses `Upload`, `Loader2`, `AlertTriangle`, `TrendingUp` icons; `FAKE_SIGNALS` const at lines 38-42 (3 hard-coded signals: Risk/Gap/Opportunity) | Left: serif heading "Drop in the pack. Read the signals." + 90-second story; right: animated 12s loop showing upload → progress bar → "AKKI is reading…" → 3 signal cards appearing | `bg-white` card, `border-[var(--rule)]`, tone-coloured signal cards (red/amber/emerald), `akki-serif` 36px heading | **KEEP, but RECAST as Section 2 of the new homepage** (the "60-second proof" walkthrough). The animated loop is already a 3-state visualisation — perfect for the new "intake → workspace → signal card with citation" — but states need to be re-mapped. See §7. |
| **3** | **ThreePillars** (`#solve-pillar` anchor wrapper) | `Landing.jsx:192-194` (wrapper); body in `components/marketing/ThreePillars.jsx:16-160` | `ThreePillars`; inside: `Button`, `Sparkles`, `ArrowRight`, `Layers`, `GitBranch` + 2 Unsplash images (library books + library hall) | Three product pillars in bento grid: **Solve** (dominant 8-col dark `bg-[var(--ink)]` card with library image, 4-stage list, "Start a Solve session" / "How it works" CTAs) + **Cross Board Pulse** (4-col cream-deep card) + **Decks + Reports** (12-col slim teaser bar linking to #enterprise) | `bg-[var(--ink)]` (oxblood-on-cream contrast), `bg-[var(--cream-deep)]`, `akki-serif` 34px, sepia images | **RELOCATE to /features** — the new homepage has no "three pillars" section. The Solve stages list and Pulse / Decks blurbs become Features-page blocks. The "Solve as star pillar" framing **conflicts** with the new "one sharpest use case" homepage section (Friday→Tuesday brief), which is a different angle entirely. |
| **4** | **EnterpriseFeature** (`#enterprise` anchor wrapper) | `Landing.jsx:197-199` (wrapper); body in `components/marketing/EnterpriseFeature.jsx:36-249` | `EnterpriseFeature`; inside: `Button`, `Loader2`, `Sparkles`, `ArrowRight`, `ShieldCheck`, `Eye`; live API call to `/api/public/studio/sensitivity-demo` | Full-bleed navy band promoting Decks + Reports Studio enterprise feature: 3 bullets (auto-sensitivity / read-tracking / exposure score) + **interactive textarea live demo** that classifies pasted text via a real backend endpoint with debounce, error states, sample-text fill, and tone-coloured result block | NAVY `#0A1F44` bg, CREAM `#F7F3EA` text, OXBLOOD `#8B2E2B` accent overlines, classification chips emerald/amber/orange/red | **RELOCATE to /features** (or keep the live demo but **REMOVE the surrounding band copy** from homepage). The new homepage's §4 "Trust" is editorial copy only — not a full-width product feature. The live demo could be migrated as-is to a Features page subsection. |
| **5** | **Editorial pull-quote** (Exco360 voice) | `Landing.jsx:202-232` | Inline JSX; uses `Quote` icon; `Link` to `/blog`; one navy chip + one cream-deep panel | Centered single Exco360 quote: "Adopting tools that preserve value isn't operational — it is a fiduciary duty." + navy chip "Exco360" + "Read the Exco360 Blog →" link | `bg-[var(--cream-deep)]/40` panel, `akki-serif italic` 34px, NAVY chip, `text-[var(--accent)]` link, `Quote` icon 8px | **REPLACE with new copy** — repurpose into new §5 "Voice" but expand from **1 quote** to **3 Exco360 pull-quotes** + single "Read Exco360 →" link. Same visual language can be reused. |
| **6** | **Trust strip** (3 guarantees) | `Landing.jsx:235-249` | Inline 3-up grid; `Check` icon; hard-coded array of 3 [headline, body] tuples | "Every claim cites a document." / "Every context stays sealed." / "Every signal is verified." with 1-line bodies each | `divide-x divide-[var(--rule)]`, `Check` 4px in `text-[var(--accent)]`, `akki-serif` 19px, `text-[var(--muted)]` body | **KEEP** — almost a 1:1 fit for new §4 Trust ("evidence-first / audit trail / sensitivity-aware"). The current trio is close but not identical — copy needs **REPLACE** to the new exact wording while the **layout is reusable**. |
| **7** | **Audience cards** (NED + Exec) | `Landing.jsx:252-291` | Inline 2-up grid; hard-coded array of 2 audience objects | Two cards: "Sitting on five boards at once." (For NEDs) and "Running the quarter." (For Executives) with 3-line bodies each | `bg-white` cards, `border-[var(--rule)]`, `akki-overline` chip in `text-[var(--accent)]`, `akki-serif` 26px headline | **RELOCATE to /about** — there is no "Who it's for" section in the new homepage. This audience-segmentation is closer to an About-page persona block. Could also fold into Features-page intro. |
| **8** | **Final inline CTA** | `Landing.jsx:294-323` | Inline; `Button`; "Try AKKI in 60 seconds" + "Request a team workspace" | Centered headline "Open a context. Upload a pack. See what AKKI sees." + sub-line + 2 CTAs | `akki-serif` 40px, accent button + outline secondary | **KEEP shell, REPLACE copy** — this matches new §7 "Closing CTA" but the new brief specifies a **single centered button** matching the hero CTA, not a two-button grouping. |
| **9** | **Colophon footer** | `Landing.jsx:326-337` | Inline minimal footer; `Sparkles` icon | "© 2026 Syni.ai · AKKI · v1.0" + "Confidential · by invitation" tagline | `bg-[var(--cream)]`, mono `text-[11px] uppercase tracking-[0.2em]`, `text-[var(--muted)]` and `text-[var(--accent)]` | **REPLACE entirely** — new footer brief: Plans · Security · Enterprise · About · Contact · RSS · Status · Terms · Privacy. Current footer has only 2 short lines and **none of those links**. (See §5.) |

---

## 2. Mapping table — current → new

| Current section | Lines | New homepage section | Notes |
|---|---|---|---|
| Masthead nav | `Landing.jsx:120-166` | **Nav** (replaces) | Re-label: About→Methodology, Features→Product, drop "Akki Solve" anchor, change "Request access" → "Try the Sandbox" |
| HeroSection | `HeroSection.jsx:24-110` | **§1 Hero** (replaces copy) | Drop "reads the pack / read the room" metaphor; add literal pain headline; add secondary CTA "How AKKI thinks"; add trust strip below CTAs |
| First-run demo | `Landing.jsx:38-189` | **§2 60-second proof** (recast) | Currently 1 visual (animated signal-generation loop). New brief asks for **3-state walkthrough** (intake → workspace → signal card with citation). Single-state demo must be split into 3. |
| ThreePillars | `ThreePillars.jsx:16-160` | **→ /features** (relocate) | Solve content moves to Features (already has its own /solve page in `SolveLanding.jsx` — see §6 risk). Pulse + Decks blurbs also move. |
| EnterpriseFeature | `EnterpriseFeature.jsx:36-249` | **→ /features** (relocate, esp. live demo) | The live `/api/public/studio/sensitivity-demo` interactive widget is a real backend integration; preserve as a /features sub-section. |
| Editorial pull-quote (1) | `Landing.jsx:202-232` | **§5 Voice** (replaces, expanded) | Expand from 1 → 3 Exco360 pull-quotes per new brief. |
| Trust strip (3 items) | `Landing.jsx:235-249` | **§4 Trust** (keep layout, replace copy) | 3-up grid is already correct; new brief specifies "evidence-first / audit trail / sensitivity-aware". Current trio is close but wording differs. |
| Audience cards (NED+Exec) | `Landing.jsx:252-291` | **→ /about** (relocate) | No "Who it's for" section in new homepage. Could also fold into Features intro. |
| Final inline CTA | `Landing.jsx:294-323` | **§7 Closing CTA** (keep shell, single button) | New brief: single centered button with same copy as hero. Current has 2 buttons — drop the secondary. |
| Colophon | `Landing.jsx:326-337` | **Footer** (replace) | Current footer has zero of the 9 links the new footer needs. |
| _(no source today)_ | — | **§3 One sharpest use case** (Friday→Tuesday, before/after) | **NO CURRENT SECTION MAPS HERE.** Net-new component needed. |
| _(no source today)_ | — | **§6 Price signal** ("See plans →") | **NO CURRENT SECTION MAPS HERE.** Net-new — and there is no `/plans` route today (see §6 risk). |

**Sections with no home in the new structure (will be removed from homepage):**
- ThreePillars — relocate, no homepage home
- EnterpriseFeature band — relocate, no homepage home
- Audience cards (NED+Exec) — relocate to /about
- "Akki Solve" nav anchor pill in masthead — drop (no homepage three-pillars target)

**Sections in new homepage with no current source:**
- §3 "One sharpest use case" Friday→Tuesday before/after
- §6 "Price signal" line + "See plans →" link

---

## 3. Reusable component inventory — `components/marketing/*`

| Component file | Lines | What it does | Reusability for new homepage |
|---|---|---|---|
| `HeroSection.jsx` | 111 | Two-column hero: overline + headline + sub-head + primary CTA + sign-in/sign-up footer + right-rail quote + sepia image | **Reuse with copy changes.** Layout (8-col body / 4-col aside with photo) suits new §1 Hero. Copy must change (metaphor headline → literal pain headline). Need to add secondary CTA "How AKKI thinks" beside primary, and add a **trust strip** under the CTAs (currently absent). Hard-coded `HERO_QUOTE` const at `:18-22` — easy to swap or remove. |
| `ThreePillars.jsx` | 161 | Bento 3-card grid (Solve dominant + Pulse + Decks teaser); 4-stage Solve list at `:55-72`; 2 Unsplash images | **Not used on new homepage.** Move whole component to `/features` (already has CTAs pointing there). Solve content also overlaps with the dedicated `/solve` page (`SolveLanding.jsx`) — see §6. |
| `EnterpriseFeature.jsx` | 249 | Full-bleed navy band; left: 3-bullet pitch; right: **live interactive textarea** debounced against `POST /api/public/studio/sensitivity-demo` with classification + reasons rendering | **Not used on new homepage.** **High-value asset to preserve elsewhere.** The live demo is a real backend integration (`API_BASE` on `:34`) — must move intact to /features as a "Sensitivity scoring · try it live" subsection. The full-bleed navy band aesthetic is **inconsistent** with the cream-only new homepage. |
| `MarketingShell.jsx` | 104 | Wraps About / Features / Security / Blog with `MarketingHeader` (sticky cream/90 bg) + `MarketingFooter` (4-col grid: Logo+tagline / Product / Company / Posture) | **Reuse with copy changes.** Header NAV array at `:6-11` matches the *current* nav. Need to update labels (About→Methodology, Features→Product, drop "Security Design"→merge under Product). Footer 4-col grid does **not** match new flat 9-link footer brief — needs **rewrite** (or use the new flat footer on Landing only and keep this shell on inner pages). The "Try the sandbox" link at `:33-35` already exists — reuse for new nav CTA. |

**Net-new components needed for the new homepage:**

1. **`SixtySecondProof.jsx`** (new) — 3-state visual walkthrough for §2. The existing inline `FirstRunDemo` at `Landing.jsx:44-111` is a single-stage CSS-keyframes animation; the new brief wants three discrete frames (intake → workspace → signal card with citation). Either expand `FirstRunDemo` (3× the keyframes) or build new.
2. **`SharpestUseCase.jsx`** (new) — Friday-board-pack-lands → Tuesday-2-page-brief before/after for §3. **No analogue exists** in the current codebase.
3. **`PriceSignal.jsx`** (new) — single muted line + "See plans →" link for §6. **No analogue exists.** Also missing the `/plans` route (see §6 risk).
4. **Voice trio block** — expand current single-quote pull-quote at `Landing.jsx:202-232` into 3 quotes. Could be inline JSX in Landing or a small `Exco360PullQuotes.jsx` component.
5. **New flat footer** for Landing (9 links) — current `MarketingFooter` is a 4-col grid mismatch.

---

## 4. Copy clichés found

Grep run case-insensitively across all five marketing files + every `components/marketing/*.jsx`. Banned terms in the brief:

| Term | Occurrences |
|---|---|
| `supercharge` | **0** |
| `unlock` | **0** |
| `10x` | **0** |
| `game-chang` | **0** |
| `revolutio` | **0** |
| `AI-powered` / `AI powered` | **0** |
| `intelligent` / `intelligen…` | **1 — needs review.** `MarketingShell.jsx:54` — footer tagline: `"Intelligence for non-executive directors and operating executives."` (uses the noun "Intelligence", not the adjective "intelligent" — borderline; flag for tone review under the new brief. The same phrase is the product positioning.) |
| `\bsmart\b` | **0** |
| `in today's` | **0** |
| `in an era` | **0** |
| `more than ever` | **0** |
| `!` (exclamation marks in copy strings) | **0** — none found. The marketing copy across all 9 files contains zero exclamation marks. |

**Other risk flag — `"AI hallucination"`** at `Security.jsx:22`:
> "That alone disqualifies the \"AI hallucination\" defence in a board meeting."
The phrase is in scare-quotes and used to dismiss the trope, but it's still present. Worth a tone review.

### Metaphor headlines (flagged per brief)

| File:line | Headline | Verdict |
|---|---|---|
| `HeroSection.jsx:36-39` | **"AKKI reads the pack so you can read the room."** | **Metaphor** — explicitly named in the brief as the kind to flag. Sub-head also continues the metaphor: "frameworks, mindsets, and tooling that pay off in the room" (`:43-47`). The new brief replaces this with a literal pain headline. |
| `Landing.jsx:171` | comment: `"AKKI reads the pack"` | Code comment, not user-visible. |
| `Landing.jsx:177-178` | "Drop in the pack. Read the signals." | Mild metaphor ("Drop in") but acceptably literal — flag for tone review. |
| `About.jsx:15` | "AKKI is the colleague who reads with them." | Metaphor (reads as personification). About copy — lower-priority cleanup. |
| `About.jsx:20` | "the most useful person in the room was the one who'd read the pack twice" | Flavour text, not headline. |
| `Landing.jsx:296-297` | "Open a context. Upload a pack. See what AKKI sees." | Mild metaphor ("See what AKKI sees") — flag. |
| `SolveLanding.jsx:122` | "For the board problems that don't have tidy answers." | Acceptable — concrete idiom, not extended metaphor. |
| `SolveLanding.jsx:208-210` | "Bring Solve a problem you've been carrying." | Metaphor ("carrying a problem"). |

**Net**: marketing copy is already cliché-light (zero hits on the banned-term list, zero exclamation marks). The single largest tone risk is **the homepage hero metaphor itself** — which the new brief explicitly replaces.

---

## 5. Nav + footer current state

### Current top nav

There are **two distinct top nav implementations** in the codebase:

#### (a) Landing-page-only inline nav — `Landing.jsx:120-166`
| Label | Destination | Visibility | Notes |
|---|---|---|---|
| `Logo` | `/` (implicit) | always | `Logo` component from `components/brand/Logo.jsx` |
| `About` | `/about` | `hidden md:inline` | text-muted hover-ink |
| `Features` | `/features` | `hidden md:inline` | |
| `Security Design` | `/security` | `hidden md:inline` | |
| `Exco360` | `/blog` | `hidden md:inline` | |
| `Akki Solve` | `#solve-pillar` (anchor) | `hidden md:inline-flex` | accent-border pill with Sparkles icon |
| `Sign in` | `/signin` | always (logged-out) | text link |
| **`Request access`** | `/signup` | always (logged-out) | accent button (primary CTA) |
| `Go to workspace` | `/app` | always (logged-in) | accent button — replaces Sign in / Request access |

#### (b) MarketingShell shared nav — `components/marketing/MarketingShell.jsx:13-45`
Used by `About.jsx`, `Features.jsx`, `Security.jsx`, `Blog.jsx`, `BlogPost.jsx`, `BlogAdmin.jsx`. **Different from (a).**

| Label | Destination | Notes |
|---|---|---|
| `Logo` | `/` | |
| `About` | `/about` | from `NAV` array `:6-11` |
| `Features` | `/features` | |
| `Security Design` | `/security` | |
| `Exco360` | `/blog` | |
| `Try the sandbox` | `/sandbox` | text link, `hidden sm:inline` |
| `Sign in` | `/signin` | grey-button |

`SolveLanding.jsx:87-112` has yet a **third** distinct nav (just Logo + Home + "Try Akki Solve" CTA).

#### Disposition for new nav (`Logo · Product · Methodology · Exco360 · Sign in · [Try the Sandbox]`)

| New nav item | Current source | Gap |
|---|---|---|
| `Logo` | both navs already have it | ✅ no change |
| `Product` | currently `Features` → `/features` | **Re-label only** — destination unchanged, but the page itself is currently named "Features" (`Features.jsx:67-68`: `<h1>What AKKI does for the executive.</h1>`). Page title may need re-labelling too. |
| `Methodology` | currently `About` → `/about` (per brief: "→ /about or /methodology") | **No `/methodology` route exists** (`App.js:69-90`). Either re-point to `/about` or create new route + page. |
| `Exco360` | both have `Exco360 → /blog` | ✅ no change |
| `Sign in` | both have it | ✅ no change |
| `[Try the Sandbox]` (CTA) | `MarketingShell` has it as a text link (`:33-35`); `Landing.jsx` has `Request access → /signup` as the button instead | **Re-style** — promote sandbox CTA to button-rank in the masthead (replacing "Request access"). Sandbox route exists (`App.js:91`). |
| ~~`Security Design`~~ | currently in both navs | **DROP from nav** per new brief (Security still in footer per brief). |
| ~~`Akki Solve` pill~~ | only in `Landing.jsx:136-142` | **DROP** — `#solve-pillar` anchor target is being removed too. |

### Current footer

#### (a) Landing colophon — `Landing.jsx:326-337`
- "© 2026 Syni.ai" · "AKKI" · "v1.0" (left)
- "Confidential · by invitation" with Sparkles icon (right)

**No links.** No Plans, no Security, no Enterprise, no About, no Contact, no RSS, no Status, no Terms, no Privacy.

#### (b) MarketingShell footer — `MarketingShell.jsx:47-93`
4-column grid + bottom bar:

| Column | Links |
|---|---|
| **Logo + tagline** | (no links) `"Intelligence for non-executive directors and operating executives."` |
| **Product** | `Features → /features`, `Security Design → /security`, `Try the sandbox → /sandbox`, `Sign in → /signin` |
| **Company** | `About AKKI → /about`, `Exco360 — the series → /blog`, `Contact → mailto:hello@akki.ai` |
| **Posture** | (no links — 4 bullet points) |
| Bottom bar | "© AKKI · Syni.ai 2026" + "Build v4.3 · §12 redesign" |

#### Disposition for new footer (`Plans · Security · Enterprise · About · Contact · RSS · Status · Terms · Privacy`)

| New footer item | Current source | Status |
|---|---|---|
| `Plans` | **MISSING** | ⚠️ No `/plans` route in `App.js`. The codebase has `routers/billing.py: GET /api/billing/plans` but no public marketing page. Need new route + page or a /pricing route. |
| `Security` | `/security` exists | ✅ |
| `Enterprise` | `/app/enterprise` is a protected route in `App.js:125`. There is no public `/enterprise` marketing page. | ⚠️ **Mismatch.** Either expose a public Enterprise page or repurpose the protected page. The marketing site has an `EnterpriseFeature` *component* (used in Landing) but no standalone /enterprise page. |
| `About` | `/about` exists | ✅ |
| `Contact` | `mailto:hello@akki.ai` (in MarketingShell) | ✅ — mailto only, no /contact route |
| `RSS` | `GET /api/blog/rss` exists in backend (`routers/blog.py:700`) | ✅ — direct link to `/api/blog/rss` |
| `Status` | **MISSING** | ⚠️ No /status page; no statuspage.io style page; not in admin either. |
| `Terms` | **MISSING** | ⚠️ No /terms route. Not anywhere in `App.js`. |
| `Privacy` | **MISSING** | ⚠️ No /privacy route. Not anywhere in `App.js`. |

**The new footer requires 4 missing destinations** (Plans, Status, Terms, Privacy) and **1 page-vs-protected-route mismatch** (Enterprise).

---

## 6. Risks / open questions for orchestrator

### Routing gaps

1. **`/methodology` route does not exist** (`App.js:69-90`). Brief says "→ /about or /methodology". Decision needed: re-point new nav to existing `/about`, or create new `/methodology` route + page (and what's its content vs `/about`?).
2. **`/plans` does not exist.** Backend has `GET /api/billing/plans` (`routers/billing.py:106`) but no public pricing page. New §6 "Price signal" + footer "Plans" both require this.
3. **`/enterprise` not public.** `App.js:125` has it behind `ProtectedRoute`. New footer wants it as a public link.
4. **`/status` does not exist.** No status page implementation found. Either external (statuspage.io) or net-new internal page.
5. **`/terms` does not exist.** Required by new footer.
6. **`/privacy` does not exist.** Required by new footer.
7. **`/contact` does not exist** as a route — currently only `mailto:hello@akki.ai`. Brief says "Contact" — is that a /contact page or a mailto?

### Copy / dependencies

8. **Three nav implementations.** `Landing.jsx`, `MarketingShell.jsx`, and `SolveLanding.jsx` each ship their own nav. Decision needed: consolidate to one shared component before homepage rewrite, or accept divergence.
9. **`MarketingShell` footer is 4-col, new brief is flat 9-link.** Decision needed: does the new flat footer apply only to `/` (Landing) or also to /about, /features, /security, /blog (which use MarketingShell)? If the latter, MarketingShell's footer must be replaced too.
10. **`SolveLanding.jsx` overlap.** The Solve content on the homepage (`ThreePillars.jsx:32-93`) duplicates a lot of `SolveLanding.jsx:20-57`. If the homepage Solve pillar moves to `/features`, does it also still live at `/solve`? Two surfaces explaining the same thing.
11. **The live sensitivity demo (`EnterpriseFeature.jsx`) calls a real backend endpoint.** When relocated to `/features`, the `API_BASE` constant (`:34`) and `POST /api/public/studio/sensitivity-demo` integration must move with it. Endpoint is **public, IP rate-limited** — no auth required, so portable.
12. **Hero quote is hard-coded** (`HeroSection.jsx:18-22`). New §5 "Voice" needs **3 Exco360 pull-quotes** — source needed (quotes from real `db.blog_posts` rows? or hand-curated?). Backend has `GET /api/blog/posts` but no "featured-quote" field on posts.
13. **"How AKKI thinks" CTA target.** Brief says "→ /about or /methodology". Same routing question as item 1.
14. **New §3 "Friday → Tuesday brief" uses a feature flow** (Catch-up brief from Prepare surface — `routers/prepare.py`, `pages/Prepare.jsx`). Before/after copy needs concrete artefacts — does the audit team have permission to use a real (anonymised) brief for the visual? Or is it fictional like the FirstRunDemo signals (which are hard-coded fakes)?
15. **The hero photo URL** (`HeroSection.jsx:96`) and ThreePillars images (`ThreePillars.jsx:38, 102`) are Unsplash hot-links with `crop=entropy` query strings. Stable but external — flag for licensing review and consider local copies.
16. **`useAuth()` destructures `user`** at `Landing.jsx:115` and `SolveLanding.jsx:83`, but `AuthContext.jsx:191-198` exposes `account`, not `user`. So `user` is **undefined** in current code (silent — both files only check truthiness). Pre-existing bug, not blocking, but flag if you reuse this code path. The new nav must use `account` instead.
17. **Trust-strip copy in §4 of new homepage** is "evidence-first / audit trail / sensitivity-aware". Current trio (`Landing.jsx:237-241`) is "cites a document / context stays sealed / signal is verified". **"Audit trail"** is supported by `db.audit_log` + `routers/audit.py`. **"Sensitivity-aware"** maps to `routers/studio.py` sensitivity scoring. **"Evidence-first"** maps to BM25 grounding + `[doc:xxx]` citation pattern (`Security.jsx:22`). Wording change is not a feature regression.

### Content production

18. **Sandbox copy** at `Sandbox.jsx:124-127` reads "Five questions. AKKI builds you a fictional company mirroring your sector and region…" — this is **5 questions** today, but `Landing.jsx:117` and the brief both say **"60 seconds"**. The 60-seconds claim is reused as the new primary CTA. Verify this is still accurate (the actual time to first signal in the sandbox is `60s` per `AUDIT_iter68.md` Journey A).
19. **Cliché audit was clean** (zero matches on banned-term list, zero exclamation marks). The remaining tone work is on metaphors, not clichés.

---

## 7. Asset / screenshot requirements for §2 "60-second proof"

The new §2 needs **3 visuals**: intake → workspace → signal card with citation.

I inspected `pages/Sandbox.jsx`, `pages/SandboxGenerating.jsx`, `pages/QuickResults.jsx`, `pages/Workspace.jsx` for screenshot suitability.

### Frame 1 — Intake
**Source: `pages/Sandbox.jsx:101-285`** (5-question form: Q1 company, Q2 sector, Q3 role, Q4 region, Q5 objective). Visually:
- `bg-[var(--cream)]` background
- `akki-overline` "Sandbox · 60 seconds · no sign-up" (`:117`)
- `akki-serif text-[30px]` headline "Try AKKI on data that looks like yours." (`:118-123`)
- White rounded inputs, Q-numbered labels with `akki-overline` (`:130-200`)
- Framer-motion entrance (still capture would be after motion settles)

**Recommendation: SCREENSHOT REAL UI.** Capture the form mid-completion (Q1 + Q2 filled, Q3 visible). Crop to ~600px tall. Already cream-coloured, on-brand, no chrome to hide.

### Frame 2 — Workspace (with the pack open)
**Source: `pages/Workspace.jsx:498-682`** (the main workspace) **OR** `pages/QuickResults.jsx:55-307` (the post-sandbox arrival page).

- `Workspace.jsx` is dense — sidebar `DocumentsBrowser` (`:117-303`) + main `DocumentPane` (`:306-497`) + bottom citation rail (`:620-622`). Not first-run friendly to screenshot — too many UI affordances visible.
- `QuickResults.jsx` is **purpose-built for first-run**: 3 use-case cards (`:31-53`) keyed `summary` / `risks` / `briefing`, each with icon + title + blurb + CTA. Cleaner shot.

**Recommendation: SCREENSHOT `QuickResults.jsx` REAL UI.** Capture the 3-card grid with the user's filename in the hero (`Q4_Audit_Committee_Pack_Nov2025.pdf` style is already used in `FirstRunDemo`). This is the literal "workspace" frame from the user's POV after sandbox seeding completes.

### Frame 3 — Signal card with citation
**Two options:**

**Option A — Reuse the existing `FirstRunDemo` signal card.** The cards already exist as live JSX at `Landing.jsx:85-108` (with tone-coloured borders, Risk/Gap/Opportunity labels, headlines). They render in HTML — just freeze-frame the CSS animation at 100% complete. No source citation chip is shown today, though.

**Option B — Build a stylised mock block** mimicking a real Workspace signal card with `[doc:xxx]` citation. The Workspace bottom rail (`Workspace.jsx:620-622`) shows: "Click any `[doc:…]` citation to open the document on the left" — this confirms the actual UI uses inline `[doc:abc123]` tokens, not chip-style citations. **Backend grounding contract** is `(headline, evidence_paragraph, sources: [{doc_id, page, section}])` per `briefings_service.py:40-60`.

**Recommendation: STYLISED MOCK BLOCK.** Real Workspace signal cards in production carry monospace `[doc:abc123]` inline citations that look terse and developer-y in a marketing context. A new stylised block — 1 risk-tone card + bold inline citation chip + page reference — communicates the proof faster than a screenshot. Shape:

```
┌────────────────────────────────────────────┐
│ ⚠ RISK                                     │
│ ERP migration 90% complete for six months  │
│ — schedule risk on Q1 close.               │
│                                            │
│ Evidence: "[the rollout has been at 90% …] │
│  [doc:Q4_Audit_Pack.pdf · p.14]            │
└────────────────────────────────────────────┘
```

### Net asset list for §2

| Frame | Source | Method |
|---|---|---|
| 1. Intake | `pages/Sandbox.jsx:101-285` | **Real screenshot**, mid-form |
| 2. Workspace | `pages/QuickResults.jsx:55-307` | **Real screenshot** of 3-use-case grid |
| 3. Signal w/ citation | `Landing.jsx:85-108` (existing) + new citation chip | **Stylised mock block** (preferred) — keep tone-coloured card aesthetic but add inline `[doc:xxx · p.14]` chip not present in current code |

The existing `FirstRunDemo` (`Landing.jsx:44-111`) is a **single composed loop** (upload → reading → signals appear). The new §2 needs **3 distinct static frames**, so the loop animation has to be split into 3 stills (or remain animated but with explicit pause states).

---

## 8. Summary of dispositions

| Disposition | Count | Sections |
|---|---|---|
| **KEEP** | 2 | First-run demo (recast for §2), Trust strip layout |
| **REPLACE with new copy** | 4 | Masthead, Hero, Editorial pull-quote (expand to 3), Final CTA, Colophon footer |
| **RELOCATE to /features** | 2 | ThreePillars, EnterpriseFeature band+demo |
| **RELOCATE to /about** | 1 | Audience cards (NED+Exec) |
| **DROP** | 2 | "Akki Solve" anchor pill in nav, "Security Design" in nav (stays in footer) |
| **NEW components needed** | 5 | SixtySecondProof (3-state), SharpestUseCase (Friday→Tuesday), PriceSignal, expanded Voice trio, flat 9-link footer |
| **Routes missing** | 5 | `/methodology` (or re-point), `/plans`, `/status`, `/terms`, `/privacy`; plus Enterprise public-page question |

No homepage code was modified during this audit. All findings are anchored to file:line citations above.
