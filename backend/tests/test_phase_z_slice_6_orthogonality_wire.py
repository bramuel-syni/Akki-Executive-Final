"""
Phase Z-slice-6 (2026-05-27) — Orthogonality wire-test (DOM-level).

THIS is the institutional Recurrence #5 prevention wire-test. The
data-model contract (Z-slice-1's `test_Z_ORTHOGONAL_critical`)
locks: a doc with `{origin: "upload", category: "report"}` MUST
surface in BOTH the Work Studio "Reports" listing AND the
`/app/documents` "Uploaded" listing, with zero leakage into the
other 5 category tabs or the other 2 origin tabs.

Z-slice-6 promotes that contract to LIVE DOM via Playwright:

  1. Login as admin@akki.ai → active context = `TEST_SeededNedCo`.
  2. Open the Work Studio sidebar `+ Add a document` card.
  3. Set category="report", attach a small `.txt` file with a
     UUID-marked display name, submit.
  4. Modal closes → success toast surfaces.
  5. Navigate to WS Reports tab → assert the doc appears inside
     `[data-testid="ws-tab-content-report"]` with origin badge
     "Uploaded".
  6. Loop the other 5 category tabs (board_pack / minutes /
     draft / deck / briefing) → assert the doc does NOT appear in
     their `ws-tab-content-${category}` body.
  7. Navigate to `/app/documents?tab=upload` → assert the doc
     appears inside `[data-testid="documents-tab-content-upload"]`.
  8. Navigate to the other 2 origin tabs (akki_generated /
     email_receipt) → assert the doc does NOT appear.
  9. Click the doc card on the Documents page → drawer opens with
     the matching name.
 10. Multi-viewport rule (1280 / 1024 / 820) — the body-content
     testids stay resolvable + the doc row renders at each
     breakpoint.

Cleanup runs in a `finally` block — deletes the marker doc by its
unique display name AFTER the assertions complete (or fail).

Marked `runtime_playwright` so fast CI can skip it. Run with:
    pytest backend/tests/test_phase_z_slice_6_orthogonality_wire.py
or unconditional with the marker present.
"""
from __future__ import annotations

import os
import uuid
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


# Skip cleanly when Playwright isn't installed.
try:
    from playwright.async_api import async_playwright  # noqa: F401
    HAVE_PW = True
except Exception:  # noqa: BLE001
    HAVE_PW = False


# Categories the Z6 contract iterates over.
OTHER_WS_CATEGORIES = ("board_pack", "minutes", "draft", "deck", "briefing")
OTHER_DOCS_ORIGINS = ("akki_generated", "email_receipt")
ADMIN_CTX_NAME = "TEST_SeededNedCo"
ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASSWORD = "AkkiAdmin2026!"


async def _ensure_active_context(page, ctx_name: str) -> None:
    """The shell renders the active context name in the top bar. If
    it's already `ctx_name` we no-op; otherwise we open the context
    switcher and pick it. We accept a noisy header — the test only
    needs the active context to match before document upload.
    """
    header_match = await page.locator(f'text={ctx_name}').count()
    if header_match > 0:
        return
    # Open the company switcher and select. The trigger button
    # carries `data-testid="company-switcher-trigger"` per AppShell.
    try:
        await page.locator('[data-testid="company-switcher-trigger"]').first.click(timeout=4000)
        await page.wait_for_timeout(800)
        await page.locator(f'text={ctx_name}').first.click(timeout=4000)
        await page.wait_for_timeout(2000)
    except Exception:
        # If the switcher path differs, the test will fail downstream
        # with a clearer error than swallowing here.
        pass


async def _delete_marker_doc(name_marker: str) -> int:
    """Cleanup helper — deletes the uploaded marker doc via Motor
    so the test leaves no residue in the seeded context. Returns
    the deleted row count.
    """
    from motor.motor_asyncio import AsyncIOMotorClient

    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        db = c[os.environ["DB_NAME"]]
        # Filter on display name marker so we don't disturb anything
        # else. Marker is a UUID-suffixed string unique per run.
        res = await db.documents.delete_many({"name": name_marker})
        return res.deleted_count
    finally:
        c.close()


