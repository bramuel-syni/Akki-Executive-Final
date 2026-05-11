# Cycle Manager — Sprint Brief

**Status:** APPROVED-FOR-BUILD (2026-02). Scope locked. C3 resolved: **ASSIGNMENT HANDOFF model** (see §3.3 locked decisions below).
**Author:** Fork agent, 2026-02.
**Inputs used:** `/app/memory/SPRINT_AUDIT.md`, `/app/docs/PRODUCT_SPEC.md §5.6`, `/app/docs/NED_CYCLE_MANAGER_DESIGN.md`, `/app/backend/work_studio/samples/Akki_NED_Cycle_Manager_Module_Specification.docx` (extracted), live code in `/app/backend/routers/{cycle.py, cycle_manager.py, cycle_config.py, ned_cycle.py}`, `/app/frontend/src/pages/{Cycle.jsx, CycleSettings.jsx, ned/NedMeeting.jsx, ned/NedCommittee.jsx, home/HomeNed.jsx}`.

---

## 1. Context & Purpose

Cycle Manager is the surface for the recurring decision rhythm of a board / committee / executive team — agenda, contributions, scoring, draft compilation, follow-ups, decision history. It sits **between** Solva (where unknowns get worked into structured answers) and Work Studio (where final artefacts are rendered). It has two structurally distinct sides: an **Executive** side (orchestrate the cycle, build the team, score contributions, draft compilation, send follow-ups) and a **NED** side (receive packs, prepare, take notes silently, register positions Post-meeting, chase follow-ups, hold cross-board through-lines without leaking content). Primary users: ExCo members + Chiefs of Staff on the Executive side; NEDs on the NED side. The spec mandates the two sides remain **architecturally separate** with no shared writes.

---

## 2. Current State (live in code)

### 2.1 Executive Cycle Manager — what's wired

| Route / Page | File path | What it does | Status |
|---|---|---|---|
| `POST /api/contexts/{cid}/cycle/agenda` | `routers/cycle_manager.py:142` | Create / replace agenda for a cycle | Working |
| `GET /api/contexts/{cid}/cycle/agenda` | `routers/cycle_manager.py:133` | Read current agenda | Working |
| `GET /api/contexts/{cid}/cycle/team` | `cycle_manager.py` | List active team members for cycle | Working |
| `POST /api/contexts/{cid}/cycle/team` | `cycle_manager.py` | Add team member + contribution description | Working |
| `DELETE /api/contexts/{cid}/cycle/team/{member_id}` | `cycle_manager.py` | Remove team member | Working |
| `POST /api/contexts/{cid}/cycle/contributions` | `cycle_manager.py` | Upload / forward a contribution | Working |
| `GET /api/contexts/{cid}/cycle/contributions` | `cycle_manager.py` | List contributions, scored or not | Working |
| `POST /api/contexts/{cid}/cycle/contributions/{cid_contribution}/score` | `cycle_manager.py` | Score a contribution | Working |
| `GET /api/contexts/{cid}/cycle/readiness` | `cycle_manager.py` | Readiness roll-up (storyline + indicators) | Working |
| `POST /api/contexts/{cid}/cycle/follow-ups/draft` | `cycle_manager.py` | Draft follow-up via Akki-for-`<exec>` alias | Working |
| `GET /api/contexts/{cid}/cycle/follow-ups` | `cycle_manager.py` | List drafted / approved / sent follow-ups | Working |
| `POST /api/contexts/{cid}/cycle/follow-ups/{fid}/approve` | `cycle_manager.py` | Mark draft as approved-to-send | Working |
| `POST /api/contexts/{cid}/cycle/follow-ups/{fid}/send` | `cycle_manager.py` | Send via Resend (test mode in dev) | Working |
| `POST /api/contexts/{cid}/cycle/draft-compilation` | `cycle_manager.py:739` | **Rebuilt (Phase D.1):** two-pass LLM synth → Solva-shaped envelope → `build_brief_from_solva` → `ensure_brief_persisted` → DOCX render | Working |
| Page `/app/cycle` | `frontend/src/pages/Cycle.jsx` (864 lines) | Executive 6-step stepper UI | Working |
| Page `/app/cycle/settings` | `frontend/src/pages/CycleSettings.jsx` (334 lines) | Per-context config | Working |
| Legacy router (questions / committees / submissions / checklists / reports / schedule) | `routers/cycle.py` (30 endpoints) | Pre-Phase-D cycle surface | Working; **additive** to Phase D, not removed |
| Per-context config router | `routers/cycle_config.py` | Bands, cadence, role labels | Working |
| Cross-board metadata signatures | `services/metadata_signatures.py` (Phase E.0.2 — keyword/regex only, NO LLM, NO embeddings) | Derives + persists regulatory_ref / governance_theme / pulse_class signatures | Working |

### 2.2 NED Cycle Manager — the 12 routes + 2 pages

