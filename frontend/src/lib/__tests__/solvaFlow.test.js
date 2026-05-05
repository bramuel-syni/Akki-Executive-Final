/**
 * Unit tests for solvaFlow.js — Phase I.2 reducer.
 *
 * Run with:  cd frontend && yarn test -- --watchAll=false --testPathPattern=solvaFlow
 */
import {
  STATES,
  ARTEFACT_REFUSAL,
  initialState,
  nextState,
  canGoBack,
  isFlowState,
  isQuestionState,
  isReflectionState,
  questionProgress,
  resumePoint,
  Actions,
} from "../solvaFlow";

describe("STATES list (locked order)", () => {
  test("contains exactly the 14 states from the brief, in order", () => {
    expect(STATES).toEqual([
      "LANDING",
      "FRAMING",
      "Q1", "Q2", "Q3",
      "DEPTH_Q1", "DEPTH_Q2", "DEPTH_Q3",
      "PREPARING",
      "ARTEFACT",
      "REFLECT_1", "REFLECT_2", "REFLECT_3",
      "COMPLETE",
    ]);
  });
  test("STATES is frozen", () => {
    expect(Object.isFrozen(STATES)).toBe(true);
  });
  test("ARTEFACT_REFUSAL is named consistently", () => {
    expect(ARTEFACT_REFUSAL).toBe("ARTEFACT_REFUSAL");
  });
});

describe("initialState", () => {
  test("default fields", () => {
    const s = initialState();
    expect(s.state).toBe("LANDING");
    expect(s.submodule).toBe("seek_clarity");
    expect(s.persona).toBeNull();
    expect(s.sessionId).toBeNull();
    expect(s.framing).toBe("");
    expect(s.answers).toEqual({});
    expect(s.reflections).toEqual({});
    expect(s.history).toEqual(["LANDING"]);
    expect(s.refusal).toBe(false);
    expect(s.error).toBeNull();
  });
  test("custom submodule + persona", () => {
    const s = initialState({ submodule: "get_perspective", persona: "Chair" });
    expect(s.submodule).toBe("get_perspective");
    expect(s.persona).toBe("Chair");
  });
});

describe("classifiers", () => {
  test("isQuestionState", () => {
    ["Q1","Q2","Q3","DEPTH_Q1","DEPTH_Q2","DEPTH_Q3"].forEach((s) =>
      expect(isQuestionState(s)).toBe(true));
    ["FRAMING","PREPARING","ARTEFACT","REFLECT_1"].forEach((s) =>
      expect(isQuestionState(s)).toBe(false));
  });
  test("isReflectionState", () => {
    ["REFLECT_1","REFLECT_2","REFLECT_3"].forEach((s) =>
      expect(isReflectionState(s)).toBe(true));
    ["FRAMING","Q1","ARTEFACT"].forEach((s) =>
      expect(isReflectionState(s)).toBe(false));
  });
  test("questionProgress on Q1 / DEPTH_Q1", () => {
    expect(questionProgress("Q1")).toEqual({ round:1, n:1, of:3, depth:false });
    expect(questionProgress("DEPTH_Q1")).toEqual({ round:2, n:1, of:3, depth:true });
    expect(questionProgress("FRAMING")).toBeNull();
  });
  test("isFlowState", () => {
    expect(isFlowState("LANDING")).toBe(false);
    expect(isFlowState("COMPLETE")).toBe(false);
    expect(isFlowState("FRAMING")).toBe(true);
    expect(isFlowState("ARTEFACT")).toBe(true);
  });
});

