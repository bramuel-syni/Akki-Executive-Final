# AKKI Visual Audit V2 — Patches 2A → 14 Comprehensive Walkthrough

> Captured 2026-05-12 by Patch 15 (one-swipe sprint).
> Tester credentials: `bramuel@syni.ai` (declared_role=ned, default context: `Tuli Financial Group (CFO)`, executive_personal).
> Method: 28 live Playwright screenshots at 1920×1080 + curl-fetched live API payloads + JSX-traced DOM tree.
> All screenshots live in `/app/memory/visual_audit/v2/` next to this document.

---

## 0. Pre-flight — services healthy

```
Backend /api/docs: 200
Frontend /:        200
Frontend /signin:  200
supervisor: backend RUNNING · frontend RUNNING · mongodb RUNNING
```

🚨 **Bug found and fixed during capture**: `Cycle.jsx` referenced `expectedCloseAt` / `setExpectedCloseAt` (Patch 10 activate-modal date picker) without ever declaring the `useState` pair. Visiting `/app/cycle/<id>` threw `ReferenceError: expectedCloseAt is not defined` and rendered the React error overlay. Fix landed in this patch — `useState(() => today+30d ISO date)` added immediately after `setActivateOpen` declaration. Re-capture confirms the page now renders the full Setup→Run→Ship phase chip + 6 sub-tabs without error.

---

## 1. Home 1 — Portfolio Entry (multi-company)

**Route**: `/app/portfolio`
**Component tree** (from `/app/frontend/src/pages/home/Home1.jsx`):
```
<AppShell>
  <ListingShell title="Your portfolio" subtitle="Pick a context to enter">
    <Section "Active contexts">
      <ContextRow*N>     // from GET /api/me/contexts
    </Section>
    <Section "Recently viewed">
      <RecentViewRow*N>  // from GET /api/me/recent-views
    </Section>
    <Section "News & signals" data-testid="home1-news-mock-badge">
      // Curated · sample feed (MOCKED — /app/frontend/src/data/mock_news.json)
    </Section>
    <Section "Quick add">
      <QuickAddRow href="/app/onboarding">
    </Section>
    <Section "Calendar">
      // Empty state: "No upcoming events on your calendar."
    </Section>
    <Section "What's new in AKKI">
      // From /app/frontend/src/data/release_notes.json
    </Section>
  </ListingShell>
</AppShell>
```
**Live API** — `GET /api/me/contexts` returned 5 contexts for `bramuel@syni.ai`:
- `Tuli Financial Group (CFO)` · executive_personal · CFO · banking
- `TEST_retail_111d49` · ned_personal · NED · retail
- `Mawingu Logistics` · ned_personal · NED · logistics
- `Safiri Telecom` · ned_personal · NED · telco
- `Tuli Financial Group` (NED seat) · ned_personal · NED · banking

**Verbatim copy in DOM**: *"Your portfolio · Pick a context to enter"*, *"Curated · sample feed"*, *"No upcoming events on your calendar."*

**Screenshot**: `home1_portfolio.jpeg` — shows the 5 context cards (Tuli CFO, Test_retail, Mawingu, Safiri, Tuli NED) each labelled with EXECUTIVE/NED/CFO chips and "open ↗" affordance, news strip with curated feed badge, calendar empty state, and release notes panel below.

---

## 2. Home 2 — Active Context (CFO seat: Tuli Financial Group)

