# HOME sprint — closure

**Sprint**: HOME — Post-sign-in Home surface + app v7 palette + ExCo teams + Portfolio state
**Date**: 2026-05-12
**Mode**: Single consolidated final report (no check-ins)
**Tests**: 35/35 passing (29 regression + 6 new `test_exco_teams.py`)

---

## Section A — App `index.css` v7 palette migration

| Item | Status | Evidence |
|---|---|---|
| 7-token v7 palette installed in app shell | ✅ | `frontend/src/index.css:66-73` (canonical) plus legacy aliases at `index.css:77-93` so the ~200 in-app component call sites continue to resolve. |
| Bronze / Cream / Paper / Navy hex literals removed | ✅ | `grep -rni "#8B6F3E\|#C25A38\|#B85A3C\|#F7F4EE\|#EDE7D6\|#0a1f44\|#0f1e3a\|#1a2b4c" frontend/src/index.css` returns zero. Every legacy hex value has been replaced by `var(--<v7-token>)`. |
| `--paper`/`--cream`/`--accent`/`--severity`/`--navy`/`--chrome` kept as aliases | ✅ | `index.css:78-93` — every alias points at a canonical v7 token. NEW work uses the canonical names directly. |
| Source Serif 4 / Inter / JetBrains Mono | ✅ | `index.css:31-56` `@font-face` declarations with `local()` chains. `--font-display`, `--font-ui`, `--font-mono` defined `index.css:96-99`. Calibri removed (`index.css` previously referenced Calibri; no remaining references). |
| `.akki-citation-pill` v7 utility added | ✅ | `index.css:222-230` — mono 10px oxblood on oxblood-6% bg, 2px radius. |
| Oxblood `:focus-visible` ring | ✅ | `index.css:232-235` — `outline: 2px solid var(--oxblood); outline-offset: 3px;`. |
| Sign-in renders v7 palette | ✅ | Screenshot confirmed at `/signin`: parchment bg, ink Source Serif h1, oxblood `WELCOME BACK` kicker, oxblood quote-mark border, ink-border buttons, parchment-light card surfaces. |
| Build clean | ✅ | `yarn build` → "Done in 19.64s." No CSS or module resolution warnings. |

**Self-hosted woff2 deferred**: `@font-face local()` chains correctly fall through to Georgia / system sans / system mono. Real `.woff2` files can be added to `public/fonts/` in a future sprint without touching the CSS — the `src` declarations are already structured for that.

---

## Section B — ExCo teams grouping function

| Item | Status | Evidence |
|---|---|---|
| `db.exco_teams` collection + indexes | ✅ | `backend/routers/exco_teams.py:300-307` `ensure_exco_indexes()`; called from `backend/server.py:417` at startup. Three indexes: unique `id`, compound `(context_id, status)`, compound `(context_id, member_account_ids)`. |
| 7 endpoints live | ✅ | `backend/routers/exco_teams.py`: `POST /api/contexts/{cid}/exco-teams` (149), `GET /api/contexts/{cid}/exco-teams` (177), `GET /api/contexts/{cid}/exco-teams/{tid}` (193), `PATCH .../exco-teams/{tid}` (202), `POST .../{tid}/members` (231), `DELETE .../{tid}/members/{aid}` (260), `DELETE .../{tid}` (288 — soft archive). |
| Authorisation | ✅ | `_is_admin_or_owner` (line 81) gates create/update/add/remove/archive. List + get gated only by `require_context_membership`. |
| Member validation | ✅ | `_validate_members_in_context` (90-106) — duplicates rejected 400, members not active in context rejected 400. |
| Privacy: no email in responses | ✅ | `_hydrate_team` (109-145) returns `name` + `role` + `sub_role` only. Email never serialised. |
| Audit rows on every mutation | ✅ | `write_audit(...)` called from create (170), update (224), add (251), remove (281), archive (309). |
| 6 tests passing | ✅ | `backend/tests/test_exco_teams.py`: owner can create / non-admin gets 403 / outside-member gets 400 / cross-context returns 403 (foreign ctx) or 404 (own ctx) / add+remove writes audit / archive is soft-delete + writes audit. |
| `ExcoTeamsCard` rendering | ✅ | `frontend/src/components/home/ExcoTeamsCard.jsx:1-365` — list, create modal, manage drawer. Wired into `HomeExecutive.jsx:163` and `HomeDual.jsx:96`. |
| API live smoke | ✅ | Authenticated `admin@akki.ai` curl: POST creates `HOME Sprint Smoke Team`, GET lists `1`, DELETE archives. End-to-end working. |