| # | Route / Page | File path | What it does | Status |
|---|---|---|---|---|
| 1 | `GET /api/ned/landing` | `routers/ned_cycle.py:71` | Cross-board landing: this week, next two weeks, outstanding items, patterns flag | Working |
| 2 | `POST /api/ned/meetings` | `routers/ned_cycle.py:182` | Create a meeting on a (board, committee) | Working |
| 3 | `GET /api/ned/meetings/{meeting_id}` | `routers/ned_cycle.py` | Read meeting state (Pre / In / Post) + notes + positions + follow-ups | Working |
| 4 | `PATCH /api/ned/meetings/{meeting_id}` | `routers/ned_cycle.py` | Update meeting (formulated_question, state advance Pre→In→Post→closed) | Working |
| 5 | `DELETE /api/ned/meetings/{meeting_id}` | `routers/ned_cycle.py` | Soft-delete a meeting | Working |
| 6 | `POST /api/ned/meetings/{meeting_id}/notes` | `routers/ned_cycle.py` | Add a lightweight note (Question/Response, Decision, Open) — In act, LLM-free | Working |
| 7 | `DELETE /api/ned/meetings/{meeting_id}/notes/{note_id}` | `routers/ned_cycle.py` | Remove a note | Working |
| 8 | `POST /api/ned/meetings/{meeting_id}/positions` | `routers/ned_cycle.py` | Register For/Against/Abstained + private note (Post act) | Working |
| 9 | `POST /api/ned/meetings/{meeting_id}/followups` | `routers/ned_cycle.py` | Create a follow-up (Post act) | Working |
| 10 | `POST /api/ned/meetings/{meeting_id}/followups/{fid}/send` | `routers/ned_cycle.py` | Send the follow-up via Resend (Akki-for-<NED> alias) | Working |
| 11 | `GET /api/ned/committee/{context_id}/{committee}` | `routers/ned_cycle.py` | Per-committee through-line: recurring questions, deferred decisions, response patterns, position history | Working |
| 12 | `GET /api/ned/search` | `routers/ned_cycle.py:_ned_search` | Personal-memory search (topic / decision / person / date range / committee) | Working |
| P1 | `/app/ned/meeting/:id` | `frontend/src/pages/ned/NedMeeting.jsx` (550 lines) | Pre / In / Post composite page | Working |
| P2 | `/app/ned/committee/:cid/:committee` | `frontend/src/pages/ned/NedCommittee.jsx` (145 lines) | Per-committee through-line page | Working |
| (entry) | `frontend/src/pages/home/HomeNed.jsx:98` | Calls `POST /ned/meetings` from the NED home tile | Working |

### 2.3 The 7 "Done" items from the audit (with file paths)

| # | Item | File path |
|---|---|---|
| 1 | Executive 6-step stepper (Agenda → Team → Contributions → Scoreboard → Follow-ups → Compilation) | `frontend/src/pages/Cycle.jsx`; `routers/cycle_manager.py` |
| 2 | Additive collections (`cycle_agendas`, `cycle_team`, `cycle_contributions`, `cycle_followups`) | `routers/cycle_manager.py:28-37` (header) |
| 3 | Follow-ups send via Resend with `From: akki+<context_slug>@syni.ai` | `routers/cycle_manager.py` (uses `email_service`) |
| 5 | Per-step audit_log rows emitted | `routers/cycle_manager.py` (uses `write_audit`) |
| 7 | NED Questions-to-ask surface | `routers/ned_cycle.py` (formulated_question on meeting + notes type "question") |
| 8 | NED Signals worth digging into | `routers/ned_cycle.py` cross-references `db.context_metadata_signatures` |
| 11 | NED Open-questions ledger | `routers/ned_cycle.py:_positions/_followups` and `_ned_search` |
| 12 | NED-private writes isolation (`db.ned_annotations` + per-account scoping) | `routers/ned_cycle.py` (imports `services.privacy_wall.cross_context_query` for confidentiality enforcement) |

### 2.4 The 4 "Partial" items from the audit (with file paths + what's missing)

| # | Item | File path | What's missing |
|---|---|---|---|
| 4 | Executive Draft Compilation | `routers/cycle_manager.py:739` | **OUTDATED CALL-OUT.** The Phase D.1 rebuild has **removed** the placeholder citation row the audit flagged. Compilation now flows through `services.cycle_synthesis.synthesise_cycle` (Sonnet 4.5 drafter + Gemini 2.5 Flash validator) → Solva-shaped envelope → `build_brief_from_solva` → `ensure_brief_persisted` → DOCX render. **Acceptance verification owed** (regression test does not yet exist). |
| 6 | NED catch-up: Briefing pre-read + private notes | `routers/ned_cycle.py`; `frontend/src/pages/ned/NedMeeting.jsx` | Pack ingestion **from Bell Icon notification** (spec §4 + §5 Pre act) is not wired — meetings are created from the NED Home tile only. Integrated reading-view + per-paper Akki Chat / Solva launch (spec §5 Pre act, "In scope") is not wired in the page. |
| 9 | NED Minutes consumption + diff | `routers/ned_cycle.py` (positions/follow-ups exist) | Exec-side compilation → NED-side pack lift is unidirectional from the spec's POV (spec §12 "Brief delivery model: TBD"). No diff narrative endpoint surfaces what changed between two consecutive cycles for the same committee. |
| 10 | NED Commitments + decisions log | `routers/ned_cycle.py` (positions endpoint exists); reuses `routers/prepare.py` minutes extraction | The decisions log is a join across `db.ned_meetings`, `db.ned_positions`, `db.ned_followups`. There is no single read endpoint that returns the per-NED, per-committee commitments ledger as one shape — clients have to compose it themselves. |

