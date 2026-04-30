# AKKI · Progress Audit + Journey Guide (iter68)

_A concluding review after 67 iterations. Written to answer three
questions: **are we maintaining our experience rules, have all
requirements been met or dropped, and does the journey actually deliver
the promise?**_

---

## 0 · What just closed

**Share with the Chair** (iter68, P0 carry-over) — the Studio's last
loose thread. Closed today.

- Backend: `POST /api/contexts/{cid}/studio/{kind}/{aid}/share-email`
  (Resend) + public `GET /api/public/studio/track/{token}` (JWT-signed,
  14-day TTL, redirects to in-app deep link).
- External readers collapse to a synthetic `account_id =
  external:<sha256(email)>` so re-opens dedupe just like logged-in users.
- Frontend: **Share** affordance on every DeckStep and every Studio
  history row; `<ShareArtefactModal>` with toast + success state.
- Verified end-to-end via curl: email sends via Resend (`mode=sent`),
  recipient click records a view, exposure score moved 0 → 52, 302 to
  `/app/decks/:id` or `/app/prepare#brief-:id`.

Outcome: **the Studio is now a genuine distribution surface, not a
sandbox**, and the Exposure Score is fed by real external behaviour.

---

## 1 · Experience rules — are we still holding the line?

The platform was built against a small set of non-negotiables. Rating
each one honestly:

| Rule | Status | Evidence |
|---|---|---|
| **Editorial, not transactional** (Georgia serif leads, Inter chrome, JetBrains for metadata, cream/oxblood) | **HOLDING** | CSS tokens tokenised since iter2; every new component uses them. Iter65 landing redesign held the palette and added navy only as a third accent. |
| **No progress bars / step counters / "Stage 2 of 6"** on Plays/Workflows | **HOLDING** | Per iter24 cadence rules. Plays stages are named, not numbered. Only surface that uses numerals is Cycle's "1·Your team / 2·…" spine — deliberate because the user asked for it in iter33. |
| **AKKI as "the third party"** (reply-to principal, not to AKKI) | **HOLDING** | Every outbound email (checklists, shares, report handoffs) uses `"AKKI for <Executive>" <noreply@...>` with reply-to on the principal. |
| **Context-primary isolation** (switching context or role rebuilds the experience) | **HOLDING** | Iter46 added strict `my_role` enforcement + context realignment. Deep-linking via `/decks/resolve/{id}` and `/briefings/resolve/{id}` auto-switches active context when needed. |
| **Trust-first chrome** — footer + shielding chip on every authed page | **HOLDING** | "INTERNAL · SECURE · CONFIDENTIAL" centred in topbar (iter51). Trust centre reachable from anywhere. |
| **Synisense shielding on every LLM call** | **HOLDING** | Every LLM-backed endpoint returns `shielding: {identifiers_masked, by_category, shielded_by}` — covered by `iter9` regression. |
| **Validated by an independent model** visible on anything consequential | **MOSTLY HOLDING** | Real second-LLM validator (Gemini 2.5 Flash) on Briefs (iter49). Decks, Reports and Solve syntheses **do not yet carry a real validator pass** — they show the badge without the second call. Minor drift. |
| **Every claim cites a source** | **HOLDING** | BM25 retrieval (M13) + source chips on signals and briefings. `Receipts` slide on every board deck. Chat audit pack (iter36) ships a SHA256-chained verify.py. |
| **Deterministic mocks where paid services aren't wired** | **HOLDING** | LLM deterministic fallback. Local disk replaces S3. Stripe test-mode key. Postmark inbound live. |
| **No generic "AI slop"** (bland purple gradients, centred layouts, emoji icons) | **HOLDING** | Lucide icons throughout. Left-aligned editorial layouts. Cream/oxblood owned. |

**Net**: 10 of 11 rules intact. The one drift (validator not fully
fanned out to decks/reports/solve) is surfaced in the backlog below.

