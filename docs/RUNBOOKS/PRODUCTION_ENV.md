# Runbook — Production environment variables

_Stub runbook. Grows as we find more platform-managed config that needs surfacing to operators. Phase 10 seeded the first entry._

---

## Stripe test-mode key leak

### Symptom

The backend container has `STRIPE_API_KEY=sk_test_emergent` set in its environment even though `BILLING_ENABLED=false`. The backend log carries:

```
WARNING  akki.billing  Stripe test-mode key detected in non-billing env — ignored, but should be removed
```

### Cause

The Emergent preview platform ships a default `STRIPE_API_KEY=sk_test_emergent` in every container via the pod spec. This was useful when the product shipped with `BILLING_ENABLED=true` by default; Phase 10 flipped billing off by default and retired the `sk_test_emergent` default inside `routers/billing.py`. The key is now inert — no code path reads it as long as `BILLING_ENABLED=false` and `STRIPE_SECRET_KEY` is unset — but its continued presence is a confused-deputy hazard.

### Immediate mitigation (already in this repo)

`/etc/supervisor/conf.d/supervisord.conf` masks the inherited value for the backend process:

```
[program:backend]
environment=...,STRIPE_API_KEY="",STRIPE_SECRET_KEY=""
```

This means `os.environ.get("STRIPE_API_KEY")` returns an empty string inside the backend, which all guards in `billing.py` treat as "not configured". The supervisor config is the source of truth inside the container; the platform-level env is effectively shadowed.

### Permanent removal (platform-side, one-line action)

Remove the `STRIPE_API_KEY` entry from the Kubernetes pod spec / platform container config. Where exactly depends on the deployment surface:

| Surface                        | Action                                                                                            |
|--------------------------------|---------------------------------------------------------------------------------------------------|
| Emergent preview pod spec       | Remove the `- name: STRIPE_API_KEY` / `value: sk_test_emergent` block from the container `env:`. |
| Emergent Deploy                 | In the deploy UI, unset the `STRIPE_API_KEY` variable.                                           |
| Self-hosted Kubernetes          | `kubectl edit deployment akki-backend` → delete the relevant `env:` block → apply.               |
| Docker-Compose self-host        | Remove `STRIPE_API_KEY` from `docker-compose.yml` service env and `.env`.                        |

Verification after removal:

```bash
# Shell into the running backend container
kubectl exec -it <pod> -- env | grep -i stripe
# Expected: empty (or only the supervisor-masked values STRIPE_API_KEY= / STRIPE_SECRET_KEY=)
```

Verification in the running backend:

```bash
# Backend process environment
tr '\0' '\n' < /proc/$(pidof -s uvicorn)/environ | grep -i stripe
# Expected: STRIPE_API_KEY=\nSTRIPE_SECRET_KEY=  (empty values, masked by supervisor)
```

Once the platform spec is cleaned up, the supervisor masking lines in `supervisord.conf` can stay as belt-and-braces — they're no-ops when the inherited value is empty.

### When you need to re-enable Stripe

1. Set `BILLING_ENABLED=true` in `/app/backend/.env`.
2. Set `STRIPE_SECRET_KEY` (not `STRIPE_API_KEY`) to a **live** or **new test-mode** key of your choosing — not the retired `sk_test_emergent`.
3. Set `STRIPE_WEBHOOK_SECRET` to the webhook signing secret from the Stripe dashboard.
4. Restart the backend. The boot guard in `server.py:on_startup` will refuse to start if `BILLING_ENABLED=true` without a `STRIPE_SECRET_KEY` — that is the intended behaviour.