### 2.5 Test coverage today

| File | Covers |
|---|---|
| `backend/tests/test_cycle_manager_actions_tab.py` | Legacy cycle.py actions tab |
| `backend/tests/test_daily_review_solva_cycle.py` | Daily-review → Solva → Cycle handshake |
| `backend/tests/test_iter18_cycle_blog.py` | Iter-18 blog smoke |
| **no `test_ned_cycle.py`** | **Zero automated coverage for the 12 NED routes** |
| **no `test_cycle_phase_d.py`** | **Zero automated coverage for Phase D 14 endpoints** |
| **no `test_cycle_compilation.py`** | **Zero automated coverage for the rebuilt Draft Compilation pipeline** |

---

## 3. PRODUCT_SPEC §5.6 Reconciliation

### 3.1 What §5.6 claims (summarized precisely)

PRODUCT_SPEC.md §5.6 ("Cycle Manager") at HEAD claims:

> 1. Executive side: 6-step stepper (Agenda → Team → Contributions → Scoreboard → Follow-ups → Compilation).
> 2. Draft Compilation injects a **placeholder citation row** `{"doc_id":"stub",...}` when no real citation resolves.
> 3. NED side has **zero code today** — design only, see `docs/NED_CYCLE_MANAGER_DESIGN.md`.
> 4. NED Cycle Manager catch-up surfaces (Briefing pre-read, Questions-to-ask, Signals worth digging into, Minutes diff, Commitments + decisions log, Open-questions ledger) are **design-only**.
> 5. The mandated NED catch-up surface set is itemized in `docs/NED_CYCLE_MANAGER_DESIGN.md`.

The richer 13-section design spec (`Akki_NED_Cycle_Manager_Module_Specification.docx`, extracted) supersedes §5.6 on the **NED side** and adds explicit hard rules: structural separation from Exec CM, LLM-free In act, multi-NED collaboration banned, cross-board confidentiality enforced architecturally (not by policy), six page states (Cross-board landing · Meeting view × 3 acts · Committee view · Cross-board Patterns view), pattern detection on metadata signatures only, read-only calendar.

### 3.2 Contradictions with live code

