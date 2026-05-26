"""Phase E.3 — Universal Document Drawer wire tests (2026-05-26).

Asserts:
  (a) Drawer mounts on every primary listing surface (WorkStudio,
      Workspace, Pulse, Cycle) so `?doc_id=` deep links work.
  (b) Mode selection: state=draft+origin=akki_generated → Creation;
      everything else → Reference.
  (c) All 5 CTAs use the canonical `?ctx_type=document&ctx_id=` URL.
  (d) DRAFT watermark overlay testid present in Creation mode.
  (e) Backend endpoints wired: PATCH /documents/{did},
      GET/POST /intelligence, GET /export-guard.
  (f) Share modal ports legacy engagement endpoints
      (no new collections invented).
  (g) Objective capture modal fires + persists.

Same lesson as Phase C: tests check the actual generated URL/testid,
not className strings.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
FE   = REPO / "frontend" / "src"
BE   = REPO / "backend"

DRAWER          = FE / "components" / "documents" / "DocumentDrawer.jsx"
WATERMARK       = FE / "components" / "documents" / "DocumentDrawerWatermark.jsx"
SHARE_MODAL     = FE / "components" / "documents" / "ShareDocumentModal.jsx"
OBJ_MODAL       = FE / "components" / "documents" / "ObjectiveCaptureModal.jsx"
WORKSTUDIO      = FE / "pages" / "WorkStudio.jsx"
WORKSPACE       = FE / "pages" / "Workspace.jsx"
PULSE           = FE / "pages" / "Pulse.jsx"
CYCLE           = FE / "pages" / "Cycle.jsx"
DOCUMENTS_PY    = BE / "routers" / "documents.py"
INTEL_SVC       = BE / "services" / "documents" / "intelligence_service.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────
# (a) Drawer mounts on every primary listing surface
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("surface", [WORKSTUDIO, WORKSPACE, PULSE, CYCLE])
def test_e3_document_drawer_mounted_on_every_primary_surface(surface):
    """Every primary doc-listing surface must mount `<DocumentDrawer>`
    so the `?doc_id=` deep-link contract works from any route."""
    src = _read(surface)
    assert "import DocumentDrawer" in src, (
        f"{surface.name} must import DocumentDrawer"
    )
    assert "<DocumentDrawer" in src, (
        f"{surface.name} must render <DocumentDrawer …/>"
    )


# ─────────────────────────────────────────────────────────────────────
# (b) Mode selection by doc.state
# ─────────────────────────────────────────────────────────────────────
def test_e3_drawer_mode_selection_logic():
    """isCreationMode = state==='draft' AND origin==='akki_generated'.
    Every other combination → Reference."""
    src = _read(DRAWER)
    # The function body must check both fields.
    assert 'doc?.state === "draft"' in src
    assert 'doc?.origin === "akki_generated"' in src
    # The mode is data-mode on the drawer root for live DOM verification.
    assert 'data-mode={mode}' in src


def test_e3_drawer_state_badge_renders_oxblood_for_draft():
    """DRAFT badge uses oxblood background; COMMITTED badge uses
    emerald (green pill per spec)."""
    src = _read(DRAWER)
    assert 'data-testid="drawer-state-badge"' in src
    assert "bg-[color:var(--oxblood)]" in src
    assert "bg-emerald-700" in src
    # Badge text — DRAFT in creation, COMMITTED in reference.
    assert '"DRAFT" : "COMMITTED"' in src


# ─────────────────────────────────────────────────────────────────────
# (c) 5 CTAs all use canonical `?ctx_type=document&ctx_id=` URL contract
# ─────────────────────────────────────────────────────────────────────
def test_e3_drawer_five_ctas_all_canonical_urls():
    """All 5 footer CTAs must emit `?ctx_type=document&ctx_id=` URLs.
    Each CTA carries a `data-href` attribute for live DOM verification
    + a unique testid."""
    src = _read(DRAWER)
    cta_testids = [
        "drawer-cta-use-in-solva",
        "drawer-cta-use-in-chat",
        "drawer-cta-generate-brief",
        "drawer-cta-test-hypothesis",
        "drawer-cta-share",
    ]
    for tid in cta_testids:
        assert f'data-testid="{tid}"' in src, f"missing CTA testid: {tid}"
    # The 4 navigate-CTAs must call the canonical URL-builder functions.
    for fn in ("buildSolvaUrl()", "buildChatUrl()", "buildBriefUrl()", "buildHypothesisUrl()"):
        assert fn in src, f"missing URL builder call: {fn}"
    # Each builder constructs the canonical pair.
    for builder in ("buildSolvaUrl", "buildChatUrl", "buildBriefUrl", "buildHypothesisUrl"):
        # Locate the const declaration tolerating column alignment.
        m = re.search(rf"const {builder}\s*=\s*\(\)\s*=>\s*`([^`]+)`", src)
        assert m, f"could not parse URL builder body for {builder}"
        body = m.group(1)
        assert "ctx_type=document" in body, f"{builder} must emit ?ctx_type=document"
        assert "ctx_id=" in body, f"{builder} must emit &ctx_id="


def test_e3_share_cta_opens_share_modal_not_canonical_url():
    """The 5th CTA opens the ShareDocumentModal — share is internal,
    not a route navigation."""
    src = _read(DRAWER)
    # The share button calls setShareOpen(true), NOT navigate(...).
    share_section = src.split('data-testid="drawer-cta-share"')[0].rsplit("<Button", 1)[1]
    assert "setShareOpen(true)" in share_section
    assert "navigate(" not in share_section


# ─────────────────────────────────────────────────────────────────────
# (d) DRAFT watermark overlay
# ─────────────────────────────────────────────────────────────────────
def test_e3_watermark_overlay_present_only_in_creation_mode():
    """DocumentDrawerWatermark renders only when mode === creation
    AND on the Document tab (not on Intelligence / Notes / Signals /
    Related — those tabs need the body content visible)."""
    src = _read(DRAWER)
    assert "<DocumentDrawerWatermark" in src
    # The render gate is `mode === "creation" && activeTab === "document"`.
    assert 'mode === "creation" && activeTab === "document"' in src


def test_e3_watermark_component_rotates_minus30_oxblood_repeating_tile():
    """Watermark SVG pattern uses -30deg rotation, oxblood fill,
    repeating tile (patternUnits=userSpaceOnUse)."""
    src = _read(WATERMARK)
    assert 'patternTransform="rotate(-30)"' in src
    # oxblood fill (CSS var or fallback hex).
    assert "var(--oxblood" in src
    # Tiled pattern.
    assert 'patternUnits="userSpaceOnUse"' in src
    # Pointer events disabled so the body underneath stays clickable.
    assert "pointer-events-none" in src
    # ~12% opacity per spec.
    assert "opacity: 0.12" in src


# ─────────────────────────────────────────────────────────────────────
# (e) Backend endpoints wired
# ─────────────────────────────────────────────────────────────────────
def test_e3_backend_patch_document_endpoint_wired():
    """PATCH /documents/{did} accepts title/body/state/objective/audience/origin."""
    src = _read(DOCUMENTS_PY)
    assert '@router.patch("/contexts/{context_id}/documents/{doc_id}")' in src
    # The patch schema includes all 6 mutable fields.
    schema_block = src.split("class _DocPatchIn(BaseModel):")[1].split("class ")[0]
    for field in ("title", "body", "state", "objective", "audience", "origin"):
        assert field in schema_block, f"PATCH schema missing field: {field}"


def test_e3_backend_intelligence_endpoints_wired():
    """GET + POST /intelligence/* endpoints defined."""
    src = _read(DOCUMENTS_PY)
    assert '@router.get("/contexts/{context_id}/documents/{doc_id}/intelligence")' in src
    assert '@router.post("/contexts/{context_id}/documents/{doc_id}/intelligence/regenerate")' in src
    # Regenerate uses BackgroundTasks for async extraction.
    regen_block = src.split('@router.post("/contexts/{context_id}/documents/{doc_id}/intelligence/regenerate")')[1].split("@router")[0]
    assert "BackgroundTasks" in regen_block or "background_tasks" in regen_block


def test_e3_backend_export_guard_allows_drafts_with_watermark_required():
    """Per E.3 scope-compliance (2026-05-26): drafts ARE now exportable
    — the watermark pipeline embeds a visible DRAFT stamp before
    serving the bytes. The guard signals `watermark_required: True`
    on drafts. Block-on-failure still lives in the download endpoint."""
    src = _read(DOCUMENTS_PY)
    assert '@router.get("/contexts/{context_id}/documents/{doc_id}/export-guard")' in src
    guard_block = src.split('@router.get("/contexts/{context_id}/documents/{doc_id}/export-guard")')[1].split("@router")[0]
    assert 'doc.get("state") == "draft"' in guard_block
    assert '"can_export":         True' in guard_block
    assert '"watermark_required": True' in guard_block
    assert '"watermark_label":    "DRAFT"' in guard_block


def test_e3_intelligence_service_routes_through_shield():
    """Every LLM call inside intelligence_service goes through
    Shield's invoke() — no raw LLM bypass."""
    src = _read(INTEL_SVC)
    assert "from services.synisense.shield.client import invoke as shield_invoke" in src
    # Three Shield invocations: summary, signals, objective.
    assert src.count("await shield_invoke(") >= 3
    # No direct emergentintegrations import (must go through Shield).
    assert "from emergentintegrations" not in src


def test_e3_intelligence_extraction_purpose_allowlisted():
    """The purpose used in the Shield call must be in the
    allowlist (config.py:ALLOWED_PURPOSES). `document_journal.*` matches
    the existing wildcard."""
    config_src = (BE / "services" / "synisense" / "config.py").read_text("utf-8")
    assert '"document_journal.*"' in config_src or "document_journal." in config_src
    intel_src = _read(INTEL_SVC)
    # Each Shield call uses a document_journal.* purpose.
    purposes = re.findall(r'purpose="([^"]+)"', intel_src)
    assert purposes, "intelligence_service must declare a purpose on every Shield call"
    for p in purposes:
        assert p.startswith("document_journal."), f"purpose '{p}' must start with document_journal."


# ─────────────────────────────────────────────────────────────────────
# (f) Share modal ports legacy engagement endpoints
# ─────────────────────────────────────────────────────────────────────
def test_e3_share_modal_wires_legacy_engagement_endpoints():
    """ShareDocumentModal posts to /documents/{did}/share and reads
    from /documents/{did}/engagement — the existing legacy endpoints.
    No new collection invented."""
    src = _read(SHARE_MODAL)
    assert "/documents/${docId}/share" in src
    assert "/documents/${docId}/engagement" in src
    # Revoke uses the existing /shares/{id}/revoke endpoint.
    assert "/shares/${shareId}/revoke" in src


def test_e3_share_modal_renders_engagement_metrics():
    """The modal surfaces views + readers + shares + per-row revoke."""
    src = _read(SHARE_MODAL)
    for tid in (
        "share-modal-engagement-views",
        "share-modal-engagement-shares",
        "share-modal-share-row",
        "share-modal-revoke-btn",
    ):
        assert f'data-testid="{tid}"' in src, f"missing testid: {tid}"


# ─────────────────────────────────────────────────────────────────────
# (g) Objective capture modal
# ─────────────────────────────────────────────────────────────────────
def test_e3_objective_modal_fires_on_new_draft_creation():
    """WorkStudio's onCreateClick('draft') opens ObjectiveCaptureModal
    instead of the regular CreateArtefactModal."""
    src = _read(WORKSTUDIO)
    assert "import ObjectiveCaptureModal" in src
    assert "<ObjectiveCaptureModal" in src
    # The dispatch logic.
    click_block = src.split("const onCreateClick")[1].split("};")[0]
    assert 'k === "draft"' in click_block
    assert "setObjectiveModalOpen(true)" in click_block


def test_e3_objective_modal_persists_via_patch():
    """The modal's onSave POSTs a new document with the objective payload."""
    src = _read(WORKSTUDIO)
    obj_block = src.split("<ObjectiveCaptureModal")[1].split("</ObjectiveCaptureModal>")[0] \
                if "</ObjectiveCaptureModal>" in src else src.split("<ObjectiveCaptureModal")[1].split("/>")[0]
    # Must call manual-create with state=draft, origin=akki_generated, objective payload.
    assert '"draft"' in obj_block
    assert '"akki_generated"' in obj_block
    assert "objective:" in obj_block


# ─────────────────────────────────────────────────────────────────────
# Live HTTP — happy paths against the in-process FastAPI app
# ─────────────────────────────────────────────────────────────────────
@pytest.fixture
async def seeded_context():
    from core import db, hash_password
    uid = f"test-e3-{uuid.uuid4().hex[:8]}"
    cid = f"ctx-e3-{uuid.uuid4().hex[:8]}"
    email = f"e3-{uuid.uuid4().hex[:6]}@example.com"
    await db.accounts.insert_one({
        "id": uid, "email": email,
        "password_hash": hash_password("Pw!1234567Abc"),
        "name": "E3", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.contexts.insert_one({
        "id": cid, "name": "E3 Co", "owner_account_id": uid,
        "type": "executive_personal",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}",
        "account_id": uid, "context_id": cid,
        "role": "executive", "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"uid": uid, "cid": cid, "email": email, "password": "Pw!1234567Abc"}
    # Cleanup
    await db.documents.delete_many({"context_id": cid})
    await db.document_intelligence.delete_many({})
    await db.memberships.delete_many({"account_id": uid})
    await db.contexts.delete_one({"id": cid})
    await db.accounts.delete_one({"id": uid})


@pytest.mark.asyncio
async def test_e3_patch_document_persists_state_and_objective(seeded_context):
    """End-to-end: create doc with state=draft, PATCH the objective,
    fetch back to confirm persistence."""
    from server import app  # noqa: F401
    from core import db
    did = f"doc-e3-{uuid.uuid4().hex[:8]}"
    await db.documents.insert_one({
        "id": did, "context_id": seeded_context["cid"],
        "name": "E3 draft",
        "state": "draft",
        "origin": "akki_generated",
        "extracted_text": "Initial draft body.",
        "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/auth/login",
                         json={"email": seeded_context["email"], "password": seeded_context["password"]})
        token = r.json().get("access_token") or r.json().get("token")
        hdr = {"Authorization": f"Bearer {token}", "X-Active-Context": seeded_context["cid"]}
        # PATCH objective + body.
        r = await c.patch(f"/api/contexts/{seeded_context['cid']}/documents/{did}", json={
            "body": "Updated draft body.",
            "objective": {"goal": "Decide pricing for Q4", "context": "Board wants 3 options"},
        }, headers=hdr)
        assert r.status_code == 200, r.text
        # Fetch.
        r = await c.get(f"/api/contexts/{seeded_context['cid']}/documents/{did}", headers=hdr)
        assert r.status_code == 200
        doc = r.json()
        assert doc["objective"]["goal"] == "Decide pricing for Q4"
        assert doc["objective"]["context"] == "Board wants 3 options"
        assert doc["state"] == "draft"
        assert doc["origin"] == "akki_generated"
        assert "Updated draft body" in (doc.get("extracted_text") or "")


@pytest.mark.asyncio
async def test_e3_export_guard_allows_draft_with_watermark_required(seeded_context):
    """Per E.3 scope-compliance: a doc with state=draft hits the
    export-guard and gets can_export=True + watermark_required=True.
    The download endpoint applies the watermark and falls back to
    HTTP 503 (DRAFT_WATERMARK_FAILED) if the pipeline errors."""
    from server import app  # noqa: F401
    from core import db
    did = f"doc-e3-{uuid.uuid4().hex[:8]}"
    await db.documents.insert_one({
        "id": did, "context_id": seeded_context["cid"],
        "name": "Draft to export",
        "state": "draft",
        "origin": "akki_generated",
        "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/auth/login",
                         json={"email": seeded_context["email"], "password": seeded_context["password"]})
        token = r.json().get("access_token") or r.json().get("token")
        hdr = {"Authorization": f"Bearer {token}", "X-Active-Context": seeded_context["cid"]}
        r = await c.get(f"/api/contexts/{seeded_context['cid']}/documents/{did}/export-guard", headers=hdr)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["can_export"] is True
        assert data["watermark_required"] is True
        assert data["watermark_label"] == "DRAFT"
        # Now commit and verify guard reports no watermark needed.
        r = await c.patch(f"/api/contexts/{seeded_context['cid']}/documents/{did}", json={
            "state": "committed",
        }, headers=hdr)
        assert r.status_code == 200
        r = await c.get(f"/api/contexts/{seeded_context['cid']}/documents/{did}/export-guard", headers=hdr)
        data = r.json()
        assert data["can_export"] is True
        assert data["watermark_required"] is False


@pytest.mark.asyncio
async def test_e3_intelligence_endpoint_returns_pending_until_extracted(seeded_context):
    """GET /intelligence returns status=pending when no cache row,
    then the regenerate POST kicks off a background task. On a fresh
    doc with no cache, status should be 'pending'."""
    from server import app  # noqa: F401
    from core import db
    did = f"doc-e3-{uuid.uuid4().hex[:8]}"
    await db.documents.insert_one({
        "id": did, "context_id": seeded_context["cid"],
        "name": "Intel test doc",
        "extracted_text": "Body for intelligence extraction.",
        "status": "ready",
        "state": "committed",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/auth/login",
                         json={"email": seeded_context["email"], "password": seeded_context["password"]})
        token = r.json().get("access_token") or r.json().get("token")
        hdr = {"Authorization": f"Bearer {token}", "X-Active-Context": seeded_context["cid"]}
        r = await c.get(f"/api/contexts/{seeded_context['cid']}/documents/{did}/intelligence", headers=hdr)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending"
        # Regenerate should accept the request and return queued.
        r = await c.post(f"/api/contexts/{seeded_context['cid']}/documents/{did}/intelligence/regenerate", headers=hdr)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "queued"


def test_e3_log_section_present_in_home_cleanup_log():
    log = (REPO / "memory" / "sprints" / "HOME_CLEANUP_LOG.md").read_text("utf-8")
    assert "### E.3 — Universal Document Drawer" in log
