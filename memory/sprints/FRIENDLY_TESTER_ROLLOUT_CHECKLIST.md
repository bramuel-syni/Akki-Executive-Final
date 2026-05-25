# Friendly-Tester Rollout Checklist

**Audience:** the operator running a controlled rollout of the onboarding flow to 5–10 friendly testers.
**Status at 2026-05-25:** ready to invite. Onboarding has never been seen by real users — this checklist closes that gap.
**Source artefacts referenced:** `HARDENING_LOG.md` (Steps 1–4), `PUSH_READINESS.md`, `AKKI_ONBOARDING_SPEC.md` v1.1, `T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md`.

---

## 1. Pre-rollout checklist

Run these checks before sending a single invite. Each check has a clear pass-state — if any fails, fix before inviting.

| # | Check | How | Expected pass-state |
| --- | --- | --- | --- |
| 1.1 | ClamAV daemon state in prod | `GET https://<prod-host>/api/healthz/clamav` | `clamd_daemon: "alive"` AND `clamd_ping_response_ms` is a small positive number (typically <100ms). If `"unreachable"` — clamd sidecar is down in prod; uploads will silently bypass per dev-bypass branch in `clamav_service.py`. **DO NOT invite testers until clamd is up.** |
| 1.2 | Demo seeds applied on test/preview pods | `tail -n 200 /var/log/supervisor/backend.err.log \| grep seed_backlog_b_demo` | Log line: `seed_backlog_b_demo: seeds present, skipping (rows=N, delta=0)` — confirms the Step 3 boot hook fired. Restart the pod once to capture the line. |
| 1.3 | All 18 sprint tags pushed | Trigger "Save to GitHub" in the Emergent chat input, then check `git fetch --tags origin && git tag -l` on the remote. | All 18 tags from `PUSH_READINESS.md` §2 visible on origin. |
| 1.4 | Mongo snapshot | `mongodump --uri="$MONGO_URL" -d "$DB_NAME" -o /app/backup/pre_friendly_tester_$(date -u +%Y%m%dT%H%M%SZ)/` | Backup dir non-empty (~80 MB). Tags the rollback point. |
| 1.5 | Pytest baseline | `cd /app/backend && python -m pytest -q --no-header --tb=no` | `1248 passed · 453 skipped · 1 failed (pre-existing requirements-guard)`. Any other deviation → investigate before inviting. |
| 1.6 | Onboarding spec lock | `head -5 /app/memory/AKKI_ONBOARDING_SPEC.md` shows `v1.1`. | Spec version matches the deployed build. |

---

## 2. Tester invite template

Send via your usual email / DM channel. **Do not over-explain** — the testers are doing you a favour; respect their time. Copy-paste, edit `{{NAME}}` + the signup URL only.

```
Hi {{NAME}},

I'm running a small preview round of Akki, a calm board-intelligence
companion. You're one of ~10 people I'm asking — would love your
read on the first 10 minutes.

Sign up here: https://akki-executive.preview.emergentagent.com/signin

A few things to know:
  • Preview build — billing is "Coming Soon", you won't be charged.
  • PII you type into the intake gets de-identified before storage
    (Shield). You can see what was redacted in the Trust Center.
  • The most useful feedback is: where you got stuck, where the
    copy felt off, and anything that didn't behave like you'd
    expect.

If anything breaks, just reply to this email with what you saw —
ideally a screenshot if it was visual.

Thanks,
{{YOUR_NAME}}
```

Keep it short. The testers will skim it.

---

## 3. Per-stage watch-list — what's most likely to break

For each onboarding stage, here are the failure modes a real user is most likely to surface. Most have been tested in pytest / e1_tester, but real users always find edges we miss.

### Stage 1 — Sign-up
- Verification email deliverability (if wired) — check spam folder on a fresh Gmail/Outlook account.
- Duplicate-email handling — second signup with same email should 400, not silent-create.
- Password validation edge cases — unicode passwords, very long passwords, passwords with quotes.
- Tester arrives from a previous Akki session with `localStorage` still set → confirm sign-out flow before sign-in works.