| # | §5.6 / design-doc claim | Live code reality | Proposed resolution | Reason |
|---|---|---|---|---|
| C1 | "NED side has zero code today — design only" (§5.6) | 12 routes in `routers/ned_cycle.py`; 2 pages in `frontend/src/pages/ned/`; NED home tile creates meetings | **keep-code, update spec** | The Phase E ship is real, tested by humans, wired end-to-end. Reverting would destroy weeks of NED-side work. PRODUCT_SPEC needs to be brought up to date, not the code. |
| C2 | "Draft Compilation injects a placeholder citation row `{doc_id:stub}`" (§5.6) | `routers/cycle_manager.py:739` (Phase D.1) **removed** the heuristic concat-of-bullets path; compilation flows through `services.cycle_synthesis.synthesise_cycle` two-pass LLM | **keep-code, update spec** | Phase D.1 is the spec's own P0 cohort blocker fix — the post-rebuild path is correct. Spec is lagging. |
| C3 | Spec §12 ("Brief delivery model: TBD") — Exec cycle compilation → NED meeting pack handoff is undecided | No code today bridges Exec `cycle_history` / Brief output into a NED meeting's pack. `ned_meetings` rows reference `pack_brief_id` but population path is undefined. | **hybrid** — keep-code for both halves, add a thin **read-only ingestion endpoint** (one of the must-haves below) that materialises an Exec-side compiled Brief as a NED pack entry. Cleanest split: ingestion is a NED-side **pull**, never an Exec-side push. | Architectural separation rule (§1 hard rule) requires NED-side initiation. A pull endpoint preserves the boundary. |
| C4 | Spec §4 — Cross-board landing must order meeting cards by date, not by board; "Patterns worth knowing" hidden if none | `routers/ned_cycle.py:71` returns landing payload — must verify date-ordering and conditional patterns block | **keep-code, verify** | Likely already correct; needs one acceptance test, no rewrite. |
| C5 | Spec §5 Pre act — "Akki Chat integration for paper-specific questions" + "Solva integration for structured analysis of papers" are IN SCOPE | `NedMeeting.jsx` has a question-formulation field and a notes editor but no "Ask in Chat about this paper" / "Take this paper into Solva" CTAs grounded against the paper's `document_id` | **keep-code, extend** | Two new buttons + one cross-surface seed endpoint. Small surface area, high spec compliance. |
| C6 | Spec §5 In act — **LLM-FREE** hard rule; no real-time AI commentary / transcription | `routers/ned_cycle.py` In-act notes endpoint has no LLM call (verified). The danger is *future* drift. | **keep-code, lock with a CI test** | Add a guard test that asserts no LLM is called along the In-act write path. Cheap; protects the hard rule architecturally. |
| C7 | Spec §7 — Cross-board pattern detection runs **on metadata signatures only**; no content exchange | `services/metadata_signatures.py` (Phase E.0.2) is built; `routers/pulse.py:355` Cross-board aggregator (Phase E.0.3) is built — both keyword/regex/enum-only, no LLM, no embeddings | **keep-code, surface in NED UI** | The detection engine exists but **the NED-side "Cross-board Patterns view" page (spec §10 — sixth page state) is not in `frontend/src/pages/ned/`**. Build the read-only page; backend already supports it. |
| C8 | Spec §6 — Per-committee through-line surfaces: recurring questions, deferred decisions, management response patterns, position history, pack patterns | `GET /api/ned/committee/{cid}/{committee}` returns most of these; "pack patterns" (e.g. "every Q3 cycle the audit pack adds a going-concern annex") is not derived | **hybrid** — keep-code, defer "pack patterns" to a later sprint | Pack-pattern derivation needs longitudinal data we don't yet have at scale. v1 ships without it. |
| C9 | Spec §8 — Personal memory across years, searchable | `GET /api/ned/search` exists and accepts query | **keep-code, verify** | One acceptance test verifying topic / decision / person / date-range / committee filters all work. |
| C10 | Spec §12 — "Calendar integration: read-only is recommended" | Zero calendar integration today; meetings created manually | **keep-code, out-of-scope this sprint** | Spec marks calendar depth as "TBD" (§13). Defer. Document in §5. |
| C11 | Spec §11 failure mode — "policy-based confidentiality instead of architectural" | `routers/ned_cycle.py` writes use `services.privacy_wall.cross_context_query`; reads scope by `account_id` | **keep-code, lock with a CI test** | Add an isolation test that asserts NED A on Board X cannot read NED B's annotations on the same board, and that NED A cannot read NED A's own annotations from Board Y when querying Board X. Hard architectural rule deserves a hard test. |
| C12 | Audit / §5.6 — "4 hex literals (`#8B2E2B`) remain in `pages/Cycle.jsx`" + "2 in `pages/Pulse.jsx`" | Confirmed via grep | **keep-code, sweep** | Trivial v7 token replacement on the Cycle page; Pulse is out of scope for this sprint (Should-have only). |
| C13 | Audit deviation — "two cycle routers coexist (`cycle_manager.py` Phase D + legacy `cycle.py` 30 endpoints) — intentional but cognitive collision risk" | Confirmed | **keep-code, document** | Removing `cycle.py` is out-of-scope and dangerous; the legacy router serves questions / committees / submissions which still have frontend consumers. Document the split in `cycle_manager.py` header (already partly there) and leave a `## Layering` section in this brief's §6 dependencies. |

### 3.3 Highest-risk reconciliation decision — LOCKED (ASSIGNMENT HANDOFF)

**C3 resolution (locked 2026-02):** Exec → NED brief delivery is **neither push nor pull**. It is an explicit **assignment handoff** with privacy-wall-enforced ingest, in five state transitions:

1. **Submit** `POST /api/contexts/{cid}/cycles/{cycle_id}/briefs/{brief_id}/submit-for-board` — marks brief `submitted`. Permitted callers: owner (individual workspace); owner + ExCo members + `sub_role="chief_of_staff"` (team workspace). Helper: `services/cycle_permissions.can_submit_for_board`.
2. **Assign** `POST /api/contexts/{cid}/cycles/{cycle_id}/briefs/{brief_id}/assignments` — body `{ned_ids?:[str], cohort_id?:str, note?:str}`. Mutually exclusive — exactly one of `ned_ids` / `cohort_id` MUST be set. Cohort resolution snapshots NED ids at assignment time, persists on the row. Fans out one `cycle_assignments` row per NED.
3. **NED inbox** `GET /api/ned/inbox/assignments` — strict field whitelist `{assignment_id, brief_id, submitter_display_name, cycle_title, submitted_at, cohort_label_optional}`. NO Exec-internal fields, EVER.
4. **Accept** `POST /api/ned/assignments/{assignment_id}/accept` — idempotent. Privacy Wall projects ONLY the approved Brief artefact into the NED's durable record. No agenda metadata, no scoring, no contribution metadata.
5. **Decline** `POST /api/ned/assignments/{assignment_id}/decline` — body `{reason?:str}`. Logs; never ingests.

**Forbidden code path:** any write that copies Exec-internal fields (`cycle_agendas`, `cycle_contributions`, `cycle_team`, `cycle_followups`, scoring rationale, agenda internals) into NED collections (`ned_meetings`, `ned_meeting_notes`, `ned_positions`, `ned_followups`, `ned_annotations`). Enforced by negative tests in `test_cycle_assignment_privacy_wall.py`.