describe("nextState — happy path forward sequence", () => {
  test("LANDING → FRAMING via PICK_SUBMODULE", () => {
    let s = initialState();
    s = nextState(s, Actions.pickSubmodule("develop_strategy"));
    expect(s.state).toBe("FRAMING");
    expect(s.submodule).toBe("develop_strategy");
    expect(s.history).toEqual(["LANDING","FRAMING"]);
  });
  test("PICK_SUBMODULE preserves persona for get_perspective", () => {
    let s = initialState();
    s = nextState(s, Actions.pickSubmodule("get_perspective", "Chair"));
    expect(s.submodule).toBe("get_perspective");
    expect(s.persona).toBe("Chair");
  });
  test("FRAMING → Q1 with valid framing", () => {
    let s = initialState();
    s = nextState(s, Actions.pickSubmodule("seek_clarity"));
    s = nextState(s, Actions.submitFraming("This is a long enough framing string."));
    expect(s.state).toBe("Q1");
    expect(s.framing).toBe("This is a long enough framing string.");
  });
  test("FRAMING rejects too-short framing with error, no transition", () => {
    let s = initialState();
    s = nextState(s, Actions.pickSubmodule("seek_clarity"));
    s = nextState(s, Actions.submitFraming("too short"));
    expect(s.state).toBe("FRAMING");
    expect(s.error).toMatch(/at least 20/);
  });
  test("Q1 → Q2 → Q3 → DEPTH_Q1 → DEPTH_Q2 → DEPTH_Q3 → PREPARING", () => {
    let s = initialState();
    s = nextState(s, Actions.pickSubmodule("seek_clarity"));
    s = nextState(s, Actions.submitFraming("This is a long enough framing string."));
    const expected = ["Q2","Q3","DEPTH_Q1","DEPTH_Q2","DEPTH_Q3","PREPARING"];
    const answers = ["a1","a2","a3","d1","d2","d3"];
    answers.forEach((a, i) => {
      s = nextState(s, Actions.answerQuestion(a));
      expect(s.state).toBe(expected[i]);
    });
    expect(s.answers).toEqual({
      Q1:"a1", Q2:"a2", Q3:"a3", DEPTH_Q1:"d1", DEPTH_Q2:"d2", DEPTH_Q3:"d3",
    });
  });
  test("PREPARING_DONE without refusal → ARTEFACT", () => {
    let s = { ...initialState(), state: "PREPARING" };
    s = nextState(s, Actions.preparingDone(false));
    expect(s.state).toBe("ARTEFACT");
    expect(s.refusal).toBe(false);
  });
  test("PREPARING_DONE with refusal → ARTEFACT_REFUSAL", () => {
    let s = { ...initialState(), state: "PREPARING" };
    s = nextState(s, Actions.preparingDone(true));
    expect(s.state).toBe("ARTEFACT_REFUSAL");
    expect(s.refusal).toBe(true);
  });
  test("ARTEFACT → REFLECT_1 → REFLECT_2 → REFLECT_3 → COMPLETE", () => {
    let s = { ...initialState(), state: "ARTEFACT" };
    // ARTEFACT advances on ANSWER_REFLECTION? No — the screen flow in the
    // page jumps state from ARTEFACT to REFLECT_1 via a UI button. We
    // simulate that by transitioning manually for the test (the reducer
    // does not expose an "advance from artefact" action — page-level).
    s = { ...s, state: "REFLECT_1" };
    s = nextState(s, Actions.answerReflection("yes, surprised by Scenario B"));
    expect(s.state).toBe("REFLECT_2");
    s = nextState(s, Actions.answerReflection("", true));
    expect(s.state).toBe("REFLECT_3");
    expect(s.reflections.REFLECT_2).toEqual({ text: "", skipped: true });
    s = nextState(s, Actions.answerReflection("the explanation would be that we ignored the cash flow."));
    expect(s.state).toBe("COMPLETE");
  });
  test("ARTEFACT_REFUSAL → REFLECT_1 (refusal flow still asks for reflection)", () => {
    let s = { ...initialState(), state: "ARTEFACT_REFUSAL", refusal: true };
    // page-level advance
    s = { ...s, state: "REFLECT_1" };
    s = nextState(s, Actions.answerReflection("learned the cash forecast was thinner than I thought"));
    expect(s.state).toBe("REFLECT_2");
  });
});

describe("nextState — go back semantics", () => {
  test("canGoBack false from LANDING / PREPARING / ARTEFACT / COMPLETE", () => {
    expect(canGoBack({ state: "LANDING" })).toBe(false);
    expect(canGoBack({ state: "PREPARING" })).toBe(false);
    expect(canGoBack({ state: "ARTEFACT" })).toBe(false);
    expect(canGoBack({ state: "ARTEFACT_REFUSAL" })).toBe(false);
    expect(canGoBack({ state: "COMPLETE" })).toBe(false);
    expect(canGoBack({ state: "REFLECT_1" })).toBe(false);
  });
  test("canGoBack true mid-flow", () => {
    ["FRAMING", "Q1", "Q2", "Q3", "DEPTH_Q1", "DEPTH_Q2", "DEPTH_Q3"].forEach((st) =>
      expect(canGoBack({ state: st })).toBe(true));
  });
  test("GO_BACK preserves prior answers", () => {
    let s = initialState();
    s = nextState(s, Actions.pickSubmodule("seek_clarity"));
    s = nextState(s, Actions.submitFraming("This is a long enough framing string."));
    s = nextState(s, Actions.answerQuestion("first answer"));
    expect(s.state).toBe("Q2");
    s = nextState(s, Actions.goBack());
    expect(s.state).toBe("Q1");
    expect(s.answers.Q1).toBe("first answer");   // preserved
  });
  test("GO_BACK noop on non-rewindable state", () => {
    const s = { ...initialState(), state: "PREPARING" };
    const out = nextState(s, Actions.goBack());
    expect(out.state).toBe("PREPARING");
  });
});

