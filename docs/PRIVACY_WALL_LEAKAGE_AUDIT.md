# AKKI — Privacy Wall Leakage Audit (baseline, 2026-05-05)

> **Purpose.** A read-only audit of every cross-context surface in
> the codebase **as it ships today**. This is the baseline we
> measure Phase 2b against. If a route is leaking now, this doc says
> so plainly. No code changes were made to produce this audit —
> only `grep` over `backend/routers/` and `view_file` reads.
>
> **Severity legend.**
> - **NONE** — the route's projection or scope rules already preclude content from crossing contexts.
> - **LOW** — content can technically ship cross-context but only in fields whose classification is genuinely ambiguous (one of the §2 TBDs in `PRIVACY_WALL_DESIGN.md`). No fix possible until product signs off on the TBD.
> - **HIGH** — content is shipping cross-context today and the path is clear-cut. Phase 2b must close.

---

## 1 · Surfaces audited

### `GET /api/me/home/stream` — `routers/shares.py:403`
**Cross-context aggregator. The original Privacy-Wall-unsafe surface.**

| Filter | Currently filters by `context_id`? | Notes |
|---|---|---|
| Membership | Yes (membership-keyed) | `ctx_ids` from `db.memberships.find({account_id: current.id, status: "active"})`. Caller cannot read a context they're not a member of. |
| Content fields shipped | — | See per-row below. |

| Row source | Projection | Verdict |
|---|---|---|
| `db.signals.find({"context_id": {"$in": active_ctx_ids}}, {"_id": 0})` (line 468) | `_id` stripped, **everything else shipped** | **HIGH — leak.** Ships `headline`, `body`, `evidence_excerpt`, `recommended_actions[]` cross-context. |
| `db.boardpacks.find({"context_id": {"$in": active_ctx_ids}}, {"_id": 0})` (line 470) | `_id` stripped, **everything else shipped** | **HIGH — leak.** Ships `commentary`, `commentary_redacted`, `title`, `subject`, `document_ids[]` cross-context. |
| `db.documents.find(documents_q, {projection})` (line 474–481) | Tight projection: `id, name, context_id, created_at, updated_at, kind, trust_score, trust_tier, page_count` | **LOW — TBD-3 (`name`).** All shipped fields are metadata except `name`. `name` is tagged content in the design doc (deal-codename leak class T3). Today this leaks; Phase 2b's helper drops `name` and replaces it with `title_redacted: "·············"` or a stable hash. |
| `approvals` block: `db.boardpacks.find(... {projection})` (line 506–513) | `id, title, subject, context_id, created_at` | **HIGH — leak.** `title`, `subject` shipped raw cross-context. |
| `approvals` block: `db.inbound_queue.find(... {projection})` (line 515–518) | `id, subject, context_id, created_at, sender` | **HIGH — leak.** `subject` and `sender` are content. |

**Net.** The home-stream is shipping 4–5 content fields across context boundaries today. Phase-1 testers see this as "the home page" so the leak is heavily user-visible. **Highest priority for Phase 2b.**

---

### `GET /app/pulse` (frontend) → `pages/PulsePlaceholder.jsx`
**No backend route exists today.**

```
$ grep -rn "router\.(get|post).*['\"]/pulse" backend/routers/   →   no matches
```

| Filter | — |
|---|---|
| Content fields shipped | None — page is a static holding placeholder. |
| **Severity** | **NONE.** The Pulse surface does not exist yet. By construction, leakage = 0. |

The non-existence of a backend Pulse endpoint is what makes Phase 2b → 2c possible: there is nothing to retro-fit. We design the wall, then build Pulse on top of it.

---

### `GET /api/me/governance` — `routers/governance.py:189`
**User's own governance panel — aggregates audit + classification across the user's contexts.**

| Filter | Currently filters by `context_id`? | Notes |
|---|---|---|
| Membership | Yes | `_user_context_ids(current.id)`. |
| `audit_log` rows | `{"$or": [{"context_id": {"$in": ctx_ids}}, {"account_id": current.id}]}` | Membership-keyed. Cross-context by design. |
| Audit row projection | `{"_id": 0}` only — full row | **HIGH — leak via `details`.** TBD-4 in design doc. `details` is a free-form blob; the action-type-by-action-type sweep has not been done. Some action types (e.g. `document.uploaded`, `briefing.created`) put `title` / `name` in `details`. Today these flow into the recent-10 list cross-context. |
| `synisense_runs` aggregation | `_build_synisense_block(current, ctx_ids)` reads counts only | Counts + categorical fields only. Looked at the helper; no raw text or offsets shipped. **NONE.** |
| `classification_breakdown` | Counts only, projected `{classification, updated_at, created_at}` | **NONE.** |

