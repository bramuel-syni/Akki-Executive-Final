import axios from "axios";

// Phase P5.6 (2026-02) — cross-origin guard.
//
// The build-time `REACT_APP_BACKEND_URL` is the canonical API base
// for preview environments. In production deploys the SPA is served
// from a custom domain (e.g. https://akki.syni.ai) but the bundle
// can carry a baked URL that points at a different host
// (https://akki-executive.emergent.host). When that mismatch occurs,
// every request is cross-origin: the CSRF cookie is set on the
// backend's host, and the SameSite=Lax attribute blocks the cookie
// from being sent on the subsequent cross-site POST → the SPA
// surfaces "CSRF token missing. Reload the page and retry." even
// though the backend, the deploy and the user are all healthy.
//
// Resolution: prefer same-origin `/api` when the configured backend
// origin doesn't match the page origin. Same-origin requests share
// the cookie jar, so the CSRF double-submit flow works regardless
// of which host the bundle was baked for. The ingress on both
// preview and production proxies `/api/*` to the FastAPI backend
// (system contract — see kubernetes ingress) so a relative base is
// portable everywhere.
const BUILD_BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

function _resolveApiBase() {
  // Server-rendered / non-browser context — use the build-time value.
  if (typeof window === "undefined") return `${BUILD_BACKEND_URL}/api`;
  if (!BUILD_BACKEND_URL) return "/api";
  try {
    const buildOrigin = new URL(BUILD_BACKEND_URL).origin;
    if (window.location.origin === buildOrigin) {
      // Origins match — the bundle was built for this domain. Use the
      // configured value (relevant for environments where the API base
      // includes a path prefix or non-default port).
      return `${BUILD_BACKEND_URL}/api`;
    }
    // Mismatch — fall back to same-origin so the cookie jar is shared.
    return "/api";
  } catch (_e) {
    // BUILD_BACKEND_URL was malformed; fall back to same-origin.
    return "/api";
  }
}

export const API_BASE = _resolveApiBase();

// Phase P5.6 (2026-02) — public helper. Many marketing / sandbox
// surfaces still build their own absolute URLs from
// `process.env.REACT_APP_BACKEND_URL`. They all need the same
// cross-origin guard. Importing this helper instead of the raw env
// var means callers automatically pick up the same-origin fallback
// when the page origin doesn't match the baked backend URL.
// (Migrations are incremental; not in P5.6 scope.)
export function resolveApiUrl(path) {
  const p = path || "";
  const tail = p.startsWith("/") ? p : `/${p}`;
  return `${API_BASE}${tail.replace(/^\/api/, "")}`;
}

// Phase P5.6 (2026-02) — exposed so non-/api absolute URLs (e.g. the
// SolvaArtefact export.html links) can swap to a same-origin path.
// Returns either the configured BACKEND_URL when origin matches the
// page, or empty string (resolve relative to page origin) otherwise.
export function resolveBackendOrigin() {
  if (typeof window === "undefined") return BUILD_BACKEND_URL;
  if (!BUILD_BACKEND_URL) return "";
  try {
    const buildOrigin = new URL(BUILD_BACKEND_URL).origin;
    return window.location.origin === buildOrigin ? BUILD_BACKEND_URL : "";
  } catch (_e) {
    return "";
  }
}

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
