"""Sprint M.0c — Cohort applications scaffold contract tests.

Coverage:
  • Accepts valid payload → 200 + record persisted with status=received.
  • Rejects malformed payload → 422 (missing fields / bad email).
  • Idempotent on duplicate email within 24h → returns same id with
    deduplicated=true.
  • Applicant confirmation body is `<!-- COPY TBD M.2 -->` placeholder.
  • Source-strict: docs/cohort_pricing.md exists; router registered.
"""
from __future__ import annotations
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

REPO = Path(__file__).resolve().parent.parent.parent
SERVER_PY = REPO / "backend" / "server.py"
ROUTER_PY = REPO / "backend" / "routers" / "cohort_applications.py"
PRICING_MD = REPO / "docs" / "cohort_pricing.md"


def test_m0c_router_registered():
    src = SERVER_PY.read_text(encoding="utf-8")
    assert "cohort_applications_router.router" in src
    assert "cohort_applications" in (ROUTER_PY.read_text(encoding="utf-8"))


def test_m0c_pricing_doc_placeholder_present():
    assert PRICING_MD.exists()
    content = PRICING_MD.read_text(encoding="utf-8")
    # Updated dispatch 11 — doc now records HELD status.
    assert "Pricing not yet defined" in content
    assert "Status: HELD" in content


# (dispatch 11 — M.0c happy path test below also updated to assert
# the new applicant confirmation body, not the original placeholder.)


@pytest.fixture
def app():
    import importlib, server
    importlib.reload(server)
    return server.app


@pytest.mark.asyncio
async def test_m0c_post_application_happy_path(app):
    from core import db
    transport = ASGITransport(app=app)
    seeded = []
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            email = f"m0c-{uuid.uuid4().hex[:8]}@example.com"
            r = await c.post("/api/cohort/applications", json={
                "name": "Hadley Wickham",
                "email": email,
                "organisation": "RStudio",
                "role": "Chief Scientist",
                "use_case": "Calmer board reading rhythm for monthly investor meetings.",
                "referral_source": "Twitter",
            })
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["status"] == "received"
            assert body["deduplicated"] is False
            seeded.append(body["id"])
            row = await db.cohort_applications.find_one(
                {"id": body["id"]}, {"_id": 0},
            )
            assert row["email"] == email.lower()
            assert row["status"] == "received"
            assert row["applicant_confirmation_body"].startswith(
                "Thank you for requesting access to Akki."
            )
            assert "early access" in row["applicant_confirmation_body"]
            assert "founding cohort" not in row["applicant_confirmation_body"].lower()
            # Idempotent within 24h → second POST returns same id.
            r2 = await c.post("/api/cohort/applications", json={
                "name": "Hadley Wickham",
                "email": email,
                "organisation": "RStudio",
                "role": "Chief Scientist",
                "use_case": "Calmer board reading rhythm.",
            })
            assert r2.status_code == 200
            assert r2.json()["id"] == body["id"]
            assert r2.json()["deduplicated"] is True
    finally:
        for sid in seeded:
            await db.cohort_applications.delete_one({"id": sid})


@pytest.mark.asyncio
async def test_m0c_post_application_validation_errors(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Missing required field 'use_case'.
        r = await c.post("/api/cohort/applications", json={
            "name": "X", "email": "x@y.com", "organisation": "O", "role": "R",
        })
        assert r.status_code == 422
        # Bad email shape.
        r = await c.post("/api/cohort/applications", json={
            "name": "Xander", "email": "not-an-email",
            "organisation": "O", "role": "R", "use_case": "Anything.",
        })
        assert r.status_code == 422
        # name too short (< 2 chars).
        r = await c.post("/api/cohort/applications", json={
            "name": "X", "email": "x@y.com",
            "organisation": "O", "role": "R", "use_case": "Anything.",
        })
        assert r.status_code == 422


def test_m0c_notify_skips_without_env(monkeypatch):
    """FOUNDER_NOTIFY_EMAIL unset → _notify_founder no-ops without raising."""
    monkeypatch.delenv("FOUNDER_NOTIFY_EMAIL", raising=False)
    from routers.cohort_applications import _notify_founder
    _notify_founder({
        "id": "noop-test", "name": "T", "email": "t@y.com",
        "organisation": "O", "role": "R", "use_case": "x",
        "referral_source": None,
    })
    # No raise = pass.
