# Bug 27 + P4 rot fix + Tooltip — Combined dispatch
**Date:** 2026-02 (sprint, fork-resume)
**Scope:** P0 from QA sweep — Email Reply mode plumbing (bug 27 /
Fig 42), P4 cohort funnel test rot (2 pre-existing failures),
tooltip on /auth/set-password heading.
**Author:** main agent (autonomous; user instructed focused trio)

---

## Honesty Protocol — what shipped vs. what was claimed

### Item 1 (primary) — Bug 27 / Fig 42 — Email Reply mode plumbing

**Verbatim QA-doc text:** NOT FOUND in `/app/memory`. The
24-may-2026 QA aggregate (`memory/sprints/qa_24may2026/*.md` and
`*.docx`) contains no reference to "Task Manager bug 27", "Fig 42",
or "Email Reply mode". The handoff one-liner is the only surface
the agent has. **I surfaced this divergence BEFORE touching code**
per the No-Silent-Deviations contract.

**Ground-truth code trace (cited file:line):**

| Hop | File:Line | Behaviour |
|-----|-----------|-----------|
| 1. Inbound | `backend/routers/inbound_email.py:1472` | `@router.post("/sendgrid")` — multipart inbound parse |
| 2. Adapter | `inbound_email.py:1450` | normalizes to Postmark-shape dict |
| 3. Dispatch | `inbound_email.py:_dispatch_inbound_payload` | reads `MailboxHash` → branches |
| 4. Classifier | `mailbox_hash.startswith("task-")` | routes to `_handle_task_contributor_reply` |
| 5. Token resolve | `inbound_email.py:662` | `find_one({"token": …, "used": False})` |
| 6. Sender auth | line ~688 | rejects `from != row.contributor_email` |
| 7. Doc insert | line ~722 | inserts `documents` row per attachment with `origin="email_receipt"` |
| 8. Comment push | line ~746 | `$push contributor_comments { kind: "email_body", reviewer, comment, subject, doc_ids, created_at }` |
| 9. Team flip | line ~772 | `team[idx].status = "submitted"` |
| 10. Audit | line ~787 | `task.contribution.submitted_via_email` |
| 11. Reply | line ~830 | best-effort confirmation back to contributor |
| 12. **Read** | `routers/tasks.py:_sanitize_task` (109-132) | **DID NOT INCLUDE `contributor_comments`** |

**Classification (per your spec):** option **(c)** — write succeeded,
read-side adapter missed it. The data lands in MongoDB correctly
under `tasks.contributor_comments[]` with the full shape. The
right-rail audit feed shows the verb (`submitted_via_email`) but
NO body content. The Contributions tab in TaskDrawer shows only
the team-row status pill. The contributor's actual reply was
invisible to the task owner.

**Fix scope (strict, no creep):**
1. `routers/tasks.py::_sanitize_task` — surface
   `contributor_comments[]` on the wire.
2. New helper `_sanitize_comments(rows)` — strips `_id`, trims
   bodies to 4000 chars defensively, sorts most-recent-first,
   normalises the shape across both write paths (`kind:
   "email_body"` from inbound; `kind: "contributor"` from portal
   /comment).
3. `frontend/src/components/tasks/TaskDrawer.jsx::ContributionsTab`
   — renders the comments inline under each contributor's row
   (filtered by `reviewer.toLowerCase() === m.email.toLowerCase()`)
   with: kind chip + timestamp + subject + body text + attached
   doc count. Voice-lint clean. Data-testids:
   `task-drawer-contributions-comment-{i}-{c.id}`,
   `…-comment-kind-{i}-{c.id}`,
   `…-comment-subject-{i}-{c.id}`,
   `…-comment-body-{i}-{c.id}`,
   `…-comment-docs-{i}-{c.id}` plus
   `data-comment-kind="email_body|contributor"` on the row.

**What I did NOT touch (no scope creep):**
- The inbound classifier, the token resolver, the sender check,
  the document-write loop, the team-status flip, the audit, the
  confirmation reply, the email-issuance side, or the inbound
  webhook URL config.
- The portal `/contribute/<token>/comment` write — already pushes
  with `kind="contributor"`, surfaces automatically with the same
  read-side change.

