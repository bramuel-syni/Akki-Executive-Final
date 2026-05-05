/**
 * Solva v3 — Guided Flow state machine (Phase I.2).
 *
 * Pure reducer. No React, no DOM, no I/O. Deterministic. Testable from
 * a Node script or Jest. The brief (§8.1) specifies the state sequence:
 *
 *   LANDING → FRAMING → Q1 → Q2 → Q3 →
 *   DEPTH_Q1 → DEPTH_Q2 → DEPTH_Q3 →
 *   PREPARING → ARTEFACT → REFLECT_1 → REFLECT_2 → REFLECT_3 → COMPLETE
 *
 * Refusal interrupt: PREPARING → ARTEFACT_REFUSAL → REFLECT_1 → REFLECT_2 → REFLECT_3 → COMPLETE.
 *
 * The reducer takes a current state object and an action, and returns
 * the next state. It also keeps a record of every answer so going back
 * preserves prior answers (brief §4 + §8.1).
 *
 * Public surface:
 *
 *   STATES                        — frozen list of all state names
 *   nextState(current, action)    — pure reducer
 *   canGoBack(current)            — boolean: can we go to the previous state?
 *   goBack(current)               — return previous state (no answers cleared)
 *   resumePoint(session)          — given a server session row, return the
 *                                   state the user should land on
 *   isFlowState(state)            — true for any non-LANDING / non-COMPLETE state
 */

// Locked list — must not change order (the index is the progress).
export const STATES = Object.freeze([
  "LANDING",
  "FRAMING",
  "Q1",
  "Q2",
  "Q3",
  "DEPTH_Q1",
  "DEPTH_Q2",
  "DEPTH_Q3",
  "PREPARING",
  "ARTEFACT",
  "REFLECT_1",
  "REFLECT_2",
  "REFLECT_3",
  "COMPLETE",
]);

export const ARTEFACT_REFUSAL = "ARTEFACT_REFUSAL";

const FORWARD = {
  LANDING:    "FRAMING",
  FRAMING:    "Q1",
  Q1:         "Q2",
  Q2:         "Q3",
  Q3:         "DEPTH_Q1",
  DEPTH_Q1:   "DEPTH_Q2",
  DEPTH_Q2:   "DEPTH_Q3",
  DEPTH_Q3:   "PREPARING",
  PREPARING:  "ARTEFACT",
  ARTEFACT:   "REFLECT_1",
  REFLECT_1:  "REFLECT_2",
  REFLECT_2:  "REFLECT_3",
  REFLECT_3:  "COMPLETE",
  ARTEFACT_REFUSAL: "REFLECT_1",
};

const BACKWARD = (() => {
  const m = {};
  for (const [from, to] of Object.entries(FORWARD)) {
    if (!(to in m)) m[to] = from;
  }
  // Special: from ARTEFACT_REFUSAL the user cannot go back into the
  // engine; refusal is final. Same as ARTEFACT.
  m["FRAMING"] = "LANDING";
  return Object.freeze(m);
})();

// States that a user cannot navigate backwards out of (the synthesis
// has run, the artefact is composed). Going back from REFLECT_1 lands
// on ARTEFACT (or ARTEFACT_REFUSAL), not on DEPTH_Q3.
const NON_REWINDABLE = new Set([
  "PREPARING",
  "ARTEFACT",
  "ARTEFACT_REFUSAL",
  "COMPLETE",
]);

const QUESTION_STATES = new Set(["Q1", "Q2", "Q3", "DEPTH_Q1", "DEPTH_Q2", "DEPTH_Q3"]);
const REFLECTION_STATES = new Set(["REFLECT_1", "REFLECT_2", "REFLECT_3"]);

/** Build a fresh state container — used at /app/solva/session/new mount. */
export function initialState({ submodule = "seek_clarity", persona = null } = {}) {
  return {
    state: "LANDING",
    submodule,
    persona: persona || null,
    sessionId: null,
    framing: "",
    answers: {},        // Q1..DEPTH_Q3 → string
    reflections: {},    // REFLECT_1..REFLECT_3 → { text, skipped }
    history: ["LANDING"],   // chronological state log
    refusal: false,
    error: null,
  };
}

/** Are we currently on a question screen? */
export function isQuestionState(state) {
  return QUESTION_STATES.has(state);
}

/** Are we on a reflection screen? */
export function isReflectionState(state) {
  return REFLECTION_STATES.has(state);
}

