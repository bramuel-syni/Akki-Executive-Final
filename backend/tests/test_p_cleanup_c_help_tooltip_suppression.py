"""P-Cleanup C — Help tooltip suppression for returning users.

Pre-fix at `routers/onboarding_status.py:114`:

    show_help_tooltip = not help_dismissed

…showed the black "Help is one click away" callout to EVERY user who
hadn't explicitly dismissed it, including returning users who'd
already finished onboarding. The reported symptom: orphan black
tooltip artifact under the Help button on the top bar.

Post-fix mirrors the trust-center tooltip gate:

    show_help_tooltip = not help_dismissed and not acknowledged_at

(See the docstring comment on line 105-108 which already documented
this contract — implementation had drifted from documentation.)

Invariant locked here:
  • Fresh user (no `re_intro_acknowledged_at`, no dismiss):
      help_tooltip.show == True
  • Returning user with `re_intro_acknowledged_at` set:
      help_tooltip.show == False     ← previously was True (BUG)
  • User who explicitly dismissed:
      help_tooltip.show == False
  • Both flags set:
      help_tooltip.show == False     (idempotent)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import server  # noqa: F401
from server import app


@pytest_asyncio.fixture(scope="module")
async def transport():
    yield ASGITransport(app=app)


async def _csrf_login(client, *, email: str, password: str) -> Dict[str, str]:
    r = await client.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await client.post(
        "/api/auth/login", json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    r.raise_for_status()
    body = r.json()
    token = body.get("access_token") or body.get("token")
    r = await client.get("/api/csrf")
    return {"Authorization": f"Bearer {token}",
            "X-CSRF-Token": r.json()["csrf_token"]}


async def _seed_account(db, *, acknowledged_at=None, help_dismissed_at=None):
    from core import hash_password
    email = f"pclean-c-{uuid.uuid4().hex[:6]}@example.com"
    aid = "acct-pcc-" + uuid.uuid4().hex[:10]
    doc: Dict[str, Any] = {
        "id": aid,
        "email": email.lower(), "email_lc": email.lower(),
        "name": "P-Cleanup C test user",
        "password_hash": hash_password("PccTest!"),
        "declared_role": "user",
        "first_session": {"status": "completed", "current_step": "done"},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if acknowledged_at:
        doc["shield_v1_intro_acknowledged_at"] = acknowledged_at
    if help_dismissed_at:
        doc["help_tooltip_dismissed_at"] = help_dismissed_at
    await db.accounts.insert_one(doc)
    return email, aid


async def _get_status(client, hdrs):
    r = await client.get("/api/users/me/onboarding-status", headers=hdrs)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_fresh_user_sees_help_tooltip(transport):
    """Default state: no dismissal, no re-intro acknowledgement → show."""
    from core import db
    email, _ = await _seed_account(db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login(client, email=email, password="PccTest!")
        s = await _get_status(client, hdrs)
    assert s["help_tooltip"]["show"] is True, s
    assert s["help_tooltip"]["dismissed_at"] in (None, ""), s


@pytest.mark.asyncio
async def test_returning_user_with_acknowledged_at_is_suppressed(transport):
    """KEY INVARIANT — pre-fix this rendered the tooltip; post-fix it
    must be suppressed.

    Returning user who completed the J1 re-intro flow → no tooltip,
    even though they never explicitly clicked "X" to dismiss the
    tooltip itself.
    """
    from core import db
    email, _ = await _seed_account(
        db,
        acknowledged_at=datetime.now(timezone.utc).isoformat(),
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login(client, email=email, password="PccTest!")
        s = await _get_status(client, hdrs)
    assert s["help_tooltip"]["show"] is False, (
        "P-Cleanup C regression — returning user with re_intro_acknowledged_at "
        "set must NOT see the help tooltip. Got: " + str(s)
    )


@pytest.mark.asyncio
async def test_explicit_dismissal_suppresses_independently(transport):
    """Explicit dismiss always wins, no matter the other flags."""
    from core import db
    email, _ = await _seed_account(
        db,
        help_dismissed_at=datetime.now(timezone.utc).isoformat(),
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login(client, email=email, password="PccTest!")
        s = await _get_status(client, hdrs)
    assert s["help_tooltip"]["show"] is False


@pytest.mark.asyncio
async def test_both_flags_set_is_idempotent_off(transport):
    from core import db
    now = datetime.now(timezone.utc).isoformat()
    email, _ = await _seed_account(
        db, acknowledged_at=now, help_dismissed_at=now,
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login(client, email=email, password="PccTest!")
        s = await _get_status(client, hdrs)
    assert s["help_tooltip"]["show"] is False


@pytest.mark.asyncio
async def test_source_marker_present(transport):
    """Guard against future drift back to the bug-shape gate."""
    src = open("/app/backend/routers/onboarding_status.py", encoding="utf-8").read()
    assert "show_help_tooltip = (\n        not help_dismissed and not acknowledged_at\n    )" in src, (
        "onboarding_status.py drifted off the P-Cleanup C help_tooltip gate."
    )