**Resend in dev:** MOCKED IN DEV (test mode). Notification call sites are wired in code with explicit `# MOCKED IN DEV` markers; no fake confirmation surfaced to the user.

### 3.4 Original reconciliation table (for historical context)

### 3.5 Original highest-risk callout (resolution: ASSIGNMENT HANDOFF, see §3.3)

**C3 — Exec cycle compilation → NED meeting pack delivery:** this is the only contradiction where (a) the spec hard-rule (§1 architectural separation, §11 failure mode "policy-based confidentiality") combines with (b) a real product handoff that doesn't yet have a code path, and (c) the wrong direction (Exec push vs NED pull) is **silently** unsafe — a push from the Exec side would tempt downstream consumers to enrich the NED pack with Exec-side fields like `cycle_agendas.scoring_rationale` that the NED is not supposed to see and that, once on the NED's surface, become impossible to retract.

The brief recommends a **NED-side pull** that takes only the Brief artefact_id (no agenda metadata, no contribution metadata, no scoring), with the privacy wall enforcing the cross-context guard. Getting this direction wrong on the first ship is the single decision that could leak Exec-internal cycle data onto a NED's permanent record.

---

## 4. Proposed Sprint Scope

### 4.1 Must-have

| # | Requirement | Acceptance (binary-verifiable) | Files likely touched | Complexity |
|---|---|---|---|---|
| M1 | **Compilation regression test** — assert the rebuilt Phase D.1 path produces a Brief with non-empty `cover_lead_paragraph`, non-empty `sections`, and `audit_log` row written; assert NO row containing `{"doc_id":"stub"}` is ever inserted into `db.work_studio_briefs`. | `pytest backend/tests/test_cycle_compilation.py -q` returns 4/4 green | `backend/tests/test_cycle_compilation.py` (NEW) | M |
| M2 | **NED cross-board confidentiality test** — assert NED A cannot read NED B's annotations on the same context; assert NED A cannot read own annotations from a different context via `GET /api/ned/landing`, `/ned/committee/{cid}/{committee}`, `/ned/search`. | `pytest backend/tests/test_ned_cycle_isolation.py -q` returns 6/6 green | `backend/tests/test_ned_cycle_isolation.py` (NEW) | M |
| M3 | **In-act LLM-FREE guard test** — assert the entire In-act write path (`POST /ned/meetings/{id}/notes`) calls neither `services.llm_streaming.*` nor `emergentintegrations.*` nor `services.synisense.llm_fallback.*` (mock + spy). | `pytest backend/tests/test_ned_in_act_llm_free.py -q` returns 1/1 green | `backend/tests/test_ned_in_act_llm_free.py` (NEW) | S |
| M4 | **Exec→NED pack pull endpoint** — implement `POST /api/ned/meetings/{meeting_id}/ingest-pack` that takes only `{"brief_id": "..."}`, validates the requester is a NED on the brief's source context, copies ONLY the rendered Brief artefact (no agenda metadata, no contributions, no scoring) into the meeting's pack, and writes an audit row. | curl: NED on board X ingests brief → 200 + `pack_brief_id` set; NED not on board X → 403; Exec on board X → 403 (NED-side action only); request includes any field other than `brief_id` → 400 | `routers/ned_cycle.py`, `services/privacy_wall.py` (read-only), `backend/tests/test_ned_pack_ingestion.py` (NEW) | M |
| M5 | **Cross-board Patterns view (NED page state #6)** — new page `/app/ned/patterns` reads `routers/pulse.py:355` cross-board aggregator + `db.context_metadata_signatures` and renders pattern cards (title, description, boards-touched-by-NED-label, date detected, Dismiss / Save-for-later). NO content from any board surfaces — only the pattern signature. | Playwright: NED with patterns sees cards; NED with no patterns sees an empty-state with the §7 explanation copy; clicking a board label does NOT reveal the source artefact_id. | `frontend/src/pages/ned/NedPatterns.jsx` (NEW); `frontend/src/App.js` route; small backend read endpoint `GET /api/ned/patterns` if not yet exposed | M |
| M6 | **Pre-act paper actions: "Ask in Chat" + "Take into Solva"** — two CTAs per paper in `NedMeeting.jsx` Pre act, each pre-seeds a Chat / Solva session grounded against the paper's `document_id`. | Manual: click "Ask in Chat" → opens `/app/chat?seed_document_id=...`; click "Take into Solva" → opens `/app/solva/new?seed_document_id=...` ; both honour the privacy wall on the document. | `frontend/src/pages/ned/NedMeeting.jsx`; backend already supports seeded chat / solva sessions | S |
| M7 | **v7 palette sweep on `pages/Cycle.jsx`** — remove the 4 `#8B2E2B` hex literals; resolve via existing tokens. | `grep -E "#[0-9A-Fa-f]{6}" frontend/src/pages/Cycle.jsx` returns 0; visual diff smoke; lint clean. | `frontend/src/pages/Cycle.jsx`; `frontend/src/index.css` (none expected — tokens already exist) | S |
| M8 | **PRODUCT_SPEC §5.6 update** — rewrite §5.6 to match live reality (12 NED routes, Phase D.1 rebuilt compilation, no stub citation, page-state count, cross-board patterns engine status). Cite file paths. | Diff applied to `/app/docs/PRODUCT_SPEC.md` §5.6; no other section touched. | `/app/docs/PRODUCT_SPEC.md` | S |
| M9 | **Per-committee through-line acceptance test** — assert `GET /api/ned/committee/{cid}/{committee}` returns recurring_questions[], deferred_decisions[], management_response_patterns[], position_history[]. | `pytest backend/tests/test_ned_committee.py -q` returns 4/4 green | `backend/tests/test_ned_committee.py` (NEW) | S |
| M10 | **Phase D readiness + draft-compilation acceptance tests** — cover the 14 Exec endpoints with happy-path + 1 invalid-input case each. | `pytest backend/tests/test_cycle_phase_d.py -q` returns ≥14/14 green | `backend/tests/test_cycle_phase_d.py` (NEW) | M |

### 4.2 Should-have

| # | Requirement | Acceptance | Files | Complexity |
|---|---|---|---|---|
| S1 | **`WorkspaceEntryGate` already wired on `Cycle.jsx`** — verify; add the same on the NED meeting / committee / patterns pages. | `Cycle.jsx`, `NedMeeting.jsx`, `NedCommittee.jsx`, `NedPatterns.jsx` all render the streaming reveal on first session-visit. | `frontend/src/pages/ned/*.jsx` | S |
| S2 | **`Cycle.jsx` font-token sweep** — verify Source Serif 4 / Inter / JetBrains Mono token usage (no inline `font-family`). | `grep -E "font-family\s*:" pages/Cycle.jsx pages/ned/*.jsx` returns 0 | `pages/Cycle.jsx`, `pages/ned/*.jsx` | S |
| S3 | **NED commitments ledger read endpoint** — `GET /api/ned/commitments?committee=&from=&to=` returns the per-NED commitments + decisions ledger as one shape (joins ned_positions + ned_followups + ned_meetings). | curl returns array of rows with `{meeting_id, position, decision_topic, follow_up_status, due_date, sent_at}`; acceptance test 3/3 green | `routers/ned_cycle.py`; `backend/tests/test_ned_commitments.py` (NEW) | M |
| S4 | **Compilation citation telemetry** — surface a "citations resolved: N/M" mini-bar on the Exec stepper compilation step (read-only, derived from the rebuilt synth result). | Visual: when M=0 → "no citations resolved" line in graphite, when M>0 → ratio rendered. | `frontend/src/pages/Cycle.jsx` | S |
| S5 | **NED minutes-diff narrative (read-only)** — `GET /api/ned/committee/{cid}/{committee}/diff?from_meeting=&to_meeting=` returns a structured diff (decisions changed, follow-ups closed, positions reversed). Pure derivation, no LLM. | curl returns 4 array fields; acceptance test 2/2 green | `routers/ned_cycle.py`; `test_ned_minutes_diff.py` (NEW) | M |

### 4.3 Could-have

| # | Requirement | Acceptance | Files | Complexity |
|---|---|---|---|---|
| C-h1 | **Empty-state copy pass** on the cross-board landing + patterns view (calm, non-operational voice per spec §9). | Manual review by user. | `pages/ned/*.jsx` | S |
| C-h2 | **Single-board filter** on the cross-board landing (spec §4: "Single-board view is a filter, not a separate surface"). | Click a board chip → landing filters to that board; click again → clears. | `pages/home/HomeNed.jsx` or landing component | S |
| C-h3 | **Voice review** — pass `pages/ned/*.jsx` copy through the spec §9 voice rules (reflective, brief, no operational verbs). | Grep for banned vocab returns 0. | `pages/ned/*.jsx` | S |
| C-h4 | **`Cycle.jsx` decomposition** — current 864-line page splits into stepper-frame + 6 step components. | File sizes < 250 lines each; behaviour unchanged; existing Playwright e2e green. | `pages/Cycle.jsx`, new `components/cycle/Step*.jsx` | M |

---

## 5. Explicitly Out of Scope

### 5.1 In §5.6 / spec but deliberately deferred

| Item | Source | Reason |
|---|---|---|
| Calendar integration (read-only) | spec §12, §13 ("Calendar depth: TBD") | Design-decision-blocked. OAuth provider, manual-entry vs auto-import, multi-calendar UX all undefined. Defer. |
| Multi-NED collaborative surfaces | spec §1 explicitly **forbidden** | NOT a deferral — a permanent out-of-scope. Listed here only to make the boundary loud. |
| Real-time transcription / live-AI commentary during meetings | spec §1, §5 In act explicitly **forbidden** | Same as above. |
| "Pack patterns" derivation on per-committee through-line | spec §6 | Needs longitudinal data we don't yet have. Defer to a later sprint when 3+ cycles of data exist. |
| External Company Secretary support / sharing model for NED-artefacts | spec §13 | Design-decision-blocked. Defer. |
| Voice-input note-taking on the In act surface | spec §13 | Design-decision-blocked. Defer. |
| Predictive features recommending positions / votes | spec §1, §11 explicitly **forbidden** | Permanent out-of-scope. |
| Networking features (other NEDs visible) | spec §1, §11 explicitly **forbidden** | Permanent out-of-scope. |
| HR-style metrics on NED engagement | spec §11 explicitly **forbidden** | Permanent out-of-scope. |
| Onboarding tutorials | spec §11 explicitly **forbidden** | Permanent out-of-scope. |

### 5.2 Live in code, NOT being ripped out

| Item | File path | Reason |
|---|---|---|
| Legacy `routers/cycle.py` (30 endpoints — questions / committees / submissions / checklists / reports / schedule) | `routers/cycle.py` | Still has frontend consumers; removal is its own multi-sprint deprecation effort. |
| `routers/cycle_config.py` (per-context cycle config) | `routers/cycle_config.py` | Used by Phase D and legacy alike. |
| Heuristic concat-of-bullets compilation fallback | already removed in Phase D.1 | Already gone. Nothing to do. |
| Sandbox Cycle Manager (read-only demo) | sandbox routes | Sandbox is its own surface; out of scope. |

### 5.3 Cross-service work explicitly NOT in this sprint

| Item | Owner sprint |
|---|---|
| Pulse same-context Synisense routing (`services/privacy_wall.project_for_pulse` no-op) | TRUST / future Pulse sprint |
| Work Studio audit-footer route-side wiring (`work_studio_phase_c.py` doesn't populate `Brief.audit_summary`) | STUDIO close-out — owner: Work Studio |
| Pulse hex-literal sweep (`pages/Pulse.jsx` 2 hex literals) | future Pulse sprint |
| Monitor + Learn v7 sweep | future Monitor / Learn sprints |
| Deployment blockers (Cosmos `retrywrites=false`, Key Vault rotation, ClamAV un-bypass, APScheduler distributed lock) | DEPLOY sprint |
| GPT-5.2 direct streaming | future Chat sprint |
| Postmark HMAC enforcement in production | DEPLOY sprint |

---

## 6. Dependencies

### 6.1 Hard dependencies on other services / integrations

| Dependency | Where it shows up | Status |
|---|---|---|
| Synisense Shield (PII redaction) | NED notes / follow-ups go through the same pipeline as Solva | Wired |
| Solva v2 sessions | M6 "Take into Solva" CTA seeds a Solva session against a document | Wired |
| Akki Chat | M6 "Ask in Chat" CTA seeds a chat session against a document | Wired |
| Work Studio Briefs persistence (`build_brief_from_solva`, `ensure_brief_persisted`, `render_docx`) | M4 pack-pull + Phase D.1 compilation | Wired |
| Resend (test mode in dev) | Follow-up send from both Exec + NED sides | Wired (test-mode in dev — fine for sprint acceptance) |
| `services/metadata_signatures.py` (Phase E.0.2) | M5 Cross-board Patterns view backend | Wired |
| `routers/pulse.py:355` cross-board aggregator (Phase E.0.3) | M5 Cross-board Patterns view backend | Wired |
| `services/privacy_wall.cross_context_query` | M2 + M4 isolation enforcement | Wired |
| `services/cycle_synthesis.synthesise_cycle` (Sonnet 4.5 drafter + Gemini 2.5 Flash validator) | M1 compilation regression test | Wired |

### 6.2 Open blockers from the audit that would stop this sprint

| Blocker | Impact | Recommendation |
|---|---|---|
| Pre-existing 11 backend test failures + 9 errors (unrelated to sprint) | Cosmetic — runs at base | Continue to gate on the 41/41 critical regression subset only; document non-critical failures as known-state and do not let them block the sprint. |
| `services/work_studio_export.py` legacy export pipeline (no audit footer) | Tangential — M4 pack-pull uses the Solva-pipeline `render_docx`, not the legacy pipeline | Not a blocker for this sprint. STUDIO close-out owns it. |
| Resend in test-mode | M4 send actions may bounce to allowlist only | Use `juliusaopio@gmail.com` (test_credentials.md) as allowlisted recipient in tests. |

---

## 7. Acceptance & Test Plan

### 7.1 Binary criteria for sprint completion

A sprint is **DONE** iff all of the following hold:

1. `pytest backend/tests/test_privacy_wall.py tests/test_phase_g_privacy_wall_sentinel.py tests/test_privacy_wall_phase_2c.py tests/test_universal_search.py tests/test_exco_teams.py tests/test_render_determinism.py -q` returns **41 / 41 green** (no regression).
2. `pytest backend/tests/test_cycle_compilation.py tests/test_ned_cycle_isolation.py tests/test_ned_in_act_llm_free.py tests/test_ned_pack_ingestion.py tests/test_ned_committee.py tests/test_cycle_phase_d.py -q` returns **green** (must-have tests for this sprint).
3. `grep -nE "#[0-9A-Fa-f]{6}" frontend/src/pages/Cycle.jsx` returns **0**.
4. `frontend/src/pages/ned/NedPatterns.jsx` exists, routed at `/app/ned/patterns`, and renders without errors in the smoke screenshot.
5. `routers/ned_cycle.py` has the new `POST /api/ned/meetings/{meeting_id}/ingest-pack` endpoint, and a curl probe against it from a non-NED account returns 403.
6. PRODUCT_SPEC §5.6 has been rewritten and references the 12 routes + Phase D.1 + cross-board patterns engine + the 6 page states.
7. `frontend/src/pages/ned/NedMeeting.jsx` Pre-act surface exposes "Ask in Chat about this paper" + "Take this paper into Solva" CTAs per paper.

### 7.2 Automated test vs human verification matrix

| Item | Automated test | Human verification |
|---|---|---|
| M1 Compilation regression | ✅ `test_cycle_compilation.py` | — |
| M2 NED isolation | ✅ `test_ned_cycle_isolation.py` | — |
| M3 In-act LLM-FREE guard | ✅ `test_ned_in_act_llm_free.py` | — |
| M4 Pack-pull endpoint | ✅ `test_ned_pack_ingestion.py` | curl smoke from preview URL |
| M5 Cross-board Patterns view | partial (`GET /api/ned/patterns`) | ✅ Playwright smoke (no content leak in cards) |
| M6 Pre-act paper actions | — | ✅ Manual click-through; verify document_id seed |
| M7 v7 hex sweep on Cycle.jsx | ✅ `grep -E "#[0-9A-Fa-f]{6}"` | ✅ Visual diff smoke |
| M8 PRODUCT_SPEC §5.6 rewrite | — | ✅ User read-through |
| M9 Per-committee through-line | ✅ `test_ned_committee.py` | — |
| M10 Phase D 14 endpoints | ✅ `test_cycle_phase_d.py` | — |
| S1 WorkspaceEntryGate on NED pages | — | ✅ Visual smoke |
| S2 Font-token sweep | ✅ grep | — |
| S3 Commitments ledger | ✅ `test_ned_commitments.py` | — |
| S4 Citation telemetry | — | ✅ Visual smoke |
| S5 Minutes-diff narrative | ✅ `test_ned_minutes_diff.py` | — |

### 7.3 Existing test files that cover Cycle Manager today

| File | Scope | Status |
|---|---|---|
| `backend/tests/test_cycle_manager_actions_tab.py` | Legacy `cycle.py` actions tab | Working baseline; **do not break** during sprint |
| `backend/tests/test_daily_review_solva_cycle.py` | Daily-review → Solva → Cycle handshake | Working baseline; **do not break** |
| `backend/tests/test_iter18_cycle_blog.py` | Iter-18 cycle blog smoke | Working baseline; **do not break** |

---

## 8. Open Questions for User

1. **M4 pack-pull direction.** Confirm the architectural call: Exec-side compilation never *pushes* a Brief onto a NED meeting; instead the NED *pulls* a Brief into a meeting via `POST /api/ned/meetings/{id}/ingest-pack {"brief_id"}`. Confirm? (Default: yes — this is the only direction that doesn't risk Exec-internal cycle data bleeding onto a NED's record.)
2. **M5 Patterns view backend endpoint.** `routers/pulse.py:355` is the cross-board aggregator today. Should the NED Patterns view call it directly, or do we mint a NED-scoped read endpoint `GET /api/ned/patterns` that wraps it with stricter projection (boards-touched-by-NED-label only, no raw context_id leakage)? (Default: mint the NED-scoped wrapper.)
3. **M8 PRODUCT_SPEC §5.6 rewrite — depth.** Rewrite §5.6 to point at the 13-section `Akki_NED_Cycle_Manager_Module_Specification.docx` as the source of truth, or inline a precis of §1–§12 into §5.6 of the spec itself? (Default: point + add a 6-line precis covering hard rules — LLM-free In act, multi-NED ban, calendar read-only, architectural confidentiality, no predictive features, six page states.)
4. **Phase D.1 compilation downloadable artefact format.** Today it renders Board Summary / High Fidelity DOCX inline. Brief mentions 18 (Format × Depth × Fidelity) combinations. Do we expose a format picker on the compilation step this sprint, or stay with the default and ship the picker later? (Default: stay with default; format picker is a Could-have at most.)
5. **Test-allowlist recipient for M4 send-path probes.** Confirm `juliusaopio@gmail.com` is the right allowlisted Resend recipient for sprint tests, or supply an alternative. (Default: yes, per `/app/memory/test_credentials.md`.)
6. **Legacy `routers/cycle.py` deprecation.** Out-of-scope for this sprint, but please confirm — should the next sprint after this one open the deprecation, or is `cycle.py` planned to live indefinitely as the questions/committees/submissions store? (Default: defer the decision; do nothing this sprint.)

---

*End of brief.*
