"""Phase E — `/api/help/features` route tests."""
from __future__ import annotations

import sys

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


async def test_help_features_returns_envelope(client):
    """`GET /api/help/features` returns the JSON envelope expected by
    the `/help` React page."""
    r = await client.get("/api/help/features")
    assert r.status_code == 200, (r.status_code, r.text[:200])
    body = r.json()
    for key in ("title", "last_modified", "char_count", "word_count", "markdown"):
        assert key in body, f"envelope missing key: {key!r}"

    assert isinstance(body["title"], str) and body["title"]
    assert isinstance(body["markdown"], str) and len(body["markdown"]) > 1000, (
        "markdown body looks truncated — the help doc is supposed to be "
        f">1 KB, got {len(body['markdown'])} chars"
    )
    assert body["char_count"] == len(body["markdown"])
    assert body["word_count"] > 100, (
        f"word_count={body['word_count']} unreasonably low"
    )
    # ISO-8601 timestamp.
    assert "T" in body["last_modified"]


async def test_help_features_title_extracted_from_h1(client):
    """Title comes from the first H1 in the markdown body."""
    r = await client.get("/api/help/features")
    assert r.status_code == 200
    body = r.json()
    md_first_h1 = next(
        (line[2:].strip() for line in body["markdown"].splitlines() if line.startswith("# ")),
        None,
    )
    assert md_first_h1 is not None, "doc lacks an H1"
    assert body["title"] == md_first_h1, (
        f"title mismatch: api={body['title']!r} vs first-h1={md_first_h1!r}"
    )


async def test_help_features_md_endpoint_returns_raw_markdown(client):
    """`GET /api/help/features.md` returns raw `text/markdown` for
    direct browser/download view."""
    r = await client.get("/api/help/features.md")
    assert r.status_code == 200, (r.status_code, r.text[:200])
    ct = r.headers.get("content-type", "")
    assert ct.startswith("text/markdown"), f"wrong content-type: {ct!r}"
    body_text = r.text
    assert body_text.startswith("# "), "raw md should open with an H1"
    assert len(body_text) > 1000


async def test_help_features_no_auth_required(client):
    """The endpoint is intentionally no-auth (same posture as
    /api/product-features) — confirm no Authorization header is needed."""
    r = await client.get("/api/help/features")
    assert r.status_code == 200, (
        f"endpoint should be open, got {r.status_code}: {r.text[:200]}"
    )
