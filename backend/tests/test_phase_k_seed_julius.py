"""Phase K.3 — seed_julius_opio integration test.

Runs the seed script twice (idempotence) and confirms:
  • the account ends with the canonical credentials
  • exactly 4 contexts (one per type) owned by Julius
  • exactly 4 memberships
  • a real /api/auth/login returns 200 + access_token

Uses subprocess to invoke the seed script directly so this also
catches import / import-order regressions.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "scripts" / "seed_julius_opio.py"

EMAIL = "juliusaopio@gmail.com"
PASSWORD = "Julius@Akki!2026-Exec"


def _run_seed() -> str:
    proc = subprocess.run(
        [sys.executable, str(SEED)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"seed_julius_opio.py exited {proc.returncode}\n"
        f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
    )
    return proc.stdout


@pytest.mark.asyncio
async def test_seed_julius_opio_creates_then_idempotent():
    """First run creates; second run hits the ↺ updated branches."""
    out1 = _run_seed()
    out2 = _run_seed()

    # Run 1 — at minimum the four contexts get created OR exist+reasserted
    # (the order between this test and ad-hoc runs is non-deterministic).
    # We only require: both runs succeed and log the four context names.
    for spec_name in (
        "Personal NED Seat",
        "Sponsored NED Seat",
        "Executive Role",
        "Enterprise Executive",
    ):
        assert spec_name in out1
        assert spec_name in out2

    # Run 2 must hit the idempotent path — every line should be ↺,
    # never ✚, on the second invocation.
    assert "✚ Account created" not in out2, "Re-run should not re-create the account."
    assert out2.count("↺ Context exists") == 4
    assert "memberships          = 4" in out2
    assert "contexts owned       = 4" in out2


@pytest.mark.asyncio
async def test_julius_login_succeeds_after_seed():
    _run_seed()
    transport = httpx.ASGITransport  # noqa: F841 — fall back to real HTTP
    base = os.environ.get("BACKEND_URL", "http://localhost:8001")
    async with httpx.AsyncClient(base_url=base, timeout=10.0) as ac:
        r = await ac.post(
            "/api/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
        )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data and len(data["access_token"]) > 50
    assert data["account"]["email"] == EMAIL
    assert data["account"]["declared_role"] == "dual"
    assert data["account"]["is_superadmin"] is True
    assert data["account"]["plan"] == "enterprise"
    assert data["account"]["subscription_status"] == "active"
    assert data["account"]["first_session"]["status"] == "skipped"
    # 4 contexts attached on login
    contexts = data.get("contexts") or []
    types = sorted(c["type"] for c in contexts)
    assert types == sorted([
        "executive_enterprise",
        "executive_personal",
        "ned_personal",
        "ned_sponsored",
    ])
    # All 4 carry the standard 6-committee set
    # (committee data is on the context document; the login payload
    # may or may not surface it depending on `sanitize_context`. We
    # don't insist on it here; the seed-side mongo cross-check in
    # the next test asserts the committees.)


@pytest.mark.asyncio
async def test_julius_seed_writes_full_committee_set():
    _run_seed()
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    acc = await db.accounts.find_one({"email": EMAIL}, {"_id": 0})
    assert acc is not None
    cursor = db.contexts.find(
        {"owner_account_id": acc["id"]},
        {"_id": 0, "type": 1, "name": 1, "committees": 1},
    )
    by_type = {}
    async for c in cursor:
        by_type[c["type"]] = c
    assert set(by_type.keys()) == {
        "ned_personal", "ned_sponsored",
        "executive_personal", "executive_enterprise",
    }
    expected_committee_ids = {"audit", "risk", "nominations", "remuneration", "esg", "strategy"}
    for ctype, ctx in by_type.items():
        committee_ids = {cm["id"] for cm in (ctx.get("committees") or [])}
        assert expected_committee_ids <= committee_ids, (
            f"context type={ctype} missing committees: "
            f"expected {expected_committee_ids}, got {committee_ids}"
        )
    client.close()


def test_seed_julius_opio_log_format():
    out = _run_seed()
    # Sanity-check the printed credential block is intact (no accidental
    # silent failure mode where the script prints "Seed complete" but
    # logs no credentials).
    assert "✅ Seed complete." in out
    assert f"email:    {EMAIL}" in out
    assert f"password: {PASSWORD}" in out
