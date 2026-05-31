/**
 * Phase P5.6 (2026-02) — production CSRF cross-origin block regression.
 *
 * The bundle that was deployed to akki.syni.ai had API_BASE baked to
 * https://akki-executive.emergent.host/api. When the SPA loaded on
 * akki.syni.ai, every API call was cross-origin → SameSite=Lax cookie
 * suppressed on the login POST → backend rejected with
 * csrf_token_missing.
 *
 * The fix in lib/api.js auto-detects the mismatch at runtime and falls
 * back to same-origin "/api". This test locks the resolver behaviour.
 */

describe("Phase P5.6 — API_BASE cross-origin resolver", () => {
  const originalLocation = window.location;
  const originalBackendEnv = process.env.REACT_APP_BACKEND_URL;

  function setWindowOrigin(origin) {
    delete window.location;
    // eslint-disable-next-line no-global-assign
    window.location = new URL(origin);
  }

  afterEach(() => {
    // Restore.
    window.location = originalLocation;
    if (originalBackendEnv === undefined) {
      delete process.env.REACT_APP_BACKEND_URL;
    } else {
      process.env.REACT_APP_BACKEND_URL = originalBackendEnv;
    }
    jest.resetModules();
  });

  it("uses the configured BACKEND_URL when origin matches (preview happy path)", () => {
    process.env.REACT_APP_BACKEND_URL = "https://akki-executive.preview.emergentagent.com";
    setWindowOrigin("https://akki-executive.preview.emergentagent.com");
    const { API_BASE } = require("../api");
    expect(API_BASE).toBe("https://akki-executive.preview.emergentagent.com/api");
  });

  it("falls back to same-origin when bundle URL doesn't match page origin (the production bug)", () => {
    // Reproduces the exact production deploy state.
    process.env.REACT_APP_BACKEND_URL = "https://akki-executive.emergent.host";
    setWindowOrigin("https://akki.syni.ai");
    const { API_BASE } = require("../api");
    // Same-origin → no leading hostname. Requests resolve to akki.syni.ai/api/...
    expect(API_BASE).toBe("/api");
  });

  it("falls back to same-origin when REACT_APP_BACKEND_URL is empty", () => {
    process.env.REACT_APP_BACKEND_URL = "";
    setWindowOrigin("https://akki.syni.ai");
    const { API_BASE } = require("../api");
    expect(API_BASE).toBe("/api");
  });

  it("falls back to same-origin when the configured URL is malformed", () => {
    process.env.REACT_APP_BACKEND_URL = "not-a-valid-url";
    setWindowOrigin("https://akki.syni.ai");
    const { API_BASE } = require("../api");
    expect(API_BASE).toBe("/api");
  });

  it("resolveBackendOrigin returns the build URL on origin match and '' on mismatch", () => {
    // Match case.
    process.env.REACT_APP_BACKEND_URL = "https://akki.syni.ai";
    setWindowOrigin("https://akki.syni.ai");
    let mod = require("../api");
    expect(mod.resolveBackendOrigin()).toBe("https://akki.syni.ai");
    jest.resetModules();

    // Mismatch case — same setup as the production bug.
    process.env.REACT_APP_BACKEND_URL = "https://akki-executive.emergent.host";
    setWindowOrigin("https://akki.syni.ai");
    mod = require("../api");
    expect(mod.resolveBackendOrigin()).toBe("");
  });
});
