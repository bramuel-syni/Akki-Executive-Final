# Runbook 01 — Solva SSE stream stalls mid-session

**Sprint:** P1 κ (2026-02)
**Owner:** on-call backend
**Severity:** SEV-2 (degraded UX, session unusable)
**Last drilled:** never (TODO: first drill 2026-03)

## Detection signals

| Signal | Where |
|---|---|
| User reports "the answer just stopped" | Inbound email / Slack `#help` |
| `/api/solva/sessions/{sid}/v2/stream` p95 TTFB > 30s | Sentry performance dashboard |
| `solva_v2_stream_stalled` event count > 5/hr | Backend logs |
| SSE connection close before final `event: complete` frame | Frontend `useReasoningStream` hook telemetry |
| Mongo `solva_v2_sessions.status = 'streaming'` count climbing | Periodic check |

## First 3 mitigation steps

1. **Identify the stuck sessions.** Run:
   ```bash
   API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
   # Sessions stuck in 'streaming' for >5 min
   ```
   Or against Mongo directly:
   ```python
   from datetime import datetime, timedelta, timezone
   cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
   stuck = list(db.solva_v2_sessions.find({
       "status": "streaming",
       "started_at": {"$lt": cutoff},
   }))
   ```

2. **Mark stuck sessions as failed.** For each `sid` in `stuck`:
   ```python
   db.solva_v2_sessions.update_one(
       {"id": sid},
       {"$set": {"status": "failed", "failure_reason": "sse_stream_timeout"}},
   )
   ```
   Users can re-start; their evidence isn't lost (audit log persists).

3. **Check the LLM router queue.** If LLM provider is the bottleneck:
   ```bash
   tail -200 /var/log/supervisor/backend.*.log | grep -E "llm_router|provider_quota|rate_limit"
   ```
   If LLM provider is exhausted, jump to Runbook 03 (LLM key exhaustion).

## Escalation path

- **First 15 min:** on-call engineer
- **15-30 min:** notify product owner via Slack `#incidents`
- **30+ min:** open a Sentry incident; consider posting on the public
  status page (see `P1_iota_status_page_proposal.md`)

## Post-incident checklist

- [ ] All stuck sessions cleared / marked failed
- [ ] Affected users notified by email (if email contact known)
- [ ] Root cause traced — was it LLM provider? Mongo slow query?
      In-process SSE buffer leak?
- [ ] Telemetry signal added to Sentry / monitoring dashboard if
      novel cause
- [ ] Runbook updated if new mitigation step discovered
- [ ] If user-facing, post-mortem published to `/legal/incidents`
      (once that surface exists)
