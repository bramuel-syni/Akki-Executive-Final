# Runbook 04 — SendGrid delivery failure

**Sprint:** P1 κ (2026-02)
**Owner:** on-call backend
**Severity:** SEV-3 (cohort applicants don't get confirmation; founder doesn't get notify)

## Detection signals

| Signal | Where |
|---|---|
| `sendgrid_send_failed` in backend logs | `/var/log/supervisor/backend.*.log` |
| `python_http_client.exceptions.HTTPError` from sendgrid SDK | Backend logs |
| Founder notify emails (`bramuel@syni.ai`, `mugwe.marion@syni.ai`) not arriving | Inbox check |
| `password_reset_email_skipped: sendgrid_not_configured` log line | Backend logs |

## First 3 mitigation steps

1. **Confirm the key is set + valid.**
   ```bash
   grep -c "^SENDGRID_API_KEY=" /app/backend/.env
   API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
   # Trigger a test send (forgot-password is the simplest path)
   curl -s -X POST "$API_URL/api/auth/forgot-password" \
        -H "Content-Type: application/json" \
        -d '{"email":"juliusaopio@gmail.com"}'
   ```
   Check the SendGrid Activity dashboard for the resulting send.

2. **Check sandbox mode.** Pytest runs use `SENDGRID_SANDBOX_MODE=true`
   which silently DROPS sends. If production is misconfigured:
   ```bash
   grep "^SENDGRID_SANDBOX" /app/backend/.env
   ```
   If sandbox mode is True in production, flip to False + restart backend.

3. **Check SendGrid sender authentication.** All sends use the
   `info@syni.ai` from-address. If domain authentication or DMARC
   alignment is failing:
   - SendGrid → Settings → Sender Authentication → check syni.ai domain status
   - Confirm SPF + DKIM records still present on syni.ai DNS
   - Confirm DMARC policy isn't quarantining (`p=quarantine` with strict alignment)

## Escalation path

- **First 10 min:** on-call attempts steps 1-3
- **10-30 min:** if SendGrid account-level issue (suspension, quota),
  escalate to product owner — only they can resolve account billing
- **30+ min:** consider switching to SES or Postmark as fallback (no
  code change to switch sender — only env vars + library import; ~2 hours
  of work for full failover)

## Post-incident checklist

- [ ] Lost messages identified (cohort apps that didn't get notify)
- [ ] Manual catch-up sends issued where contact is known
- [ ] Sender authentication health-check added to status page
- [ ] SendGrid webhook (event notifications) configured to push
      bounces/spam-reports back to our backend for triage
- [ ] Per-day send quota review (free tier 100/day; paid tier scales)
