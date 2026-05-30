# P5 — P4 corrections + OAuth-mode consume (2026-02) ✅

Closes the two tester-found regressions on P4 + ships the OAuth-mode
magic-link consume across Google and Microsoft + appends the P4-pattern
discipline note to the self-verification postmortem.

## P5.1 — Admin UI surfaces magic_url with copy-to-clipboard ✅

**Root cause of the P4 miss:** the original P4.B implementation
rendered the pinned panel INSIDE `items.map(...)` — when the
admin clicked Approve, the post-action `load()` re-fetched the list
filtered to `received`, the just-approved row dropped out of the
filter, and the React parent unmounted the row + its pinned panel
together. The toast was the only surviving artefact. Net effect: no
way for the admin to copy the magic link.

**Fix:** moved the pinned panel out of the row map into a
persistent `<div data-testid="admin-cohort-pinned-links">` section
above the row list. Filter changes / list reloads cannot make it
vanish. The container key remains `pinnedLinks[appId]` so the
existing copy/dismiss state survives unchanged.

**Live verification:** `/tmp/p5_1_admin_magic_link_trace.py` —
admin signs in, approves a seeded application, the green panel
mounts above the row list, the `magic_url` text is the exact backend
return value, the Copy button writes that exact value to
`navigator.clipboard`, and the button text flips to "Copied". 7/7
trace steps green.

## P5.2 — `/welcome/{token}` post-consume redirect lands on /app, not /signin ✅

**Root cause of the P4 miss:** the consume handler called
`navigate(redirect)` (react-router) which preserves the SPA mount.
AuthContext's `account === false` snapshot (set when the user
unauthenticated-landed on /welcome) outlived the consume response;
`<Gated>` saw the snapshot and bounced to /signin BEFORE AuthContext
bootstrap re-fetched against the new HttpOnly cookies.

**Fix:** swap `navigate(target)` for `window.location.href = target`
in `WelcomePage.submitPassword`. Full-page reload → AuthContext
re-mounts → `/auth/me` returns the live account → `<Gated>` lets
the user through.

**Live verification:** `/tmp/p5_2_welcome_consume_trace.py` —
loads `/welcome/{token}`, sets a password, asserts final URL =
`/app/first-session` (not `/signin`), confirms `access_token` +
`refresh_token` + `csrf_token` cookies are set. 5/5 trace steps green.

## P5.3 — OAuth-mode consume wires magic_link_token across both providers ✅

**The 3 gaps shipped in this slice:**

1. **Backend Microsoft `/start`** now accepts `magic_link_token` as a
   query param and packs it into the state JWT under the `mlt` claim.
   The existing `/microsoft/callback` already extracted `mlt` from
   `state_payload` (P4 leftover); now the round-trip closes.
2. **Frontend `WelcomePage.withMagicLinkOAuth`** rewritten:
   - Microsoft path: `GET /microsoft/start?magic_link_token=X` → parse
     `authorize_url` from JSON response → `window.location.href`.
   - Google path: stash token in `sessionStorage` under
     `akki.pending_magic_link_token` → `GET /google/start` → build
     `auth_base_url + ?redirect=window.location.origin/oauth/callback`
     → `window.location.href`. (Emergent Auth's flow can't carry
     custom state across its redirect, hence the sessionStorage stash.)
3. **Frontend `OAuthCallback`** pops the sessionStorage stash and
   forwards `magic_link_token` to `POST /google/finish` alongside
   `session_id`. Stash key is removed in the same statement so a
   back-button replay can't try to re-consume.

Backend Google `/finish` already accepted `magic_link_token` from a
prior session; I also extended both Google and Microsoft find-or-create
paths to query `email_lc` (mirrors the magic-link consume invariant)
and to write `email_lc` on new account creation. Without this the
`cohort_application_id` linkage would fail for cross-provider sign-ins.

**Live verification:** `/tmp/p5_3_oauth_start_trace_v2.py` — mints a
fresh magic link via the admin REST API, opens `/welcome/{token}`,
exercises both Google and Microsoft buttons, asserts:
  - Google: `sessionStorage["akki.pending_magic_link_token"]` matches
    the minted token AND the navigation target is
    `https://auth.emergentagent.com/?redirect=...`.
  - Microsoft: backend `/microsoft/start` and SPA-driven click both
    produce an authorize_url whose state JWT's `mlt` claim equals
    the minted token (decoded server-side with `JWT_SECRET`).
4/4 trace steps green.

**HUMAN_REQUIRED:** the full OAuth round-trip (auth.emergentagent.com
landing → Google consent → callback → /google/finish consume) cannot
be exercised in headless Playwright because Emergent Auth requires
human consent on the Google login page. Backend code path is locked
by 7 pytest assertions (`test_phase_p5_corrections.py::test_p5_3_*`)
incl. a mocked `_fetch_emergent_session_data` round-trip that
confirms `magic_link_consumed: True` + `cohort_application_id`
linkage + 410 on replay. Same situation applies to Microsoft —
covered by `test_p5_3_ms_start_packs_magic_link_token_in_state` +
`test_p5_3_ms_state_carries_mlt_when_provided`.

## P5.4 — Postmortem discipline note appended ✅

Added a "P4 corrections — repeated misses" section to
`/app/memory/sprints/P2_1_self_verification_postmortem.md` with:
- Per-miss "what my self-check did" / "what actually happened" /
  "what would have caught it" breakdown matching the original
  postmortem template.
- The sharper rule: post-action settle window must be waited out
  (network round-trip + React commit + filter reapplication +
  AuthContext bootstrap) before measuring; the DOM scan must be the
  LAST step of the trace.

## Tests + gates

- **`test_phase_p5_corrections.py`:** 7/7 GREEN.
  - 4 OAuth-state-JWT lockdowns (mlt present, mlt absent, sign+verify
    round-trip, microsoft start status).
  - 2 Google finish acceptance probes (consumes; rejects replay).
  - 1 Google finish backward-compat (no-mlt path unchanged).
  - 1 backend P5.2 consume-redirect-shape probe.
- **`test_solva_v1_unchanged.py`:** 4/4 GREEN. Byte-identical guard
  holds.
- **`test_phase_u_oauth.py`:** 16/16 GREEN when run before P5
  (default Phase-U-first ordering). The 2 `test_U_d_finish_*` async
  tests hit a PRE-EXISTING event-loop binding issue when P5 runs
  first (Motor binds to one loop; pytest-asyncio uses another) —
  verified by stashing all P5 changes and reproducing the same 2
  failures. Out of scope for P5; a separate test-harness slice.
- **Voice-lint:** clean across customer-copy surfaces.
- **ESLint:** clean on all 3 touched frontend files.
- **Ruff:** 2 pre-existing E401 multi-import warnings on PKCE
  helpers — not P5 territory.
