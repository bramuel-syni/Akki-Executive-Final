# Provenance Trace — Plays + Cycle Routers

**Dispatched:** 2026-05-26 (legacy-conflict audit Task B).
**Goal:** Determine whether `Plays` and the three cycle routers (`cycle.py`, `cycle_manager.py`, `cycles.py`) are canonical per the spec or orphan.
**Hard rule:** READ ONLY. No code changes. No moving anything yet.

**Canonical sources scanned (verbatim list):**
- `/app/memory/AKKI_PRODUCT_SPEC.md` v1.1 (24 May 2026)
- `/app/memory/AKKI_ONBOARDING_SPEC.md` v1.1
- `/app/memory/sprints/qa_24may2026/document_journal_qa_24may2026.md`
- `/app/memory/sprints/qa_24may2026/cycle_manager_qa_24may2026.md`
- `/app/memory/sprints/qa_24may2026/work_studio_qa_24may2026.md`
- `/app/memory/sprints/qa_24may2026/aggregated_qa_24may2026.md`
- `/app/memory/qa_reports/SOLVA_QA_BRIEF_20MAY2026.md`

**Grep recipe (word-boundary, case-insensitive):**
```
grep -niE "\bplay\b|\bplays\b|\bworkflow\b|\bworkflows\b" <each canonical file>
```

---

## Part 1 — Plays / Workflows surface

### Files in scope

| File | Purpose | Earliest commit |
| --- | --- | --- |
| `backend/routers/plays.py` | `/api/contexts/{cid}/plays/*` + `/api/plays/library` (auto-launch, briefs, status). | `4604787` — **2026-04-26** |
| `backend/routers/agenda.py` | `/api/contexts/{cid}/cycle/agenda/preboard` (Pre-Board Play scheduling). | `2a2f6f4` — **2026-04-26** |
| `frontend/src/pages/PlaysLibrary.jsx` | `/app/plays` route → cards for each Play type. | `4604787` — **2026-04-26** |
| `frontend/src/pages/PlayView.jsx` | `/app/plays/:playId` route → progress view for a single Play. | `4604787` — **2026-04-26** |
| `frontend/src/components/plays/BoardPackStages.jsx` | Stage walkthrough for Board Pack Play. Calls `/cycle/schedule`, `/cycle/checklists`, `/cycle/reports/...`, `/cycle/submissions`. | `4604787` — **2026-04-26** |
| `frontend/src/components/plays/PreBoardStages.jsx` | Stage walkthrough for Pre-Board Play. | `4604787` — **2026-04-26** |

### Canonical-source citation check

| Canonical source | `\bplay\b` | `\bplays\b` | `\bworkflow\b` | `\bworkflows\b` |
| --- | :-: | :-: | :-: | :-: |
| `AKKI_PRODUCT_SPEC.md` v1.1 | 0 | 0 | 0 | 0 |
| `AKKI_ONBOARDING_SPEC.md` v1.1 | 0 | 0 | 0 | 0 |
| `document_journal_qa_24may2026.md` | 0 | 0 | 0 | 0 |
| `cycle_manager_qa_24may2026.md` | 0 | 0 | 0 | 0 |
| `work_studio_qa_24may2026.md` | 0 | 0 | 0 | 0 |
| `aggregated_qa_24may2026.md` | 0 | 0 | 0 | 0 |
| `SOLVA_QA_BRIEF_20MAY2026.md` | 0 | 0 | 0 | 0 |

**Zero word-boundary mentions across every canonical source.** (Substring hits exist in canonical files only inside unrelated words like `displays`, `replaces`, `display`, etc. — confirmed by re-running with `\b...\b` boundary anchors.)

### Cross-check against ratified gaps

`AKKI_PRODUCT_SPEC.md` §6 lists ratified gaps G1–G12 (each tagged with a sprint anchor). `AKKI_ONBOARDING_SPEC.md` §6 lists J-series gaps. Neither references a Play, a Workflow, a Pre-Board flow, a Board Pack Play, or any equivalent named choreography.

### Non-canonical doc references (for completeness)

Plays IS referenced in:
- `memory/PRODUCT_FEATURES.md` (LEDGER row 3.2 — flagged for archive, predates spec v1.1).
- `memory/product/AKKI_FEATURES_AND_FUNCTIONALITY.md` (spec §1.4 stripped its authority).
- `memory/CHANGELOG.md` (entry `iter26 — rename Play → Workflow`).

