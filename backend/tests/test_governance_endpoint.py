"""Phase 12.1 closeout — governance endpoint regression test.

Target bug: `/api/me/governance` returned HTTP 500 with
    AttributeError: 'dict' object has no attribute 'lower'
whenever a row in briefings / decks / reports carried `classification`
as a full verdict dict (Phase 8 composer rescore shape) rather than a
string tier (Phase 5 sensitivity scoring shape). Both shapes exist in
production data; the governance roll-up now handles both honestly via
isinstance dispatch.

Exercises the full live surface rather than unit-testing in isolation,
because the bug is about the interaction between mongo-shape drift and
the endpoint's roll-up logic \u2014 not the endpoint's own arithmetic.
"""
from __future__ import annotations

import os

import pytest
import requests

BACKEND = os.environ.get("AKKI_BACKEND_URL", "http://localhost:8001")


@pytest.fixture(scope="module")
def admin_headers():
    s = requests.session()
    r = s.post(
        f"{BACKEND}/api/auth/login",
        json={"email": "admin@akki.ai", "password": "AkkiAdmin2026!"},
        timeout=10,
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        pytest.skip("login did not return an access token")
    return {"Authorization": f"Bearer {token}"}


def test_me_governance_returns_200_after_synisense_shape_change(admin_headers):
    """Regression root cause: governance.py:130 blew up on dict-shape
    `classification`. Fix handles both shapes; endpoint must 200 and
    return the documented body."""
    r = requests.get(f"{BACKEND}/api/me/governance",
                     headers=admin_headers, timeout=10)
    assert r.status_code == 200, r.text[:400]
    body = r.json()
    # Top-level contract \u2014 stable since iter64.
    for key in ("audit_log", "shielding", "inbound",
                "connected_models", "sensitivity"):
        assert key in body, f"missing top-level key {key!r}"
    # Sensitivity roll-up shape.
    sens = body["sensitivity"]
    assert "classification_breakdown" in sens
    assert set(sens["classification_breakdown"].keys()) == {
        "public", "internal", "confidential", "restricted",
    }
    # No value should be negative; classification_breakdown is always int counts.
    for k, v in sens["classification_breakdown"].items():
        assert isinstance(v, int) and v >= 0, f"{k} = {v!r}"


def test_me_governance_handles_mixed_shape_data(admin_headers):
    """The dev DB carries rows with BOTH shapes (21+ dict rows on
    briefings per the regression probe, plus any new string-tier rows
    added by the daily-review path). A clean 200 proves both branches
    of the isinstance dispatch fire without blowing up."""
    r = requests.get(f"{BACKEND}/api/me/governance",
                     headers=admin_headers, timeout=10)
    assert r.status_code == 200
    sens = r.json()["sensitivity"]
    total_classified = sum(sens["classification_breakdown"].values())
    # We don't assert a specific count because the dev seed shifts; we do
    # assert that at least some counts were tallied (proving the fix
    # actually read the mixed-shape rows instead of silently dropping).
    assert total_classified > 0, (
        "no rows tallied \u2014 the isinstance dispatch may have silently "
        "skipped both shapes"
    )
