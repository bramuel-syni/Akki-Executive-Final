/**
 * Sandbox v2 — Guided Flow state machine (Phase J.1).
 *
 * Pure reducer. No React, no DOM, no I/O. Deterministic. Testable from
 * Jest. The Sandbox UX Brief §3-§7 specifies the state sequence:
 *
 *   WELCOME
 *     → STEP_1_SOLVA → STEP_1_REVEAL
 *     → STEP_3_STUDIO → STEP_3_REVEAL          (Step 2 deferred to Phase D.2)
 *     → STEP_4_CYCLE → STEP_4_REVEAL
 *     → CLOSING
 *
 * STEP_2_PULSE / STEP_2_REVEAL are declared in STATES but not reachable
 * until Phase D.2 wires Pulse into the visit. STEP_1_REVEAL transitions
 * directly to STEP_3_STUDIO via the FORWARD map below — see the marker
 * comment on that line.
 *
 * Backwards navigation preserves answers, expansions, and draft state at
 * each step (brief §8.4). Exit at any state preserves the session for
 * 7 days via the persistence layer in routers/sandbox.py.
 */

export const STATES = Object.freeze([
  "WELCOME",
  "STEP_1_SOLVA", "STEP_1_REVEAL",
  "STEP_2_PULSE", "STEP_2_REVEAL",
  "STEP_3_STUDIO", "STEP_3_REVEAL",
  "STEP_4_CYCLE", "STEP_4_REVEAL",
  "CLOSING",
]);

const FORWARD = {
  WELCOME:        "STEP_1_SOLVA",
  STEP_1_SOLVA:   "STEP_1_REVEAL",
  // PHASE D.2 — when Pulse ships, change this to "STEP_2_PULSE".
  STEP_1_REVEAL:  "STEP_3_STUDIO",
  STEP_2_PULSE:   "STEP_2_REVEAL",
  STEP_2_REVEAL:  "STEP_3_STUDIO",
  STEP_3_STUDIO:  "STEP_3_REVEAL",
  STEP_3_REVEAL:  "STEP_4_CYCLE",
  STEP_4_CYCLE:   "STEP_4_REVEAL",
  STEP_4_REVEAL:  "CLOSING",
};

const BACKWARD = {
  STEP_1_SOLVA:   "WELCOME",
  STEP_1_REVEAL:  "STEP_1_SOLVA",
  STEP_2_PULSE:   "STEP_1_REVEAL",
  STEP_2_REVEAL:  "STEP_2_PULSE",
  // Step 2 is deferred — going back from STEP_3_STUDIO lands on STEP_1_REVEAL.
  STEP_3_STUDIO:  "STEP_1_REVEAL",
  STEP_3_REVEAL:  "STEP_3_STUDIO",
  STEP_4_CYCLE:   "STEP_3_REVEAL",
  STEP_4_REVEAL:  "STEP_4_CYCLE",
  CLOSING:        "STEP_4_REVEAL",
};

const VISIBLE_REVEAL_STATES = new Set([
  "STEP_1_REVEAL", "STEP_2_REVEAL", "STEP_3_REVEAL", "STEP_4_REVEAL",
]);

const STEP_INDEX_BY_STATE = {
  WELCOME:       null,
  STEP_1_SOLVA:  1, STEP_1_REVEAL: 1,
  STEP_2_PULSE:  2, STEP_2_REVEAL: 2,
  STEP_3_STUDIO: 3, STEP_3_REVEAL: 3,
  STEP_4_CYCLE:  4, STEP_4_REVEAL: 4,
  CLOSING:       null,
};

/** Build a fresh state container — used at /sandbox mount. */
export function initialState() {
  return {
    state: "WELCOME",
    sessionId: null,
    expiresAt: null,
    welcome: { name: "", role: null, org_type: null, hope: "" },
    solvaSessionId: null,         // attached after Step 1 starts
    solvaRefusal: false,          // true if Solva refused
    studio: {                     // populated through Step 3
      draft_built: false,
      added_sentence: null,
      refused_sentence: null,
    },
    cycle: {                      // populated when user views Step 4
      viewed: false,
    },
    capturedEmail: null,
    history: ["WELCOME"],
    error: null,
  };
}

