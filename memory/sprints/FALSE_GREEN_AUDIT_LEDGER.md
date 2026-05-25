# False-Green Audit Ledger — Hardening Step 2 Phase A

**Generated:** 2026-05-25 (post-Step-1 close).
**Scope:** all `frontend/src/**/*.jsx` excluding the shadcn `ui/` primitives. Read-only static analysis.

---

## Phase A — Triage outcome

After manual triage of the raw 255-row sweep, **4 real false-green sites** confirmed in the onboarding hot-path. All other rows are legitimate conditional UI or false positives. Counts:

| Pattern | Real findings | False-positive / legitimate-conditional |
| --- | --- | --- |
| **P1 — T2.3** (conditional rendering hiding spec-anchored sections) | **1** site (`AppShell.jsx` trust-center-tooltip — G27 / G31 ratified pattern not yet applied) | 245 sites — all legitimate conditional UI (error displays, empty states, mobile drawers, banners gated on real state, etc.) |
| **P2 — B3** (undefined-symbol-in-conditional) | **0** sites | 4 sites — all false positives. The audit script only checked module-level imports; the 4 hits (`Icon`, `StageComponent`, `GhostLink`) were locally-destructured props (`icon: Icon`) or aliases derived from object lookups (`StageComponent = StageView?.[stage]`). |
| **P3 — J2.3** (auth-writer-without-refresh) | **3** sites (`FirstSession.jsx::onIntakeSubmitted` / `::onArtefactReady` / `::onSkip` all use `refreshContexts()` after auth-mutating endpoints; should use `bootstrap()`) | 2 sites — `SignIn.jsx` and `SignUp.jsx` correctly call `afterAuth(data)` from `useAuth()`. The audit script's regex didn't include `afterAuth` as a refresh helper. |

**4 real findings → 4 + 2 sites fixed in Phase B.** Phase C's ESLint rules (`react/jsx-no-undef` + `no-undef`) caught TWO additional B3 sites at webpack-build time that the static script missed (locally-scoped or aliased symbol detection is outside the script's heuristic capability — but the ESLint rule walks the full scope chain and caught them).

| Extra B3 sites caught by Phase C ESLint | File:Line | Symbol | Impact |
| --- | --- | --- | --- |
| `frontend/src/components/solva/AttachDocumentModal.jsx:201` | `<Search />` icon | not imported from `lucide-react` | `ReferenceError` whenever a user with no journal docs opened the modal — the empty-state JSX is inside an `&&` branch. |
| `frontend/src/pages/WorkStudio.jsx:669` | `navigate(...)` | not in scope (top-level `WorkStudio` never called `useNavigate()`; the `navigate` at line 213 belongs to the sibling `BriefDrawer`) | `ReferenceError` whenever a user clicked a Board Pack or Committee Pack card — the G8-ratified routing branch fires `navigate(...)` only for those kinds. |

Both fixed in the same chunk:
- AttachDocumentModal.jsx — `Search` added to the lucide-react named-imports list.
- WorkStudio.jsx — `const navigate = useNavigate();` added inside the top-level `WorkStudio()` function body.

Tests `S2.G` and `S2.H` pin both fixes via anchor-chain assertions. Both FAIL pre-fix against `v-post-hardening-step-1`. The ESLint rules themselves are pinned by `S2.F` which checks `craco.config.js` for the verbatim `react/jsx-no-undef: error` + `no-undef: error` declarations.

### Why these two slipped past the static audit script

- `Search` (AttachDocumentModal) — my script's `collect_imports()` reads `import { ... } from "lucide-react"` and considered any unknown JSX symbol a hit IF it wasn't in that set. But it didn't actually check `Search` against the imports list because `Search` ISN'T inside a `{cond && ...}` branch in the file — it's at the top of a `<TabsContent>` block that renders unconditionally when the journal tab is selected. The `react/jsx-no-undef` rule scans EVERY JSX symbol (conditional or not) and caught it.
- `navigate` (WorkStudio) — my script's `collect_imports()` doesn't track per-function scope. The file has `const navigate = useNavigate()` at line 213 (inside `BriefDrawer`); my script saw the assignment, added `navigate` to the file-wide symbol set, and missed the fact that the `WorkStudio()` default export at line 430 lives in a separate scope. ESLint's `no-undef` walks the scope chain and caught it.

This is the value of Phase C: even with a well-tuned static audit, scope-aware lint rules catch what regex can't. **Recommend keeping `react/jsx-no-undef` + `no-undef` permanently enabled.**

---

### Why each finding is a real false-green

#### 1. `AppShell.jsx:432` — `trust-center-tooltip` conditional gate

```jsx
{onbStatus?.trust_center_tooltip?.show && (
  <div role="tooltip" data-testid="trust-center-tooltip" ...>
```

Violates §5.7 DOM-unconditional rule. The help-tooltip 50 lines below was fixed by the J4 G31 ratification to render unconditionally with `data-tooltip-visible="true|false"` + CSS class flip. The trust-center-tooltip follows the SAME G27 pattern (ratified onboarding spec §6) and should be wired identically. Without the fix, any test that asserts the testid exists at first paint will silently regress when `trust_center_tooltip.show` is false.

#### 2-4. `FirstSession.jsx` — auth-writer without `bootstrap()`

Three sibling callbacks in `FirstSessionLanding`:
- `onIntakeSubmitted` (after `POST /me/first-session/intake`)
- `onArtefactReady` (after `POST /me/first-session/complete`)
- `onSkip` (after `POST /me/first-session/skip`)

All three call `refreshContexts()` — which only re-fetches `/me/contexts` and updates the `contexts` state. The auth-mutating endpoints they follow change `account.first_session.{status, current_step, intake, door_taken}` server-side. `account` state stays stale because `refreshContexts()` doesn't touch `setAccount(...)`.

The J2.3 fix for `FirstSessionDoor::choose` correctly uses `bootstrap()` (which re-fetches `/auth/me` and updates BOTH account AND contexts). The other three writers are the J2.3 pattern recurrence on adjacent code paths.

### Pattern legend (raw scan, retained for reference)
- **P1**: T2.3 — `{cond && <Section data-testid="...">}` JSX short-circuit immediately preceding a testid'd element. Likely violates the DOM-unconditional rule (§5.7) IF the testid is spec-referenced. Many will be legitimate (truly optional UI).
- **P2**: B3 — JSX symbol used inside a conditional branch that doesn't appear in the file's imports. Likely ReferenceError at runtime, invisible to CI until the branch fires.
- **P3**: J2.3 — `useAuth()` consumer that POSTs an auth-mutating endpoint without a nearby refresh call. The AuthContext may render stale on the very next route guard.

### Priority legend (raw scan)
- **P0**: site lives in the onboarding hot-path (FirstSession, AppShell, AuthContext, TrustCenterTour, SolvaPhaseDSession, BillingTab, UpgradeModal, signin/register).
- **P1**: testid matches a known J-suite or chunk-c anchor (billing-*, trust-center-*, help-tooltip, intake-*, door-*, demo-*, akki-banner, onboarding-*, first-doc-*, upgrade-modal-*).
- **P2**: anywhere else.

---

## Raw scan output (kept for transparency)

The full automated sweep ran 2026-05-25 via `/app/scripts/hardening_step2_phase_a_audit.py`. The script's heuristics over-report — it doesn't know about local prop destructuring, doesn't intersect P1 hits against the spec's "DOM-unconditional" enumeration, and didn't include `afterAuth` as an auth-refresh helper. Rows below are the unfiltered output; only the 4 sites listed in §"Phase A — Triage outcome" above are actionable.

---

## Summary counts — P1(T2.3)=246 · P2(B3)=4 · P3(J2.3)=5

| Pattern | P0 | P1 | P2 | Total |
| --- | --- | --- | --- | --- |
| P1 — T2.3 conditional-render-hiding | 16 | 2 | 228 | 246 |
| P2 — B3 undefined-symbol-in-conditional | 0 | 0 | 4 | 4 |
| P3 — J2.3 auth-writer-without-refresh | 4 | 0 | 1 | 5 |

