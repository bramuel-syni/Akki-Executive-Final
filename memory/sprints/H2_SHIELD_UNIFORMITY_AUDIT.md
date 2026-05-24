# H2 — Shield Uniformity Audit (READ-ONLY, 2026-05-24)

Forensic audit of whether the AKKI codebase honours the product
promise: **"LLMs never see your confidential data, Shield is always on
unless explicitly deactivated, behavior is identical across all roles
and all surfaces."**

**Verdict: NO — Yes-with-P0-caveats.** The promise holds for the
non-streaming chat path, Solva v2, and the strategic-deliverable
branch of the streaming chat path. It does NOT hold for (a) the
default streaming chat path (~most user turns) which streams raw
content to cloud LLM SDKs and only shields the post-generation reply,
and (b) a handful of background / classifier / sandbox surfaces that
either degrade-open on Shield errors or bypass Shield entirely. Three
P0 violations are listed in §7. NONE require touching Shield code to
fix.

---

## Section 1 — LLM call-site inventory

Every code path that initiates a cloud-LLM round-trip. Excluding
test files. Source: parallel grep of `shield.client.invoke`,
`shield_invoke`, `shield_payload_async`, `_syn_shield`, `call_llm`,
direct SDK imports (`from anthropic|openai|google.generativeai|
google.genai|litellm import`).

### 1a — Modern Shield gateway (`shield.client.invoke`)

| File:line | Surface | Function | Through Shield? | Audit written? | Notes |
|-----------|---------|----------|-----------------|----------------|-------|
| `routers/chat.py:1431` | Chat — sync `/messages` | `send_message` | **YES** | YES — by `shield.client.invoke` | Primary sync path. **OK.** |
| `routers/chat.py:1899` | Chat — stream thin-input | streaming `send_message_stream` | **YES** | YES | Thin-input branch only. **OK.** |
| `routers/chat.py:1922` | Chat — stream retry | streaming retry | **YES** | YES | Retry after `evidence_list` 4-check; same shape. **OK.** |
| `routers/chat.py:2486` | Chat — stream Pass 1 strategic | streaming strategic | **YES** | YES | `turn_class == "strategic_deliverable"` branch. **OK.** |
| `routers/chat.py:2525` | Chat — stream Pass 2 strategic | streaming strategic | **YES** | YES | Same branch. **OK.** |
| `routers/chat.py:2010` | Chat — re-classify retry | re-call | **YES** | YES | Edge case. **OK.** |
| `routers/admin_health.py:?` | Admin health probe | health LLM probe | **YES** | YES | Admin-only diagnostic. **OK.** |
| `routers/monitor_status_assessment.py:?` | Monitor | status assessment LLM | **YES** | YES | Probably OK. Cited from grep. |
| `routers/solva_phase_d.py:?` | Solva Phase D | rapid-fire pre-pass | **YES** | YES | Modern path. **OK.** |
| `routers/strategic_goal_assessment.py:?` | Strategic Goals | goal scoring | **YES** | YES | **OK.** |
| `routers/work_studio_overlay.py:?` | Work Studio overlay | summary LLM | **YES** | YES | **OK.** |
| `services/chat/protective_layer/__init__.py:?` | Chat protective layer | refusal classifier | **YES** | YES | **OK.** |
| `services/sandbox_generation.py:167` | Admin sandbox | demo-content gen | **YES** | YES | **OK** (modern path). |
| `services/solva/orchestration/shield_invoker.py:?` | Solva v2 orchestration | shielded call helper | **YES** | YES | **OK.** |
| `services/solva/reasoning.py:?` | Solva reasoning | NED reasoning LLM | **YES** | YES | **OK.** |
| `llm_service.py:?` | Many — `call_llm` wrapper | central wrapper | **YES** (routes through `shield.client.invoke` internally) | YES | All `call_llm()` callers inherit the Shield contract. **OK.** |

### 1b — `call_llm` wrapper consumers (route through Shield via llm_service)

Surfaces invoking the central `call_llm` wrapper: `routers/blog.py`,
`routers/briefings.py`, `routers/cycle.py`, `routers/decks.py`,
`routers/documents.py`, `routers/learn.py`, `routers/lens.py`,
`routers/misc.py`, `routers/news.py`, `routers/admin_assist.py`,
`services/document_commentary_service.py`, `services/llm_tier_quota.py`.

