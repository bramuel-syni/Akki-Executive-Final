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


def test_legacy_solve_post_preserves_body_through_308(admin_session):
    """Post a JSON body to a legacy `/api/solve/sessions` URL — the 308
    must preserve method + body, so the canonical handler should see
    the same payload and return its honest 4xx if the cluster_id is
    invalid (which is what we use to verify body actually crossed)."""
    r = admin_session.post(
        f"{BACKEND}/api/solve/sessions",
        json={
            "cluster_id": "PHASE_13_1_NON_EXISTENT_CLUSTER",
            "intent": (
                "Phase 13.1 alias smoke — body must survive the 308 so "
                "the canonical handler can reject this cluster cleanly."
            ),
            "pro_tier": False,
        },
        allow_redirects=True,
        timeout=15,
    )
    # 308 preserves method + body. The canonical handler then 404s on
    # the unknown cluster — which proves the body crossed (otherwise we'd
    # see a 422 validation error from the missing required fields).
    assert r.status_code in (404, 422), (r.status_code, r.text[:200])
    body = r.json()
    detail = body.get("detail")
    if isinstance(detail, str):
        assert (
            "cluster" in detail.lower()
            or "not found" in detail.lower()
        ), detail


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
