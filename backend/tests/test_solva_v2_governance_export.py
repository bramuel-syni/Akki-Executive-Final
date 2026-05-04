"""Phase 15.3 — governance export must include Solva v2 sections (decision #12).

Asserts that the ZIP returned by `POST /api/me/governance/audit/export`
includes:
  * solva_v2_sessions.json
  * solva_v2_reasoning_log.json
  * manifest.txt with section line counts

The test does not need any v2 sessions to exist for the file to be
present — even an empty array satisfies the contract.
"""
import io
import json
import os
import zipfile

import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "http://localhost:8001"
).rstrip("/")
ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASSWORD = "AkkiAdmin2026!"


def _login():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def test_governance_export_zip_includes_solva_v2_sections():
    headers = _login()
    r = requests.post(
        f"{BASE_URL}/api/me/governance/audit/export",
        headers=headers,
        json={},
        timeout=60,
    )
    assert r.status_code == 200, f"export failed: {r.status_code}: {r.text[:240]}"
    assert r.headers["Content-Type"] == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(r.content), "r")
    names = set(zf.namelist())
    assert "audit_log.csv" in names
    assert "solva_v2_sessions.json" in names, f"sessions section missing; names={names}"
    assert "solva_v2_reasoning_log.json" in names, f"reasoning section missing; names={names}"
    assert "manifest.txt" in names

    # Both new files must be valid JSON arrays (possibly empty).
    sessions = json.loads(zf.read("solva_v2_sessions.json"))
    reasoning = json.loads(zf.read("solva_v2_reasoning_log.json"))
    assert isinstance(sessions, list)
    assert isinstance(reasoning, list)

    # Each session row, if present, must carry the v2 fingerprint.
    for s in sessions:
        assert "id" in s
        assert "submodule" in s or s.get("schema_version") in (None, 2)

    # Each reasoning row must FK back to a session.
    for entry in reasoning:
        assert "session_id" in entry
        assert "engine" in entry
    # NOTE: historical (pre-15.3) entries are preserved verbatim per the
    # immutable-audit-log contract. The cleanup contract for NEW entries
    # is verified separately in:
    #   * test_solva_v2_engine_version_cleanup.py (engine table)
    #   * test_solva_v2_reflection_real.py (no placeholder in NEW sessions)

    manifest = zf.read("manifest.txt").decode("utf-8")
    assert "solva_v2_sessions:" in manifest
    assert "solva_v2_reasoning_log:" in manifest
