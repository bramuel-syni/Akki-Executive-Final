"""Wave 5 regression — contextless chat E2E.

Locks the locked Wave 5 contract end-to-end: General RAG chat is the
DEFAULT mode. POST /chats, GET /chats/{id}, PATCH /chats/{id}, and
DELETE /chats/{id} ALL work without the X-Active-Context header.
Only `/chats/{id}/attach` (and any other endpoint that legitimately
requires a context, like uploads scoped under /contexts/{cid}/...) is
allowed to enforce the header.

Bug history captured in this test (so we don't regress again):

    Wave 5 originally lifted X-Active-Context from `create_chat` +
    `send_message`. The follow-up `GET /chats/{id}` + `PATCH` +
    `restore` were missed — they still called `_require_active_context`
    which 400'd general chats. Frontend flow:
       POST /chats → 200 (no header) →
       setActiveId(data.id) → GET /chats/{id} (no header) → 400 →
       toast "X-Active-Context header required."
    Visible to the user as a red toast immediately after "Start a
    conversation."
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ─────────────────────────────────────────────────────────────────
# A. Lifecycle — no X-Active-Context, all 4 mutations succeed.
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wave5_create_get_patch_delete_no_header():
    """End-to-end on the chat lifecycle without X-Active-Context."""
    from server import app  # type: ignore
    from core import db, get_current_account  # type: ignore

    async def _fake_user():
        # Match an existing account so we don't bypass DB constraints.
        existing = await db.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0})
        return existing or {"id": "wave5-user", "email": "admin@akki.ai", "is_superadmin": True}

    app.dependency_overrides[get_current_account] = _fake_user
    chat_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            # ── Create — no X-Active-Context header.
            r1 = await c.post("/api/chats", json={
                "title": "Wave5 lifecycle probe",
                "model_id": "claude-sonnet-4-5",
                "shielding_policy": "auto",
            })
            assert r1.status_code == 200, (
                f"Wave 5 — create_chat without X-Active-Context must 200, "
                f"got {r1.status_code} → {r1.text}"
            )
            payload = r1.json()
            chat_id = payload["id"]
            assert payload["context_id"] is None, (
                "General chat must persist with context_id=None"
            )

            # ── GET — no X-Active-Context header. THIS IS THE BUG PATH.
            r2 = await c.get(f"/api/chats/{chat_id}")
            assert r2.status_code == 200, (
                f"Wave 5 — get_chat without X-Active-Context must 200 for a "
                f"general chat, got {r2.status_code} → {r2.text}. THIS IS THE "
                f"REGRESSION the dispatch fixed — `_require_active_context` "
                f"was incorrectly gating general-chat reads."
            )

            # ── PATCH — no X-Active-Context header.
            r3 = await c.patch(f"/api/chats/{chat_id}", json={"title": "renamed"})
            assert r3.status_code == 200, (
                f"Wave 5 — patch_chat without X-Active-Context must 200 for "
                f"a general chat, got {r3.status_code} → {r3.text}"
            )
            assert r3.json().get("title") == "renamed"

            # ── DELETE — no X-Active-Context header.
            r4 = await c.delete(f"/api/chats/{chat_id}")
            assert r4.status_code == 200, (
                f"Wave 5 — soft_delete without X-Active-Context must 200 for "
                f"a general chat, got {r4.status_code} → {r4.text}"
            )
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        if chat_id:
            # Belt-and-suspenders cleanup.
            await db.chats.delete_one({"id": chat_id})
            await db.chat_messages.delete_many({"chat_id": chat_id})


# ─────────────────────────────────────────────────────────────────
# B. Negative direction — context-scoped endpoints must still gate.
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wave5_context_scoped_paths_remain_gated():
    """Confirm we did NOT accidentally lift X-Active-Context enforcement
    on endpoints that legitimately require a context. Document upload
    is scoped under /contexts/{cid}/... structurally — but the
    `/chats/{id}/attach` endpoint is a chat-side context binder that
    must still reject general-chat calls without the context header.
    """
    from server import app  # type: ignore
    from core import db, get_current_account  # type: ignore

    async def _fake_user():
        existing = await db.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0})
        return existing or {"id": "wave5-user", "email": "admin@akki.ai", "is_superadmin": True}

    app.dependency_overrides[get_current_account] = _fake_user
    chat_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            # Create a general chat first.
            r1 = await c.post("/api/chats", json={
                "title": "Wave5 negative probe",
                "model_id": "claude-sonnet-4-5",
                "shielding_policy": "auto",
            })
            assert r1.status_code == 200
            chat_id = r1.json()["id"]

            # Attach endpoint — REQUIRES X-Active-Context per docstring
            # (intentional gate; documented at lines ~640-672 of chat.py).
            # Accept any 4xx — header-required (400) OR validation gate
            # (422) both prove the endpoint isn't accepting general-chat
            # traffic without scrutiny.
            r2 = await c.post(
                f"/api/chats/{chat_id}/attach",
                json={"linked_context": {"ctx_type": "document", "ctx_id": "x"}},
            )
            assert 400 <= r2.status_code < 500, (
                f"Wave 5 — attach must STILL gate general-chat calls "
                f"(legitimate gate; not relaxed by this dispatch). Got "
                f"{r2.status_code} → {r2.text}"
            )
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        if chat_id:
            await db.chats.delete_one({"id": chat_id})


# ─────────────────────────────────────────────────────────────────
# C. Source-strict — no _require_active_context calls remain on the
#    chat lifecycle mutations (create / get / patch / delete /
#    soft-delete / restore).
# ─────────────────────────────────────────────────────────────────


def test_wave5_lifecycle_endpoints_use_optional_header():
    src = (BACKEND / "routers" / "chat.py").read_text(encoding="utf-8")

    # Locate each handler block and confirm it uses the optional
    # `request.headers.get(ACTIVE_CONTEXT_HEADER) or None` pattern,
    # NOT the strict `_require_active_context(request)` call.
    handler_names = (
        "async def get_chat(",
        "async def patch_chat(",
        "async def soft_delete_chat(",
        "async def stream_message(",
        "async def send_message(",
        "async def create_chat(",
    )
    for handler in handler_names:
        idx = src.find(handler)
        assert idx > 0, f"Handler {handler!r} not found in chat.py"
        # Inspect the next ~1500 chars (the body).
        block = src[idx:idx + 1500]
        assert "_require_active_context(request)" not in block, (
            f"Wave 5 regression — {handler.strip()} still calls "
            f"`_require_active_context(request)`. General chats must "
            f"work without the header. Use the optional pattern: "
            f"`active_ctx = request.headers.get(ACTIVE_CONTEXT_HEADER) "
            f"or None`."
        )