None of these have canonical authority per `AKKI_PRODUCT_SPEC.md` §1.4 / §1.

### Verdict

> **ORPHAN (no canonical reference, first introduced at commit `4604787` on 2026-04-26 — auto-commit for `442854ee-23ae-4d8f-ad21-888bca8a38f1`).** Companion `agenda.py` introduced the same day at commit `2a2f6f4`. The surface predates the 2026-05-24 spec-clean-break (`AKKI_PRODUCT_SPEC.md` v1.0 explicitly states: *"a fresh clean-break — it does not merge from, supersede, or reference `AKKI_FEATURES_AND_FUNCTIONALITY.md`"*) and is not adopted by spec v1.1.

---

## Part 2 — Three cycle routers

### Endpoint inventory

#### `backend/routers/cycle.py` — 30 endpoints (earliest commit `59b609f`, 2026-04-25)

Endpoint families (deduped, path-only):

| Family | Endpoints | Frontend live callers (excluding `_archived_legacy/` and `components/plays/`) |
| --- | --- | --- |
| Cycle ops | `/cycle/committees`, `/cycle/schedule`, `/cycle/actions`, `/cycle/cron/run-schedules` | 0 live non-Plays |
| Checklists | `/checklists`, `/checklists/dispatch`, `/checklists/generate`, `/checklists/{cid}` | 2 (`components/home/QuickActions.jsx`, `components/home/InSummaryTiles.jsx`) |
| Reportees | `/reportees`, `/reportees/{rid}` | 0 live non-Plays (only archived `CycleTracker.jsx` + `ReportsTab.jsx`) |
| Reports | `/reports`, `/reports/compose`, `/reports/{rid}`, `/reports/{rid}/export.deck.pdf`, `/reports/{rid}/export.pdf`, `/reports/{rid}/polish`, `/reports/{rid}/review`, `/reports/{rid}/send_up`, `/reports/inbox` | 1 (`pages/Monitor.jsx`) |
| Questions | `/questions`, `/questions/seed-from-briefings`, `/questions/{qid}` | 4 (`pages/Questions.jsx`, `pages/home/Home2.jsx`, `components/shell/HandoffActions.jsx`, +1) |
| Respond / submissions | `/respond/{token}`, `/submissions`, `/me/submitted-briefs` | 2 + 1 (`pages/RespondToChecklist.jsx`, `App.js` route `/r/:token`, `InSummaryTiles.jsx`) |

#### `backend/routers/cycle_manager.py` — 16 endpoints (earliest commit `31d411a`, 2026-05-07)

| Family | Endpoints | Frontend live callers |
| --- | --- | --- |
| Agenda | `/cycle/agenda` (GET + POST) | 1 (`pages/Cycle.jsx`) |
| Team | `/cycle/team` (GET + POST), `/cycle/team/{member_id}` (PUT + DELETE) | 2 (`pages/Cycle.jsx`, `components/cycle/TeamCatalogueDialog.jsx`) |
| Contributions | `/cycle/contributions` (GET + POST), `/cycle/contributions/{cid}/score` | 3 (`pages/Cycle.jsx`, `components/cycle/ContributionAttachPicker.jsx`, +1) |
| Readiness | `/cycle/readiness` | 1 (`pages/Cycle.jsx`) |
| Follow-ups | `/cycle/follow-ups`, `/cycle/follow-ups/draft`, `/cycle/follow-ups/{id}/approve`, `/cycle/follow-ups/{id}/send` | 1 (`pages/Cycle.jsx`) |
| Compilation | `/cycle/draft-compilation` | 1 (`pages/Cycle.jsx`) |

#### `backend/routers/cycles.py` — 6 endpoints (earliest commit `c175801`, 2026-05-11)

| Family | Endpoints | Frontend live callers |
| --- | --- | --- |
| Cycles master | `/contexts/{cid}/cycles` (GET list + POST create) | 9 files including `pages/cycle/CycleList.jsx`, `components/cycle/CycleSetupWizard.jsx`, `components/cycle/AddTeamMemberDialog.jsx`, `pages/Cycle.jsx`, `components/home/SidePanelCard.jsx`, … |
| Cycle item | `/contexts/{cid}/cycles/{cycle_id}` (GET + PATCH) | included above |
| Lifecycle | `/cycles/{cid}/activate`, `/cycles/{cid}/close`, `/cycles/{cid}/apply-template` | 1 each |

