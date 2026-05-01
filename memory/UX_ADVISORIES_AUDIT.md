# AKKI · In-Product UX Advisories Audit (v1)

> Read-only inventory of authenticated in-product surfaces against the 9 design
> advisories. **No code modified.** Cite-everything: every claim is anchored
> to `file:line`. Where the existing surface partially matches the advisory or
> the supporting backend is stubbed, that gap is named explicitly.
>
> Cross-reference: `/app/memory/PRODUCT_FEATURES.md` is the inventory of the
> codebase as a whole. This audit does not re-derive that inventory; it links
> to the relevant sections of it. Where this audit cites a feature or
> backend capability, follow the link to PRODUCT_FEATURES for the full
> file:line trail.

---

## 1. Surface inventory

Every authenticated route in `App.js`, with its primary file and a one-line
job-to-be-done. Routes captured from `App.js:101-142` (protected) and
`App.js:122-127` (admin).

### 1.1 Authenticated `/app/*` routes

| # | Route | App.js | Primary file | Job |
|---|---|---|---|---|
| 1 | `/app` | `:102` | `pages/AppHome.jsx` | "What changed since you were last here." Greeting + cross-board stream + role/context chooser + draggable section board. |
| 2 | `/app/workspace` | `:108` | `pages/Workspace.jsx` (681 lines) | Document Journal: 60/40 split — left `DocumentsBrowser` + main `DocumentPane`, persistent `AskPanel` on the right rail (was the dedicated `/app/ask` route before iter v4.2 — `:117` redirects). |
| 3 | `/app/prepare` | `:109` | `pages/Prepare.jsx` | Catch-up briefs + Minutes-as-first-class. Consolidates the old `/app/highlights` + `/app/briefings` (both redirect — `:114-115`). |
| 4 | `/app/cycle` | `:103` | `pages/Cycle.jsx` (1577-line router on the backend; large frontend page) | Reporting cycle: questions → reportees → checklists → submissions → reports. Executive-only (`AppShell.jsx:57` — `roles: ["executive"]`). |
| 5 | `/app/monitor` | `:104` | `pages/Monitor.jsx` | Strategic-goals + composite monitor dashboard. |
| 6 | `/app/inbound-queue` | `:110` | `pages/InboundQueue.jsx` | Postmark inbound triage queue (iter70). **Closest existing surface to the Approval modality (Advisory 4)** — see §3.4. |
| 7 | `/app/activity` | `:111` | `pages/Activity.jsx` | Recent activity log. |
| 8 | `/app/simulate` | `:118` | `pages/Simulate.jsx` | Scenario simulator. |
| 9 | `/app/lens` | `:119` | `pages/LensRoom.jsx` | Lens (analytical viewpoints) + coach sessions. |
| 10 | `/app/chat` | `:120` | `pages/Chat.jsx` (444 lines visible) | Multi-model chat surface — Claude Sonnet 4.5 / Haiku / GPT-5.2 / Gemini Pro / Flash. |
| 11 | `/app/influence` | `:121` | `pages/InfluenceMap.jsx` | Influence map (read-only graph aggregation). |
| 12 | `/app/decks(/:deckId)` | `:133-134` | `pages/Decks.jsx` | Studio surface — deck pipeline + history (renamed from "Workflows" per iter64 — see `AppShell.jsx:50-54`). |
| 13 | `/app/solve` | `:135` | `pages/AppSolve.jsx` | 4-phase Solve session (Surface → Depth → Synthesis → Lock-in). |
| 14 | `/app/documents/:id` | `:136` | `pages/DocumentViewer.jsx` (262 lines visible) | Document viewer — **Reading modality candidate (Advisory 2)**. |
| 15 | `/app/quick-results/:contextId/:docId` | `:128` | `pages/QuickResults.jsx` | Sandbox post-seed arrival page — 3 use-case grid (summary / risks / briefing). |
| 16 | `/app/contexts(/new)` | `:137-139` | `pages/ContextPortfolio.jsx` / `pages/NewWorkspace.jsx` | Portfolio of contexts; create new context. |
| 17 | `/app/plays(/:playId)` | `:105-106` | `pages/PlaysLibrary.jsx`, `pages/PlayView.jsx` | Workflow / "Plays" library + run. |
| 18 | `/app/learn(/:id)` | `:129-130` | `pages/Learn.jsx` | Editorial / learn surface. |
| 19 | `/app/manage` | `:131` | `pages/Manage.jsx` | Team + companies management (deep-linked from sidebar shortcuts, see §2.2). |
| 20 | `/app/enterprise` | `:132` | `pages/Enterprise.jsx` | Protected enterprise interest form (distinct from public `/enterprise`). |
| 21 | `/app/settings(/billing)` | `:140-141` | `pages/TenantSettings.jsx` | Tenant settings — billing tab, committee manager, inbound email panel, etc. |
| 22 | `/app/security` | `:142` | `pages/AccountSecurity.jsx` | Per-account MFA + sessions. |
| 23 | `/app/blog-admin` | `:107` | `pages/marketing/BlogAdmin.jsx` | Superadmin Exco360 composer (uses `MarketingShell`, not `AppShell`). |
| 24 | `/onboarding` | `:101` | `pages/Onboarding.jsx` | First-session flow — 7 questions (`Onboarding.jsx:62`). **First Session modality candidate (Advisory 5)**. |

### 1.2 Admin routes (`/admin/*`)

| Route | App.js | File | Job |
|---|---|---|---|
| `/admin` | `:127` | `pages/admin/AdminIndex.jsx` | Admin index. |
| `/admin/health` | `:122` | `pages/admin/HealthDashboard.jsx` | `GET /api/admin/health/full`. |
| `/admin/sandbox-kpi` | `:123` | `pages/admin/SandboxKPI.jsx` | Sandbox conversion KPIs. |
| `/admin/signal-kpi` | `:124` | `pages/admin/SignalKPI.jsx` | Signal-action heatmap. |
| `/admin/llm-spend` | `:125` | `pages/admin/LLMSpend.jsx` | Deep-tier LLM spend. |
| `/admin/auth-events` | `:126` | `pages/admin/AuthEvents.jsx` | Sampled auth-events viewer. |

### 1.3 Surfaces NOT in primary nav today

Routes that exist in `App.js` but are not in the `NAV` array of `AppShell.jsx:42-62`:

- `/app/inbound-queue` (Advisory 4 candidate) — only surfaced via the `InboundQueueCard` component on Home (`components/home/InboundQueueCard.jsx`)
- `/app/quick-results/:contextId/:docId` (Sandbox-arrival, deep-linked)
- `/app/documents/:id` (entered from Workspace document tile, not nav)
- `/app/plays/:playId` (entered from PlaysLibrary)
- `/app/contexts(/new)` (entered from PortfolioRail / Manage)
- `/app/blog-admin` (entered manually)
- `/app/enterprise`, `/app/security`, `/app/settings`, `/app/manage` — entered via top-bar avatar dropdown (`AppShell.jsx:206-255`) or sidebar Manage shortcut (`AppShell.jsx:66-69`)

**Implication for advisories**: the surfaces that need to be primary-rank for some advisories (e.g. Approval = `/app/inbound-queue`) are deep-link-only today. Surfaces that the advisories say should be deferred (e.g. Lens, Simulate, Influence Map) are primary-rank today (`AppShell.jsx:55, 56, 61`).

---

## 2. Top-bar / primary nav / global UI inventory

### 2.1 Top header — `AppShell.jsx:158-257`

| Region | Lines | Content |
|---|---|---|
| Left | `:162-169` | "AKKI" wordmark (`akki-serif text-[24px] navy`) + "for Executives" italic muted subtitle. Links to `/app`. |
| Centre | `:170-179` | Trust badge: "Internal · Secure · Confidential" — small `tracking-[0.2em]` chip, `text-[var(--accent)]` on "Internal". Pointer-events disabled — purely decorative. |
| Right group | `:181-256` | `ContinueWithPill` (continuation cue) → `cmdk-launch-btn` "Search ⌘K" (`:188-196`) → `MentionInbox` bell (`:199`) → avatar dropdown with Settings / Account security / Sign out (`:206-255`). |

**No "Daily Review" badge today.** No sensitivity-mode indicator on the top bar (de-id badge per OQ3 is not surfaced here).

### 2.2 Left sidebar (primary nav) — `AppShell.jsx:271-435`

220px-wide cream sidebar. 13 nav items in `NAV` (`AppShell.jsx:42-62`):

```
+ Add document            (oxblood pill primary action — :279-287)
- - - SURFACES - - -
  Home                    (/app)                    -- :43
  Document Journal        (/app/workspace)          -- :44
  Chat                    (/app/chat)               -- :45
  Solve  [Preview]        (/app/solve)              -- :46-47
  Catch-up                (/app/prepare)            -- :48
  Decks + Reports         (/app/decks)              -- :49
  The Lens (POV)          (/app/lens)               -- :55
  Test Hypothesis         (/app/simulate)           -- :56
  Reporting Cycle         (/app/cycle)              -- :57-58 [exec only]
  Monitor                 (/app/monitor)            -- :59
  Learn                   (/app/learn)              -- :60
  Influence Map           (/app/influence)          -- :61
- - - HOUSEKEEPING - - -
  Manage my team          (/app/manage?tab=team)    -- :67
  Manage my companies     (/app/manage?tab=companies) -- :68
```

