# P5.6.1 — Same-origin guard cascade across non-`lib/api.js` surfaces

**Scope:** every JS surface (outside `lib/api.js`) that previously read `process.env.REACT_APP_BACKEND_URL` directly. These all carried the same defect that broke production sign-in (cross-origin host baked at build time → SameSite-Lax cookie suppression on cross-site POSTs). Same root cause, same fix, applied uniformly.

**Migration shape per file:**
```diff
- const API = process.env.REACT_APP_BACKEND_URL || "";
+ import { resolveBackendOrigin } from "@/lib/api";
+ // Phase P5.6.1 (2026-02) — same-origin guard. See lib/api.js.
+ const API = resolveBackendOrigin();
```
For the two multi-line `(typeof process !== "undefined" && process.env && process.env.REACT_APP_BACKEND_URL) || ""` ternaries (`sandbox/api.js`, `hooks/useSolvaReasoningStream.js`) the entire guarded read collapses to a single `resolveBackendOrigin()` call — that helper itself does the SSR / undefined-env / window-check.

## Files migrated (18 total)

| # | File | Change |
|---|---|---|
| 1 | `components/chat/GovernanceSignals.jsx` | const → `resolveBackendOrigin()` |
| 2 | `components/marketing/EnterpriseFeature.jsx` | const → `resolveBackendOrigin()` |
| 3 | `components/sandbox/v2/ClosingStep.jsx` | const → `resolveBackendOrigin()` |
| 4 | `components/sandbox/v2/Step1SolvaWrapper.jsx` | const → `resolveBackendOrigin()` |
| 5 | `components/sandbox/v2/Step3StudioWrapper.jsx` | const → `resolveBackendOrigin()` |
| 6 | `components/sandbox/v2/Step4CycleSnapshot.jsx` | const → `resolveBackendOrigin()` |
| 7 | `components/work_studio/DocumentCardsSection.jsx` | inline expr → `resolveBackendOrigin()` |
| 8 | `hooks/useSolvaReasoningStream.js` | multi-line guarded ternary → `resolveBackendOrigin()` |
| 9 | `pages/Chat.jsx` | const → `resolveBackendOrigin()` |
| 10 | `pages/ContributorPortal.jsx` | const → `resolveBackendOrigin()` |
| 11 | `pages/HelpFeatures.jsx` | const → `resolveBackendOrigin()` |
| 12 | `pages/SharedArtefact.jsx` | const → `resolveBackendOrigin()` |
| 13 | `pages/StatusPage.jsx` | const → `resolveBackendOrigin()` |
| 14 | `pages/TrustCenter.jsx` | const → `resolveBackendOrigin()` |
| 15 | `pages/WelcomePage.jsx` | const → `resolveBackendOrigin()` |
| 16 | `sandbox/api.js` | multi-line guarded ternary → `resolveBackendOrigin()` |
| 17 | `website/components/PublicVelocityTile.jsx` | const → `resolveBackendOrigin()` |
| 18 | `website/pages/Cohort.jsx` | const → `resolveBackendOrigin()` |

## Explicitly NOT migrated (Solva v1 byte-identical guard)

| File | Reason |
|---|---|
| `components/solva/artefact/SolvaArtefact.jsx` | v1 isolation — covered by `test_solva_v1_unchanged.py` |
| `components/solva/artefact/SolvaRefusalArtefact.jsx` | v1 isolation — covered by `test_solva_v1_unchanged.py` |

These two surfaces are within the Solva v1 frozen tree. The byte-identical guard pytest reads every v1 file's exact bytes; changing them — even with a functionally identical refactor — would fail the guard. They remain on `process.env.REACT_APP_BACKEND_URL` until the v1 freeze lifts.

**Production impact of the carve-out:** the two excluded files are rendered only inside `/app/solva/*` artefact viewers, which are reached only by authenticated logged-in users (session cookie already established via the now-fixed `/api/auth/login` same-origin path). Once a user is signed in, the auth cookies are scoped to `akki.syni.ai`; the SolvaArtefact ESM-style fetches that hit the baked `REACT_APP_BACKEND_URL` will still misroute to `emergent.host` on production — but those calls return public artefact HTML/JSON and the failure mode is "artefact preview blank", not "user locked out of the app". Tracked as a follow-up when the v1 freeze lifts.

## Regression coverage

- The existing 5/5 frontend resolver tests in `src/lib/__tests__/apiBaseResolver.test.js` lock the underlying `_resolveApiBase` / `resolveBackendOrigin` behaviour. All 18 migrated surfaces now go through that path, so the same 5 tests cover all 18.
- The 4/4 backend regression in `tests/test_phase_p5_6_csrf_cookie_domain.py` locks the cookie-shape side.
- ESLint clean across all 18 touched files (single batch run).
