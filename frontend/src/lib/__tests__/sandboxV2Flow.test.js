/**
 * Unit tests for sandboxV2Flow.js — Phase J.1 reducer.
 *
 * Run:  cd frontend && yarn test --watchAll=false --testPathPattern=sandboxV2Flow
 */
import {
  STATES,
  initialState,
  nextState,
  canGoBack,
  isRevealState,
  stepIndexForState,
  resumePoint,
  Actions,
} from "../sandboxV2Flow";

const VALID_WELCOME = { name: "Sam", role: "ned", org_type: "bank", hope: "" };

describe("STATES list (locked order)", () => {
  test("contains the 10 brief-spec states in order", () => {
    expect(STATES).toEqual([
      "WELCOME",
      "STEP_1_SOLVA", "STEP_1_REVEAL",
      "STEP_2_PULSE", "STEP_2_REVEAL",
      "STEP_3_STUDIO", "STEP_3_REVEAL",
      "STEP_4_CYCLE", "STEP_4_REVEAL",
      "CLOSING",
    ]);
  });
  test("STATES is frozen", () => {
    expect(Object.isFrozen(STATES)).toBe(true);
  });
});

describe("initialState", () => {
  test("default fields", () => {
    const s = initialState();
    expect(s.state).toBe("WELCOME");
    expect(s.sessionId).toBeNull();
    expect(s.welcome).toEqual({ name: "", role: null, org_type: null, hope: "" });
    expect(s.solvaSessionId).toBeNull();
    expect(s.solvaRefusal).toBe(false);
    expect(s.studio).toEqual({ draft_built: false, added_sentence: null, refused_sentence: null });
    expect(s.cycle).toEqual({ viewed: false });
    expect(s.capturedEmail).toBeNull();
    expect(s.history).toEqual(["WELCOME"]);
    expect(s.error).toBeNull();
  });
});

describe("classifiers", () => {
  test("isRevealState only true for the 4 reveal states", () => {
    ["STEP_1_REVEAL", "STEP_2_REVEAL", "STEP_3_REVEAL", "STEP_4_REVEAL"].forEach((s) =>
      expect(isRevealState(s)).toBe(true));
    ["WELCOME", "STEP_1_SOLVA", "STEP_3_STUDIO", "CLOSING"].forEach((s) =>
      expect(isRevealState(s)).toBe(false));
  });
  test("stepIndexForState", () => {
    expect(stepIndexForState("WELCOME")).toBeNull();
    expect(stepIndexForState("CLOSING")).toBeNull();
    expect(stepIndexForState("STEP_1_SOLVA")).toBe(1);
    expect(stepIndexForState("STEP_3_STUDIO")).toBe(3);
    expect(stepIndexForState("STEP_4_REVEAL")).toBe(4);
  });
});

describe("Welcome submission", () => {
  test("rejects missing name", () => {
    const s = nextState({ ...initialState(), welcome: { name: "", role: "ned", org_type: "bank", hope: "" } }, Actions.submitWelcome());
    expect(s.state).toBe("WELCOME");
    expect(s.error).toMatch(/name/i);
  });
  test("rejects missing role", () => {
    const s = nextState({ ...initialState(), welcome: { name: "Sam", role: null, org_type: "bank", hope: "" } }, Actions.submitWelcome());
    expect(s.state).toBe("WELCOME");
    expect(s.error).toMatch(/role/i);
  });
  test("rejects missing org_type", () => {
    const s = nextState({ ...initialState(), welcome: { name: "Sam", role: "ned", org_type: null, hope: "" } }, Actions.submitWelcome());
    expect(s.state).toBe("WELCOME");
    expect(s.error).toMatch(/org/i);
  });
  test("hope is optional", () => {
    let s = { ...initialState(), welcome: { ...VALID_WELCOME } };
    s = nextState(s, Actions.submitWelcome());
    expect(s.state).toBe("STEP_1_SOLVA");
    expect(s.error).toBeNull();
  });
  test("SET_WELCOME_FIELD", () => {
    let s = initialState();
    s = nextState(s, Actions.setWelcomeField("name", "Sam"));
    expect(s.welcome.name).toBe("Sam");
    s = nextState(s, Actions.setWelcomeField("role", "ned"));
    expect(s.welcome.role).toBe("ned");
    // Unknown field rejected
    s = nextState(s, Actions.setWelcomeField("unknown", "x"));
    expect(s.welcome.unknown).toBeUndefined();
  });
});

