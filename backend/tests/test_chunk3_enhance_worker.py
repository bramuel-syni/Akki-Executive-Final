"""Chunk 3 — Enhance worker_crash regression tests (WS-R06, R12, R15).

Pre-Chunk 3 the three Enhance variants (Minutes, Deck, Report)
all wrote the literal string `"worker_crash"` into the export row
when ANY exception fired inside `_run_enhance` — the catch-all
swallowed the real exception class, message, and traceback. The
real underlying bugs for the WS-R06 (Minutes) case were:
  1. `minutes` was not registered in `_ENHANCE_KINDS` (400 at the door)
  2. The two-pass schema dispatch in `_run_two_pass_for_export`
     `KeyError`'d on `kind="minutes"`
  3. The `scrape_content_text` helper crashed with
     `TypeError: sequence item N: expected str instance, dict found`
     when the LLM returned recommendations as dicts rather than strings

These tests:
  * Assert that any uncaught exception in the enhance worker writes
    a structured `{ClassName}: {message}` error — NEVER the literal
    `"worker_crash"`.
  * Assert that `minutes` is a registered kind.
  * Assert that the recommendations-coercion path doesn't crash when
    the LLM returns dicts.

The tests mock the LLM call so they don't need to spend ~60 s per
test on real model latency.
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


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_conn():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


@pytest_asyncio.fixture
async def seeded(db_conn):
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk3-enh-{suffix}@example.com"
    password = "Chunk3Enh2026!"
    aid = f"acc-c3-{suffix}"
    cid = f"ctx-c3-{suffix}"
    now = _iso()
    from core import hash_password
    await db_conn.accounts.insert_one({
        "id": aid, "email": email, "password_hash": hash_password(password),
        "name": "Chunk3 Probe", "role": "executive", "created_at": now,
        "default_context_id": cid, "session_version": 0, "verified": True,
    })
    await db_conn.contexts.insert_one({
        "id": cid, "name": "Probe Ctx Chunk3", "type": "executive_personal",
        "status": "active", "owner_account_id": aid, "created_at": now,
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4()}", "context_id": cid, "account_id": aid,
        "status": "active", "role": "executive", "sub_role": "admin", "joined_at": now,
    })
    yield {"email": email, "password": password, "account_id": aid, "context_id": cid}
    await db_conn.memberships.delete_many({"account_id": aid})
    await db_conn.contexts.delete_one({"id": cid})
    await db_conn.accounts.delete_one({"id": aid})
    await db_conn.work_studio_exports.delete_many({"account_id": aid})


async def _login(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _pdf_bytes() -> bytes:
    """Tiny valid PDF generated via reportlab — small enough that
    none of our extension/size guards reject it."""
    from io import BytesIO
    from reportlab.pdfgen import canvas
    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "Probe — Chunk 3 enhance test fixture")
    c.drawString(100, 730, "Decision: approve.")
    c.save()
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────
# 1. `minutes` is a registered enhance kind (post-Chunk-3).
# ─────────────────────────────────────────────────────────────────
def test_minutes_is_a_registered_enhance_kind():
    from routers import work_studio_export as wse
    assert "minutes" in wse._ENHANCE_KINDS
    assert "minutes" in wse._ENHANCE_ACCEPTED_EXT_BY_KIND


# ─────────────────────────────────────────────────────────────────
# 2. Worker exception MUST write a structured `{Class}: {msg}` error,
#    NEVER the literal "worker_crash". Three variants (minutes, deck,
#    report) all share the runner so one mock covers the class.
# ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("kind,output_format", [
    ("minutes", "docx"),
    ("report",  "docx"),
    ("deck",    "pptx"),
])
@pytest.mark.asyncio
async def test_enhance_runner_writes_structured_error_not_worker_crash(
    client, seeded, monkeypatch, db_conn, kind, output_format,
):
    """Mock `_run_enhance` to raise a vivid error. The runner's
    catch-all must persist `{Class}: {msg}` — not the legacy
    opaque `worker_crash` string — so the user / ops can act on it."""
    from routers import work_studio_export as wse

    async def _exploding_worker(**kwargs):
        raise ValueError("Synthetic chunk-3 explosion: LLM provider returned 503.")

    monkeypatch.setattr(wse, "_run_enhance", _exploding_worker)

    token = await _login(client, seeded["email"], seeded["password"])
    files = {"file": (f"probe.pdf", _pdf_bytes(), "application/pdf")}
    data = {
        "instructions": "Tighten the prose.",
        "output_format": output_format,
    }
    r = await client.post(
        f"/api/contexts/{seeded['context_id']}/work-studio/enhance/{kind}",
        files=files, data=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"start_enhance: {r.status_code} {r.text}"
    export_id = r.json()["export_id"]

    # Allow the runner a moment to mark the row as failed.
    import asyncio
    for _ in range(40):
        row = await db_conn.work_studio_exports.find_one(
            {"id": export_id}, {"_id": 0, "status": 1, "error": 1},
        )
        if row and row.get("status") == "failed":
            break
        await asyncio.sleep(0.05)
    else:
        raise AssertionError("runner never marked the row as failed")

    err = row.get("error") or ""
    assert err != "worker_crash", (
        "REGRESSION: runner wrote the opaque legacy `worker_crash` literal. "
        "Should write `{ClassName}: {message}` instead."
    )
    assert err.startswith("ValueError"), f"expected ValueError prefix, got: {err}"
    assert "Synthetic chunk-3" in err, f"underlying message not preserved: {err}"


# ─────────────────────────────────────────────────────────────────
# 3. `scrape_content_text` coerces dict-shaped recommendations
#    instead of crashing — direct unit test of the helper.
# ─────────────────────────────────────────────────────────────────
def test_scrape_content_text_handles_dict_recommendations():
    """Pre-Chunk-3 this raised TypeError because the LLM occasionally
    returns recommendations as dicts. Post-fix the helper coerces
    dicts into one flat readable string and never crashes."""
    from services.work_studio_export import scrape_content_text

    content = {
        "title": "Minutes — Probe",
        "executive_summary": "Decisions taken below.",
        "sections": [
            {"heading": "Item 1", "paragraphs": ["Discussion.", "Decision."]},
        ],
        "recommendations": [
            "Plain string action.",
            {"owner": "Alice", "action": "Draft Q3 plan", "when": "by Friday"},
            {"heading": "Procure Y", "body": "Action with no when"},
            {"text": "Loose text-only dict"},
            42,            # an int — must still not crash
            None,          # None — must be dropped
        ],
    }
    text = scrape_content_text(content)
    assert "Alice" in text
    assert "Draft Q3 plan" in text
    assert "Procure Y" in text
    assert "Loose text-only dict" in text
    # Plain string should also appear.
    assert "Plain string action." in text


# ─────────────────────────────────────────────────────────────────
# 4. Adjust-and-Retry preserves file state (frontend logic captured
#    server-side: the endpoint MUST accept a second submission with
#    the same file without complaining the file is empty).
# ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_enhance_can_be_resubmitted_after_a_failed_attempt(
    client, seeded, monkeypatch, db_conn,
):
    """The "Adjust and Retry" flow re-submits the same file with
    different instructions. There is no server-side "you already
    tried this file" guard — that would defeat retry — and the
    second submission must reach `running` cleanly."""
    from routers import work_studio_export as wse

    attempts = []
    async def _flaky_worker(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise RuntimeError("first attempt failed on purpose")
        # Second attempt succeeds — mark row as `complete` directly.
        from core import db, iso, now
        await db.work_studio_exports.update_one(
            {"id": kwargs["export_id"]},
            {"$set": {"status": "complete", "completed_at": iso(now())}},
        )

    monkeypatch.setattr(wse, "_run_enhance", _flaky_worker)

    token = await _login(client, seeded["email"], seeded["password"])
    file_bytes = _pdf_bytes()

    # Attempt 1 — must fail.
    r1 = await client.post(
        f"/api/contexts/{seeded['context_id']}/work-studio/enhance/minutes",
        files={"file": ("probe.pdf", file_bytes, "application/pdf")},
        data={"instructions": "First attempt.", "output_format": "docx"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    exp1 = r1.json()["export_id"]

    # Attempt 2 — re-submit same file, different instructions.
    r2 = await client.post(
        f"/api/contexts/{seeded['context_id']}/work-studio/enhance/minutes",
        files={"file": ("probe.pdf", file_bytes, "application/pdf")},
        data={"instructions": "Adjusted: drop bullet 3.", "output_format": "docx"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200, f"retry submission rejected: {r2.status_code} {r2.text}"
    exp2 = r2.json()["export_id"]
    assert exp2 != exp1, "retry must create a fresh export row, not reuse"

    # Let both runners settle.
    import asyncio
    await asyncio.sleep(0.4)

    # Two attempts recorded.
    assert len(attempts) == 2

    # Second attempt's row is `complete`.
    row2 = await db_conn.work_studio_exports.find_one(
        {"id": exp2}, {"_id": 0, "status": 1},
    )
    assert row2 and row2["status"] == "complete", row2


# ─────────────────────────────────────────────────────────────────
# 5. Unknown kind still 400s with a clean message (defense-in-depth
#    against the `worker_crash` regression class).
# ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_unknown_enhance_kind_returns_400_not_worker_crash(client, seeded):
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.post(
        f"/api/contexts/{seeded['context_id']}/work-studio/enhance/whatever",
        files={"file": ("probe.pdf", _pdf_bytes(), "application/pdf")},
        data={"instructions": "x", "output_format": "docx"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
    assert "worker_crash" not in r.text.lower()
    assert "minutes" in r.text or "Allowed" in r.text  # message mentions the allow-list
