"""Phase E.1 + E.2 — Work Studio cleanup wire tests (2026-05-26).

Asserts the structural contract on the frontend source files. Per the
Phase C false-greens lesson, every test checks the actual computed
artefact (URL string, tab id string, DOM testid presence), not the
JSX className or comment text.

E.1 — Tab cleanup
  • DOCUMENT CARDS h2 heading is removed (only the listing remains).
  • Tab bar order: Main Board & Committee Packs · Minutes · Drafts ·
    Decks · Reports · Briefing.
  • "Board Packs" + "Committee Packs" tab labels do NOT appear in the
    tab definitions anywhere.
  • Drafts tab sources documents (state=draft), not aggregates.
  • Legacy `?kind=cycle_board_pack` / `?kind=cycle_committee_pack`
    URLs redirect to the merged tab.

E.2 — Right side panel restructure
  • Ready-to-Compile + At-Risk cards mounted on CycleList, NOT on
    CompilationRail.
  • CompilationRail header: "Generate Report" button + italic subtext
    "from multiple documents".
  • Recent Drafts deck present with view-more →
    /app/work-studio?kind=drafts.
  • Recent Activity deck present with view-more →
    /app/work-studio/activity.
  • Backend endpoints: /api/contexts/{cid}/documents/drafts +
    /api/contexts/{cid}/activity/recent are wired.
  • /app/work-studio/activity route is mounted.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent.parent
FE   = REPO / "frontend" / "src"
BE   = REPO / "backend"

WORK_STUDIO        = FE / "pages" / "WorkStudio.jsx"
DOC_CARDS_SECTION  = FE / "components" / "work_studio" / "DocumentCardsSection.jsx"
COMPILATION_RAIL   = FE / "components" / "work_studio" / "CompilationRail.jsx"
CYCLE_LIST         = FE / "pages" / "cycle" / "CycleList.jsx"
READINESS_SECTION  = FE / "components" / "cycle" / "CompilationReadinessSection.jsx"
APP_JS             = FE / "App.js"
ACTIVITY_PAGE      = FE / "pages" / "WorkStudioActivity.jsx"
DOCUMENTS_PY       = BE / "routers" / "documents.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────
# E.1 — Tab cleanup
# ─────────────────────────────────────────────────────────────────────
def test_e1_document_cards_heading_removed():
    """The h2 "Document Cards" label is removed from the listing.
    The listing container + ul stay (we only delete the label)."""
    src = _read(DOC_CARDS_SECTION)
    # The h2 with the label MUST be gone.
    assert "Document Cards" not in re.sub(r"//.*|/\*.*?\*/", "", src, flags=re.DOTALL) or \
           "<h2" not in src.split("data-testid=\"work-studio-document-cards-section\"")[1].split("<ul")[0], \
        "Document Cards h2 heading must be removed from DocumentCardsSection"
    # Listing container preserved.
    assert 'data-testid="work-studio-document-cards-section"' in src
    assert 'data-testid="work-studio-document-cards-list"' in src


def test_e1_tab_bar_post_merge_layout_locked():
    """Phase E.1 specced 6 tabs (Board+Committee merge, Briefing as
    6th solo). Drafts+Briefs merge (2026-02 fork-resume) subsequently
    collapsed Drafts + Briefing into one `drafts_briefs` tab, reducing
    the strip to 5 entries. This guard accepts the POST-MERGE layout
    only — the merge has shipped and is locked elsewhere
    (`test_workstudio_drafts_briefs_merged.py` + `test_phase_z_slice_6_orthogonality_wire.py`).

    The pre-merge 6-tab assertion is intentionally removed. Briefing
    data path is preserved via the merged tab's `category: ["draft",
    "briefing"]` array form, which is locked separately."""
    src = _read(WORK_STUDIO)
    block = src.split("const KIND_TABS = [")[1].split("];")[0]
    pairs = re.findall(r'id:\s*"([^"]+)"[^}]*?label:\s*"([^"]+)"', block, re.DOTALL)
    expected = [
        ("cycle_main_and_committee_pack", "Main Board & Committee Packs"),
        ("cycle_minutes",                 "Minutes"),
        ("drafts_briefs",                 "Drafts & Briefs"),
        ("deck",                          "Decks"),
        ("report",                        "Reports"),
    ]
    assert pairs == expected, (
        f"KIND_TABS post-merge order/labels drifted.\n"
        f"  expected: {expected}\n"
        f"  actual:   {pairs}"
    )


def test_e1_legacy_tab_labels_removed():
    """The standalone "Board Packs" / "Committee Packs" tab labels
    must no longer appear in the KIND_TABS definition. They can
    appear in comments/docs explaining the merge."""
    src = _read(WORK_STUDIO)
    block = src.split("const KIND_TABS = [")[1].split("];")[0]
    # Strip comments.
    code = re.sub(r"//.*", "", block)
    assert '"Board Packs"'     not in code, "Legacy 'Board Packs' label still in KIND_TABS"
    assert '"Committee Packs"' not in code, "Legacy 'Committee Packs' label still in KIND_TABS"


def test_e1_merged_tab_carries_canonical_category():
    """Phase E.1 originally used a `union_of: ["cycle_board_pack",
    "cycle_committee_pack"]` array to mark the merge data-contract.
    Phase Z (2026-05-27) replaced `union_of:` with a single canonical
    `category: "board_pack"` on the merged tab — the sub-distinction
    between Main Board and Committee packs is preserved at the
    `work_studio_exports.kind` level (for compile-template selection)
    but rolls up to one category in the listing layer.

    Locks the post-Z merge contract:
      - Merged tab id = `cycle_main_and_committee_pack`
      - Carries `category: "board_pack"`
      - Legacy URL params (`?kind=cycle_board_pack`/`cycle_committee_pack`)
        still redirect to the merged tab id at `initialKind` capture."""
    src = _read(WORK_STUDIO)
    tabs_block = src.split("const KIND_TABS = [")[1].split("];")[0]
    merged_block = tabs_block.split('id: "cycle_main_and_committee_pack"')[1].split("},")[0]
    assert 'category: "board_pack"' in merged_block, (
        "Merged tab must declare canonical `category: \"board_pack\"`"
    )
    # Legacy URL-param redirect still in place.
    init_block = src.split("const initialKind = (() => {")[1].split("})();")[0]
    assert 'k === "cycle_board_pack"' in init_block, (
        "initialKind must still redirect legacy `?kind=cycle_board_pack`"
    )
    assert 'k === "cycle_committee_pack"' in init_block, (
        "initialKind must still redirect legacy `?kind=cycle_committee_pack`"
    )
    assert 'return "cycle_main_and_committee_pack"' in init_block, (
        "Legacy redirects must land on the merged tab id"
    )


