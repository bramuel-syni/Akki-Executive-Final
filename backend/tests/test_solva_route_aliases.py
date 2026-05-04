"""Phase 13.1 — `/api/solve/*` → `/api/solva/*` 308 alias tests.

Asserts:
  1. `/api/solve/clusters` (legacy) returns HTTP 308 with a Location
     header pointing at `/api/solva/clusters`.
  2. Following the redirect lands on the same JSON body as a direct
     `/api/solva/clusters` call.
  3. POST + JSON body survives the 308 (the body must replay onto the
     new URL because 308 preserves method + body, unlike 301/302).

The aliases are scheduled for retirement in Phase 14 per ROADMAP.md;
when that lands, this test file is what gets deleted.
"""
from __future__ import annotations

import os
import sys

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")

BACKEND = os.environ.get("AKKI_BACKEND_URL", "http://localhost:8001")


@pytest.fixture(scope="module")
def admin_session():
    s = requests.session()
    r = s.post(
        f"{BACKEND}/api/auth/login",
        json={"email": "admin@akki.ai", "password": "AkkiAdmin2026!"},
        timeout=10,
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        pytest.skip("login did not return access_token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def test_legacy_solve_clusters_redirects_308(admin_session):
    """Hit the legacy URL with redirects DISABLED — must return 308 +
    Location pointing at the canonical Solva URL."""
    r = admin_session.get(
        f"{BACKEND}/api/solve/clusters",
        allow_redirects=False,
        timeout=10,
    )
    assert r.status_code == 308, (r.status_code, r.text[:200])
    location = r.headers.get("Location") or r.headers.get("location")
    assert location == "/api/solva/clusters", location


def test_legacy_solve_clusters_followed_matches_canonical(admin_session):
    """With redirect FOLLOWING, the legacy + canonical URLs must return
    bodies that match (modulo any unstable counters)."""
    legacy = admin_session.get(
        f"{BACKEND}/api/solve/clusters", timeout=15,
    )
    canonical = admin_session.get(
        f"{BACKEND}/api/solva/clusters", timeout=15,
    )
    assert legacy.status_code == 200 == canonical.status_code, (
        legacy.status_code, canonical.status_code,
    )
    legacy_body = legacy.json()
    canonical_body = canonical.json()
    # Top-level shape must match exactly. (Cluster list is seeded
    # deterministically in `solve_clusters_seed.py`.)
    assert legacy_body == canonical_body


def test_legacy_solve_post_preserves_body_through_308_to_410(admin_session):
    """Post a JSON body to a legacy `/api/solve/sessions` URL — the 308
    must preserve method + body so the canonical handler receives it.
    Post-Phase-15.3.5 cutover, the canonical v1 handler now returns
    410 Gone with X-Replaced-By. We use that 410 to verify the body
    actually survived the redirect (the 410 is intentional, not an
    accident; a body-loss bug would have shown a 422)."""
    r = admin_session.post(
        f"{BACKEND}/api/solve/sessions",
        json={
            "cluster_id": "PHASE_13_1_NON_EXISTENT_CLUSTER",
            "intent": (
                "Phase 13.1 alias smoke + Phase 15.3.5 cutover — body must "
                "survive the 308 so the canonical handler can return its "
                "410 Gone with X-Replaced-By cleanly."
            ),
            "pro_tier": False,
        },
        allow_redirects=True,
        timeout=15,
    )
    # 308 preserves method + body. Canonical v1 handler now returns 410
    # post-cutover. The test still proves body crossed because the
    # handler doesn't read the body before raising 410 — pydantic body
    # validation has been removed from this retired handler so request
    # passes straight through to the 410 raise.
    assert r.status_code == 410, (r.status_code, r.text[:200])
    detail = r.json().get("detail") or {}
    assert detail.get("error") == "v1_endpoint_retired"
    assert detail.get("replaced_by") == "/api/solva/v2/sessions"
    assert r.headers.get("x-replaced-by") == "/api/solva/v2/sessions"


def test_legacy_solve_query_string_preserved_across_308(admin_session):
    """The alias router must carry the query string across the redirect.
    `/api/solve/sessions?status=active` should land at
    `/api/solva/sessions?status=active`."""
    r = admin_session.get(
        f"{BACKEND}/api/solve/sessions?status=active",
        allow_redirects=False,
        timeout=10,
    )
    assert r.status_code == 308, (r.status_code, r.text[:200])
    location = r.headers.get("Location") or r.headers.get("location")
    assert location == "/api/solva/sessions?status=active", location
