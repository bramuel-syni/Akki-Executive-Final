# D Implementation Log — Trust Center "known deviation" note

**Chunk:** D — `de_id_summary` transparency note (UI-only)
**Started:** 2026-05-25
**Spec contract:** the user's chunk-(d) brief (verbatim wording supplied, mildly refined for Trust Center voice — see "Final wording" below).
**Boundary:** UI-only. NO backend, NO schema, NO guardrail file changes.

---

## Pre-chunk hygiene

| Artifact | Path | UTC timestamp |
| --- | --- | --- |
| Git tag | `v-pre-d` → `8b…` (created 2026-05-25T09:10Z, local-only) | 2026-05-25T09:10Z |
| Mongo dump | `/app/backup/pre_d_20260525T091055Z/` (66 MB) | 2026-05-25T09:10:55Z |

Note: tags are local-only. `git push origin v-pre-d` requires the user's "Save to Github" feature.

---

## Scope (verbatim from user brief)

1. **Trust Center session view** — small inline help/info affordance next to the headline `de_id_summary` numbers. Plain-English copy. Lucide-react `Info` icon → Popover. DOM-unconditional.
2. **Per-turn drill-down inline note** — one-liner below the per-turn table.
3. **Methodology doc** — `/app/memory/sprints/TRUST_CENTER_METHODOLOGY.md`.
4. **Backend** — zero changes.

---

## Files changed

| File | Change |
| --- | --- |
| `frontend/src/pages/TrustCenter.jsx` | (a) added `Info` to lucide-react imports; (b) added `Popover/PopoverTrigger/PopoverContent` import from `../components/ui/popover`; (c) extended the `Counter` component to accept an optional `infoSlot` prop rendered inline with the label; (d) new `DeIdSummaryInfoPopover` component (DOM-unconditional trigger button); (e) "Identifiers shielded" Counter now passes `infoSlot={<DeIdSummaryInfoPopover />}`; (f) new `tc-perturn-deviation-note` div under the "Per-turn detail" heading. |
| `memory/sprints/TRUST_CENTER_METHODOLOGY.md` | NEW — authoritative reference for the methodology, with stable keyphrase anchors and standards mapping. |
| `backend/tests/test_d_trust_center_deidsummary_note.py` | NEW frontend wire test. |

**Backend files touched: 0.** Verified by `git diff --name-only HEAD backend/` (only the new test file under `backend/tests/`). No change to:
- `services/synisense/deidentifier.py`
- `services/synisense/canonical.py`
- `services/synisense/audit.py`
- `routers/trust_center.py`
- `services/trust_center.py`
- any other guardrail surface.

---

## Final wording (slight refinement from user draft — documented for review)

### Popover content (testid: `tc-deidsummary-info-content`)

Heading line: **"How this count is built"**

Body (two paragraphs):

> Session totals count every place Shield touched data — including historical context and grounding replay for this session. Per-turn totals below count only what Shield processed at each specific turn.
>
> Both views are factually accurate to their question; expect the session total to be a superset of the sum of per-turn counts.

### Per-turn drill-down inline note (testid: `tc-perturn-deviation-note`)

> Per-turn counts. Session totals above may be larger because they include historical context and grounding replay.

### Refinements vs. the user's draft

| Source phrase (user draft) | Final phrase | Why |
| --- | --- | --- |
| "Session totals count every place Shield touched data — including historical context **and grounding material replayed for this session**." | "…including historical context **and grounding replay** for this session." | Compactness; matches TrustCenter voice ("Trust Center is factual reporting" header comment). "Grounding replay" is the audit-anchor phrase reused everywhere else. |
| "Both views are **accurate to their question**" | "Both views are **factually accurate** to their question" | Aligns with the page's existing self-description "Trust Center is factual reporting" so the auditor reads the same voice throughout. |
| (per-turn) "Per-turn counts. Session-level totals **at the top** may be larger because they include historical context **+ grounding replay**." | "Per-turn counts. Session totals **above** may be larger because they include historical context **and grounding replay**." | "Above" reads more naturally than "at the top" in a scrolling page; "and" instead of "+" for prose tone. |

All three key-phrase anchors the tester needs (`"session totals"`, `"per-turn"`, `"superset"`) are preserved verbatim. Two additional anchors (`"historical context"`, `"grounding replay"`) are also preserved for stable assertions.

**Please flag during the verification pass if any of the refinements drift.** I held the audit-anchor phrases stable and only adjusted around them.

---

## Tests

### Frontend wire (`tests/test_d_trust_center_deidsummary_note.py`)

| Test | Asserts |
| --- | --- |
| `test_info_button_testid_present` | `data-testid="tc-deidsummary-info-button"` renders unconditionally |
| `test_info_popover_content_testid_present` | `data-testid="tc-deidsummary-info-content"` is present in source |
| `test_info_popover_contains_audit_anchor_keyphrases` | Popover body contains all 5 anchors: `Session totals`, `per-turn`, `superset`, `historical context`, `grounding replay` |
| `test_info_button_renders_dom_unconditionally` | The button does NOT live behind a `&& (...)` conditional gate in source — guards the T2.3 DOM-unconditional rule |
| `test_perturn_deviation_note_testid_present` | `data-testid="tc-perturn-deviation-note"` is present |
| `test_perturn_deviation_note_contains_audit_anchors` | Per-turn note contains `Session totals above`, `historical context`, `grounding replay` |
| `test_perturn_note_renders_dom_unconditionally` | The per-turn note is NOT gated by a conditional render |
| `test_no_guardrail_files_changed_under_backend` | `git diff --name-only HEAD~1` (with a sane fallback) confirms only `services/work_studio_overlay.py`, `routers/cycles.py`, `scripts/seed_backlog_b_demo.py`, and `tests/test_d_*` + `tests/test_backlog_b_*` are present — no Shield/Trust-Center backend writer touched |
| `test_lucide_info_imported` | `Info` is in the lucide-react import block (import-survival guard per closeout §5.6) |
| `test_popover_components_imported` | `Popover`, `PopoverTrigger`, `PopoverContent` are imported from the shadcn ui module |

---

## Run results

(Populated below as each item is verified.)
