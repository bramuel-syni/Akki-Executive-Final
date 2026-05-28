# AKKI Deployment Notes (Emergent Platform)

> Reference doc surfaced on user request (2026-02 fork-resume). Tells the operator what to expect when promoting `akki-executive` from the preview environment into production.

## 1. Production URL pattern

Emergent issues production URLs on the **emergentagent.com** apex (no `preview.` subdomain). For the current project the deployed URL will surface as:

- **Preview (now):**   `https://akki-executive.preview.emergentagent.com`
- **Production:**      `https://akki-executive.emergentagent.com`

Both share the same Kubernetes ingress shape. The only string-level difference is the `preview.` subdomain dropping out. Your `REACT_APP_BACKEND_URL` env var becomes the production hostname in the production env.

## 2. How to deploy

Emergent provides **a single-click "Deploy" action** in the chat UI (next to "Save to GitHub"). The action runs the GitHub Actions workflow at `.github/workflows/deploy.yml` which:

1. Builds Docker images for backend + frontend
2. **NEW: runs the `deploy-check` job** — `pytest -m runtime_playwright` blocks on Phase Z-slice-6 + AA-slice-7 orthogonality regressions before the deploy step (added in Wave8.followup.3, 2026-02)
3. Pushes images to ACR
4. Deploys to the production VM
5. Smoke-tests the live URL

No CLI commands required from the operator. If the GitHub Actions workflow fails on `deploy-check`, the deploy will not proceed — fix the orthogonality regression first.

## 3. Custom domain (akki.ai or app.akki.ai)

Yes, custom domains are supported. Two paths:

### Option A — Apex domain (akki.ai)
Cloudflare/Route53/etc. → create an **A record** pointing `@` to the Emergent platform's edge IP. Emergent surfaces the exact IP in the deploy panel once production is live.

### Option B — Subdomain (recommended: `app.akki.ai`)
Cloudflare/Route53/etc. → create a **CNAME record** pointing `app` → `akki-executive.emergentagent.com`. Wait 5–30 minutes for DNS to propagate.

Then in the Emergent deployment panel, **add the custom domain** and Emergent will auto-issue a TLS cert via Let's Encrypt. Verify HTTPS resolves correctly before flipping traffic.

For the marketing site at `akki.ai` apex and the app at `app.akki.ai`, the standard pattern is:
- `akki.ai` → marketing landing (current `/` route, served from the same React SPA)
- `app.akki.ai` → app shell (auto-redirect `/` to `/app/today` for authenticated users)

Both can resolve to the same Emergent deployment — your `App.js` already handles route-based context switching.

## 4. Environment variables — production vs preview

Most env vars **carry over identically** from preview to production via Emergent's secrets manager. The handful that need explicit production values:

| Variable                       | Preview value              | Production value (you set)                 | Why |
|---|---|---|---|
| `REACT_APP_BACKEND_URL`        | preview URL                | `https://akki-executive.emergentagent.com` (or custom domain) | Frontend bakes this in at build-time |
| `MONGO_URL`                    | local k8s MongoDB          | **NEW**: production MongoDB Atlas connection string | Preview shares cluster; prod must be isolated |
| `DB_NAME`                      | `akki_dev`                 | `akki_prod`                                | Strict isolation |
| `SENDGRID_API_KEY`             | sandbox key                | **production-tier SendGrid key** w/ verified sender domain (`@akki.ai`) | Sandbox keys hit a recipient allowlist |
| `EMERGENT_LLM_KEY`             | shared dev key             | same (no change needed)                    | The universal key works in both envs |
| `JWT_SECRET`                   | dev secret                 | **rotated production secret** (64+ chars)  | Never reuse dev secret in prod |
| `JWT_REFRESH_SECRET`           | dev secret                 | **rotated production secret** (64+ chars)  | Never reuse dev secret in prod |
| `GOOGLE_OAUTH_CLIENT_ID`       | dev OAuth app              | **prod OAuth app** w/ production redirect URI added | Google requires explicit redirect URI registration |
| `GOOGLE_OAUTH_CLIENT_SECRET`   | dev secret                 | **prod secret** from the prod OAuth app    | Same as above |

Set these in Emergent's deployment panel **before** the first deploy. Missing env vars will fail fast (the backend has no fallback defaults).

## 5. Pre-deploy checklist

Run this list once before clicking "Deploy" the first time. Every item is fail-loud — if any of these are wrong, the deploy will surface the error immediately.

- [ ] **Tests green:** `cd /app && pytest backend/tests/ -q` shows zero failures (current baseline: 71/71 regression + 61/61 locked-sequence GREEN)
- [ ] **Deploy-check job green:** `make deploy-check` succeeds locally
- [ ] **No hardcoded URLs:** `grep -rn "localhost:" /app/backend/ /app/frontend/src/ --include="*.py" --include="*.js" --include="*.jsx"` returns only test files
- [ ] **No hardcoded env values:** No fallback defaults in `os.environ.get("X", "fallback")` — must fail fast on missing config
- [ ] **`/app/backend/.env`** is NOT committed (verified — `.gitignore` excludes it)
- [ ] **`/app/frontend/.env`** uses `REACT_APP_BACKEND_URL` only
- [ ] **Production MongoDB**: provisioned, accessible from the production VM's IP, **`akki_prod` collection initialised with `db.accounts` first superadmin** (use `python backend/scripts/seed_superadmin.py` against the prod connection string)
- [ ] **SendGrid sender domain verified**: `akki.ai` DNS records (SPF, DKIM, link tracking) live in the SendGrid console
- [ ] **Google OAuth production redirect URI**: `https://akki-executive.emergentagent.com/api/auth/google/callback` (and custom domain variant if applicable) registered
- [ ] **Anthropic / Emergent LLM budget**: ≥$10 remaining on the Universal Key (top up via Profile → Universal Key → Add Balance)
- [ ] **Phase X cron / scheduled task**: nothing scheduled today. Soft-deletes process when the admin manually hits `POST /api/admin/users/process-deletions`. If you want automatic processing, wire a cron via your platform of choice (Cloudflare Cron Trigger, Vercel Cron, or k8s CronJob) hitting that endpoint with a superadmin token once per day.
- [ ] **Backup**: production MongoDB has automated backup enabled (Atlas default — `M0/M2/M5` tiers have free continuous backup)

## 6. Post-deploy smoke

After the first deploy completes, verify these manually:

1. `https://akki-executive.emergentagent.com/` → marketing landing loads
2. `https://akki-executive.emergentagent.com/signin` → sign-in form loads
3. `POST /api/auth/login` with the prod superadmin → 200 + `access_token`
4. `GET /api/admin/users` with that token → 200 + user list
5. `GET /api/admin/tenants` → 200 (will be empty if `akki_prod` is fresh)
6. `GET /api/admin/extractions` → 200 (empty array on fresh DB)
7. Issue a test cohort invite via the new Invite Founder modal → magic link email lands
8. Click the magic link → activates the account → trial countdown starts

## 7. Rollback

Emergent supports **point-in-time rollback** from the deployment panel — pick any prior commit and click rollback. This is free and instant. Use this instead of `git revert` for production reversion.

For DB rollback (data corruption etc), restore from the Atlas continuous-backup snapshot at the moment before the incident.

---

_Maintained by the orchestrator. Last updated: 2026-02 fork-resume dispatch (Phase W.followup.1 + Invite Founder CTA + this notes file)._
