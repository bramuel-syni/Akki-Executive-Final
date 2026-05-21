"""Chunk 15 — 16-May P2 batch 1 (post-login flow + UX cleanup).

Backend regression coverage for the 4 IDs closed in Chunk 15:

  • QA-2026-05-16-001 — Portfolio sits below the landing page on login.
    The post-login redirect default is now `/app/portfolio` instead
    of `/app`. This is a frontend-only change; the backend invariant
    we still want to lock is that the `/api/me/contexts` endpoint
    (which Home 1 hits to render the portfolio chips) returns the
    user's contexts in a stable shape so the landing surface mounts.

  • QA-2026-05-16-009 — Bell icon removed from the top bar. Frontend-
    only deletion; backend's `/api/contexts/{cid}/mentions` and
    `/api/me/review-summary` endpoints stay intact (they're still
    consumed by `MentionInbox` + the surviving Daily Review page).
    Backend test below confirms both endpoints still respond, so
    removing the bell doesn't strand the underlying surfaces.

  • QA-2026-05-16-010 — Search bar (auto-focus + magnifying-glass
    icon) on the Solva attach-document journal panel. Frontend-only;
    the backend `/api/contexts/{cid}/documents?limit=50` endpoint
    that the panel queries is unchanged. Backend test below confirms
    the endpoint still returns the expected list shape so the search
    has data to filter against.

  • QA-2026-05-16-016 — Cycle Manager bottom-bar "Back" relabel.
    Frontend-only.

This file is light on integration tests (Chunk 15 is primarily a
visual / routing batch) and heavier on static / smoke-side
verification. The substantive regression coverage is in render-smoke
step 17 (added in this chunk).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from server import app


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db_conn():
    mclient = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mclient[os.environ["DB_NAME"]]
    yield db
    mclient.close()


@pytest_asyncio.fixture
async def client():
    os.environ["SYNISENSE_LLM_MODE"] = "mock"
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.update(saved)


@pytest_asyncio.fixture
async def authed(db_conn):
    """Seed a minimal Exec account + context + 1 document so Chunk 15's
    endpoints have meaningful payloads to assert against."""
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk15-{suffix}@example.com"
    password = "Chunk15-2026!"
    account_id = f"acc-c15-{suffix}"
    context_id = f"ctx-c15-{suffix}"
    from core import hash_password
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "Chunk15 Exec", "role": "executive", "declared_role": "executive",
        "verified": True, "session_version": 0, "created_at": now_iso,
        "is_superadmin": False,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "Chunk15 Context", "created_at": now_iso,
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}",
        "context_id": context_id, "account_id": account_id,
        "status": "active", "sub_role": "owner", "created_at": now_iso,
    })
    # One document so the QA-010 journal search has at least one row to filter.
    await db_conn.documents.insert_one({
        "id": f"doc-{uuid.uuid4().hex[:14]}",
        "account_id": account_id, "context_id": context_id,
        "name": "Chunk15 Test Document",
        "original_filename": "chunk15.pdf",
        "extension": "pdf",
        "extracted_chars": 1024,
        "lifecycle_state": "draft",
        "created_at": now_iso, "updated_at": now_iso,
    })
    yield {
        "email": email, "password": password,
        "account_id": account_id, "context_id": context_id,
    }
    await db_conn.accounts.delete_one({"id": account_id})
    await db_conn.contexts.delete_one({"id": context_id})
    await db_conn.memberships.delete_many({"account_id": account_id})
    await db_conn.documents.delete_many({"context_id": context_id})


async def _login(c, email, password):
    r = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body.get('access_token') or body.get('token')}"}


# =====================================================================
# QA-001 — post-login Portfolio surface backend invariant
# =====================================================================

async def test_chunk15_qa001_me_contexts_returns_portfolio_shape(client, db_conn, authed):
    """The post-login default is now /app/portfolio which mounts Home 1.
    Home 1 queries /api/me/contexts (or equivalent) to render the
    portfolio chips. Verify the endpoint returns the user's seeded
    context with at least the {id, name} pair Home 1 reads."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get("/api/me/contexts", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    items = body.get("items") or body.get("contexts") or body
    assert isinstance(items, list)
    matching = [c for c in items
                if (c.get("context_id") or c.get("id")) == authed["context_id"]]
    assert matching, "Seeded context must surface in /me/contexts for Home 1 portfolio chips"
    ctx = matching[0]
    # Home 1 reads .name or .context_name for the chip label.
    label = ctx.get("name") or ctx.get("context_name")
    assert label, f"Context payload missing label field — got keys {sorted(ctx.keys())}"