**Net.** One **HIGH** path through `audit_log.details`. Closes when 2b's helper applies a `details` redactor that drops free-form keys not in a per-`action` allowlist.

---

### `GET /api/me/governance/audit` — `routers/governance.py:309`
**Paginated, filterable audit log.**

| Filter | Currently filters by `context_id`? | Notes |
|---|---|---|
| Membership | Yes | Same `_user_context_ids` membership scope. |
| Row projection | Full row | **HIGH — leak via `details`** (same TBD-4 as above). |

Same severity as above — **HIGH** — and closes via the same helper. Lists in this audit separately because the Phase 2b refactor must touch both call sites.

---

### `POST /api/me/governance/audit/export` — `routers/governance.py:363`
**CSV / NDJSON export of the same audit feed.**

Inherits the same leakage class as the GET endpoint (it iterates the same query). **HIGH.** Phase 2b must wrap this too.

---

### `GET /api/me/review-queue` — `routers/daily_review.py:172`
**User's own daily-review queue across her contexts.**

| Filter | Currently filters by `context_id`? | Notes |
|---|---|---|
| Membership | Yes | `_user_context_ids(account.id)`. |
| `inbound_queue.find({"context_id": {"$in": cids}, "status": "pending_review"}, {"_id": 0})` (line 206) | Full row | Surfaces inbound subject + sender + body across contexts. |
| `boardpacks.find({"context_id": {"$in": cids}, "status": "active"}, {"_id": 0})` (line 209) | Full row | Surfaces full boardpack including `commentary` cross-context. |
| `studio_<kind>.find({"context_id": {"$in": cids}, "block_status": "in_review"}, {"_id": 0})` | Full row | Surfaces draft block bodies cross-context. |
| `solva_cycle_handoff_queue.find(...)` | Full row | |

**However** — the user is the **same authenticated person on every context** in the queue. Daily Review is a single-user productivity surface: every item is something *she* owes a decision on, in a context *she* is a member of with the right role. By the design-doc litmus (§1: "we are NOT trying to prevent the user from seeing her own data"), this is **NOT a Privacy Wall threat** — it is a normal authorised read.

| **Severity** | **NONE.** Per-context membership + per-action role check is the right scope. Daily Review will not pass through `project_for_pulse`. |
|---|---|

> **Important nuance for the design.** Pulse is different from Daily
> Review precisely because Pulse synthesises *across* the contexts in
> ways the user couldn't synthesise herself by clicking each board.
> Pulse imputes patterns. Daily Review just lists. The wall guards the
> first; the second is fine as-is.

---

### `GET /api/me/inbound-queue/counts` — `routers/inbound_queue.py`
Counts only, per-context. **NONE.**

### `GET /api/me/shares/inbox` — `routers/shares.py:314`
### `GET /api/me/shares/outbox` — `routers/shares.py:330`
The inbox surface lists shares **made TO the user** (or **BY the user**). Each row carries an explicit per-share token; the share writer chose to expose those rows cross-tenant. Rows ship the artefact body via the per-share read endpoint (`GET /api/shares/{sid}`), not directly. **NONE.** (Sharing is opt-in and per-artefact.)

### `GET /api/contexts/{cid}/mentions` — `routers/comments.py:244`
Per-context. **NONE.**

---

### Admin surfaces

#### `GET /api/admin/health/full` — `routers/admin_health.py:170`
Pings external dependencies. No content shipped. **NONE.**

#### `GET /api/admin/sandbox/{kpi,objectives}` — `routers/admin_sandbox_kpi.py`
Aggregates `sandbox_v2_sessions` across all sessions. Sessions are not membership-bound (they are pre-auth ghost rows). Projection is counts + funnel-stage labels only. No content. **NONE.**

#### `GET /api/admin/signals/action-heatmap` — `routers/admin_signal_kpi.py:31`
Quick view: aggregates over `signal_actions` and `signals`. **TODO-AUDIT-NEEDED** — the heatmap projection was not inspected in detail in this pass. Phase 2b will sweep it; if it ships `signal.headline` it's HIGH, else NONE.

| **Severity** | **TBD — needs targeted re-audit before 2b lands.** Documented as a follow-up so we don't paper over it. |
|---|---|

#### `GET /api/admin/llm/{spend, decks/quality, retries_24h}` — `routers/admin_llm_spend.py`
Ledger-style aggregates over `llm_deep_usage`, `llm_validator_usage`, `llm_retry_log`, `deck_telemetry`. These collections are billing/observability, not content. The retry-log has a `last_error` truncated string but it's a stack trace, not user content. **NONE** for billing fields. **LOW** for `last_error` (could in principle quote a prompt fragment). Phase 2b documents the truncation rule and verifies.