### Path-collision check

Cross-router path-overlap detection (full `/api/contexts/{cid}/...` paths, grouped):

```
$ for f in cycle.py cycle_manager.py cycles.py; do
    grep -E "^@router\." "$f" | sed -E 's|.*\("([^"]+)".*|\1|' | sed "s|^|$f\t|"
  done | sort -k2 | awk -F'\t' '{ p[$2] = p[$2] ? p[$2] " | " $1 : $1; n[$2]++ }
                                  END { for (k in n) if (n[k] > 1) print k " — used by: " p[k] }'
```

Every multi-row hit is the SAME router declaring GET + POST on the same path (e.g. `cycle_manager.py` declares both GET `/cycle/agenda` and POST `/cycle/agenda`). **No cross-router path collisions detected** — the three routers carve disjoint endpoint families.

### Canonical-source citation per router

| Router | Endpoint families | Canonical citation? |
| --- | --- | --- |
| `cycles.py` | cycles master, lifecycle (activate / close / apply-template) | **YES.** `cycle_manager_qa_24may2026.md` §2 (Landing Page), §3 (Setup Wizard `Save as Draft` + `Commission Cycle`), §4 (`Activate Cycle` button + status). `AKKI_PRODUCT_SPEC.md` §4 cycle journey (lines 105–107). Maps to: Setup Wizard → POST cycle, Activate → activate endpoint, Compile → close endpoint. |
| `cycle_manager.py` | agenda, team, contributions (+ score), readiness, follow-ups, draft-compilation | **YES.** `cycle_manager_qa_24may2026.md` §4.1–§4.3 (Cycle Page sections: Cycle Status Overview, Contributions Table with Score column, Cycle Actions including Add Agenda / Add Team Member / Add Contribution / Follow Up / Compile). Maps cleanly to the spec's 6-section Cycle Page. |
| `cycle.py` | committees, schedule, actions, checklists, reportees, reports, questions, respond/{token}, submissions, send_up, /me/submitted-briefs, cron/run-schedules | **NO.** Zero word-boundary hits for `committees`, `checklist`, `reportee`, `send_up`, `submission`, `schedule`, `questions` in `cycle_manager_qa_24may2026.md`. `AKKI_PRODUCT_SPEC.md` mentions `reports` 17 times but only as a Work Studio tab (W3, W9 — "Minutes / Decks / Reports tabs"), NEVER as `/api/contexts/{cid}/reports/*`. |

### Per-router cross-check

#### `routers/cycles.py` — KEEP

Canonical citation: `cycle_manager_qa_24may2026.md` §2.1 (Add Cycle Button), §3.3 (Save as Draft → POST a Draft cycle; Commission Cycle → POST an Active cycle), §4 (Activate Cycle button → `/cycles/{cid}/activate`).

Frontend coverage: 9 live files including the T5 entry points (`CycleSetupWizard.jsx`, `CycleList.jsx`). Cleanly maps spec terminology → endpoint.

> **Verdict: KEEP (canonical, cited at `cycle_manager_qa_24may2026.md` §§ 2.1, 3.3, 4; `AKKI_PRODUCT_SPEC.md` §4 cycle journey C1–C8).**

#### `routers/cycle_manager.py` — KEEP

Canonical citation: `cycle_manager_qa_24may2026.md` §4.1 (Cycle Status Overview → readiness), §4.2 (Contributions Table with Score column → contributions + contributions/{id}/score), §4.3 (Cycle Actions: Add Agenda → /cycle/agenda; Add Team Member → /cycle/team; Add Contribution → /cycle/contributions; Follow Up → /cycle/follow-ups; Compile → /cycle/draft-compilation).

Frontend coverage: 9+ live calls from `pages/Cycle.jsx`. Direct 1:1 mapping to the spec's Section 4 endpoints.

> **Verdict: KEEP (canonical, cited at `cycle_manager_qa_24may2026.md` §4.1–§4.3; `AKKI_PRODUCT_SPEC.md` §4 cycle journey C4–C8).**

#### `routers/cycle.py` — MIXED

The router's 30 endpoints split into:

