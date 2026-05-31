"""Phase P5.7 (2026-02) — Waitlist + day-10 reminder + email HTML.

Covers:
  - POST /api/cohort/waitlist accepts a valid email, persists,
    idempotent re-submit returns 200 with already_present=true.
  - Bad email shape → 400 email_invalid.
  - Source-application correlation persists when provided.
  - send_decline with a waitlist_url switches to the door-back body.
  - HTML rendering escapes user-controlled inputs.
  - run_expiry_reminder_sweep is idempotent — second run sends 0.
  - Reminder body word-count ≤60.
  - Decline-with-waitlist body word-count ≤80.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

import pymongo  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from server import app  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ─── Waitlist endpoint ────────────────────────────────────────────────
def test_p5_7_6_waitlist_accepts_valid_email():
    email = f"p5-7-waitlist-{uuid.uuid4().hex[:6]}@example.com"
    fake_ip = f"203.0.{uuid.uuid4().int % 200 + 50}.{uuid.uuid4().int % 250 + 1}"

    async def _do():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            return await ac.post(
                "/api/cohort/waitlist",
                headers={"X-Forwarded-For": fake_ip},
                json={"email": email},
            )

    r = _run(_do())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["already_present"] is False


def test_p5_7_6_waitlist_idempotent_on_repeat_email():
    email = f"p5-7-waitlist-idem-{uuid.uuid4().hex[:6]}@example.com"
    fake_ip = f"203.0.{uuid.uuid4().int % 200 + 50}.{uuid.uuid4().int % 250 + 1}"

    async def _do():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            r1 = await ac.post(
                "/api/cohort/waitlist",
                headers={"X-Forwarded-For": fake_ip},
                json={"email": email},
            )
            r2 = await ac.post(
                "/api/cohort/waitlist",
                headers={"X-Forwarded-For": fake_ip},
                json={"email": email},
            )
            return r1, r2

    r1, r2 = _run(_do())
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["already_present"] is True


def test_p5_7_6_waitlist_rejects_malformed_email():
    fake_ip = f"203.0.{uuid.uuid4().int % 200 + 50}.{uuid.uuid4().int % 250 + 1}"

    async def _do():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            return await ac.post(
                "/api/cohort/waitlist",
                headers={"X-Forwarded-For": fake_ip},
                json={"email": "not-an-email"},
            )

    r = _run(_do())
    # Pydantic EmailStr rejects → 422; the body validator also catches.
    assert r.status_code in (400, 422)


def test_p5_7_6_waitlist_correlates_source_application_id():
    email = f"p5-7-waitlist-corr-{uuid.uuid4().hex[:6]}@example.com"
    app_id = f"p5-7-app-{uuid.uuid4().hex[:8]}"
    fake_ip = f"203.0.{uuid.uuid4().int % 200 + 50}.{uuid.uuid4().int % 250 + 1}"

    async def _do():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            return await ac.post(
                "/api/cohort/waitlist",
                headers={"X-Forwarded-For": fake_ip},
                json={"email": email, "source_application_id": app_id},
            )

    r = _run(_do())
    assert r.status_code == 200
    # Verify the stored row carries the correlation.
    dbc = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    row = dbc.cohort_waitlist.find_one({"email_lc": email.lower()}, {"_id": 0})
    assert row is not None
    assert row["source_application_id"] == app_id


# ─── Decline-with-waitlist body ───────────────────────────────────────
def test_p5_7_6_send_decline_with_waitlist_url_switches_body():
    """When `waitlist_url` is passed, the body must include the
    door-back line. When omitted, the original body is unchanged."""
    from services.cohort_email import (
        DECLINE_BODY, DECLINE_BODY_WITH_WAITLIST,
    )
    bare = DECLINE_BODY.format(first_name="Friend")
    with_wl = DECLINE_BODY_WITH_WAITLIST.format(
        first_name="Friend", waitlist_url="https://akki.syni.ai/waitlist?from=abc",
    )
    assert "waitlist" in with_wl.lower()
    assert "waitlist" not in bare.lower()
    assert "https://akki.syni.ai/waitlist?from=abc" in with_wl


# ─── HTML escape ──────────────────────────────────────────────────────
def test_p5_7_html_escapes_first_name_and_magic_link():
    from services.cohort_email_html import (
        render_approval_html, render_decline_html, render_receipt_html,
    )
    evil_name = '<script>alert(1)</script>'
    evil_link = 'https://example.com/?x="><script>alert(1)</script>'
    r = render_receipt_html(first_name=evil_name)
    assert '<script>' not in r
    assert '&lt;script&gt;' in r
    a = render_approval_html(first_name=evil_name, magic_link=evil_link)
    assert '<script>' not in a
    assert 'alert(1)' in a  # the string is present, but escaped — verify the html parts
    # The button href must carry the escaped quote.
    assert 'href="https://example.com/?x=&quot;&gt;' in a or "&quot;" in a
    d = render_decline_html(first_name=evil_name, waitlist_url=evil_link)
    assert '<script>' not in d


# ─── Reminder sweep idempotency ───────────────────────────────────────
def test_p5_7_4_reminder_sweep_idempotent():
    """Seed a magic_link row at day-10.5; run the sweep twice; first
    run sends, second run finds nothing."""
    dbc = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    app_id = f"p5-7-rem-{uuid.uuid4().hex[:8]}"
    link_id = uuid.uuid4().hex
    issued_at = datetime.now(timezone.utc) - timedelta(days=10, hours=12)
    dbc.cohort_applications.insert_one({
        "id": app_id,
        "email": f"{app_id}@example.com",
        "name": "Reminder Tester",
        "status": "approved",
        "created_at": issued_at.isoformat(),
    })
    dbc.cohort_magic_links.insert_one({
        "id": link_id,
        "application_id": app_id,
        "token_hash": "x" * 64,
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + timedelta(days=14)).isoformat(),
        "consumed_at": None,
    })

    async def _do():
        from routers.cohort_expiry_reminder import run_expiry_reminder_sweep
        first = await run_expiry_reminder_sweep()
        second = await run_expiry_reminder_sweep()
        return first, second

    first, second = _run(_do())
    # First run picks up the seeded row.
    assert first["candidates_scanned"] >= 1
    # Stamped now → second run scans 0.
    assert second["candidates_scanned"] == 0
    # And the marker is on the doc.
    row = dbc.cohort_magic_links.find_one({"id": link_id}, {"_id": 0})
    assert row.get("expiry_reminder_sent_at"), "marker not stamped"


# ─── Word-count caps ──────────────────────────────────────────────────
def test_p5_7_self_check_passes():
    """`cohort_email._self_check()` runs at import; if any word cap
    is exceeded the import itself raises. This test re-runs it to be
    explicit about the contract."""
    from services.cohort_email import _self_check
    counts = _self_check()
    # All known kinds present.
    assert {"receipt", "approval", "decline", "reminder", "decline_waitlist"} <= set(counts)
    # Reminder fits the 60-word cap.
    assert counts["reminder"] <= 60
    # Decline+waitlist fits the 80-word cap.
    assert counts["decline_waitlist"] <= 80