**Lockdown tests:** `backend/tests/test_bug27_email_reply_plumbing.py` — 7 tests:
1. Source-strict: `_sanitize_task` surfaces field; `_sanitize_comments` helper exists.
2. Inbound writer still pushes to `contributor_comments` (regression guard).
3. End-to-end ingestion + read round-trip — payload → handler → DB
   → owner sees body + subject + status flip.
4. `_sanitize_task` direct call confirms the FE-facing shape +
   most-recent-first sort.
5. Sender-mismatch silently dropped (no comment push, no team
   flip).
6. Cross-tenant isolation — token A's reply CANNOT land on a
   like-named task under tenant B (both rows seeded; comment
   count asserted at 1 + 0).
7. Attached docs surface under `doc_ids` and the underlying
   `documents` row exists with `origin in (email_receipt,
   akki_generated)`.

**Raw Playwright traces (NO generic testing subagents):**
- `/tmp/bug27_fe_trace.py` — admin sign-in → Task Manager →
  drawer Contributions tab → comment row mounts with
  `data-comment-kind="email_body"` + body + subject + doc count
  visible at 4 viewports. **4 × 5 = 20/20 PASS.**

### Item 2 (bundle) — P4 cohort funnel test rot

**Repair option chosen:** Option (a) — `conftest.py` adds
`COHORT_EMAILS_ENABLED=false` for the test session. Reasoning:
- P1-B's own tests use `monkeypatch.setenv` to control the flag
  per-test, so they're unaffected by the conftest default
  (monkeypatch wraps + restores). Verified by running
  `tests/test_p1_b_cohort_approval_email.py` in isolation → 4/4
  PASS.
- The 2 P4 tests in question assert the legacy `flag_off` shape;
  flipping the conftest default restores that shape without
  touching any P4 assertion line.
- Production is unaffected: production reads `backend/.env`,
  preview still has `COHORT_EMAILS_ENABLED=true` from P1-B.
- Option (b) — updating the 2 P4 assertions — was rejected
  because it widened the assertion (any-safe-terminal-status)
  which loses signal on real regressions.

**Change:** ONE line added to `backend/tests/conftest.py` (plus a
multi-line comment block citing P1-B):
```python
os.environ["COHORT_EMAILS_ENABLED"] = "false"
```

Verified: `test_p4_a_receipt_flag_off_logs_redacted` and
`test_p4_b_decline_writes_audit_and_skips_email_when_flag_off`
both PASS in the new broad sweep. **P4 file: 14/14.**

P1-B coverage unaffected: `tests/test_p1_b_cohort_approval_email.py`
4/4 in the same broad sweep.

### Item 3 (bundle) — Tooltip on /auth/set-password heading

**Heading-only enhancement.** No form fields, no button copy, no
submit flow changes (locked in by `test_form_fields_button_copy_and_flow_unchanged`).

Reused the existing shadcn `Tooltip` primitive
(`frontend/src/components/ui/tooltip.jsx`) — no new dependency.
Imported `HelpCircle` from `lucide-react` (already in deps).

Verbatim copy: **"Akki uses your password as a fallback if your
Google or Microsoft account becomes unreachable."**

A11y wire:
- Heading carries `id="set-password-heading-text"`.
- Trigger has `aria-label="Why am I being asked to set a
  password?"` and `aria-describedby="set-password-heading-text"`.
- Content carries `role="tooltip"` + verbatim copy +
  `data-testid="set-password-tooltip-content"`.
- Trigger focus-visible ring uses
  `var(--oxblood)` (theme-consistent).

**Lockdown tests:** `backend/tests/test_set_password_tooltip.py`
— 5 source-strict tests:
1. Reuses existing shadcn module; no new tooltip library.
2. Heading id present.
3. Trigger has aria-label + aria-describedby + data-testid.
4. Content carries role="tooltip" + verbatim copy.
5. Form fields, button copy, and flow unchanged.

**Raw Playwright a11y trace:** `/tmp/item3_tooltip_trace.py` —
gated user signs in → bounce to /auth/set-password → tooltip
trigger visible → a11y wiring asserted → hover shows verbatim
copy → keyboard focus also opens the content at 4 viewports.
**4 × 5 = 20/20 PASS.**