### Stage 2 — Intake (3 questions)
- PII in answers — paste an email, SSN, phone, or PAN into the Q3 "top of mind" field. After submit, open Trust Center → de-id summary should show the value as a `[[ENT_*]]` token, NOT the raw text. **This is the highest-priority Shield invariant.**
- Empty Q3 (whitespace only) — should reject gracefully, not 500.
- Browser back button mid-intake — should preserve typed answers (UX nicety, not invariant).
- Q2 primary-context name conflicts — what happens if the tester types a name that matches an existing context? (Should auto-create a fresh context, not attach to existing.)

### Stage 3 — Doors (cycle · upload · solve · demo)
- Each door must land on a real surface — manually click all 4 doors with different tester accounts.
- `FirstSessionGuard` redirect loops (the J2.3 class of bug) — after taking a door, refresh the page on the destination surface. Should stay there, NOT bounce back to `/app/first-session`.
- Demo door — confirms a demo context is attached on first click. Second click on the demo door should be idempotent (no duplicate attach).

### Stage 4 — First doc upload
- ClamAV behavior in prod (1.1 above) — upload an EICAR test signature file. Should reject with the G24 verbatim 400 toast. If clamd is `unreachable`, the file is silently accepted under the dev-bypass branch — this is a production concern.
- File size — try a 26 MB file (above the `CLAMAV_MAX_FILE_SIZE_BYTES` 25 MB preflight). Should reject with the G25 verbatim 413 toast.
- File type — try a `.exe` or `.bat`. Should reject.
- Empty file (0 bytes) — should reject with the G24 verbatim 400 toast.

### Stage 5 — Trust Center tour
- Copy renders correctly — em-dashes (`—`) MUST NOT regress to hyphens (`-`). Quote marks render as `"..."` not `&quot;`. Apostrophes render as `'` not `&#x27;`.
- Dismiss button persists — close the tour, refresh the page, tour does NOT re-open.
- Tour anchors point to real elements — each of the 3 stops should highlight a real on-page element, not float off-screen.

### Stage 6 — First Akki Chat / Solva session
- G30 starter prompt — the chat composer pre-populates with the user's Q3 answer. **CRITICAL:** raw PII (an email the tester typed into Q3) MUST NOT appear in:
  - The URL bar (no `?starter=ceo@example.com` — should be `?starter=...[[ENT_EMAIL_*]]...`).
  - The composer DOM (`document.querySelector('textarea').value` should show the de-identified value).
  - Any network request payload.
  - The browser console.
- G29 Help tooltip — verbatim copy *"Tap Help any time. Akki has a built-in tour of every screen."* — no typos, no rephrasing.
- G31 DOM-unconditional — open browser DevTools, search HTML for `data-testid="help-tooltip"` BEFORE clicking anything. Element MUST exist with `data-tooltip-visible="false"` (the visibility flips via the attribute, not via `&& (...)` conditional render).

---

## 4. What to capture on every reported issue

Tell testers (or capture yourself when triaging):

1. **Browser console output** — instruction: *"Open DevTools (F12 or Cmd-Opt-I), Console tab, take a screenshot of any red errors BEFORE clicking anything else."* The console state at the moment of failure is the highest-signal artefact.
2. **Browser URL bar** — the full URL when the issue happened. Paste verbatim, don't summarise.
3. **Account email** — so the operator can correlate to backend logs (`grep <email> /var/log/supervisor/backend.err.log`).
4. **The exact step that triggered it** — *"I clicked Cycle, the page loaded, I refreshed, then it sent me back"* is much more useful than *"the cycle page is broken"*.
5. **Screenshot if visual** — even a phone-photo of the screen is better than a textual description for layout issues.

---

## 5. Operator triage decision tree

When a tester reports an issue, classify it FIRST, fix SECOND.