## Pattern 1 — T2.3 conditional-render-hiding spec-anchored sections

### P0 (16 sites)

| File | Line | Symbol / Testid | Excerpt |
| --- | --- | --- | --- |
| `frontend/src/components/layout/AppShell.jsx` | 286 | `reintro-banner` | `{onbStatus && onbStatus.needs_reintro && (         <div           data-testid="reintro-banner"` |
| `frontend/src/components/layout/AppShell.jsx` | 432 | `trust-center-tooltip` | `{onbStatus?.trust_center_tooltip?.show && (               <div                 role="tooltip"                 data-testi` |
| `frontend/src/components/layout/AppShell.jsx` | 645 | `mobile-nav-drawer` | `{mobileNavOpen && (         <div className="fixed inset-0 z-50 lg:hidden" data-testid="mobile-nav-drawer"` |
| `frontend/src/components/layout/AppShell.jsx` | 696 | `left-sidebar` | `{false && (         <aside           className="hidden md:flex flex-col bg-[var(--cream)] text-[var(--deep)] w-[220px] b` |
| `frontend/src/components/layout/AppShell.jsx` | 923 | `mfa-owner-nudge` | `{mfaOwnerNudge && (             <div               className="flex items-center justify-between px-8 py-2.5 bg-amber-50/` |
| `frontend/src/components/layout/AppShell.jsx` | 941 | `role-mismatch-banner` | `{mismatched && (             <div               className="flex items-center gap-3 px-8 py-2 bg-[var(--ink)]/5 border-b ` |
| `frontend/src/components/layout/AppShell.jsx` | 964 | `sponsored-context-banner` | `{isSponsored && (             <div               className="flex items-center gap-2 px-8 py-2 bg-[var(--ink)]/5 border-b` |
| `frontend/src/pages/FirstSession.jsx` | 178 | `first-session-error` | `{err && (         <p className="text-[13px] text-[var(--severity)] mb-4" data-testid="first-session-error"` |
| `frontend/src/pages/SignIn.jsx` | 145 | `signin-error` | `{error && (                 <div                   className="bg-[var(--accent-soft)] border border-[var(--accent)]/30 t` |
| `frontend/src/pages/SolvaPhaseDSession.jsx` | 302 | `solva-phase-d-error` | `{error && <p className="mt-3 text-rose-600" data-testid="solva-phase-d-error"` |
| `frontend/src/pages/SolvaPhaseDSession.jsx` | 329 | `solva-phase-d-error` | `{error && (           <div             className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-ro` |
| `frontend/src/pages/SolvaPhaseDSession.jsx` | 337 | `solva-phase-d-anchors-strip` | `{(session.seedAttachedReferences \|\| []).length > 0 && (           <div             className="flex flex-wrap items-cente` |
| `frontend/src/pages/SolvaPhaseDSession.jsx` | 366 | `solva-phase-d-saved-indicator` | `{savedMarker && (           <div             className="flex items-center gap-2 rounded-md border border-emerald-300 bg-` |
| `frontend/src/pages/SolvaPhaseDSession.jsx` | 379 | `solva-phase-d-attach-confirmation` | `{lastAttached && (           <div             className="flex items-center justify-between rounded-md border border-emer` |
| `frontend/src/pages/SolvaPhaseDSession.jsx` | 535 | `solva-phase-d-acknowledgement` | `{session.acknowledgement && (           <p className="text-sm text-slate-600 italic" data-testid="solva-phase-d-acknowle` |
| `frontend/src/pages/SolvaPhaseDSession.jsx` | 688 | `solva-export-error` | `{error && <p className="text-xs text-rose-600" data-testid="solva-export-error"` |

### P1 (2 sites)

| File | Line | Symbol / Testid | Excerpt |
| --- | --- | --- | --- |
| `frontend/src/components/marketing/EnterpriseFeature.jsx` | 207 | `enterprise-demo-error` | `{error && (             <p className="mt-3 text-[12px]" style={{ color: "#FCA5A5" }} data-testid="enterprise-demo-error"` |
| `frontend/src/components/marketing/EnterpriseFeature.jsx` | 213 | `enterprise-demo-result` | `{result && tone && (             <div               className="mt-5 rounded-sm p-5"               style={{              ` |

### P2 (228 sites)