---

## No silent deviations

1. **QA-doc text for Bug 27 / Fig 42 not found in
   `/app/memory`.** Surfaced above. Ground-truth defect identified
   via code trace; fix scoped strictly to the read-side break.

2. **Cross-test fixture state leak (`Future attached to a
   different loop`)** — pre-existing structural defer. Surfaces
   when `test_phase_p4_cohort_funnel.py` + `test_p1_b_*` run in a
   single pytest process AND interactions with `_run(coro)` create
   fresh event loops per call. **NOT touched** per your earlier
   explicit instruction ("leave it logged as structural/deferred").
   The broad sweep ordering used below (P4 → P1-B with adjacent
   files priming the loop) avoids the hot path; the 14/14 P4 + 4/4
   P1-B combo is green in the verbatim sweep.

3. **One pre-existing slow path** — individual P4 tests run
   ~120s each when invoked solo because each `_run(coro)` opens a
   fresh AsyncClient and motor reconnects. Full-file run finishes
   normally because the loop primes once. Not a regression from
   this dispatch — verified by `git stash` reproducer in the
   previous dispatch and re-confirmed here. No fix attempted.

---

## Verbatim sweep summary

```
153 passed, 22 warnings in 446.51s (0:07:26)
```

Files-touched (verbatim `git status --short`):
```
 M backend/routers/tasks.py
 M backend/tests/conftest.py
 M frontend/src/components/tasks/TaskDrawer.jsx
 M frontend/src/pages/SetPasswordRequired.jsx
?? backend/tests/test_bug27_email_reply_plumbing.py
?? backend/tests/test_set_password_tooltip.py
?? /tmp/bug27_fe_trace.py
?? /tmp/item3_tooltip_trace.py
```

Active bundle (17 files):
- test_solva_v1_unchanged
- test_admin_qa_hooks
- test_p0_c_oauth_session_ingestion
- test_p1_a_intel_to_pulse
- test_p1_b_cohort_approval_email (4/4 — flag unaffected by conftest)
- test_phase_r1_cohort_foundation
- **test_phase_p4_cohort_funnel** (14/14, was 12/14 — UP +2)
- test_phase_p5_5_session_reauth
- test_phase_s_password_reset
- test_home_cleanup_phase_f5
- test_c1_a_first_login_password_set (16/16 from C1-revised)
- test_c1_b_contributor_link_codes (10/10 from C1-revised)
- test_phase_r2_welcome_email
- test_phase_p3_1_csrf
- test_phase_p5_6_csrf_cookie_domain
- **test_bug27_email_reply_plumbing** (NEW, 7 tests)
- **test_set_password_tooltip** (NEW, 5 tests)

### Suite-size delta vs. prior dispatch baseline

Prior baseline (C1-revised close-out): **139 passing tests** for
the 15-file bundle.
This dispatch: **153 passing tests** for the expanded 17-file
bundle. Net new: **+14** (7 bug 27 + 5 tooltip + 2 P4 rot
unblocked).

Discipline gates:
- Solva v1 byte-identical guard: `4 passed, 15 warnings in 3.28s`.
- Voice-lint: `voice_lint: clean across customer-copy surfaces.`
- C1-revised Phase A Playwright trace: 24/24 PASS (re-confirmed).
- C1-revised Phase B Playwright trace: 28/28 PASS (re-confirmed).

---

## Production env actions

**None required for this dispatch.**

P1-B's `COHORT_EMAILS_ENABLED=true` in preview's `backend/.env`
remains as-is — production should continue setting it (or not)
per the email-on/off product decision. The conftest fix only
touches the in-process test env.

No new env vars.

---

## Resume contract

Trio closed clean. Pause for e1_tester re-verification before the
next phase per protocol. Remaining backlog (unchanged):
- 🟡 P8 SendGrid Inbound Parse webhook — BLOCKED on you
- 🟢 "Questions for you" page work — NEXT phase after this
- 🟢 P5.18 OAuth migration — BLOCKED on Google GCP creds
- 🔵 Future / backlog low (digest cadence, why-not-shown diff,
     re-target badge, Postmark history scrub deferred)