def test_e1_legacy_kind_query_param_redirects_to_merged():
    """?kind=cycle_board_pack and ?kind=cycle_committee_pack must
    resolve to the merged tab id at initialKind capture time."""
    src = _read(WORK_STUDIO)
    init_block = src.split("const initialKind = (() => {")[1].split("})();")[0]
    assert 'k === "cycle_board_pack"' in init_block
    assert 'k === "cycle_committee_pack"' in init_block
    assert 'return "cycle_main_and_committee_pack"' in init_block


# ─────────────────────────────────────────────────────────────────────
# E.2 — Right side panel restructure
# ─────────────────────────────────────────────────────────────────────
def test_e2_ready_to_compile_lives_on_cycle_list_not_work_studio_rail():
    """The Ready-to-Compile + At-Risk cards moved to Cycle Manager.
    They must be ABSENT from CompilationRail and PRESENT on CycleList
    (via CompilationReadinessSection)."""
    rail_src = _read(COMPILATION_RAIL)
    # Removed from rail.
    assert 'data-testid="compilation-rail-ready"'   not in rail_src
    assert 'data-testid="compilation-rail-atrisk"'  not in rail_src
    # Present on the new section (Cycle Manager).
    readiness_src = _read(READINESS_SECTION)
    assert 'data-testid="cycle-list-ready-to-compile"' in readiness_src
    assert 'data-testid="cycle-list-at-risk"'          in readiness_src
    # And the section is mounted on CycleList.
    cycle_src = _read(CYCLE_LIST)
    assert "<CompilationReadinessSection" in cycle_src
    assert "import CompilationReadinessSection" in cycle_src


def test_e2_rail_cta_is_generate_report_with_italic_subtext():
    """Rail top CTA reads 'Generate Report' and is followed directly
    by an italic subtext 'from multiple documents'."""
    src = _read(COMPILATION_RAIL)
    # CTA copy.
    assert ">Generate Report<"        in src.replace(" ", " ").replace("\n", " ") or "Generate Report" in src
    assert "Generate Report" in src
    # Subtext element with the canonical class + testid.
    assert 'data-testid="compilation-rail-generate-report-subtext"' in src
    subtext_block = src.split('data-testid="compilation-rail-generate-report-subtext"')[0].rsplit("<p", 1)[1] \
                    + src.split('data-testid="compilation-rail-generate-report-subtext"', 1)[1].split("</p>", 1)[0]
    assert "italic" in subtext_block, "subtext must be italic"
    assert "from multiple documents" in subtext_block, "subtext content must read 'from multiple documents'"
    # Legacy "Compile a Report" copy is gone.
    code_only = re.sub(r"//.*|/\*.*?\*/", "", src, flags=re.DOTALL)
    assert "Compile a Report" not in code_only, "Legacy 'Compile a Report' CTA label must be removed"