- **Pre-spec families** (no canonical citation): `/cycle/committees`, `/cycle/schedule`, `/cycle/actions`, `/cycle/cron/run-schedules`, `/checklists/*`, `/reportees`, `/reports/*` (the §12 Reports namespace, distinct from Work Studio's Reports TAB), `/questions/*`, `/respond/{token}`, `/submissions`, `/me/submitted-briefs`. These describe a pre-spec product layer ("Questions" + "Reportees" + "Checklists" + "Send-up Reports") that does not appear in any canonical source.
- **Live frontend callers** (so deletion would break live UX): 9 of the 30 endpoints. Specifically: `/questions` family (4 callers including `pages/Questions.jsx`, `pages/home/Home2.jsx`), `/respond/{token}` (`pages/RespondToChecklist.jsx` + `App.js` route `/r/:token`), `/checklists` family (`components/home/QuickActions.jsx`, `components/home/InSummaryTiles.jsx`), `/reports/inbox` and `/reports/{rid}/review` (`pages/Monitor.jsx`), `/submissions` (`components/home/InSummaryTiles.jsx`), `/me/submitted-briefs` (1 caller).
- **Dead families** (zero live callers — only archived components or Plays): `/cycle/committees`, `/cycle/schedule`, `/cycle/actions`, `/cycle/cron/run-schedules`, `/reportees`, `/reports/compose`, `/reports/{rid}/export.*.pdf`, `/reports/{rid}/polish`, `/reports/{rid}/send_up`.

The remaining live callers are mostly side-panel cards on Home (`QuickActions`, `InSummaryTiles`) and pre-spec pages (`Questions`, `Monitor` v1, `RespondToChecklist`).

> **Verdict: MIXED — partial-orphan (introduced at commit `59b609f`, 2026-04-25 — predates spec v1.1 by 1 month).** Router as a whole is NOT canonical. Roughly 9 of 30 endpoints are still load-bearing for live UX surfaces (Questions, Respond, side-panel cards on Home, Monitor v1 reports inbox). The other 21 endpoints describe a pre-spec product layer with no canonical authority.
>
> Per the user's "no decision menu" directive, this is reported as fact. The endpoints split cleanly into "live but pre-spec" (9) and "dead pre-spec" (21).

---

## Bonus — `backend/routers/cycle_config.py` (LEDGER row 1.9)

User's audit deferred row 1.9 (cycle_config) to Task B as cycle-adjacent. Findings:

- **Endpoints (5):** `/cycle-config` (GET + PUT), `/cycle-config/advance`, `/cycle-config/reset`, `/cycle-config/phases/{phase_id}/summary` — under `/api/contexts/{cid}/...`.
- **Canonical citation:** ZERO hits across all canonical sources for `cycle-config`, `cycle_config`, `phase configuration`, or "Cycle Strip".
- **Frontend callers:** 0 live frontend callers under `frontend/src/` (search `cycle/config\|cycle_config`). The router docstring states *"powering the Cycle Strip on Home and `/app/cycle`"* — but `components/cycle/CycleStrip.jsx` was archived in CLEANUP_B1 (zero importers). The router is functionally orphan now that its only stated consumer is in `_archived_legacy/`.
- **First introduced:** commit `3fb656b`, 2026-05-01 — auto-commit for `a49a828e-05f4-44ee-8d86-505f0b5bfd96`. Predates spec by 23 days.

> **Verdict: ORPHAN (no canonical reference, first introduced at commit `3fb656b` on 2026-05-01; only stated consumer `CycleStrip.jsx` archived in CLEANUP_B1).**

---

## Summary table

| Item | Verdict |
| --- | --- |
| Plays / Workflows surface (router `plays.py` + `agenda.py` + `pages/PlaysLibrary.jsx` + `pages/PlayView.jsx` + `components/plays/`) | **ORPHAN** (no canonical reference, first introduced at commit `4604787` on 2026-04-26) |
| `backend/routers/cycle.py` | **MIXED — partial-orphan** (no canonical reference for any of its 30 endpoints; 9 still load-bearing for live pre-spec UX surfaces; 21 dead) |
| `backend/routers/cycle_manager.py` | **KEEP** (canonical, cited at `cycle_manager_qa_24may2026.md` §4.1–§4.3) |
| `backend/routers/cycles.py` | **KEEP** (canonical, cited at `cycle_manager_qa_24may2026.md` §§ 2.1, 3.3, 4) |
| `backend/routers/cycle_config.py` | **ORPHAN** (no canonical reference, first introduced at commit `3fb656b` on 2026-05-01; sole consumer archived in CLEANUP_B1) |

---

*Provenance trace complete. Awaiting user review. No code changes performed.*
