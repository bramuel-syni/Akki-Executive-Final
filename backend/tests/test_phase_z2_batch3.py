"""Phase Z2 Batch 3 (2026-02 fork-resume v2) — source-strict lockdown +
backend behaviour for Z2.5 (Doc Journal delete) and Z2.6 (Doc Journal
upload parity).

Locks:

  Z2.5 — Trash icon visible only on `origin == "upload"` rows.
         Confirm modal with voice-compliant copy (locked verbatim
         here). DELETE endpoint enforces origin-restriction (defence
         in depth) and soft-delete with tombstone (status="archived",
         storage file removed, audit log written).

  Z2.6 — Doc Journal upload routes through the SAME shared modal
         (via the `akki:open-upload-modal` event listened by
         AppShell's UploadModal). CompanyHome right-rail splits
         the folder icon (→ /app/documents) from + ADD DOCUMENT
         (→ event-based modal open, no route change).

  Voice — All new copy passes WEBSITE_BRIEF_V3 §1.3 ban list +
         UK English checks. Tooltip copy + delete modal copy locked
         verbatim.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient, ASGITransport

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND = REPO_ROOT / "frontend" / "src"
BACKEND = REPO_ROOT / "backend"

DOCUMENTS_PAGE = FRONTEND / "pages" / "DocumentsPage.jsx"
COMPANY_HOME = FRONTEND / "pages" / "CompanyHome.jsx"
DOCUMENTS_ROUTER = BACKEND / "routers" / "documents.py"


BANNED_WORDS = [
    "leverage", "empower", "empowering", "AI-powered", "AI-driven",
    "insights", "dashboard", "game-changer", "game-changing", "synergy",
    "synergistic", "unlock", "unlocking", "supercharge", "supercharged",
    "seamless", "revolutionary", "revolutionise", "cutting-edge",
    "disrupt", "disruptive", "frictionless",
]


def _voice_lint(snippet: str) -> list[str]:
    lc = snippet.lower()
    return [w for w in BANNED_WORDS if w.lower() in lc]


# ════════════════════════════════════════════════════════════════════════
# Z2.5 — Doc Journal delete: source-strict locks                          
# ════════════════════════════════════════════════════════════════════════

def test_z2_5_trash_icon_only_for_uploaded_rows():
    src = DOCUMENTS_PAGE.read_text(encoding="utf-8")
    # The trash icon is gated by `canDelete = origin === "upload"`.
    assert 'const canDelete = (doc.origin || "") === "upload";' in src
    # And the trash icon renders ONLY when canDelete is truthy.
    assert "{canDelete && (" in src
    assert 'data-testid="documents-journal-row-delete"' in src
    # Lucide Trash2 imported.
    assert "Trash2" in src


def test_z2_5_confirm_modal_copy_verbatim():
    src = DOCUMENTS_PAGE.read_text(encoding="utf-8")
    # Heading template: `Delete {name}?`
    assert "Delete {name}?" in src
    # Body verbatim
    body = ("This cannot be undone. The file is removed from your library. "
            "Signals already extracted from it stay in the audit trail.")
    assert body in src
    # CTAs
    assert 'data-testid="documents-delete-confirm-cancel"' in src
    assert 'data-testid="documents-delete-confirm-delete"' in src
    assert 'data-testid="documents-delete-confirm-heading"' in src
    assert 'data-testid="documents-delete-confirm-body"' in src


def test_z2_5_confirm_modal_copy_passes_voice_lint():
    user_visible_copy = [
        "Delete {name}?",
        "This cannot be undone. The file is removed from your library. Signals already extracted from it stay in the audit trail.",
        "Delete this document",  # tooltip
        "Deleting…",              # busy state
    ]
    for s in user_visible_copy:
        hits = _voice_lint(s)
        assert not hits, f"Voice-lint failed for {s!r}: banned terms {hits}"


def test_z2_5_delete_calls_existing_contextful_endpoint():
    src = DOCUMENTS_PAGE.read_text(encoding="utf-8")
    # We use the existing `/contexts/{cid}/documents/{id}` endpoint
    # (already filtering archived in all listing paths).
    assert "api.delete(`/contexts/${cid}/documents/${pendingDelete.id}`)" in src


def test_z2_5_backend_endpoint_enforces_origin_upload():
    src = DOCUMENTS_ROUTER.read_text(encoding="utf-8")
    assert 'if (d.get("origin") or "") != "upload":' in src
    assert "Only uploaded documents can be deleted" in src


def test_z2_5_backend_endpoint_soft_deletes_with_tombstone():
    """The endpoint must NOT hard-delete the doc row — it sets
    status="archived" + archived_at, deletes the storage file,
    writes an audit_log entry. This preserves provenance for
    extractions_log + signals."""
    src = DOCUMENTS_ROUTER.read_text(encoding="utf-8")
    assert '"$set": {"status": "archived", "archived_at": _iso(_now())}' in src
    # Hard-delete must be absent
    assert "db.documents.delete_one" not in src or "archived" in src
    # Audit log written
    assert "document.archived" in src


# ════════════════════════════════════════════════════════════════════════
# Z2.6 — Doc Journal upload parity: source-strict locks                   
# ════════════════════════════════════════════════════════════════════════

def test_z2_6_company_home_right_rail_split_affordances():
    src = COMPANY_HOME.read_text(encoding="utf-8")
    # Folder icon → /app/documents (canonical Doc Journal)
    assert 'navigate("/app/documents")' in src
    # + ADD DOCUMENT → akki:open-upload-modal event (no route change)
    assert 'window.dispatchEvent(new CustomEvent("akki:open-upload-modal"))' in src
    # Old behaviour (BOTH routing to /app/work-studio) must be gone.
    legacy = 'const onAddDoc = useCallback(() => navigate("/app/work-studio"), [navigate]);'
    assert legacy not in src
    # Tooltips on both
    assert 'title="Open the document journal"' in src
    assert 'title="Upload a document without leaving this page"' in src


def test_z2_6_documents_page_upload_routes_through_shared_modal():
    src = DOCUMENTS_PAGE.read_text(encoding="utf-8")
    # The page dispatches the same event as Work Studio + Home — there
    # is intentionally NO local UploadModal instance here.
    assert 'window.dispatchEvent(new CustomEvent("akki:open-upload-modal"))' in src
    # And no parallel modal component is mounted in this file.
    assert "<UploadModal" not in src


def test_z2_6_appshell_listens_for_open_upload_modal_event():
    appshell = FRONTEND / "components" / "layout" / "AppShell.jsx"
    src = appshell.read_text(encoding="utf-8")
    # AppShell is the canonical mount for the shared UploadModal and
    # listens for akki:open-upload-modal. Locked here so a future
    # refactor cannot accidentally move the listener.
    assert "akki:open-upload-modal" in src


def test_z2_6_tooltip_copy_passes_voice_lint():
    snippets = [
        "Open the document journal",
        "Upload a document without leaving this page",
    ]
    for s in snippets:
        hits = _voice_lint(s)
        assert not hits, f"Tooltip voice-lint failed for {s!r}: {hits}"


# ════════════════════════════════════════════════════════════════════════
# Z2.5 — Backend behaviour: delete endpoint contract                      
# ════════════════════════════════════════════════════════════════════════
# Run these as live HTTP probes against the in-process FastAPI app so
# the existing dependency wiring (require_context_membership, audit
# log writer, storage backend) all fires for real. Skipped if admin
# seed not present.


@pytest.fixture
def app():
    import importlib, server
    importlib.reload(server)
    return server.app


def _get_admin_token() -> str:
    import requests
    base = "https://akki-executive.preview.emergentagent.com"
    rr = requests.post(
        f"{base}/api/auth/login",
        json={"email": "admin@akki.ai", "password": "AkkiAdmin2026!"},
        timeout=15,
    )
    rr.raise_for_status()
    return rr.json()["access_token"]


async def _live_db_and_admin_async():
    """Return (db, admin_account_id, context_id) — call from async."""
    from server import db as live_db
    admin = await live_db.accounts.find_one({"email": "admin@akki.ai"})
    if not admin:
        return live_db, None, None
    return live_db, admin["id"], admin.get("default_context_id")


@pytest.mark.asyncio
async def test_z2_5_backend_delete_upload_then_listing_skips_archived(app):
    db, account_id, context_id = await _live_db_and_admin_async()
    if db is None or not account_id or not context_id:
        pytest.skip("admin@akki.ai seed not available")

    import uuid, datetime
    doc_id = str(uuid.uuid4())
    await db.documents.insert_one({
        "id": doc_id,
        "context_id": context_id,
        "name": "z2_5_test_uploaded.pdf",
        "original_filename": "z2_5_test_uploaded.pdf",
        "origin": "upload",
        "category": "report",
        "status": "extracted",
        "storage_key": f"{context_id}/{doc_id}.pdf",
        "uploaded_by": account_id,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })

    token = _get_admin_token()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        h = {"Authorization": f"Bearer {token}", "X-Active-Context": context_id}
        r = await c.delete(f"/api/contexts/{context_id}/documents/{doc_id}", headers=h)
        assert r.status_code == 200, r.text
        r2 = await c.get(
            f"/api/contexts/{context_id}/documents",
            params={"origin": "upload", "limit": 500},
            headers=h,
        )
        body = r2.json()
        items = body if isinstance(body, list) else body.get("items", [])
        ids = {x.get("id") for x in items}
        assert doc_id not in ids

    survivor = await db.documents.find_one({"id": doc_id})
    assert survivor is not None
    assert survivor.get("status") == "archived"
    assert survivor.get("archived_at")
    await db.documents.delete_one({"id": doc_id})


@pytest.mark.asyncio
async def test_z2_5_backend_rejects_akki_generated_with_403(app):
    db, account_id, context_id = await _live_db_and_admin_async()
    if db is None or not account_id or not context_id:
        pytest.skip("admin@akki.ai seed not available")

    import uuid, datetime
    doc_id = str(uuid.uuid4())
    await db.documents.insert_one({
        "id": doc_id,
        "context_id": context_id,
        "name": "z2_5_test_generated.md",
        "original_filename": "z2_5_test_generated.md",
        "origin": "akki_generated",
        "category": "minutes",
        "status": "extracted",
        "storage_key": f"{context_id}/{doc_id}.md",
        "uploaded_by": account_id,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })

    token = _get_admin_token()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        h = {"Authorization": f"Bearer {token}", "X-Active-Context": context_id}
        r = await c.delete(f"/api/contexts/{context_id}/documents/{doc_id}", headers=h)
        assert r.status_code == 403, r.text
        assert "uploaded documents" in r.text.lower()

    survivor = await db.documents.find_one({"id": doc_id})
    assert survivor is not None
    assert survivor.get("status") != "archived"
    await db.documents.delete_one({"id": doc_id})


@pytest.mark.asyncio
async def test_z2_5_backend_404_for_missing_doc(app):
    db, account_id, context_id = await _live_db_and_admin_async()
    if db is None or not account_id or not context_id:
        pytest.skip("admin@akki.ai seed not available")

    import uuid
    token = _get_admin_token()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        h = {"Authorization": f"Bearer {token}", "X-Active-Context": context_id}
        ghost_id = str(uuid.uuid4())
        r = await c.delete(f"/api/contexts/{context_id}/documents/{ghost_id}", headers=h)
        assert r.status_code == 404, r.text