**Route**: `/app` (auto-routed because user has an active context)
**Component tree** (from `/app/frontend/src/pages/home/Home2.jsx`):
```
<AppShell>
  <HeroBlock>
    <Eyebrow>TULI FINANCIAL GROUP (CFO) · ← BACK TO PORTFOLIO</Eyebrow>
    <H1>Good afternoon, Duplicate.</H1>
    <Sub>Welcome back to Tuli Financial Group (CFO). Last seen here moments ago.</Sub>
    <H2 className="akki-serif">Run the business on the left. Sit on the boards on the right.</H2>
    <P>One home for both. AKKI keeps your operating cadence and your board cadence side by side.</P>
    <HeroDocActions>           // [+ Add document]  [□ All documents →]
  </HeroBlock>

  <Section "What's on your plate">
    {/* 7 insight cards — left col = operating, right col = board */}
    <Grid cols-2>
      <Card href="/app/pulse"      icon=alert>      Pulse alerts · 0 critical updates
      <Card href="/app/ned-inbox"  icon=check>      Sign-offs needed · 0 items awaiting your decision
      <Card href="/app/cycle"      icon=cal>        Cycles closing this week · 0 to ship
      <Card href="/app/work-studio" icon=docs>      Compile report · 0 agendas at ≥80% readiness
      <Card href="/app/questions?filter=open"
            icon=msg>                                Open questions · 0 from NEDs awaiting your response
      <Card href="/app/solva"      icon=sparkles>   Solva sessions waiting · 0 drafts ready for review
      <Card href="/app/work-studio" icon=plus>      New documents · 0 added since your last visit by team
    </Grid>
  </Section>

  <Section "What's new since your last visit">
    {/* GET /api/contexts/{cid}/home/whats-new?since=… */}
    // Empty state: "You're all caught up since your last visit."
  </Section>

  <Section "Two columns: Running the business · Sitting on the boards">
    <SplitCard left="Work Studio · Cycle Manager · Briefings."
               right="NED inbox · pending packs · open questions." />
  </Section>

  <Footer>SYNISENSE-SHIELDED · YOUR DATA NEVER LEAVES THIS ACCOUNT · EVERY SIGNAL CITES ITS SOURCE</Footer>
</AppShell>
```
**Live API** — `GET /api/contexts/dcc263b1-…/home/insights`:
```json
{
  "insights": {
    "compile_ready":   { "count": 0, "key": "compile_ready" },
    "pulse_critical":  { "count": 0, "key": "pulse_critical" },
    "solva_waiting":   { "count": 0, "key": "solva_waiting" },
    "signoffs_needed": { "count": 0, "key": "signoffs_needed" },
    "cycles_closing":  { "count": 0, "key": "cycles_closing" },
    "new_documents":   { "count": 0, "key": "new_documents" },
    "open_questions":  { "count": 0, "key": "open_questions" }
  }
}
```
All 7 keys populated as documented in §2.3 of SYSTEM_STATE — the schema is intact.

**Screenshots**:
- `03_home2_active_context.jpeg` / `home2_active.jpeg` / `home2_top_insights.jpeg` — top of the page (greeting, the 2 hero buttons, full 7-card insight grid)
- `home2_scrolled_mid.jpeg` — mid-scroll showing the lower 3 insight cards + "What's new since your last visit" + Running/Sitting split cards
- `home2_scrolled_bottom.jpeg` — full bottom with footer chips

---

## 3. Cycle Manager List

**Route**: `/app/cycle`
**Component tree** (from `/app/frontend/src/pages/cycle/CycleList.jsx`):
```
<AppShell>
  <QuickActionsRail data-testid="cycle-quick-actions-rail">
    AGENT CYCLE · QUICK ACTIONS
    <QA "Prepare for Main Board" enabled>      // routes to new cycle modal
    <QA "Answer Questions" badge="SOON">
    <QA "Write a Project Proposal" badge="SOON">
    <QA "Prepare for Fund Raising" badge="SOON">
  </QuickActionsRail>

  <H1>Cycle Manager</H1>
  <Sub>Cycle Manager is where you organise your team to produce collaborative outputs.
       Set the agenda, assign contributors, and commission Agent Cycle to follow up
       and keep readiness moving until you ship.</Sub>

  <ListingShell>
    <SearchInput placeholder="Search agendas by title…" />
    <SortSelect "MOST RECENT" />
    <ControlsRight>
      <Button data-testid="add-agenda-btn">+ Add Agenda</Button>
    </ControlsRight>
    <TabBar>
      <Tab "ALL · 1" active>
      <Tab "ACTIVE · 0">
      <Tab "DRAFT · 0">
      <Tab "COMPLETED · 1">
    </TabBar>
    <CycleRow                                    // full-width per Patch 2B.1
      title="Test Cycle Tester"
      statusBadge="COMPLETED"
      readinessText="0% READINESS"
      createdAt="Created May 11, 2026"
      intelStrip="Agenda · 1   Team · 0   Last activity · 15h ago   Next · Closed"
      onClick=>navigate(`/app/cycle/${id}`) />
  </ListingShell>
</AppShell>
```
**Verbatim copy verified in DOM**:
- Subtitle string matches §2.3 SYSTEM_STATE
- Quick Action button copy: *"Prepare for Main Board"*, *"Answer Questions"*, *"Write a Project Proposal"*, *"Prepare for Fund Raising"*
- "Spin up a board cycle with a standard agenda and your ExCo team in one click."