describe("Forward sequence (Step 2 deferred)", () => {
  test("WELCOME → STEP_1_SOLVA → STEP_1_REVEAL → STEP_3_STUDIO (skip Step 2)", () => {
    let s = { ...initialState(), welcome: { ...VALID_WELCOME } };
    s = nextState(s, Actions.submitWelcome());
    expect(s.state).toBe("STEP_1_SOLVA");
    s = nextState(s, Actions.advance());
    expect(s.state).toBe("STEP_1_REVEAL");
    s = nextState(s, Actions.advance());
    expect(s.state).toBe("STEP_3_STUDIO");   // <-- DEFER
    s = nextState(s, Actions.advance());
    expect(s.state).toBe("STEP_3_REVEAL");
    s = nextState(s, Actions.advance());
    expect(s.state).toBe("STEP_4_CYCLE");
    s = nextState(s, Actions.advance());
    expect(s.state).toBe("STEP_4_REVEAL");
    s = nextState(s, Actions.advance());
    expect(s.state).toBe("CLOSING");
  });
  test("ADVANCE on terminal state is no-op", () => {
    const s = { ...initialState(), state: "CLOSING" };
    expect(nextState(s, Actions.advance()).state).toBe("CLOSING");
  });
});

describe("Backward navigation preserves answers", () => {
  test("GO_BACK from STEP_1_REVEAL → STEP_1_SOLVA preserves welcome answers", () => {
    let s = { ...initialState(), welcome: { ...VALID_WELCOME } };
    s = nextState(s, Actions.submitWelcome());
    s = nextState(s, Actions.advance());            // STEP_1_REVEAL
    expect(s.state).toBe("STEP_1_REVEAL");
    s = nextState(s, Actions.goBack());
    expect(s.state).toBe("STEP_1_SOLVA");
    expect(s.welcome).toEqual(VALID_WELCOME);       // preserved
  });
  test("GO_BACK from STEP_3_STUDIO → STEP_1_REVEAL (skipping deferred Step 2)", () => {
    let s = { ...initialState(), state: "STEP_3_STUDIO", welcome: { ...VALID_WELCOME } };
    s = nextState(s, Actions.goBack());
    expect(s.state).toBe("STEP_1_REVEAL");
  });
  test("GO_BACK from STEP_3_REVEAL preserves studio.draft_built", () => {
    let s = { ...initialState(), state: "STEP_3_STUDIO" };
    s = nextState(s, Actions.studioDraftBuilt());
    s = nextState(s, Actions.advance());
    expect(s.state).toBe("STEP_3_REVEAL");
    s = nextState(s, Actions.goBack());
    expect(s.state).toBe("STEP_3_STUDIO");
    expect(s.studio.draft_built).toBe(true);
  });
  test("canGoBack false from WELCOME and from any unmapped state", () => {
    expect(canGoBack({ state: "WELCOME" })).toBe(false);
    expect(canGoBack({ state: "STEP_1_SOLVA" })).toBe(true);
    expect(canGoBack({ state: "CLOSING" })).toBe(true);
    expect(canGoBack(null)).toBe(false);
  });
});

describe("Solva session attach + refusal", () => {
  test("ATTACH_SOLVA_SESSION + SET_SOLVA_REFUSAL", () => {
    let s = { ...initialState(), state: "STEP_1_SOLVA" };
    s = nextState(s, Actions.attachSolvaSession("solva-abc"));
    expect(s.solvaSessionId).toBe("solva-abc");
    s = nextState(s, Actions.setSolvaRefusal(true));
    expect(s.solvaRefusal).toBe(true);
    s = nextState(s, Actions.setSolvaRefusal(false));
    expect(s.solvaRefusal).toBe(false);
  });
});