def test_e2_recent_drafts_deck_present_with_view_more_link():
    """Rail has a Recent Drafts section with 5-row cap + view-more
    link pointing to /app/work-studio?kind=drafts."""
    src = _read(COMPILATION_RAIL)
    assert 'data-testid="compilation-rail-recent-drafts"' in src
    assert 'data-testid="compilation-rail-recent-drafts-list"' in src
    assert 'data-testid="compilation-rail-recent-drafts-view-more"' in src
    assert "/app/work-studio?kind=drafts" in src
    # 5-row cap reuses the RECENT_DOCS_LIMIT constant from the rail.
    assert ".slice(0, RECENT_DOCS_LIMIT)" in src


def test_e2_recent_activity_deck_present_with_view_more_link():
    """Rail has a Recent Activity section with view-more link
    pointing to /app/work-studio/activity."""
    src = _read(COMPILATION_RAIL)
    assert 'data-testid="compilation-rail-recent-activity"' in src
    assert 'data-testid="compilation-rail-recent-activity-list"' in src
    assert 'data-testid="compilation-rail-recent-activity-view-more"' in src
    assert "/app/work-studio/activity" in src


def test_e2_recent_activity_route_is_mounted():
    """The view-more destination /app/work-studio/activity must be a
    real route in App.js."""
    src = _read(APP_JS)
    assert "/app/work-studio/activity" in src
    assert "<WorkStudioActivity" in src
    # The page component file exists.
    assert ACTIVITY_PAGE.exists(), "WorkStudioActivity.jsx must exist"


def test_e2_rail_section_order_generate_drafts_activity():
    """Rail section order top-to-bottom:
       Generate Report → Recent Drafts → Recent Activity.

    UPDATED 2026-02 fork-resume — Document Journal deck was removed
    from CompilationRail (its data path moved to a different surface).
    The remaining 3 decks order as above."""
    src = _read(COMPILATION_RAIL)
    markers = [
        ('data-testid="compilation-rail-generate-report-block"',         "Generate Report block"),
        ('data-testid="compilation-rail-recent-drafts"',                 "Recent Drafts deck"),
        ('data-testid="compilation-rail-recent-activity"',               "Recent Activity deck"),
    ]
    last_pos = -1
    for needle, label in markers:
        pos = src.find(needle)
        assert pos != -1, f"missing {label} ({needle})"
        assert pos > last_pos, (
            f"{label} ({needle}) appears out-of-order in CompilationRail.jsx; "
            f"previous marker ended at {last_pos}, this one starts at {pos}"
        )
        last_pos = pos
    # Anti-regression: the legacy Document Journal deck testid must
    # NOT reappear (its removal is intentional, not a bug).
    assert 'data-testid="compilation-rail-document-journal"' not in src, (
        "Document Journal deck was removed from CompilationRail (post "
        "2026-02 dispatch). Its data path moved off the rail; the "
        "testid must not regress."
    )


def test_e2_backend_drafts_endpoint_wired():
    """GET /contexts/{cid}/documents/drafts endpoint defined in
    routers/documents.py with state=draft filter."""
    src = _read(DOCUMENTS_PY)
    assert '@router.get("/contexts/{context_id}/documents/drafts")' in src
    drafts_fn = src.split('@router.get("/contexts/{context_id}/documents/drafts")')[1].split("@router")[0]
    assert '"state": "draft"' in drafts_fn


def test_e2_backend_drafts_endpoint_declared_before_doc_id_route():
    """Route ordering: /documents/drafts MUST appear before
    /documents/{doc_id} in source so FastAPI matches the literal first."""
    src = _read(DOCUMENTS_PY)
    drafts_pos = src.find('@router.get("/contexts/{context_id}/documents/drafts")')
    docid_pos  = src.find('@router.get("/contexts/{context_id}/documents/{doc_id}")')
    assert drafts_pos != -1 and docid_pos != -1
    assert drafts_pos < docid_pos, (
        "/documents/drafts must be declared BEFORE /documents/{doc_id} so "
        "FastAPI matches the literal path first"
    )