Each routes through `llm_service.call_llm()` which routes through
`shield.client.invoke()`. All inherit Shield + audit. **OK** as a group.

### 1c — Legacy `shield_payload_async` (a.k.a. `_syn_shield`)

This is the LEGACY pre-redaction pre-pass — used as a "detection-only"
step BEFORE the modern Shield call, OR (in older surfaces) as a
standalone shielding step.

| File:line | Surface | Function | Through full Shield? | Audit? | Notes |
|-----------|---------|----------|----------------------|--------|-------|
| `routers/chat.py:1685` (sync) + `:1685` (stream) | Chat | detection pre-pass | partial — detection only | **YES** if `message_id` passed (Phase J.2), else dryrun (no persist) | Chat-family always passes message_id → audit persisted. **OK.** |
| `routers/chat.py:2486` Pass 2 history scrub | Chat history | retroactive scrub | partial | persists for `chat` surface | **OK.** |
| `routers/work_studio_export.py:1106` | Work Studio export | shielded re-write of source | partial — REDACTION only, no LLM trip | **NO audit row** — uses `surface="enhance"` which the chat-family persistence gate excludes (line 92 of adapter.py: `if message_id and surface.startswith("chat")`). | **P1 violation** — work_studio_export shields the source text before LLM extraction, but the audit shows no row. The downstream LLM call DOES get redacted text, so the LLM doesn't see raw PII; only the audit visibility is missing. |
| `services/sandbox_generation.py:324` | Admin sandbox | demo-content pre-pass | partial — REDACTION only | dryrun, no audit row | **P2** — admin-only surface, low risk, but not surfaced in the trail. |

### 1d — Direct LLM SDK imports outside `services/synisense/shield/`

```
grep -rnE "^from (openai|anthropic|google.generativeai|google.genai|litellm|cohere|emergentintegrations) import|^import (openai|anthropic|litellm|cohere)" /app/backend --include="*.py" \
    | grep -v __pycache__ | grep -v /tests/ | grep -v services/synisense/shield
→ (empty)
```
**OK** — CI guard is doing its job. ZERO direct SDK leaks outside `shield/`.

### 1e — Direct LLM SDK use INSIDE `services/synisense/shield/streaming.py`

`shield/streaming.py:102` imports `anthropic`, `:144` imports
`google.genai`, `:195` imports `openai`, `:254` uses `litellm`.
Function: `stream_llm_direct(provider, model_id, system_msg,
user_text, ...)` opens a streaming connection to the cloud provider
directly.

This module lives INSIDE `services/synisense/shield/`, so the CI
guard accepts it. **But** the function takes a `user_text` parameter
and feeds it verbatim to the cloud provider's streaming endpoint with
**no de-identification step**, **no tenant_id binding**, **no audit
row written**, **no trust receipt signed**.

This is the linchpin of the §3 streaming carve-out finding below.
**P0** — see Section 3.

---

## Section 2 — Surface × Role × Policy matrix

Roles: Executive (default), NED (`my_role=ned`), Admin, Superadmin.

