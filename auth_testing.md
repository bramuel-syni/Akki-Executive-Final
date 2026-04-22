# AKKI Sandbox Auth Testing Playbook

## MongoDB verification
```
mongosh
use akki_sandbox
db.users.find({role: "superadmin"}).pretty()
db.users.findOne({email: "admin@akki.ai"}, {password_hash: 1})  // must start with $2b$
db.users.getIndexes()          // expect unique index on email
db.invitations.getIndexes()    // expect unique index on token
db.memberships.find({}).pretty()
```

## Happy-path curl (external URL for e2e)
```bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)

# Register new exec
curl -sS -c /tmp/c1.txt -X POST $API/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"exec.test@akki.ai","password":"TestExec2026!","name":"Test Executive","tenant_name":"Test Bank"}' | jq .

# Login (admin)
curl -sS -c /tmp/ca.txt -X POST $API/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@akki.ai","password":"AkkiAdmin2026!"}' | jq .

# Me
curl -sS -b /tmp/ca.txt $API/api/auth/me | jq .
```

## Multi-tenancy isolation checks
- Create two users in separate tenants. User A calls `GET /api/tenants/<tenant-of-B>/members` → must return 403.
- Remove collaborator → verify membership status flips to "removed" in Mongo.
- Revoked invitation token cannot be used; expired tokens return 410.
- Non-owner member calling `PATCH /api/tenants/{id}` → 403.

## Brute force
- 5 bad logins for the same `{ip}:{email}` → 6th returns 429 (15 min lockout).

## Export
- Owner `POST /api/tenants/{id}/export` → JSON file includes tenant, memberships, users (no password hashes), audit_log.

## MFA
- `POST /api/auth/mfa/setup` → returns QR data URL and secret
- Compute TOTP with `python -c "import pyotp; print(pyotp.TOTP('<secret>').now())"`
- `POST /api/auth/mfa/verify` with that code → `{mfa_enabled: true}`

## LLM scaffolding probe
- `POST /api/tenants/{id}/llm/probe` with `{"module":"signals","query":"hello"}` → returns layered mock JSON with `mode: "mock-scaffolding"`.