**Current label is "Document Journal", not "Workspace"** (`AppShell.jsx:44`). This contradicts the locked default ("Primary nav label: 'Workspace' not 'Reading'"). The route is `/app/workspace`, but the label users see is "Document Journal". Decision needed.

### 2.3 Right rail — `PortfolioRail` (`components/layout/PortfolioRail.jsx`)

Permanent fixed rail on every `/app/*` page (`AppShell.jsx:263`). Default-collapsed to 12px sliver since iter57 (`:265-268`). Shows: contexts list with green active dot, role switcher inline. Reclaims ~250px of horizontal canvas in collapsed state.

### 2.4 Notifications model

Mentions only. `MentionInbox` bell at `AppShell.jsx:199` polls `/api/contexts/{cid}/mentions`. There is no:
- "Awaiting your approval" pinned queue on Home
- Daily-review badge on top bar
- System-event toast aggregator
- Push-notification surface

### 2.5 Empty / loading / error patterns

- **Home empty**: `AppHome.jsx:128-141` — single panel "let's set you up" with one CTA `start-onboarding-btn` to `/onboarding`. **This already matches the Advisory 1 empty-state pattern** in shape, though the CTA copy is "Start onboarding" rather than "Forward a document to your inbox."
- **Inbound queue empty**: `InboundQueue.jsx:226` (`inbound-queue-empty`) — center panel.
- **Chat empty**: `Chat.jsx:268` (`chat-empty`) — center splash with "New chat" CTA.
- **Loading**: most pages show `Loader2` spinner; no skeletons.
- **Error toasts**: `sonner` mounted at `App.js:70` — top-right rich colors. Used heavily in Cycle / Decks / Inbound flows.

### 2.6 Command palette (⌘K)

Implementation: `AppShell.jsx:99-114` registers global keydown; opens dialog at `:519`. Currently a **context-switcher only** (M1 stub per `AppShell.jsx:517`); becomes universal search "in M7". The locked default ("typing → BM25 only; ↵ or 'Ask AKKI' button → LLM") is **not yet implemented**.

---

## 3. Advisory-by-advisory mapping

### 3.1 Advisory 1 — Home / Entry modality

- **Pattern reference**: Linear inbox / Superhuman split / Readwise daily review. 240px context rail · main column "what changed" reverse-chrono · 320px "Awaiting your approval" right rail (hidden when empty). Empty state: single panel + "Forward a document to your inbox."
- **Currently matches advisory**: **PARTIAL.**
- **Existing surfaces in scope**:
  - `pages/AppHome.jsx` (the main page)
  - `components/home/{AgendaEvolutionCard,InboundQueueCard,InSummaryTiles,PlayReadyCards,PlaysInProgressStrip,QuickActions,RecentActivity,WorkflowsHub}.jsx` (the section cards)
  - `components/home/InboundQueueCard.jsx` — surface count of pending inbound items (closest signal to "awaiting your approval")
  - `components/cycle/ReviewInboxCard.jsx` — also surfaces an approval-shaped count
  - `components/layout/PortfolioRail.jsx` — the right-side context switcher (collapsed by default)
- **Backend capability check**:
  - "What changed since last visit" → `GET /api/me/home/stream` (`PRODUCT_FEATURES.md` §3.18) — already aggregates cross-board.
  - "Awaiting your approval" → composite query needed: pending inbound (`db.inbound_queue` where `status: pending`), pending review reports (`db.reports` where `state: review`), pending invitations, pending sandbox items. **No single endpoint exists.** Today these are surfaced as separate Home cards.
  - Empty state — `Onboarding.jsx:60-99` already exists; `AppHome.jsx:128-141` already renders an empty branch.
- **Gaps to ship the advisory**:
  - **UI**: relocate context switcher from right rail → 240px LEFT rail (currently in `PortfolioRail` on the right). Reverse `AppShell.jsx:263` placement OR introduce a dedicated 3-column Home layout that overrides the AppShell pattern for `/app` only.
  - **UI**: introduce a 320px right rail on Home only ("Awaiting your approval" pinned queue), hidden when empty. Reuse the InboundQueueCard + ReviewInboxCard patterns into a single component.
  - **Backend**: add `GET /api/me/home/awaiting` that returns `{inbound, reports, invitations, total}` from a single round-trip. (Currently the page calls 4-5 endpoints to populate Home cards — see `AppHome.jsx:54-87`.)
  - **Copy**: empty-state CTA text changes from "Start onboarding" to "Forward a document to your inbox." Requires confirming the inbound-mailbox UX is ready (it is — `routers/inbound_email.py` is production per PRODUCT_FEATURES §3.12).
- **Disposition**: **SHIPPABLE WITH BACKEND PHASE** — the awaiting-queue aggregator endpoint is small (~30 lines), but the layout shift is non-trivial because `PortfolioRail` is fixed-positioned and shared across all `/app/*` pages.
- **Risks / tensions**: moving the context switcher to the left rail means it competes with the 13-item primary nav. Decision: do they coexist (split sidebar)? Or does context switcher live above-or-below nav? `AppShell.jsx` already reserves 220px on the left for nav — adding 240px context rail makes it 460px, which is wide. Mobile (per OQ4 Q1 commitment) needs a separate pattern.

---

### 3.2 Advisory 2 — Reading modality (Document viewer)

- **Pattern reference**: Readwise Reader / Matter / Apple Books. Center max-720px body · right 360px persistent rail with paragraph-anchored AKKI commentary · top bar (title + sensitivity badge + "Generate brief" primary). Citations as superscript `p.14¶3` with hover popover. NO highlighter colours, NO multi-user annotation.
- **Currently matches advisory**: **PARTIAL — body width and rail position are right, but content type and interaction model are wrong.**
- **Existing surfaces in scope**:
  - `pages/DocumentViewer.jsx` (entry point — 262 lines)
  - `components/documents/DocumentEngagement.jsx`
  - `components/documents/DocumentEvolutionPanel.jsx`
  - `components/documents/DocumentJournalStats.jsx`
  - `components/documents/DocumentPlayContext.jsx`
  - `components/documents/DocumentSummaryCard.jsx`
  - `components/documents/DocumentSummaryPanel.jsx`
  - `components/documents/DocumentThread.jsx`
  - `components/documents/DocLensRail.jsx`
  - `pages/Workspace.jsx:516-682` — the doc pane inside the Workspace (60/40 split with persistent AskPanel)
- **Currently in DocumentViewer.jsx**:
  - Body column: `max-w-3xl mx-auto` (`:170` — that's 768px, slightly wider than the advisory's 720)
  - Right rail: `aside` at `:220-261`, sticky outline rail (parses headings out of the doc text)
  - Top bar: doc title + back button + download (`:121-156`)
  - Sensitivity badge: `TRUST_STYLE` map at `:17-22` + render at `:138-141`. **Already shows trust band** (`trusted/internal/confidential/restricted`). Maps cleanly to advisory's "sensitivity badge".
- **Backend capability check**:
  - Paragraph-anchored citations: `briefings_service.py:40-60` documents the `(headline, evidence_paragraph, sources: [{doc_id, page, section}])` contract. Backend already returns paragraph + page anchors for signals. The frontend just doesn't render them as superscript chips.
  - "Generate brief" action: `POST /api/contexts/{cid}/briefings` — production per PRODUCT_FEATURES §3.4.
  - Click-rail-item → scroll-to-paragraph: requires DOM-level paragraph IDs to exist on the rendered body text. Currently `DocumentViewer.jsx:170-205` renders body as a flat text block — no paragraph IDs.
  - Click-paragraph → scroll-rail: same — paragraph-level events need DOM hooks.
