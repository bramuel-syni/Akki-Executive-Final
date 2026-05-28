"""
Phase AA-slice-4 (2026-05-27 redispatch) — Monitor surface
Playwright DOM + bounding-rect lock.

Distinct from the source-strict `test_phase_aa_slice_4_monitor.py`
already shipped (which scans the .jsx for required testids /
literals). This file probes the LIVE DOM at 1280 / 1024 / 820:

  • Capsule-tab row renders both tabs WITHOUT flex-wrap
    (Recurrence #4 lock): top-Y of both tab buttons must match
    within 2px at every viewport.
  • Owner-capsule row + status-filter row also enforce no
    wrap (same top-Y test).
  • Default tab = "goals".
  • Click "Tasks" tab → URL gains `?tab=tasks` + tasks panel
    mounts.
  • Owner capsules render ONLY for owner_roles present in the
    fetched listing (seed-aware probe).
  • Provenance chip presence is conditional on `extracted_by`:
    seeded LLM row → chip present; manual row → chip absent.
  • Probability bar fill uses `var(--accent)` brand-purple
    token (computed background contains the accent rgb after
    Tailwind compile).
  • No console errors during the run.

Marked `runtime_playwright` so fast CI can skip it.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest


pytestmark = pytest.mark.runtime_playwright

REPO = Path(__file__).resolve().parent.parent.parent

try:
    from playwright.async_api import async_playwright  # noqa: F401
    HAVE_PW = True
except Exception:  # noqa: BLE001
    HAVE_PW = False


def _frontend_url() -> str:
    env = REPO / "frontend" / ".env"
    for ln in env.read_text("utf-8").splitlines():
        if ln.startswith("REACT_APP_BACKEND_URL="):
            return ln.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not in frontend/.env")


ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASSWORD = "AkkiAdmin2026!"

VIEWPORTS = (1280, 1024, 820)


async def _seed_three_tasks(cid: str) -> tuple[str, str, str]:
    """Seed three tasks_initiatives rows with distinct provenance:

      • A1 — LLM-extracted, owner=CFO, source_document_id set.
      • A2 — Manual, owner=CEO.
      • A3 — Manual, owner_role=None (drives the "Unassigned"
        capsule).
    """
    from motor.motor_asyncio import AsyncIOMotorClient

    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        db = c[os.environ["DB_NAME"]]
        # Seed an owning document so the LLM row's provenance chip
        # can resolve a name.
        doc_id = f"aa4dom-doc-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.documents.insert_one({
            "id": doc_id, "context_id": cid, "name": "AA4 Doc",
            "extracted_text": "x" * 80, "origin": "upload",
            "category": "report", "status": "extracted",
            "created_at": now_iso, "updated_at": now_iso,
        })
        ids = []
        seeds = [
            {"title": f"AA4-DOM A1 LLM {uuid.uuid4().hex[:6]}", "owner_role": "CFO",
             "extracted_by": "llm", "source_document_id": doc_id,
             "probability_score": 70},
            {"title": f"AA4-DOM A2 Manual {uuid.uuid4().hex[:6]}", "owner_role": "CEO",
             "extracted_by": "manual", "source_document_id": None,
             "probability_score": 30},
            {"title": f"AA4-DOM A3 Unassigned {uuid.uuid4().hex[:6]}", "owner_role": None,
             "extracted_by": "manual", "source_document_id": None,
             "probability_score": 50},
        ]
        for s in seeds:
            tid = uuid.uuid4().hex
            ids.append((tid, s["title"]))
            await db.tasks_initiatives.insert_one({
                "id": tid, "context_id": cid,
                "title": s["title"], "body": "AA4 seeded row",
                "category": "operations", "owner_role": s["owner_role"],
                "parent_objective_id": None, "status": "on_track",
                "performance_score": 50,
                "probability_score": s["probability_score"],
                "last_reassessed_at": now_iso,
                "source_document_id": s["source_document_id"],
                "extracted_by": s["extracted_by"],
                "status_active": True,
                "created_at": now_iso, "updated_at": now_iso,
            })
        return ids[0][1], ids[1][1], ids[2][1]
    finally:
        c.close()


async def _cleanup_seeds(cid: str, titles: tuple[str, ...]) -> None:
    from motor.motor_asyncio import AsyncIOMotorClient
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        db = c[os.environ["DB_NAME"]]
        await db.tasks_initiatives.delete_many({"context_id": cid, "title": {"$in": list(titles)}})
        await db.documents.delete_many({"context_id": cid, "name": "AA4 Doc"})
    finally:
        c.close()


async def _admin_default_context_id() -> str:
    """Return the context the admin lands in by default — which is
    the `TEST_SeededNedCo` context per the cohort seed. The first-
    active-membership heuristic is unreliable when admin sits on
    multiple contexts (and they do — admin is a superadmin); the
    UI restores last-active which differs from Mongo doc order.
    """
    from motor.motor_asyncio import AsyncIOMotorClient
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        db = c[os.environ["DB_NAME"]]
        # First try the seeded NED test context by name.
        ctx = await db.contexts.find_one(
            {"name": "TEST_SeededNedCo"}, {"_id": 0, "id": 1},
        )
        if ctx:
            return ctx["id"]
        # Fallback: any active membership for the admin.
        acct = await db.accounts.find_one({"email": ADMIN_EMAIL}, {"_id": 0, "id": 1})
        if not acct:
            raise RuntimeError(f"No admin account {ADMIN_EMAIL!r} in DB")
        m = await db.memberships.find_one(
            {"account_id": acct["id"], "status": "active"},
            {"_id": 0, "context_id": 1},
        )
        if not m:
            raise RuntimeError(f"No active membership for admin {ADMIN_EMAIL}")
        return m["context_id"]
    finally:
        c.close()


@pytest.mark.skipif(not HAVE_PW, reason="playwright not installed")
@pytest.mark.asyncio
async def test_aa4_monitor_dom_multi_viewport_no_flex_wrap_and_owner_capsules():
    """Live DOM probe at 1280 / 1024 / 820 — Recurrence #4 lock +
    AA-slice-4 redispatch acceptance criteria.

    Seed strategy: login first, *then* read the admin's actually-
    active context from localStorage, *then* seed three rows into
    THAT context. Guarantees the seed and the browser session see
    the same context_id (the original `_admin_default_context_id`
    heuristic picked a different context than AuthContext's
    first-from-API fallback).
    """
    from playwright.async_api import async_playwright

    base = _frontend_url()
    llm_title = manual_title = unassigned_title = None
    seeded_cid = None

    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as e:
                pytest.skip(f"chromium not available: {e}"[:200])

            ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
            page = await ctx.new_page()

            console_errs: list[str] = []
            page.on("console", lambda msg: msg.type == "error" and console_errs.append(msg.text))

            try:
                # ── Login first so AuthContext picks the active ctx ──
                await page.goto(f"{base}/sign-in", wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(1500)
                try:
                    await page.locator('[data-testid="signin-email-input"]').first.fill(ADMIN_EMAIL, timeout=4000)
                except Exception:
                    await page.locator("text=Sign in").first.click(timeout=4000)
                    await page.wait_for_timeout(1500)
                    await page.locator('[data-testid="signin-email-input"]').first.fill(ADMIN_EMAIL)
                await page.locator('[data-testid="signin-password-input"]').first.fill(ADMIN_PASSWORD)
                await page.locator('[data-testid="signin-submit-btn"]').first.click()
                await page.wait_for_url("**/app**", timeout=20000)
                await page.wait_for_timeout(2500)  # let AuthContext settle

                # Read the active context that AuthContext picked.
                # Phase A note: per-tab active context lives in
                # SESSIONSTORAGE (not localStorage) — see
                # `frontend/src/lib/api.js::ACTIVE_CONTEXT_STORAGE_KEY`.
                seeded_cid = await page.evaluate("""() => {
                  return sessionStorage.getItem('akki_active_context_id');
                }""")
                # Fallback — if sessionStorage isn't populated yet,
                # force a brief navigation that triggers AuthContext's
                # bootstrap.
                if not seeded_cid:
                    await page.goto(f"{base}/app/", wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_timeout(3000)
                    seeded_cid = await page.evaluate("""() => {
                      return sessionStorage.getItem('akki_active_context_id');
                    }""")
                if not seeded_cid:
                    pytest.skip("AuthContext didn't populate active_context_id; "
                                "preview pod admin session is in an unexpected state.")

                # NOW seed three rows into the same context the browser is on.
                llm_title, manual_title, unassigned_title = await _seed_three_tasks(seeded_cid)

                # ── Navigate to Monitor (tasks tab) ──
                await page.goto(f"{base}/app/monitor?tab=tasks",
                                wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(4500)

                # ── Multi-viewport: capsule-tab row + owner + status
                #    rows MUST NOT wrap (top-Y matches within 2px). ──
                for vw in VIEWPORTS:
                    await page.set_viewport_size({"width": vw, "height": 900})
                    await page.wait_for_timeout(1000)
                    probe = await page.evaluate("""() => {
                      const out = {};
                      const top = (sel) => {
                        const el = document.querySelector(sel);
                        return el ? Math.round(el.getBoundingClientRect().top) : null;
                      };
                      const childTops = (rowSel) => {
                        const row = document.querySelector(rowSel);
                        if (!row) return [];
                        return Array.from(row.children).map(c =>
                          Math.round(c.getBoundingClientRect().top));
                      };
                      out.capsule_tabs_top = top('[data-testid="monitor-capsule-tabs"]');
                      out.capsule_tabs_child_tops = childTops('[data-testid="monitor-capsule-tabs"]');
                      out.owner_capsules_child_tops = childTops('[data-testid="tasks-owner-capsules"]');
                      out.status_filters_child_tops = childTops('[data-testid="tasks-status-filters"]');
                      out.url_has_tab_tasks = window.location.search.includes('tab=tasks');
                      return out;
                    }""")

                    # 1. Capsule tabs: both buttons share the same top-Y.
                    ct = probe["capsule_tabs_child_tops"]
                    assert len(ct) >= 2, f"VW={vw}: capsule_tabs has fewer than 2 children"
                    spread = max(ct) - min(ct)
                    assert spread <= 2, (
                        f"VW={vw}: capsule tabs flex-wrapped — top-Y spread "
                        f"{spread}px > 2px (Recurrence #4)."
                    )

                    # 2. Owner-capsule row: ALL pills share top-Y.
                    oc = probe["owner_capsules_child_tops"]
                    assert len(oc) >= 1, f"VW={vw}: owner_capsules row missing or empty"
                    if len(oc) > 1:
                        spread = max(oc) - min(oc)
                        assert spread <= 2, (
                            f"VW={vw}: owner capsules flex-wrapped — "
                            f"top-Y spread {spread}px > 2px."
                        )

                    # 3. Status filter row: all pills share top-Y.
                    sf = probe["status_filters_child_tops"]
                    assert len(sf) >= 2, f"VW={vw}: status_filters has < 2 children"
                    spread = max(sf) - min(sf)
                    assert spread <= 2, (
                        f"VW={vw}: status filter row flex-wrapped — "
                        f"top-Y spread {spread}px > 2px."
                    )

                    assert probe["url_has_tab_tasks"] is True

                # ── Default tab = goals (fresh load with no ?tab=). ──
                await page.set_viewport_size({"width": 1280, "height": 900})
                await page.goto(f"{base}/app/monitor",
                                wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(3000)
                default_active = await page.evaluate("""() => {
                  const g = document.querySelector('[data-testid="monitor-tab-goals"]');
                  const t = document.querySelector('[data-testid="monitor-tab-tasks"]');
                  const goalsBody = document.querySelector('[data-testid="monitor-tab-content-goals"]');
                  const tasksBody = document.querySelector('[data-testid="monitor-tab-content-tasks"]');
                  return {
                    goals_active: g ? g.className.includes('text-white') : false,
                    tasks_active: t ? t.className.includes('text-white') : false,
                    goals_body_present: !!goalsBody,
                    tasks_body_present: !!tasksBody,
                  };
                }""")
                assert default_active["goals_active"] is True
                assert default_active["tasks_active"] is False
                assert default_active["goals_body_present"] is True
                assert default_active["tasks_body_present"] is False

                # ── Click Tasks tab → URL flips. ──
                await page.locator('[data-testid="monitor-tab-tasks"]').click(timeout=4000)
                await page.wait_for_timeout(2500)
                after_click = await page.evaluate("""() => {
                  return {
                    url_has_tab_tasks: window.location.search.includes('tab=tasks'),
                    tasks_body_present: !!document.querySelector('[data-testid="monitor-tab-content-tasks"]'),
                    panel_mounted: !!document.querySelector('[data-testid="tasks-initiatives-panel"]'),
                  };
                }""")
                assert after_click["url_has_tab_tasks"] is True
                assert after_click["panel_mounted"] is True

                # ── Owner capsule row reflects seeded owners. ──
                await page.wait_for_timeout(2000)
                cap_probe = await page.evaluate("""() => {
                  const all = document.querySelector('[data-testid="tasks-owner-capsule-all"]');
                  const cfo = document.querySelector('[data-testid="tasks-owner-capsule-CFO"]');
                  const ceo = document.querySelector('[data-testid="tasks-owner-capsule-CEO"]');
                  const unassigned = document.querySelector('[data-testid="tasks-owner-capsule-unassigned"]');
                  return {
                    all_present: !!all,
                    cfo_present: !!cfo,
                    ceo_present: !!ceo,
                    unassigned_present: !!unassigned,
                  };
                }""")
                assert cap_probe["all_present"] is True, (
                    "Owner-capsule row must render an 'All owners' capsule."
                )
                assert cap_probe["cfo_present"] is True, (
                    "Owner-capsule row must surface 'CFO' since the seeded LLM row "
                    "uses owner_role=CFO."
                )
                assert cap_probe["ceo_present"] is True, (
                    "Owner-capsule row must surface 'CEO' since one seeded row uses it."
                )
                assert cap_probe["unassigned_present"] is True, (
                    "An 'Unassigned' capsule must surface when at least one row has "
                    "owner_role=null."
                )

                # ── Provenance chip presence is conditional on extracted_by. ──
                chip_probe = await page.evaluate(f"""() => {{
                  const rows = Array.from(document.querySelectorAll('[data-testid^="task-initiative-"]'));
                  const llmRow = rows.find(r => r.textContent.includes({llm_title!r}));
                  const manualRow = rows.find(r => r.textContent.includes({manual_title!r}));
                  return {{
                    llm_row_present: !!llmRow,
                    llm_row_chip: llmRow ? !!llmRow.querySelector('[data-testid^="task-card-provenance-"]') : null,
                    manual_row_present: !!manualRow,
                    manual_row_chip: manualRow ? !!manualRow.querySelector('[data-testid^="task-card-provenance-"]') : null,
                  }};
                }}""")
                assert chip_probe["llm_row_present"], "Seeded LLM row not found in listing."
                assert chip_probe["llm_row_chip"] is True, (
                    "Provenance chip MUST render on extracted_by='llm' rows."
                )
                assert chip_probe["manual_row_present"], "Seeded manual row not found in listing."
                assert chip_probe["manual_row_chip"] is False, (
                    "Provenance chip MUST be absent on extracted_by='manual' rows."
                )

                # ── Owner-capsule click filters listing (server query
                #    + client re-render). ──
                await page.locator('[data-testid="tasks-owner-capsule-CFO"]').click()
                await page.wait_for_timeout(2000)
                after_cfo = await page.evaluate(f"""() => {{
                  const rows = Array.from(document.querySelectorAll('[data-testid^="task-initiative-"]'));
                  return {{
                    row_count: rows.length,
                    has_llm: rows.some(r => r.textContent.includes({llm_title!r})),
                    has_manual: rows.some(r => r.textContent.includes({manual_title!r})),
                    has_unassigned: rows.some(r => r.textContent.includes({unassigned_title!r})),
                  }};
                }}""")
                assert after_cfo["has_llm"], (
                    "After clicking the CFO capsule, the seeded CFO-owned LLM "
                    "row must still surface."
                )
                assert not after_cfo["has_manual"], (
                    "After clicking the CFO capsule, the seeded CEO-owned row "
                    "must be filtered out."
                )
                assert not after_cfo["has_unassigned"], (
                    "After clicking the CFO capsule, the seeded unassigned "
                    "row must be filtered out."
                )

                # ── Probability bar fill uses brand-purple token. ──
                await page.locator('[data-testid="tasks-owner-capsule-CFO"]').click()  # toggle off
                await page.wait_for_timeout(1500)
                bar_probe = await page.evaluate("""() => {
                  // ScoreBar structure:
                  //   wrap [data-testid] (flex-col w-28)
                  //     ├ label row (flex)
                  //     └ track (h-1 bg-slate-100)
                  //         └ fill (h-full bg-[brand-purple])  ← target
                  const wrap = document.querySelector('[data-testid^="task-card-prob-bar-"]');
                  if (!wrap) return { wrap_present: false };
                  const track = wrap.querySelector('.bg-slate-100');
                  if (!track) return { wrap_present: true, track_present: false };
                  const fill = track.firstElementChild;
                  if (!fill) return { wrap_present: true, track_present: true, fill_present: false };
                  const cs = getComputedStyle(fill);
                  return {
                    wrap_present: true,
                    track_present: true,
                    fill_present: true,
                    bg: cs.backgroundColor,
                    width: fill.style.width,
                  };
                }""")
                assert bar_probe.get("wrap_present"), "Probability bar wrap missing."
                assert bar_probe.get("track_present"), "Probability bar track missing."
                assert bar_probe.get("fill_present"), "Probability bar fill missing."
                # The fill carries Tailwind's `bg-[color:var(--ned-purple)]` which
                # resolves to a non-transparent computed colour. We don't lock the
                # exact hex (AA-slice-6 will tune it) but we refuse
                # `rgba(0, 0, 0, 0)` / `transparent`.
                bg = (bar_probe.get("bg") or "").lower()
                assert bg and "rgba(0, 0, 0, 0)" not in bg and bg != "transparent", (
                    f"Probability bar fill must carry a non-transparent brand "
                    f"colour; got bg={bg!r}."
                )

                # ── Zero NEW console errors during the run. Existing
                #    background-polling 401/503 noise (auth bootstrap
                #    + Citizen Digital RSS 503 — filed as separate
                #    rewire in sequence) is filtered. ──
                noise_patterns = (
                    "ResizeObserver loop",
                    "Hydration",
                    "Strict Mode",
                    "React Router Future Flag",
                    "Failed to load resource: the server responded with a status of 401",
                    "Failed to load resource: the server responded with a status of 503",
                )
                real_errs = [e for e in console_errs if not any(p in e for p in noise_patterns)]
                assert not real_errs, (
                    f"Console errors during run: {real_errs!r}"
                )
            finally:
                await browser.close()
    finally:
        if seeded_cid and llm_title:
            await _cleanup_seeds(seeded_cid, (llm_title, manual_title, unassigned_title))