#### `GET /api/admin/auth/events` — `routers/admin_auth_events.py:33`
IP, UA, account-id, event type. No business content. **NONE.**

#### `GET /api/admin/synisense/perf` — `routers/synisense.py:141`
Returns the in-memory perf ring buffer (latency, surface, layers used, span counts) and a status snapshot. The ring's row schema deliberately excludes input text and span offsets. **NONE.**

#### `POST /api/admin/journal/backfill` — `routers/admin_journal.py:41` (Phase 1, this round)
Returns a counts summary (total / eligible / generated / skipped / failed). The `failed[]` list carries `doc_id` + `error` string. The doc-id is metadata; the error string is from `llm_service.call_llm` and `synisense_pipeline.run` and could in principle quote a fragment of the input on a parse failure. **LOW.** Phase 2b adds a `clip_to(80)` on the error string to be safe.

---

### Chat surfaces

#### `GET /api/chats/{chat_id}/audit` — `routers/chat.py:1255`
Filtered by `{"chat_id": chat_id, "account_id": current.id}`. Per-chat, per-user. **NONE.**

#### `GET /api/chats/{chat_id}/audit/export.zip` — `routers/chat.py:1284`
Same scope as the GET. **NONE.**

#### `POST /api/admin/chat-retention/sweep` — `routers/chat.py`
Operations endpoint, no content shipped to caller (returns counts of what got soft-deleted). **NONE.**

---

### Solva surfaces
All Solva v2 reads (`/api/solva/v2/sessions[/{sid}]`) are per-account-and-context. The cron sweep emits counts. **NONE.**

### Studio surfaces
All Studio reads are per-context. The public-read tokens (`/api/public/studio/read/{token}`) ship `body_redacted` only and are gated by a server-side recursive walk that 500s on internal-field leakage (already a documented hard guard). **NONE.**

### Document surfaces
All document reads are per-context-id in the URL path. **NONE.**

### Sandbox v2
Pre-auth, per-ephemeral-session. Cross-session reads do not exist. **NONE.**

---

## 2 · Net leakage scoreboard (today)

| Severity | Count | Surfaces |
|---|---|---|
| **HIGH** | **5** | `home/stream` (signals), `home/stream` (boardpacks), `home/stream` (approvals: boardpacks), `home/stream` (approvals: inbound), `me/governance` + `me/governance/audit` + `me/governance/audit/export` (audit_log.details) |
| **LOW** | **3** | `home/stream` (documents.name), `admin/llm/retries_24h` (last_error), `admin/journal/backfill` (failed[].error) |
| **TBD** | **1** | `admin/signals/action-heatmap` (re-audit needed) |
| **NONE** | rest | — |

---

## 3 · What Phase 2b must close

In priority order:

1. **`/api/me/home/stream`** — wrap all four `find()` results through `project_for_pulse(...)`. Replace `_id: 0` projections with explicit allowlists drawn from §2 of the design doc. Tier-1 priority: this is the user-visible surface that exists today.
2. **`/api/me/governance`** + **`/api/me/governance/audit`** + **`/api/me/governance/audit/export`** — wrap the audit-row stream through `project_audit_row(...)` which strips `details` keys not in a per-`action` allowlist. Resolves TBD-4.
3. **`/admin/signals/action-heatmap`** — targeted re-audit, classify, fix if HIGH.
4. **The two LOW items** (`admin/llm/retries_24h`, `admin/journal/backfill.failed`) — apply a defensive `clip_to(80)` on the error strings.
5. **The static AST sweep test** (`test_privacy_wall_route_coverage.py`) goes in CI so Phase 2c (Pulse) is born wall-aware: every new cross-context call site is forced to either go through the helper or explicitly opt into the "this is a per-context surface" exception via a `# privacy-wall: per-context` comment.

What Phase 2b deliberately does NOT touch:

- Daily Review (`/api/me/review-queue`) — fine as-is.
- Mentions, comments, shares — all per-context or per-share-token.
- All admin observability surfaces except the three flagged above.
- All chat / Solva / Studio / Document surfaces.

---

## 4 · How this audit was produced

```bash
$ grep -rn -E 'router\.(get|post)' backend/routers/ | wc -l
$ grep -n -E '"\$in".*context_id|context_id.*"\$in"' backend/routers/*.py
$ grep -n '_user_context_ids|active_ctx_ids|cids' backend/routers/*.py
$ view_file every flagged route's projection
```

Re-runnable. The full set of cross-context call sites is enumerated
above; if a future surface is added, the AST sweep test from §5
of the design doc will fail until it's classified here.

---
Last updated: 2026-05-05 by main agent.
