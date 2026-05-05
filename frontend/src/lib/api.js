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
  return String(detail);
}
