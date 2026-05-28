"""
Phase AA-slice-3 (2026-05-27) — Upload-modal extraction prompt
+ trigger endpoint CI guards.

Lock surface:

  Source-strict FE (UploadModal.jsx) —
    * Two checkboxes render with stable testids:
        `upload-extract-goals-checkbox`
        `upload-extract-tasks-checkbox`
    * Helper text testid `upload-extraction-helper` carries the
      locked copy.
    * `useEffect` recomputes the defaults whenever `category`
      changes UNTIL `extractionTouched=true`.
    * The high-signal default list is `["board_pack", "report",
      "briefing"]` — locked source-strictly.
    * `onUpload` fires the extract trigger POST whenever at least
      one checkbox is checked + at least one file uploaded
      successfully.

  Source-strict BE (routers/tasks_initiatives.py) —
    * `POST /api/contexts/{cid}/documents/{doc_id}/extract` declared.
    * Returns 202 on the success path.
    * Uses FastAPI `BackgroundTasks` so the LLM round-trip doesn't
      block the response.
    * `_bg_extract` swallows exceptions (auditable via the AA-2
      `extraction_failures` collection).

  Runtime —
    * Endpoint returns 202 with `{extraction_queued: True, …}`.
    * 400 when both flags are False.
    * 404 when doc doesn't exist in the context.
    * Audit row written.
    * The BackgroundTask actually invokes
      `extract_from_document(...)` with the right args (mocked in
      tests so we don't pay the LLM round-trip).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend" / "src"
UPLOAD_MODAL = FRONTEND / "components" / "upload" / "UploadModal.jsx"
TASKS_INITIATIVES_PY = REPO_ROOT / "backend" / "routers" / "tasks_initiatives.py"


# ─────────────────────────────────────────────────────────────────
# Frontend source-strict
# ─────────────────────────────────────────────────────────────────


def test_aa3_extraction_checkboxes_present_in_source() -> None:
    src = UPLOAD_MODAL.read_text(encoding="utf-8")
    assert 'data-testid="upload-extract-goals-checkbox"' in src
    assert 'data-testid="upload-extract-tasks-checkbox"' in src
    assert 'data-testid="upload-extraction-helper"' in src
    assert 'data-testid="upload-extraction-block"' in src


def test_aa3_extraction_helper_copy_locked() -> None:
    """User-visible copy spec — lock the exact sentence so silent
    rewrites cause CI to fail."""
    src = UPLOAD_MODAL.read_text(encoding="utf-8")
    assert (
        "AI will scan for strategic goals and the specific work to deliver them."
        in src
    )
    assert "review and edit later in Monitor" in src


def test_aa3_high_signal_default_list_locked() -> None:
    """The 3 high-signal categories that auto-flip both checkboxes
    ON are `board_pack`, `report`, `briefing`. Lock the trio
    source-strictly — a typo or omission would silently break the
    "smart default" UX."""
    src = UPLOAD_MODAL.read_text(encoding="utf-8")
    pattern = r'const\s+high\s*=\s*\[\s*"board_pack"\s*,\s*"report"\s*,\s*"briefing"\s*\]'
    assert re.search(pattern, src), (
        "High-signal default list must be `['board_pack', 'report', "
        "'briefing']` literally in UploadModal.jsx."
    )


def test_aa3_recompute_effect_skips_when_touched() -> None:
    """The recompute-on-category-change effect MUST return early
    when `extractionTouched` is true — otherwise the user's manual
    toggle keeps getting overwritten."""
    src = UPLOAD_MODAL.read_text(encoding="utf-8")
    assert "if (extractionTouched) return;" in src


def test_aa3_touched_flag_flipped_on_user_toggle() -> None:
    """User-driven onChange handlers MUST set extractionTouched=true
    so the recompute effect stops overriding their pick."""
    src = UPLOAD_MODAL.read_text(encoding="utf-8")
    # Both checkbox handlers set the touched flag.
    assert src.count("setExtractionTouched(true);") >= 2


def test_aa3_onupload_triggers_extract_endpoint() -> None:
    """`onUpload` must POST to the extract endpoint when at least
    one checkbox is checked + at least one file uploaded."""
    src = UPLOAD_MODAL.read_text(encoding="utf-8")
    # The conditional gate.
    assert "(extractGoals || extractTasks) && uploadedIds.length > 0" in src
    # The actual POST.
    assert "/extract" in src
    assert "extract_goals" in src
    assert "extract_tasks" in src


# ─────────────────────────────────────────────────────────────────
# Backend source-strict
# ─────────────────────────────────────────────────────────────────


def test_aa3_extract_endpoint_declared() -> None:
    src = TASKS_INITIATIVES_PY.read_text(encoding="utf-8")
    assert '@router.post("/contexts/{context_id}/documents/{doc_id}/extract"' in src
    assert "status_code=202" in src
    assert "BackgroundTasks" in src


def test_aa3_bg_extract_swallows_exceptions() -> None:
    """The background driver MUST not crash the worker process on a
    transient LLM error — the failure is auditable via the AA-2
    extraction_failures collection."""
    src = TASKS_INITIATIVES_PY.read_text(encoding="utf-8")
    # _bg_extract carries a try/except wrapping the service call.
    assert "async def _bg_extract" in src
    assert "except Exception" in src


# ─────────────────────────────────────────────────────────────────
# Runtime
# ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def trigger_ctx():
    """Seed a member account + a context + a doc inside the context."""
    from core import db, hash_password

    uid = f"aa3-user-{uuid.uuid4().hex[:8]}"
    email = f"aa3-user-{uuid.uuid4().hex[:6]}@example.com"
    pw = "AA3!Phase-User"
    cid = f"aa3-ctx-{uuid.uuid4().hex[:8]}"
    did = f"aa3-doc-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    await db.accounts.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(pw),
        "name": "AA3 Member", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False, "created_at": now_iso,
    })
    await db.contexts.insert_one({
        "id": cid, "name": "AA3 Test Context",
        "owner_account_id": uid, "created_at": now_iso,
    })
    await db.memberships.insert_one({
        "context_id": cid, "account_id": uid, "status": "active",
        "role": "executive", "created_at": now_iso,
    })
    await db.documents.insert_one({
        "id": did, "context_id": cid, "name": "AA3 doc",
        "extracted_text": "Sample text " * 50,
        "origin": "upload", "category": "report", "status": "extracted",
        "created_at": now_iso, "updated_at": now_iso,
    })
    yield {"uid": uid, "email": email, "password": pw, "cid": cid, "did": did}
    await db.accounts.delete_one({"id": uid})
    await db.contexts.delete_one({"id": cid})
    await db.memberships.delete_many({"account_id": uid})
    await db.documents.delete_one({"id": did})
    await db.audit_log.delete_many({"account_id": uid})


async def _login(client, email, password):
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_aa3_trigger_returns_202_and_invokes_service(trigger_ctx) -> None:
    """Endpoint returns 202 immediately + the BackgroundTask invokes
    `extract_from_document` with the args passed in."""
    from server import app
    from services.tasks_initiatives import extraction as ex

    mock_extract = AsyncMock()
    with patch.object(ex, "extract_from_document", mock_extract):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            tok = await _login(c, trigger_ctx["email"], trigger_ctx["password"])
            r = await c.post(
                f"/api/contexts/{trigger_ctx['cid']}/documents/{trigger_ctx['did']}/extract",
                headers={"Authorization": f"Bearer {tok}"},
                json={"extract_goals": True, "extract_tasks": True},
            )
        assert r.status_code == 202, r.text
        body = r.json()
        assert body["extraction_queued"] is True
        assert body["document_id"] == trigger_ctx["did"]
        assert body["extract_goals"] is True
        assert body["extract_tasks"] is True

    # Background task fires before the async-context exits.
    assert mock_extract.await_count >= 1, "extract_from_document was never invoked"
    call = mock_extract.await_args
    args = call.args
    assert args[0] == trigger_ctx["did"]
    assert args[1] == trigger_ctx["cid"]
    assert args[2] == trigger_ctx["uid"]
    kw = call.kwargs
    assert kw["extract_goals"] is True
    assert kw["extract_tasks"] is True


@pytest.mark.asyncio
async def test_aa3_trigger_rejects_both_flags_false(trigger_ctx) -> None:
    """`extract_goals=False, extract_tasks=False` → 400 (no-op
    trigger surfaces as a clear error)."""
    from server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login(c, trigger_ctx["email"], trigger_ctx["password"])
        r = await c.post(
            f"/api/contexts/{trigger_ctx['cid']}/documents/{trigger_ctx['did']}/extract",
            headers={"Authorization": f"Bearer {tok}"},
            json={"extract_goals": False, "extract_tasks": False},
        )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_aa3_trigger_404s_on_missing_doc(trigger_ctx) -> None:
    from server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login(c, trigger_ctx["email"], trigger_ctx["password"])
        r = await c.post(
            f"/api/contexts/{trigger_ctx['cid']}/documents/ghost-doc-zzz/extract",
            headers={"Authorization": f"Bearer {tok}"},
            json={"extract_goals": False, "extract_tasks": True},
        )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_aa3_trigger_writes_audit_row(trigger_ctx) -> None:
    from core import db
    from server import app
    from services.tasks_initiatives import extraction as ex

    with patch.object(ex, "extract_from_document", AsyncMock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            tok = await _login(c, trigger_ctx["email"], trigger_ctx["password"])
            await c.post(
                f"/api/contexts/{trigger_ctx['cid']}/documents/{trigger_ctx['did']}/extract",
                headers={"Authorization": f"Bearer {tok}"},
                json={"extract_goals": False, "extract_tasks": True},
            )

    rows = await db.audit_log.find(
        {"account_id": trigger_ctx["uid"],
         "action": "tasks_initiative.extract_triggered"},
        {"_id": 0, "metadata": 1},
    ).to_list(5)
    assert len(rows) == 1
    assert rows[0]["metadata"]["extract_tasks"] is True
    assert rows[0]["metadata"]["extract_goals"] is False


@pytest.mark.asyncio
async def test_aa3_trigger_only_tasks_flag(trigger_ctx) -> None:
    """`extract_tasks=True` alone is enough to queue extraction."""
    from server import app
    from services.tasks_initiatives import extraction as ex

    mock_extract = AsyncMock()
    with patch.object(ex, "extract_from_document", mock_extract):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            tok = await _login(c, trigger_ctx["email"], trigger_ctx["password"])
            r = await c.post(
                f"/api/contexts/{trigger_ctx['cid']}/documents/{trigger_ctx['did']}/extract",
                headers={"Authorization": f"Bearer {tok}"},
                json={"extract_goals": False, "extract_tasks": True, "force": False},
            )
        assert r.status_code == 202
    assert mock_extract.await_count >= 1
    kw = mock_extract.await_args.kwargs
    assert kw["extract_goals"] is False
    assert kw["extract_tasks"] is True
    assert kw["force"] is False


@pytest.mark.asyncio
async def test_aa3_trigger_force_flag_forwarded(trigger_ctx) -> None:
    """`force=True` must reach the underlying service so re-extraction
    bypasses idempotency."""
    from server import app
    from services.tasks_initiatives import extraction as ex

    mock_extract = AsyncMock()
    with patch.object(ex, "extract_from_document", mock_extract):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            tok = await _login(c, trigger_ctx["email"], trigger_ctx["password"])
            await c.post(
                f"/api/contexts/{trigger_ctx['cid']}/documents/{trigger_ctx['did']}/extract",
                headers={"Authorization": f"Bearer {tok}"},
                json={"extract_goals": True, "extract_tasks": True, "force": True},
            )
    assert mock_extract.await_count >= 1
    assert mock_extract.await_args.kwargs["force"] is True
