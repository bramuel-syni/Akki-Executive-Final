# Runbook 03 — LLM key exhaustion / rate limit (Anthropic / OpenAI / Gemini)

**Sprint:** P1 κ (2026-02)
**Owner:** on-call backend
**Severity:** SEV-2 (Solva non-functional; cached UI still serves)

## Detection signals

| Signal | Where |
|---|---|
| `HTTP 429` from Anthropic API in backend logs | `/var/log/supervisor/backend.*.log` |
| `provider_quota_exceeded` event | Sentry / backend logs |
| Solva v2 session contract layer fails repeatedly | `solva_v2_sessions.status=failed` with `failure_reason=engine_layer_retry_exhausted` |
| EMERGENT_LLM_KEY balance low warning | Emergent platform dashboard |
| User reports "got an error halfway through" | Inbound |

## First 3 mitigation steps

1. **Check the key + provider status.**
   ```bash
   # Verify EMERGENT_LLM_KEY is set
   grep -c "^EMERGENT_LLM_KEY=" /app/backend/.env
   # Check provider status page (Anthropic / OpenAI / Gemini)
   ```
   If EMERGENT_LLM_KEY is exhausted: user must top up via Profile →
   Universal Key → Add Balance (or enable auto-top-up). Surface this
   to the product owner immediately — there's no engineering fix.

2. **Fail soft on new Solva starts.** Add a temporary feature-flag
   override that blocks `POST /api/solva/sessions/start` and returns
   503 with a clear "LLM provider temporarily unavailable; please try
   again in 15 min" message. Existing sessions in non-streaming state
   are unaffected.
   ```bash
   # Update feature flag in DB (or set env var SOLVA_V2_LOCKED=true + restart)
   ```

3. **Failover to alternate provider if available.** The Emergent LLM
   key auto-routes across Anthropic / OpenAI / Gemini for text
   generation. If one provider is the bottleneck, check the router
   config in `backend/services/llm_router.py` — confirm the failover
   chain is active and not pinned to a single provider.

## Escalation path

- **First 5 min:** confirm whether the issue is key exhaustion
  (cost) or provider outage (latency)
- **5-15 min:** if cost — escalate to product owner for top-up; if
  outage — disable Solva v2 starts via feature flag
- **15+ min:** post on public status page; email cohort applicants
  if it persists >1 hr

## Post-incident checklist

- [ ] EMERGENT_LLM_KEY auto-top-up enabled
- [ ] Provider failover chain verified (no single-provider pin)
- [ ] Rate-limit telemetry added to Sentry
- [ ] Per-account daily session quota considered (currently uncapped)
- [ ] Cost-control alert thresholds tuned
