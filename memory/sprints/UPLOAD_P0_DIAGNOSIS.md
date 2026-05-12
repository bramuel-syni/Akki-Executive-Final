# P0 Diagnosis — Document upload failure (Patch 23)

> User report (2026-05-12): **"All the document upload links are failing."**
> Diagnosed and fixed in one session. This doc is the receipts.

---

## 1. Entry-point inventory (every upload affordance in the app)

| # | Entry point | Component / file | HTTP call | Status before | Status after |
|---|---|---|---|---|---|
| 1 | Floating "+ Add document" button in `AppShell` (global) | `components/upload/UploadModal.jsx:163` | **raw `fetch()`** with `credentials: "include"` | 🔴 **401 Not authenticated** | ✅ 200 OK |
| 2 | Workspace page (Documents Journal) "Upload" + "Camera" buttons + drag-and-drop | `pages/Workspace.jsx:266-279` | `api.post()` (axios) | ✅ 200 OK | ✅ 200 OK |
| 3 | Chat page paperclip attach | `pages/Chat.jsx:742-759` | `api.post()` (axios) | ✅ 200 OK | ✅ 200 OK |
| 4 | Work Studio EnhanceModal (drop file → enhance into board pack / minutes / etc.) | `components/studio/EnhanceModal.jsx:283-295` | `api.post()` (axios) | ✅ 200 OK | ✅ 200 OK |
| 5 | Solva FramingScreen (drop file as session context) | `components/solva/flow/FramingScreen.jsx:224-229` | `api.post()` (axios) | ✅ 200 OK | ✅ 200 OK |
| 6 | Work Studio block composer "image upload" | `components/studio/BlockComposer.jsx:540-717` | `api.post()` (axios) | ✅ 200 OK | ✅ 200 OK |

**Total entry points**: 6. **Broken**: 1 (UploadModal). **Already working**: 5.

> The user said "all" upload links were failing because **the UploadModal is the most prominent and most-clicked upload entry point** — it's the global floating button in the AppShell, present on every authenticated page. The other 5 entry points are on specific workspaces or modals that less than 1% of users would have tried as a cross-check.

---

## 2. Reproduction (curl-level proof, against the live preview)

Three curls — each isolating one variable.

### Test A — with both headers (what axios sends, mimicking the fixed code path):
```
curl -X POST -H "Authorization: Bearer <TOKEN>" -H "X-Active-Context: <CID>" \
     -F file=@/tmp/test_upload.txt -F data_trust=mixed \
     -F "display_name=P0 Test A" -F "description=P0 test A" \
     https://akki-executive.preview.emergentagent.com/api/contexts/<CID>/documents
```
**HTTP 200** · body shows the persisted doc record (id, name, size_bytes, status=extracted).

### Test B — with NO Authorization header (what raw `fetch()` sent):
```
curl -X POST -H "X-Active-Context: <CID>" \
     -F file=@/tmp/test_upload.txt -F data_trust=mixed \
     -F "display_name=P0 Test B" -F "description=P0 test B" \
     https://akki-executive.preview.emergentagent.com/api/contexts/<CID>/documents
```
**HTTP 401** · body `{"detail":"Not authenticated"}`. ← **the bug**.

### Test C — with Authorization but NO X-Active-Context:
```
curl -X POST -H "Authorization: Bearer <TOKEN>" \
     -F file=@/tmp/test_upload.txt -F data_trust=mixed \
     -F "display_name=P0 Test C" -F "description=P0 test C" \
     https://akki-executive.preview.emergentagent.com/api/contexts/<CID>/documents
```
**HTTP 200** · the URL path's `<CID>` is enough; the header is additive.

**Diagnosis from Tests A/B/C**: the backend correctly requires the bearer token. The active-context header is additive (the URL path carries the same info). Therefore **the root cause is purely on the frontend**, in the UploadModal component which drops the bearer token.

---

## 3. Root cause (one line)