def test_e2_backend_activity_endpoint_wired():
    """GET /contexts/{cid}/activity/recent endpoint defined."""
    src = _read(DOCUMENTS_PY)
    assert '@router.get("/contexts/{context_id}/activity/recent")' in src
    # Reads from audit_log scoped to the context.
    activity_fn = src.split('@router.get("/contexts/{context_id}/activity/recent")')[1].split("@router")[0]
    assert "db.audit_log.find(" in activity_fn
    assert '"context_id"' in activity_fn


# ─────────────────────────────────────────────────────────────────────
# Live HTTP — happy paths
# ─────────────────────────────────────────────────────────────────────
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_e2_drafts_endpoint_returns_empty_list_when_no_drafts():
    """state=draft documents collection is empty today; endpoint
    must return [] not 500."""
    from server import app  # noqa: F401
    from core import db, hash_password
    import uuid
    from datetime import datetime, timezone

    uid  = f"test-e2-{uuid.uuid4().hex[:8]}"
    cid  = f"ctx-e2-{uuid.uuid4().hex[:8]}"
    email = f"e2-{uuid.uuid4().hex[:6]}@example.com"

    await db.accounts.insert_one({
        "id": uid, "email": email,
        "password_hash": hash_password("Pw!1234567Abc"),
        "name": "E2", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.contexts.insert_one({
        "id": cid, "name": "E2 Co", "owner_account_id": uid,
        "type": "executive_personal",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}",
        "account_id": uid, "context_id": cid,
        "role": "executive", "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test") as c:
            r = await c.post("/api/auth/login",
                             json={"email": email, "password": "Pw!1234567Abc"})
            token = r.json().get("access_token") or r.json().get("token")
            hdr = {"Authorization": f"Bearer {token}",
                   "X-Active-Context": cid}
            r = await c.get(f"/api/contexts/{cid}/documents/drafts", headers=hdr)
            assert r.status_code == 200, r.text
            assert r.json() == []
            r = await c.get(f"/api/contexts/{cid}/activity/recent", headers=hdr)
            assert r.status_code == 200
            assert isinstance(r.json(), list)
    finally:
        await db.memberships.delete_many({"account_id": uid})
        await db.contexts.delete_one({"id": cid})
        await db.accounts.delete_one({"id": uid})


@pytest.mark.asyncio
async def test_e2_drafts_endpoint_filters_state_draft():
    """Seed 2 documents — one with state=draft, one without —
    confirm the endpoint returns only the draft."""
    from server import app  # noqa: F401
    from core import db, hash_password
    import uuid
    from datetime import datetime, timezone

    uid  = f"test-e2-{uuid.uuid4().hex[:8]}"
    cid  = f"ctx-e2-{uuid.uuid4().hex[:8]}"
    email = f"e2-{uuid.uuid4().hex[:6]}@example.com"
    did_draft     = f"doc-d-{uuid.uuid4().hex[:8]}"
    did_committed = f"doc-c-{uuid.uuid4().hex[:8]}"

    await db.accounts.insert_one({
        "id": uid, "email": email,
        "password_hash": hash_password("Pw!1234567Abc"),
        "name": "E2", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.contexts.insert_one({
        "id": cid, "name": "E2 Co", "owner_account_id": uid,
        "type": "executive_personal",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}",
        "account_id": uid, "context_id": cid,
        "role": "executive", "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.documents.insert_one({
        "id": did_draft, "context_id": cid,
        "name": "Draft One.docx",
        "state": "draft", "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.documents.insert_one({
        "id": did_committed, "context_id": cid,
        "name": "Committed Doc.pdf",
        "state": "committed", "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test") as c:
            r = await c.post("/api/auth/login",
                             json={"email": email, "password": "Pw!1234567Abc"})
            token = r.json().get("access_token") or r.json().get("token")
            hdr = {"Authorization": f"Bearer {token}",
                   "X-Active-Context": cid}
            r = await c.get(f"/api/contexts/{cid}/documents/drafts", headers=hdr)
            assert r.status_code == 200, r.text
            rows = r.json()
            assert len(rows) == 1, f"expected exactly 1 draft, got {len(rows)}"
            assert rows[0]["id"] == did_draft
    finally:
        await db.documents.delete_many({"id": {"$in": [did_draft, did_committed]}})
        await db.memberships.delete_many({"account_id": uid})
        await db.contexts.delete_one({"id": cid})
        await db.accounts.delete_one({"id": uid})


def test_e_log_section_present_in_home_cleanup_log():
    """HOME_CLEANUP_LOG.md carries the Phase E section with E.1 + E.2
    sub-sections."""
    log = (REPO / "memory" / "sprints" / "HOME_CLEANUP_LOG.md").read_text("utf-8")
    assert "## Phase E — Work Studio" in log
    assert "### E.1 — Tab cleanup" in log
    assert "### E.2 — Right side panel restructure" in log
