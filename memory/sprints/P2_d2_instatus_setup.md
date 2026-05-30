# P2 D.2 — Instatus setup steps (2026-02)

**Status:** In-app `/status` page shipped. Instatus integration
gated on `INSTATUS_API_KEY` — not yet wired (out-of-scope for this
slice). This file is the operator playbook for the day Instatus
lands.

## What's shipped already

- Public `/status` page (`frontend/src/pages/StatusPage.jsx`) read
  by anyone, no auth.
- Backend `GET /api/health/composite` (cache 30 s) probing:
  - Mongo (live ping)
  - LLM key configured
  - SendGrid configured
  - Google OAuth configured
  - Microsoft OAuth configured
  - Solva engine module loadable
- Page polls every 60 s; manual refresh button visible.
- Overall state rolls up to `ok` / `warn` / `fail` (warn = any
  configured-but-not-exercised; fail = anything broken).

## Instatus integration steps (when ready)

1. **Create an Instatus account** at https://instatus.com — sign up
   with the team email.
2. **Add a status page** named "Akki Status". Slug → `akki`.
3. **Add components** mirroring the composite probes:
   - Database
   - Reasoning models
   - Email delivery
   - Google sign-in
   - Microsoft sign-in
   - Solva engine
4. **Copy the API key** from Settings → API.
5. **Set `INSTATUS_API_KEY` in `backend/.env`** and restart.
6. **Wire the bridge worker** (out-of-scope for this slice — needs a
   small recurring task, every 60 s, that posts the composite-probe
   result up to Instatus). Pattern:
   ```python
   for name, p in probes.items():
       requests.put(
           f"https://api.instatus.com/v1/{PAGE_ID}/components/{COMPONENT_IDS[name]}",
           headers={"Authorization": f"Bearer {INSTATUS_API_KEY}"},
           json={"status": _instatus_state(p["state"])},
       )
   ```
   where `_instatus_state(ok)='OPERATIONAL'`, `warn='UNDERMAINTENANCE'`,
   `fail='MAJOROUTAGE'`.

## Why hybrid

- The in-app `/status` page covers the "user is signed out and
  wants to know if Akki is up" case without external dependencies.
- The Instatus mirror covers the "Akki itself is down, and the page
  reading the in-app probe is therefore also down" case — Instatus
  hosts the bad-day surface on infrastructure independent of ours.

## Auth contract

The in-app `/status` route is intentionally PUBLIC. CSP allows
`fetch` to the same origin; no cookies required. The composite
probe endpoint does NOT require auth — it returns environment
configuration state (presence/absence of API keys) without ever
revealing the key values themselves.

## Verification

| Probe                                                       | Result |
|-------------------------------------------------------------|--------|
| `curl GET /api/health/composite` (no auth)                  | 200 OK, JSON shape verified ✓ |
| Overall=`ok` when all probes pass                           | ✓ |
| Solva engine probe locks on `services.solva_v2.feature_flag`| ✓ |
| Cached for 30 s                                             | ✓ |
| Frontend `/status` renders all six probe rows               | ✓ (smoke-tested live) |