---

## 2 · Requirements met vs dropped

The full promise of AKKI sits across three layers: **marketing
story**, **BRD v4.0 modules**, and **user-feedback waves**. Walking
each layer:

### 2.1 · The marketing promise (current landing page)

> "AKKI reads the pack so you can read the room."

The landing page makes four explicit promises. Each maps to a shipped
capability:

| Landing claim | Surface | Live? |
|---|---|---|
| 01 — "Track strategic goals against where you actually are" | Monitor → Strategic Goals | ✅ |
| 02 — "Consolidate your team's submissions into board-ready reports" | Cycle + Reports | ✅ |
| 03 — "Cite every number to the page it came from. No unsourced claims." | Signals, Briefings, Chat audit pack | ✅ |
| Three-pillar hero — **Solve · Cross-Board Pulse · Decks + Reports** | /app/solve, /app/home aggregated stream, /app/decks | ✅ |
| Live sensitivity demo on the landing page | `POST /api/public/studio/sensitivity-demo` | ✅ (regex scorer, microseconds) |
| Enterprise band — "auto-sensitivity · read-tracking · exposure score" | Studio (iter64-68) | ✅ (with the Share-with-Chair loop closed today) |

**Landing honours the promise.** The only weak link is **Cross-Board
Pulse** — it exists (Home aggregated stream), but the landing copy
implies a dedicated surface that inspects patterns across multiple
boards. Today it's a toggle on Home, not a standalone surface. Worth
either upgrading the feature or softening the copy.

### 2.2 · BRD v4.0 modules (18 modules, Path A = free-tier)

Shipped (live and used): M0 Contexts · M1 Shell · M2 Onboarding ·
M3 Documents · M5 Signals/Ask · M7 Doc Viewer · M9 Learn · M11
Pipeline · M12 Briefings · M13 Hybrid retrieval · M14 Lens +
Simulate · M15/M16 Home · M17 Signals feed · M18 Workspace. **14
of 18 modules live.**

Deferred (explicitly, per Path A rules): M4 Stripe billing hooks are
mocked (keys accepted, checkout URL minted, webhook wired, but no
real subscription state — iter22 shipped the scaffolding). M6
Integrations (Calendar / board portals) not started. Vector DB
still BM25. Real virus scan still a stub.

**Dropped entirely**: none. Everything in the BRD is either live or
tracked. That's unusual for 67 iterations — worth calling out.

### 2.3 · User-feedback waves (the surprise)

The heaviest lift across iterations was **responding to the user's
directed feedback**, not following the BRD. A compressed tally:

- Sprint 1-3 (iter3-5): tabbed Home + Portfolio page + Context
  committees + Simulate + Comments
- Sprint 4-9 (iter6-12): BM25 Ask, Pipeline trace drawer, server.py
  refactor (1941→171 lines), All-boards aggregated Home, External
  Share
- Sprint 10-14 (iter13-19): Sandbox pre-auth evaluation, 6 polished
  sector templates, Sandbox→account conversion, Learn mini-tabs,
  marketing site
- Sprint 15-28 (iter20-29): Reports chain + polish diff, Plays
  (Workflows) with editorial cadence, Doc engagement, Agenda
  Evolution, Strategic Goals + extract + score history
- UX batches (iter30-49): 30+ targeted pieces from direct user
  asks — rename Play→Workflow, Chat with audit pack, Influence Map,
  Prepare/Catch-up, Postmark inbound, Minutes as first-class,
  Enterprise upsell, deep-tier quota system, Decks pipeline with
  outline→generate→quality→feedback loop
- AKKI Solve (iter56-63): Full 4-phase state machine, 27 curated
  comparables, handoff trio (brief/decks/cycle), PDF export, Pro
  pricing
- Studio (iter64-68): Merged Decks + Reports, sensitivity scoring
  (regex + LLM tiebreaker), read receipts, exposure score, plan-gated
  PII, **Share with the Chair** (today)