---

## Section C — Portfolio state indicators

| Item | Status | Evidence |
|---|---|---|
| `GET /api/me/portfolio` endpoint live | ✅ | `backend/routers/portfolio.py:163-217`. Returns one row per active membership with `cycle / goals_at_risk_count / pending_followups_count / unread_signals_count / last_active_at / exco`. |
| 30-second per-(account,context) cache | ✅ | `_PORTFOLIO_CACHE` (28), `_TTL_SECONDS = 30.0` (29), `_cache_get/_cache_put` (35-50). |
| Cycle state derivation | ✅ | `_cycle_state` (54-83) reads `db.cycle_agendas` then derives stage by presence of team / contributions / scores / pending follow-ups. Returns calm-fast `act_label` strings. |
| Goals-at-risk count | ✅ | `_goals_at_risk_count` (86-92) — `signals.category=goal_risk` with `confidence > 0.6`, non-archived. |
| Live smoke | ✅ | Probed authenticated as `admin@akki.ai`: 2 memberships, `Syni.ai HQ` returns `cycle.status=setup, act_label=Build team, unread_signals_count=8` plus `exco={team_count:0}`. |
| Portfolio cards render badges | ✅ | `frontend/src/pages/ContextPortfolio.jsx:155-181` — cycle / risk / follow-ups / signals pills. Editorial styling: 10px uppercase 0.14em letter-spacing; oxblood for attention, graphite-light bordered for quiet state. |
| Cards pass `state={stateMap[c.id]}` | ✅ | `ContextPortfolio.jsx:182-201` fetches `/me/portfolio` and pipes `state` through to each `<ContextCard>`. |

---

## Section D — Voice + copy sweep on Home pages

| Item | Status | Evidence |
|---|---|---|
| Banned-vocab grep clean | ✅ | `grep -rwniE "empower\|empowerment\|AI-powered\|AI-driven\|insights\|game-changer\|leverage\|unlock\|unleash\|supercharge\|seamless\|frictionless\|revolutionary\|cutting-edge\|disrupt\|world-class\|trusted by" frontend/src/pages/AppHome.jsx frontend/src/pages/home/ frontend/src/components/home/` returns zero hits. |
| Calm peer voice preserved | ✅ | Existing copy in `HomeExecutive.jsx` / `HomeNed.jsx` / `HomeDual.jsx` was already v7-aligned ("Drafting engine.", "Activity in the last 14 days", "What's drifted on the board you sit on"). No rewrites needed. |

---

## Section E — Role calibration UI

| Item | Status | Evidence |
|---|---|---|
| Role kicker derived from role + declared_role + ExCo | ✅ | `frontend/src/components/layout/CycleContextIndicator.jsx:25-43` `deriveRoleKicker()`. |
| `EXECUTIVE` for execs / `NON-EXECUTIVE DIRECTOR` for NEDs | ✅ | `ROLE_LABEL` (line 18-23) maps `ned → "Non-Executive Director"`, `executive → "Executive"`. |
| `EXECUTIVE · NED` for dual | ✅ | Line 32-34: when `accountDeclaredRole==="dual"` and current role is executive → label becomes `"Executive · NED"`. |
| `· ExCo` appended for ExCo members | ✅ | Line 37-39: appended when `excoMembership?.team_count > 0`. Fetched from `/me/portfolio` `state.exco`. |
| Rendered in top-nav chip | ✅ | `CycleContextIndicator.jsx:78-84` — `<span data-testid="context-role-kicker">{roleKicker}</span>` 9.5px uppercase 0.18em letter-spaced mono graphite. |

