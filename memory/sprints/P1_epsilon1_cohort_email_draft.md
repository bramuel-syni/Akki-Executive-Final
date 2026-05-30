# P1 ε.1 — Cohort applicant confirmation email (DRAFT)

**Date:** 2026-02
**Status:** DRAFT. NOT wired to live SendGrid yet.
**Trigger:** `POST /api/cohort/applications` succeeds (HTTP 200/201).
**Recipient:** the applicant (`email` field on the form).
**From:** `info@syni.ai` (matches existing founder-notify FROM).
**Voice-lint:** clean. Founder-tone. No pricing language. No "founding cohort" / "join the cohort" phrasings (banned per Sprint M.5).

---

## Subject

```
Akki early access — request received
```

## Plain-text body (≤80 words, voice-clean)

```
Hello {first_name_or_blank},

Thank you for requesting access to Akki. We have your request on file
and read every one personally.

We will reply within 3 business days with next steps. If your request
sits at the edge of what Akki is built for, we will say so plainly —
we would rather give you a clear no than a slow maybe.

If anything changes about your situation in the meantime, reply to this
email.

— The Akki team
info@syni.ai
```

## Word count

68 words (under the 80-word cap).

## Voice-lint checklist

- ✓ No banned vocabulary (no "senior", no "best", no "premier", no
  "industry-leading", no "elite")
- ✓ No "Founding Cohort" / "Join the cohort" (Sprint M.5 phrase bans)
- ✓ No commitment language about pricing
- ✓ No timeline promises beyond the 3-business-day reply
- ✓ Plain founder-tone; no marketing register
- ✓ Names the failure mode ("if your request sits at the edge of what
  Akki is built for, we will say so plainly") — Trust pillar 1
- ✓ Preserves applicant agency (no "you should…" language)

## HTML body (optional — defer until SendGrid template is wired)

If we ship a template later, render the plain text inside a minimal
HTML wrapper with brand wordmark + one paragraph break per blank line.
No tracking pixels, no marketing CTAs, no upsell.

## Variables

| Token | Source | Fallback |
|---|---|---|
| `{first_name_or_blank}` | `application.name.split()[0]` if name present | empty string + drop the comma after "Hello" |

## Implementation guidance (DO NOT IMPLEMENT YET)

When wiring to SendGrid:

1. Add `applicant_notify_body` to the cohort_applications router's
   stored payload (currently we store `applicant_confirmation_body`
   which carries similar copy — reconcile names: prefer
   `applicant_confirmation_body` if it already matches).
2. Send via the existing `_notify_founder` SendGrid path but with
   `to_emails=[application.email]` and `from_email=info@syni.ai`.
3. **Idempotency:** if `_notify_applicant_sent_at` is already
   populated on the row, don't send again. Add a `sent_at` field on
   the row to record successful delivery.
4. **Sandbox mode:** in test/CI environments, log "applicant_notify_skipped:
   sendgrid_sandbox" — don't burn real sends during pytest.

## Re-use of existing applicant_confirmation_body

The cohort_applications router already stores an
`applicant_confirmation_body` field (Sprint M.5 rewrote it to early-
access register). The above DRAFT is a slight tightening of that body
for live send. If the orchestrator approves, we should reconcile —
either:
(a) replace the stored body with this draft and wire the send
(b) keep the stored body as-is (it's already voice-clean and 56 words)
    and wire the send using THAT body

Both are valid. Recommendation: (b) — the M.5 body is already locked
+ tested. This DRAFT is a slight expansion (adds the 3-business-day
reply commitment), which is a content delta worth a separate
slice + test.