/** Compute the human-readable progress on a question screen. */
export function questionProgress(state) {
  switch (state) {
    case "Q1": return { round: 1, n: 1, of: 3, depth: false };
    case "Q2": return { round: 1, n: 2, of: 3, depth: false };
    case "Q3": return { round: 1, n: 3, of: 3, depth: false };
    case "DEPTH_Q1": return { round: 2, n: 1, of: 3, depth: true };
    case "DEPTH_Q2": return { round: 2, n: 2, of: 3, depth: true };
    case "DEPTH_Q3": return { round: 2, n: 3, of: 3, depth: true };
    default: return null;
  }
}

/** True when the user can rewind to the previous state. */
export function canGoBack(current) {
  if (!current || current.state === "LANDING") return false;
  if (NON_REWINDABLE.has(current.state)) return false;
  if (current.state === "REFLECT_1") return false;   // back from reflection lands on artefact, handled separately
  return true;
}

/** Return the previous-state name if rewindable, else null. */
function previousStateName(state) {
  return BACKWARD[state] || null;
}

/** Pure reducer. */
export function nextState(current, action) {
  if (!current) return initialState();
  if (!action || !action.type) return current;

  const cur = current.state;
  switch (action.type) {
    /* ----- meta ----- */
    case "PICK_SUBMODULE": {
      // From LANDING, the picker chooses a sub-module and pushes us to FRAMING.
      // No answers cleared.
      return {
        ...current,
        state:    "FRAMING",
        submodule: action.submodule || current.submodule || "seek_clarity",
        persona:   action.persona || null,
        history:   [...current.history, "FRAMING"],
        error:     null,
      };
    }
    case "SET_PERSONA": {
      return { ...current, persona: action.persona || null };
    }
    case "ATTACH_SESSION_ID": {
      return { ...current, sessionId: action.sessionId };
    }
    case "SET_ERROR": {
      return { ...current, error: action.error || null };
    }

    /* ----- forward ----- */
    case "SUBMIT_FRAMING": {
      if (cur !== "FRAMING") return current;
      const framing = (action.framing || "").trim();
      if (framing.length < 20) {
        return { ...current, error: "Tell me a little more (at least 20 characters)." };
      }
      const next = FORWARD["FRAMING"];   // → Q1
      return {
        ...current,
        state:   next,
        framing,
        history: [...current.history, next],
        error:   null,
      };
    }
    case "ANSWER_QUESTION": {
      if (!QUESTION_STATES.has(cur)) return current;
      const answer = (action.answer || "").trim();
      // Allow empty answers (user can "skip" a question by submitting empty).
      const next = FORWARD[cur];
      return {
        ...current,
        state:   next,
        answers: { ...current.answers, [cur]: answer },
        history: [...current.history, next],
        error:   null,
      };
    }
    case "PREPARING_DONE": {
      // After PREPARING completes, the orchestrator either lands on
      // ARTEFACT (synthesis) or ARTEFACT_REFUSAL (refusal triggered).
      if (cur !== "PREPARING") return current;
      const refusal = !!action.refusal;
      const next = refusal ? "ARTEFACT_REFUSAL" : "ARTEFACT";
      return {
        ...current,
        state:   next,
        refusal,
        history: [...current.history, next],
        error:   null,
      };
    }
    case "ANSWER_REFLECTION": {
      if (!REFLECTION_STATES.has(cur)) return current;
      const skipped = !!action.skipped;
      const text = skipped ? "" : (action.answer || "").trim();
      const next = FORWARD[cur];
      return {
        ...current,
        state:   next,
        reflections: { ...current.reflections, [cur]: { text, skipped } },
        history: [...current.history, next],
        error:   null,
      };
    }

    /* ----- backwards ----- */
    case "GO_BACK": {
      if (!canGoBack(current)) return current;
      const prev = previousStateName(cur);
      if (!prev) return current;
      return {
        ...current,
        state:   prev,
        history: [...current.history, prev],
        error:   null,
      };
    }

    /* ----- resume ----- */
    case "RESUME": {
      // action.snapshot — pre-built state to drop in (used by SolvaSession on mount).
      if (!action.snapshot) return current;
      return {
        ...initialState({
          submodule: action.snapshot.submodule || current.submodule,
          persona: action.snapshot.persona || current.persona,
        }),
        ...action.snapshot,
        history: [...(action.snapshot.history || ["LANDING"])],
      };
    }

    default:
      return current;
  }
}

