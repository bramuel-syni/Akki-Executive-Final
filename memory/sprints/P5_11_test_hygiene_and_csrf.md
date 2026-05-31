# P5.11 — Test hygiene + Notify gating + MX verification + Sister CSRF fixes

**Date:** 2026-02-23 · fork-resume on the live preview cluster
**Status:** Slices .1, .2, .4 SHIPPED to disk on preview · slice .3 (MX inbound) diagnosed: **HUMAN_REQUIRED — SendGrid console step**
**Sister surfaces:** marketing sensitivity demo, sandbox session create/delete
**ANTIFORGET PROTOCOL:** acknowledged. No subagents. Raw scripts in `/tmp` + `/app/scripts` only. Solva v1 untouched.

---

## Checkpoint table

| Slice | Status | Notes |
| --- | --- | --- |
| P5.11.1 — cleanup script | ✅ SHIPPED + executed `--apply` on preview | 107 rows purged across 5 collections |
| P5.11.2 — notify gating | ✅ SHIPPED | `COHORT_NOTIFY_DISABLED` env honoured in 3 send paths; pytest auto-sets it |
| P5.11.3 — MX inbound probe | ❌ FAIL — definitive root cause identified | **HUMAN_REQUIRED**: SendGrid Inbound Parse host registration |
| P5.11.4 — sister CSRF fixes | ✅ SHIPPED + live-verified | 403 → 200 on sensitivity-demo; 403 → 400 (schema) on sandbox |
| Cross-cutting | v1 byte-identical guard green · voice-lint clean · 53/53 lockdown tests green · Chat happy-path STILL green |

---

## P5.11.3 — MX inbound probe result

```
MX_INBOUND_FAIL no_inbound_received_within_120s
sendgrid_status=202
sendgrid_x_message_id='fylcEeTIRNePRvVX8x3YKw'
inbound_domain_mx='10 mx.sendgrid.net.'
last_admin_inbox_status=200
last_admin_inbox_body='{"items":[],"total":0,"limit":5,"skip":0}'
```

### Stage-by-stage diagnosis

| Stage | Check | Status |
| --- | --- | --- |
| 1. SendGrid outbound API | `POST /v3/mail/send` → status 202, X-Message-Id minted | ✅ |
| 2. DNS MX record | `dig MX inbound.akki.syni.ai` → `10 mx.sendgrid.net.` | ✅ |
| 3. SendGrid receives the inbound | We cannot directly probe (Parse API requires admin scope; our key has `mail.send` only) | ❓ |
| 4. SendGrid Inbound Parse webhook fires | No POST to `/api/inbound/sendgrid` for the probe address in 120 s | ❌ |
| 5. Backend `/api/inbound/sendgrid` accepts + stores | **Direct curl probe with HTTP Basic auth → 200 + row written to `admin_inbox_messages` in ~80 ms.** Chain works. | ✅ |
| 6. Admin inbox list endpoint | `GET /api/admin/inbox/messages?q=` returns the row instantly | ✅ |

Stage 4 is the breaking link. Stage 5 was independently verified by a one-shot curl with the live `SENDGRID_INBOUND_AUTH_USERNAME`/`_PASSWORD` Basic credentials, which **did** land an `admin_inbox_messages` row (id `b538081fcf7648a39e4c5c5d6e3d314d`, routing_result `pending`, provider `sendgrid`). So the storage path is intact end-to-end — the gap is upstream at SendGrid.

### Root cause (best-evidence inference)

**SendGrid Inbound Parse webhook is NOT registered for host `inbound.akki.syni.ai` in the SendGrid console.** Symptoms align:

- DNS MX is correct → SendGrid's MTA receives the message.
- No Parse host registration → the MTA has no destination URL to POST to.
- Result: the message is silently dropped (or bounced upstream — but no NDR returned because the sender is also `*@syni.ai` which has its own MX at Outlook).
- The webhook receiving end (`/api/inbound/sendgrid`) is therefore never hit, and our log buffer for that path is empty for the probe id.

### Fix (HUMAN_REQUIRED, ~3 minutes in SendGrid UI)

1. Sign in to `https://app.sendgrid.com`.
2. **Settings → Inbound Parse → "Add Host & URL"**.
3. **Receiving Domain**: `inbound.akki.syni.ai`
4. **Subdomain**: leave blank (the MX is on the apex of this host).
5. **Destination URL**: `https://akki.syni.ai/api/inbound/sendgrid`
   (preview equivalent: `https://akki-executive.preview.emergentagent.com/api/inbound/sendgrid`)
