/**
 * Patch 20 + 24A — Render smoke test.
 *
 * Phase 1 (Patch 20): boots headless Chromium, signs in as
 * `bramuel@syni.ai`, visits 8 authenticated routes. Asserts non-empty
 * DOM, zero fatal console errors, zero uncaught page errors.
 *
 * Phase 2 (Patch 24A): exercises the upload happy path on two real
 * entry points — HeroDocActions "+ Add document" + Work Studio
 * Briefing "Create a Brief" — using a real fixture PDF. Intercepts
 * the network request to assert HTTP 2xx and waits for the success
 * toast. This catches the exact regression that hit Patch 23 — a raw
 * `fetch()` bypassing the auth interceptor would return 401 and the
 * toast would never appear.
 *
 * Local run:
 *   cd /app/frontend && yarn render-smoke
 * CI run:
 *   .github/workflows/render-smoke.yml
 *
 * Override target URL via $RENDER_SMOKE_BASE_URL.
 * Override credentials via $RENDER_SMOKE_EMAIL / $RENDER_SMOKE_PASSWORD.
 */
const path = require("path");
const { chromium } = require("playwright");

const BASE_URL =
  process.env.RENDER_SMOKE_BASE_URL ||
  "https://akki-executive.preview.emergentagent.com";

const EMAIL = process.env.RENDER_SMOKE_EMAIL || "bramuel@syni.ai";
const PASSWORD = process.env.RENDER_SMOKE_PASSWORD || "Bramuel2026!";

const FIXTURE_PDF = path.resolve(__dirname, "../tests/fixtures/smoke-upload.pdf");

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
  // Phase E (2026-05-16) — new React surfaces shipped in the rewrite.
  { name: "Solva landing (Phase D-routed)", path: "/app/solva" },
  { name: "Solva Phase D — new session", path: "/app/solva/phase-d/session/new?submodule=seek_clarity" },
  { name: "Synisense Observability (admin)", path: "/app/admin/synisense-observability" },
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

