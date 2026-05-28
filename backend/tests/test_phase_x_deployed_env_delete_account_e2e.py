"""Phase X bug-1 regression — deployed-env E2E.

The original `_schedule_deletion` shipped with `if not existing:` against
a Mongo `find_one(...)` result projected to only-optional fields. New
accounts (no `status`, no `deletion_*` keys yet) trip the falsy-empty-
dict trap — find_one returns `{}` which is truthy under `is not None`
but falsy under `not`. The unit tests in `test_phase_x_account_deletion.py`
created their fixture accounts WITH a `status: "active"` field, so the
projection returned `{"status": "active"}` (truthy) and the bug never
surfaced. Real seed accounts in deployed env lack the field.

This test runs against the LIVE mounted DB (NOT a fresh fixture) using
the FastAPI TestClient — same `db` handle the deployed process uses.
Seeds a minimal account WITHOUT `status` / `deletion_*` keys, calls the
endpoint, asserts 200. Cleanup in finally.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.mark.asyncio
async def test_phase_x_bug1_deployed_env_delete_account_minimal_account():
    """Seed an account on the LIVE mounted db (the one the deployed
    process actually uses) without `status` / `deletion_*` keys, hit
    the endpoint, assert 200."""
    from server import app  # type: ignore
    from core import db, get_current_account  # type: ignore

    acc_id = f"px-deployed-{uuid.uuid4().hex[:8]}"
    email = f"px-deployed-{uuid.uuid4().hex[:6]}@example.com"

    # Insert a deliberately-minimal account that mirrors what `seed`
    # scripts produce — NO `status` field.
    await db.accounts.insert_one({
        "id": acc_id,
        "email": email,
        "name": "PX Deployed Probe",
        "is_superadmin": False,
        "created_at": _iso_now(),
    })

    async def _fake_resolve():
        # Re-fetch with full projection so the dependency mimics what
        # `get_current_account` returns in production.
        return await db.accounts.find_one({"id": acc_id}, {"_id": 0})

    app.dependency_overrides[get_current_account] = _fake_resolve
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            # The failing path pre-fix: this returned 404 "Account not
            # found" because the projected dict came back empty `{}` and
            # the route had `if not existing:` instead of `is None:`.
            r = await client.post("/api/me/delete-account", json={"confirm": email})
            assert r.status_code == 200, (
                f"Phase X bug-1 regression: minimal-account delete must "
                f"return 200, got {r.status_code} → {r.text}"
            )
            payload = r.json()
            assert payload["status"] == "pending_deletion"
            assert payload["grace_days"] == 30
            assert "deletion_scheduled_for" in payload

            # Cancel — must also work.
            r2 = await client.post("/api/me/delete-account/cancel")
            assert r2.status_code == 200, (
                f"Cancel must succeed for minimal account, got "
                f"{r2.status_code} → {r2.text}"
            )

            # Confirm the DB state is back to active.
            row = await db.accounts.find_one({"id": acc_id}, {"_id": 0})
            assert row["status"] == "active"
            assert row.get("deletion_scheduled_for") is None
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        await db.accounts.delete_one({"id": acc_id})


@pytest.mark.asyncio
async def test_phase_x_bug1_source_uses_is_none_not_truthy_check():
    """Source-strict guard — `_schedule_deletion` must use `is None`
    (not `not existing`) so the empty-dict projection trap can't
    return."""
    src = (BACKEND / "routers" / "account_deletion.py").read_text(encoding="utf-8")
    # The schedule helper specifically — search for the line.
    sched_block_start = src.find("async def _schedule_deletion")
    assert sched_block_start > 0
    sched_block_end = src.find("\n\n", sched_block_start)
    block = src[sched_block_start:sched_block_end if sched_block_end > 0 else len(src)]
    assert "if existing is None" in block, (
        "_schedule_deletion must use `is None` for Mongo find_one falsy "
        "check — the empty-dict projection trap returns `{}` which is "
        "falsy under `not …` but truthy under `is not None`."
    )
    assert "if not existing:" not in block, (
        "_schedule_deletion must NOT use `if not existing` — "
        "see Phase X bug-1 lesson."
    )