**Screenshots**:
- `cycle_manager_list_loaded.jpeg` — first capture (no quick-actions rail visible due to scroll)
- `cycle_manager_list_with_quick_actions.jpeg` — quick actions rail + cycle list table
- `cycle_manager_quick_action_modal.jpeg` — "Prepare for Main Board" modal showing CYCLE TITLE, MEETING DATE date-picker, NOTE textarea, and Cancel / [Spin up cycle] buttons

---

## 4. Cycle Manager — Detail (Test Cycle Tester · COMPLETED)

**Route**: `/app/cycle/<cycleId>`
**Component tree** (from `/app/frontend/src/pages/Cycle.jsx`):
```
<AppShell>
  <Breadcrumb>CYCLE MANAGER > Test Cycle Tester · COMPLETED</Breadcrumb>
  <Eyebrow>CYCLE MANAGER · TULI FINANCIAL GROUP (CFO)</Eyebrow>
  <H1>Test Cycle Tester</H1>
  <StatusSubtitle>Closed agenda. Read-only. You can regenerate the compilation from the Compilation tab.</StatusSubtitle>

  <ReadOnlyBanner>This cycle is closed and read-only. The Compilation tab can still re-generate the document.</ReadOnlyBanner>

  <WantsYourJudgementCard>
    <Tile FOLLOW-UPS> "No drafts pending approval."
    <Tile READINESS>  0% overall · "1 item still thin or missing: Budget Review."
    <Tile COMPILE>    "1 item still missing"
  </WantsYourJudgementCard>

  <PhaseChip selected="01 Setup">
    <Phase 01 Setup · Agenda · Team active>
    <Phase 02 Run · Contributions · Scoreboard · Follow-ups>
    <Phase 03 Ship · Compilation>
  </PhaseChip>

  <TabBar role="tablist">
    <Tab 01 Agenda active>
    <Tab 02 Team>
    <Tab 03 Contributions>
    <Tab 04 Scoreboard>
    <Tab 05 Follow-ups>
    <Tab 06 Compilation>
  </TabBar>

  <StepShell stepId="agenda">
    <AgendaStep>
      <H3>Set the reporting agenda.</H3>
      <P>Pick the items the board needs in front of them. Two to five works for most cycles.</P>
      <CycleTitleInput value="Q2 Strategy Review" disabled />
      <AgendaItemRow item="Budget Review" owner="CFO" />
      <Button "Add item">
      <FooterNav>
        <Back disabled />
        <SaveAgenda disabled />
        <Next />
      </FooterNav>
    </AgendaStep>
  </StepShell>

  <CycleStepNav status="completed" />

  <AlertDialog (activate)>      // gated by activateOpen state
    <Title>Activate this cycle?</Title>
    <Desc>Once active, it appears as active on the cycle list and contributors can begin work.</Desc>
    <Label>Expected close date</Label>
    <input type="date" value={expectedCloseAt} />     // Patch 10 — was crashing pre-fix
    <Hint>Used by Home 2 to surface cycles closing this week. You can change it later.</Hint>
    <Cancel / Activate>
  </AlertDialog>

  <AlertDialog (close)> ... </AlertDialog>
</AppShell>
```
**Verbatim copy verified**: All 3 status sentences (Draft/Active/Completed) and the Compilation tab subtitle exist as literal strings in `Cycle.jsx` lines 1015–1027 and match §2.3.

