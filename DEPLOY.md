# AKKI · Production Deployment Checklist

This is the one-page "click through" for deploying AKKI to Emergent Cloud
with a custom subdomain. Print it, work top-to-bottom.

## 1 · Click **Deploy** (chat input → Deploy)

Emergent will provision a deployed app at `https://<slug>.emergentagent.com`
and prompt for environment variables.

## 2 · Required environment variables

| Variable                   | Where to get it / what to use                                                                                                            |
|----------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `MONGO_URL`                | Use the production MongoDB URL Emergent provisions, OR your own (e.g. MongoDB Atlas connection string).                                  |
| `DB_NAME`                  | `akki_prod` (recommend distinct from preview's `akki_sandbox`).                                                                          |
| `CORS_ORIGINS`             | Set to your **deployed origin** comma-separated. e.g. `https://app.yourdomain.com,https://akki-prod.emergentagent.com`. NOT `*`.        |
| `JWT_SECRET`               | **GENERATE A NEW ONE** for prod. `python3 -c "import secrets; print(secrets.token_hex(32))"`                                              |
| `ADMIN_EMAIL`              | Your real admin email (used by the bootstrap script).                                                                                    |
| `ADMIN_PASSWORD`           | A strong password. Rotate post-launch.                                                                                                   |
| `FRONTEND_URL`             | Your final public URL. e.g. `https://app.yourdomain.com` (set after step 4).                                                              |
| `EMERGENT_LLM_KEY`         | Same value as preview — the Universal Key works in prod.                                                                                 |
| `APP_NAME`                 | `AKKI` (or your prod brand label).                                                                                                       |
| `AKKI_CRON_SECRET`         | Generate fresh: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`                                                          |
| `RESEND_API_KEY`           | Same value (or rotate). For prod email you must verify your sending domain at https://resend.com/domains.                                 |
| `RESEND_FROM_EMAIL`        | After Resend domain verification: `noreply@yourdomain.com`.                                                                              |
| `RESEND_FROM_NAME`         | `AKKI`.                                                                                                                                  |
| `STRIPE_API_KEY`           | Your **live** Stripe key (sk_live_...) when you go billing-live; otherwise leave the test key.                                            |
| `POSTMARK_SERVER_TOKEN`    | Same value: `c04fdcf8-24c4-4e44-b19f-337f80607d6c` — OR provision a new prod Postmark server.                                            |
| `POSTMARK_INBOUND_DOMAIN`  | (optional) The domain on which inbound mail arrives. Default `inbound.akki.ai`. If you own `mail.yourdomain.com`, point Postmark there. |
| `LLM_MODEL_DEEP`           | (optional) Override the deep tier model. Default `claude-opus-4-6`. Switch to `claude-opus-4-7` once Emergent catalogues it.              |
| `LLM_MODEL_STANDARD`       | (optional) Default `claude-sonnet-4-5-20250929`.                                                                                          |
| `LLM_MODEL_FAST`           | (optional) Default `gemini-2.5-flash`.                                                                                                   |
| `AKKI_DEEP_UNIT_COST_USD`  | (optional) Tune unit cost on /admin/llm-spend. Default `0.045`.                                                                          |
| `AKKI_DEEP_QUOTA_BRIEF`    | (optional) Daily deep-brief quota per user. Default `10`.                                                                                |
| `AKKI_DEEP_QUOTA_BLOG`     | (optional) Default `5`.                                                                                                                  |
| `AKKI_DEEP_QUOTA_DECK`     | (optional) Default `3`.                                                                                                                  |
| `AKKI_DEEP_QUOTA_CHAT`     | (optional) Default `30`.                                                                                                                 |
| `AKKI_DEEP_QUOTA_VALIDATE` | (optional) Default `20`.                                                                                                                 |
| `AKKI_DEEP_QUOTA_MINUTES`  | (optional) Default `5`.                                                                                                                  |

**Frontend env (`/app/frontend/.env`) — set in deploy panel too:**

| Variable                 | Value                                                                  |
|--------------------------|------------------------------------------------------------------------|
| `REACT_APP_BACKEND_URL`  | Your deployed backend URL (or custom domain once mapped).              |

## 3 · Bootstrap the production database

After first deploy, run the one-shot bootstrap script (see
`/app/backend/scripts/bootstrap_prod.py`) once to seed:
- The superadmin account (uses `ADMIN_EMAIL` / `ADMIN_PASSWORD`)
- All required MongoDB indexes (auth, contexts, llm_deep_usage uniqueness, etc.)

```bash
# From the deployed pod or via emergent's pod-shell:
python3 /app/backend/scripts/bootstrap_prod.py
```

The script is idempotent — running it twice is safe.

## 4 · Map your custom subdomain

1. In Emergent's deployment dashboard → **Link domain**.
2. Enter your subdomain (e.g. `app.yourdomain.com`).
3. Click **Entri** → follow the DNS prompts (Entri auto-detects most major
   DNS providers and writes the CNAME / TXT records for you).
4. **Wait 5–15 min** for propagation. SSL/TLS is provisioned automatically.
5. After propagation, **update these env vars** to match the new URL and redeploy:
   - `FRONTEND_URL=https://app.yourdomain.com`
   - `CORS_ORIGINS` → include `https://app.yourdomain.com`
   - `REACT_APP_BACKEND_URL` → your backend URL (same custom domain or its API subdomain)

> **Stuck?** If site not live after 15 min: open your DNS provider, remove
> any conflicting A records, leave only the CNAME from Entri.

## 5 · Wire Postmark inbound

In your Postmark server → **Inbound stream** → set the webhook URL to:

```
https://app.yourdomain.com/api/inbound/postmark?secret=$POSTMARK_SERVER_TOKEN
```

(replace `$POSTMARK_SERVER_TOKEN` with the actual token value you set in
the env). Hit "Check" — Postmark sends a test ping; you should see a 200
in your logs and an `inbound_email.rejected` audit row (test ping has no
valid mailbox hash, so it's rejected — that's expected).

## 6 · Smoke-test live

```bash
APP_URL=https://app.yourdomain.com

# Ping
curl -s "$APP_URL/api/healthz" && echo

# Login
TOKEN=$(curl -s -X POST "$APP_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Quota check (should show all defaults)
curl -s "$APP_URL/api/llm/quota" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Admin spend (should be empty + show defaults)
curl -s "$APP_URL/api/admin/llm/spend?days=7" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Then load `https://app.yourdomain.com` in a browser, sign in, generate one
test brief in deep mode, and confirm the call appears in `/admin/llm-spend`.

## 7 · Keep building

This preview environment is unaffected by your deploy. When the next batch
of changes is ready, click **Deploy** again — it'll snapshot fresh.
Rollback is free if anything goes sideways (Emergent's rollback option
restores the prior snapshot).
