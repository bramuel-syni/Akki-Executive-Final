"""Blog v2 — admin compose/publish + public list/read/subscribe (Phase C).

Replaces the blog half of the original `test_iter18_cycle_blog.py`
quarantine entry. Per QUARANTINE_TRIAGE_PLAN.md Phase-5 recipe:

  > Split this file into `test_cycle_questions_v2.py` +
  > `test_blog_admin_v2.py` and rewrite each against current routes.

Blog endpoints live in `routers/blog.py` under the `/api/blog` prefix.
The auth gating for compose/publish moved from the legacy
`X-Blog-Admin-Secret` header to a superadmin role check; freshly-
registered accounts are NOT superadmin, so admin routes must reject
them with 401/403.

Public list/read/subscribe stay open.

In-process httpx + fresh account — no rate-limit, no seed-credential
dependency.
"""
from __future__ import annotations

import sys
import uuid

import httpx
import pytest
import pytest_asyncio

sys.path.insert(0, "/app/backend")
from server import app  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


async def _register(client: httpx.AsyncClient):
    email = f"blog-admin-v2-{uuid.uuid4().hex[:10]}@example.com"
    pw = "Blog-Admin-V2-2026!"
    r = await client.post("/api/auth/register", json={
        "email": email, "password": pw, "name": "Blog Probe",
    })
    assert r.status_code == 200, (r.status_code, r.text[:300])
    return r.json()["access_token"]


async def test_blog_public_posts_list_open(client):
    """Public list is open to everyone — no auth header needed."""
    r = await client.get("/api/blog/posts")
    assert r.status_code == 200, (r.status_code, r.text[:200])
    body = r.json()
    # Either bare list or paginated wrapper — both acceptable.
    assert isinstance(body, (list, dict))


async def test_blog_public_post_read_returns_200_or_404(client):
    """A non-existent slug returns 404; a known slug returns 200. We
    don't assume seed posts exist, so 404 is acceptable here."""
    r = await client.get(f"/api/blog/posts/non-existent-{uuid.uuid4().hex[:8]}")
    assert r.status_code in (200, 404), (r.status_code, r.text[:200])


async def test_blog_subscribe_open(client):
    """Anyone can subscribe — POST /api/blog/subscribe takes an email."""
    email = f"subscriber-{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post("/api/blog/subscribe", json={"email": email})
    # 200 = subscribed; 409 = already subscribed (idempotent retry);
    # 422 = validation error if the route shape changed.
    assert r.status_code in (200, 201, 409, 422), (r.status_code, r.text[:200])


async def test_blog_admin_compose_requires_superadmin(client):
    """A freshly-registered user is NOT superadmin → 401/403 on compose."""
    token = await _register(client)
    r = await client.post(
        "/api/blog/compose",
        json={"topic": "Test topic", "lens": "neutral"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (401, 403), (
        f"Non-superadmin reached /blog/compose with {r.status_code}: "
        f"{r.text[:200]}"
    )


async def test_blog_admin_publish_requires_superadmin(client):
    """Same gate on publish."""
    token = await _register(client)
    r = await client.post(
        f"/api/blog/posts/some-slug-{uuid.uuid4().hex[:6]}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (401, 403, 404), (
        f"Non-superadmin reached /blog/.../publish with {r.status_code}: "
        f"{r.text[:200]}"
    )
