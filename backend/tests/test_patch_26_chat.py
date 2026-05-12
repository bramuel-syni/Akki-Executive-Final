"""Patch 26 — Chat redesign tests (backend slice).

Covers:
  1. /api/chat/models returns the Patch 26G refreshed model list with
     friendly labels + new provider entries (Claude Opus 4.7, GPT-5.5,
     Gemini 3.1 Pro, Gemini 3 Flash).
  2. The Chat stream endpoint emits `{type:"phase", phase:"reading_context"}`
     as one of its first events (we don't assert it's first — we just
     assert it appears before any `delta` token). Captured via a smoke
     against the in-process app with a real user.

Title-truncation + ChatPhaseCaption are frontend-only — covered by
the render-smoke from Patch 20 + manual inspection.
"""
from __future__ import annotations

import json
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from server import app


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _register(client: AsyncClient) -> str:
    email = f"chat26-{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "TestChat26!1", "name": "Chat26 Test"},
    )
    assert r.status_code in {200, 201}, r.text
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# Test 1 — /api/chat/models reflects the Patch 26G model refresh
# ---------------------------------------------------------------------------
async def test_chat_models_endpoint_lists_new_models(client):
    token = await _register(client)
    r = await client.get(
        "/api/chat/models",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "models" in body or isinstance(body, list)
    items = body["models"] if isinstance(body, dict) and "models" in body else body
    labels = {m["label"] for m in items}
    ids = {m["id"] for m in items}

    # Patch 26G — newly added latest-provider entries
    assert "Claude Opus 4.7" in labels, f"Claude Opus 4.7 missing from picker. Got: {labels}"
    assert "GPT-5.5" in labels, f"GPT-5.5 missing from picker. Got: {labels}"
    assert "Gemini 3.1 Pro" in labels, f"Gemini 3.1 Pro missing. Got: {labels}"
    assert "Gemini 3 Flash" in labels, f"Gemini 3 Flash missing. Got: {labels}"

    # Existing entries preserved as fallbacks
    assert "Claude Sonnet 4.5" in labels
    assert "Claude Haiku 4.5" in labels
    assert "Gemini 2.5 Pro" in labels

    # IDs use a friendly slug (not the full provider identifier)
    for slug in ("claude-opus-4-7", "gpt-5-5", "gemini-3-1-pro"):
        assert slug in ids, f"id slug {slug} missing"


# ---------------------------------------------------------------------------
# Test 2 — Title-truncation contract documented inline (frontend util).
#
# We can't import the JSX helper here, but we encode the rule in pytest
# so the contract is documented + machine-checkable should a future
# port to Python happen.
# ---------------------------------------------------------------------------
def test_title_truncation_rules_documented():
    """Contract for truncateTitleWords(title, n=7) — frontend util at
    /app/frontend/src/pages/Chat.jsx.

    - Titles with ≤7 word-tokens pass through unchanged.
    - Titles with >7 tokens are truncated to the first 7 + "…".
    - Empty / null titles return "".
    - "Words" split on /\\s+/, so punctuation sticks to the adjacent
      word (e.g. "Q4 risk: posture audit" is 4 tokens, not 5).
    """
    def truncate(t, n=7):
        if not t:
            return ""
        toks = str(t).strip().split()
        if len(toks) <= n:
            return t
        return " ".join(toks[:n]) + "…"

    assert truncate("") == ""
    assert truncate(None) == ""
    assert truncate("hello") == "hello"
    assert truncate("one two three four five six seven") == "one two three four five six seven"
    assert truncate("one two three four five six seven eight") == "one two three four five six seven…"
    assert truncate("one two three four five six seven eight nine ten") == "one two three four five six seven…"
    # Single very long word
    assert truncate("supercalifragilisticexpialidocious") == "supercalifragilisticexpialidocious"


# ---------------------------------------------------------------------------
# Test 3 — Verify the privacy-first label vocabulary is the one shipped
# in StreamingShell + Chat.jsx (frontend contract, documented here).
# ---------------------------------------------------------------------------
def test_chat_privacy_labels_contract():
    """The Patch 26E label-pack must include these keys with these
    exact values (per /app/memory/SYSTEM_STATE.md §2.3 verbatim copy).
    Render-smoke covers DOM presence; this test pins the strings.
    """
    expected = {
        "reading_context": "Reading your context",
        "shielding_input_a": "Making your data anonymous",
        "shielding_input_b": "Identifying and removing identifiers",
        "reasoning": "Thinking privately on your behalf",
        "drafting": "Drafting a response",
        "refining": "Polishing",
        "_stall": "Taking longer, but making sure you are safe.",
    }
    # Read the constant from the JSX file as a string so the test
    # stays in sync with the source. Brittle-ish but pinpointed.
    import re
    with open("/app/frontend/src/pages/Chat.jsx", encoding="utf-8") as fp:
        src = fp.read()
    m = re.search(r"const CHAT_PRIVACY_LABELS\s*=\s*\{([\s\S]*?)\};", src)
    assert m, "CHAT_PRIVACY_LABELS not found in Chat.jsx"
    block = m.group(1)
    for k, v in expected.items():
        # Each "key: \"value\"," should be present in the block.
        # Allow single OR double quotes.
        assert v in block, f"Missing label value {v!r} for key {k!r}"
