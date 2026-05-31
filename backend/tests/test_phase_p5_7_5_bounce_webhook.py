"""Phase P5.7.5 (2026-02) — SendGrid event webhook ingestion."""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

import pymongo  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from server import app  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_p5_7_5_bounce_event_writes_failed_bucket_on_application_row():
    """A bounce event from SendGrid for an email that matches a
    cohort_applications row → that row's `latest_email_event_bucket`
    becomes 'failed' so the admin badge renders."""
    dbc = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    email = f"p5-7-5-bounce-{uuid.uuid4().hex[:6]}@example.com"
    app_id = f"p5-7-5-app-{uuid.uuid4().hex[:8]}"
    dbc.cohort_applications.insert_one({
        "id": app_id,
        "email": email,
        "email_lc": email.lower(),
        "name": "Bounce Tester",
        "status": "approved",
    })

    async def _do():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            return await ac.post(
                "/api/cohort/email-events/sendgrid",
                json=[{
                    "email": email,
                    "event": "bounce",
                    "timestamp": 1730000000,
                    "sg_message_id": "MSGID_BOUNCE_TEST",
                    "reason": "550 5.1.1 user unknown",
                }],
            )

    r = _run(_do())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["processed"] == 1
    assert body["buckets"]["failed"] == 1

    row = dbc.cohort_applications.find_one({"id": app_id}, {"_id": 0})
    assert row["latest_email_event_bucket"] == "failed"
    assert row["latest_email_event_type"] == "bounce"
    assert "user unknown" in (row.get("latest_email_event_reason") or "")


def test_p5_7_5_delivered_event_writes_delivered_bucket():
    dbc = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    email = f"p5-7-5-ok-{uuid.uuid4().hex[:6]}@example.com"
    app_id = f"p5-7-5-app-{uuid.uuid4().hex[:8]}"
    dbc.cohort_applications.insert_one({
        "id": app_id, "email": email, "email_lc": email.lower(),
        "name": "Delivered Tester", "status": "approved",
    })

    async def _do():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            return await ac.post(
                "/api/cohort/email-events/sendgrid",
                json=[{
                    "email": email, "event": "delivered",
                    "timestamp": 1730000000,
                    "sg_message_id": "MSGID_OK_TEST",
                }],
            )

    r = _run(_do())
    assert r.status_code == 200
    row = dbc.cohort_applications.find_one({"id": app_id}, {"_id": 0})
    assert row["latest_email_event_bucket"] == "delivered"


def test_p5_7_5_unknown_recipient_does_not_create_row():
    """An event for an email NOT in cohort_applications must not
    silently create a row — it should only update existing
    applicants. The event still lands in cohort_email_events for
    debug visibility, just not in cohort_applications."""
    email = f"p5-7-5-unknown-{uuid.uuid4().hex[:6]}@nowhere.example.com"

    async def _do():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            return await ac.post(
                "/api/cohort/email-events/sendgrid",
                json=[{
                    "email": email, "event": "bounce",
                    "timestamp": 1730000000,
                    "sg_message_id": "MSGID_GHOST",
                }],
            )

    r = _run(_do())
    assert r.status_code == 200
    dbc = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    assert dbc.cohort_applications.count_documents({"email_lc": email.lower()}) == 0
    # But the event WAS recorded in the events collection.
    assert dbc.cohort_email_events.count_documents({"email_lc": email.lower()}) >= 1


def test_p5_7_5_invalid_body_returns_400():
    async def _do():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            return await ac.post(
                "/api/cohort/email-events/sendgrid",
                content=b"this is not json",
                headers={"Content-Type": "application/json"},
            )

    r = _run(_do())
    assert r.status_code == 400


def test_p5_7_5_classify_buckets_correctly():
    from routers.cohort_email_events import _classify
    assert _classify("bounce") == "failed"
    assert _classify("BOUNCE") == "failed"
    assert _classify("spamreport") == "failed"
    assert _classify("dropped") == "failed"
    assert _classify("blocked") == "failed"
    assert _classify("delivered") == "delivered"
    assert _classify("open") == "delivered"
    assert _classify("deferred") == "pending"
    assert _classify("processed") == "pending"
    assert _classify("unknown_event_xyz") == "other"