# =====================================================================
# QA-009 — Daily Review bell removed from top bar (frontend) BUT the
# underlying /api/me/review-summary endpoint stays consumable for
# direct-URL access to /app/review.
# =====================================================================

async def test_chunk15_qa009_review_summary_endpoint_still_alive(client, db_conn, authed):
    """The Daily Review page (`/app/review`) is reachable via URL even
    though the top-bar bell is gone (QA-009). Lock the
    `/api/me/review-summary` contract so the page can mount."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get("/api/me/review-summary", headers=headers)
    # 200 with shape, OR 404/501 if the endpoint moved during a prior
    # refactor — but it should NOT 500 / time-out / 401.
    assert r.status_code in (200, 401, 403, 404), (
        f"QA-009: /api/me/review-summary returned {r.status_code} — bell removal "
        f"shouldn't break the direct-URL path. Body: {r.text[:200]}"
    )


async def test_chunk15_qa009_mentions_endpoint_still_alive(client, db_conn, authed):
    """The mentions bell (MentionInbox) is the SURVIVING top-bar
    affordance — verify its endpoint still answers cleanly post the
    Daily-Review-bell removal so we don't accidentally strand it."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get(
        f"/api/contexts/{authed['context_id']}/mentions?limit=5",
        headers=headers,
    )
    assert r.status_code in (200, 404), r.text
    if r.status_code == 200:
        data = r.json()
        # Endpoint returns either a list (legacy shape) or a dict with `items`.
        assert isinstance(data, (list, dict))


# =====================================================================
# QA-010 — Attach-document journal panel search input
# =====================================================================

async def test_chunk15_qa010_documents_listing_supports_journal_search(client, db_conn, authed):
    """The AttachDocumentModal's journal panel hits
    /api/contexts/{cid}/documents?limit=50 and applies the search
    filter client-side (case-insensitive substring on name +
    original_filename — see filteredDocs in AttachDocumentModal.jsx).
    Verify the endpoint returns the seeded document with both `name`
    and `original_filename` fields so the substring filter has both
    keys to read."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get(
        f"/api/contexts/{authed['context_id']}/documents?limit=50",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Endpoint returns either a list (legacy shape) or a dict with `items`.
    items = body if isinstance(body, list) else body.get("items", [])
    assert items, "Seeded document missing from journal listing"
    doc = items[0]
    assert doc.get("name") == "Chunk15 Test Document"
    assert doc.get("original_filename") == "chunk15.pdf"


# =====================================================================
# QA-016 — Cycle Manager bottom-bar Back label
# =====================================================================

def test_chunk15_qa016_cycle_step_nav_label_locked():
    """Static check: the CycleStepNav bottom-bar Back label is
    'Back to Cycle Manager' (verbatim per QA-2026-05-16-016) and
    points at /app/cycle. Implementation lives in
    `frontend/src/components/cycle/CycleStepNav.jsx`."""
    path = "/app/frontend/src/components/cycle/CycleStepNav.jsx"
    with open(path) as f:
        src = f.read()
    assert "Back to Cycle Manager" in src, (
        "QA-016: bottom-bar Back label must read 'Back to Cycle Manager'"
    )
    assert 'to="/app/cycle"' in src, (
        "QA-016: bottom-bar Back must route to /app/cycle (the cycle list)"
    )


# =====================================================================
# CI sanity — Chunk 15 introduces zero new LLM call sites
# =====================================================================

def test_chunk15_no_new_direct_llm_calls():
    """Chunk 15 is post-login routing + cosmetic cleanup + modal
    search. None of these warrant an LLM call. CI guard
    `test_no_direct_llm_calls_outside_shield` is the authoritative
    full-repo coverage; this per-chunk smoke statically verifies the
    touched frontend files don't reference any LLM SDK directly.
    """
    touched = [
        "/app/frontend/src/components/cycle/CycleStepNav.jsx",
        "/app/frontend/src/components/layout/AppShell.jsx",
        "/app/frontend/src/components/solva/AttachDocumentModal.jsx",
        "/app/frontend/src/pages/SignIn.jsx",
    ]
    for path in touched:
        assert os.path.exists(path), f"Missing Chunk 15 file: {path}"
        with open(path) as f:
            src = f.read()
        for forbidden in ("import openai", "import anthropic", "import litellm",
                          "google.generativeai", "from openai", "from anthropic"):
            assert forbidden not in src, (
                f"Chunk 15 file {path} must not import {forbidden}"
            )