**Not a single user ask dropped on the floor.** Every backlog item
from the PRD's "Open / deferred" sections has been either shipped,
mocked with a clear upgrade path, or tagged P2 with explicit
reasoning.

---

## 3 · Journey guide — is it seamless?

Walking two canonical journeys, I look for: **does each surface hand
off to the next without the user having to think?**

### Journey A — A new executive (seasoned, busy)

1. `akki.ai` — hero CTA → **"Try AKKI in 60 seconds"** → `/sandbox`.
2. 5-question intake (company, sector, role, region, **objective** —
   iter38's critical addition).
3. `/sandbox/generating/:id` — 10-stage streaming narrative with
   *their* sector woven in. Seed takes ~2s; streaming holds till ready.
4. `/app/quick-results/:cid/:docId` — **3 doc-bound use-cases**
   (iter43) with one-click output. Validator badge visible. No flood.
5. `/app` — Home with PlayReady / AgendaEvolution cards; sidebar
   reveals 12 surfaces. Continue-with-[doc] pill in topbar.
6. 24h later — **ObjectiveCheck** card surfaces (iter39): "Did
   this trial feel like time well spent?" — captures yes/partial/no
   + note. Feeds the Sandbox KPI dashboard (iter40).
7. `/signup?from_sandbox=<cid>` — conversion flow keeps the explored
   environment as a working context.

**Seamless**: ✅ The sandbox→signup bridge is the most polished
journey in the product. Every step drops the user where they need
to be next. iter59/60 fixed the cookie-poisoning loop that had
briefly broken this flow.

**Weak link**: the `/app` landing after signup is *very* dense for a
brand-new user. 12 sidebar entries + PlayReady + AgendaEvolution +
InSummary + WorkflowsHub + QuickActions + RecentActivity is a lot
to parse simultaneously. The SandboxTutorial card helps (iter38) but
it's easy to dismiss.

### Journey B — An NED preparing for Thursday's audit committee

1. Home → **Catch-up** (iter64 rename — was "Prepare") → Brief tab.
2. Generate brief. Validator runs in background (Gemini Flash).
   Walk-in question surfaces.
3. Modal opens inline. "Send to colleague" → ShareModal.
4. **Solve** surface for the one nagging problem ("our top-3 credit
   concentration keeps ticking up"). 4-phase state machine. 3 curated
   comparables appear in synthesis. Lock-in → Handoff Trio:
   - → **Decks + Reports** (Studio) → outline → confirm → Opus deck
     with sensitivity auto-scored + exposure pill live.
   - → **Cycle** → 1-3 questions dropped into the question bank,
     tagged to the relevant reportees.
   - → **Brief** → opening paragraph from synthesis, lock-in items
     become decide/watch/walk-in chips.
5. From the Studio history row → **Share** → recipient gets a
   tracked email. Clicks land back on the deck. **Exposure score
   updates in real time** — the NED sees on the pill that the Chair
   opened it before Thursday.
6. Thursday morning, NED hits `/app` → the freshly-dispatched
   checklist is visible via PlayReady card ("PLAY READY · Board
   Pack Play — April 2026 report just dispatched"). One click opens
   the Board Pack Play at stage "Consolidate submissions".

**Seamless**: ✅ The Solve → Handoff → Distribution → Exposure
loop is the **most distinctive journey the product delivers**.
Nothing I've seen in the competitive set stitches this together.

**Weak links**:
- The `/app/plays` page is still reachable and functional, but the
  primary entry point is now Home's PlayReady cards and the Studio's
  ActiveWorkflowsRail (iter66). Two routes to the same thing is
  tolerable but redundant.
- Briefings (`db.briefings`, the formal document) vs briefs (`db.briefs`,
  the Catch-up brief) still confuse — they're different collections
  with different UX. iter67 worked around it by routing briefing
  rows in Studio history to the PDF export (blob URL). Solid
  workaround but a rename wouldn't hurt ("Briefings" → "Reports" in
  the history strip, since that's what they are).

---

## 4 · What's genuinely dropped / at risk

Being honest about the edges:

1. **Real Stripe billing hooks for Solve Pro** — iter22 shipped
   Stripe Checkout wiring; the Solve Pro toggle is still gated by
   `account.plan` being manually set. Users can click "Upgrade to
   Pro" and land at the Stripe test-mode checkout, but the webhook
   doesn't flip the Solve Pro affordance back into "unlimited" mode
   — it just flips `plan` to `pro`. **Close this loop before any
   real monetisation push.** (P1, tagged in iter62.)

2. **Real validator coverage** — briefs carry a Gemini Flash
   countercheck (iter49). Decks, reports and Solve syntheses carry
   the visual badge but not the actual second-LLM call. **Either
   upgrade to the real validator or soften the badge copy on those
   surfaces.** (P1.)

3. **Cross-Board Pulse as a dedicated surface** — landing implies
   this is a pillar, but today it's a toggle on Home's aggregated
   stream. **Build the surface or retire the claim.** (P1.)

4. **Vector DB** — BM25 is sufficient for MVP but the grounding
   quality will hit a ceiling at ~50 documents per context.
   Pinecone or pgvector when scale demands it. (P2, explicit Path A
   deferral.)

5. **Workflows route duplication** — `/app/plays` still exists
   alongside the Studio's ActiveWorkflowsRail and Home's PlayReady
   cards. Works, but three entry points for the same thing. (P2,
   cosmetic.)

6. **Experimental LLM tiebreaker on sensitivity** — iter66 added it
   for the ambiguous "internal" band, but it's opt-in via query
   parameter. Worth promoting to default-on with opt-out so the
   scoring quality improves for everyone. (P2.)

7. **Deep-link friction for non-AKKI recipients** — the Share with
   the Chair tracker lands a non-authenticated recipient on
   `/app/decks/:id` which bounces them to `/signin`. For external
   directors who *aren't* on AKKI, this is friction. Consider a
   public read-only artefact view for recipients with valid
   share-tokens. (P1, new — introduced by today's feature.)

---

## 5 · The promise, delivered?

The platform promises "the colleague who reads with you". For the
**seasoned executive on an AKKI-provisioned seat**, yes —
unambiguously. The Sandbox → Signup → Solve → Handoff → Studio →
Share → Exposure loop is a complete, distinctive journey.

For the **external NED reading a shared document**, partially — the
tracked link works, the exposure loop closes, but the recipient hits a
sign-in wall on arrival if they're not on AKKI. That's the next
friction to remove.

For the **enterprise buyer reviewing AKKI's trust posture**, yes —
Trust centre, Synisense shielding, audit-pack export, chain-of-custody
on reports, Postmark inbound, bank-grade chat audit log, and now
sensitivity scoring + read-tracking on every artefact. The
differentiator is real.

---

## 6 · Priority list (iter69+)

**P1 — close the open loops introduced during build-out**
- Real Stripe → Solve Pro state flip (unblocks monetisation)
- Real validator fan-out to decks, reports, Solve syntheses
- Cross-Board Pulse as a proper surface OR soften landing copy
- Public read-only share page for non-AKKI recipients

**P2 — cosmetic / polish**
- Rename "Briefings" → "Reports" in Studio history (avoids the
  briefs vs briefings collision)
- Collapse `/app/plays` into Studio's ActiveWorkflowsRail
- Promote sensitivity LLM tiebreaker to default-on
- Real virus scan
- Vector DB upgrade when scale demands it

**P3 — open-ended**
- M6 Integrations (Calendar, board portals)
- Monthly Performance Workflow (executive) — needs §4 Monitor hooks
- Cross-Board Pulse Workflow (NED) — needs real cross-context
  signal aggregation