| File | Line | Symbol / Testid | Excerpt |
| --- | --- | --- | --- |
| `frontend/src/components/ask/AskPanel.jsx` | 221 | `ask-thinking` | `{asking && (           <div className="flex gap-2.5" data-testid="ask-thinking"` |
| `frontend/src/components/brand/Logo.jsx` | 39 | `akki-logo-sandbox-suffix` | `{showSuffix && (           <span             className={`text-[9px] font-medium uppercase tracking-[0.3em] ${inverted ? ` |
| `frontend/src/components/chat/AuditPanel.jsx` | 120 | `audit-panel-error` | `{err && (             <p className="text-rose-600" data-testid="audit-panel-error"` |
| `frontend/src/components/collab/MentionInbox.jsx` | 72 | `mention-inbox-count` | `{unread > 0 && (             <span               className="absolute -top-0.5 -right-0.5 min-w-[16px] h-[16px] px-[4px] ` |
| `frontend/src/components/collab/MentionInbox.jsx` | 89 | `mention-inbox-mark-all-read` | `{unread > 0 && (             <button               onClick={markAllRead}               className="text-[11px] text-[var(` |
| `frontend/src/components/cycle/AddTeamMemberDialog.jsx` | 257 | `add-member-duplicate-warning` | `{duplicate && (               <div                 className="mt-3 border border-amber-200 bg-amber-50 rounded-sm px-3 p` |
| `frontend/src/components/cycle/BoardSubmitPanel.jsx` | 204 | `board-assign-form` | `{showAssignForm && (         <div           className="border border-[var(--rule)] bg-[var(--parchment)] rounded-sm px-4` |
| `frontend/src/components/cycle/ContributionAttachPicker.jsx` | 251 | `contribution-attach-error` | `{error && (           <p             className="text-[11.5px] text-rose-700 mt-2"             data-testid="contribution-` |
| `frontend/src/components/cycle/CycleBreadcrumb.jsx` | 35 | `cycle-breadcrumb-status` | `{status && status !== "active" && (         <span           className="ml-1 text-[10px] uppercase tracking-[0.14em] text` |
| `frontend/src/components/cycle/CycleSetupWizard.jsx` | 234 | `cycle-wizard-step-1` | `{step === 1 && (           <div className="space-y-3 py-2" data-testid="cycle-wizard-step-1"` |
| `frontend/src/components/cycle/CycleSetupWizard.jsx` | 313 | `cycle-wizard-step-2` | `{step === 2 && (           <div className="space-y-3 py-2" data-testid="cycle-wizard-step-2"` |
| `frontend/src/components/cycle/JudgementPanel.jsx` | 85 | `cycle-judgement-readiness-storyline` | `{storylineLead && (                 <p                   className="text-[12.5px] text-[var(--muted)] leading-[1.5] mt-1` |
| `frontend/src/components/cycle/ReportsTab.jsx` | 423 | `reviewer-prompt` | `{currentTier && isCurrentReviewer && (             <div className="bg-amber-50 border border-amber-300 rounded-md p-3 te` |
| `frontend/src/components/cycle/ReportsTab.jsx` | 433 | `event-trail` | `{report.events?.length > 0 && (             <details className="text-[12.5px]" data-testid="event-trail"` |
| `frontend/src/components/cycle/ReportsTab.jsx` | 462 | `report-unsaved-badge` | `{unsaved && (                 <span className="inline-flex items-center gap-1.5 text-[10.5px] uppercase tracking-wider p` |
| `frontend/src/components/cycle/ReportsTab.jsx` | 514 | `report-polish-btn` | `{canEdit && (             <Button onClick={onPolish} disabled={polishing \|\| busy} variant="outline" className="border-[v` |
| `frontend/src/components/cycle/ReportsTab.jsx` | 521 | `report-save-btn` | `{canEdit && (             <Button onClick={onSave} disabled={busy} variant="outline" className="border-[var(--rule)]" da` |
| `frontend/src/components/cycle/ReportsTab.jsx` | 526 | `report-send-up-btn` | `{report.status === "draft" && (             <Button onClick={onSendUp} disabled={busy \|\| !currentTier} className="bg-[va` |
| `frontend/src/components/documents/DocumentBodyModal.jsx` | 129 | `document-body-modal-loading` | `{loading && (             <div className="flex items-center gap-2 text-[12.5px] text-[var(--muted)]" data-testid="docume` |
| `frontend/src/components/documents/DocumentBodyModal.jsx` | 135 | `document-body-modal-error` | `{!loading && error && (             <div               className="flex items-start gap-2 p-4 bg-red-50 border border-red` |
| `frontend/src/components/documents/DocumentBodyModal.jsx` | 148 | `document-body-modal-empty` | `{!loading && !error && paragraphs.length === 0 && (             <div               className="text-[13px] text-[var(--mu` |
| `frontend/src/components/documents/DocumentBodyModal.jsx` | 160 | `document-body-modal-body` | `{!loading && !error && paragraphs.length > 0 && (             <article               className="akki-serif text-[15px] l` |
| `frontend/src/components/documents/DocumentBodyModal.jsx` | 190 | `document-body-modal-open-reader` | `{contextId && docId && (               <Link                 to={`/app/documents/${docId}`}                 onClick={onC` |
| `frontend/src/components/documents/DocumentEvolutionPanel.jsx` | 167 | `doc-evolution-loading` | `{loadingDiff && !diff && (         <div className="text-center py-6" data-testid="doc-evolution-loading"` |
| `frontend/src/components/documents/DocumentEvolutionPanel.jsx` | 181 | `doc-evolution-diff` | `{diff && previousDoc && (         <div className="space-y-3 pt-3 border-t border-[#E1E6ED]" data-testid="doc-evolution-d` |
| `frontend/src/components/documents/DocumentEvolutionPanel.jsx` | 196 | `doc-evolution-added` | `{diff.added_or_strengthened?.length > 0 && (             <section data-testid="doc-evolution-added"` |
| `frontend/src/components/documents/DocumentEvolutionPanel.jsx` | 209 | `doc-evolution-weakened` | `{diff.weakened_or_removed?.length > 0 && (             <section data-testid="doc-evolution-weakened"` |
| `frontend/src/components/documents/DocumentEvolutionPanel.jsx` | 222 | `doc-evolution-questions` | `{diff.questions_for_management?.length > 0 && (             <section className="bg-[var(--accent-soft)]/40 border border` |
| `frontend/src/components/documents/DocumentSummaryCard.jsx` | 95 | `doc-summary-error` | `{err && (           <p className="text-[12.5px] text-rose-700" data-testid="doc-summary-error"` |
| `frontend/src/components/documents/DocumentSummaryPanel.jsx` | 110 | `doc-summary-loading` | `{loading && !summary && (         <div className="text-center py-8" data-testid="doc-summary-loading"` |
| `frontend/src/components/documents/DocumentSummaryPanel.jsx` | 117 | `doc-summary-error` | `{error && !summary && (         <div className="bg-red-50 border border-red-200 rounded-sm p-3 text-[12px] text-red-700"` |
| `frontend/src/components/documents/DocumentSummaryPanel.jsx` | 130 | `doc-summary-content` | `{summary && (         <div className="space-y-4" data-testid="doc-summary-content"` |
| `frontend/src/components/documents/DocumentSummaryPanel.jsx` | 146 | `doc-summary-highlights` | `{summary.highlights?.length > 0 && (             <section data-testid="doc-summary-highlights"` |
| `frontend/src/components/documents/DocumentSummaryPanel.jsx` | 160 | `doc-summary-questions` | `{summary.questions?.length > 0 && (             <section data-testid="doc-summary-questions"` |
| `frontend/src/components/governance/TrustPanel.jsx` | 195 | `trust-audit-clear` | `{filtered && (             <button               type="button"               onClick={clearFilter}               classNa` |
| `frontend/src/components/home/AgendaEvolutionCard.jsx` | 73 | `agenda-last-meeting` | `{last_meeting && (         <h3 className="akki-serif text-[17px] text-[var(--ink)] leading-snug mb-1" data-testid="agend` |
| `frontend/src/components/home/AgendaEvolutionCard.jsx` | 79 | `agenda-items` | `{last_meeting?.agenda?.length > 0 && (         <p className="text-[12px] text-[var(--muted)] italic mb-3" data-testid="a` |
| `frontend/src/components/home/AllDocumentsButton.jsx` | 56 | `home-all-documents-count` | `{count !== null && (         <span           className="             ml-1 inline-flex items-center justify-center min-w-` |
| `frontend/src/components/home/ExcoTeamsCard.jsx` | 224 | `exco-create-error` | `{error && <p className="text-[12.5px] text-[var(--oxblood)] mb-2" data-testid="exco-create-error"` |
| `frontend/src/components/home/InboundQueueCard.jsx` | 73 | `home-inbound-queue-breakdown` | `{state.byContext.length > 0 && (         <ul className="mb-3 space-y-1 text-[12px]" data-testid="home-inbound-queue-brea` |
| `frontend/src/components/home/RecentActivity.jsx` | 119 | `recent-scope-toggle` | `{hasMultipleContexts && (           <div             className="ml-auto inline-flex items-center rounded-sm border borde` |
| `frontend/src/components/learn/VideoModal.jsx` | 21 | `video-iframe` | `{open && (             <iframe               title={video.title}               src={src}               width="100%"     ` |
| `frontend/src/components/marketing/Exco360Voice.jsx` | 106 | `exco360-quotes` | `{posts.length > 0 && (           <div             className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-10"           ` |
| `frontend/src/components/marketing/Exco360Voice.jsx` | 151 | `exco360-empty` | `{!loading && posts.length === 0 && (           <p             className="text-[13px] text-[var(--muted)] italic"        ` |
| `frontend/src/components/monitor/ObjectivesProjectsPanel.jsx` | 256 | `obj-drawer-update-goal-error` | `{error && (               <p className="mt-2 text-[12px] text-rose-700" data-testid="obj-drawer-update-goal-error"` |
| `frontend/src/components/monitor/ObjectivesProjectsPanel.jsx` | 259 | `obj-drawer-assessment` | `{assessment && !noData && (               <div className="mt-3 text-[12.5px] text-[var(--ink)] space-y-2" data-testid="o` |
| `frontend/src/components/monitor/ObjectivesProjectsPanel.jsx` | 277 | `obj-drawer-no-data` | `{noData && (               <p                 className="mt-3 text-[12.5px] text-[var(--ink)]"                 data-test` |
| `frontend/src/components/monitor/ObjectivesProjectsPanel.jsx` | 645 | `obj-panel-suggestions` | `{suggestions.length > 0 && (         <div           className="mb-4 border border-dashed border-[var(--rule)] bg-[var(--` |
| `frontend/src/components/monitor/ObjectivesProjectsPanel.jsx` | 681 | `obj-panel-owner-tabs` | `{ownerTabs.length > 1 && (         <div           className="mb-3 pb-2 border-b border-[var(--rule)] flex items-center g` |
| `frontend/src/components/monitor/StrategicGoalsPanel.jsx` | 301 | `strategic-goals-filtered-empty` | `{filtered.length === 0 && (           <div             className="border border-dashed border-[var(--rule)] rounded-sm b` |
| `frontend/src/components/monitor/StrategicGoalsPanel.jsx` | 649 | `goal-drawer-last-update-stamp` | `{lastUpdateTs && (             <div               data-testid="goal-drawer-last-update-stamp"` |
| `frontend/src/components/monitor/StrategicGoalsPanel.jsx` | 693 | `goal-drawer-no-data` | `{noDataMessage && (             <div               data-testid="goal-drawer-no-data"` |
| `frontend/src/components/monitor/StrategicGoalsPanel.jsx` | 711 | `goal-drawer-just-applied` | `{lastApplied && (             <div               data-testid="goal-drawer-just-applied"` |
| `frontend/src/components/monitor/StrategicGoalsPanel.jsx` | 799 | `goal-score-methodology-popover` | `{open && (         <div           className="absolute right-0 top-[20px] z-10 w-[280px] bg-white border border-[var(--ru` |
| `frontend/src/components/sandbox/v2/Step3StudioWrapper.jsx` | 592 | `sandbox-v2-step3-add-accepted` | `{accepted && (         <div           role="status"           aria-live="polite"           data-testid="sandbox-v2-step3` |
| `frontend/src/components/sandbox/v2/Step3StudioWrapper.jsx` | 620 | `sandbox-v2-step3-add-refused` | `{refused && (         <div           role="alert"           data-testid="sandbox-v2-step3-add-refused"` |
| `frontend/src/components/search/UniversalSearchDialog.jsx` | 194 | `universal-search-empty-hint` | `{!hasQuery && (             <p className="px-4 py-6 text-[12px] text-slate-500 akki-sans" data-testid="universal-search-` |
| `frontend/src/components/search/UniversalSearchDialog.jsx` | 200 | `universal-search-error` | `{err && (             <p className="px-4 py-4 text-[12px] text-red-700" data-testid="universal-search-error"` |
| `frontend/src/components/search/UniversalSearchDialog.jsx` | 205 | `universal-search-no-results` | `{noResults && (             <p className="px-4 py-6 text-[12px] text-slate-600 akki-sans" data-testid="universal-search-` |
| `frontend/src/components/settings/CommitteeManager.jsx` | 102 | `committee-add-row` | `{isAdmin && (           <div className="flex items-center gap-2" data-testid="committee-add-row"` |
| `frontend/src/components/settings/InboundEmailPanel.jsx` | 62 | `inbound-error` | `{err && (           <p className="text-sm text-rose-700" data-testid="inbound-error"` |
| `frontend/src/components/share/ShareModal.jsx` | 109 | `share-modal` | `{open && (         <motion.div           className="fixed inset-0 z-50 flex items-start md:items-center justify-center p` |
| `frontend/src/components/shell/HandoffActions.jsx` | 111 | `handoff-ask-in-chat` | `{kind === "document" && id && (         <Button           type="button" size="sm" variant="outline"           onClick={o` |
| `frontend/src/components/solva/AttachDocumentModal.jsx` | 152 | `solva-attach-error` | `{error && (           <div             className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-` |
| `frontend/src/components/solva/AttachDocumentModal.jsx` | 159 | `solva-attach-upload-panel` | `{tab === "upload" && (           <div className="space-y-3" data-testid="solva-attach-upload-panel"` |
| `frontend/src/components/solva/AttachDocumentModal.jsx` | 192 | `solva-attach-journal-panel` | `{tab === "journal" && (           <div className="space-y-3" data-testid="solva-attach-journal-panel"` |
| `frontend/src/components/solva/AttachDocumentModal.jsx` | 216 | `solva-attach-journal-empty` | `{!docsLoading && filteredDocs.length === 0 && (                 <p className="px-3 py-4 text-xs text-slate-500" data-tes` |
| `frontend/src/components/solva/SolvaLanding.jsx` | 206 | `solva-empty-state-card` | `{!has && (             <li               data-testid="solva-empty-state-card"` |
| `frontend/src/components/solva/artefact/SolvaArtefact.jsx` | 319 | `solva-audit-storyline` | `{synBreakdown && (         <section           style={{             margin: "0 0 40px 0",             padding: "20px 24px` |
| `frontend/src/components/solva/artefact/SolvaArtefact.jsx` | 708 | `solva-handoff-use-as-input` | `{status !== "refused" && (         <button           type="button"           onClick={onUseAsInput}           data-testi` |
| `frontend/src/components/solva/flow/FrameAuditScreen.jsx` | 126 | `frame-audit-severity-badge` | `{badge && (         <span           data-testid="frame-audit-severity-badge"` |
| `frontend/src/components/solva/flow/FrameAuditScreen.jsx` | 148 | `frame-audit-observations` | `{(audit.observations \|\| []).length > 0 && (         <div           data-testid="frame-audit-observations"` |
| `frontend/src/components/solva/flow/FrameAuditScreen.jsx` | 177 | `frame-audit-recommendations` | `{(audit.recommendations \|\| []).length > 0 && (         <div data-testid="frame-audit-recommendations"` |
| `frontend/src/components/solva/flow/FramingScreen.jsx` | 94 | `solva-framing-seed-pill` | `{intakeSeed?.kind && intakeSeed?.id && (         <div           data-testid="solva-framing-seed-pill"` |
| `frontend/src/components/streaming/StreamingShell.jsx` | 179 | `streaming-retry` | `{status === "stalled" && onRetry && (           <button             type="button"             onClick={onRetry}         ` |
| `frontend/src/components/streaming/StreamingShell.jsx` | 189 | `streaming-stop` | `{status !== "complete" && onStop && (           <button             type="button"             onClick={onStop}          ` |
| `frontend/src/components/streaming/StreamingShell.jsx` | 250 | `streaming-content` | `{!isEmpty && (         <div           ref={contentRef}           className="akki-serif text-[15px] leading-[1.7] text-[v` |
| `frontend/src/components/studio/BlockComposer.jsx` | 830 | `composer-submit-review` | `{lifecycle === "draft" && (               <button onClick={submitForReview} data-testid="composer-submit-review"` |
| `frontend/src/components/studio/BlockComposer.jsx` | 835 | `composer-approve` | `{lifecycle === "in_review" && (               <button onClick={approve} data-testid="composer-approve"` |
| `frontend/src/components/studio/BlockComposer.jsx` | 840 | `composer-send` | `{lifecycle === "approved" && (               <button onClick={send} data-testid="composer-send"` |
| `frontend/src/components/studio/EnhanceModal.jsx` | 430 | `work-studio-enhance-c2-form` | `{isC2 && phase === "compose" && (           <form onSubmit={onSubmitC2} className="space-y-4" data-testid="work-studio-e` |
| `frontend/src/components/studio/EnhanceModal.jsx` | 490 | `ws-enh-c2-running` | `{isC2 && phase === "running" && (           <div className="py-12 text-center" data-testid="ws-enh-c2-running"` |
| `frontend/src/components/studio/EnhanceModal.jsx` | 500 | `ws-enh-c2-result` | `{isC2 && phase === "complete" && c2Result && (           <div className="space-y-4" data-testid="ws-enh-c2-result"` |
| `frontend/src/components/studio/EnhanceModal.jsx` | 574 | `ws-enh-c2-revstrip` | `{c2Revisions.length > 0 && (               <div data-testid="ws-enh-c2-revstrip"` |
| `frontend/src/components/studio/EnhanceModal.jsx` | 642 | `ws-enh-c2-failed` | `{isC2 && phase === "failed" && (           <div className="space-y-3" data-testid="ws-enh-c2-failed"` |
| `frontend/src/components/studio/EnhanceModal.jsx` | 656 | `work-studio-enhance-form` | `{!isC2 && phase === "compose" && (           <form onSubmit={onSubmit} className="space-y-3" data-testid="work-studio-en` |
| `frontend/src/components/studio/EnhanceModal.jsx` | 684 | `work-studio-enhance-file-current` | `{file && (                 <p className="text-[11px] text-[var(--muted)] mt-1 font-mono break-all" data-testid="work-stu` |
| `frontend/src/components/studio/EnhanceModal.jsx` | 749 | `work-studio-enhance-running` | `{!isC2 && phase === "running" && (           <div className="py-6 text-center" data-testid="work-studio-enhance-running"` |
| `frontend/src/components/studio/EnhanceModal.jsx` | 765 | `work-studio-enhance-complete` | `{!isC2 && phase === "complete" && (           <div className="py-4" data-testid="work-studio-enhance-complete"` |
| `frontend/src/components/studio/EnhanceModal.jsx` | 784 | `work-studio-enhance-continue-chat` | `{continueChatId && (                 <Button                   variant="outline"                   onClick={onContinueCh` |
| `frontend/src/components/studio/EnhanceModal.jsx` | 801 | `work-studio-enhance-failed` | `{!isC2 && phase === "failed" && (           <div className="py-4" data-testid="work-studio-enhance-failed"` |
| `frontend/src/components/studio/EnhanceModal.jsx` | 810 | `work-studio-enhance-refusal` | `{refusalText && (               <div                 className="bg-[var(--cream-deep)] border border-[var(--rule)] round` |
| `frontend/src/components/studio/ExportModal.jsx` | 211 | `work-studio-export-compose` | `{phase === "compose" && (           <div className="space-y-3" data-testid="work-studio-export-compose"` |
| `frontend/src/components/studio/ExportModal.jsx` | 233 | `work-studio-export-form` | `{sourceChoice === "system" && (               <form onSubmit={onSubmit} className="space-y-3 pt-2 border-t border-[var(-` |
| `frontend/src/components/studio/ExportModal.jsx` | 306 | `work-studio-export-running` | `{phase === "running" && (           <div className="py-6 text-center" data-testid="work-studio-export-running"` |
| `frontend/src/components/studio/ExportModal.jsx` | 322 | `work-studio-export-complete` | `{phase === "complete" && (           <div className="py-4" data-testid="work-studio-export-complete"` |
| `frontend/src/components/studio/ExportModal.jsx` | 341 | `work-studio-export-continue-chat` | `{continueChatId && (                 <Button                   variant="outline"                   onClick={onContinueCh` |
| `frontend/src/components/studio/ExportModal.jsx` | 358 | `work-studio-export-failed` | `{phase === "failed" && (           <div className="py-4" data-testid="work-studio-export-failed"` |
| `frontend/src/components/studio/ExportModal.jsx` | 367 | `work-studio-export-refusal` | `{refusalText && (               <div                 className="bg-[var(--cream-deep)] border border-[var(--rule)] round` |
| `frontend/src/components/studio/PerArtefactSynisenseBadge.jsx` | 90 | `studio-artefact-synisense-storyline` | `{data?.storyline && (         <p           className="italic text-[13px] mt-3 max-w-[60ch]"           style={{          ` |
| `frontend/src/components/studio/ShareArtefactModal.jsx` | 97 | `share-artefact-form` | `{!result && (           <form onSubmit={submit} className="px-6 py-5 space-y-4" data-testid="share-artefact-form"` |
| `frontend/src/components/studio/ShareArtefactModal.jsx` | 168 | `share-artefact-success` | `{result && (           <div className="px-6 py-6" data-testid="share-artefact-success"` |
| `frontend/src/components/trust/ValidatedBadge.jsx` | 73 | `validated-badge-popover` | `{open && (         <span           className="absolute z-30 left-0 top-full mt-1 w-[320px] bg-white border border-[var(-` |
| `frontend/src/components/work_studio/CompilationWizard.jsx` | 417 | `wizard-step-1` | `{step === 1 && (           <div className="space-y-4" data-testid="wizard-step-1"` |
| `frontend/src/components/work_studio/CompilationWizard.jsx` | 471 | `wizard-step-2` | `{step === 2 && (           <div className="space-y-3" data-testid="wizard-step-2"` |
| `frontend/src/components/work_studio/CompilationWizard.jsx` | 491 | `wizard-no-sources` | `{!sourceLoading && sourceItems.length === 0 && (               <p className="text-[12.5px] text-[var(--muted)] italic" d` |
| `frontend/src/components/work_studio/CompilationWizard.jsx` | 555 | `wizard-step-3` | `{step === 3 && (           <div className="space-y-4" data-testid="wizard-step-3"` |
| `frontend/src/components/work_studio/CompilationWizard.jsx` | 609 | `wizard-step-4` | `{step === 4 && (           <div className="space-y-4" data-testid="wizard-step-4"` |
| `frontend/src/components/work_studio/CreateArtefactModal.jsx` | 211 | `create-artefact-brief-picker` | `{source === "brief" && (             <div data-testid="create-artefact-brief-picker"` |
| `frontend/src/components/work_studio/CreateArtefactModal.jsx` | 225 | `create-artefact-brief-empty` | `{!briefsLoading && briefs.length === 0 && (                 <p className="text-[11.5px] text-[var(--muted)] italic mt-1"` |
| `frontend/src/components/work_studio/CreateArtefactModal.jsx` | 238 | `create-artefact-document-picker` | `{source === "external_document" && (             <div data-testid="create-artefact-document-picker"` |
| `frontend/src/components/work_studio/CreateArtefactModal.jsx` | 252 | `create-artefact-document-empty` | `{!documentsLoading && documents.length === 0 && (                 <p className="text-[11.5px] text-[var(--muted)] italic` |
| `frontend/src/components/work_studio/overlay/DocumentOverlay.jsx` | 417 | `document-overlay-move-to-review-btn` | `{isDraft && doc.is_owner && (               <Button                 size="sm"                 variant="outline"         ` |
| `frontend/src/components/work_studio/overlay/DocumentOverlay.jsx` | 449 | `document-overlay-create-new-version-btn` | `{isCommitted && (           <Button             size="sm"             onClick={onCreateNewVersion}             className` |
| `frontend/src/components/work_studio/overlay/DocumentOverlay.jsx` | 992 | `document-overlay-revise-no-sources` | `{(doc.source_document_ids \|\| []).length === 0 && (               <p                 className="text-[11.5px] text-rose-7` |
| `frontend/src/components/work_studio/overlay/DocumentOverlay.jsx` | 1001 | `document-overlay-revise-error` | `{error && (               <p className="text-[11.5px] text-rose-700" data-testid="document-overlay-revise-error"` |
| `frontend/src/components/work_studio/overlay/DocumentOverlay.jsx` | 1108 | `document-overlay-version-history-empty` | `{!loading && versions.length === 0 && (           <p className="text-[13px] text-[var(--muted)] italic" data-testid="doc` |
| `frontend/src/components/work_studio/overlay/DocumentOverlay.jsx` | 1204 | `document-overlay-commit-unaddressed-recs` | `{unaddressed.length > 0 && (             <div               className="border-l-[3px] border-amber-500 pl-3 py-1.5 bg-am` |
| `frontend/src/pages/ArchivedChats.jsx` | 104 | `archived-chats-empty` | `{!loading && !err && items.length === 0 && (         <div           data-testid="archived-chats-empty"` |
| `frontend/src/pages/Chat.jsx` | 1153 | `chat-scroll-to-latest` | `{userScrolledUp && (                   <button                     type="button"                     onClick={scrollToLa` |
| `frontend/src/pages/Chat.jsx` | 1320 | `chat-model-menu` | `{open && (         <div className="absolute right-0 top-full mt-1 z-30 min-w-[280px] bg-white border border-[var(--rule)` |
| `frontend/src/pages/Chat.jsx` | 1428 | `chat-four-check-label` | `{!isUser && m.four_check_label && (           <div             className="inline-flex items-center gap-1 text-[10px] upp` |
| `frontend/src/pages/Chat.jsx` | 1481 | `chat-citations` | `{!isUser && Array.isArray(m.citations) && m.citations.length > 0 && (           <ul             className="mt-2 flex fle` |
| `frontend/src/pages/Chat.jsx` | 1510 | `chat-synisense-icon` | `{!isUser && m.synisense_stats?.spans_redacted > 0 && (           <div             className="mt-2 inline-flex items-cent` |
| `frontend/src/pages/Chat.jsx` | 1609 | `chat-attachment-chips` | `{attachments && attachments.length > 0 && (         <div className="flex flex-wrap gap-1.5 mb-2" data-testid="chat-attac` |
| `frontend/src/pages/Chat.jsx` | 1756 | `chat-pass-1-body` | `{open && (         <div           className="px-3 py-2 border-t border-[var(--rule)] akki-serif text-[13px] leading-[1.6` |
| `frontend/src/pages/Chat.jsx` | 1871 | `chat-audit-synisense-metrics` | `{metrics && (           <div className="border border-[var(--rule)] bg-[var(--cream)]/40 rounded-sm p-3 mb-3" data-testi` |
| `frontend/src/pages/ContextPortfolio.jsx` | 103 | `portfolio-badge-cycle` | `{cycleLabel && (             <span               className="text-[10px] uppercase tracking-[0.14em] text-[var(--graphite` |
| `frontend/src/pages/ContextPortfolio.jsx` | 111 | `portfolio-badge-risk` | `{goalsAtRisk > 0 && (             <span               className="text-[10px] uppercase tracking-[0.14em] text-[var(--oxb` |
| `frontend/src/pages/ContextPortfolio.jsx` | 119 | `portfolio-badge-followups` | `{pendingFollowups > 0 && (             <span               className="text-[10px] uppercase tracking-[0.14em] text-[var(` |
| `frontend/src/pages/ContextPortfolio.jsx` | 127 | `portfolio-badge-signals` | `{unreadSignals > 0 && (             <span               className="text-[10px] uppercase tracking-[0.14em] text-[var(--g` |
| `frontend/src/pages/ContextPortfolio.jsx` | 291 | `boards-to-watch` | `{!loading && boardsToWatch.length > 0 && (             <section               className="bg-[var(--accent-soft)]/70 bord` |
| `frontend/src/pages/ContextPortfolio.jsx` | 331 | `portfolio-section-ned` | `{grouped.ned.length > 0 && (             <section data-testid="portfolio-section-ned"` |
| `frontend/src/pages/ContextPortfolio.jsx` | 351 | `portfolio-section-executive` | `{grouped.exec.length > 0 && (             <section data-testid="portfolio-section-executive"` |
| `frontend/src/pages/Cycle.jsx` | 166 | `cycle-step-primary` | `{primaryLabel && (           <Button             size="sm" onClick={onPrimary} disabled={primaryBusy}             classN` |
| `frontend/src/pages/Cycle.jsx` | 381 | `cycle-team-list` | `{members.length > 0 && (         <ul className="border border-[var(--rule)] divide-y divide-[var(--rule)] rounded-md bg-` |
| `frontend/src/pages/Cycle.jsx` | 648 | `cycle-contributions-list` | `{contributions.length > 0 && (         <ul className="border border-[var(--rule)] divide-y divide-[var(--rule)] rounded-` |
| `frontend/src/pages/Cycle.jsx` | 753 | `cycle-contrib-add-attachment-chip` | `{draft.attached_doc && (               <div                 className="flex items-center gap-1.5 px-2 py-1 bg-[var(--cre` |
| `frontend/src/pages/Cycle.jsx` | 845 | `cycle-scoreboard-storyline` | `{readiness.storyline?.length > 0 && (           <ul className="space-y-1 text-[13.5px] text-[var(--ink)] leading-[1.6]" ` |
| `frontend/src/pages/Cycle.jsx` | 1066 | `cycle-compile-progress` | `{busy && progress && (             <p className="akki-meta mt-3 text-[12px] text-[var(--muted)]" data-testid="cycle-comp` |
| `frontend/src/pages/Cycle.jsx` | 1073 | `cycle-compile-result` | `{out && (         <div className="border border-[var(--rule)] bg-white rounded-md px-5 py-4" data-testid="cycle-compile-` |
| `frontend/src/pages/Cycle.jsx` | 1330 | `cycle-readonly-banner` | `{isCompleted && (           <p             className="text-[12px] text-[var(--muted)] bg-[var(--parchment)] border borde` |
| `frontend/src/pages/DailyReview.jsx` | 421 | `review-filter-chips` | `{filterChips.length > 1 && (             <div               className="flex flex-wrap gap-1.5 mb-4"               data-t` |
| `frontend/src/pages/Decks.jsx` | 337 | `decks-history` | `{history.length > 0 && (         <section data-testid="decks-history"` |
| `frontend/src/pages/Decks.jsx` | 437 | `decks-outline-iteration-chip` | `{outline.iteration && outline.iteration > 1 && (         <div className="bg-[var(--cream-deep)]/30 border border-[var(--` |
| `frontend/src/pages/Decks.jsx` | 646 | `decks-downgraded-banner` | `{deck.quota?.downgraded && (         <div           className="bg-amber-50 border border-amber-200 rounded-sm px-4 py-3 ` |
| `frontend/src/pages/Decks.jsx` | 685 | `decks-readers` | `{engagement?.readers?.length > 0 && (           <div className="mt-4 pt-4 border-t border-[var(--rule)]" data-testid="de` |
| `frontend/src/pages/Decks.jsx` | 702 | `decks-readers-locked` | `{engagement?.readers_locked && engagement?.unique_readers > 0 && (           <div className="mt-4 pt-4 border-t border-[` |
| `frontend/src/pages/Decks.jsx` | 736 | `decks-quality-card` | `{qc && (         <div className="bg-white border border-[var(--rule)] rounded-sm p-5" data-testid="decks-quality-card"` |
| `frontend/src/pages/Decks.jsx` | 835 | `decks-feedback-recorded` | `{fb && (               <p className="text-[12px] text-[var(--muted)]" data-testid="decks-feedback-recorded"` |
| `frontend/src/pages/Decks.jsx` | 852 | `decks-regen-reason-panel` | `{showReasonChips && !fb && (           <div             className="bg-[var(--cream-deep)]/40 border border-[var(--rule)]` |
| `frontend/src/pages/HelpFeatures.jsx` | 86 | `help-features-last-modified` | `{data?.last_modified && (             <p               className="mt-3 text-sm text-stone-500"               data-testid` |
| `frontend/src/pages/HelpFeatures.jsx` | 102 | `help-features-loading` | `{loading && (           <div             className="text-stone-500"             data-testid="help-features-loading"` |
| `frontend/src/pages/HelpFeatures.jsx` | 111 | `help-features-error` | `{error && !loading && (           <div             className="rounded-md border border-red-300 bg-red-50 p-4 text-sm tex` |
| `frontend/src/pages/HelpFeatures.jsx` | 121 | `help-features-content` | `{data?.markdown && !loading && !error && (           <article             className="space-y-5 text-stone-800 leading-7"` |
| `frontend/src/pages/InboundQueue.jsx` | 185 | `inbound-queue-ctx-switcher` | `{ctxOptions.sorted.length > 1 && (         <div className="mb-5 flex flex-wrap items-center gap-2" data-testid="inbound-` |
| `frontend/src/pages/InboundQueue.jsx` | 225 | `inbound-queue-empty` | `{!loading && pendingHere.length === 0 && (           <div className="px-6 py-10 text-center" data-testid="inbound-queue-` |
| `frontend/src/pages/InboundQueue.jsx` | 242 | `inbound-queue-processed` | `{processedHere.length > 0 && (         <section className="mt-6 bg-white border border-[var(--rule)] rounded-md" data-te` |
| `frontend/src/pages/InfluenceMap.jsx` | 258 | `influence-overflow-note` | `{(peopleHidden > 0 \|\| docsHidden > 0) && (         <div className="px-3 py-2 text-[10.5px] text-[var(--muted)] border-t ` |
| `frontend/src/pages/Learn.jsx` | 162 | `learn-source-link` | `{article.source_url && (             <a               href={article.source_url}               target="_blank"           ` |
| `frontend/src/pages/Learn.jsx` | 423 | `learn-research-btn` | `{q.trim() && (                 <Button                   onClick={onResearch}                   disabled={researching}  ` |
| `frontend/src/pages/Learn.jsx` | 491 | `learn-research-empty-btn` | `{q.trim() && (                   <Button                     onClick={onResearch}                     disabled={research` |
| `frontend/src/pages/Monitor.jsx` | 199 | `monitor-overdue` | `{data.cycle?.overdue?.length > 0 && (           <div className="mb-3" data-testid="monitor-overdue"` |
| `frontend/src/pages/Monitor.jsx` | 212 | `monitor-awaiting` | `{data.cycle?.awaiting_approval?.length > 0 && (           <div className="mb-3" data-testid="monitor-awaiting"` |
| `frontend/src/pages/NewWorkspace.jsx` | 169 | `newctx-other-sector-block` | `{isOther && (                     <motion.div                       initial={{ opacity: 0, height: 0 }}                 ` |
| `frontend/src/pages/PlaysLibrary.jsx` | 62 | `plays-in-progress` | `{active.length > 0 && (           <section className="mb-12" data-testid="plays-in-progress"` |
| `frontend/src/pages/Prepare.jsx` | 245 | `prepare-line-tabs` | `{!embedded && (               <div className="border-b border-[var(--rule)] flex items-stretch gap-0" data-testid="prepa` |
| `frontend/src/pages/Prepare.jsx` | 468 | `prepare-brief-deep-quota` | `{briefQuota && (                 <span                   className="text-[10.5px] uppercase tracking-[0.14em] text-[var(` |
| `frontend/src/pages/Prepare.jsx` | 896 | `prepare-brief-continue-chat` | `{brief?.id && (               <Button                 variant="outline"                 size="sm"                 onClic` |
| `frontend/src/pages/Pulse.jsx` | 688 | `pulse-empty` | `{!loading && cards.length === 0 && (           <div className="py-16 text-center" data-testid="pulse-empty"` |
| `frontend/src/pages/Pulse.jsx` | 694 | `pulse-feed` | `{!loading && cards.length > 0 && (           <div data-testid="pulse-feed"` |
| `frontend/src/pages/Pulse.jsx` | 886 | `pulse-drawer-confidence` | `{card.confidence != null && (                 <span className="px-2 py-0.5 bg-slate-50 border border-slate-200 rounded-s` |
| `frontend/src/pages/Questions.jsx` | 148 | `question-drawer-answer` | `{isAnswered && (             <div data-testid="question-drawer-answer"` |
| `frontend/src/pages/Questions.jsx` | 159 | `question-drawer-composer` | `{!isAnswered && (             <div data-testid="question-drawer-composer"` |
| `frontend/src/pages/Questions.jsx` | 186 | `question-drawer-history` | `{(row.history \|\| []).length > 0 && (             <div data-testid="question-drawer-history"` |
| `frontend/src/pages/SearchResults.jsx` | 206 | `search-results-error` | `{err && (               <p className="px-4 py-4 text-[12px] text-red-700" data-testid="search-results-error"` |
| `frontend/src/pages/SearchResults.jsx` | 211 | `search-results-empty` | `{noResults && (               <p className="px-4 py-6 text-[12px] text-slate-600 akki-sans" data-testid="search-results-` |
| `frontend/src/pages/SharedArtefact.jsx` | 89 | `shared-loading` | `{state.loading && (           <div className="flex items-center gap-2 text-[13px] text-[var(--muted)] italic" data-testi` |
| `frontend/src/pages/SharedArtefact.jsx` | 250 | `shared-open-in-akki` | `{authed && (             <Link               to={data.kind === "deck" ? `/app/decks/${data.artefact_id}` : "/app/prepare` |
| `frontend/src/pages/SharedArtefact.jsx` | 259 | `shared-try-akki` | `{!authed && (             <Link               to="/sandbox"               className="text-[11.5px] uppercase tracking-[0` |
| `frontend/src/pages/SignUp.jsx` | 187 | `signup-error` | `{error && (               <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2.5 text-sm rounded-sm" d` |
| `frontend/src/pages/Simulate.jsx` | 398 | `simulate-stage` | `{running && stage && (                     <div className="text-[11.5px] text-[var(--deep)] italic bg-[var(--accent-soft` |
| `frontend/src/pages/Simulate.jsx` | 407 | `simulate-starters` | `{!running && hypothesis.trim().length < 10 && (                   <div className="bg-white border border-dashed border-[` |
| `frontend/src/pages/SolvaSession.jsx` | 479 | `solva-session-privacy-provenance` | `{flow.sessionId && activeContext?.id && (           <div             data-testid="solva-session-privacy-provenance"` |
| `frontend/src/pages/SynisenseObservability.jsx` | 118 | `syn-obs-error` | `{error && (           <div             data-testid="syn-obs-error"` |
| `frontend/src/pages/TenantSettings.jsx` | 566 | `export-context-btn` | `{isAdmin && (                   <Button onClick={onExport} variant="outline" className="rounded-sm h-9 border-[#E1E6ED]"` |
| `frontend/src/pages/TrustCenter.jsx` | 305 | `tc-plaintext-content` | `{text && (             <pre               data-testid="tc-plaintext-content"` |
| `frontend/src/pages/TrustCenter.jsx` | 393 | `tc-backfill-banner` | `{isBackfilled && (         <div           data-testid="tc-backfill-banner"` |
| `frontend/src/pages/TrustCenter.jsx` | 434 | `tc-by-class` | `{ps.by_class && Object.keys(ps.by_class).length > 0 && (         <div data-testid="tc-by-class"` |
| `frontend/src/pages/TrustCenter.jsx` | 502 | `tc-turn-backfill-badge` | `{t.is_backfill && (                   <span                     data-testid="tc-turn-backfill-badge"` |
| `frontend/src/pages/TrustCenter.jsx` | 693 | `tc-activity-bars` | `{data.by_class && Object.keys(data.by_class).length > 0 && (         <div data-testid="tc-activity-bars"` |
| `frontend/src/pages/TrustCenter.jsx` | 832 | `tc-intro-card` | `{showIntroCard && !introDismissed && (           <div             data-testid="tc-intro-card"` |
| `frontend/src/pages/TrustCenter.jsx` | 871 | `tc-no-chat` | `{tab === "session" && !chatId && (             <div className="text-[13px] text-[var(--muted)]" data-testid="tc-no-chat"` |
| `frontend/src/pages/WorkStudio.jsx` | 261 | `work-studio-brief-drawer-loading` | `{loading && (             <div className="text-[var(--muted)] text-sm flex items-center gap-2" data-testid="work-studio-` |
| `frontend/src/pages/WorkStudio.jsx` | 266 | `work-studio-brief-drawer-err` | `{err && (             <div className="text-amber-900 bg-amber-50 border border-amber-100 rounded-sm px-3 py-2 text-[12.5` |
| `frontend/src/pages/WorkStudio.jsx` | 307 | `work-studio-brief-drawer-cta-row` | `{detail.composer_url && (                 <div className="mb-5 pb-4 border-b border-[var(--rule)]" data-testid="work-stu` |
| `frontend/src/pages/WorkStudio.jsx` | 399 | `work-studio-brief-drawer-citations` | `{n.citations && n.citations.length > 0 && (                         <div className="mt-3 pt-2 border-t border-[var(--rul` |
| `frontend/src/pages/WorkStudioDocumentPage.jsx` | 61 | `work-studio-document-page-missing` | `{!aid && (         <div className="px-6 py-12 text-center" data-testid="work-studio-document-page-missing"` |
| `frontend/src/pages/Workspace.jsx` | 455 | `workspace-drop-overlay` | `{dragOver && (           <div             className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--accen` |
| `frontend/src/pages/Workspace.jsx` | 544 | `workspace-filter-tabs` | `{searchHits === null && (           <div             className="mb-5 flex items-center gap-1 flex-wrap border-b border-[` |
| `frontend/src/pages/Workspace.jsx` | 598 | `workspace-empty` | `{!loading && filteredRows.length === 0 && searchHits === null && tabCounts.all === 0 && (           <div className="py-1` |
| `frontend/src/pages/Workspace.jsx` | 607 | `workspace-empty-filter` | `{!loading && filteredRows.length === 0 && searchHits === null && tabCounts.all > 0 && (           <div className="py-12 ` |
| `frontend/src/pages/Workspace.jsx` | 612 | `workspace-no-search-hits` | `{!loading && filteredRows.length === 0 && searchHits !== null && (           <div className="py-12 text-center text-[var` |
| `frontend/src/pages/Workspace.jsx` | 617 | `workspace-list` | `{!loading && filteredRows.length > 0 && (           <ul className="border border-[var(--rule)] divide-y divide-[var(--ru` |
| `frontend/src/pages/admin/AuthEvents.jsx` | 92 | `auth-events-dual-mismatch-banner` | `{dualMismatch > 0 && (           <div             className="mb-8 bg-amber-50 border border-amber-200 rounded-sm px-5 py` |
| `frontend/src/pages/admin/HealthDashboard.jsx` | 104 | `health-checks` | `{data && (           <div className="space-y-2.5" data-testid="health-checks"` |
| `frontend/src/pages/admin/HealthDashboard.jsx` | 112 | `health-env` | `{data?.env && (           <div className="mt-6 text-[10.5px] text-[var(--muted)] font-mono pt-4 border-t border-[var(--r` |
| `frontend/src/pages/admin/LLMSpend.jsx` | 192 | `llm-spend-by-day` | `{(data?.by_day \|\| []).length > 0 && (           <section className="bg-white border border-[var(--rule)] rounded-sm mb-8` |
| `frontend/src/pages/admin/LLMSpend.jsx` | 223 | `llm-spend-deck-quality` | `{deckQuality && deckQuality.outlines_drafted > 0 && (           <section             className="bg-white border border-[` |
| `frontend/src/pages/admin/LLMSpend.jsx` | 265 | `llm-spend-deck-alerts` | `{deckQuality?.alerted_accounts?.length > 0 && (           <section             className="bg-amber-50 border border-ambe` |
| `frontend/src/pages/admin/LLMSpend.jsx` | 304 | `llm-spend-regen-reasons` | `{deckQuality?.top_regen_reasons?.length > 0 && (           <section             className="bg-white border border-[var(-` |
| `frontend/src/pages/admin/SignalKPI.jsx` | 149 | `signal-kpi-recent` | `{(data?.recent_actions \|\| []).length > 0 && (           <section data-testid="signal-kpi-recent"` |
| `frontend/src/pages/cycle/CycleDraftJournal.jsx` | 93 | `cycle-draft-journal-loading` | `{loading && (           <p className="text-[12.5px] text-[var(--muted)] italic" data-testid="cycle-draft-journal-loading` |
| `frontend/src/pages/cycle/CycleDraftJournal.jsx` | 98 | `cycle-draft-journal-empty` | `{!loading && drafts.length === 0 && (           <div             className="border border-dashed border-[var(--rule)] bg` |
| `frontend/src/pages/cycle/CycleDraftJournal.jsx` | 109 | `cycle-draft-journal-list` | `{!loading && drafts.length > 0 && (           <ul className="space-y-3" data-testid="cycle-draft-journal-list"` |
| `frontend/src/pages/cycle/CycleReadyJournal.jsx` | 73 | `cycle-ready-journal-loading` | `{loading && (           <p className="text-[12.5px] text-[var(--muted)] italic" data-testid="cycle-ready-journal-loading` |
| `frontend/src/pages/cycle/CycleReadyJournal.jsx` | 78 | `cycle-ready-journal-empty` | `{!loading && cycles.length === 0 && (           <div             className="border border-dashed border-[var(--rule)] bg` |
| `frontend/src/pages/cycle/CycleReadyJournal.jsx` | 90 | `cycle-ready-journal-list` | `{!loading && cycles.length > 0 && (           <ul className="space-y-3" data-testid="cycle-ready-journal-list"` |
| `frontend/src/pages/marketing/BlogAdmin.jsx` | 147 | `seed-launch-banner` | `{posts.length < 5 && (             <div className="mt-4 bg-[var(--cream-deep)]/60 border border-[var(--accent)]/20 round` |
| `frontend/src/pages/marketing/BlogAdmin.jsx` | 176 | `blog-draft` | `{draft && (           <div className="bg-white border-2 border-[var(--accent)]/30 rounded-lg p-7 mb-8" data-testid="blog` |
| `frontend/src/pages/marketing/EarlyAccess.jsx` | 198 | `ea-error` | `{error && (             <p               className="text-[13px] text-[var(--accent)]"               role="alert"        ` |
| `frontend/src/pages/ned/NedMeeting.jsx` | 326 | `ned-post-positions-list` | `{(meeting.positions \|\| []).length > 0 && (           <ul className="divide-y divide-[var(--rule)] mb-3" data-testid="ned` |
| `frontend/src/pages/ned/NedMeeting.jsx` | 396 | `ned-post-followups-list` | `{(meeting.followups \|\| []).length > 0 && (           <ul className="divide-y divide-[var(--rule)] mb-3" data-testid="ned` |
| `frontend/src/sandbox/components/Form.jsx` | 75 | `sandbox-form-page-0` | `{page === 0 && (         <div data-testid="sandbox-form-page-0"` |
| `frontend/src/sandbox/components/Form.jsx` | 103 | `sandbox-form-page-1` | `{page === 1 && (         <div data-testid="sandbox-form-page-1"` |
| `frontend/src/sandbox/components/Form.jsx` | 136 | `sandbox-form-page-2` | `{page === 2 && (         <div data-testid="sandbox-form-page-2"` |
| `frontend/src/sandbox/components/Form.jsx` | 153 | `sandbox-form-page-3` | `{page === 3 && (         <div data-testid="sandbox-form-page-3"` |
| `frontend/src/sandbox/components/Form.jsx` | 177 | `sandbox-form-error` | `{err && <p className="sb-error" data-testid="sandbox-form-error"` |


## Pattern 2 — B3 undefined-symbol-in-conditional branch

### P2 (4 sites)

| File | Line | Symbol / Testid | Excerpt |
| --- | --- | --- | --- |
| `frontend/src/components/solva/flow/QuestionScreen.jsx` | 95 | `GhostLink` | `{canBack ? (           <GhostLink` |
| `frontend/src/components/studio/SourceStep.jsx` | 257 | `Icon` | `{Icon && <Icon` |
| `frontend/src/pages/PlayView.jsx` | 283 | `StageComponent` | `{StageComponent ? (           <StageComponent` |
| `frontend/src/pages/admin/SignalKPI.jsx` | 195 | `Icon` | `{Icon && <Icon` |


## Pattern 3 — J2.3 auth-writer-without-refresh

### P0 (4 sites)

| File | Line | Symbol / Testid | Excerpt |
| --- | --- | --- | --- |
| `frontend/src/pages/FirstSession.jsx` | 99 | `/me/first-session/intake` | `api.post("/me/first-session/intake` |
| `frontend/src/pages/FirstSession.jsx` | 302 | `/me/first-session/choose-door` | `api.post("/me/first-session/choose-door` |
| `frontend/src/pages/FirstSession.jsx` | 660 | `/me/first-session/skip` | `api.post("/me/first-session/skip` |
| `frontend/src/pages/SignIn.jsx` | 32 | `/auth/login` | `api.post("/auth/login` |

### P2 (1 site)

| File | Line | Symbol / Testid | Excerpt |
| --- | --- | --- | --- |
| `frontend/src/pages/SignUp.jsx` | 61 | `/auth/register` | `api.post("/auth/register` |