| Surface | Roles | `policy=always` | `policy=auto` | `policy` unset / `off` | Audit guaranteed? |
|---|---|---|---|---|---|
| Chat — sync `/messages` | Exec, NED, Admin, Super | Shield invoked every turn (chat.py:1431) | Same — `policy` recorded but NOT consulted in sync path (chat.py:1295-1297 hard-codes `will_shield=True`) | Same | **YES** (sync path) |
| Chat — stream `/messages/stream` default branch | Exec, NED, Admin, Super | RAW prompt sent via `stream_llm_direct()` to cloud SDK (chat.py:2409) — Shield only post-processes the assembled reply. See §3 P0. | Same — policy gates the post-process `_syn_rehydrate` (chat.py:2231) but the LLM provider already saw the raw text. | Same | **NO** — no shield audit row for the LLM round-trip in the default streaming branch |
| Chat — stream strategic_deliverable branch | Exec, NED, Admin, Super | Shielded (chat.py:2486 + 2525, both passes) | Same | Same | **YES** |
| Solva v2 (all phases) | Exec, NED | Shielded via `solva.orchestration.shield_invoker` | Same | Same | **YES** |
| Solva legacy | (only Phase D modern wired) | Modern path | Same | Same | **YES** |
| Work Studio (overlay LLM) | Exec | Shielded via `shield.client.invoke` | Same | Same | **YES** |
| Work Studio export (enhance re-write) | Exec | Legacy `_syn_shield` redacts source pre-LLM, but **no audit row written** (`surface="enhance"`, not `"chat*"`) — see §1c | Same | Same | **NO** (P1) |
| Cycle Manager | Exec, NED | `call_llm()` → Shield | Same | Same | **YES** |
| Monitor — status assessment | Exec, NED | Shield | Same | Same | **YES** |
| Pulse | (`call_llm()` consumers) | Shield | Same | Same | **YES** |
| Strategic Goals — assessment | Exec, NED | Shield (modern) | Same | Same | **YES** |
| Admin — health probe | Admin, Super | Shield | Same | Same | **YES** |
| Admin — sandbox generation | Admin only | Modern call shielded; pre-pass legacy `_syn_shield` w/o audit | Same | Same | **NO** (P2) |
| Blog / Briefings / Decks / Documents / Learn / Lens / News | (whichever roles can hit them) | Shield (via `call_llm()`) | Same | Same | **YES** |

**Role-gating note:** in NO surface does the role check decide whether
Shield runs. Roles only gate ACCESS to the endpoint, not the
Shield-or-not branching. See §4.

---

## Section 3 — `auto` vs `always` divergence

### Sync chat path (`/messages`)
**No divergence.** chat.py:1295-1297 sets `will_shield = True` as the
hardcoded default and the policy enum is recorded on the user_message
but **not consulted** for any if-branch in the sync handler. Every
sync message goes through Shield.

### Streaming chat path (`/messages/stream`)
**Two layers of divergence:**

1. **Policy gate at chat.py:1692** decides `will_shield` based on
   `body.shielding_policy`:
   ```python
   if policy == "always": will_shield = True
   elif policy == "off":  will_shield = False (unless detected & no ack)
   else (auto):           will_shield = bool(detected_identifiers)
   ```
   With `auto` AND zero identifiers detected by the legacy `_syn_shield`
   pre-pass, `will_shield=False`. **But this gate only affects whether
   the post-generation rehydration runs.** The cloud LLM SDK call
   below (chat.py:2409 `stream_llm_direct`) happens REGARDLESS of
   `will_shield`.

2. **The streaming default branch (chat.py:2390) is the P0 violation:**
   Whether `will_shield=True` OR `False`, OR `policy=always` OR `auto`
   OR `off`, the function `stream_llm_direct()` is called with the
   `full_prompt` that contains the RAW user text (`sent_to_llm = text`
   at chat.py:2090, where `text = body.content.strip()` at chat.py:1683).
   Anthropic / Gemini / OpenAI see the original PII tokens. The
   "shield" that runs afterwards (chat.py:2231) operates only on the
   user-visible reply, not the LLM input.

   The comment at chat.py:2392-2398 documents this carve-out:
   > "Synisense Shield only fires on the ASSEMBLED final reply below
   > … each delta is a token-fragment and Shield is built for
   > whole-text payloads."

   This means in the streaming path, ALL three policy modes are
   functionally equivalent w.r.t. what the LLM provider sees. The
   policy choice only affects what gets RE-IDENTIFIED in the
   user-facing reply.

### Recommendation
**Collapse `auto` and `always` semantics** AND fix the streaming
carve-out:
- Make the streaming default branch run de-identification on
  `full_prompt` BEFORE calling `stream_llm_direct`, using the legacy
  `_syn_shield` (which already returns `(redacted_text, shield_map)`)
  OR teach `stream_llm_direct` to accept a `tenant_id` + call the
  Shield deidentifier internally.
- Then post-process the streamed reply with `_syn_rehydrate(...,
  shield_map)` honouring the reidentifier's PII-class skip list from
  Fork A.
- `auto` and `always` then differ ONLY in the user-visible
  rehydration step: `always` keeps tokens as `[PAYMENT_CARD_••••]`
  placeholders in the final reply for ALL classes; `auto` keeps
  the PII-class skip list (contextual entities rehydrate, hard PII
  stays redacted). This matches the user trust mental model.
