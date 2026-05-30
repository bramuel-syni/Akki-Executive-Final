import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

// Phase A — per-tab active context. Held in sessionStorage (NOT
// localStorage) so two tabs in different contexts don't trample each
// other (Memo Item 5 / D-004). The SPA reads/writes through these
// helpers; the request interceptor below attaches the value as the
// `X-Active-Context` header on every authenticated call.
export const ACTIVE_CONTEXT_STORAGE_KEY = "akki_active_context_id";

export function readActiveContextId() {
  try {
    if (typeof window === "undefined") return null;
    return window.sessionStorage.getItem(ACTIVE_CONTEXT_STORAGE_KEY) || null;
  } catch { return null; }
}

export function writeActiveContextId(contextId) {
  try {
    if (typeof window === "undefined") return;
    if (contextId) {
      window.sessionStorage.setItem(ACTIVE_CONTEXT_STORAGE_KEY, contextId);
    } else {
      window.sessionStorage.removeItem(ACTIVE_CONTEXT_STORAGE_KEY);
    }
    // Notify in-app listeners (the role badge, the switcher, the
    // boot guard) so they can re-fetch without polling.
    window.dispatchEvent(new CustomEvent("akki:active-context-changed", {
      detail: { contextId },
    }));
  } catch { /* noop */ }
}

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

// ─── Phase P3.1 (2026-02) — CSRF double-submit-cookie wrapper ──────
// In-memory cache of the most recently minted CSRF token. The backend
// `/api/csrf` endpoint sets the cookie (non-HttpOnly so JS can read
// it) AND returns the token in the JSON body. We hold the latest
// value in memory so we don't re-read the cookie on every request.
let _csrfToken = null;
let _csrfFetchPromise = null;

function _readCsrfCookie() {
  if (typeof document === "undefined") return null;
  for (const part of (document.cookie || "").split(";")) {
    const [k, ...rest] = part.trim().split("=");
    if (k === "csrf_token") return rest.join("=") || null;
  }
  return null;
}

export async function ensureCsrfToken() {
  if (_csrfToken) return _csrfToken;
  const fromCookie = _readCsrfCookie();
  if (fromCookie) { _csrfToken = fromCookie; return fromCookie; }
  if (_csrfFetchPromise) return _csrfFetchPromise;
  _csrfFetchPromise = (async () => {
    try {
      const r = await axios.get(`${API_BASE}/csrf`, { withCredentials: true });
      const t = r?.data?.csrf_token;
      if (t) _csrfToken = t;
      return _csrfToken;
    } catch (_e) {
      return null;
    } finally {
      _csrfFetchPromise = null;
    }
  })();
  return _csrfFetchPromise;
}

const NON_IDEMPOTENT = new Set(["post", "put", "patch", "delete"]);
api.interceptors.request.use(async (config) => {
  const method = (config.method || "get").toLowerCase();
  if (NON_IDEMPOTENT.has(method)) {
    let t = _csrfToken || _readCsrfCookie();
    if (!t) t = await ensureCsrfToken();
    if (t) {
      config.headers = config.headers || {};
      config.headers["X-CSRF-Token"] = t;
    }
  }
  return config;
});

// On any 403 with code csrf_token_*, refresh the token + retry once.
api.interceptors.response.use(
  (resp) => resp,
  async (err) => {
    try {
      const code = err?.response?.data?.detail?.code;
      if (
        err?.response?.status === 403 &&
        (code === "csrf_token_missing" || code === "csrf_token_invalid") &&
        !err.config?._csrfRetried
      ) {
        _csrfToken = null;
        await ensureCsrfToken();
        const cfg = { ...err.config, _csrfRetried: true };
        cfg.headers = cfg.headers || {};
        cfg.headers["X-CSRF-Token"] = _csrfToken || _readCsrfCookie() || "";
        return api.request(cfg);
      }
    } catch (_e) { /* fall through */ }
    return Promise.reject(err);
  }
);

// Attach Bearer token + active-context header on every call.
// * Bearer (legacy) — used by the pre-auth Sandbox flow where the
//   server mints a JWT we store in localStorage rather than a
//   cross-site cookie. The regular signed-in session relies on the
//   httponly cookie; the header is additive and doesn't disturb
//   cookie auth.
// * X-Active-Context (Phase A) — per-tab membership selector. Read
//   from sessionStorage so each browser tab can be in its own
//   context; the server resolves the role fresh on every request
//   from this header (D-004 / D-005).
api.interceptors.request.use((config) => {
  try {
    const t = typeof window !== "undefined"
      ? window.localStorage.getItem("akki_access_token")
      : null;
    if (t) {
      config.headers = config.headers || {};
      config.headers["Authorization"] = `Bearer ${t}`;
    }
    const activeCtx = readActiveContextId();
    if (activeCtx) {
      config.headers = config.headers || {};
      config.headers["X-Active-Context"] = activeCtx;
    }
  } catch { /* noop */ }
  return config;
});

// Phase A — surface RBAC errors to a global event bus so the SPA
// can react with a forced re-pick (MEMBERSHIP_REVOKED) or a missing-
// header redirect (ACTIVE_CONTEXT_REQUIRED). We deliberately do NOT
// auto-redirect from the interceptor — that would race with whatever
// the calling component is doing. We just emit; the boot guard /
// AppShell listens.
//
// Phase P3.4 (2026-02) — session-timeout signalling. The backend
// surfaces `session_idle_timeout` (re-auth required) and
// `session_absolute_timeout` (full sign-out required) as 401
// responses. Emit `akki:session-event` so AppShell can render the
// re-auth modal or the expired-session surface respectively.
api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    try {
      const code = err?.response?.data?.detail?.code;
      if (code === "MEMBERSHIP_REVOKED" || code === "ACTIVE_CONTEXT_REQUIRED") {
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("akki:rbac-error", {
            detail: { code, message: err?.response?.data?.detail?.message },
          }));
        }
      }
      if (code === "session_idle_timeout" || code === "session_absolute_timeout") {
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("akki:session-event", {
            detail: { code, message: err?.response?.data?.detail?.message },
          }));
        }
      }
    } catch { /* noop */ }
    return Promise.reject(err);
  }
);

export function apiErrorMessage(err, fallback = "Something went wrong. Please try again.") {
  const detail = err?.response?.data?.detail;
  if (detail == null) return err?.message || fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  }
  if (detail && typeof detail.msg === "string") return detail.msg;
  // Chunk 6 (2026-05-13) — many backend HTTPException(detail={...})
  // payloads use a {code, message} shape (e.g. chat_empty,
  // synthesis_not_ready). Read `message` so the toast description
  // surfaces the human-readable explanation instead of "[object
  // Object]".
  if (detail && typeof detail.message === "string") return detail.message;
  return String(detail);
}

// Chunk 6 (2026-05-13) — error-code helper. Reads `detail.code` from
// the same nested-dict payloads. Lets callers branch on known states
// (e.g. show a different toast for chat_empty vs unknown failures)
// without parsing the raw response.
export function apiErrorCode(err) {
  const detail = err?.response?.data?.detail;
  if (detail && typeof detail === "object" && typeof detail.code === "string") {
    return detail.code;
  }
  return null;
}