- **Gaps to ship the advisory**:
  - **UI / state**:
    1. Replace right rail content from "outline rail" (currently parses headings — `:220-261`) with **AKKI commentary**: signals + ask answers + citations, anchored to paragraphs.
    2. Add scroll-sync state — clicking rail item invokes `scrollIntoView` on the matching `[data-paragraph-id]` in the body; clicking a paragraph invokes scrollIntoView on the matching rail item.
    3. Render citations as superscript: change `[doc:Q4_Audit_Pack.pdf · p.14]` chip-style (current — visible in marketing landing's §2 frame) to `<sup>p.14¶3</sup>` inline with hover popover (Radix `Tooltip`, already in deps).
    4. Add "Generate brief" primary button to top bar — invokes `POST /briefings` with the current doc as context, navigates to `/app/prepare` with the new brief.
    5. Tighten body width: `max-w-3xl` (768px) → `max-w-[720px]`. Cosmetic.
  - **Backend**: add paragraph-anchored grounding response shape to `/api/contexts/{cid}/ask` so the rail can map ask answers → paragraph IDs. **Existing contract already returns `sources[]` with doc_id+page+section** — just need to add a stable paragraph index.
  - **Schema**: documents need stable paragraph IDs persisted (or computed deterministically from text hash) so reads after re-uploads still anchor.
- **Disposition**: **SHIPPABLE WITH BACKEND PHASE** — paragraph IDs need stable persistence; everything else is UI on top of existing endpoints.
- **Risks / tensions**:
  - The Workspace surface (`pages/Workspace.jsx:516-682`) already has a 60/40 split with persistent AskPanel. **There are now two doc-reading surfaces**: `/app/documents/:id` (DocumentViewer) and `/app/workspace` (Workspace). The advisory implies one. Decision: which one becomes the Reading modality? Workspace has the persistent Ask, DocumentViewer has the outline rail. They could be merged or one deprecated.
  - "NO multi-user annotation" — `DocumentThread.jsx` exists (`components/documents/DocumentThread.jsx`) and renders inside DocumentViewer body at `:211-220`. That's a **multi-user threaded comment surface** that conflicts directly with the advisory. Decision: remove from DocumentViewer? Move to a separate tab?
  - "NO highlighter colours" — current DocumentViewer doesn't have highlighter colours, so no conflict.

---

### 3.3 Advisory 3 — Conversation modality (Ask / Chat)

- **Pattern reference**: Claude chat with two AKKI mods — citation chips at end of every response (click → opens reading modality at the cited paragraph) + mode selector ("Ask" / "Solve" / "Draft"). Entry points: ⌘K global / AskPanel inside doc / `/chat`. NO voice / image / plugins / chat-history sidebar competing with Home.
- **Currently matches advisory**: **PARTIAL — chat surface exists with multi-model + audit, but mode selector doesn't exist and a chat-history sidebar competes with Home today.**
- **Existing surfaces in scope**:
  - `pages/Chat.jsx` (444 lines) — `/app/chat`
  - `components/ask/AskPanel.jsx` — used inside `pages/Workspace.jsx:3` (right pane on workspace)
  - `AppShell.jsx:188-196` — `cmdk-launch-btn` (current ⌘K is context-switcher, not an Ask gateway)
- **Backend capability check**:
  - Multi-model chat: `POST /api/chats/{cid}/messages` — production. Models: Claude Sonnet 4.5 / Haiku / GPT-5.2 / Gemini Pro / Flash (`PRODUCT_FEATURES.md` §3.10).
  - Citation chips: Ask answers already include `sources` per the grounding contract. Chat responses **may not** carry the same shape — need to verify by looking at `routers/chat.py:240-360` (not done in this audit, see open question §7-Q3).
  - Mode selector ("Ask" / "Solve" / "Draft"):
    - **"Ask"** maps to `/api/contexts/{cid}/ask` — production.
    - **"Solve"** maps to `/api/solve/sessions` (4-phase) — production but currently a separate dedicated surface (`/app/solve`).
    - **"Draft"** is **not a discrete backend mode**. Today, drafting happens implicitly inside Decks composer, Reports composer, Briefings composer. There is no `POST /chat/draft` style endpoint.
  - "Click chip → opens reading modality at cited paragraph" — depends on Advisory 2's paragraph-anchor work landing first.
- **Currently in `Chat.jsx`**:
  - 300px sidebar with chat history (`:243` — `grid-cols-[300px_1fr]`)
  - Header model picker + shielding policy + audit gesture (`:384-444`)
  - Splash empty state with "Start a new conversation" CTA
- **Currently in `AskPanel.jsx`** (right pane of Workspace):
  - Persistent inside Workspace, tied to the active doc
  - Click `[doc:xxx]` chip handler in Workspace at `:606`
- **Gaps to ship the advisory**:
  - **UI**:
    1. Add mode selector above input — three pills: Ask / Solve / Draft. Solve currently lives at `/app/solve` as a separate page; either merge it into Chat as a mode (large change) or keep it a deep-link from the Chat mode pill (small change).
    2. Render citation chips at end of every response with click → `/app/documents/:id#p14` deep-link (depends on Advisory 2 paragraph IDs).
    3. **Remove or hide the chat-history sidebar** at `Chat.jsx:243-302`. Per advisory: "NO chat history sidebar competing with Home." Today this 300px column lists all past chats, which is exactly what the advisory says to delete. Replace with: a small "Recent" link in the top-right of the Chat header that opens a dropdown of last 5 conversations.
    4. Wire ⌘K: typing in the palette runs BM25 against current context; pressing ↵ or "Ask AKKI" button promotes to LLM Ask. Currently ⌘K is `AppShell.jsx:519` context-switcher dialog only.
  - **Backend**: introduce a "Draft" mode contract that fans out to the right composer (Brief / Deck / Report) with the chat thread as input. Or: explicitly punt Draft to v2 and offer Ask/Solve only at v1.
- **Disposition**: **SHIPPABLE WITH BACKEND PHASE** — Ask + Solve modes are already wired; Draft is the gap. ⌘K rewrite is pure UI but non-trivial.
- **Risks / tensions**:
  - Removing the chat-history sidebar deletes a surface users rely on for re-finding past conversations. The audit ZIP export (`GET /api/chats/{cid}/audit/export.zip`) is the load-bearing receipt; the sidebar is just navigation. Replacing it with a "Recent" dropdown is fine, but flag for tester walkthrough.
  - The advisory says Chat lives at `/chat` — i.e. **no `/app/`** prefix. Per `App.js:120` the route is `/app/chat`. The advisory is probably shorthand; the actual decision is whether the surface lives under the protected app shell. Given the audit zip + per-account + shielded contract, it must.

---

### 3.4 Advisory 4 — Approval modality (the load-bearing one)

- **Pattern reference**: Superhuman triage / GitHub PR review / Hey's Imbox. "Daily Review" pattern — top-bar badge → focused full-screen queue. Items: drafted emails / ingested docs / questions for Cycle / generated briefs. 3 actions only: Approve (oxblood) / Edit (navy) / Reject (muted). Keyboard: ⏎ approve, e edit, x reject, ↑↓ navigate, esc exit. NO inline approval toasts elsewhere.
- **Currently matches advisory**: **NO — fragmented across 4-5 different inline-approval surfaces, none of which match the pattern.**
- **Existing surfaces in scope** (all are partial-approval today):
  - `pages/InboundQueue.jsx` (`/app/inbound-queue`) — closest match: triage queue for inbound documents with Accept/Reject buttons (`:339, :347`) and a reject-with-reason modal (`:393-422`). 2 actions (no Edit). Iter70 trust-tiered.
  - `components/cycle/ReviewInboxCard.jsx` — Home-card surface for reports awaiting review.
  - `pages/Cycle.jsx` — has report send-up + review flow (per `routers/cycle.py: /reports/{rid}/review` per PRODUCT_FEATURES §3.5). UI is inline buttons, not a queue.
  - `pages/Decks.jsx` — has feedback / quality-check (per `routers/decks.py:feedback`) — also inline.
  - Briefings created in `pages/Prepare.jsx` are auto-saved; no explicit approval before publish.
  - **Drafted-emails approval = does not exist.** AKKI does not currently draft outbound emails on the user's behalf as a queueable item — outbound email is only via Cycle checklist dispatch (manual trigger by the user) and Studio share-with-Chair (manual trigger).
- **Backend capability check**:
  - InboundQueue: production (`/api/contexts/{cid}/inbound-queue/{qid}/accept|reject` per PRODUCT_FEATURES §3.12). 2-state (`pending` → `accepted` / `rejected`). No `edit` action.
  - Reports review: production (`/reports/{rid}/review`).
  - **Daily Review aggregator endpoint**: does not exist. There is no single `GET /api/me/daily-review` returning the union of pending items with a stable shape and 3-action contract.
  - Keyboard navigation in queues: not implemented anywhere.
- **Gaps to ship the advisory**:
  - **UI**:
    1. New `/app/daily-review` route + page — full-screen focused queue, single-item-in-frame, hotkeys (`use-keyboard-shortcut` or simple `useEffect` keydown).
    2. Top-bar badge on `AppShell.jsx:181-256` — counts pending across all sources.
    3. 3-button action footer per item — Approve (`bg-[var(--accent)]`) / Edit (`bg-[var(--navy)]`) / Reject (muted outline).
    4. **Remove inline approve/reject buttons** from InboundQueue, Cycle reports, Decks feedback. Per advisory: "NO inline approval toasts elsewhere." This is a structural deprecation across multiple files.
  - **Backend**:
    1. New aggregator: `GET /api/me/daily-review` returning `{items: [{type, id, ctx_id, summary, created_at, …}]}`.
    2. Unify the action contract — every approvable thing accepts `POST /api/me/daily-review/{item_id}/{approve|edit|reject}` regardless of underlying type, OR proxies to the right per-type endpoint.
    3. Add **`edit`** semantics to InboundQueue (currently 2-state, advisory needs 3-state).
    4. **Drafted-emails approval queue** — net new. AKKI would need to start drafting outbound emails on the user's behalf (Cycle checklist drafts, Studio share-with-Chair drafts, etc.) and queue them for approval before send. This is a significant product expansion.
  - **Schema**: new `daily_review_items` collection or a virtual aggregator over existing collections (`db.inbound_queue`, `db.reports`, draft emails to be created).
- **Disposition**: **SHIPPABLE WITH BACKEND PHASE — and this is the largest backend phase across the 9 advisories.**
- **Risks / tensions**:
  - Drafted-emails-as-approval-items is a product expansion, not a UI rearrangement. Without it, the queue has only 2 of 4 promised item types (docs, reports). Decision: ship Phase A with docs+reports, defer email drafts to Phase B.
  - The "NO inline approval toasts elsewhere" rule conflicts with `pages/Cycle.jsx`'s polish-and-send flow — that uses inline buttons today and the workflow doesn't naturally fit a daily queue (the executive is actively iterating on a draft, not triaging). Decision: distinguish "active editing" (inline) from "passive triage" (queue).
  - Hotkey conflicts — ⏎ is already submit-form in many places; e and x are common single-key activations. Need to confirm focus is exclusive when the queue is open.

---

### 3.5 Advisory 5 — First Session modality

- **Pattern reference**: Linear onboarding / Superhuman coach / Readwise first import. Single guided conversation. Step 1: 3-question intake. Step 2: 3 doors (forward email / upload / Solve). Step 3: AKKI produces ONE artefact in reading modality. Step 4: shows what's set up (inbound + Home + daily review) in 3 sentences and exits.
- **Currently matches advisory**: **PARTIAL — `/onboarding` exists but doesn't follow the 4-step shape.**
- **Existing surfaces in scope**:
  - `pages/Onboarding.jsx:60-99` — current shape:
    - **Step 0**: declare role (NED / Executive / Dual) — `:207-249`
    - **Steps 1-7**: linear questions (`TOTAL_QUESTIONS = 7` at `:62`) — questions sourced from `lib/onboardingQuestions.js`
    - **Step 8**: review (`:318`)
    - **Step 9**: completion / hand-off (`:249-318`)
  - `lib/onboardingQuestions.js` — onboarding catalogue
  - `pages/Sandbox.jsx` — pre-auth equivalent (5-question intake, also in marketing audit §7)
- **Backend capability check**:
  - 3-question intake: backend `POST /api/contexts/{cid}/context-object` accepts arbitrary M2 onboarding answers (PRODUCT_FEATURES §3.14). 3 vs 7 questions is a frontend/copy decision.
  - 3 doors:
    - "Forward email" → inbound mailbox is production (`/api/inbound/address` returns the user's mailbox per PRODUCT_FEATURES §3.12). Need UI to surface it during onboarding.
    - "Upload" → `POST /api/contexts/{cid}/documents` is production.
    - "Solve" → `/api/solve/sessions` is production.
  - "Produce ONE artefact in reading modality" → would need to auto-trigger `POST /briefings` or similar after first doc lands, then deep-link to DocumentViewer / Reading modality. Auto-trigger logic doesn't exist today.
- **Gaps to ship the advisory**:
  - **UI**:
    1. Cut question count from 7 → 3. Decide which 3 (suggest: role, primary board / company, primary objective).
    2. After Step 1, render a 3-door panel rather than continuing the question chain.
    3. After Door selection: poll for first doc to land (inbound) or immediately (upload / solve), then transition to reading modality with the auto-generated artefact.
    4. Step 4 page: "You're set up. Forward to {inbound_address}. Home shows what changed. Daily review shows what needs you." — 3 sentences, exits to `/app`.
    5. **Remove progress bar** at `Onboarding.jsx:383`. Advisory: "NO percent-complete bars."
    6. No badges (none today, so no work).
  - **Backend**: auto-artefact on first doc — small endpoint `POST /api/contexts/{cid}/onboarding/auto-artefact` that picks Briefing or Solve based on doc type, runs it, returns artefact id.
- **Disposition**: **SHIPPABLE WITH BACKEND PHASE** (small).
- **Risks / tensions**:
  - 7 → 3 questions is a meaningful reduction. The 7 today gather context-object data used downstream (regulators, sector, jurisdiction). Decision: which 4 questions move to "ask later, in flow" vs are dropped entirely?
  - "Coach" feel of the advisory implies AKKI speaks first-person during onboarding. Current onboarding is form-shaped. Voice/tone work needed.

---

### 3.6 Advisory 6 — Cycle modality

- **Pattern reference**: Linear cycle view / Asana timeline / Notion calendar. Horizontal collapsible timeline strip pinned at top of Home. Phases NAMED: "Pack arriving" → "Reading week" → "Pre-board" → "Meeting" → "Minutes" → "Follow-up." Current emphasised; past muted; future dim. Click a phase → see what AKKI did/does/will do.
- **Currently matches advisory**: **NO — phases as the advisory describes them do not exist in the schema; the closest existing surface is play-stages, which are different.**
- **Existing surfaces in scope**:
  - `components/cycle/CycleTracker.jsx` — current cycle progress visualisation
  - `pages/Cycle.jsx` — Reporting Cycle dashboard (questions / reportees / checklists / submissions / reports)
  - `routers/cycle.py:1488-1568` — cycle_schedules CRUD (`upsert_cycle_schedule`, `disable_cycle_schedule`, cron runner)
  - `components/plays/{BoardPackStages,PreBoardStages}.jsx` — Plays use named stages. Plays != Cycle in the codebase.
- **Currently the cycle data model**:
  - `db.cycle_schedules` is keyed on `context_id` and stores recurrence rules (RRULE-style) for cycle dispatch. **The schedule is the recurrence, not the phases.**
  - `db.checklists` / `db.submissions` / `db.reports` carry their own per-instance state (`pending`, `dispatched`, `submitted`, `review`, `published`) — these are **per-artefact lifecycles**, not a context-level phase.
  - **There is no `cycle_config` collection or per-context phase enumeration.** The advisory's 6-phase model needs new schema.
- **Locked default OQ2**: cycle-phase model is **per-context** (`cycle_config` schema, 6-phase default, override in tenant settings). This means every context will need its own phase config doc.
- **Backend capability check**:
  - Per-context cycle_config: **does not exist.** Schema work is required. `db.cycle_schedules` is the closest table but encodes recurrence, not phases.
  - "What AKKI did/does/will do" per phase: would need to map phase → expected actions (e.g. "Pre-board" → run Solve, generate brief; "Minutes" → ingest minutes, extract questions). Audit-log already exists (`db.audit_log`) and could backfill the "did" half. The "will do" half needs a phase-action contract.
- **Gaps to ship the advisory**:
  - **Schema**: new `db.cycle_configs` (or extension to `db.contexts`) — `{context_id, phases: [{name, order, expected_duration_days, expected_actions}], current_phase_index, last_advanced_at}` with 6-phase default.
  - **Endpoints**:
    - `GET /api/contexts/{cid}/cycle-config` — read config + current phase
    - `POST /api/contexts/{cid}/cycle-config/advance` — manual phase advancement
    - `PATCH /api/contexts/{cid}/cycle-config` — override phases (per-tenant per OQ2)
    - `GET /api/contexts/{cid}/cycle-config/audit` — what AKKI did in this phase (filtered audit-log)
  - **UI**:
    1. New component `CyclePhaseStrip.jsx` — horizontal collapsible strip at top of `pages/AppHome.jsx`, between greeting and section board.
    2. 6 phase pills, current emphasised oxblood, past muted, future dim.
    3. Click phase → expanded panel showing past audit-log entries + future-expected actions.
    4. Tenant settings tab — phase override editor.
- **Disposition**: **SHIPPABLE WITH BACKEND PHASE** — schema is small (1 collection, 4 endpoints) but per-context default seeding needs care.
- **Risks / tensions**:
  - **The advisory's 6-phase default is a strong opinion.** Some contexts have committee cycles that don't fit "Pack arriving / Reading week / Pre-board / Meeting / Minutes / Follow-up" cleanly (e.g. quarterly audit vs monthly risk vs annual nominations). Per-tenant override mitigates this — but the default needs to be reviewed by an actual NED before ship.
  - `components/cycle/CycleTracker.jsx` already exists with a different visualisation — likely lifecycle tracking of the current `db.checklists` cycle. Decision: deprecate it, rename it, or run both.

---

### 3.7 Advisory 7 — Governance modality

- **Pattern reference**: 1Password vault / GitHub audit log. Single "Trust" panel from top-right user menu (NOT primary nav). Audit log + sensitivity classification settings + de-id status + inbound email mgmt + connected models. De-id badge next to user name in top bar when in de-id mode.
- **Currently matches advisory**: **PARTIAL — components exist scattered across multiple settings tabs; no single "Trust" panel.**
- **Existing surfaces in scope**:
  - `pages/TenantSettings.jsx` (the unified settings page; renders multiple tabs)
  - `components/settings/InboundEmailPanel.jsx` — inbound mailbox display
  - `components/settings/CommitteeManager.jsx` — committee CRUD (governance-shaped, but not in scope here)
  - `components/settings/BillingTab.jsx` — billing
  - `pages/AccountSecurity.jsx` (`/app/security`) — MFA + account lockouts
  - `components/collab/MentionInbox.jsx` (`AppShell.jsx:199`) — mentions bell, not governance
  - **Audit log surface**: `routers/audit.py: GET /api/contexts/{cid}/audit-log` exists (PRODUCT_FEATURES §3.16) but **there is no frontend page that renders it.** Current audit-log access is admin-only via `/admin/auth-events`.
  - Synisense status: `routers/synisense.py` is mock-scaffolding (PRODUCT_FEATURES §3.16). UI panel at `pages/TenantSettings.jsx:849-850` is a status note.
- **Backend capability check**:
  - Audit log: production (`GET /api/contexts/{cid}/audit-log`)
  - Audit export: `POST /api/contexts/{cid}/export` (PRODUCT_FEATURES §3.16) → ZIP export
  - Sensitivity classification settings: backfill endpoint exists (`POST /api/contexts/{cid}/studio/backfill_sensitivity`); no per-tenant default classification policy endpoint
  - De-id (Synisense): mock today (`PRODUCT_FEATURES.md` §7 Item 2 — "Synisense = local mock"). De-id is on-by-default per OQ3 (per-context default, per-message override).
  - Per-message override of de-id: backend supports policy at LLM-call time (`auto | always | off` per `routers/chat.py`); chat surface doesn't expose it as a per-message switch yet.
  - Inbound mailbox mgmt: `GET /api/inbound/address` is production
  - Connected models: `GET /api/chat/models` is production
- **Gaps to ship the advisory**:
  - **UI**:
    1. New `Trust` panel — opened from top-right user menu (`AppShell.jsx:206-255`). Sits as a Sheet or full-screen overlay.
    2. 5 sub-panels inside Trust:
       - Audit log (chronological list, filterable by type, ZIP export button — wired to `POST /export`)
       - Sensitivity policy (default per-context band, override list)
       - De-identification (current scope per OQ3, per-message override toggle in Chat input area)
       - Inbound email (the mailbox + queue link)
       - Connected models (model picker default, shielding policy)
    3. **De-id badge in top bar** when active — small chip next to user name. Shows masking on. Per OQ3 default: per-context.
  - **Backend**: small additions
    - `GET /api/contexts/{cid}/sensitivity-policy` (default + overrides)
    - `PATCH /api/contexts/{cid}/sensitivity-policy`
    - `GET /api/me/de-id-status` (per active context — derived from existing context settings)
- **Disposition**: **SHIPPABLE NOW for the UI consolidation** (all underlying endpoints exist or are 1-line additions). Synisense mock remains a mock until the live service swap (PRODUCT_FEATURES §7 #2).
- **Risks / tensions**:
  - Some content currently in `TenantSettings.jsx` is per-tenant (committees, billing); some is per-account (MFA via `/app/security`). The Trust panel is per-account-in-active-context. Three scopes co-existing in one nav location risks confusion. Decision: Trust panel covers per-account governance; per-tenant settings stay at `/app/settings`; per-account security stays at `/app/security`. Three doors, all from the avatar menu.

---

### 3.8 Advisory 8 — Depth features (Lens, Simulate, Influence Map, Strategic Goals, Plays)

- **Pattern reference**: Withheld from primary nav until corpus threshold (3 docs OR 1 briefing). Once crossed, "Depth" disclosure on Home phrased as offer not menu. Pro-only depth features show inline "Pro" pill; click → upgrade modal.
- **Currently matches advisory**: **NO — all 5 are primary-nav today, no threshold gating, no Pro pill.**
- **Existing surfaces in scope**:
  - `AppShell.jsx:55` — "The Lens (POV)" → `/app/lens` — primary nav today
  - `AppShell.jsx:56` — "Test Hypothesis" → `/app/simulate` — primary nav today
  - `AppShell.jsx:61` — "Influence Map" → `/app/influence` — primary nav today
  - **Strategic Goals**: surfaced via `pages/Monitor.jsx` (component `StrategicGoalsPanel.jsx`) — embedded in Monitor, not a separate nav item, but Monitor is primary-nav at `:59`.
  - **Plays**: `AppShell.jsx` does **not** include Plays in NAV — already deferred from primary nav (per `:50-54` comment about iter64 folding Workflows into Decks). PlaysLibrary at `/app/plays` is reachable via deep-link only.
  - `components/home/PlayReadyCards.jsx`, `PlaysInProgressStrip.jsx`, `WorkflowsHub.jsx` — Home-card surfaces for Plays
- **Backend capability check**:
  - Corpus threshold check: needs new lightweight endpoint or computed inline. Required signals: `db.documents.count_documents({context_id, status: ingested})` and `db.briefings.count_documents({context_id, status: published})`. Both are 2-line queries against existing collections.
  - Plan gating: `GET /api/solve/pro-status` already exists for Solve. Needs a unified `GET /api/me/plan-features` for cross-feature gating.
  - Lens/Simulate/InfluenceMap/Plays endpoints: production per PRODUCT_FEATURES §3.8, §3.9, §3.11. No backend gaps.
- **Gaps to ship the advisory**:
  - **UI**:
    1. **Remove from primary nav**: Lens (`AppShell.jsx:55`), Simulate (`:56`), Influence Map (`:61`). Strategic Goals stays inside Monitor (already not in nav as a top-level item). Plays already not in nav.
    2. New `DepthDisclosure.jsx` Home component — appears below the section board when corpus crosses threshold. Phrasing per advisory: "AKKI now has enough material to run a Lens analysis on your board. Try one →" with one suggested lens auto-selected (not a menu of 5).
    3. Pro pill — small chip rendered next to a Depth offer when the underlying feature is Pro-tier (currently: deep-tier Solve is Pro per PRODUCT_FEATURES §3.2; Lens/Simulate are not Pro-tier today). Click → existing upgrade modal (need to verify presence — see open question §7-Q4).
    4. Inline disclosure rotation logic — show one offer at a time, rotate weekly OR show whichever feature has highest correlation with the user's recent activity (telemetry-dependent).
  - **Backend**:
    1. `GET /api/contexts/{cid}/depth-eligibility` returning `{eligible: bool, reasons: [...], suggested_lens?: lens_id}` based on corpus threshold.
    2. `GET /api/me/plan-features` — unified plan check for Pro-gating.
- **Disposition**: **SHIPPABLE NOW for the nav-removal + threshold gate** (pure UI + 1 small endpoint). Inline rotation logic and "highest correlation" feature suggestion is **DEFERRED — needs telemetry first** (see §6).
- **Risks / tensions**:
  - Removing Lens / Simulate / Influence Map from primary nav is a regression for users who already use them. Adoption analytics required to confirm they're under-used pre-removal. If they have non-trivial usage, the advisory's "withhold until threshold" should be enforced **only for new users** — existing users keep their nav. That requires a feature flag.
  - "One suggested lens auto-selected" — there are ~12 lenses in `routers/lens.py: GET /api/lens/catalog`. Picking the right one for a given user / context is a recommendation problem. v1 can hard-code the default ("Audit Committee POV") or pick the most-popular-by-sector. v2 needs telemetry.

---

### 3.9 Advisory 9 — Studio / Composition modality

- **Pattern reference**: Notion block-based composer / Linear issue editor. Composing surface for briefings, decks, reports. Draft → refine → distribute. Sensitivity classification + read-receipt tracking inherent. Share-with-Chair flow lives here.
- **Currently matches advisory**: **PARTIAL — Studio exists with sensitivity + read-receipts + share-with-Chair, but it is NOT block-based today.**
- **Existing surfaces in scope**:
  - `pages/Decks.jsx` — Studio surface
  - `routers/decks.py` — outline → generate → quality_check → feedback (PRODUCT_FEATURES §3.3)
  - `routers/studio.py` — sensitivity + view tracking + share + history (PRODUCT_FEATURES §3.3)
  - `studio_sensitivity.py` — auto-classification regex
  - `components/studio/ShareArtefactModal.jsx` — Share-with-Chair flow
  - `pages/Prepare.jsx` — Briefings + Briefs composer
  - `routers/prepare.py` — Briefing + brief CRUD (PRODUCT_FEATURES §3.4)
  - `routers/cycle.py` (Reports section) — Report compose + polish + send_up
  - `components/cycle/PolishDiffModal.jsx` — diff modal for Report polish
- **Backend capability check**:
  - Sensitivity classification: production (`POST /api/contexts/{cid}/studio/{kind}/{aid}/rescore` + auto on creation per `studio_sensitivity.py`)
  - Read-receipt tracking: production (`POST .../view`)
  - Share-with-Chair: production (`POST .../share-email` + JWT tracker per PRODUCT_FEATURES §3.3) — **but** PRODUCT_FEATURES §7 Item 6 flags that the public read-only artefact view at `/api/public/studio/read/{token}` is **MISSING** — non-AKKI recipients clicking the tracker bounce to `/signin`. **This is a v1 P1 carry-over.**
  - Block-based composition: **does not exist.** Today, all composition is generate-then-edit-as-flat-text. There is no block-level structure (paragraph, heading, callout, image, citation, quote — Notion-style).
- **Gaps to ship the advisory**:
  - **UI** (large):
    1. Block-based composer component — wraps Briefing + Deck + Report editors. Per-block toolbar, drag-to-reorder, slash-menu for new block types.
    2. Block types: paragraph, heading 2/3, callout, citation, signal-card, divider, image. Each block carries its own metadata (e.g. citation block knows which doc / page).
    3. Sensitivity badge persists at the artefact level (already done) **and** the block level — flag a block as "internal-only" inline.
    4. Read receipts panel — adjacent to the doc, not a separate route. Already exists in `studio.py` as the engagement endpoint; UI needs to surface it next to the block view.
    5. Share-with-Chair: already exists modal-shaped; once block-based composer ships, the modal becomes the "distribute" step in the Draft → refine → distribute flow.
  - **Backend** (medium):
    1. New schema: `db.studio_blocks` — per-artefact block list with `{block_id, type, content, sensitivity_override, citation_anchor?, order}`. Block-level operations: insert, delete, reorder, update.
    2. Per-block sensitivity scoring: extension to `studio_sensitivity.py`.
    3. Public read-only artefact view at `/api/public/studio/read/{token}` — **already on the v1 backlog per PRODUCT_FEATURES §7 #6**, would land here.
- **Disposition**: **SHIPPABLE WITH BACKEND PHASE — and this is the largest UI investment across the 9 advisories.** Block-based composition is a project, not a sprint.
- **Risks / tensions**:
  - Existing Briefings / Decks / Reports composers each have different shapes (Briefings is generated-text + speaking-notes; Decks is outline → slides; Reports is composed-text with polish-diff). Forcing all three into one block-based composer requires careful UX work.
  - Block-based ≠ free-form. The advisory implies Notion-style flexibility, but a brief is structurally more like an FT leader (intro / claim / evidence / question) — the block library should be opinionated, not infinite.
  - Per-block sensitivity is a **cool capability with unclear demand**. If no listed-company governance reviewer is asking for paragraph-level classification today, defer it.

---

## 4. Prioritised fix list

Ranked by **load-bearing-ness × cost-inverse × reversibility-high**. Highest leverage first.

| Rank | Advisory | Fix | Cost | Backend dep? | Reversibility | Recommended phase |
|---|---|---|---|---|---|---|
| 1 | 1 — Home | Add 320px right rail "Awaiting your approval" pinned queue, hidden when empty (reuses existing InboundQueueCard + ReviewInboxCard). Empty-state CTA copy change to "Forward a document to your inbox." | **S** | Yes — small `GET /api/me/home/awaiting` aggregator | High | Phase 1 (this sprint) |
| 2 | 2 — Reading | Replace DocumentViewer right rail content from "outline" → "AKKI commentary anchored to paragraphs" + add "Generate brief" primary action in top bar + cite-as-superscript rendering | **M** | Yes — paragraph IDs need stable persistence | Med | Phase 1 |
| 3 | 7 — Governance | Consolidate audit-log + sensitivity + de-id + inbound + connected-models into a single Trust panel from avatar menu. All endpoints exist or are 1-liners. De-id badge in top bar when active. | **S** | Minor — 2 small endpoints (sensitivity policy GET/PATCH) | High | Phase 1 |
| 4 | 8 — Depth nav | Remove Lens / Simulate / Influence Map from primary nav. Add Home `DepthDisclosure` component with corpus threshold (3 docs OR 1 briefing). Single suggested lens auto-selected (hard-coded "Audit Committee POV" at v1). | **S** | Minor — 1 endpoint `/depth-eligibility` | High | Phase 1 |
| 5 | 5 — First Session | Cut onboarding from 7 → 3 questions. Remove progress bar. Add 3-door step (forward / upload / Solve). Auto-artefact on first doc. | **M** | Minor — 1 endpoint `/onboarding/auto-artefact` | High | Phase 1 |
| 6 | 3 — Conversation | Hide chat-history sidebar in `Chat.jsx`. Add mode-pill (Ask / Solve / Draft); Draft punts to v2. Citation chips at end of every response (depends on rank-2 paragraph IDs). | **M** | Yes — Draft mode contract; ⌘K BM25→LLM rewrite | Med | Phase 2 (after rank 2 lands) |
| 7 | 4 — Approval | Build full-screen Daily Review queue at `/app/daily-review` with hotkey nav. Top-bar badge. Aggregator endpoint. **Phase A**: docs + reports as queue items. **Phase B**: drafted-emails-as-queue-items (product expansion). | **L** | Yes — large: aggregator + unified action contract + Phase B email-draft generation | Med | Phase 2 (Phase A); Phase 3 (Phase B) |
| 8 | 6 — Cycle | New `cycle_configs` collection, 6-phase default (Pack arriving / Reading / Pre-board / Meeting / Minutes / Follow-up), per-context override per OQ2. Phase strip on Home below greeting. | **L** | Yes — large: new collection + 4 endpoints + tenant settings UI for overrides | Med | Phase 2 |
| 9 | 9 — Studio | Block-based composer for Briefings / Decks / Reports. Per-block sensitivity. **Land the public read-only artefact view first** (already P1 per PRODUCT_FEATURES §7 #6). | **L** | Yes — largest: new `studio_blocks` schema + block-level endpoints | Low | Phase 3 |

**Phase 1 totals: 5 advisories, 1 L sprint of UI + ~5 small backend additions. The high-reversibility, high-leverage cluster.**

---

## 5. Mockup-priority modalities — implementation sketches

These are not Figma mockups. They are component-composition sketches the next person picks up and implements.

### 5.1 Advisory 2 — Reading modality (mockup-priority)

**File entry**: `pages/DocumentViewer.jsx` (already exists, restructure)

**Component composition** (left → right):

```
<DocumentReadingShell>          // new wrapper, replaces current AppShell child layout
  <ReadingTopBar>
    <BackToWorkspace/>
    <DocTitle>{doc.title}</DocTitle>
    <SensitivityBadge band={doc.data_trust} />   // already exists at :138-141, reuse
    <GenerateBriefButton onClick={() => api.post(`/contexts/${cid}/briefings`, {doc_id})} />  // NEW primary action
  </ReadingTopBar>

  <ReadingSplit>                                 // grid-cols: 1fr 360px on lg+
    <DocBody className="max-w-[720px] mx-auto">  // tighten from current max-w-3xl
      {paragraphs.map(p => (
        <Paragraph
          id={`p-${p.idx}`}                      // NEW: stable paragraph anchor
          data-paragraph-id={p.idx}
          onClick={() => scrollRailToParagraph(p.idx)}
        >
          {p.text}
          {p.citations.map(c => (                // NEW superscript cite chip
            <SuperscriptCite
              page={c.page}
              paragraph={c.section}
              tooltip={<EvidencePopover doc={c.doc_id} excerpt={c.excerpt} />}
            >p.{c.page}¶{c.section}</SuperscriptCite>
          ))}
        </Paragraph>
      ))}
    </DocBody>

    <CommentaryRail className="w-[360px] sticky top-16">  // replaces current outline rail at :220-261
      {akki_commentary.map(item => (
        <CommentaryItem
          key={item.id}
          type={item.type}                       // 'signal' | 'ask-answer' | 'note'
          tone={item.tone}                       // for signals: 'risk' | 'gap' | 'opportunity'
          anchorParagraphId={item.anchor}
          onClick={() => scrollBodyToParagraph(item.anchor)}
        >
          <ItemHeadline>{item.headline}</ItemHeadline>
          <ItemEvidence>{item.evidence}</ItemEvidence>
          <ItemCite page={item.page} paragraph={item.section} />
        </CommentaryItem>
      ))}
    </CommentaryRail>
  </ReadingSplit>
</DocumentReadingShell>
```

**State** (top-level in `DocumentViewer.jsx`):
```js
const [doc, setDoc] = useState(null);                      // existing
const [paragraphs, setParagraphs] = useState([]);          // NEW — derived from doc text + extraction
const [commentary, setCommentary] = useState([]);          // NEW — signals + ask answers + notes for this doc
const [scrolledTo, setScrolledTo] = useState(null);        // NEW — currently-anchored paragraph for scroll-sync highlighting
```

**Data sources**:
- `GET /api/contexts/{cid}/documents/{did}` — existing
- `GET /api/contexts/{cid}/signals?doc_id={did}` — existing (filter signals to this doc)
- `GET /api/contexts/{cid}/ask?doc_id={did}` — existing (filter ask answers)

**Removed from current `DocumentViewer.jsx`**:
- The `<DocumentThread>` mounted inside body at `:211-220` (multi-user comments — explicitly counter-advisory)
- The outline-rail content at `:222-261` (replaced with commentary)

**Plumbing assumption**: paragraph IDs come from a deterministic split of `doc.text`. Even if the split logic is naive (split-on-double-newline), the IDs are stable enough for scroll-sync within a session. Persistent re-anchoring across re-uploads is a Phase-2 concern.

**Existing components that plug in**:
- `SensitivityBadge` ← `pages/DocumentViewer.jsx:17-22` (TRUST_STYLE map) + `:138-141`
- `EvidencePopover` ← Radix `Tooltip` (already in deps per `package.json`)
- `CommentaryItem` (signal flavour) ← style cues from `Landing.jsx §2 frame 3` (the new homepage signal mock)

---

### 5.2 Advisory 4 — Approval modality, Phase A

**File entry**: NEW `pages/DailyReview.jsx` (route `/app/daily-review`).

**Component composition**:

```
<DailyReviewShell>           // full-screen takeover, no AppShell sidebar
  <ReviewHeader>
    <ReviewCount>{items.length} awaiting your review</ReviewCount>
    <ReviewProgress>{currentIdx + 1} of {items.length}</ReviewProgress>
    <ExitButton onClick={navigate('/app')} />   // ESC also
  </ReviewHeader>

  <ReviewItemFrame>                              // single item in frame at a time
    <ItemTypeChip>{item.type}</ItemTypeChip>     // 'inbound-doc' | 'report-review' | 'cycle-question'
    <ItemSummary>{item.summary}</ItemSummary>
    <ItemPreview>
      {item.type === 'inbound-doc' && <DocPreview doc={item.payload} />}
      {item.type === 'report-review' && <ReportPolishDiff diff={item.payload} />}
      {item.type === 'cycle-question' && <QuestionCard q={item.payload} />}
    </ItemPreview>

    <ReviewActions>
      <ApproveButton kbd="↵"  onClick={() => act('approve')} />  // bg-[var(--accent)]
      <EditButton    kbd="e"  onClick={() => act('edit')} />     // bg-[var(--navy)]
      <RejectButton  kbd="x"  onClick={() => act('reject')} />   // muted outline
    </ReviewActions>
  </ReviewItemFrame>

  <ReviewFooter>
    <KbdHint>↑↓ to navigate · ↵ approve · e edit · x reject · esc exit</KbdHint>
  </ReviewFooter>
</DailyReviewShell>
```

**State**:
```js
const [items, setItems] = useState([]);
const [currentIdx, setCurrentIdx] = useState(0);
const [acting, setActing] = useState(false);

// Hotkeys
useEffect(() => {
  const onKey = (e) => {
    if (acting) return;
    if (e.key === 'Enter') act('approve');
    else if (e.key === 'e') act('edit');
    else if (e.key === 'x') act('reject');
    else if (e.key === 'ArrowDown') setCurrentIdx(i => Math.min(i+1, items.length-1));
    else if (e.key === 'ArrowUp') setCurrentIdx(i => Math.max(i-1, 0));
    else if (e.key === 'Escape') navigate('/app');
  };
  window.addEventListener('keydown', onKey);
  return () => window.removeEventListener('keydown', onKey);
}, [items, currentIdx, acting]);
```

**Data sources** (Phase A — no new aggregator needed if we accept multiple round-trips at v1):
```js
const [inbox, reports] = await Promise.all([
  api.get(`/contexts/${cid}/inbound-queue?status=pending`),
  api.get(`/reports/inbox`),  // existing endpoint per PRODUCT_FEATURES §3.5
]);
const items = [
  ...inbox.data.items.map(i => ({type:'inbound-doc', id:i.id, summary:i.subject, payload:i})),
  ...reports.data.items.map(r => ({type:'report-review', id:r.id, summary:r.title, payload:r})),
];
```

**Or** Phase A++ — single aggregator `GET /api/me/daily-review` returns the union pre-merged.

**Per-action contract** (Phase A — proxy to existing per-type endpoints):
```js
const act = async (action) => {
  setActing(true);
  const item = items[currentIdx];
  if (item.type === 'inbound-doc' && action === 'approve') await api.post(`/contexts/${cid}/inbound-queue/${item.id}/accept`);
  else if (item.type === 'inbound-doc' && action === 'reject') await api.post(`/contexts/${cid}/inbound-queue/${item.id}/reject`, {reason:''});
  else if (item.type === 'report-review' && action === 'approve') await api.post(`/reports/${item.id}/review`, {decision:'approved'});
  // 'edit' opens the per-type editor in a new tab; queue continues.
  await loadItems();              // refetch
  setCurrentIdx(0);                // reset to top
  setActing(false);
};
```

**Removed elsewhere** (per advisory's "NO inline approval toasts"):
- Inline Accept/Reject buttons in `pages/InboundQueue.jsx:339-347` — keep the page reachable but redirect actions through Daily Review; OR keep page and let Daily Review be a faster alternate path.
- Inline review buttons in `pages/Cycle.jsx`'s reports tab.

**Top-bar badge**:
```jsx
// in AppShell.jsx — replaces or sits beside cmdk-launch-btn
<DailyReviewBadge count={pendingCount} onClick={() => navigate('/app/daily-review')}>
  {pendingCount} awaiting your review
</DailyReviewBadge>
```

`pendingCount` derives from a small periodic fetch (15s interval) of the aggregator. When 0, the badge is hidden.

---

### 5.3 Advisory 6 — Cycle phase strip

**File entry**: NEW `components/home/CyclePhaseStrip.jsx`, mounted in `pages/AppHome.jsx` between `<h1>Greeting</h1>` and the section board.

**Component composition** (horizontal pinned at top):

```
<CyclePhaseStrip>
  <PhaseStripHeader>
    <CycleLabel>Q4 board cycle</CycleLabel>          // derived from cycle_config name
    <PhaseStripCollapseToggle />                      // collapses to 1-line summary
  </PhaseStripHeader>

  <PhaseStripTrack>                                  // 6 pills, equal width
    {phases.map((p, i) => (
      <PhasePill
        key={p.name}
        emphasis={
          i < current_phase_index ? 'past'           // muted
          : i === current_phase_index ? 'current'    // emphasised oxblood
          : 'future'                                 // dim
        }
        onClick={() => setExpandedPhaseIdx(i)}
      >
        <PhaseName>{p.name}</PhaseName>              // "Pack arriving" / "Reading week" / etc.
        <PhaseDuration>{p.expected_duration_days}d</PhaseDuration>
      </PhasePill>
    ))}
  </PhaseStripTrack>

  {expandedPhaseIdx !== null && (
    <PhaseExpandPanel>
      <PhaseExpandHeader>
        {phases[expandedPhaseIdx].name}
        {expandedPhaseIdx === current_phase_index && <CurrentMarker>current</CurrentMarker>}
      </PhaseExpandHeader>

      <PhaseDidDoesWill>
        <PhaseColumn label="What AKKI did">
          {past_audit_log.filter(l => l.phase === phases[expandedPhaseIdx].name).map(l => (
            <AuditLogEntry entry={l} />
          ))}
        </PhaseColumn>
        <PhaseColumn label="What AKKI is doing">
          {expandedPhaseIdx === current_phase_index ? (
            <CurrentActions actions={phases[expandedPhaseIdx].expected_actions} />
          ) : <Empty />}
        </PhaseColumn>
        <PhaseColumn label="What AKKI will do">
          {expandedPhaseIdx > current_phase_index ? (
            <ExpectedActions actions={phases[expandedPhaseIdx].expected_actions} />
          ) : <Empty />}
        </PhaseColumn>
      </PhaseDidDoesWill>
    </PhaseExpandPanel>
  )}
</CyclePhaseStrip>
```

**State**:
```js
const [config, setConfig] = useState(null);     // GET /api/contexts/{cid}/cycle-config
const [auditByPhase, setAuditByPhase] = useState({});
const [collapsed, setCollapsed] = useState(false);
const [expandedPhaseIdx, setExpandedPhaseIdx] = useState(null);
```

**Backend dependency** (per §3.6 above):
- `GET /api/contexts/{cid}/cycle-config` — must land first
- `GET /api/contexts/{cid}/cycle-config/audit?phase={name}` — gated audit-log
- (advance/override endpoints for tenant settings — not needed at first ship)

**Default phase config** (seeded on context creation):
```js
{
  context_id, current_phase_index: 0, last_advanced_at: now(),
  phases: [
    { name: 'Pack arriving',  order: 0, expected_duration_days: 3, expected_actions: ['ingest_pack', 'classify_sensitivity'] },
    { name: 'Reading week',   order: 1, expected_duration_days: 4, expected_actions: ['surface_signals', 'compose_brief', 'flag_risks'] },
    { name: 'Pre-board',      order: 2, expected_duration_days: 1, expected_actions: ['final_brief', 'speaking_notes', 'questions_to_table'] },
    { name: 'Meeting',        order: 3, expected_duration_days: 1, expected_actions: ['minutes_capture'] },
    { name: 'Minutes',        order: 4, expected_duration_days: 5, expected_actions: ['ingest_minutes', 'extract_actions', 'cycle_questions'] },
    { name: 'Follow-up',      order: 5, expected_duration_days: 14, expected_actions: ['monitor_strategic_goals', 'cross_pack_signals'] },
  ]
}
```

**Existing components that plug in**:
- `components/cycle/CycleTracker.jsx` — current cycle visualisation (per-checklist). Distinct from this PhaseStrip but renders adjacent on /app/cycle. Keep both at v1 — they show different views (PhaseStrip = where in the rhythm; CycleTracker = where in the dispatched checklist).
- `routers/audit.py` — audit-log feed. Filter by `created_at` window matching the phase.

**Existing risks**:
- A context can have multiple committees (Audit, Risk, Nominations, …). Each may be on a different cadence. v1: single phase strip = the **board** cadence; per-committee phases are v2.
- Phase advancement: manual at v1 (user clicks "Mark phase complete"). Cron-based auto-advance is v2.

---

## 6. Things deferred and why

### 6.1 Forward-design hypotheses requiring telemetry first

| Hypothesis | Why telemetry-blocked |
|---|---|
| "Lens / Simulate / Influence Map are under-used and safe to remove from primary nav" (Advisory 8) | Remove based on telemetry, not opinion. Need 4-week window of nav-click distribution before disabling for existing users. |
| "Daily Review queue length stabilises at <10 items/day for active users" (Advisory 4) | Determines whether the queue is one-frame-at-a-time or a scroll list. Today: unknown. |
| "Onboarding 7→3 questions doesn't materially hurt downstream signal quality" (Advisory 5) | The 7 questions populate `db.context_objects` which is grounding for downstream LLM calls. Cutting 4 may reduce signal precision. Need A/B before ship. |
| "Single suggested lens auto-selected" — which lens (Advisory 8) | Defaulting to "Audit Committee POV" is a guess. Telemetry on lens-selection-by-sector lets us pick the high-correlation default per sector. |
| "Block-based vs structured-template composer" (Advisory 9) | Not all artefact types benefit equally from block flexibility. Briefings have a strict editorial shape; Decks have a stricter one (slide-shaped). Reports are the most flex-amenable. Telemetry on edit-actions per artefact type informs whether full block-based is worth the lift. |

### 6.2 Capabilities blocked by stubbed backends

| Capability the advisory needs | Stub | Reference |
|---|---|---|
| Live de-id status badge in top bar (Advisory 7) | Synisense is mock-scaffolding; the regex masker is real, but the "Synisense status: live" claim is a planned URL swap | `PRODUCT_FEATURES.md` §3.16 + §7 #2 (`backend/llm_service.py:1-9`) |
| Public read-only artefact view for Share-with-Chair (Advisory 9) | Endpoint `GET /api/public/studio/read/{token}` is on the v1 backlog but **not implemented** — non-AKKI recipients clicking the Studio tracker bounce to `/signin` | `PRODUCT_FEATURES.md` §7 #6 |
| Real ClamAV virus scan during inbound triage (Advisory 1 right rail surfacing inbound items) | `documents_service.virus_scan_stub` only catches EICAR test signatures | `PRODUCT_FEATURES.md` §7 #1 (`backend/documents_service.py:26`) |
| Validator-confirmed signal in commentary rail (Advisory 2) | Validator badge exists across surfaces but the actual second-LLM Gemini-Flash check only runs on Briefings today; Decks/Reports/Solve syntheses show the badge without the call | `PRODUCT_FEATURES.md` §7 #4 |
| Cycle-reply ingestion landing as a Daily Review item (Advisory 4 Phase B) | `routers/cycle.py:15` flags reply ingestion as stub | `PRODUCT_FEATURES.md` §7 #11 |
| In-app Share email landing as a Daily Review item (Advisory 4 Phase B) | `components/share/ShareModal.jsx:96` shows email-on-share is "stub logged — SMTP delivery ships with email-in integration" — distinct from the production Share-with-Chair on Studio | `PRODUCT_FEATURES.md` §7 #12 |
| Stripe → Solve Pro state flip on Daily Review's "approve plan upgrade" item (Advisory 8 upgrade modal) | Webhook flips `account.plan` but Solve Pro affordance still requires manual flip | `PRODUCT_FEATURES.md` §7 #3 |

### 6.3 Features requiring new schema work

| Feature | Schema needed |
|---|---|
| Cycle phases (Advisory 6) | `db.cycle_configs` per-context with 6-phase default |
| Daily Review queue Phase B (Advisory 4 — drafted emails) | `db.draft_emails` (or extension to existing `db.shares` with `status: pending_approval`) |
| Block-based composition (Advisory 9) | `db.studio_blocks` per-artefact |
| Stable paragraph anchors (Advisory 2) | Either persisted on `db.documents` as a `paragraphs[]` field, or computed-and-cached |
| Per-context sensitivity policy (Advisory 7) | New field on `db.contexts` or new `db.sensitivity_policies` |
| Per-message de-id override in Chat (Advisory 7) | New field on `db.chat_messages` (`shielding_override: 'auto'|'always'|'off'`) — backend supports this at LLM-call time but no per-message persistence exists |

---

## 7. Open questions that block design

Before drawing mockups (i.e. before Phase 1 starts), these need answers from the orchestrator:

1. **Q1 — Primary nav label**: locked default says "Workspace" not "Reading", but `AppShell.jsx:44` currently labels it "Document Journal". Three candidates exist: Workspace / Document Journal / Reading. Which does the new nav use?

2. **Q2 — Reading modality canonical surface**: `/app/documents/:id` (DocumentViewer) and `/app/workspace` (Workspace) are both doc-reading surfaces today, with different UX (DocumentViewer = single doc + outline rail; Workspace = doc list + persistent Ask). The advisory implies one. Decision: deprecate one, merge them, or keep both with distinct purposes?

3. **Q3 — Chat citation chip behaviour**: do Chat responses in `pages/Chat.jsx` currently carry `sources[]` in the message payload? The audit didn't read deep enough into `routers/chat.py`. If yes, the citation chip work is pure UI. If no, the contract needs adding.

4. **Q4 — Existing upgrade modal**: Advisory 8 says Pro pill click → upgrade modal. Does an upgrade modal exist today or is it new? `routers/billing.py: POST /api/billing/checkout` is production, but the *modal* component is unverified in this audit.

5. **Q5 — Chat-history sidebar removal**: Advisory 3 says "NO chat history sidebar competing with Home." Today `Chat.jsx:243-302` is a 300px sidebar of all past chats. Removing it deletes a wayfinding surface. Replacement: top-right "Recent" dropdown? Sheet? Or genuinely not surfaced (only via deep-link from audit zip)?

6. **Q6 — Cycle phase default per OQ2**: locked default says 6-phase, per-context, override in tenant settings. Are the 6 phases in §3.6 the final names? Specifically: "Reading week" feels NED-specific (executives often have less than a week); "Pre-board" assumes a single board, not committee-by-committee.

7. **Q7 — Daily Review Phase A scope**: include reports + inbound-docs only at Phase A, or also include cycle-questions (reportee questions waiting to dispatch)? The latter is a more conventional "approve before sending" item but adds a third item-type.

8. **Q8 — Approval modality and active editing**: `pages/Cycle.jsx`'s polish-and-send report flow is iterative — the executive edits, AKKI proposes diffs, the executive iterates. Does that flow live inside Daily Review (the 'Edit' action opens the polish editor) or stay outside the queue entirely?

9. **Q9 — Depth disclosure rotation**: Advisory 8 says one offer at a time. With 5 candidate features (Lens / Simulate / Influence Map / Strategic Goals / Plays), what's the rotation policy? Round-robin? Highest-correlation? First-unseen? At v1 we suggested "hard-code one default per sector" — confirm.

10. **Q10 — De-id badge on top bar (Advisory 7)**: badge text? Current candidate from PRODUCT_FEATURES is "Shielded" or a small lock icon. Locked default says per-context default + per-message override; the badge represents the current default. When the user overrides per-message, does the badge dim, blink, or annotate?

11. **Q11 — Mobile commitment scope (OQ4)**: Q1 commitment for Reading + Approval modalities. Does Reading mobile = stripped-down DocumentViewer (no rail, citations as inline links) or a different layout entirely (Readwise-Reader-style edit-margin notes)? Does Approval mobile = same focused queue but vertically stacked actions?

12. **Q12 — Onboarding question reduction (Advisory 5)**: which 4 of the current 7 onboarding questions get cut, and which 3 stay? The 7 today populate `db.context_objects` for downstream grounding. Cutting wrong ones reduces grounding precision.

13. **Q13 — Studio block library scope (Advisory 9)**: which block types are v1? Suggested: paragraph, heading 2/3, callout, citation, signal-card, divider. Anything else? Image blocks, table blocks, embed blocks?

---

_End of audit. No code modified during this review. All findings anchored to file:line citations above. Cross-reference: `/app/memory/PRODUCT_FEATURES.md` for the full inventory of routers / collections / stubs._