describe("Studio actions + Cycle viewed + Email capture", () => {
  test("STUDIO_DRAFT_BUILT", () => {
    const s = nextState(initialState(), Actions.studioDraftBuilt());
    expect(s.studio.draft_built).toBe(true);
  });
  test("STUDIO_SENTENCE_ACCEPTED + REFUSED are mutually exclusive", () => {
    let s = initialState();
    s = nextState(s, Actions.studioSentenceAccepted("EBITDA fell to 12%."));
    expect(s.studio.added_sentence).toBe("EBITDA fell to 12%.");
    expect(s.studio.refused_sentence).toBeNull();
    s = nextState(s, Actions.studioSentenceRefused("growth will accelerate"));
    expect(s.studio.added_sentence).toBeNull();
    expect(s.studio.refused_sentence).toBe("growth will accelerate");
  });
  test("CYCLE_VIEWED + CAPTURE_EMAIL", () => {
    let s = initialState();
    s = nextState(s, Actions.cycleViewed());
    expect(s.cycle.viewed).toBe(true);
    s = nextState(s, Actions.captureEmail("a@b.co"));
    expect(s.capturedEmail).toBe("a@b.co");
  });
});

describe("Refusal interrupt path", () => {
  test("Solva refusal still progresses through reveal → step 3 → step 4 → closing", () => {
    let s = { ...initialState(), welcome: { ...VALID_WELCOME } };
    s = nextState(s, Actions.submitWelcome());
    s = nextState(s, Actions.attachSolvaSession("sid-1"));
    s = nextState(s, Actions.setSolvaRefusal(true));
    s = nextState(s, Actions.advance());          // refusal artefact reveal screen
    expect(s.state).toBe("STEP_1_REVEAL");
    s = nextState(s, Actions.advance());
    expect(s.state).toBe("STEP_3_STUDIO");
    s = nextState(s, Actions.advance());
    expect(s.state).toBe("STEP_3_REVEAL");
    s = nextState(s, Actions.advance());
    expect(s.state).toBe("STEP_4_CYCLE");
    s = nextState(s, Actions.advance());
    expect(s.state).toBe("STEP_4_REVEAL");
    s = nextState(s, Actions.advance());
    expect(s.state).toBe("CLOSING");
    expect(s.solvaRefusal).toBe(true);
  });
});

describe("Pause + resume", () => {
  test("RESUME loads server-side record into a snapshot", () => {
    const rec = {
      id: "sb-99", state: "STEP_3_STUDIO",
      name: "Mara", role: "ceo", org_type: "saas", hope: "Show me citations.",
      solva_session_id: "solva-xyz", solva_refusal: false,
      studio_state: { draft_built: true, added_sentence: null, refused_sentence: null },
      cycle_state: { viewed: false },
      captured_email: null, expires_at: "2026-05-12T00:00:00Z",
    };
    const snap = resumePoint(rec);
    const s = nextState(initialState(), Actions.resume(snap));
    expect(s.state).toBe("STEP_3_STUDIO");
    expect(s.sessionId).toBe("sb-99");
    expect(s.welcome.name).toBe("Mara");
    expect(s.welcome.role).toBe("ceo");
    expect(s.solvaSessionId).toBe("solva-xyz");
    expect(s.studio.draft_built).toBe(true);
  });
  test("RESUME with null returns initial-with-error", () => {
    const snap = resumePoint(null);
    expect(snap.error).toBe("No session.");
  });
  test("RESUME with unknown state falls back to WELCOME", () => {
    const snap = resumePoint({ id: "x", state: "BOGUS" });
    expect(snap.state).toBe("WELCOME");
  });
});

describe("Hardening", () => {
  test("Null + unknown actions are no-ops", () => {
    const s = initialState();
    expect(nextState(s, null)).toEqual(s);
    expect(nextState(s, {})).toEqual(s);
    expect(nextState(s, { type: "ZZZ" })).toEqual(s);
  });
  test("Null current returns initialState()", () => {
    expect(nextState(null, Actions.advance()).state).toBe("WELCOME");
  });
  test("ATTACH_SESSION stamps id without changing state", () => {
    let s = { ...initialState(), state: "STEP_1_SOLVA" };
    s = nextState(s, Actions.attachSession("sb-1", "2026-05-12T00:00:00Z"));
    expect(s.state).toBe("STEP_1_SOLVA");
    expect(s.sessionId).toBe("sb-1");
    expect(s.expiresAt).toBe("2026-05-12T00:00:00Z");
  });
  test("EXIT is a no-op state-wise (page handler does the API call)", () => {
    const s = { ...initialState(), state: "STEP_3_STUDIO" };
    expect(nextState(s, Actions.exit()).state).toBe("STEP_3_STUDIO");
  });
});
