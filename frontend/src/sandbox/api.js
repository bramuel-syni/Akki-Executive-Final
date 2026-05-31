import { resolveBackendOrigin, ensureCsrfToken } from "@/lib/api";
/* Phase J — Sandbox API wrapper. Hits /api/sandbox-gen/*.
 *
 * Phase P5.11.4 (2026-02) — raw fetch() must carry `X-CSRF-Token`
 * on every state-changing POST/DELETE because the axios interceptor
 * in lib/api.js (which auto-injects it) does NOT run on plain
 * fetch. Without this, CSRFMiddleware rejects POST /sessions and
 * DELETE /sessions/{sid} with 403 csrf_token_missing — the live
 * preview returned 403 on both endpoints before this patch. The
 * sandbox-gen route is intentionally NOT on the CSRF allowlist
 * (it's a state-changing public endpoint, exactly what CSRF
 * defends), so the fix is on the client side.
 *
 * `ensureCsrfToken()` lazily mints / reads the CSRF cookie + token
 * via `GET /api/csrf` on first call; subsequent calls reuse the
 * in-memory cache.
 */
const API_BASE = (
  resolveBackendOrigin()
).replace(/\/$/, "");

async function _csrfHeaders() {
  const csrf = await ensureCsrfToken();
  const h = { "Content-Type": "application/json" };
  if (csrf) h["X-CSRF-Token"] = csrf;
  return h;
}

export async function createSandboxSession(form) {
  const headers = await _csrfHeaders();
  const res = await fetch(`${API_BASE}/api/sandbox-gen/sessions`, {
    method: "POST",
    headers,
    body: JSON.stringify(form),
  });
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail || ""; } catch (e) { /* noop */ }
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getSandboxSession(sid) {
  const res = await fetch(`${API_BASE}/api/sandbox-gen/sessions/${sid}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function deleteSandboxSession(sid) {
  const csrf = await ensureCsrfToken();
  const headers = {};
  if (csrf) headers["X-CSRF-Token"] = csrf;
  const res = await fetch(`${API_BASE}/api/sandbox-gen/sessions/${sid}`, {
    method: "DELETE",
    headers,
  });
  return res.ok;
}
