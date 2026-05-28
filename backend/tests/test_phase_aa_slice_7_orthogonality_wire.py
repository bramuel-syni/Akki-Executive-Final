"""
Phase AA-slice-7 (2026-05-27) — Orthogonality wire-test.

Mirror of Z-slice-6 but for the full upload → extract →
tasks_initiatives → Monitor surface chain. The Z-6 test locks the
DOCUMENT axis (uploaded doc surfaces in both Work Studio category
tab AND /app/documents origin tab). The AA-7 test locks the TASK
axis: a single document uploaded with `category=report` +
`extract_tasks=True` MUST surface its extracted tasks_initiatives
rows on the Monitor Tasks tab — without polluting the Goals tab.

Test flow (live preview pod, mocked LLM):

  1. Login as admin@akki.ai → bind to active context from
     sessionStorage.
  2. Mock `services.tasks_initiatives.extraction.call_llm` to
     return a canned 2-task payload (avoids real LLM round-trip
     during CI).
  3. Use the Z-slice-5 upload modal flow:
       a. Open `/app/documents`, click `+ Add a document`.
       b. Pick category=report.
       c. Attach a marker .txt file.
       d. Tick the AA-3 "Extract tasks" checkbox.
       e. Submit.
  4. Wait for the background extraction to complete.
  5. Navigate to `/app/monitor?tab=tasks`.
  6. Assert the two seeded tasks surface in `tasks-listing`.
  7. Switch to Goals tab → assert the seeded TASKS do NOT appear
     in the strategic goals listing (no cross-collection leakage).
  8. Cleanup: delete the marker doc + tasks + extraction logs.

NOTE on mocking: the Playwright browser can't import Python
modules, so we mock `call_llm` indirectly by seeding tasks
directly via Mongo right after the upload returns the new doc_id
— skipping the LLM round-trip entirely. The orthogonality lock is
on the AA-1 collection wiring (correct context_id +
source_document_id + extracted_by="llm"), not on the LLM service
itself (which is covered by AA-2's 21 unit tests).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest


pytestmark = pytest.mark.runtime_playwright

REPO = Path(__file__).resolve().parent.parent.parent


def _frontend_url() -> str:
    env = REPO / "frontend" / ".env"
    for ln in env.read_text("utf-8").splitlines():
        if ln.startswith("REACT_APP_BACKEND_URL="):
            return ln.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not in frontend/.env")


try:
    from playwright.async_api import async_playwright  # noqa: F401
    HAVE_PW = True
except Exception:  # noqa: BLE001
    HAVE_PW = False


ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASSWORD = "AkkiAdmin2026!"


async def _simulate_extraction(cid: str, doc_id: str, marker: str) -> tuple[str, str]:
    """Stand-in for the real Sonnet 4.5 extraction. Writes two
    `tasks_initiatives` rows with `extracted_by="llm"` +
    `source_document_id=doc_id` so the Monitor surface treats them
    exactly the way real LLM output would arrive.
    """
    from motor.motor_asyncio import AsyncIOMotorClient

    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        db = c[os.environ["DB_NAME"]]
        now_iso = datetime.now(timezone.utc).isoformat()
        t1_title = f"{marker} — Refactor RBAC"
        t2_title = f"{marker} — Launch CRM POC"
        for title, owner in ((t1_title, "CTO"), (t2_title, "CRO")):
            await db.tasks_initiatives.insert_one({
                "id": uuid.uuid4().hex, "context_id": cid,
                "title": title, "body": "AA-7 wire test seeded row",
                "category": "operations", "owner_role": owner,
                "parent_objective_id": None, "status": "on_track",
                "performance_score": 50, "probability_score": 70,
                "last_reassessed_at": now_iso,
                "source_document_id": doc_id,
                "extracted_by": "llm", "status_active": True,
                "created_at": now_iso, "updated_at": now_iso,
            })
        return t1_title, t2_title
    finally:
        c.close()


async def _cleanup(cid: str, marker: str) -> None:
    from motor.motor_asyncio import AsyncIOMotorClient
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        db = c[os.environ["DB_NAME"]]
        await db.tasks_initiatives.delete_many(
            {"context_id": cid, "title": {"$regex": marker}},
        )
        await db.documents.delete_many(
            {"context_id": cid, "name": {"$regex": marker}},
        )
        await db.strategic_goals.delete_many(
            {"context_id": cid, "title": {"$regex": marker}},
        )
    finally:
        c.close()


@pytest.mark.skipif(not HAVE_PW, reason="playwright not installed")
@pytest.mark.asyncio
async def test_aa7_uploaded_report_extracts_to_monitor_tasks_tab():
    """End-to-end DOM round-trip: upload a report → extract →
    tasks surface on Monitor Tasks tab + don't pollute Goals tab.
    """
    from playwright.async_api import async_playwright

    base = _frontend_url()
    marker = f"AA7-{uuid.uuid4().hex[:8]}"
    tmpfile = Path(f"/tmp/{marker}.txt")
    tmpfile.write_text(
        f"{marker} body — AA-slice-7 orthogonality wire-test fixture. "
        "Should extract tasks via the AA-2 service. " * 20,
        encoding="utf-8",
    )

    cid = None
    t1_title = t2_title = None
    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as e:
                tmpfile.unlink(missing_ok=True)
                pytest.skip(f"chromium not available: {e}"[:200])

            ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
            page = await ctx.new_page()
            try:
                # 1. Login.
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
                await page.wait_for_timeout(2500)

                cid = await page.evaluate("""() => sessionStorage.getItem('akki_active_context_id')""")
                if not cid:
                    await page.goto(f"{base}/app/", wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_timeout(2500)
                    cid = await page.evaluate("""() => sessionStorage.getItem('akki_active_context_id')""")
                if not cid:
                    pytest.skip("AuthContext didn't populate active_context_id")

                # 2. Use the upload modal to attach the doc. We rely
                #    on the doc-create endpoint to actually persist
                #    the row; the LLM extraction is simulated via
                #    direct Mongo writes below.
                await page.goto(f"{base}/app/documents",
                                wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2500)
                await page.locator('[data-testid="documents-page-add-document-btn"]').click(timeout=5000)
                await page.wait_for_timeout(1500)
                await page.locator('[data-testid="upload-category-select"]').select_option("report")
                await page.wait_for_timeout(400)
                await page.locator('[data-testid="upload-file-input"]').set_input_files(str(tmpfile))
                await page.wait_for_timeout(800)
                # The "Extract tasks" checkbox should already be ON
                # by default for category=report. Verify.
                checked = await page.locator(
                    '[data-testid="upload-extract-tasks-checkbox"]'
                ).is_checked()
                assert checked, (
                    "AA-3 default — `category=report` must auto-check "
                    "the 'Extract tasks' checkbox."
                )
                await page.locator('[data-testid="upload-submit-btn"]').click()
                # Wait for modal to close + a moment for the upload to settle.
                await page.locator('[data-testid="upload-modal"]').wait_for(
                    state="hidden", timeout=15000,
                )
                await page.wait_for_timeout(2500)

                # 3. Pull the newly-created doc_id so we can wire it
                #    into the simulated extraction.
                doc_info = await page.evaluate(f"""async () => {{
                  const xac = sessionStorage.getItem('akki_active_context_id');
                  const r = await fetch('/api/contexts/' + xac + '/documents?origin=upload&limit=50', {{
                    credentials: 'include',
                  }});
                  if (!r.ok) return null;
                  const docs = await r.json();
                  return (docs || []).find(d => d.name && d.name.includes({marker!r})) || null;
                }}""")
                assert doc_info and doc_info.get("id"), (
                    "Uploaded report doc not found via origin=upload listing."
                )

                # 4. Simulate the LLM-extraction outcome (the AA-2
                #    service is unit-tested separately; here we lock
                #    the wiring between persisted tasks_initiatives
                #    rows and the Monitor surface).
                t1_title, t2_title = await _simulate_extraction(
                    cid, doc_info["id"], marker,
                )

                # 5. Navigate to Monitor Tasks tab + verify the two
                #    seeded rows surface.
                await page.goto(f"{base}/app/monitor?tab=tasks",
                                wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(4500)
                listing = page.locator('[data-testid="tasks-listing"]')
                await listing.wait_for(state="visible", timeout=10000)
                t1_present = await listing.locator(f'text={t1_title}').count()
                t2_present = await listing.locator(f'text={t2_title}').count()
                assert t1_present >= 1, (
                    f"AA-7 wire-test: seeded LLM task {t1_title!r} did NOT "
                    f"surface in Monitor Tasks tab. Wiring broken between "
                    f"tasks_initiatives collection and TasksInitiativesPanel."
                )
                assert t2_present >= 1, (
                    f"AA-7 wire-test: seeded LLM task {t2_title!r} did NOT "
                    f"surface in Monitor Tasks tab."
                )

                # 6. Provenance chip lights up for these LLM rows.
                chip_count = await page.evaluate(f"""() => {{
                  const rows = Array.from(document.querySelectorAll('[data-testid^="task-initiative-"]'));
                  const ours = rows.filter(r => r.textContent.includes({marker!r}));
                  return ours.filter(r => r.querySelector('[data-testid^="task-card-provenance-"]')).length;
                }}""")
                assert chip_count == 2, (
                    f"AA-7: both seeded LLM rows must render the provenance "
                    f"chip; got {chip_count}/2."
                )

                # 7. Switch to Goals tab — the AA-7 lock says these
                #    TASKS rows MUST NOT leak into the strategic
                #    goals listing.
                await page.locator('[data-testid="monitor-tab-goals"]').click()
                await page.wait_for_timeout(3500)
                goals_body = page.locator('[data-testid="monitor-tab-content-goals"]')
                await goals_body.wait_for(state="visible", timeout=8000)
                leakage = await goals_body.locator(f'text={t1_title}').count()
                assert leakage == 0, (
                    f"AA-7 ORTHOGONALITY BROKEN — seeded tasks_initiatives "
                    f"row {t1_title!r} leaked into the Goals tab "
                    f"(StrategicGoalsPanel). Tasks and Goals must stay in "
                    f"separate collections."
                )
                leakage2 = await goals_body.locator(f'text={t2_title}').count()
                assert leakage2 == 0, (
                    f"AA-7 ORTHOGONALITY BROKEN — task {t2_title!r} leaked."
                )

            finally:
                await browser.close()
    finally:
        if cid:
            await _cleanup(cid, marker)
        tmpfile.unlink(missing_ok=True)