6. Check **"POST the raw, full MIME message"** (gives us the source body for the audit trail).
7. **Save**.
8. **Verify**: re-run `python3 scripts/probe_inbound_mx.py` — the script prints `MX_INBOUND_OK <message_id>` within 5–30 seconds.

### Alternative routes if (3) ever returns FAIL again

- If SendGrid says **"delivered to inbound parse"** in `https://app.sendgrid.com/email_activity` but the inbox still has no row → backend storage path broke. Tail `/var/log/supervisor/backend.out.log` for `POST /api/inbound/sendgrid` 5xx.
- If SendGrid says **"bounced"** → the receiver MX (`mx.sendgrid.net`) rejected because no host registration; fix above.
- If SendGrid says **"deferred"** → transient queue delay; re-run probe in 5 minutes.

The probe script's auto-diagnostic output now prints the exact UI fix steps inline, so a future operator running the script after a regression sees the answer without reading this memo.

---

## P5.11.1 — Cleanup script

### Files

- `scripts/cleanup_test_pollution.py` (new, 250 lines)

### Live execution (preview Mongo, `--apply` mode)

```
# cleanup_test_pollution.py
# mode:        APPLY (DESTRUCTIVE)
# db_name:     akki_dev
# keep_after:  2026-05-31T18:17:16.525308+00:00

Targets matched:
  cohort_applications                20 row(s)
  cohort_magic_links                 16 row(s)
  cohort_waitlist                    17 row(s)
  admin_inbox_messages               35 row(s)
  cohort_application_audit           19 row(s)

Deleted:
  cohort_applications                20 row(s)
  cohort_magic_links                 16 row(s)
  cohort_waitlist                    17 row(s)
  admin_inbox_messages               35 row(s)
  cohort_application_audit           19 row(s)

Audit row appended to `admin_cleanup_audit`.
```

**Total: 107 pollution rows purged from preview Mongo.** One audit row inserted into a new `admin_cleanup_audit` collection (mode=`apply`, actor=`cleanup_script`, target counts + delete counts captured).

### Production command (DO NOT auto-run this phase)

```bash
# Connect via SSH or ops console to the production pod, then:
cd /app
python3 scripts/cleanup_test_pollution.py                          # dry-run first — verify the count
python3 scripts/cleanup_test_pollution.py --apply                  # destructive
# Or with a recency guard so only legacy data is touched:
python3 scripts/cleanup_test_pollution.py --apply --keep-after=2026-02-23T00:00:00Z
```

The script writes a `mode=dry_run` audit row on every read, so even the rehearsal leaves a trail in `admin_cleanup_audit`.

### Email-pattern catalogue

`@example.com` · `@example.org` · `@test.*` · `m0c-*@*` · `mx-probe-*@*` · `r1-tester@*` · `phasea-curl@*` · `*@inbound.akki.syni.ai`

### Subject-pattern catalogue (admin_inbox_messages only)

`^inbound test` · `^test \d+\b` · `^test$` · `\bmx-probe\b` · `^\[test\]`

Subject patterns are combined with the email-pattern requirement on the `from_email` field (belt-and-braces — a legitimate inbound whose subject happens to be "Test 12" will NOT be purged if the sender is real).

---

## P5.11.2 — Notify gating

### Files touched

| File | Change |
| --- | --- |
| `backend/services/cohort_email.py` | `_notify_disabled()` helper; checked first inside `_send_via_sendgrid` |
| `backend/routers/cohort_applications.py` | `_notify_founder` returns early if flag set, logs `cohort_application_notify_skipped` |
| `backend/routers/website.py` | Both `EARLY_ACCESS_NOTIFY_EMAIL` and `CONTACT_NOTIFY_EMAIL` paths skip when flag set |
| `backend/tests/conftest.py` | `os.environ.setdefault("COHORT_NOTIFY_DISABLED", "true")` at module load |

### Behaviour matrix

| Env state | Production / preview | Pytest session |
| --- | --- | --- |
| `COHORT_NOTIFY_DISABLED=unset` | Real sends to bramuel / mugwe.marion / akki@syni.ai | — |
| `COHORT_NOTIFY_DISABLED=true` | (never set in prod) | All 3 notify paths log + skip |

The flag is **not** documented in `backend/.env.example` — intentional. It exists exclusively in `conftest.py` so that opening a fresh fork agent automatically inherits the safe default. No CI plumbing or pod-template changes are required.

### Test coverage

`test_cohort_email_send_returns_test_mode_disabled_when_flag_set` mocks `sendgrid.SendGridAPIClient` and asserts:
- Return value: `{"status": "test_mode_disabled", "reason": "COHORT_NOTIFY_DISABLED"}`
- `SendGridAPIClient` constructor was called **0 times** (truly zero network setup).

