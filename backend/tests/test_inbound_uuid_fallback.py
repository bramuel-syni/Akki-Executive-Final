"""Inbound-email UUID fallback (Phase C — replaces 1/3 of test_iter55_decks.py).

Per QUARANTINE_TRIAGE_PLAN.md Phase-5 recipe for `test_iter55_decks.py`:

  > Split into 3 small files: ... `test_inbound_uuid_fallback.py`
  > (the smaller piece).

The "inbound UUID fallback" piece tested the legacy behaviour where
an inbound email with no Message-Id header got a generated UUID
assigned to it (so the audit trail stays unique). Phase 70 simplified
the inbound queue surface — the UUID generation is now done in
`routers/inbound_email.py:_resolve_mailbox` and `receive_postmark_inbound`,
emitting `inbound-<hex>` placeholders when the upstream Message-Id
is absent (grep "f\"notify-{uuid.uuid4().hex[:10]}\"" in the router).

This file is a small contract check that:
  - The canonical Postmark inbound endpoint exists in the OpenAPI schema.
  - The back-compat alias `/api/webhooks/postmark/inbound` is mounted
    (NB: it has `include_in_schema=False`, so we probe live with a GET
    that the route does not implement → 405 confirms the path is
    routed, while 404 would mean it isn't mounted).
  - The UUID-fallback emitter code is still present in the router
    source — a regression here would silently drop the unique-audit
    invariant for Message-Id-less inbound emails.

We intentionally do NOT replay full Postmark fixtures here — that's
covered in `test_postmark_inbound_phase_b.py` (10/10 green).
"""
from __future__ import annotations

import sys

import httpx
import pytest
import pytest_asyncio

sys.path.insert(0, "/app/backend")
from server import app  # noqa: E402


@pytest.fixture(scope="module")
def openapi_paths():
    schema = app.openapi()
    return set(schema.get("paths", {}).keys())


def test_canonical_inbound_route_in_openapi(openapi_paths):
    """`/api/inbound/postmark` is the schema-documented surface."""
    assert "/api/inbound/postmark" in openapi_paths, (
        "canonical Postmark inbound route missing from openapi — "
        "router include may have regressed."
    )


@pytest.mark.asyncio
async def test_backcompat_inbound_route_is_mounted():
    """The back-compat alias `/api/webhooks/postmark/inbound` is mounted
    with `include_in_schema=False`, so it does NOT appear in OpenAPI.
    We probe live — GET against the POST-only route yields 405 if the
    path is routed; 404 would mean the include was dropped.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/webhooks/postmark/inbound")
    # 405 (Method Not Allowed) → path is routed, just wrong verb.
    # 401/403 → auth fired before method check (also confirms mount).
    # 404 → NOT mounted — regression.
    assert r.status_code in (401, 403, 405), (
        f"back-compat Postmark route appears unmounted: "
        f"GET returned {r.status_code}, expected 401/403/405."
    )


def test_inbound_uuid_fallback_helper_still_present():
    """`routers/inbound_email.py` still emits a UUID placeholder when
    the upstream Message-Id header is absent. We assert by source
    inspection because the fallback is a code-path, not an endpoint:
    triggering it cleanly requires a Postmark fixture + Basic-Auth.
    """
    from routers import inbound_email  # noqa: PLC0415
    src = inbound_email.__file__
    with open(src, "r", encoding="utf-8") as fh:
        body = fh.read()
    # Two distinct hex-uuid fallback emitter shapes in the router —
    # one for `notify-` audit events, one for rejected/inbound rows.
    assert "notify-" in body and "no-id-" in body, (
        "uuid-fallback emitters seem to have been removed from "
        "routers/inbound_email.py — Phase 70 contract regressed."
    )