/**
 * Compute where to drop the user when they click "Resume" on a saved
 * server session. Maps the session's `layer` field + `synthesis` /
 * `reflection` presence to a state name.
 *
 * Mapping rules:
 *   - completed session with `reflection` complete → COMPLETE
 *   - completed session with synthesis but reflection incomplete → first
 *     unanswered REFLECT_n
 *   - active session, layer='framing' → FRAMING
 *   - active session, layer='grounding' → first unanswered Q1..Q3, or
 *     DEPTH_Q1..DEPTH_Q3 once layer_index >= 2
 *   - active session, layer='hypothesis' → DEPTH_Q1
 *   - active session, layer='synthesis' → PREPARING
 *   - active session, layer='reflection' → first unanswered REFLECT_n
 *   - blocked / refused session → ARTEFACT_REFUSAL
 *
 * The output is { state, submodule, persona, sessionId, framing,
 *   answers, reflections, refusal }.
 */
export function resumePoint(session) {
  if (!session) {
    return { ...initialState(), error: "No session." };
  }
  const status = (session.status || "active").toLowerCase();
  const submodule = session.submodule || "seek_clarity";
  const persona = session.persona || null;
  const sessionId = session.id || null;
  const framing = session.intent || "";

  // Build answers from solva user-turn list; question screens map by index.
  const userTurns = (session.turns || []).filter((t) => t && t.role === "user");
  const ANSWER_KEYS = ["Q1", "Q2", "Q3", "DEPTH_Q1", "DEPTH_Q2", "DEPTH_Q3"];
  const answers = {};
  ANSWER_KEYS.forEach((k, i) => {
    if (userTurns[i]?.text) answers[k] = userTurns[i].text;
  });

  const reflections = {};
  const reflResp = ((session.reflection || {}).responses) || [];
  ["REFLECT_1", "REFLECT_2", "REFLECT_3"].forEach((k, i) => {
    if (reflResp[i]) {
      reflections[k] = {
        text: reflResp[i].answer || reflResp[i].text || "",
        skipped: !!reflResp[i].skipped,
      };
    }
  });

  // Refusal — explicit status OR refusal entry in audit log.
  const refusal = ["refused", "blocked_hard", "blocked_soft"].includes(status);

  // State decision.
  // Brief §6.3: the artefact is the DESTINATION. Reflections are an
  // opt-in side-trip the user starts from the artefact, not a forced
  // gate. So a completed (or in-reflection) session always lands on
  // ARTEFACT, even when reflections are blank.
  let state = "FRAMING";
  if (status === "completed") {
    state = refusal ? "ARTEFACT_REFUSAL" : "ARTEFACT";
  } else if (refusal) {
    state = "ARTEFACT_REFUSAL";
  } else {
    const layer = (session.layer || "framing").toLowerCase();
    const ix = session.layer_index || 0;
    switch (layer) {
      case "framing":
        state = "FRAMING";
        break;
      case "grounding": {
        // first unanswered Q
        const filled = ANSWER_KEYS.filter((k) => answers[k]).length;
        if (filled < 3) state = ANSWER_KEYS[filled] || "Q1";
        else if (ix >= 2) state = ANSWER_KEYS[Math.min(filled, 5)] || "DEPTH_Q1";
        else state = "DEPTH_Q1";
        break;
      }
      case "hypothesis":
        state = "DEPTH_Q1";
        break;
      case "synthesis":
        state = "PREPARING";
        break;
      case "reflection":
        // synthesis is in the box already; show artefact, user opts in
        // to reflection from there.
        state = "ARTEFACT";
        break;
      default:
        state = "FRAMING";
    }
  }

  return {
    state,
    submodule,
    persona,
    sessionId,
    framing,
    answers,
    reflections,
    history: ["LANDING", state],
    refusal,
    error: null,
  };
}

/** Is the given state still part of the active flow (i.e. not the terminal)? */
export function isFlowState(state) {
  return state !== "LANDING" && state !== "COMPLETE";
}

/** Helper: convenience action creators for tests + screens. */
export const Actions = Object.freeze({
  pickSubmodule: (submodule, persona = null) =>
    ({ type: "PICK_SUBMODULE", submodule, persona }),
  setPersona: (persona) => ({ type: "SET_PERSONA", persona }),
  attachSession: (sessionId) => ({ type: "ATTACH_SESSION_ID", sessionId }),
  submitFraming: (framing) => ({ type: "SUBMIT_FRAMING", framing }),
  answerQuestion: (answer) => ({ type: "ANSWER_QUESTION", answer }),
  preparingDone: (refusal = false) => ({ type: "PREPARING_DONE", refusal }),
  answerReflection: (answer, skipped = false) =>
    ({ type: "ANSWER_REFLECTION", answer, skipped }),
  goBack: () => ({ type: "GO_BACK" }),
  resume: (snapshot) => ({ type: "RESUME", snapshot }),
  setError: (error) => ({ type: "SET_ERROR", error }),
});