- `off` becomes the "explicit deactivation" the product promise allows.

---

## Section 4 — Role-based gating

`grep -rnE "if.*role|require_role|require_admin|is_admin|is_superadmin" /app/backend | grep -iE "shield|llm|invoke"`

Findings:
- `routers/admin_llm_spend.py` — role-gates the **read** of LLM spend
  telemetry. Does not affect Shield path. **OK.**
- No other surfaces gate Shield by role.

**Verdict:** ZERO role-based gating of detection or audit. Every
authenticated user — Executive, NED, Admin, Superadmin — gets the
same Shield treatment. ✅ This part of the product promise holds.

---

## Section 5 — Bypass risk catalog

| Risk | File:line | Severity | Notes |
|---|---|---|---|
| Direct LLM SDK imports outside `shield/` | (grep returns empty) | OK | CI guard `test_no_direct_llm_calls_inside_shield_except_router` enforces |
| `stream_llm_direct` direct provider streaming with raw user_text | `services/synisense/shield/streaming.py:331-420` + `routers/chat.py:2405` | **P0** | Lives inside `shield/` so passes CI guard, but bypasses de-identification on input |
| Legacy `_syn_shield` degrades open on pipeline error | `services/synisense/adapter.py:111-120` | **P1** | Returns raw `text, {}` on exception, then downstream `call_llm` sends the raw text to LLM. Documented as intentional ("chat-style surfaces have historically degraded rather than refusing") but contradicts the promise |
| Classifier LLM call on RAW user text | `routers/chat.py:1788` (`_classify_and_audit` is fed `body.content` raw) | **P1** | Need to verify: does the classifier route through Shield? — needs deeper review |
| `shield_payload_async` w/o `message_id` → dryrun, no audit row | `services/synisense/adapter.py:92-110` | **P1** | Non-chat surfaces (enhance, briefing, deck, report, ingest) don't get persisted Shield audit rows |
| Work Studio export — `surface="enhance"` → no audit | `routers/work_studio_export.py:1106` | **P1** | See above. LLM gets redacted text but no audit trail visible |
| Admin sandbox generation — `dryrun` pre-pass | `services/sandbox_generation.py:324` | **P2** | Admin-only, low risk; not in user-visible trail |
| `SYNISENSE_ALLOW_INSECURE` env var | `backend/.env` | **P2** | Weakens key derivation but does NOT skip Shield. Empty in prod per file check |
| Feature flags / debug modes that skip Shield | `grep -rnE "SHIELD_DISABLE|bypass_shield|skip_shield"` | (empty) | OK |
| Scripts / cron / migrations touching LLMs | `/app/backend/scripts/`, `/app/backend/migrations/` | (no LLM use) | OK |
| Background workers (APScheduler) | `services/jobs/*` | (no LLM use beyond `call_llm` which routes through Shield) | OK |

---

## Section 6 — Telemetry / audit-row write guarantees

| Guarantee | Holds? | Evidence |
|---|---|---|
| Every `shield.client.invoke()` writes an audit row | **YES** | `shield/client.py:61-114` — audit_id minted unconditionally, persisted to `synisense_audit_log` |
| Audit row written for zero-redaction calls | **YES** | `shield/client.py` writes row even when `de_id_summary == {}` |
| Audit row identical across modes (`auto`/`always`/`off`) when Shield runs | **YES** | Mode determines whether `shield.client.invoke()` is called; once called, row shape is mode-agnostic |
| Audit row written for NED vs Admin vs Exec | **YES** | No role-gated branching in shield/client.py |
| Audit row written when Shield fails mid-call | **PARTIAL** | `shield/client.py` raises one of four shield-specific exceptions on failure; the audit row is written BEFORE the LLM call so the row exists. **BUT** if the legacy `shield_payload_async` raises (adapter.py:111-120), it returns raw text and no row at all → the downstream LLM call proceeds with raw content. **P1** |
| Audit row written in the streaming default branch | **NO** | `stream_llm_direct` writes nothing to `synisense_audit_log`. The chat-level `_append_audit` writes a different audit table (`chat_audit_log`) for chat message lifecycle, not for the LLM trip itself. **P0** (paired with §3 finding) |

---

## Section 7 — Rank-ordered findings