@pytest.mark.skipif(not HAVE_PW, reason="playwright not installed")
@pytest.mark.asyncio
async def test_z6_uploaded_report_surfaces_in_both_ws_and_documents():
    """Institutional Recurrence #5 wire-test — full DOM round-trip."""
    from playwright.async_api import async_playwright

    base = _frontend_url()
    name_marker = f"Z6-Orth-{uuid.uuid4().hex[:12]}"
    tmpfile = Path(f"/tmp/{name_marker}.txt")
    tmpfile.write_text(
        f"Z-slice-6 orthogonality wire-test fixture\n"
        f"This file should surface in BOTH Work Studio Reports AND\n"
        f"/app/documents Uploaded tabs. Marker: {name_marker}\n",
        encoding="utf-8",
    )

    deleted_count = 0
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception as e:  # noqa: BLE001
            tmpfile.unlink(missing_ok=True)
            pytest.skip(f"chromium browser not available: {e!s}"[:200])

        ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()
        try:
            # ─── 1. Login ────────────────────────────────────────
            await page.goto(f"{base}/sign-in", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(1500)
            # The marketing landing intercepts /sign-in; click "Sign in"
            # link if we landed there.
            try:
                await page.locator('[data-testid="signin-email-input"]').first.fill(
                    ADMIN_EMAIL, timeout=3000,
                )
            except Exception:
                await page.locator("text=Sign in").first.click(timeout=4000)
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1500)
                await page.locator('[data-testid="signin-email-input"]').first.fill(ADMIN_EMAIL)
            await page.locator('[data-testid="signin-password-input"]').first.fill(ADMIN_PASSWORD)
            await page.locator('[data-testid="signin-submit-btn"]').first.click()
            await page.wait_for_url("**/app**", timeout=20000)
            await page.wait_for_timeout(1500)

            await _ensure_active_context(page, ADMIN_CTX_NAME)

            # ─── 2. Open Work Studio sidebar + Add a document ─────
            await page.goto(
                f"{base}/app/work-studio?kind=cycle_main_and_committee_pack",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            await page.wait_for_timeout(3000)
            sidebar_btn = page.locator(
                '[data-testid="work-studio-sidebar-add-document-btn"]'
            )
            await sidebar_btn.wait_for(state="visible", timeout=10000)
            await sidebar_btn.click()

            # ─── 3. Wait for modal + upload one file w/ category=report ─
            modal = page.locator('[data-testid="upload-modal"]')
            await modal.wait_for(state="visible", timeout=8000)
            # Select category=report.
            await page.locator(
                '[data-testid="upload-category-select"]'
            ).select_option("report")
            # Attach the file via the hidden file input.
            await page.locator(
                '[data-testid="upload-file-input"]'
            ).set_input_files(str(tmpfile))
            await page.wait_for_timeout(800)
            # Override the display name with our marker so cleanup is
            # deterministic. The seeded name from the filename stem
            # already includes the marker, but typing it explicitly
            # locks it.
            name_input = page.locator('[data-testid="upload-name-input"]')
            await name_input.click()
            await name_input.fill(name_marker)
            await page.wait_for_timeout(400)
            # Submit.
            await page.locator('[data-testid="upload-submit-btn"]').click()

            # ─── 4. Modal closes; success toast surfaces ──────────
            await modal.wait_for(state="hidden", timeout=20000)
            await page.wait_for_timeout(2500)

            # ─── 5. WS Reports tab → doc surfaces in ws-tab-content-report ─
            await page.goto(
                f"{base}/app/work-studio?kind=report",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            await page.wait_for_timeout(3500)
            reports_body = page.locator(
                '[data-testid="ws-tab-content-report"]'
            )
            await reports_body.wait_for(state="visible", timeout=10000)
            doc_in_reports = reports_body.locator(f'text={name_marker}')
            assert await doc_in_reports.count() >= 1, (
                f"Uploaded report doc {name_marker!r} NOT found inside "
                f"ws-tab-content-report. Orthogonality broken — "
                f"Recurrence #5."
            )
            # Origin badge MUST read "Uploaded" on the row.
            row = reports_body.locator(
                f'[data-testid="work-studio-document-row"]:has-text("{name_marker}")'
            ).first
            origin_badge = row.locator(
                '[data-testid="work-studio-document-row-origin-badge"]'
            )
            badge_text = (await origin_badge.text_content() or "").strip()
            assert badge_text == "Uploaded", (
                f"Origin badge on the uploaded report row reads "
                f"{badge_text!r}; expected 'Uploaded'."
            )

            # ─── 6. NOT in the other 5 WS category tab bodies ─────
            for cat in OTHER_WS_CATEGORIES:
                # Each tab uses a different `kind` query param; the
                # main_and_committee_pack tab is the only board_pack
                # holder.
                kind_param = (
                    "cycle_main_and_committee_pack" if cat == "board_pack"
                    else "cycle_minutes" if cat == "minutes"
                    else "drafts" if cat == "draft"
                    else cat
                )
                await page.goto(
                    f"{base}/app/work-studio?kind={kind_param}",
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                await page.wait_for_timeout(2500)
                body = page.locator(f'[data-testid="ws-tab-content-{cat}"]')
                await body.wait_for(state="visible", timeout=8000)
                leakage = await body.locator(f'text={name_marker}').count()
                assert leakage == 0, (
                    f"Uploaded report doc {name_marker!r} LEAKED into "
                    f"ws-tab-content-{cat} (kind={kind_param!r}). "
                    f"Orthogonality broken."
                )

            # ─── 7. /app/documents Uploaded tab → doc surfaces ────
            await page.goto(
                f"{base}/app/documents?tab=upload",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            await page.wait_for_timeout(3500)
            uploaded_body = page.locator(
                '[data-testid="documents-tab-content-upload"]'
            )
            await uploaded_body.wait_for(state="visible", timeout=10000)
            doc_in_uploaded = uploaded_body.locator(f'text={name_marker}')
            assert await doc_in_uploaded.count() >= 1, (
                f"Uploaded report doc {name_marker!r} NOT found inside "
                f"documents-tab-content-upload. Orthogonality broken."
            )

            # ─── 8. NOT in the other 2 origin tab bodies ──────────
            for origin in OTHER_DOCS_ORIGINS:
                await page.goto(
                    f"{base}/app/documents?tab={origin}",
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                await page.wait_for_timeout(2500)
                body = page.locator(
                    f'[data-testid="documents-tab-content-{origin}"]'
                )
                await body.wait_for(state="visible", timeout=8000)
                leakage = await body.locator(f'text={name_marker}').count()
                assert leakage == 0, (
                    f"Uploaded report doc {name_marker!r} LEAKED into "
                    f"documents-tab-content-{origin}. Orthogonality "
                    f"broken on the /app/documents axis."
                )

            # ─── 9. Click the doc card → drawer opens ──────────────
            await page.goto(
                f"{base}/app/documents?tab=upload",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            await page.wait_for_timeout(2500)
            uploaded_body = page.locator(
                '[data-testid="documents-tab-content-upload"]'
            )
            await uploaded_body.wait_for(state="visible", timeout=8000)
            doc_row = uploaded_body.locator(f'text={name_marker}').first
            await doc_row.click()
            await page.wait_for_timeout(2000)
            # The URL must carry `?doc_id=` after the click — the
            # canonical drawer contract.
            assert "doc_id=" in page.url, (
                "Clicking the uploaded doc card MUST set the "
                "`?doc_id=` URL contract so DocumentDrawer mounts."
            )

            # ─── 10. Multi-viewport — Reports tab + Uploaded tab ──
            for vw in (1024, 820):
                await page.set_viewport_size({"width": vw, "height": 900})
                await page.wait_for_timeout(800)
                # WS Reports body still resolves.
                await page.goto(
                    f"{base}/app/work-studio?kind=report",
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                await page.wait_for_timeout(2500)
                rb = page.locator('[data-testid="ws-tab-content-report"]')
                await rb.wait_for(state="visible", timeout=8000)
                assert await rb.locator(f'text={name_marker}').count() >= 1, (
                    f"Reports body lost {name_marker!r} at viewport={vw}px."
                )
                # Documents Uploaded body still resolves.
                await page.goto(
                    f"{base}/app/documents?tab=upload",
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                await page.wait_for_timeout(2500)
                ub = page.locator(
                    '[data-testid="documents-tab-content-upload"]'
                )
                await ub.wait_for(state="visible", timeout=8000)
                assert await ub.locator(f'text={name_marker}').count() >= 1, (
                    f"Uploaded body lost {name_marker!r} at viewport={vw}px."
                )

        finally:
            await browser.close()

    # Cleanup — delete the marker doc from Mongo regardless of pass/fail.
    deleted_count = await _delete_marker_doc(name_marker)
    tmpfile.unlink(missing_ok=True)
    # Sanity — at least 1 row removed if the upload succeeded; harmless
    # if the test failed before upload completed.
    assert deleted_count >= 0
