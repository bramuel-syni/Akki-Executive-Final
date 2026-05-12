# Lint Rule — Raw `fetch()` Forbidden Outside the API Client (Patch 24B)

> Origin: P0 (Patch 23) — `UploadModal.jsx` used raw `fetch()` instead of the axios `api` client, dropping the `Authorization: Bearer <token>` header that AKKI's auth interceptor injects. Every upload returned **HTTP 401**. The fix is one line; the prevention is structural.

---

## Rule

`craco.config.js` `eslint.configure.rules`:
```js
"no-restricted-syntax": [
  "error",
  {
    selector: "CallExpression[callee.name='fetch']",
    message:
      "Use the project's `api` client (`import { api } from '@/lib/api'`) " +
      "instead of raw `fetch()`. Raw `fetch()` bypasses bearer-token / " +
      "X-Active-Context / error interceptors. " +
      "See /app/memory/sprints/LINT_API_CLIENT_RULE.md (Patch 24B). " +
      "Legitimate exception (SSE streaming, public marketing endpoint)? " +
      "Add `// eslint-disable-next-line no-restricted-syntax -- <reason>`.",
  },
  {
    selector: "NewExpression[callee.name='Request']",
    message: "Use the project's `api` client instead of constructing a raw `Request`."
  },
],
```

Severity: **error**. CI build fails on any new violation. Local `yarn build` fails the same way.

## Allowlist (whole-file)

Configured under `eslint.configure.overrides`:

| Path | Why |
|---|---|
| `src/lib/api.js` / `src/lib/api.ts` | The canonical axios wrapper itself. Has to talk to the network. |
| `src/sandbox/api.js` / `src/sandbox/api.ts` | Sandbox sub-app has its own public (no-auth) API surface. Same role as `lib/api.js` for the sandbox. |
| `**/*.test.{js,jsx,ts,tsx}`, `**/__tests__/**`, `tests/**` | Test files can use `fetch()` for setup, mocking, polyfills, etc. |

To add a new file to the allowlist, add an entry to `craco.config.js` `webpackConfig.eslint.configure.overrides`. Document the reason inline.

## Per-line escape hatch

For files that legitimately need raw `fetch()` (SSE streaming, public unauthenticated endpoints, multipart over fetch for streaming bodies), add:

```js
// eslint-disable-next-line no-restricted-syntax -- streaming SSE; axios cannot
const res = await fetch(endpoint, { … });
```

The `-- <reason>` after the disable directive is **mandatory** — without it, the next code reviewer has no way to evaluate whether the disable is still warranted.

## Current escape hatches in this codebase (Patch 24C inventory)

After the cleanup in Patch 24C, the following raw `fetch()` calls remain — all with the required disable + reason:

| File | Line | Reason |
|---|---|---|
| `src/pages/Chat.jsx` | 453 | Streaming SSE for chat tokens. Axios doesn't expose `ReadableStream` cleanly. Bearer token + X-Active-Context injected manually above the call. |
| `src/hooks/useStreamingPhases.js` | 97 | Streaming SSE for Solva / Cycle compile / Work Studio Enhance `phase` events. Bearer token injected manually inside the hook. |
| `src/components/marketing/EnterpriseFeature.jsx` | 58 | PUBLIC marketing endpoint (`/api/public/studio/sensitivity-demo`). Using `api` would inject Authorization from any cached localStorage token, tainting the server-side rate limit. |

All migrated to the `api` client (no escape hatch needed):
- `src/components/upload/UploadModal.jsx:163` (the original P0)
- `src/components/synisense/PreviewDrawer.jsx:90`
- `src/pages/TenantSettings.jsx:231`
- `src/pages/Decks.jsx:971`

Allowlisted at file level:
- `src/sandbox/api.js` (3 call sites — POST / GET / DELETE for sandbox sessions)

## Self-test verification

To prove the rule catches the regression:

```bash
cd /app/frontend
# Inject a synthetic violation
sed -i '/await api.post/i const _probe = fetch("/api/contexts/x/probe");' src/components/upload/UploadModal.jsx

CI=true yarn build
# Expect: build fails, error line points at the synthetic fetch()
# Output includes "no-restricted-syntax" rule name and the full message.

# Revert
git checkout src/components/upload/UploadModal.jsx
```

Verified during Patch 24B development (2026-05-12). Output:
```
src/components/upload/UploadModal.jsx
  Line 158:27:  Use the project's `api` client (…) instead of raw `fetch()`.   no-restricted-syntax
```

## Why `error` and not `warn`

- CRA + craco's eslint plugin treats warnings as build failures only when `CI=true`. We want failures on local builds too — that's where regressions get caught earliest.
- "warn" is silent in `yarn start` dev-server output; the rule could regress invisibly.
- Promoting from warn to error is the difference between "good intentions" and "structural guarantee".

— end of lint rule doc —
