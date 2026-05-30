# Runbook 05 — OAuth callback failure (Google or Microsoft)

**Sprint:** P1 κ (2026-02)
**Owner:** on-call backend
**Severity:** SEV-2 (degraded sign-in; magic-link + password still work)

## Detection signals

| Signal | Where |
|---|---|
| `oauth_callback_failure` audit-log event | `chat_audit_log` collection |
| User reports "Microsoft sign-in just errored" | Inbound |
| `/api/auth/oauth/{provider}/callback` 4xx rate spikes | Sentry / backend logs |
| `state_jwt_invalid` / `pkce_mismatch` log entries | Backend logs |
| Microsoft Azure tenant: AAD sign-in failure events | Azure Portal → Enterprise Apps → Sign-in logs |

## First 3 mitigation steps

1. **Confirm the failure shape from the audit log.**
   ```python
   recent = list(db.chat_audit_log.find(
       {"event_type": {"$regex": "oauth"}},
       {"_id": 0, "event_type": 1, "details": 1, "created_at": 1}
   ).sort("created_at", -1).limit(20))
   ```
   Categorise: state JWT expiry (>10 min between start + callback),
   PKCE mismatch (browser cookie wiped), provider error (`?error=…`),
   ID token signature failure (clock skew or JWKS rotation).

2. **Verify the provider's authorize URL is fresh.** For Microsoft:
   ```bash
   API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
   curl -s "$API_URL/api/auth/oauth/microsoft/start?probe=1"
   # Expected: {"configured":true,"provider":"microsoft"}
   curl -s "$API_URL/api/auth/oauth/microsoft/start" | python3 -c "
   import sys, json
   d = json.load(sys.stdin)
   print('authorize_url shape OK?', 'login.microsoftonline.com' in d.get('authorize_url', ''))
   "
   ```
   For Google: same check on `/google/start`.

3. **Verify the redirect URI registered at the provider matches the
   constructed URL.** This is the #1 cause of OAuth callback failure
   after a tenant migration or env-var typo:
   - Microsoft (Azure Portal → App registrations → Authentication →
     Redirect URIs): must be **exactly**
     `https://akki-executive.preview.emergentagent.com/api/auth/oauth/microsoft/callback`
     (preview) or `https://akki.syni.ai/api/auth/oauth/microsoft/callback`
     (production).
   - Google (Google Cloud Console → APIs → Credentials → OAuth client):
     same shape, `/api/auth/oauth/google/callback`.
   - Compare the `MICROSOFT_OAUTH_REDIRECT_URI` env var with what the
     provider has registered. Mismatched → callback always fails.

## Escalation path

- **First 10 min:** confirm the failure category (state expiry vs
  provider config drift vs network)
- **10-30 min:** if config drift, escalate to whoever holds the
  provider tenant (likely the product owner)
- **30+ min:** disable the affected provider's button in
  `OAuthButtons.jsx` via a feature flag while config is restored;
  magic-link + password still work

## Post-incident checklist

- [ ] Provider config (redirect URI, client ID/secret expiry,
      tenant ID) verified
- [ ] State JWT TTL reviewed (currently 10 min — appropriate)
- [ ] JWKS cache TTL reviewed (Microsoft rotates keys daily; cache
      should auto-refresh on miss)
- [ ] Clock-skew tolerance confirmed (±5 min on `iat` / `exp`)
- [ ] PKCE cookie SameSite / HttpOnly settings verified (Lax + Secure;
      not None — would break the round trip)
- [ ] Audit-log retention period extended on `oauth_*` event types
      for forensic clarity