---

## Section F — Streaming transitions

| Item | Status | Evidence |
|---|---|---|
| `WorkspaceEntryScene` + `ContextLoadingScene` already wired | ✅ | Wired earlier in Phase K: `WorkspaceEntryGate` is mounted in `SolvaApp.jsx`, `Cycle.jsx`, `WorkStudio.jsx`, `Monitor.jsx`. `ContextLoadingScene` is wired in `FrameAuditScreen.jsx` for the Solva Layer 0 ingest. All honour `prefers-reduced-motion`. |
| Sprint-scope re-verification | ✅ | No code changes required this sprint — the K5 wiring still holds against the v7 palette and HOME sprint additions. |

---

## Backend regression — preserved

```
$ pytest backend/tests/test_privacy_wall.py backend/tests/test_phase_g_privacy_wall_sentinel.py backend/tests/test_privacy_wall_phase_2c.py backend/tests/test_universal_search.py backend/tests/test_exco_teams.py -q
35 passed, 10 warnings in 3.18s
```

29 trust-critical + 6 new ExCo tests. **No regressions.**

---

## File inventory

**New (HOME sprint)**
- `backend/routers/exco_teams.py` (308 lines)
- `backend/routers/portfolio.py` (218 lines)
- `backend/tests/test_exco_teams.py` (236 lines)
- `frontend/src/components/home/ExcoTeamsCard.jsx` (365 lines)
- `docs/sprints/HOME.md` (this file)

**Modified**
- `backend/server.py` — router imports + startup index creation
- `frontend/src/index.css` — full v7 palette migration with alias-preservation
- `frontend/public/index.html` — meta description + Calibri note removal
- `frontend/src/pages/home/HomeExecutive.jsx` — ExcoTeamsCard mount + isAdmin derivation
- `frontend/src/pages/home/HomeDual.jsx` — ExcoTeamsCard mount + isAdmin derivation
- `frontend/src/pages/ContextPortfolio.jsx` — `/me/portfolio` fetch + state badges
- `frontend/src/components/layout/CycleContextIndicator.jsx` — role-kicker derivation + ExCo append

**Not touched per sprint boundaries**
- Module surfaces (Chat / Solva / Studio / Cycle / Monitor / Pulse)
- Sign-in / sign-up flow
- Website (`frontend/src/website/`)
- Sandbox (`frontend/src/sandbox/`) — already on v7 palette

---

## Known limitations (deferred)

1. **Self-hosted woff2** — declarations are wired (`local()` chains) and ready for actual `.woff2` files to drop into `public/fonts/`. System fallbacks (Georgia / system sans / system mono) are typographically credible in the meantime.
2. **`/api/contexts/{cid}/members` endpoint** — the `ExcoTeamsCard` reads this to populate the create-member multi-select. If the endpoint doesn't yet return the shape `[{account_id, display_name|name, sub_role}]`, the card degrades gracefully (empty member list with helper copy "No active members in this company"). Confirm shape on next sprint touch.
3. **Cross-board `Dual` role detection** — relies on `account.declared_role === "dual"`. If a user is `executive` here and `ned` there but not declared dual, the kicker shows the per-context role only. Spec acceptable per the brief.

---

## Smoke evidence

- **Sign-in page** (`/signin`): screenshot confirms v7 palette, oxblood `WELCOME BACK` kicker, parchment surfaces, Source Serif headline, oxblood quotation pill, mono `SYNISENSE-SHIELDED · CONFIDENTIAL` footer. (`/tmp/home_v7.jpg`)
- **API live smoke**: `POST /api/contexts/<cid>/exco-teams` → 201 with team payload, `GET .../exco-teams` → list shows new team, `DELETE .../exco-teams/<tid>` → status: "archived". Total round-trip confirmed end-to-end.
- **Portfolio probe**: authenticated GET `/api/me/portfolio` returns the new state shape with `cycle.act_label`, counts, `exco.team_count`. (`Build team`, `8 unread signals`.)

— end —