| Symptom | Priority | First action |
| --- | --- | --- |
| `ReferenceError` or `TypeError` in console | **P0** | Surface to dev immediately. Pattern: B3-class missing-import (Step 2 §2.G/H) or J2.3-class stale-state (Step 2 §S2.B/C/D). Run `npm run build` locally to reproduce; the new `react/jsx-no-undef` + `no-undef` ESLint rules should have caught it but may have slipped. |
| **PII leak** — raw email / SSN / PAN / phone appears anywhere visible to the user (URL, DOM, console, network panel) | **P0 CRITICAL — STOP THE ROLLOUT** | Halt invites. Surface to dev with the leak surface (URL? DOM? log?). Shield invariant breach. Likely root cause: a code path that consumed `top_of_mind` before G18 redaction, OR a G30-style seed forwarding the wrong field. |
| `404` from a known route | **P1** | Check the route exists in the deployed build (`/api/healthz/clamav` style probe). Likely root cause: env-specific config drift (missing router include, mis-set base URL). |
| `403` from a route the tester should have access to | **P1** | Check `account.is_superadmin` if it's an admin route; check `context_id` membership if it's a context-scoped route. |
| `500` from any route | **P1** | Read backend logs: `grep <correlation-id-or-route> /var/log/supervisor/backend.err.log`. Look for an unhandled exception stack. |
| Verbatim copy drift — em-dash regressed to hyphen, wrong toast wording, missing space | **P1** | Code-level fix. The verbatim spec lives in `AKKI_ONBOARDING_SPEC.md`; cross-check the offending file. |
| `FirstSessionGuard` redirect loop (tester says *"I keep getting sent back to the intake page"*) | **P1** | J2.3-class bug. Check the writer endpoint at fault — does it call `bootstrap()` from `AuthContext` AFTER the auth-mutating POST? Step 2 §S2.B/C/D covers the 3 known sites; new redirect loops likely indicate a 4th site needing the same fix. |
| "I'm stuck" / UX confusion without an actual error | **P2** | Log for UX iteration, NOT a code fix. Aggregate into the post-rollout `FRIENDLY_TESTER_FINDINGS_*.md` Recommendations section. |
| Tester gives up before completing intake | **P2** | Most valuable signal in the whole rollout — the FRICTION FUNNEL. Capture where they dropped off. Don't fix individually; aggregate to find the worst step. |

---

## 6. Post-rollout closeout

After the tester batch is done (a week is usually enough for 5–10 testers):

1. **Tag the post-rollout state** — `git tag v-post-friendly-tester-batch-1 -m "post tester batch 1, $(date -I)"` (local-only; push via "Save to GitHub" if you want it on origin).
2. **Snapshot Mongo** — `mongodump --uri="$MONGO_URL" -d "$DB_NAME" -o /app/backup/post_friendly_tester_$(date -u +%Y%m%dT%H%M%SZ)/`. Compare row counts with the pre-rollout snapshot from §1.4 to see real-user traffic shape.
3. **Aggregate findings** — write `/app/memory/sprints/FRIENDLY_TESTER_FINDINGS_<YYYYMMDD>.md`. Sections:
   - **Counts by priority** — `P0: N · P0-CRITICAL: N · P1: N · P2: N`. If `P0-CRITICAL > 0`, this is the pivotal data point — don't widen until 0.
   - **Top 3 friction points** — from the P2 funnel. The thing 6/10 testers stumbled on is the thing to fix next.
   - **Verbatim copy drift inventory** — every regressed em-dash / quote / spec-string. One-line each. Send to dev as a batch.
   - **Verdict** — `READY TO WIDEN` (P0 = 0, P1 ≤ 2 minor) or `ANOTHER PASS NEEDED` (anything else).
4. **Decide widening** — if VERDICT = `READY TO WIDEN`, send the same template to the next 25 testers. If `ANOTHER PASS NEEDED`, fix the surfaced items first, re-run the 5–10-tester batch, repeat.

---

## 7. Quick references

| Need | Where |
| --- | --- |
| Signup URL | `https://akki-executive.preview.emergentagent.com/signin` |
| Prod ClamAV probe | `GET /api/healthz/clamav` (anonymous; Step 1 endpoint) |
| Backend logs | `/var/log/supervisor/backend.err.log` + `backend.out.log` |
| Onboarding spec (verbatim copy source of truth) | `/app/memory/AKKI_ONBOARDING_SPEC.md` v1.1 |
| Step-by-step hardening history | `/app/memory/sprints/HARDENING_LOG.md` |
| Sprint-tag inventory | `/app/memory/sprints/PUSH_READINESS.md` §2 |
| Mongo backup directory | `/app/backup/` |
| Shield de-id surface (operator-readable) | The Trust Center page (`/app/trust-center`) within the deployed app |

---

**Status:** ready for first-batch invite. The onboarding flow is code-verified (1248 passing tests across 18 sprint tags) but real-user-verified zero. This checklist closes that gap by giving you a structured way to find what the test suite couldn't.
