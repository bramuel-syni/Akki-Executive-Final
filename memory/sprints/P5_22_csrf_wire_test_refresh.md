# P5.22 — CSRF-rotted wire test refresh (test-rig only)

**Date:** 2026-02-06
**Mode:** Test-rig only — mechanical.
**ANTIFORGET PROTOCOL:** acknowledged. Raw pytest + verbatim output.
**Files touched (single shared fix):** `backend/tests/conftest.py` only. **Zero production source changes.**

---

## Step 1 — BEFORE trace (verbatim)

```
======================== 4 passed, 15 warnings in 3.37s ========================   ← v1 byte-identical guard
voice_lint: clean across customer-copy surfaces.

$ pytest tests/test_h2_5_shield_uniformity.py -v
…
FAILED tests/test_h2_5_shield_uniformity.py::test_wire_streaming_llm_receives_redacted_prompt_not_raw_pan
FAILED tests/test_h2_5_shield_uniformity.py::test_wire_audit_integrity_invariant_holds
FAILED tests/test_h2_5_shield_uniformity.py::test_wire_audit_invariant_violations_collection_empty_for_normal_flow
FAILED tests/test_h2_5_shield_uniformity.py::test_wire_three_way_agreement_metrics_audit_chat
FAILED tests/test_h2_5_shield_uniformity.py::test_wire_chat_envelope_uses_uppercase_shield_v1_vocabulary
FAILED tests/test_h2_5_shield_uniformity.py::test_wire_stream_envelope_audit_id_resolves_to_shield_row
================== 6 failed, 24 passed, 15 warnings in 7.69s ===================
```

Per-test failure line (single representative trace — all 6 fail with the same shape):

```
async with client.stream(
    "POST", f"/api/chats/{chat_id}/messages/stream",
    json=body, headers=hdrs, timeout=30.0,
) as resp:
    body_bytes = b""
    async for chunk in resp.aiter_bytes():
        body_bytes += chunk
>   assert resp.status_code == 200, (resp.status_code, body_bytes[:300])
E   AssertionError: (403, b'{"detail":{"code":"csrf_token_missing","message":"CSRF token missing. Reload the page and retry."}}')
E   assert 403 == 200
```

All six failures share that 403 csrf_token_missing.

---

## Step 2 — Diagnosis (one sentence)

**Shared-helper rot.** `conftest.py` patches `httpx.AsyncClient.request` to inject the `X-CSRF-Test-Bypass: 1` header, but `httpx.AsyncClient.stream` builds its own request via `build_request` + `send` and bypasses the patch — so every `client.stream(...)` call hits production CSRFMiddleware with no bypass token. The 6 failing tests all use `client.stream(`; the 24 passing tests use `client.post(`/`client.get(` (which go through the patched `request`).

---

## Step 3 — Fix (single shared change at `backend/tests/conftest.py`)

Mirror the existing `request` monkey-patch on `stream`. Production CSRFMiddleware untouched.

Diff summary:

```
backend/tests/conftest.py
  +17 lines (1 import note + parallel _patched_stream + assignment)
  -0 lines
```

```python
# Phase P5.22 (2026-02) — symmetric bypass on the streaming path.
# `AsyncClient.stream(...)` builds its own request via `build_request`
# + `send` and bypasses the `request` monkey-patch above. The wire-
# level tests in `test_h2_5_shield_uniformity.py` exercise the
# streaming endpoint, so without this they regressed to 403
# `csrf_token_missing` on the production CSRFMiddleware. Mirror the
# header-injection on `stream` so both sync-style POST and streaming
# POST paths carry the test bypass token.
_orig_stream = _httpx.AsyncClient.stream
def _patched_stream(self, method, url, *args, **kwargs):
    headers = kwargs.get("headers") or {}
    headers = dict(headers)
    headers.setdefault("X-CSRF-Test-Bypass", "1")
    kwargs["headers"] = headers
    return _orig_stream(self, method, url, *args, **kwargs)
_httpx.AsyncClient.stream = _patched_stream
```

`stream` is a sync method that returns an async-context-manager, hence the patch is sync (not async) and re-invokes the original.

---

## Step 4 — AFTER trace (verbatim)

```
$ pytest tests/test_h2_5_shield_uniformity.py -v
…
======================= 30 passed, 15 warnings in 10.23s =======================
```

All 6 previously-failing wire tests now PASS. The 24 previously-passing tests still PASS (no regression).

### Broad bundle (verbatim, full command from spec)

```
$ pytest tests/test_solva_v1_unchanged.py tests/test_phase_p5_15_ideas_by_akki.py \
        tests/test_phase_p5_15_ideas_scheduler.py tests/test_phase_p5_14_workbook_analyze.py \
        tests/test_phase_p5_16_inbox_routing.py tests/test_phase_p5_17_upstream_adapter.py \
        tests/test_phase_p5_19_signal_cycle_adapter.py \
        tests/test_phase_p5_20_default_inbox_cycle.py \
        tests/test_h2_5_shield_uniformity.py -q
…
177 passed, 15 warnings in 107.77s (0:01:47)
```

**Suite-size delta vs P5.20.1 baseline (147):** **+30** (the entire h2_5_shield_uniformity suite of 30 tests is now eligible for inclusion in the broad bundle — was un-includable while 6 were red). New combined floor: **177/177 green.**

---

## Step 5 — Closing discipline gates (verbatim)

```
v1 byte-identical guard (test_solva_v1_unchanged.py):  4 passed, 15 warnings in 3.43s
voice_lint:                                             clean across customer-copy surfaces.
```

---

## Step 6 — Files-touched check (verbatim `git status --short`)

```
 M backend/tests/conftest.py
?? backend/.env          ← pre-existing untracked
?? frontend/.env         ← pre-existing untracked
?? frontend/yarn.lock    ← pre-existing untracked
```

**Single test-rig file modified. Zero production source changes.**

Production files NOT touched (constraint hard-honoured):
- `services/csrf.py` (CSRFMiddleware) — untouched.
- `server.py` — untouched.
- Any router — untouched.
- Any service — untouched.
- Any test file other than `conftest.py` — untouched.

---

## Out-of-scope deferrals (carry forward, NOT piggybacked)

Per spec — each logged here, not fixed:

- **Cross-test fixture state leak** (`Future attached to a different loop`) — Motor event-loop binding, structural. User-kept-deferred.
- **Postmark history scrub** — user-deferred.
- **LLM-shielded classifier flag flip** — not in scope.
- **HA-safe Ideas scheduler** — not in scope.
- **Daily / biweekly Ideas cadence** — future.
- **"Why didn't this idea appear last week?"** diff view — future.
- **Re-target row action on default-inbox badge** — deferred polish from P5.20.1.
- **Trust Center tour pre-dismissal flag for probes** — LOW; probe-hygiene from P5.21.
- **AdminTopBar tile / routing-log distribution chart / public trust snapshot** — declined.

While in `test_h2_5_shield_uniformity.py` I also noticed:

- `services/llm_streaming.py::stream_llm_direct` is monkey-patched in 6 of the 6 wire tests using a namedtuple shim — DRYable into a fixture, but explicitly **NOT** piggybacked here.

---

## ANTIFORGET PROTOCOL re-acknowledged at memo close.

This dispatch was mechanical and test-rig-only. Both production source code and the v1 byte-identical guard remain untouched. The fix is symmetric to a year-old pattern in the same file — minimum surface, maximum reuse.
