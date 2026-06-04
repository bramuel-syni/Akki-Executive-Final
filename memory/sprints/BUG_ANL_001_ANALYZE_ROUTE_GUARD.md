# BUG-ANL-001 — Analyze Journal route guard

**Shipped:** 2026-06-04 (single-dispatch surgical fix per user direction)
**Approver:** User picked option (a) — route guard → redirect when `context_id` missing.

---

## Symptom (user-reported)

- URL: `/app/analyze` with NO `context_id` query param.
- Page renders the Analyze Journal listing + "New Analysis" upload form.
- Red toast top-right: `context_id_required`.
- Silent broken state — upload button visible but POST would fail with the same error.
- Screenshot: https://customer-assets.emergentagent.com/job_feature-docs/artifacts/mc4gtnev_Screenshot_20260604_222916_Chrome.jpg

---

## Ground-truth read

**Route**: `pages/AnalyzeJournal.jsx` (mounted at `/app/analyze` per `App.js:490`).

**Trigger surface**: the listing call `GET /workbook/v2/analyses` does NOT require `context_id` (filters by account-scope only — `workbook_analysis.py:1136-1170`). The actual `context_id_required` error fires from `POST /workbook/upload-multi` at `workbook_analysis.py:660-665` when the route's `context_id` form field is absent AND the user's `active_context_id` on the account row is also unset.

The user's screenshot showed the toast on direct page load — most likely path: a previous upload attempt without a context, OR a global axios response interceptor that surfaces the 400 from a different background call that ran with no context. Either way, the **route guard is the right intervention** because the page is in a silent broken state any time `context_id` is absent.

---

## Fix landed

`pages/AnalyzeJournal.jsx`:

1. Imported `useAuth` from `@/contexts/AuthContext` to read `activeContextId` and `account.default_context_id`.
2. Added an `effectiveContextId` derived value: URL `?context_id=` → `activeContextId` → `account.default_context_id` → `null`.
3. Mount-time `useEffect` that runs once `auth.account` is hydrated:
   - If URL already carries `context_id`: no-op.
   - If a default or active context exists: `setParams({ context_id: <id> }, { replace: true })` — backfills the URL without a history entry.
   - Otherwise: `toast.info("Pick a context to view your Analyze Journal.")` + `navigate("/app/home", { replace: true })`.
4. Defensive belt: `onCreate` (the upload submit handler) now explicitly threads `effectiveContextId` into the multipart `FormData` so the backend never has to fall back to `active_context_id`. If still missing at submit time, the upload is blocked with an informational toast + redirect.

**Files touched (1):**

```
frontend/src/pages/AnalyzeJournal.jsx     +35 LOC / -6 LOC
```

**Backend unchanged.** Per user direction — `context_id_required` is a correct API contract.

---

## Coverage sweep (per user request)

Greped every page that fires `api.get`/`api.post` and references `context_id`:

| Route | Pattern | Verdict |
|---|---|---|
| `pages/AnalyzeJournal.jsx` | API call fires regardless of cid | **FIXED THIS DISPATCH** |
| `pages/Events.jsx` | `if (!cid) return` at line 445/457 | Safe — silently skips fetches when no context. |
| `pages/Questions.jsx` | Same `if (!cid) return` pattern | Safe. |
| `pages/TaskManager.jsx` | Same pattern | Safe. |
| `pages/InboundQueue.jsx` | Has guard signals | Safe. |
| `pages/WorkStudio.jsx` | Already gated behind WorkspaceEntryGate | Safe. |
| `pages/CompanyHome.jsx` | Home page itself; context picker lives here | Safe. |
| `pages/Learn.jsx`, `pages/TenantSettings.jsx` | Have guard signals | Safe. |

**No sibling bugs found.** Analyze Journal was the only top-level route that fired a `context_id`-required API call without first checking for a context.

---

## Verification (live preview)

Captured at `/tmp/bug_anl_001_case1.png` and via in-line screenshot tool against `https://akki-executive.preview.emergentagent.com`:

```
Case 1: /app/analyze (no context_id)
  URL after mount: /app/analyze?context_id=aff5e102-04b8-4948-9f6b-27c9eca1f0d7
  has context_id_required toast: False
  case1_redirect: PASS — URL backfilled
  case1_no_toast: PASS

Case 2: /app/analyze?context_id=<valid>
  URL: /app/analyze?context_id=aff5e102-04b8-4948-9f6b-27c9eca1f0d7
  case2_listing: PASS — upload input present, 8+ history rows render
  case2_no_toast: PASS
```

Screenshot confirms the page renders cleanly with the upload form ready and historical analyses listed — no red toast.

---

## Discipline rails observed

- **Ground-truth read first**: read `AnalyzeJournal.jsx:1-199`, `App.js:490`, `workbook_analysis.py:660-665`, `auth.py:233-292`, `core.py:406-445`, `AuthContext.js` (verified `account.default_context_id` is the canonical FE source) before any code change.
- **No backend changes**: `context_id_required` is a correct API error; we fixed the FE guard, not the contract.
- **No copy creep**: redirect toast copy is literally the user-provided string.
- **Surgical scope**: 1 file changed, 1 useEffect added, 1 FormData field appended, 1 import added. ~30 LOC delta net.
- **Coverage check completed**: greped 8 sibling routes, confirmed none have the same pattern.
- **No new dependencies**.
- **No Phase 6 work, no Phase 5 retouch**.

---

## What this dispatch did NOT touch

- The shared-HOC pattern was NOT introduced. The user's brief said "for ≤2 routes, fine; for more, surface and we scope a higher-level guard pattern separately." This dispatch fixes 1 route. The other 8 sibling routes all already handle missing-context gracefully via different mechanisms (`if (!cid) return`, WorkspaceEntryGate, etc.).

---

## Status

**BUG-ANL-001 → ✅ COMPLETE 2026-06-04T20:05:00Z.**
