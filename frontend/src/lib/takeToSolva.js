/**
 * takeToSolva.js — Phase F.2.A unified "Take to Solva" journey.
 *
 * Every "Take to Solva" CTA in the codebase MUST converge on this
 * helper. It does one thing: navigates to /app/solva/session/new
 * with seed_kind + seed_id (and optional submodule) on the URL.
 *
 * The Solva session-new page (pages/SolvaSession.jsx) reads those
 * params on mount, hits GET /api/solva/v2/seed?kind=...&id=..., and
 * pre-fills the framing textarea with the seed text. The user then
 * adds their framing context and clicks Begin.
 *
 * Supported kinds (server-side, see backend/routers/solva_v2.py:fetch_take_to_solva_seed):
 *   • signal · document · cycle_contribution · cycle_compilation
 *   • solva_artefact · chat_message · ned_meeting
 *
 * Submodule param is optional. When omitted, the Solva landing
 * defaults to seek_clarity. Pass the user's intent only when the
 * source already implies it (e.g. develop_strategy from a fork).
 *
 * Hard rule: NEVER use `?doc_id=...` deep-link directly from a
 * caller. ALWAYS go through this helper.
 */

/**
 * @param {object} args
 * @param {(path: string) => void} args.navigate          react-router navigate fn
 * @param {string} args.kind                              one of the supported kinds
 * @param {string} args.id                                the source artefact id
 * @param {("seek_clarity"|"develop_strategy"|"simulate_hypothesis"|"get_perspective")} [args.submodule]
 * @param {string} [args.persona]                         optional persona for get_perspective
 */
export function takeToSolva({ navigate, kind, id, submodule, persona } = {}) {
  if (typeof navigate !== "function") {
    throw new Error("takeToSolva: navigate function is required");
  }
  if (!kind || !id) {
    throw new Error(`takeToSolva: kind and id are required (got kind=${kind}, id=${id})`);
  }
  const params = new URLSearchParams({ seed_kind: String(kind), seed_id: String(id) });
  if (submodule) params.set("submodule", String(submodule));
  if (persona) params.set("persona", String(persona));
  navigate(`/app/solva/session/new?${params.toString()}`);
}

/**
 * Synchronous URL builder — useful for `<Link to={...}>` callsites
 * where there's no navigate function in scope. Prefer takeToSolva()
 * when you have access to navigate.
 */
export function takeToSolvaPath({ kind, id, submodule, persona } = {}) {
  if (!kind || !id) return "/app/solva/session/new";
  const params = new URLSearchParams({ seed_kind: String(kind), seed_id: String(id) });
  if (submodule) params.set("submodule", String(submodule));
  if (persona) params.set("persona", String(persona));
  return `/app/solva/session/new?${params.toString()}`;
}

export default takeToSolva;