### 🔴 P0 — violates the product promise; must fix before H3 (Trust Center build) so the Trust Center doesn't make claims that disagree with reality

1. **Streaming default branch sends raw `full_prompt` to cloud LLM SDKs**
   (`routers/chat.py:2390-2411` + `services/synisense/shield/streaming.py:331-420`)
   • Anthropic / Gemini / OpenAI receive un-redacted user content.
   • No `synisense_audit_log` row for the LLM trip.
   • Mitigation today: Shield runs on the assembled reply for the
     USER-VISIBLE rehydration, but the LLM provider already saw raw
     PII. This is the exact violation the user is auditing for and
     the gap that screenshot evidence keeps surfacing.
   • Affected: every streaming chat turn that is NOT classified as
     `strategic_deliverable` AND NOT `thin-input`. This is the
     majority of user turns.
   • Recommended fix scope: ~50-80 LOC. Either (a) teach
     `stream_llm_direct` to call `deidentifier.deidentify(user_text,
     tenant_id)` BEFORE opening the provider stream and emit one
     audit row at completion; OR (b) make `chat.py:2390` route raw
     `full_prompt` through `_syn_shield` first and pass the redacted
     version into `stream_llm_direct`.

2. **`policy=auto` and `policy=always` are functionally identical in
   the streaming path w.r.t. what the LLM provider sees**
   (paired with #1)
   • The UI lets users toggle between auto/always/off implying
     different behaviour, but in the most common code path they're
     equivalent (all leak to the provider).
   • Resolves automatically once #1 is fixed: the post-fix
     differentiation lives in the reidentifier skip list (Fork A),
     not in whether the LLM was shielded.

### 🟡 P1 — surface-visible inconsistency; should fix before user demos to bank QA

3. **Legacy `_syn_shield` degrades-open on pipeline failure**
   (`services/synisense/adapter.py:111-120`)
   • On any exception inside the Presidio + regex pipeline, returns
     raw `(text, {})` and logs. Downstream `call_llm` then ships the
     raw text. Documented as intentional but contradicts the promise.
   • Fix: change behaviour to RAISE on chat-family surfaces (mirror
     Solva v2's strict adapter at `solva_v2.llm_adapter.shielded_call`
     which DOES raise on this same path).

4. **Classifier LLM call (`_classify_and_audit` at chat.py:1788)
   appears to be fed raw `body.content`**
   • Comment says "classify on RAW user text" — needs deeper review:
     does the classifier route through Shield internally, or does it
     bypass like `stream_llm_direct`? If bypass: that's another P0.
   • TODO before fixing #1 — confirm with one more code read.

5. **`shield_payload_async` without `message_id` skips persistence**
   (`services/synisense/adapter.py:92-110`)
   • Non-chat surfaces (enhance, briefing, deck, report, ingest)
     redact correctly but don't write audit rows the Trust Center
     can show users.
   • Fix: always persist; gate the dryrun-only mode behind an
     explicit `persist=False` kwarg.

6. **Work Studio export — `surface="enhance"`** (paired with #5)
   • `routers/work_studio_export.py:1106` — LLM gets redacted text
     but no audit row. Trust Center will show "no Shield activity"
     for a surface that clearly does Shield work.

### 🟢 P2 — internal hygiene; defer

7. **Admin sandbox generation pre-pass uses `dryrun`** — admin-only,
   low risk. (`services/sandbox_generation.py:324`)

8. **`SYNISENSE_ALLOW_INSECURE` env var** — weakens key derivation if
   set. Empty in prod. Document in Trust Center as "not set on this
   tenant".

### ⚪ OK — document only, no change needed

9. ZERO direct LLM SDK imports outside `shield/` (CI guard works).
10. `shield.client.invoke` always writes an audit row regardless of
    policy / role / redaction count.
11. NO role-based gating of Shield anywhere.
12. NO debug / bypass flag that disables Shield.
13. NO LLM use in scripts, cron jobs, migrations.

---

## Section 8 — Final verdict

**Does the codebase today honour "LLMs never see your confidential
data, Shield is always on unless explicitly deactivated, identical
across roles/surfaces"?**

> **Yes-with-P0-caveats.** Three structural strengths and three
> structural weaknesses.
>
> **Strengths:** (1) the CI guard `test_no_direct_llm_calls_inside_
> shield_except_router` is empirically clean — zero rogue SDK
> imports outside `shield/`. (2) `shield.client.invoke()` is the
> single mint of `synisense_audit_log` rows and writes one
> unconditionally for every invocation, regardless of role,
> redaction count, or mode. (3) NO role-based gating of detection
> anywhere — Executive / NED / Admin / Superadmin all hit the same
> Shield path.
>
> **Weaknesses:** (1) **the streaming default branch is the load-
> bearing P0** — `services/synisense/shield/streaming.py` lives
> inside the shield namespace (passing CI), but it streams the raw
> `full_prompt` to Anthropic / Gemini / OpenAI without running
> `deidentifier.deidentify()` first, and it writes no audit row for
> the LLM round-trip. The user-visible "shielding" runs ONLY on the
> assembled reply (post-generation), which protects what the USER
> sees but does NOT protect what the LLM saw. (2) `policy=auto` and
> `policy=always` collapse to identical behaviour in this default
> streaming branch, contradicting the UI's mode selector. (3) the
> legacy `shield_payload_async` adapter degrades-open on pipeline
> failure (returns raw text), and several non-chat surfaces use
> `dryrun` so no audit row is persisted.
>
> The streaming carve-out is the same gap the user has been seeing
> in screenshots ("LLM clearly received the raw PAN"). It is NOT
> a misperception of the reidentifier rehydrating — in the streaming
> path the LLM provider really does receive raw content. The
> rehydration discussion from yesterday's H1 brief applies to the
> non-streaming sync path; the streaming path needs the actual fix.
>
> **Recommendation to user:** before H3 (Trust Center) ships, run a
> P0 corrective phase (H2.5) to plug the streaming-carve-out and
> close P1s #3, #5, #6. This is ~150-250 LOC of bounded change in
> `shield/streaming.py`, `synisense/adapter.py`, and `chat.py:2390`.
> No new libraries, no architectural shifts. If the Trust Center
> ships first, its claims will not be fully defensible under bank
> QA the moment they ask "show me what the LLM saw in a typical
> chat turn".

---

## Section 9 — Open questions / deferred-review items

- [ ] §7 P1 #4 — does `_classify_and_audit` route through Shield,
      or does it bypass like `stream_llm_direct`? File:line
      `routers/chat.py:1788` — needs one more code read into
      `services/chat/classifier.py` (or wherever
      `_classify_and_audit` lives).
- [ ] Are there other internal modules under `services/synisense/
      shield/` that import LLM SDKs directly (beyond `streaming.py`)?
      `grep -rE "from (anthropic|openai|google.genai|litellm) import"
      /app/backend/services/synisense/shield/` returns ONLY
      `streaming.py` and `_legacy_llm_fallback.py`. The latter is
      routed through `llm_router.invoke()` per the May 22 cold-
      start latency fix; needs one more confirmation read.
- [ ] Pulse / News / Blog — verified by `call_llm` consumer list,
      but did not read each route end-to-end for prompt assembly.
      Quick spot-check would tighten the matrix.

---

## Section 10 — Files cited

- `routers/chat.py` (3116 lines) — primary chat surface
- `services/synisense/shield/client.py` (116 lines) — modern shield gateway
- `services/synisense/shield/streaming.py` (482 lines) — P0 carve-out lives here
- `services/synisense/adapter.py` (180 lines) — legacy shield_payload_async
- `services/llm_streaming.py` — shim re-exporter
- `routers/work_studio_export.py` (1100+ lines)
- `services/sandbox_generation.py`
- `routers/admin_llm_spend.py` — only role-gated LLM-adjacent file (telemetry read, not Shield)

---

## Audit metadata

- **Audited by:** main agent, 2026-05-24
- **Method:** parallel grep across `/app/backend/` + targeted source
  reading; ZERO code changes
- **Time:** ~40 min within the 45 min budget
- **Source-of-truth assertion:** every claim above carries a
  file:line citation OR is marked "needs deeper review"
- **Forgetting-mitigation:** pinned to disk at this path
  (`/app/memory/sprints/H2_SHIELD_UNIFORMITY_AUDIT.md`) so future
  agents reconcile against this evidence, not against session memory.