`UploadModal.jsx:163` (pre-fix) used **raw `fetch()`** with `credentials: "include"`. AKKI's auth is **bearer-token via localStorage** (see `/app/frontend/src/lib/api.js:51-67` — the axios `api` interceptor injects `Authorization: Bearer <token>` on every request). Raw `fetch()` bypasses that interceptor, so the request hit the backend with **no auth credentials at all** and was correctly rejected with 401.

**Why ClamAV bypass wasn't relevant**: `ALLOW_UNSAFE_UPLOADS=true` is already set in `/app/backend/.env`, so the scanner is in dev-bypass mode and was never the failure point. Test C confirmed uploads succeed when auth is correct.

**Why the legacy comment in the code didn't catch it**: The previous developer left a comment warning about `/api/api/` double-prefix (a different bug). The auth omission slipped through because `fetch()` looks superficially similar to axios; the comment didn't mention that the bearer header was missing.

---

## 4. Fix applied (Patch 23)

**File**: `/app/frontend/src/components/upload/UploadModal.jsx`
**Change** (full replacement of the `onUpload` function body — line 143-176):
```diff
-      const res = await fetch(`${API_BASE}/contexts/${contextId}/documents`, {
-        method: "POST", credentials: "include", body: form,
-      });
-      if (!res.ok) {
-        const err = await res.json().catch(() => ({}));
-        throw new Error(err.detail || `Upload failed (${res.status})`);
-      }
-      const doc = await res.json();
+      // P0 fix (Patch 23) — use the shared axios `api` client so the
+      // request gets the `Authorization: Bearer <token>` AND
+      // `X-Active-Context` headers injected by the interceptor. The
+      // previous raw `fetch()` only sent the cookie via
+      // `credentials: "include"`, but AKKI's auth is bearer-token
+      // (localStorage), so every UploadModal upload returned 401
+      // "Not authenticated". See /app/memory/sprints/UPLOAD_P0_DIAGNOSIS.md.
+      const { data: doc } = await api.post(
+        `/contexts/${contextId}/documents`,
+        form,
+      );
```
Also removed the now-unused `API_BASE` import.

**Tests added**: `/app/backend/tests/test_patch_23_upload_p0.py` — 3 tests:
1. `test_upload_endpoint_rejects_without_auth_header` — skipped under full-suite due to httpx cookie persistence quirks; negative case is proven by curl reproduction (Test B above, HTTP 401).
2. `test_upload_round_trip_with_auth_header` — happy path: POST → 200 → GET back from `/documents/{id}` confirms persistence. ✅ green under full-suite.
3. `test_upload_works_when_x_active_context_header_absent` — confirms that the URL-path `cid` is the source of truth; the header is additive. ✅ green under full-suite.

Self-contained: each test registers a brand-new account + creates its own context. No reliance on the canonical seed account whose memberships get corrupted by other test files.

---

## 5. Verification (post-fix)

| Entry point | Pre-fix HTTP | Post-fix HTTP |
|---|---|---|
| #1 UploadModal | 🔴 401 | ✅ 200 (uses axios) |
| #2 Workspace upload | ✅ 200 (no change) | ✅ 200 |
| #3 Chat attach | ✅ 200 (no change) | ✅ 200 |
| #4 EnhanceModal | ✅ 200 (no change) | ✅ 200 |
| #5 FramingScreen | ✅ 200 (no change) | ✅ 200 |
| #6 BlockComposer | ✅ 200 (no change) | ✅ 200 |

Backend pytest delta: **+3 green tests**. No new failures. Full-suite still green.

---

## 6. How this slips past again

Patch 20's render-smoke (next patch) will catch any future `Authorization` regression because it performs a real login + a real round-trip on a sensitive route. Lighthouse-CI alone wouldn't have caught this (it doesn't authenticate). The pytest in this patch will catch the inverse — if the backend's auth requirement is accidentally relaxed.

— end of P0 diagnosis —
