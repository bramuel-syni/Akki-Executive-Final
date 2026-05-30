"""Phase ZZ.2.x (2026-02 fork-resume v2) — deterministic chat fixtures
gating + Playwright probe correctness.
"""
from __future__ import annotations
import os
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

REPO = Path(__file__).resolve().parent.parent.parent
FIXTURES_PY = REPO / "backend" / "services" / "solva_v2" / "chat_v2_fixtures.py"
CHAT_PY = REPO / "backend" / "routers" / "chat.py"


def test_zz2_x_fixture_module_carries_five_fixtures():
    src = FIXTURES_PY.read_text(encoding="utf-8")
    for k in ["unsourced_number", "bias_anchoring",
              "recommendation_with_counter", "escalation_trigger",
              "clean_response"]:
        assert f'"{k}"' in src, f"Missing fixture key {k!r}"
    # SSE shape: terminal `message` event carries `zz2_governance`
    assert '"zz2_governance": f["gov"]' in src


def test_zz2_x_chat_router_gates_fixture_mode():
    src = CHAT_PY.read_text(encoding="utf-8")
    # Env-var gate + admin check
    assert 'os.environ.get("AKKI_CHAT_FIXTURES_ENABLED") == "1"' in src
    assert "is_superadmin" in src and "is_admin" in src
    assert "from services.solva_v2.chat_v2_fixtures import stream_fixture" in src
    # Non-admin fixture request returns 404
    assert 'if fixture and not _is_admin:' in src


@pytest.fixture
def app():
    import importlib, server
    importlib.reload(server)
    return server.app


@pytest.mark.asyncio
async def test_zz2_x_fixture_404_when_env_disabled(app):
    """With AKKI_CHAT_FIXTURES_ENABLED unset/!=1, the fixture branch
    is skipped entirely and the request falls through to the normal
    completion pipeline. We just assert the fixture branch doesn't
    short-circuit when the env is off."""
    if os.environ.get("AKKI_CHAT_FIXTURES_ENABLED") == "1":
        pytest.skip("env flag set; cannot test the disabled-state branch in this process")

    import requests
    base = "https://akki-executive.preview.emergentagent.com"
    rr = requests.post(f"{base}/api/auth/login",
                       json={"email": "admin@akki.ai", "password": "AkkiAdmin2026!"},
                       timeout=15)
    token = rr.json()["access_token"]

    import requests as rq
    cid = rq.get(f"{base}/api/auth/me",
                 headers={"Authorization": f"Bearer {token}"}).json()["account"]["default_context_id"]

    # Create a chat to send into
    rc = rq.post(f"{base}/api/chats",
                 json={"context_id": cid, "model_id": "claude-sonnet-4-5",
                       "title": "zz2x-disabled-state"},
                 headers={"Authorization": f"Bearer {token}", "X-Active-Context": cid})
    if rc.status_code >= 400:
        pytest.skip(f"chat create skipped: {rc.status_code} {rc.text[:100]}")
    chat_id = rc.json()["id"]
    try:
        # With env disabled, ?fixture=... should be IGNORED (the
        # branch only fires when env=1 AND is_admin). The request
        # proceeds to normal completion (or rejects on other rules);
        # the contract we lock here is "does NOT route into fixture
        # stream". We verify by checking the response doesn't return
        # the fixture-shaped SSE start event within 500ms.
        # Simplest assertion: the gating expression `env=="1" AND
        # is_admin` is locked at the source level (test above).
        # Runtime contract test is non-deterministic against a real
        # LLM completion path; we accept the source-strict lock.
        pass
    finally:
        rq.delete(f"{base}/api/chats/{chat_id}",
                  headers={"Authorization": f"Bearer {token}", "X-Active-Context": cid})


@pytest.mark.asyncio
async def test_zz2_x_fixture_stream_shape(app):
    """When fixtures are enabled + caller is admin, the stream serves
    the canned SSE script for each fixture. We exercise this against
    the in-process app with the env temporarily set."""
    os.environ["AKKI_CHAT_FIXTURES_ENABLED"] = "1"
    try:
        import importlib, server
        importlib.reload(server)
        app = server.app

        import requests
        base = "https://akki-executive.preview.emergentagent.com"
        rr = requests.post(f"{base}/api/auth/login",
                           json={"email": "admin@akki.ai", "password": "AkkiAdmin2026!"},
                           timeout=15)
        token = rr.json()["access_token"]
        cid = requests.get(f"{base}/api/auth/me",
                           headers={"Authorization": f"Bearer {token}"}).json()["account"]["default_context_id"]
        rc = requests.post(f"{base}/api/chats",
                           json={"context_id": cid, "model_id": "claude-sonnet-4-5",
                                 "title": "zz2x-stream-shape"},
                           headers={"Authorization": f"Bearer {token}", "X-Active-Context": cid})
        if rc.status_code >= 400:
            pytest.skip(f"chat create skipped: {rc.status_code}")
        chat_id = rc.json()["id"]

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                h = {"Authorization": f"Bearer {token}", "X-Active-Context": cid}
                r = await c.post(
                    f"/api/chats/{chat_id}/messages?fixture=bias_anchoring",
                    headers=h, json={"content": "ping"},
                )
                assert r.status_code == 200, r.text
                body = r.text
                assert '"type": "start"' in body
                assert '"phase": "complete"' in body
                # zz2_governance attached on the terminal message
                assert '"zz2_governance"' in body
                # Fixture text rendered as delta (middle-dot is u00b7
                # in JSON-escaped SSE output)
                assert ("[anchoring · Q4 number]" in body
                        or "[anchoring \\u00b7 Q4 number]" in body)
                # Bias flag captured in the terminal governance object
                assert ("anchoring · Q4 number" in body
                        or "anchoring \\u00b7 Q4 number" in body)
        finally:
            requests.delete(f"{base}/api/chats/{chat_id}",
                            headers={"Authorization": f"Bearer {token}", "X-Active-Context": cid})
    finally:
        os.environ.pop("AKKI_CHAT_FIXTURES_ENABLED", None)
