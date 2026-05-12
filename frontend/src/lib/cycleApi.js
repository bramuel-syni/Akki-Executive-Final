/**
 * Cycle Manager v2 API helpers.
 *
 * Thin typed wrappers over the v2 endpoints + the singleton
 * `/cycle/*` endpoints with the `?cycle_id=` query param threaded
 * through.
 */
import { api } from "@/lib/api";


// ── New v2 — cycles master ───────────────────────────────────────────
export async function createCycle(cid, { title }) {
  const { data } = await api.post(`/contexts/${cid}/cycles`, { title });
  return data;
}

export async function listCycles(cid, { q = "", sort = "recent", page = 1, page_size = 12 } = {}) {
  const params = new URLSearchParams({ sort, page: String(page), page_size: String(page_size) });
  if (q) params.set("q", q);
  const { data } = await api.get(`/contexts/${cid}/cycles?${params.toString()}`);
  return data;
}

export async function getCycle(cid, cycleId) {
  const { data } = await api.get(`/contexts/${cid}/cycles/${cycleId}`);
  return data;
}

export async function activateCycle(cid, cycleId, opts = {}) {
  // Patch 10 — `expected_close_at` is optional. Bare ISO date string
  // (YYYY-MM-DD) or full ISO timestamp accepted. Backend defaults to
  // now+30d when omitted.
  const body = {};
  if (opts && opts.expected_close_at) body.expected_close_at = opts.expected_close_at;
  const { data } = await api.post(`/contexts/${cid}/cycles/${cycleId}/activate`, body);
  return data;
}

export async function closeCycle(cid, cycleId) {
  const { data } = await api.post(`/contexts/${cid}/cycles/${cycleId}/close`);
  return data;
}


// ── Team catalogue ──────────────────────────────────────────────────
export async function listCatalogue(cid) {
  const { data } = await api.get(`/contexts/${cid}/team-catalogue`);
  return data;
}

export async function addCatalogueMember(cid, { name, email }) {
  const { data } = await api.post(`/contexts/${cid}/team-catalogue`, { name, email });
  return data;
}

export async function patchCatalogueMember(cid, memberId, patch) {
  const { data } = await api.patch(`/contexts/${cid}/team-catalogue/${memberId}`, patch);
  return data;
}

export async function softDeleteCatalogueMember(cid, memberId) {
  const { data } = await api.delete(`/contexts/${cid}/team-catalogue/${memberId}`);
  return data;
}


// ── Eligible contributors ────────────────────────────────────────────
export async function listEligibleContributors(cid, cycleId, agendaItemId) {
  const { data } = await api.get(
    `/contexts/${cid}/cycles/${cycleId}/agenda-items/${agendaItemId}/eligible-contributors`,
  );
  return data;
}


// ── Duplicate check ──────────────────────────────────────────────────
export async function checkTeamDuplicate(cid, cycleId, agendaItemId, { name, email }) {
  const { data } = await api.post(
    `/contexts/${cid}/cycles/${cycleId}/agenda-items/${agendaItemId}/check-team-duplicate`,
    { name, email },
  );
  return data;
}
