# H3 — Prod Transient (2026-05-24T12:53:19 UTC) Diagnosis

**Status:** Diagnosed (partial, log access limited) · **Classification: P2 one-off** with **P3 cold-start tax to track**.

## What `deployment_agent` surfaced
- Prod backend currently healthy: status PASS, "Backend API responding successfully (200 OK)".
- Cold-start Shield warmup measured **17.8 s** on the 1Gi pod (vs ~540 ms on preview's warm venv).
- No verbatim stack trace for the 12:53:19 UTC blip — `deployment_agent` does not have a `kubectl logs --since=…` capability accessible from this container; only static config + status snapshots.

## Inference (best-evidence, NOT log-confirmed)
The 2-min 502 was almost certainly **uvicorn worker recycle during a cold-start window**, not OOM nor provider-side. Three signals point at this:
1. Shield warmup is now SUCCEEDING in prod (the Path B `warmup_or_warn` change is doing its job — there's no crash-loop).
2. 17.8 s warmup tax on the 1Gi pod means the FIRST few requests after a worker spawn race against the not-yet-warm `_SPACY_NLP` cache. During that window, requests that touch Shield will fail-closed (HTTP 503) and the user-facing surface is 502 if nginx doesn't have an upstream.
3. There's no `OOMKilled` indicator in the health summary, no provider error spike.

## Classification
- **P1 structural worker-recycle race**: NO — the per-request fail-closed path already covers this. A request landing during the warmup window returns a documented 503, not a 502. The 502 was nginx-level (upstream temporarily absent), which is a deploy/restart artefact rather than a code defect.
- **P2 one-off**: YES — the 12:53:19 UTC blip looks like exactly one such cold-start window after a deploy/redeploy. Reproducible only on cold pod spawn.
- **P3 acceptable cold-start tax**: YES — 17.8 s warmup is the cost of loading `en_core_web_sm` + the regex/dict layers on a 1Gi pod. Acceptable for v1; track for v2.

## Recommended follow-ups (NOT shipped now — H3 scope-only)
1. **Pre-cache the model in the build step**: avoid the cold-load by serializing `_SPACY_NLP` to disk during `pip install` and `mmap`'ing at boot. Cuts warmup to <2 s.
2. **Add a `/api/healthz/shield` poll in nginx readiness gating** so the LB only sends traffic once `ready=true`. Removes the 502 entirely during the warmup window.
3. **Per-request waiting**: if a Shield call lands during warmup, await `_SPACY_NLP_READY_EVENT` for up to 5 s before erroring. Buys a tiny UX win during cold starts.

None of these is necessary for H3 to ship. They go in a "Trust Center post-deploy follow-up" backlog.

## Bottom line
**P2 one-off + P3 cold-start tax to track.** Prod is healthy. H3 build proceeds.
