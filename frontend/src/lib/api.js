import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

// Attach Bearer token when present — used by the pre-auth Sandbox flow, where
// the server mints a JWT we store locally rather than a cross-site cookie.
// The regular signed-in session continues to rely on the httponly cookie;
// the header is additive and doesn't disturb cookie auth.
api.interceptors.request.use((config) => {
  try {
    const t = typeof window !== "undefined"
      ? window.localStorage.getItem("akki_access_token")
      : null;
    if (t) {
      config.headers = config.headers || {};
      config.headers["Authorization"] = `Bearer ${t}`;
    }
  } catch { /* noop */ }
  return config;
});

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