Plus 4 source-strict tests asserting each notify code-path reads the flag BEFORE any send call site.

---

## P5.11.4 — Sister CSRF fixes

### Files touched

| File | Change |
| --- | --- |
| `frontend/src/sandbox/api.js` | Imports `ensureCsrfToken`; new `_csrfHeaders()` helper; both POST + DELETE inject `X-CSRF-Token` |
| `frontend/src/components/marketing/EnterpriseFeature.jsx` | Imports `ensureCsrfToken`; the `score()` fetch awaits the token and injects the header alongside `Content-Type` |

### Live verification on preview (post-deploy)

```
=== sensitivity-demo (with CSRF cookie + header) ===
status=200    [was: 403]

=== sandbox sessions (with CSRF cookie + header) ===
status=400    [was: 403 — now 400 because schema validation hits *next*]

=== Verify CSRF protection still applies WITHOUT the header ===
sandbox-no-csrf=403    [invariant: protection intact]
```

### Binary classification per the user's instruction

For each sister site I had to choose:
- **(a)** remove the CSRF allowlist entry now that the client sends the header, OR
- **(b)** leave as-is with a comment explaining why.

Result: **none of the three sites needed allowlist removal — they were NEVER in the allowlist.** The CSRF allowlist contains only the 6 paths it should contain:

```
/api/csrf
/api/billing/webhook/
/api/auth/oauth/google/callback
/api/auth/oauth/microsoft/callback
/api/inbound/sendgrid
/api/cohort/email-events/sendgrid
```

All three sister endpoints (`/api/sandbox-gen/*`, `/api/public/studio/sensitivity-demo`) are state-changing public POST/DELETE routes — exactly the surface CSRF is designed to defend. A new pytest invariant (`test_sister_endpoints_are_not_in_csrf_allowlist`) locks this in.

---

## Cross-cutting verification

### Pytest lockdown (53/53 green)

```
tests/test_solva_v1_unchanged.py                            4 passed
tests/test_phase_p5_10_audit_panel_direct_linkage.py        5 passed
tests/test_phase_p5_10_chat_resilience.py                  12 passed
tests/test_sprint_z1_qa_fixes.py                           15 passed
tests/test_phase_p5_11_notify_gating_and_csrf.py           17 passed   ← NEW (17 tests this phase)
─────────────────────────────────────────────────────────────────────
                                                            53 passed
```

### v1 byte-identical guard

```
tests/test_solva_v1_unchanged.py: 4 passed
```

### Voice-lint

```
voice_lint: clean across customer-copy surfaces.
```

### Chat happy-path Playwright trace (regression check)

```
[trace] /api/chats POST -> 200
[trace] /messages/stream 200 at +0.56s | body=''
[trace] stream complete? True at +2.18s
[trace] cancelled marker visible? False
[trace] audit-panel toggles in DOM: 1
[trace] shielding prose: 'No sensitive identifiers were detected in this turn.'
[trace] PASS — happy path green
```

P5.10 fix continues to hold after the P5.11 sister patches.

### Pre-existing flake notice (NOT caused by P5.11)

A broad `-k` pytest run across cohort + cycle + chat suites surfaced 3 failures in `tests/test_cycle_assignment_handoff.py` (`test_assign_rejects_both_ned_ids_and_cohort_id` and two siblings). The failures **disappear when the file is run in isolation** (`pytest tests/test_cycle_assignment_handoff.py` → 22/22 pass). Root cause: shared `env` fixture mutated by an earlier test in the broad-`-k` set leaks state into the assignment tests. **Pre-existing, not in P5.11 scope.** Flagged for a future stabilisation pass that isolates the fixture per test.

---

## Mongo backfill (DEFERRED, per user instruction)

The friendly-nudge "Mongo backfill for legacy pre-P5.10 cancelled rows whose `shield_audit_id` is null" is **parked**, not started. Will revisit after the user is happy with the current production redeploy state.

---

## Deliverables index

| Artifact | Path |
| --- | --- |
| Cleanup script | `scripts/cleanup_test_pollution.py` |
| MX probe script | `scripts/probe_inbound_mx.py` |
| New pytest lockdown | `backend/tests/test_phase_p5_11_notify_gating_and_csrf.py` |
| This memo | `memory/sprints/P5_11_test_hygiene_and_csrf.md` |
| Chat happy-path Playwright (kept from P5.10) | `/tmp/p5_10_trace_happy_path.py` |
| Chat cancel-path Playwright (kept from P5.10) | `/tmp/p5_10_trace_cancel_path.py` |