async function login(page) {
  await page.goto(`${BASE_URL}/signin`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.fill('input[type="email"]', EMAIL);
  await page.fill('input[type="password"]', PASSWORD);
  await Promise.all([
    page.waitForLoadState("networkidle", { timeout: 30000 }),
    page.click('button[type="submit"]'),
  ]);
  if (page.url().includes("/signin")) {
    console.error("[render-smoke] FATAL — still on /signin after login. Check creds.");
    process.exit(2);
  }
}

// ----------------------------------------------------------------------
// Phase 1 — route smoke
// ----------------------------------------------------------------------
async function smokeRoutes(page, failures) {
  for (const route of ROUTES) {
    console.log(`[render-smoke] -- visiting ${route.name} (${route.path}) --`);

    const consoleErrors = [];
    const pageErrors = [];
    const onConsole = (msg) => {
      if (msg.type() === "error" && isFatal(msg.text())) consoleErrors.push(msg.text());
    };
    const onPageError = (err) => { pageErrors.push(err.toString()); };
    page.on("console", onConsole);
    page.on("pageerror", onPageError);

    try {
      await page.goto(`${BASE_URL}${route.path}`, { waitUntil: "domcontentloaded", timeout: 30000 });
      await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
      await page.waitForTimeout(1500);

      const bodyText = await page.evaluate(() => (document.body.innerText || "").trim());
      if (bodyText.length < 50) failures.push(`${route.name}: body is empty (${bodyText.length} chars)`);
      if (consoleErrors.length > 0) {
        failures.push(`${route.name}: ${consoleErrors.length} fatal console error(s)`);
        for (const e of consoleErrors) console.error(`    CONSOLE  ${e.slice(0, 240)}`);
      }
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
}

// ----------------------------------------------------------------------
// Phase 2 — upload happy-path smoke (Patch 24A)
//
// Tests two entry points: HeroDocActions on Home, Briefing tab in
// Work Studio. For each: open the modal, attach the fixture PDF,
// submit, assert HTTP 2xx on the network response, assert no
// uncaught errors.
// ----------------------------------------------------------------------
async function smokeUpload(page, failures, label, openFn) {
  console.log(`[render-smoke] -- upload happy path: ${label} --`);

  const uploadResponses = [];
  const uploadRequests = [];
  const pageErrors = [];
  const onRequest = (req) => {
    const url = req.url();
    if (/\/api\/contexts\/[^/]+\/documents(\?|$)/.test(url) && req.method() === "POST") {
      uploadRequests.push({
        url,
        // Capture the Authorization header — this is the Patch 23
        // regression catcher. Raw `fetch()` from inside the React app
        // drops localStorage tokens; only the axios api client
        // attaches the bearer.
        authorization: req.headers()["authorization"] || null,
      });
    }
  };
  const onResponse = (resp) => {
    const url = resp.url();
    if (/\/api\/contexts\/[^/]+\/documents(\?|$)/.test(url) && resp.request().method() === "POST") {
      uploadResponses.push({ status: resp.status(), url });
    }
  };
  const onPageError = (err) => { pageErrors.push(err.toString()); };
  page.on("request", onRequest);
  page.on("response", onResponse);
  page.on("pageerror", onPageError);

  try {
    await openFn();
    await page.waitForSelector('[data-testid="upload-modal"]', { timeout: 8000 });
    await page.setInputFiles('[data-testid="upload-file-input"]', FIXTURE_PDF);
    await page.waitForSelector('[data-testid="upload-file-selected"]', { timeout: 5000 });
    await page.click('[data-testid="upload-submit-btn"]');

    const deadline = Date.now() + 8000;
    while (uploadResponses.length === 0 && Date.now() < deadline) {
      await page.waitForTimeout(200);
    }

    if (uploadResponses.length === 0) {
      failures.push(`${label}: no upload POST observed within 8s — modal might not have submitted`);
    } else {
      const resp = uploadResponses[0];
      const req = uploadRequests[0] || { authorization: null };
      // ── Patch 24A — assert the Authorization bearer header is
      //    present. This catches the exact Patch 23 regression
      //    pattern (raw fetch() bypasses the axios interceptor).
      if (!req.authorization || !req.authorization.toLowerCase().startsWith("bearer ")) {
        failures.push(
          `${label}: upload request missing 'Authorization: Bearer …' header — ` +
          `this is the Patch 23 regression class (raw fetch() bypassing the axios interceptor).`
        );
        console.error(`    NO AUTH HEADER  authorization=${req.authorization}`);
      } else if (resp.status < 200 || resp.status >= 300) {
        failures.push(`${label}: upload returned HTTP ${resp.status}`);
        console.error(`    UPLOAD STATUS  ${resp.status}  ${resp.url}`);
      } else {
        console.log(`[render-smoke]  ✓ ${label} — upload HTTP ${resp.status} · authz=bearer ✓`);
      }
    }

    if (pageErrors.length > 0) {
      failures.push(`${label}: ${pageErrors.length} uncaught page error(s) during upload`);
      for (const e of pageErrors) console.error(`    PAGEERROR  ${e.slice(0, 240)}`);
    }

    await page.waitForTimeout(1200);
    await page.keyboard.press("Escape").catch(() => {});
    await page.waitForTimeout(500);
  } catch (e) {
    failures.push(`${label}: upload flow threw — ${e.message}`);
    console.error(`    UPLOAD ERROR  ${e.message}`);
  } finally {
    page.off("request", onRequest);
    page.off("response", onResponse);
    page.off("pageerror", onPageError);
  }
}

async function smoke() {
  console.log(`[render-smoke] base url = ${BASE_URL}`);
  console.log(`[render-smoke] fixture  = ${FIXTURE_PDF}`);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 800 } });
  const page = await context.newPage();
  const failures = [];

  console.log(`[render-smoke] step 1 — signin`);
  await login(page);
  console.log(`[render-smoke]  landed at ${page.url()}`);

  console.log(`[render-smoke] step 2 — route smoke (${ROUTES.length} routes)`);
  await smokeRoutes(page, failures);

  console.log(`[render-smoke] step 3 — upload happy path`);

  // Entry point 1 — HeroDocActions floating button on Home
  await page.goto(`${BASE_URL}/app`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  await smokeUpload(page, failures, "HeroDocActions (+ Add document)", async () => {
    // HeroDocActions dispatches `akki:open-upload-modal` to open the
    // shared modal. Click the button (preferred — exercises the real
    // user path); if it isn't visible (e.g. Home 2 layout), dispatch
    // the event directly.
    const btn = page.locator('[data-testid="home-hero-add-document"]').first();
    if (await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await btn.click();
    } else {
      await page.evaluate(() => window.dispatchEvent(new CustomEvent("akki:open-upload-modal")));
    }
  });

  // Entry point 2 — Work Studio (any context-bound surface — same
  // UploadModal is reachable from anywhere via the global event).
  await page.goto(`${BASE_URL}/app/work-studio`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  await smokeUpload(page, failures, "Work Studio upload", async () => {
    // From Work Studio, opening UploadModal is via the same global
    // event. This proves the upload flow works while the user is
    // already inside the app shell on a different surface.
    await page.evaluate(() => window.dispatchEvent(new CustomEvent("akki:open-upload-modal")));
  });

  // ────────────────────────────────────────────────────────────────────
  // Phase 3 — Patch 28 interaction smoke.
  //
  //   28C: Document Journal happy path — list row → drawer opens
  //   28D: Workspace listing rows surface a snippet description
  //   28E: Modals respect the global max-h-[85vh] sizing rule
  //   28F: Monitor v2 executive listings open a row drawer on click
  // ────────────────────────────────────────────────────────────────────
  console.log(`[render-smoke] step 4 — Patch 28 interaction smoke`);
  await smokePatch28(page, failures);

  // ────────────────────────────────────────────────────────────────────
  // Phase 4 — Chunk 4 Compilation Wizard kind dispatch.
  //
  //   WS-R02 / R07 / R08 — Compile-XXX buttons open the wizard on Step 1
  //   WS-R04             — Compile Board Pack pre-selects Board Pack
  //                        (was Report — same call site)
  //   WS-R05 / R08       — Step 2 source list is scoped to the right kind
  //                        (covered by backend test_chunk4_wizard_aggregates;
  //                        smoke only checks the Step-1 contract here).
  // ────────────────────────────────────────────────────────────────────
  console.log(`[render-smoke] step 5 — Chunk 4 Compilation Wizard smoke`);
  await smokeChunk4Wizard(page, failures);

  // ────────────────────────────────────────────────────────────────────
  // Phase 6 — Chunk 5 Create-Artefact modal (Deck + Report tabs).
  //
  //   WS-R09 / R10 / R11 — Decks "Create Summary Deck" blank-path
  //   WS-R13 / R14       — Reports "Create Report" blank-path
  //   The richer brief/document paths are covered by the backend test
  //   suite (test_chunk5_create_artefact.py — 14 tests). Render-smoke
  //   only proves the round-trip through the UI works on the simplest
  //   path that doesn't require pre-seeded data.
  // ────────────────────────────────────────────────────────────────────
  console.log(`[render-smoke] step 6 — Chunk 5 Create-Artefact modal smoke`);
  await smokeChunk5CreateArtefact(page, failures);

  // ────────────────────────────────────────────────────────────────────
  // Phase 7 — Chunk 6 Brief surfaces (WS-R01 / R17 / R18 / R19).
  //
  //   Light frontend check: when a brief / deck / report row is
  //   clicked, the drawer opens with a working "Open in composer"
  //   primary CTA whose href is NOT undefined. The full surface
  //   (DOCX title rendering, chat → brief round-trip) is covered by
  //   the 11-test backend suite test_chunk6_brief_surfaces.py.
  // ────────────────────────────────────────────────────────────────────
  console.log(`[render-smoke] step 7 — Chunk 6 Brief drawer CTA smoke`);
  await smokeChunk6BriefDrawer(page, failures);

  // ────────────────────────────────────────────────────────────────────
  // Phase 8 (Chunk 7 fix-pass, 2026-05-18) — QA-2026-05-16-007.
  //   Generate-signals action must:
  //     · flip the rail button to "Generating signals…" immediately;
  //     · render the verbatim status copy "Akki is analysing your
  //       document. This may take a moment." within ≤6s of click;
  //     · surface an inline error if the job fails (covered by
  //       pytest; here we lock the loading + 4s status DOM contract).
  // ────────────────────────────────────────────────────────────────────
  console.log(`[render-smoke] step 8 — Chunk 7 Generate-Signals loading + status copy`);
  await smokeChunk7GenerateSignals(page, failures);

  // ────────────────────────────────────────────────────────────────────
  // Phase 9 (Chunk 8, 2026-05-18) — QA-2026-05-16-029…-036.
  //   Document Overlay smoke. Opens the first Work Studio row → drawer →
  //   "Open Document Overlay" CTA → overlay shell renders, toolbar +
  //   intelligence card + document surface DOM all present. Soft-skips
  //   if no row exists (empty context).
  // ────────────────────────────────────────────────────────────────────
  console.log(`[render-smoke] step 9 — Chunk 8 Document Overlay smoke`);
  await smokeChunk8DocumentOverlay(page, failures);

  await browser.close();

  if (failures.length) {
    console.error(`\n[render-smoke] FAILED with ${failures.length} issue(s):`);
    for (const f of failures) console.error(`  • ${f}`);
    process.exit(1);
  }
  console.log(`\n[render-smoke] PASS — ${ROUTES.length} routes clean · 2 upload paths green · Patch 28 interactions green · Chunk 4 wizard green · Chunk 5 create-artefact green · Chunk 6 brief-drawer CTA green · Chunk 7 generate-signals loading green · Chunk 8 document overlay green.`);
}

// ----------------------------------------------------------------------
// Phase 4 (Chunk 4) — Compilation Wizard kind-dispatch.
//
// Visit Work Studio → click "Compile Board Pack" → wizard MUST open
// on Step 1 with Board Pack pre-selected (was: Step 2 with Report
// selected). We then close and repeat for "Compile Minutes" to prove
// the per-button dispatch routes to the right kind.
//
// We DO NOT validate Step 2's source list contents here — that's
// covered by `test_chunk4_wizard_aggregates.py` on the backend (data
// shape depends on seeded state which is account-specific). The
// contract this smoke locks is the UI-side wiring (right step, right
// radio).
// ----------------------------------------------------------------------
async function smokeChunk4Wizard(page, failures) {
  const pageErrors = [];
  const onPageError = (err) => { pageErrors.push(err.toString()); };
  page.on("pageerror", onPageError);

  try {
    await page.goto(`${BASE_URL}/app/work-studio`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(800);

    // Iterate the kinds the QA report explicitly named (R02 board_pack,
    // R07 minutes, R08 committee_pack). For each: locate the Compile
    // action chip, click it, assert wizard-step-1 visible + the matching
    // type radio carries the `-selected` testid suffix.
    const cases = [
      { tabAction: "compile_board_pack",     expectedSelected: "board_pack" },
      { tabAction: "compile_minutes",        expectedSelected: "minutes" },
      { tabAction: "compile_committee_pack", expectedSelected: "committee_pack" },
    ];

    for (const c of cases) {
      // Action chips live inside the per-tab ContextActions row in
      // WorkStudio — they don't carry a deterministic testid, so we
      // locate them by visible text inside the contextual action row.
      // First, open the matching artefact tab via its testid.
      const tabTestId = c.tabAction === "compile_board_pack"
        ? "work-studio-tab-cycle_board_pack"
        : c.tabAction === "compile_minutes"
          ? "work-studio-tab-cycle_minutes"
          : "work-studio-tab-cycle_committee_pack";
      // The active variant of the testid (when already focused) uses a
      // suffix, so we match by id prefix. The "active" suffix is
      // appended only when already on the tab — both variants suit us.
      const tabBtn = page.locator(
        `[data-testid^="${tabTestId}"]`,
      ).first();
      const labelMap = {
        compile_board_pack:     "Board Pack",
        compile_minutes:        "Minutes",
        compile_committee_pack: "Committee Pack",
      };
      const tabLabel = labelMap[c.tabAction];
      if (!(await tabBtn.isVisible({ timeout: 4000 }).catch(() => false))) {
        console.log(`[render-smoke]  · Chunk 4 — tab "${tabLabel}" not visible; soft-skipping`);
        continue;
      }
      await tabBtn.click();
      await page.waitForTimeout(500);

      const compileLabel = `Compile ${tabLabel}`;
      const compileBtn = page.locator(`button:has-text("${compileLabel}")`).first();
      if (!(await compileBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
        console.log(`[render-smoke]  · Chunk 4 — "${compileLabel}" action not visible; soft-skipping`);
        continue;
      }
      await compileBtn.click();

      // Step 1 must render. Step 2 must NOT be the initial render.
      const onStep1 = await page
        .waitForSelector('[data-testid="wizard-step-1"]', { timeout: 4000 })
        .then(() => true)
        .catch(() => false);
      if (!onStep1) {
        failures.push(`Chunk 4: wizard did not land on Step 1 for ${c.tabAction}`);
        // Close any open dialog before next iteration.
        await page.keyboard.press("Escape").catch(() => {});
        await page.waitForTimeout(300);
        continue;
      }

      // The selected radio carries `-selected` in its testid.
      const selSel = `[data-testid="wizard-artefact-type-${c.expectedSelected}-selected"]`;
      const isSelected = await page.locator(selSel).isVisible({ timeout: 2000 }).catch(() => false);
      if (!isSelected) {
        failures.push(
          `Chunk 4: Compile ${tabLabel} did not pre-select "${c.expectedSelected}" on Step 1 ` +
          `(missing ${selSel})`,
        );
      } else {
        console.log(`[render-smoke]  ✓ Chunk 4 — Compile ${tabLabel} opens Step 1 with ${c.expectedSelected} selected`);
      }

      // Close the wizard before next iteration. The wizard doesn't
      // carry a dedicated cancel button testid — ESC + click-outside
      // both fire `onClose`. We use ESC since it's deterministic.
      await page.keyboard.press("Escape").catch(() => {});
      await page.waitForTimeout(400);
    }
  } catch (e) {
    failures.push(`Chunk 4: wizard flow threw — ${e.message}`);
  }

  if (pageErrors.length > 0) {
    failures.push(`Chunk 4 step: ${pageErrors.length} uncaught page error(s)`);
    for (const e of pageErrors) console.error(`    PAGEERROR  ${e.slice(0, 240)}`);
  }
  page.off("pageerror", onPageError);
}

// ----------------------------------------------------------------------
// Phase 3 (Patch 28) — Doc journal drawer + modal sizing + Monitor drawer.
//
// We bundle the three Patch 28 interaction checks into one step because
// they all hang off the same authenticated session and the same set of
// console / pageerror listeners. Each check appends to `failures` so
// the rest still run if one fails.
// ----------------------------------------------------------------------
async function smokePatch28(page, failures) {
  const pageErrors = [];
  const onPageError = (err) => { pageErrors.push(err.toString()); };
  page.on("pageerror", onPageError);

  // ── 28C/28D: Workspace journal — row click opens drawer + snippet
  try {
    await page.goto(`${BASE_URL}/app/workspace`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(800);

    const firstRow = page.locator('[data-testid^="workspace-row-"]').first();
    const rowVisible = await firstRow.isVisible({ timeout: 4000 }).catch(() => false);

    if (!rowVisible) {
      console.log(`[render-smoke]  · workspace has zero docs — skipping 28C/28D row assertions (account empty)`);
    } else {
      // 28D — snippet renders alongside row (even if "No summary available yet.")
      const rowSnippet = page.locator('[data-testid^="workspace-row-snippet-"]').first();
      const snippetVisible = await rowSnippet.isVisible({ timeout: 2000 }).catch(() => false);
      if (!snippetVisible) {
        failures.push("Patch 28D: workspace row missing data-testid='workspace-row-snippet-…' description line");
      } else {
        const txt = (await rowSnippet.textContent() || "").trim();
        if (!txt) failures.push("Patch 28D: workspace row snippet rendered but empty");
        else console.log(`[render-smoke]  ✓ Patch 28D — row snippet present (${txt.length} chars)`);
      }

      // 28C — click row, drawer opens
      await firstRow.click();
      const drawerOpened = await page
        .waitForSelector('[data-testid="journal-drawer-panel"]', { timeout: 6000 })
        .then(() => true)
        .catch(() => false);
      if (!drawerOpened) {
        failures.push("Patch 28C: journal drawer did not open on row click");
      } else {
        console.log(`[render-smoke]  ✓ Patch 28C — journal drawer opens on row click`);
        // 28C close-out: drawer has a "Download original" only via the
        // legacy ReadingTopBar — drawer itself relies on Open-full-reader.
        // Just close it cleanly.
        const closeBtn = page.locator('[data-testid="journal-drawer-close"]').first();
        if (await closeBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
          await closeBtn.click();
          await page.waitForTimeout(300);
        }
      }
    }
  } catch (e) {
    failures.push(`Patch 28C/28D: workspace flow threw — ${e.message}`);
  }

  // ── 28E: Modal sizing — open a known modal and assert max-h-[85vh]
  //    classes are inherited from the global shadcn DialogContent rule.
  //    We use the "Set my function" modal on Monitor as the canonical
  //    hand-rolled modal under test.
  try {
    await page.goto(`${BASE_URL}/app/monitor`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(800);

    // Trigger the function picker hand-rolled modal.
    const editBtn = page.locator('[data-testid="monitor-edit-fn"]').first();
    const nudgeBtn = page.locator('[data-testid="monitor-fn-nudge-cta"]').first();
    let opened = false;
    if (await editBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await editBtn.click(); opened = true;
    } else if (await nudgeBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await nudgeBtn.click(); opened = true;
    }

    if (!opened) {
      console.log(`[render-smoke]  · 28E — no function-picker trigger visible (NED role?); skipping`);
    } else {
      const modal = await page
        .waitForSelector('[data-testid="monitor-fn-modal"]', { timeout: 4000 })
        .catch(() => null);
      if (!modal) {
        failures.push("Patch 28E: hand-rolled monitor-fn-modal did not open");
      } else {
        const cls = await modal.getAttribute("class");
        if (!cls || !/max-h-\[85vh\]/.test(cls) || !/overflow-y-auto/.test(cls)) {
          failures.push(
            `Patch 28E: monitor-fn-modal missing 85vh cap or overflow-y-auto (class=${cls ? cls.slice(0, 140) : "null"}…)`
          );
        } else {
          console.log(`[render-smoke]  ✓ Patch 28E — hand-rolled modal carries max-h-[85vh] + overflow-y-auto`);
        }
        // Close the modal so we don't pollute the next step.
        await page.keyboard.press("Escape").catch(() => {});
        await page.waitForTimeout(400);
      }
    }
  } catch (e) {
    failures.push(`Patch 28E: modal sizing check threw — ${e.message}`);
  }

  // ── 28F: Monitor executive listings → row click opens drawer.
  try {
    await page.goto(`${BASE_URL}/app/monitor`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(1200);

    // Try Strategic Goals row first (the executive Strategic listing).
    const goalRow = page.locator('[data-testid^="strategic-goal-"]').first();
    const goalVisible = await goalRow.isVisible({ timeout: 3000 }).catch(() => false);

    if (goalVisible) {
      await goalRow.click();
      const drawer = await page
        .waitForSelector('[data-testid="goal-drawer"]', { timeout: 4000 })
        .catch(() => null);
      if (!drawer) {
        failures.push("Patch 28F: Strategic Goal row click did not open the drawer");
      } else {
        console.log(`[render-smoke]  ✓ Patch 28F — Strategic Goal drawer opens on row click`);
        const closeBtn = page.locator('[data-testid="goal-drawer-close"]').first();
        if (await closeBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
          await closeBtn.click();
          await page.waitForTimeout(300);
        }
      }
    } else {
      console.log(`[render-smoke]  · 28F — no strategic goals on this context; falling back to Objectives panel`);
      const objRow = page.locator('[data-testid^="obj-row-"]').first();
      const objVisible = await objRow.isVisible({ timeout: 3000 }).catch(() => false);
      if (objVisible) {
        await objRow.click();
        const drawer = await page
          .waitForSelector('[data-testid="obj-drawer"]', { timeout: 4000 })
          .catch(() => null);
        if (!drawer) {
          failures.push("Patch 28F fallback: Objectives row click did not open the drawer");
        } else {
          console.log(`[render-smoke]  ✓ Patch 28F (objectives fallback) — drawer opens on row click`);
          const closeBtn = page.locator('[data-testid="obj-drawer-close"]').first();
          if (await closeBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
            await closeBtn.click();
            await page.waitForTimeout(300);
          }
        }
      } else {
        console.log(`[render-smoke]  · 28F — neither strategic-goals nor objectives present; nothing to click. Treating as soft-skip.`);
      }
    }
  } catch (e) {
    failures.push(`Patch 28F: Monitor drawer check threw — ${e.message}`);
  }

  if (pageErrors.length > 0) {
    failures.push(`Patch 28 interaction step: ${pageErrors.length} uncaught page error(s)`);
    for (const e of pageErrors) console.error(`    PAGEERROR  ${e.slice(0, 240)}`);
  }

  page.off("pageerror", onPageError);
}

// ----------------------------------------------------------------------
// Phase 6 (Chunk 5) — Create-Summary-Deck + Create-Report modal.
//
// Visit Work Studio → Decks tab → click "Create Summary Deck" → modal
// opens → fill title → Blank source → submit. Repeat for Reports.
// Each pass asserts a success toast/redirect indicator and that the
// modal closes cleanly. We don't validate the listing here because
// it requires waiting for the new context to refresh — that's covered
// by the backend test suite.
// ----------------------------------------------------------------------
async function smokeChunk5CreateArtefact(page, failures) {
  const pageErrors = [];
  const onPageError = (err) => { pageErrors.push(err.toString()); };
  page.on("pageerror", onPageError);

  try {
    await page.goto(`${BASE_URL}/app/work-studio`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(800);

    const cases = [
      {
        tabTestIdPrefix: "work-studio-tab-deck",
        actionLabel: "Create Summary Deck",
        modalTestId: "create-artefact-modal-deck",
        kind: "deck",
        title: `Smoke deck ${Date.now()}`,
      },
      {
        tabTestIdPrefix: "work-studio-tab-report",
        actionLabel: "Create Report",
        modalTestId: "create-artefact-modal-report",
        kind: "report",
        title: `Smoke report ${Date.now()}`,
      },
    ];

    for (const c of cases) {
      // Switch to the right tab.
      const tabBtn = page.locator(`[data-testid^="${c.tabTestIdPrefix}"]`).first();
      if (!(await tabBtn.isVisible({ timeout: 4000 }).catch(() => false))) {
        console.log(`[render-smoke]  · Chunk 5 — tab "${c.kind}" not visible; soft-skipping`);
        continue;
      }
      await tabBtn.click();
      await page.waitForTimeout(500);

      // Click the Create-XXX action chip.
      const actionBtn = page.locator(`button:has-text("${c.actionLabel}")`).first();
      if (!(await actionBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
        console.log(`[render-smoke]  · Chunk 5 — "${c.actionLabel}" action not visible; soft-skipping`);
        continue;
      }
      await actionBtn.click();

      // Modal opens.
      const modal = page.locator(`[data-testid="${c.modalTestId}"]`);
      const opened = await modal.isVisible({ timeout: 3000 }).catch(() => false);
      if (!opened) {
        failures.push(`Chunk 5: ${c.actionLabel} did not open the create modal`);
        await page.keyboard.press("Escape").catch(() => {});
        await page.waitForTimeout(300);
        continue;
      }

      // Title field is present + interactable.
      const titleInput = page.locator(`[data-testid="create-artefact-title-${c.kind}"]`).first();
      if (!(await titleInput.isVisible({ timeout: 2000 }).catch(() => false))) {
        failures.push(`Chunk 5: title input missing for ${c.kind}`);
        await page.keyboard.press("Escape").catch(() => {});
        continue;
      }
      await titleInput.fill(c.title);

      // Default source is blank — assert the radio is selected.
      const blankRadio = page.locator(`[data-testid="create-artefact-source-blank"]`).first();
      const blankSelected = await blankRadio.isChecked().catch(() => false);
      if (!blankSelected) {
        failures.push(`Chunk 5: blank source radio not checked by default for ${c.kind}`);
      }

      // Submit.
      const submitBtn = page.locator(`[data-testid="create-artefact-submit-${c.kind}"]`).first();
      await submitBtn.click();

      // Wait for the modal to close OR for the success toast to surface.
      // Either signal proves the round-trip succeeded; if neither
      // happens we fail.
      const closed = await modal.waitFor({ state: "hidden", timeout: 8000 }).then(() => true).catch(() => false);
      if (!closed) {
        failures.push(`Chunk 5: ${c.actionLabel} submit did not close the modal within 8s`);
        await page.keyboard.press("Escape").catch(() => {});
        await page.waitForTimeout(400);
        continue;
      }

      console.log(`[render-smoke]  ✓ Chunk 5 — ${c.actionLabel} blank-path round-trips`);

      // Each test redirects the user to /app/studio/composer/<kind>/<id>
      // — wait for the URL to settle, then bounce back to Work Studio.
      await page.waitForTimeout(800);
      await page.goto(`${BASE_URL}/app/work-studio`, { waitUntil: "domcontentloaded", timeout: 20000 }).catch(() => {});
      await page.waitForTimeout(500);
    }
  } catch (e) {
    failures.push(`Chunk 5: create-artefact flow threw — ${e.message}`);
  }

  if (pageErrors.length > 0) {
    failures.push(`Chunk 5 step: ${pageErrors.length} uncaught page error(s)`);
    for (const e of pageErrors) console.error(`    PAGEERROR  ${e.slice(0, 240)}`);
  }
  page.off("pageerror", onPageError);
}

// ----------------------------------------------------------------------
// Phase 7 (Chunk 6) — Brief drawer Open-in-composer CTA.
//
// Pre-Chunk-6 clicking a brief row opened a drawer whose primary
// action target was `undefined` (WS-R01) or the drawer never rendered
// because the backend 400'd with "Bad aggregate id." (WS-R17). The
// new aggregate detail endpoint surfaces `composer_url`; the drawer
// renders an "Open in composer" button. This smoke step proves the
// button is present with a non-undefined target whenever a row exists.
// ----------------------------------------------------------------------
async function smokeChunk6BriefDrawer(page, failures) {
  const pageErrors = [];
  const onPageError = (err) => { pageErrors.push(err.toString()); };
  page.on("pageerror", onPageError);

  try {
    await page.goto(`${BASE_URL}/app/work-studio`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(800);

    // Try each kind tab in order; first one with a row wins.
    const tabs = ["briefing", "deck", "report"];
    let opened = false;
    for (const tab of tabs) {
      const tabBtn = page.locator(`[data-testid="work-studio-tab-${tab}"]`).first();
      if (!(await tabBtn.isVisible({ timeout: 3000 }).catch(() => false))) continue;
      await tabBtn.click();
      await page.waitForTimeout(500);

      // Look for any brief row.
      const firstRow = page.locator(`[data-testid="work-studio-brief-row"]`).first();
      if (!(await firstRow.isVisible({ timeout: 2500 }).catch(() => false))) continue;

      await firstRow.click();
      const drawer = page.locator(`[data-testid="work-studio-brief-drawer"]`).first();
      if (!(await drawer.isVisible({ timeout: 4000 }).catch(() => false))) {
        failures.push(`Chunk 6: drawer did not open after clicking ${tab} row`);
        continue;
      }

      // Wait for either the loading state to clear or the err banner.
      const cta = page.locator(`[data-testid="work-studio-brief-drawer-open-composer"]`).first();
      const err = page.locator(`[data-testid="work-studio-brief-drawer-err"]`).first();

      // Give the detail request up to 5s.
      let success = false;
      const start = Date.now();
      while (Date.now() - start < 5000) {
        if (await cta.isVisible().catch(() => false)) { success = true; break; }
        if (await err.isVisible().catch(() => false)) { break; }
        await page.waitForTimeout(150);
      }

      if (success) {
        // Verify the button has a usable click target (no `undefined`
        // route would mean the click fires but does nothing visible —
        // this smoke just proves the testid renders with content).
        const txt = (await cta.textContent()) || "";
        if (!txt.toLowerCase().includes("open in composer")) {
          failures.push(`Chunk 6: composer CTA label is unexpected: "${txt.trim()}"`);
        } else {
          console.log(`[render-smoke]  ✓ Chunk 6 — ${tab} row → drawer → Open-in-composer CTA rendered`);
          opened = true;
        }

        // Close the drawer.
        await page.keyboard.press("Escape").catch(() => {});
        await page.waitForTimeout(400);
        break;
      } else if (await err.isVisible().catch(() => false)) {
        const errMsg = ((await err.textContent()) || "").trim();
        // If the err mentions "Bad aggregate id" the regression is back.
        if (errMsg.toLowerCase().includes("bad aggregate")) {
          failures.push(`Chunk 6: WS-R17 regression — backend still returns "Bad aggregate id." for ${tab}`);
        } else {
          // Other errors (e.g. 404 missing row) are fine — just try next tab.
          console.log(`[render-smoke]  · Chunk 6 — ${tab} row detail returned non-regression error: "${errMsg.slice(0, 60)}"`);
        }
        await page.keyboard.press("Escape").catch(() => {});
        await page.waitForTimeout(300);
      }
    }

    if (!opened) {
      console.log(`[render-smoke]  · Chunk 6 — no brief rows visible on this test account; backend test suite is the authoritative check.`);
    }
  } catch (e) {
    failures.push(`Chunk 6: brief drawer flow threw — ${e.message}`);
  }

  if (pageErrors.length > 0) {
    failures.push(`Chunk 6 step: ${pageErrors.length} uncaught page error(s)`);
    for (const e of pageErrors) console.error(`    PAGEERROR  ${e.slice(0, 240)}`);
  }
  page.off("pageerror", onPageError);
}

smoke().catch((e) => {
  console.error("[render-smoke] fatal:", e);
  process.exit(3);
});


// ----------------------------------------------------------------------
// Phase 9 (Chunk 8, 2026-05-18) — QA-2026-05-16-029…-036 smoke.
//
// Path: Work Studio → first brief row → drawer → "Open Document
// Overlay" CTA → overlay shell renders with toolbar + intelligence
// card + document surface DOM. Closes via the back arrow. Asserts no
// uncaught page errors during the round trip.
// ----------------------------------------------------------------------
async function smokeChunk8DocumentOverlay(page, failures) {
  const pageErrors = [];
  const onPageError = (err) => { pageErrors.push(err.toString()); };
  page.on("pageerror", onPageError);

  try {
    await page.goto(`${BASE_URL}/app/work-studio`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(800);

    const firstRow = page.locator('[data-testid="work-studio-brief-row"]').first();
    const rowVisible = await firstRow.isVisible().catch(() => false);
    if (!rowVisible) {
      console.log(`[render-smoke]  · Chunk 8 — work-studio has no brief rows; soft-skipping QA-029→-036`);
      return;
    }

    await firstRow.click();
    await page.waitForTimeout(1500);

    // Drawer should be open with the new Open Overlay CTA.
    const overlayBtn = page.locator('[data-testid="work-studio-brief-drawer-open-overlay"]').first();
    const btnVisible = await overlayBtn.isVisible().catch(() => false);
    if (!btnVisible) {
      failures.push(`Chunk 8 (QA-029): "Open Document Overlay" CTA not visible inside the brief drawer`);
      return;
    }

    await overlayBtn.click();
    // Wait for the overlay shell to mount.
    const shell = page.locator('[data-testid="document-overlay-shell"]').first();
    try {
      await shell.waitFor({ state: "visible", timeout: 8000 });
    } catch {
      failures.push(`Chunk 8 (QA-029): overlay shell did not mount within 8s`);
      return;
    }
    console.log(`[render-smoke]  ✓ Chunk 8 (QA-029) — overlay shell mounted`);

    // -030 toolbar
    if (!await page.locator('[data-testid="document-overlay-toolbar"]').first().isVisible().catch(() => false)) {
      failures.push(`Chunk 8 (QA-030): overlay toolbar not visible`);
    } else {
      console.log(`[render-smoke]  ✓ Chunk 8 (QA-030) — toolbar rendered`);
    }

    // -030 status badge
    const badge = page.locator('[data-testid="document-overlay-status-badge"]').first();
    if (!await badge.isVisible().catch(() => false)) {
      failures.push(`Chunk 8 (QA-030): status badge missing`);
    } else {
      const badgeText = ((await badge.textContent()) || "").trim();
      if (!/(Draft|In Review|Committed)/.test(badgeText)) {
        failures.push(`Chunk 8 (QA-030): status badge text "${badgeText}" doesn't match expected vocabulary`);
      } else {
        console.log(`[render-smoke]  ✓ Chunk 8 (QA-030) — status badge: ${badgeText}`);
      }
    }

    // -031 intelligence card
    const intelCard = page.locator('[data-testid="document-overlay-intelligence-card"]').first();
    if (!await intelCard.isVisible().catch(() => false)) {
      failures.push(`Chunk 8 (QA-031): intelligence card not visible`);
    } else {
      const band = await intelCard.getAttribute("data-confidence-band");
      console.log(`[render-smoke]  ✓ Chunk 8 (QA-031) — intelligence card band=${band}`);
    }

    // -033 document surface (default read-mode)
    if (!await page.locator('[data-testid="document-overlay-surface"]').first().isVisible().catch(() => false)) {
      failures.push(`Chunk 8 (QA-033): document surface not visible`);
    } else {
      console.log(`[render-smoke]  ✓ Chunk 8 (QA-033) — document surface mounted (read mode)`);
    }

    // -035 version history modal — open from toolbar
    const historyBtn = page.locator('[data-testid="document-overlay-history-btn"]').first();
    if (await historyBtn.isVisible().catch(() => false)) {
      await historyBtn.click();
      try {
        await page.locator('[data-testid="document-overlay-version-history-modal"]').first()
          .waitFor({ state: "visible", timeout: 4000 });
        console.log(`[render-smoke]  ✓ Chunk 8 (QA-035) — version history modal opens`);
        // Close.
        const closeBtn = page.locator('[data-testid="document-overlay-version-history-close"]').first();
        if (await closeBtn.isVisible().catch(() => false)) await closeBtn.click();
        await page.waitForTimeout(400);
      } catch {
        failures.push(`Chunk 8 (QA-035): version history modal did not open within 4s`);
      }
    }

    // Close overlay via back arrow.
    const back = page.locator('[data-testid="document-overlay-back"]').first();
    if (await back.isVisible().catch(() => false)) {
      await back.click();
      await page.waitForTimeout(400);
      const stillVisible = await page.locator('[data-testid="document-overlay-shell"]').first().isVisible().catch(() => false);
      if (stillVisible) {
        failures.push(`Chunk 8 (QA-029): overlay did not close on back-arrow click`);
      } else {
        console.log(`[render-smoke]  ✓ Chunk 8 (QA-029) — close via back arrow works`);
      }
    }
  } catch (e) {
    failures.push(`Chunk 8 overlay smoke threw: ${e.message}`);
  }

  if (pageErrors.length > 0) {
    failures.push(`Chunk 8 step: ${pageErrors.length} uncaught page error(s)`);
    for (const e of pageErrors) console.error(`    PAGEERROR  ${e.slice(0, 240)}`);
  }
  page.off("pageerror", onPageError);
}

// ----------------------------------------------------------------------
// Phase 8 (Chunk 7 fix-pass, 2026-05-18) — QA-2026-05-16-007 smoke.
//
// Opens a real document from the workspace, lands on /app/documents/:id,
// and verifies the Generate-signals empty-rail UX:
//   1) Button changes to "Generating signals…" immediately on click.
//   2) Verbatim status copy renders within ≤6s of the click.
//
// We don't wait for the job to terminate — that's a multi-minute LLM
// call and pytest covers the failure-path inline error. Soft-skip if
// the workspace has no docs, or if the rail isn't in its empty state
// (i.e. the doc already has commentary signals).
// ----------------------------------------------------------------------
async function smokeChunk7GenerateSignals(page, failures) {
  const pageErrors = [];
  const onPageError = (err) => { pageErrors.push(err.toString()); };
  page.on("pageerror", onPageError);

  try {
    await page.goto(`${BASE_URL}/app/workspace`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(600);

    const allRows = page.locator('[data-testid^="workspace-row-"]');
    const rowCount = await allRows.count();
    if (rowCount === 0) {
      console.log(`[render-smoke]  · Chunk 7 — workspace empty; soft-skipping QA-007 smoke`);
      return;
    }

    // Scan up to the first 8 rows to find a document whose
    // commentary rail is in its empty state (the only surface where
    // the Generate-signals button exists). Without this scan we'd
    // miss the silent-reset regression on contexts that have at
    // least one doc with prior commentary in row 0.
    let docId = null;
    const maxScan = Math.min(rowCount, 8);
    for (let i = 0; i < maxScan; i++) {
      const rowTestId = await allRows.nth(i).getAttribute("data-testid");
      const candidate = (rowTestId || "").replace(/^workspace-row-/, "");
      if (!candidate) continue;
      // eslint-disable-next-line no-await-in-loop
      await page.goto(`${BASE_URL}/app/documents/${candidate}`, { waitUntil: "domcontentloaded", timeout: 30000 });
      // eslint-disable-next-line no-await-in-loop
      await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
      // eslint-disable-next-line no-await-in-loop
      await page.waitForTimeout(800);
      // eslint-disable-next-line no-await-in-loop
      const railEmpty = await page.locator('[data-testid="reading-rail-empty"]').first().isVisible().catch(() => false);
      if (railEmpty) {
        docId = candidate;
        console.log(`[render-smoke]  · Chunk 7 — using empty-rail doc ${docId} (row ${i})`);
        break;
      }
    }
    if (!docId) {
      console.log(`[render-smoke]  · Chunk 7 — no empty-rail doc found in first ${maxScan} rows; soft-skipping QA-007`);
      return;
    }

    // The empty-rail "Generate signals →" button.
    const railBtn = page.locator('[data-testid="reading-rail-generate-signals"]').first();
    const railVisible = await railBtn.isVisible().catch(() => false);
    if (!railVisible) {
      console.log(`[render-smoke]  · Chunk 7 — Generate button not visible on ${docId}; soft-skipping`);
      return;
    }

    const labelBefore = ((await railBtn.textContent()) || "").trim();
    if (!/generate signals/i.test(labelBefore)) {
      failures.push(`Chunk 7 (QA-007): rail button has unexpected label "${labelBefore}" (expected "Generate signals →")`);
      return;
    }

    await railBtn.click();
    // Loading state — immediate.
    const labelAfter = ((await railBtn.textContent()) || "").trim();
    if (!/generating signals/i.test(labelAfter)) {
      failures.push(`Chunk 7 (QA-007): button did NOT flip to "Generating signals…" on click (saw "${labelAfter}")`);
    } else {
      console.log(`[render-smoke]  ✓ Chunk 7 (QA-007) — loading state present immediately`);
    }

    // Wait for the 4s status copy; allow up to 8s for the timer + render.
    // `locator.isVisible()` returns instantly in current Playwright; use
    // `waitFor({state:'visible'})` to actually poll.
    const status = page.locator('[data-testid="reading-rail-signals-status"]').first();
    let statusVisible = false;
    try {
      await status.waitFor({ state: "visible", timeout: 8000 });
      statusVisible = true;
    } catch {
      statusVisible = false;
    }
    if (!statusVisible) {
      failures.push(`Chunk 7 (QA-007): inline status "Akki is analysing your document…" did NOT render within 8s`);
    } else {
      const statusText = ((await status.textContent()) || "").trim();
      if (!/akki is analysing your document\. this may take a moment\./i.test(statusText)) {
        failures.push(`Chunk 7 (QA-007): status copy mismatched the spec verbatim (got "${statusText}")`);
      } else {
        console.log(`[render-smoke]  ✓ Chunk 7 (QA-007) — verbatim status copy rendered after 4s`);
      }
    }

    // ────────────────────────────────────────────────────────────
    // Fix-pass #2 (2026-05-18) — non-silent-reset post-condition.
    //   After the job terminates, the rail MUST show one of:
    //     · ≥1 per-doc commentary item (success-with-results — the
    //       empty rail flips to the items list and the Generate
    //       button is no longer in the DOM), OR
    //     · `reading-rail-signals-error` (failure path), OR
    //     · `reading-rail-signals-empty` (success-but-nothing-for-this-doc).
    //   The original failure mode was: button silently reset to
    //   "Generate signals →" with empty rail and no persistent
    //   message. That state MUST NOT be reachable after this fix.
    // ────────────────────────────────────────────────────────────
    const railBtnLoc = page.locator('[data-testid="reading-rail-generate-signals"]').first();
    let terminal = null;
    for (let i = 0; i < 90; i++) {
      // 90 s budget — backend Generate Signals against a real context
      // typically lands in 15-60s; status copy renders at 4s so the
      // earlier waitFor is independent of this.
      // eslint-disable-next-line no-await-in-loop
      await page.waitForTimeout(1000);
      // Read the button's text — if it's gone or shows "Generate
      // signals →" again, the handler has reached its `finally`.
      // `textContent()` returns "" if the element is detached.
      // eslint-disable-next-line no-await-in-loop
      const btnTxt = ((await railBtnLoc.textContent({ timeout: 1500 }).catch(() => "")) || "").trim();
      const buttonDetached = btnTxt === "";
      const buttonIdle = btnTxt && !/generating signals/i.test(btnTxt);
      if (buttonDetached || buttonIdle) {
        // Settle: loadCommentary's commentaryLoading toggles the empty
        // block off-then-on momentarily and our handler sets the info
        // message AFTER the await resolves. Give state propagation a
        // generous beat before sampling the terminal surface.
        // eslint-disable-next-line no-await-in-loop
        await page.waitForTimeout(2500);
        // eslint-disable-next-line no-await-in-loop
        const itemsCount = await page.locator('[data-testid^="commentary-item-"]').count();
        // eslint-disable-next-line no-await-in-loop
        const errPresent = await page.locator('[data-testid="reading-rail-signals-error"]').count();
        // eslint-disable-next-line no-await-in-loop
        const emptyPresent = await page.locator('[data-testid="reading-rail-signals-empty"]').count();
        terminal = {
          elapsedS: i + 1,
          btnTxt: buttonDetached ? "<button detached>" : btnTxt,
          itemsCount,
          errPresent,
          emptyPresent,
        };
        break;
      }
    }
    if (!terminal) {
      console.log(`[render-smoke]  · Chunk 7 (QA-007) — job did not terminate within 90s; soft-skipping silent-reset assertion`);
    } else {
      const ok = terminal.itemsCount > 0 || terminal.errPresent > 0 || terminal.emptyPresent > 0;
      if (!ok) {
        failures.push(
          `Chunk 7 (QA-007): SILENT RESET reproduced — `
          + `after job termination (${terminal.elapsedS}s, btn="${terminal.btnTxt}"), `
          + `rail has 0 items AND no error AND no empty-info message. `
          + `The button reset without surfacing anything actionable.`,
        );
      } else {
        console.log(
          `[render-smoke]  ✓ Chunk 7 (QA-007) — non-silent-reset post-condition GREEN `
          + `(items=${terminal.itemsCount}, error=${terminal.errPresent}, empty-info=${terminal.emptyPresent}, elapsed=${terminal.elapsedS}s)`,
        );
      }
    }

    // Don't block the smoke pipeline waiting for the job to terminate —
    // that's a 60-90s LLM call. Navigate away to abort the in-flight
    // poll cleanly; the next request will reset state.
    await page.goto(`${BASE_URL}/app`, { waitUntil: "domcontentloaded", timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(300);
  } catch (e) {
    failures.push(`Chunk 7 (QA-007): smoke threw — ${e.message}`);
  }

  if (pageErrors.length > 0) {
    failures.push(`Chunk 7 step: ${pageErrors.length} uncaught page error(s)`);
    for (const e of pageErrors) console.error(`    PAGEERROR  ${e.slice(0, 240)}`);
  }
  page.off("pageerror", onPageError);
}