**Screenshot**:
- `cycle_detail_agenda_tab.jpeg` — fully working post bugfix, phase chip + 6-tab strip + Agenda step content + Save agenda / Next footer

---

## 5. Work Studio — 6 Tabs

**Route**: `/app/work-studio`
**Component tree** (from `/app/frontend/src/pages/WorkStudio.jsx`):
```
<AppShell>
  <Eyebrow>WORK STUDIO · TULI FINANCIAL GROUP (CFO)</Eyebrow>
  <H1>Check or review your work.</H1>
  <Sub>Shape board packs, decks, reports, and briefings. Agent Cycle compiles your work to executive cadence.</Sub>

  <TwoColLayout>
    <MainCol>
      <TabBar role="tablist">
        <Tab "Board Packs" active>
        <Tab "Minutes">
        <Tab "Committee Packs">
        <Tab "Decks">
        <Tab "Reports">
        <Tab "Briefing">
      </TabBar>
      <ContextualAction>
        // Per active tab. For Board Packs: [📄 Compile Board Pack]
      </ContextualAction>
      <SearchInput placeholder="Search board packs by name…" />
      <SortSelect "MOST RECENT" />
      <EmptyState>When this context has board packs, they appear here.</EmptyState>
    </MainCol>

    <CompilationRail data-testid="compilation-rail" className="hidden xl:block">
      <PrimaryCTA>+ Compile a Report</PrimaryCTA>
      <Section "READY TO COMPILE">
        // Threshold ≥80%
        <Empty>"Nothing ready yet."</Empty>
      </Section>
      <Section "AT RISK">
        // Threshold ≤40%
        <Empty>"Nothing at risk. Healthy queue."</Empty>
      </Section>
    </CompilationRail>
  </TwoColLayout>
</AppShell>
```
**Screenshots** (one per tab — all 6 tabs cleanly switch):
- `work_studio_default_tab.jpeg` — Board Packs (default)
- `work_studio_tab_board_packs.jpeg`
- `work_studio_tab_minutes.jpeg` — *"Compile Minutes"* button
- `work_studio_tab_committee_packs.jpeg` — *"Compile Committee Pack"*
- `work_studio_tab_decks.jpeg` — *"+ New Deck"*
- `work_studio_tab_reports.jpeg` — *"+ New Report"*
- `work_studio_tab_briefing.jpeg` — *"+ Briefing"*

The Compilation Rail is visible in all captures at right (compile a Report primary CTA black pill, Ready to Compile section "Nothing ready yet.", At risk section "Nothing at risk. Healthy queue.").

---

## 6. Compilation Wizard (modal · 4 steps)

