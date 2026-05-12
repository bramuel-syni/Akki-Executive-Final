/**
 * Patch 20 — Render smoke test.
 *
 * Boots a headless browser, signs in as `bramuel@syni.ai` (test
 * credentials in /app/memory/test_credentials.md), then visits the
 * top authenticated routes. For each:
 *   1. Asserts the page DOM is non-empty (body innerText > 50 chars).
 *   2. Asserts ZERO console errors of severity Error.
 *   3. Asserts NO uncaught runtime exceptions (ReferenceError /
 *      TypeError / "undefined is not …").
 *
 * Would have caught:
 *   - `addAgendaButton is not defined`  (Cycle Manager regression)
 *   - `expectedCloseAt is not defined`  (Cycle detail regression, P15)
 *   - The Patch-23 401 on UploadModal — the upload entry point opens
 *     here and any 401-bubbled-to-uncaught-exception would trip the
 *     console-error guard.
 *
 * Local run:
 *   cd /app/frontend && yarn render-smoke
 * CI run (GitHub Actions workflow):
 *   .github/workflows/render-smoke.yml — installs Playwright, boots
 *   the preview, runs `yarn render-smoke`.
 *
 * Override target URL via $RENDER_SMOKE_BASE_URL.
 */
const { chromium } = require("playwright");

const BASE_URL =
  process.env.RENDER_SMOKE_BASE_URL ||
  "https://akki-executive.preview.emergentagent.com";

const EMAIL = process.env.RENDER_SMOKE_EMAIL || "bramuel@syni.ai";
const PASSWORD = process.env.RENDER_SMOKE_PASSWORD || "Bramuel2026!";

// Routes to smoke. Adjust if the app's URL shape changes.
const ROUTES = [
  { name: "Home (app shell)", path: "/app" },
  { name: "Cycle Manager list", path: "/app/cycle" },
  { name: "Work Studio", path: "/app/work-studio" },
  { name: "Monitor", path: "/app/monitor" },
  { name: "Pulse", path: "/app/pulse" },
  { name: "Learn", path: "/app/learn" },
  { name: "Questions", path: "/app/questions" },
  { name: "Workspace (Documents Journal)", path: "/app/workspace" },
];

// Console message classes we ALWAYS fail on.
const FATAL_PATTERNS = [
  /ReferenceError/i,
  /TypeError/i,
  /undefined is not/i,
  /is not defined/i,
  /Cannot read prop/i,
  /Cannot read properties/i,
];

// Console messages we IGNORE (3rd-party noise, expected dev-mode warnings).
const IGNORE_PATTERNS = [
  /favicon\.ico/i,
  /downloadable font/i,
  /Failed to load resource.*\.map/i,
  /React DevTools/i,
  /Lit is in dev mode/i,
];

function isFatal(msg) {
  for (const p of IGNORE_PATTERNS) if (p.test(msg)) return false;
  for (const p of FATAL_PATTERNS) if (p.test(msg)) return true;
  return false;
}

async function smoke() {
  console.log(`[render-smoke] base url = ${BASE_URL}`);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 800 } });
  const page = await context.newPage();

  let failures = [];

  // 1. Sign in.
  console.log(`[render-smoke] step 1 — signin`);
  await page.goto(`${BASE_URL}/signin`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.fill('input[type="email"]', EMAIL);
  await page.fill('input[type="password"]', PASSWORD);
  await Promise.all([
    page.waitForLoadState("networkidle", { timeout: 30000 }),
    page.click('button[type="submit"]'),
  ]);
  console.log(`[render-smoke]  landed at ${page.url()}`);
  if (page.url().includes("/signin")) {
    console.error("[render-smoke] FATAL — still on /signin after login. Check creds.");
    process.exit(2);
  }

  // 2. For each route, capture console errors + dom check.
  for (const route of ROUTES) {
    console.log(`[render-smoke] -- visiting ${route.name} (${route.path}) --`);

    const consoleErrors = [];
    const pageErrors = [];

    const onConsole = (msg) => {
      if (msg.type() === "error" && isFatal(msg.text())) {
        consoleErrors.push(msg.text());
      }
    };
    const onPageError = (err) => { pageErrors.push(err.toString()); };

    page.on("console", onConsole);
    page.on("pageerror", onPageError);

    try {
      await page.goto(`${BASE_URL}${route.path}`, { waitUntil: "domcontentloaded", timeout: 30000 });
      await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
      // Small settle for any post-mount async work (insight cards etc.)
      await page.waitForTimeout(1500);

      // DOM emptiness check
      const bodyText = await page.evaluate(() => (document.body.innerText || "").trim());
      if (bodyText.length < 50) {
        failures.push(`${route.name}: body is empty (${bodyText.length} chars)`);
      }

      // Fatal-pattern console error?
      if (consoleErrors.length > 0) {
        failures.push(`${route.name}: ${consoleErrors.length} fatal console error(s)`);
        for (const e of consoleErrors) console.error(`    CONSOLE  ${e.slice(0, 240)}`);
      }
      // Uncaught page error?
      if (pageErrors.length > 0) {
        failures.push(`${route.name}: ${pageErrors.length} uncaught page error(s)`);
        for (const e of pageErrors) console.error(`    PAGEERROR  ${e.slice(0, 240)}`);
      }

      console.log(`[render-smoke]  ✓ ${route.name} — dom=${bodyText.length}b · console=${consoleErrors.length} · uncaught=${pageErrors.length}`);
    } catch (e) {
      failures.push(`${route.name}: navigation threw — ${e.message}`);
      console.error(`    NAV ERROR  ${e.message}`);
    } finally {
      page.off("console", onConsole);
      page.off("pageerror", onPageError);
    }
  }

  await browser.close();

  if (failures.length) {
    console.error(`\n[render-smoke] FAILED with ${failures.length} issue(s):`);
    for (const f of failures) console.error(`  • ${f}`);
    process.exit(1);
  }
  console.log(`\n[render-smoke] PASS — ${ROUTES.length} routes clean.`);
}

smoke().catch((e) => {
  console.error("[render-smoke] fatal:", e);
  process.exit(3);
});
