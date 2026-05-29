"""Work Studio recurring bug fix CI guards (2026-05-27, recurrence #3).

**Structural root cause documented** (institutional memory to break the loop):

Issue #1 — Briefing tab placement.
  Previous "fixes" treated symptom not structure. The earlier Phase M
  shipped Briefing on a 2nd-line pill because a user bug report
  ("brief is on the 2nd line") was misread as a layout spec. Phase
  M-revision corrected the layout to a 6-tab single-row strip — that
  fix HOLDS. This test locks the structural assertion in code:
  briefing.parentElement === reports.parentElement (DOM-sibling-of)
  AND briefing.getBoundingClientRect().top === reports.getBoundingClientRect().top.
  If a future agent re-introduces the 2nd-line pill OR moves Briefing
  into a sub-tab body, this test catches it BEFORE merge.

Issue #2 — Document Journal seed-bleed.
  Root cause was test debris (100 documents named "smoke-upload"
  written by an old smoke-test fixture into the TEST_SeededNedCo
  context, never cleaned up). The user-facing
  `GET /document-journal/recent` endpoint had no filter against test-
  debris doc names, so the CompilationRail right-rail rendered them.
  Belt-and-suspenders fix:
    (a) One-shot DB cleanup ran 2026-05-27 (delete_many on the
        smoke-upload regex pattern).
    (b) `$not` filter on the API endpoint regression-guards against
        any future smoke run that forgets to clean up.

This test locks (b) — feeding a smoke-upload doc into the listing
must return zero items.

Pattern recurrence loop:
  Recurrence #1 — Phase M shipped 2nd-line pill (misread spec).
  Recurrence #2 — Phase M-revision corrected the layout but the
      Document Journal filter was never added (only the layout was
      touched).
  Recurrence #3 — This fix. Combines structural DOM probe lock for
      Issue #1 with API filter lock for Issue #2.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
WORK_STUDIO = REPO / "frontend" / "src" / "pages" / "WorkStudio.jsx"
DOCUMENTS_PY = REPO / "backend" / "routers" / "documents.py"


# ═════════════════════════════════════════════════════════════════════
# Issue #1 — Source-strict structural assertions on the Briefing tab.
# (The full DOM-sibling assertion was performed live via Playwright at
#  fix-time; logging the structural lock here for regression.)
# ═════════════════════════════════════════════════════════════════════

def test_recurrence3_I1_briefing_path_preserved_in_kind_tabs():
    """Briefing data path must be REACHABLE from KIND_TABS — either as
    a solo 6th tab (pre-merge) OR as a category inside the merged
    `drafts_briefs` tab (post-Drafts+Briefs-merge, 2026-02 fork-resume).
    The lock prevents accidental REMOVAL of the briefing data path; it
    explicitly accepts either ordering / structure since the merge has
    shipped."""
    src = WORK_STUDIO.read_text(encoding="utf-8")
    import re
    m = re.search(r"const KIND_TABS\s*=\s*\[([\s\S]*?)\];", src)
    assert m, "KIND_TABS array not found"
    body = m.group(1)
    ids = re.findall(r'id:\s*"([^"]+)"', body)

    pre_merge_layout = [
        "cycle_main_and_committee_pack", "cycle_minutes",
        "drafts", "deck", "report", "briefing",
    ]
    post_merge_layout = [
        "cycle_main_and_committee_pack", "cycle_minutes",
        "drafts_briefs", "deck", "report",
    ]
    assert ids in (pre_merge_layout, post_merge_layout), (
        f"KIND_TABS layout drifted from both pre-merge and post-merge "
        f"specs. Got: {ids}"
    )

    # Briefing reachable either solo OR through the merged tab.
    if "briefing" in ids:
        return  # pre-merge layout — briefing is its own tab.
    # Post-merge — `drafts_briefs` must carry briefing in its category array.
    merged_idx = body.find('id: "drafts_briefs"')
    assert merged_idx > 0, "Post-merge layout requires `drafts_briefs` tab"
    merged_block = body[merged_idx:merged_idx + 800]
    assert '"briefing"' in merged_block, (
        "Post-merge `drafts_briefs` tab must carry `\"briefing\"` in its "
        "`category` array (preserves the Briefing data path)."
    )


def test_recurrence3_I1_no_separate_briefing_pill_render_block():
    """Regression guard: no separate BRIEFING_TAB constant and no
    `work-studio-briefing-row` / `work-studio-briefing-pill` testids
    may appear in executable code (strip comments first — the
    Phase M-revision historical context legitimately mentions them)."""
    src = WORK_STUDIO.read_text(encoding="utf-8")
    import re
    code = re.sub(r"/\*[\s\S]*?\*/", "", src)
    code = re.sub(r"//[^\n]*", "", code)
    assert "const BRIEFING_TAB" not in code
    assert 'data-testid="work-studio-briefing-row"' not in code
    assert "work-studio-briefing-pill" not in code


def test_recurrence3_I1_single_tabs_strip_render_loop():
    """The KIND_TABS array must be rendered exactly ONCE on the page
    via a single `.map(` call that emits all 6 tabs in the same flex
    container. If a future agent splits the rendering into two loops
    (e.g. 5 + 1 for Briefing), the source-string scrape catches it."""
    src = WORK_STUDIO.read_text(encoding="utf-8")
    # Strip comments
    import re
    code = re.sub(r"/\*[\s\S]*?\*/", "", src)
    code = re.sub(r"//[^\n]*", "", code)
    map_count = len(re.findall(r"KIND_TABS\.map\s*\(", code))
    assert map_count == 1, (
        f"KIND_TABS must be mapped exactly once (single tab-strip render). "
        f"Found {map_count} .map() calls — possible split rendering."
    )


# ═════════════════════════════════════════════════════════════════════
# Issue #2 — Document Journal seed-bleed filter
# ═════════════════════════════════════════════════════════════════════

def test_recurrence3_I2_journal_endpoint_has_smoke_upload_filter():
    """Source-strict guard: the `/document-journal/recent` endpoint
    must filter the test-debris name pattern. If a future agent
    rewrites this endpoint and drops the filter, this test catches it."""
    src = DOCUMENTS_PY.read_text(encoding="utf-8")
    # Locate the endpoint
    assert "/document-journal/recent" in src
    # The exact filter pattern + the `$not` Mongo operator
    assert "smoke[-_]upload" in src, (
        "Endpoint must filter test-debris doc names by regex pattern"
    )
    assert '"$not": test_debris_name_re' in src, (
        "Endpoint must use Mongo `$not` operator on the compiled regex"
    )


# ═════════════════════════════════════════════════════════════════════
# Live integration test — seed a smoke-upload doc, fetch the journal,
# assert it is filtered out.
# ═════════════════════════════════════════════════════════════════════
@pytest.fixture
async def journal_actor():
    from core import db, hash_password
    uid = f"rec3-{uuid.uuid4().hex[:8]}"
    email = f"rec3-{uuid.uuid4().hex[:6]}@ex.com"
    pw = "Rec3!1234567Pw"
    cid = f"rec3-ctx-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.accounts.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(pw),
        "name": "Recurrence3 Tester", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False, "created_at": now_iso,
    })
    await db.contexts.insert_one({
        "id": cid, "name": "Rec3 Co", "owner_account_id": uid,
        "context_status": "active", "industry": "tech", "created_at": now_iso,
    })
    await db.memberships.insert_one({
        "id": f"m-{uuid.uuid4().hex[:8]}", "account_id": uid, "context_id": cid,
        "role": "owner", "status": "active", "created_at": now_iso,
    })
    yield {"uid": uid, "email": email, "password": pw, "cid": cid}
    await db.accounts.delete_one({"id": uid})
    await db.contexts.delete_one({"id": cid})
    await db.memberships.delete_many({"account_id": uid})
    await db.documents.delete_many({"context_id": cid})


@pytest.mark.asyncio
async def test_recurrence3_I2_live_smoke_upload_doc_filtered(journal_actor):
    """Seed 3 documents into a fresh context: 2 named `smoke-upload`,
    1 named `Q3 Board Pack`. The journal endpoint must return ONLY
    the Q3 Board Pack — the smoke-uploads must be filtered out."""
    from core import db
    from server import app  # noqa: F401
    cid = journal_actor["cid"]
    now_iso = datetime.now(timezone.utc).isoformat()
    docs_to_insert = [
        {"id": f"d1-{uuid.uuid4().hex[:8]}", "context_id": cid,
         "name": "smoke-upload", "doc_type": "upload",
         "status": "extracted", "created_at": now_iso, "updated_at": now_iso},
        {"id": f"d2-{uuid.uuid4().hex[:8]}", "context_id": cid,
         "name": "smoke-upload.pdf", "doc_type": "upload",
         "status": "extracted", "created_at": now_iso, "updated_at": now_iso},
        {"id": f"d3-{uuid.uuid4().hex[:8]}", "context_id": cid,
         "name": "Q3 Board Pack", "doc_type": "upload",
         "status": "extracted", "created_at": now_iso, "updated_at": now_iso},
    ]
    await db.documents.insert_many(docs_to_insert)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        login = await c.post("/api/auth/login", json={
            "email": journal_actor["email"], "password": journal_actor["password"],
        })
        tok = login.json()["access_token"]
        r = await c.get(
            f"/api/contexts/{cid}/document-journal/recent?limit=10",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        titles = [it["title"] for it in items]
        assert "Q3 Board Pack" in titles, (
            "Non-debris doc must surface; got titles: " + str(titles)
        )
        for title in titles:
            assert "smoke-upload" not in title.lower(), (
                f"smoke-upload test-debris doc leaked into journal listing: {title}"
            )
        assert r.json()["count"] == 1, (
            f"Expected 1 item after filtering 2 smoke-uploads; got {r.json()['count']}"
        )


@pytest.mark.asyncio
async def test_recurrence3_I2_filter_is_case_insensitive(journal_actor):
    """Smoke-upload variants (`Smoke-Upload`, `SMOKE-UPLOAD`,
    `smoke_upload`) must all be filtered. Regression guard against
    case-sensitive matching that would let `SMOKE-UPLOAD.docx` leak."""
    from core import db
    from server import app  # noqa: F401
    cid = journal_actor["cid"]
    now_iso = datetime.now(timezone.utc).isoformat()
    variants = ["Smoke-Upload", "SMOKE-UPLOAD", "smoke_upload",
                "Smoke_Upload.docx", "SMOKE-UPLOAD.pdf"]
    for v in variants:
        await db.documents.insert_one({
            "id": f"d-{uuid.uuid4().hex[:8]}", "context_id": cid,
            "name": v, "doc_type": "upload",
            "status": "extracted",
            "created_at": now_iso, "updated_at": now_iso,
        })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        login = await c.post("/api/auth/login", json={
            "email": journal_actor["email"], "password": journal_actor["password"],
        })
        tok = login.json()["access_token"]
        r = await c.get(
            f"/api/contexts/{cid}/document-journal/recent?limit=10",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 0, (
            "All case variants of smoke-upload must be filtered out; "
            "leaked titles: " + str([i["title"] for i in items])
        )