describe("nextState — hardening", () => {
  test("noop with null/empty action", () => {
    const s = initialState();
    expect(nextState(s, null)).toEqual(s);
    expect(nextState(s, {})).toEqual(s);
    expect(nextState(s, { type: "UNKNOWN" })).toEqual(s);
  });
  test("ANSWER_QUESTION ignored outside Q states", () => {
    const s = { ...initialState(), state: "FRAMING" };
    const out = nextState(s, Actions.answerQuestion("x"));
    expect(out.state).toBe("FRAMING");
  });
  test("SUBMIT_FRAMING ignored outside FRAMING", () => {
    const s = { ...initialState(), state: "Q1" };
    const out = nextState(s, Actions.submitFraming("This is more than twenty chars."));
    expect(out.state).toBe("Q1");
  });
  test("ATTACH_SESSION_ID stamps the id without changing state", () => {
    let s = { ...initialState(), state: "Q1" };
    s = nextState(s, Actions.attachSession("abc-123"));
    expect(s.state).toBe("Q1");
    expect(s.sessionId).toBe("abc-123");
  });
  test("SET_PERSONA updates persona without changing state", () => {
    let s = { ...initialState(), state: "FRAMING", submodule: "get_perspective" };
    s = nextState(s, Actions.setPersona("CFO"));
    expect(s.persona).toBe("CFO");
  });
  test("SET_ERROR populates error", () => {
    const s = nextState(initialState(), Actions.setError("Nope."));
    expect(s.error).toBe("Nope.");
  });
});

describe("resumePoint", () => {
  test("null session returns initial-with-error", () => {
    const s = resumePoint(null);
    expect(s.state).toBe("LANDING");
    expect(s.error).toBe("No session.");
  });
  test("active framing → FRAMING", () => {
    const s = resumePoint({
      id: "s1", status: "active", layer: "framing", submodule: "seek_clarity",
      intent: "Solva session", turns: [],
    });
    expect(s.state).toBe("FRAMING");
    expect(s.sessionId).toBe("s1");
  });
  test("active grounding with two answers → Q3", () => {
    const s = resumePoint({
      id: "s2", status: "active", layer: "grounding", submodule: "seek_clarity",
      intent: "Solva session",
      turns: [
        { role: "solva", text: "..." },                 // ignored
        { role: "user", text: "answer 1" },
        { role: "solva", text: "..." },
        { role: "user", text: "answer 2" },
      ],
    });
    expect(s.state).toBe("Q3");
    expect(s.answers).toEqual({ Q1: "answer 1", Q2: "answer 2" });
  });
  test("active synthesis → PREPARING", () => {
    const s = resumePoint({
      id: "s3", status: "active", layer: "synthesis", turns: [],
    });
    expect(s.state).toBe("PREPARING");
  });
  test("blocked_hard → ARTEFACT_REFUSAL + refusal flag", () => {
    const s = resumePoint({
      id: "s4", status: "blocked_hard", layer: "framing", turns: [],
    });
    expect(s.state).toBe("ARTEFACT_REFUSAL");
    expect(s.refusal).toBe(true);
  });
  test("completed lands on ARTEFACT regardless of reflection count", () => {
    // Per brief §6.3 the artefact is the destination, not a gate.
    const allThree = resumePoint({
      id: "s5", status: "completed", layer: "reflection",
      reflection: { responses: [
        { answer: "a" }, { answer: "b" }, { answer: "c" },
      ] },
      turns: [],
    });
    expect(allThree.state).toBe("ARTEFACT");
    const oneOnly = resumePoint({
      id: "s6", status: "completed", layer: "reflection",
      reflection: { responses: [{ answer: "a" }] },
      turns: [],
    });
    expect(oneOnly.state).toBe("ARTEFACT");
    expect(oneOnly.reflections.REFLECT_1).toEqual({ text: "a", skipped: false });
    const noneYet = resumePoint({
      id: "s6b", status: "completed", layer: "reflection",
      turns: [],
    });
    expect(noneYet.state).toBe("ARTEFACT");
  });
  test("RESUME action drops a snapshot in", () => {
    const snap = resumePoint({
      id: "s7", status: "active", layer: "grounding",
      submodule: "develop_strategy",
      intent: "ints",
      turns: [{ role: "user", text: "first" }],
    });
    const s = nextState(initialState(), Actions.resume(snap));
    expect(s.state).toBe("Q2");
    expect(s.sessionId).toBe("s7");
    expect(s.submodule).toBe("develop_strategy");
    expect(s.answers.Q1).toBe("first");
  });
});

describe("randomised walk — never reaches an undefined state", () => {
  test("100 random forward walks land on COMPLETE or a known state", () => {
    let coverage = new Set();
    for (let i = 0; i < 100; i++) {
      let s = initialState();
      s = nextState(s, Actions.pickSubmodule("seek_clarity"));
      s = nextState(s, Actions.submitFraming("This is a long enough framing string."));
      for (let j = 0; j < 6; j++) {
        s = nextState(s, Actions.answerQuestion("answer " + j));
      }
      s = nextState(s, Actions.preparingDone(Math.random() < 0.5));
      // page-level advance from artefact to REFLECT_1
      s = { ...s, state: "REFLECT_1" };
      for (let k = 0; k < 3; k++) {
        s = nextState(s, Actions.answerReflection("r" + k, k === 1));
      }
      coverage.add(s.state);
      expect(STATES.includes(s.state) || s.state === ARTEFACT_REFUSAL).toBe(true);
    }
    expect(coverage.has("COMPLETE")).toBe(true);
  });
});