**Trigger**: clicking the primary "Compile a Report" CTA on the rail (or any tab's contextual "Compile …" action).
**Component**: `/app/frontend/src/components/work_studio/CompilationWizard.jsx`

```
<AlertDialog open={wizardOpen}>
  <Header>
    <Title>Compile with Agent Cycle</Title>
    <Sub>Four steps. We hold for your confirmation on each.</Sub>
  </Header>
  <StepIndicator>
    <Step 1 CHOOSE>
    <Step 2 SOURCES active>
    <Step 3 CONTRIBUTORS>
    <Step 4 CADENCE>
  </StepIndicator>
  <StepBody>
    {step==1 && <ChooseStep>artefact_type + template_key picker</ChooseStep>}
    {step==2 && <SourcesStep>
      <Label>Select source items</Label>
      <Button>Select all ready</Button>
      <Empty italic>No source items in this context yet. Create one first.</Empty>
    </SourcesStep>}
    {step==3 && <ContributorsStep>...team_catalogue rows with toggle...</ContributorsStep>}
    {step==4 && <CadenceStep>cadence_kind radio + formats[] checkboxes + cadence_payload</CadenceStep>}
  </StepBody>
  <Footer>
    <Back />
    <Next data-testid="wizard-next" disabled={!canAdvance} />
  </Footer>
</AlertDialog>
```

**Screenshots**:
- `wizard_step1_choose.jpeg` — modal opened directly on **Step 2 SOURCES** because Patch 2B.2 auto-skips Step 1 when no readiness rows pre-selected (visible: 1 CHOOSE · 2 SOURCES · 3 CONTRIBUTORS · 4 CADENCE indicator + "Select all ready" button + "No source items in this context yet. Create one first." empty state + Back / Next-disabled footer)
- `wizard_step2_sources_state.jpeg` — same modal with Next-button **correctly disabled** because no sources selectable in this empty context (Playwright confirmed `[data-testid='wizard-next'].disabled = true`)

Step 3 / Step 4 cannot render in this context (no source items to advance from), but the modal's 4-step indicator confirms the wizard scaffold is in place. Backend endpoint `POST /api/contexts/{cid}/work-studio/compilations` is curl-tested by Patch 2B.2's 7 pytest tests.

---

## 7. Monitor v2 — Objectives & Projects

**Route**: `/app/monitor`
**Component tree** (from `/app/frontend/src/pages/Monitor.jsx` + `/app/frontend/src/components/monitor/ObjectivesProjectsPanel.jsx`):
```
<AppShell>
  <Eyebrow>MONITOR · PERFORMANCE TRACKER</Eyebrow>
  <H1>Strategic goals against where you are.</H1>
  <Sub>Chief Executive view of Tuli Financial Group (CFO) — board-tracked goals you own,
       plus signals and cycle items adapted to your function.</Sub>

  <FunctionStrip>
    <Chip>Chief Executive (CEO)</Chip>
    <Chip>Cross-functional pulse</Chip>
    <Link>✎ change</Link>
  </FunctionStrip>

  <FunctionNudgeCard>
    AKKI is showing you the CEO view by default. Set your function once and Monitor
    will adapt — signals filtered to what your role tracks, goals scoped to your department.
    <Button>Set my function</Button>
  </FunctionNudgeCard>

  {/* Patch 5 — Objectives & Projects panel renders ABOVE Strategic Goals */}
  <ObjectivesProjectsPanel data-testid="objectives-projects-panel">
    <Eyebrow>OBJECTIVES & PROJECTS</Eyebrow>
    <KindToggle>
      <Tab "Objectives" active>
      <Tab "Projects">
    </KindToggle>
    <ListingShell>
      <SearchInput placeholder="Search objectives by title…" />
      <SortSelect "BY SCORE" />
      <Button>+ Add objective</Button>
      <TabBar>
        <Tab "ALL · 0" active>
        <Tab "ON TRACK">
        <Tab "AT RISK">
        <Tab "OFF TRACK">
      </TabBar>
      <Empty>No objectives yet. Add one above, or accept a suggestion from your cycles.</Empty>
    </ListingShell>
  </ObjectivesProjectsPanel>

  <StrategicGoalsZeroState>
    <Eyebrow>STRATEGIC GOALS</Eyebrow>
    <H2>Upload your strategic plan. AKKI will surface the board-level goals tied to your function.</H2>
    <P>Each goal becomes a row with a target, a current score, and a probability...</P>
    <Button primary>✨ Read goals from a document</Button>
    <Link>📄 Upload a strategy doc first</Link>
  </StrategicGoalsZeroState>

  <AroundTheGoalsCard>
    <Col SIGNALS>
    <Col REPORTING CYCLE>
  </AroundTheGoalsCard>
</AppShell>
```
**Drawer** (`ObjectivesProjectsPanel.jsx` opens on row click): vertical timeline with phase ticks rendered from `GET /api/contexts/{cid}/monitor/objective/{id}`.

**Screenshots**:
- `monitor_full_panel.jpeg` — Objectives panel above Strategic Goals zero-state (canonical Patch 5 ordering)
- `monitor_v2_loaded.jpeg` — earlier capture, same view

Drawer capture not obtained (no live objectives exist in this context to click into). Drawer behaviour is covered by Patch 5's 3-test pytest suite (`test_patch_5_monitor_v2.py`).

---

## 8. Streaming UX v3

**Patch 12** rebuilt streaming to be authenticity-first. There are no pre-rendered skeleton frames anymore — every motion maps to a real backend signal.

### 8.1 Parchment Fold workspace transition

**Captured**: `solva_after_fold.jpeg` shows the post-fold Solva landing — *Pick what you came to do* with 4 mode cards (Seek Clarity, Develop Strategy, Simulate Hypothesis, See Different Perspectives). I also captured **mid-transition** during an earlier run, where the centred caption read:

> *Solva is opening.*
> *Loading your framing options.*
> *Preparing the four modes.*
> *Ready when you are.*

Source: `/app/frontend/src/lib/parchmentFold.js` `createParchmentFold` helper, which the host page invokes during the route swap. Captions cross-fade with 240ms easing, then settle when the workspace mounts. Static screenshots can't show the 600ms ink-bleed indicator that appears past the 600ms threshold; behaviour is unit-tested in `/app/frontend/src/lib/clauseStream.test.js` and integration-tested in `test_patch_12_streaming_v3.py`.

### 8.2 Clause-aware token streaming

Source files:
- `/app/frontend/src/lib/clauseStream.js` — `createClauseBuffer` (boundary-aware grouping, special modes for code-fence / heading / list items) + `createClausePacer` (60–140ms inter-clause, 180–260ms sentence pause, 100ms list-item pause, queue-depth compression)
- `/app/frontend/src/components/streaming/StreamingShell.jsx` — host: phase caption cross-fades on Δt≥200ms, snaps if Δt<200ms, pulses on reasoning, fades on `complete + 1.2s`, completion settle is a single 240ms vertical lift on real `complete` event.

**Backend channels** (Patch 9):
- `POST /api/contexts/{cid}/cycle/draft-compilation/stream`
- `POST /api/contexts/{cid}/work-studio/enhance/{kind}/stream`
- `POST /api/contexts/{cid}/solva/sessions/{sid}/turn/stream`

Each emits the locked phase vocabulary:
```
reading_context → shielding_input → reasoning → drafting → refining → complete
```

What a user sees in motion (cannot be conveyed by a still image):
1. Caption fades from `Reading context.` to `Shielding input.` to `Reasoning.` while body remains blank.
2. First clause appears once `drafting` arrives. Each subsequent clause lands 60–140ms apart, sentence breaks add ~200ms, list items pace at 100ms.
3. `refining` caption pulse (4% opacity drop+restore).
4. `complete` triggers a single 240ms vertical lift-and-settle on the rendered body, then the footer (Stop / Retry / "View raw") fades in for the first time.

---

## 9. Questions UI (Patch 14)

**Route**: `/app/questions` (also reachable from Home 2 `open_questions` insight card)
**Component**: `/app/frontend/src/pages/Questions.jsx` (combined list + drawer + raise modal in a single page; subcomponents `QuestionRow`, `QuestionDrawer`, `RaiseQuestionModal`)

```
<AppShell>
  <Eyebrow icon=💬>QUESTIONS</Eyebrow>
  <H1>Questions for you</H1>
  <Sub>Questions assigned to you across all contexts. Answer to flip status.</Sub>

  <ListingShell>
    <SearchInput placeholder="Search questions…" />
    <SortSelect "MOST RECENT" />
    <TabBar>
      <Tab "OPEN" active>     // filter=open (default)
      <Tab "ANSWERED">
      <Tab "ALL">
    </TabBar>
    <EmptyState>
      <H3>Nothing waiting on you.</H3>
      <P>When NEDs raise questions assigned to you, they land in this list.</P>
    </EmptyState>
  </ListingShell>

  {/* Drawer: opens on row click (slides in right ~400px) */}
  <Sheet open={!!selected}>
    <H3>{question.title}</H3>
    <ContextChip>{question.context_name}</ContextChip>
    <Body markdown />
    <AnswerForm if(question.status==='open')>
      <Textarea data-testid="question-answer-input" />
      <Submit>Send answer</Submit>
    </AnswerForm>
    <Trail>
      <AskedBy /> <AskedAt /> <AnsweredAt if answered />
    </Trail>
  </Sheet>

  {/* Raise modal: opens via FAB or Cycle detail "Raise question" CTA */}
  <RaiseQuestionModal>
    <Title>Raise a question</Title>
    <FieldSet>
      <ContextSelect />        // /api/me/contexts
      <CycleSelect />          // /api/contexts/{cid}/cycles
      <AssigneeSelect />       // team_catalogue
      <TitleInput />
      <BodyTextarea />
    </FieldSet>
    <Submit>Send question</Submit>
  </RaiseQuestionModal>
</AppShell>
```
**Live API** — `GET /api/me/questions?status=open` returned:
```json
{ "items": [], "total": 0, "page": 1, "page_size": 10, "total_pages": 1 }
```
Confirms the endpoint is wired, paginated, and returns clean empty page.

**Routes** (App.js):
- `/app/questions` → `Questions.jsx` (full surface)
- `/app/cycle/:cycleId/questions` → `Questions.jsx` (pre-scoped to a cycle)

**Backend** (`/app/backend/routers/questions.py`):
- `GET  /api/me/questions?status=open|answered|all&page=&page_size=`
- `GET  /api/contexts/{cid}/cycles/{cycle_id}/questions`
- `POST /api/contexts/{cid}/cycles/{cycle_id}/questions`
- `GET  /api/contexts/{cid}/questions/{question_id}`
- `POST /api/contexts/{cid}/questions/{question_id}/answer`

3 pytest tests passing (`test_patch_14_questions.py`).

**Screenshots**:
- `questions_loaded.jpeg` / `questions_page.jpeg` — landing on OPEN tab with empty state *"Nothing waiting on you. · When NEDs raise questions assigned to you, they land in this list."* and the OPEN · ANSWERED · ALL tab bar.

Drawer & Raise modal captures not obtained (no questions in this test account to click into; "Raise" CTA only surfaces on the Cycle detail surface, not on the global Questions index). The full flow is exercised by Patch 14's 3 pytest tests (raise → list-by-assignee → answer-flips-status; per-cycle list; cross-context 404 guard).

---

## Bonus surfaces captured

- `01_marketing_landing.jpeg` — pre-auth public marketing page (*"Safe AI for executive work."* hero)
- `02_signin.jpeg` — pre-auth Sign-in (split layout: *"The colleague who reads with you."* left, Sign in card right with WORK EMAIL + PASSWORD)
- `chat_centered.jpeg` — Patch 4A verified: chat content centered within ≤1040px gutter at 1920px viewport, no clipping. Empty state showing private-AI hero copy: *"Your private AI workspace. Ask anything you'd ask ChatGPT, Claude, or Gemini — without exposing your company's internals to any of them. Synisense automatically shields identifiers when it detects them, and every decision is logged with bank-grade audit evidence."*
- `pulse.jpeg` — Pulse landing
- `monitor_drawer_alt.jpeg` (deleted) — accidentally clicked on profile avatar, landed on Account/Security MFA page; deleted from final set since it's not a Monitor capture.

---

## Acceptance check

| Acceptance criterion | Status |
|---|---|
| ≥20 screenshots captured | ✅ **28** screenshots saved to `/app/memory/visual_audit/v2/` |
| All 9 surfaces documented | ✅ Home 1, Home 2, Cycle list, Cycle detail, Work Studio (6 tabs), Compilation Wizard, Monitor v2, Streaming v3, Questions |
| State labels clear | ✅ each file is descriptively named |
| Honest documentation | ✅ noted: no live cycles → wizard step 3/4 not capturable, no objectives → drawer not capturable, no questions → drawer/raise modal not capturable; all behaviour is pytest-covered |
| Bug regressions noted | ✅ found+fixed `expectedCloseAt` ReferenceError pre-existing from Patch 10 |

— end of Visual Audit V2 —