/** Convenience getters used by the page to render UI. */
export function isRevealState(state) { return VISIBLE_REVEAL_STATES.has(state); }
export function stepIndexForState(state) { return STEP_INDEX_BY_STATE[state] ?? null; }

/** Are we allowed to go back from `current.state`? */
export function canGoBack(current) {
  if (!current) return false;
  if (current.state === "WELCOME") return false;
  return Boolean(BACKWARD[current.state]);
}

function _validateWelcome(welcome) {
  if (!welcome) return "Tell us your name to get started.";
  if (!welcome.name || !welcome.name.trim()) return "Tell us your name to get started.";
  if (!welcome.role) return "Pick the role that fits best.";
  if (!welcome.org_type) return "Pick the org type that fits best.";
  return null;
}

/** Pure reducer. */
export function nextState(current, action) {
  if (!current) return initialState();
  if (!action || !action.type) return current;
  const cur = current.state;

  switch (action.type) {
    /* ---- meta ---- */
    case "SET_WELCOME_FIELD": {
      const { field, value } = action;
      if (!["name", "role", "org_type", "hope"].includes(field)) return current;
      return {
        ...current,
        welcome: { ...current.welcome, [field]: value },
        error: null,
      };
    }
    case "ATTACH_SESSION": {
      return {
        ...current,
        sessionId: action.sessionId,
        expiresAt: action.expiresAt || null,
      };
    }
    case "ATTACH_SOLVA_SESSION": {
      return { ...current, solvaSessionId: action.solvaSessionId || null };
    }
    case "SET_SOLVA_REFUSAL": {
      return { ...current, solvaRefusal: !!action.refusal };
    }
    case "SET_ERROR": {
      return { ...current, error: action.error || null };
    }

    /* ---- forward ---- */
    case "SUBMIT_WELCOME": {
      if (cur !== "WELCOME") return current;
      const err = _validateWelcome(current.welcome);
      if (err) return { ...current, error: err };
      const next = FORWARD["WELCOME"];   // → STEP_1_SOLVA
      return {
        ...current,
        state: next,
        history: [...current.history, next],
        error: null,
      };
    }
    case "ADVANCE": {
      const next = FORWARD[cur];
      if (!next) return current;
      return {
        ...current,
        state: next,
        history: [...current.history, next],
        error: null,
      };
    }
    case "STUDIO_DRAFT_BUILT": {
      return {
        ...current,
        studio: { ...current.studio, draft_built: true },
      };
    }
    case "STUDIO_SENTENCE_ACCEPTED": {
      return {
        ...current,
        studio: {
          ...current.studio,
          added_sentence: action.sentence || "",
          refused_sentence: null,
        },
      };
    }
    case "STUDIO_SENTENCE_REFUSED": {
      return {
        ...current,
        studio: {
          ...current.studio,
          added_sentence: null,
          refused_sentence: action.sentence || "",
        },
      };
    }
    case "CYCLE_VIEWED": {
      return { ...current, cycle: { ...current.cycle, viewed: true } };
    }
    case "CAPTURE_EMAIL": {
      return { ...current, capturedEmail: action.email || null };
    }

    /* ---- backwards ---- */
    case "GO_BACK": {
      if (!canGoBack(current)) return current;
      const prev = BACKWARD[cur];
      if (!prev) return current;
      return {
        ...current,
        state: prev,
        history: [...current.history, prev],
        error: null,
      };
    }

    /* ---- exit / resume ---- */
    case "EXIT": {
      // Frontend-only marker. The page handler also POSTs to
      // /api/sandbox/v2/sessions/{sid}/exit but we don't need that to
      // be synchronous with the state transition.
      return { ...current, state: cur, error: null };
    }
    case "RESUME": {
      if (!action.snapshot) return current;
      return {
        ...initialState(),
        ...action.snapshot,
        history: [...(action.snapshot.history || ["WELCOME"])],
      };
    }

    default:
      return current;
  }
}

