/* Phase J — Sandbox API wrapper. Hits /api/sandbox-gen/*. */
const API_BASE = (
  (typeof process !== "undefined" && process.env && process.env.REACT_APP_BACKEND_URL) ||
  ""
).replace(/\/$/, "");

export async function createSandboxSession(form) {
  const res = await fetch(`${API_BASE}/api/sandbox-gen/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
  const res = await fetch(`${API_BASE}/api/sandbox-gen/sessions/${sid}`, { method: "DELETE" });
  return res.ok;
}