/**
 * Map a server-side sandbox v2 session record (the dict returned by
 * GET /api/sandbox/v2/sessions/{sid}) into a reducer snapshot. Used by
 * the page when the user reloads or comes back via a resume token.
 */
export function resumePoint(rec) {
  if (!rec) {
    return { ...initialState(), error: "No session." };
  }
  const state = STATES.includes(rec.state) ? rec.state : "WELCOME";
  return {
    state,
    sessionId: rec.id || null,
    expiresAt: rec.expires_at || null,
    welcome: {
      name: rec.name || "",
      role: rec.role || null,
      org_type: rec.org_type || null,
      hope: rec.hope || "",
    },
    solvaSessionId: rec.solva_session_id || null,
    solvaRefusal: !!(rec.solva_refusal),
    studio: rec.studio_state || { draft_built: false, added_sentence: null, refused_sentence: null },
    cycle: rec.cycle_state || { viewed: false },
    capturedEmail: rec.captured_email || null,
    history: ["WELCOME", state],
    error: null,
  };
}

/** Convenience action creators. */
export const Actions = Object.freeze({
  setWelcomeField: (field, value) => ({ type: "SET_WELCOME_FIELD", field, value }),
  submitWelcome:   () => ({ type: "SUBMIT_WELCOME" }),
  advance:         () => ({ type: "ADVANCE" }),
  attachSession:   (sessionId, expiresAt) => ({ type: "ATTACH_SESSION", sessionId, expiresAt }),
  attachSolvaSession: (id) => ({ type: "ATTACH_SOLVA_SESSION", solvaSessionId: id }),
  setSolvaRefusal: (refusal) => ({ type: "SET_SOLVA_REFUSAL", refusal }),
  studioDraftBuilt: () => ({ type: "STUDIO_DRAFT_BUILT" }),
  studioSentenceAccepted: (sentence) => ({ type: "STUDIO_SENTENCE_ACCEPTED", sentence }),
  studioSentenceRefused:  (sentence) => ({ type: "STUDIO_SENTENCE_REFUSED", sentence }),
  cycleViewed:     () => ({ type: "CYCLE_VIEWED" }),
  captureEmail:    (email) => ({ type: "CAPTURE_EMAIL", email }),
  goBack:          () => ({ type: "GO_BACK" }),
  exit:            () => ({ type: "EXIT" }),
  resume:          (snapshot) => ({ type: "RESUME", snapshot }),
  setError:        (error) => ({ type: "SET_ERROR", error }),
});

/* --------------------------------------------------------------------------
 * Persistence helpers (localStorage key + welcome answers)
 * Brief §9.2 — a returning user 8+ days later shouldn't have to re-type
 * their name and role.
 * -------------------------------------------------------------------------- */
export const RESUME_TOKEN_KEY = "akki_sandbox_v2_resume_token";
export const WELCOME_KEY = "akki_sandbox_v2_welcome";

export function readResumeToken() {
  if (typeof window === "undefined") return null;
  try { return window.localStorage.getItem(RESUME_TOKEN_KEY) || null; }
  catch (_e) { return null; }
}

export function writeResumeToken(sid) {
  if (typeof window === "undefined") return;
  try {
    if (sid) window.localStorage.setItem(RESUME_TOKEN_KEY, sid);
    else window.localStorage.removeItem(RESUME_TOKEN_KEY);
  } catch (_e) { /* ignore */ }
}

export function readWelcomeCache() {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(WELCOME_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_e) { return null; }
}

export function writeWelcomeCache(welcome) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(WELCOME_KEY, JSON.stringify(welcome || {}));
  } catch (_e) { /* ignore */ }
}
