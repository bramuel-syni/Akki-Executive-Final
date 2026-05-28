"""Phase V (2026-05-27) — Admin user CRUD portal CI lockdown.

Locks the W7 stock-take #1 closure plus the W7 #4 data-safety contract:
  • 7 endpoints exist under `/api/admin/users`.
  • All are `_require_superadmin` gated.
  • LIST returns the LIST_FIELDS allowlist (no password_hash etc.).
  • TIMELINE returns ONLY the operational metadata of each
    feature_events row — never the `payload` field. The user's
    promise is "telemetry, not data peeking" — enforced here.
  • SUSPEND triggers a 401 in `get_current_account` for the
    suspended account.
  • CREATE supports both passwordful and passwordless mints.
  • EXPORT.CSV returns a CSV stream with the allowlist columns.
  • Frontend page mounts at `/app/admin/users` + carries the locked
    testids for the data-safety panel.
"""
from __future__ import annotations

import asyncio
import csv
import io
import os
import sys
from pathlib import Path
from typing import Dict, Any

import pytest


REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))


ROUTER     = REPO / "backend" / "routers" / "admin_users.py"
SERVER     = REPO / "backend" / "server.py"
CORE       = REPO / "backend" / "core.py"
PAGE       = REPO / "frontend" / "src" / "pages" / "admin" / "AdminUsers.jsx"
APP_JS     = REPO / "frontend" / "src" / "App.js"


# ─────────────────────────────────────────────────────────────────────
# Source-strict structural locks
# ─────────────────────────────────────────────────────────────────────

def test_PhaseV_a_router_module_exists():
    assert ROUTER.exists()


def test_PhaseV_b_router_declares_seven_endpoints():
    src = ROUTER.read_text(encoding="utf-8")
    expected = [
        '@router.get("")',                          # list
        '@router.post("", status_code=201)',        # create
        '@router.get("/export.csv")',               # csv
        '@router.get("/{user_id}")',                # get one
        '@router.post("/{user_id}/suspend")',       # suspend
        '@router.post("/{user_id}/restore")',       # restore
        '@router.get("/{user_id}/timeline")',       # timeline
    ]
    for sig in expected:
        assert sig in src, f"Phase V router must declare endpoint signature: {sig!r}"


def test_PhaseV_c_all_endpoints_are_superadmin_gated():
    src = ROUTER.read_text(encoding="utf-8")
    # Every endpoint MUST depend on `_require_superadmin`.
    assert src.count("_admin: Dict[str, Any] = Depends(_require_superadmin)") >= 7, \
        "All 7 Phase V endpoints must declare `_require_superadmin` Depends"


def test_PhaseV_d_list_fields_allowlist_excludes_sensitive_fields():
    src = ROUTER.read_text(encoding="utf-8")
    # The LIST_FIELDS set declared in the router MUST NOT include
    # any of the SENSITIVE_FIELDS.
    sensitive = ("password_hash", "magic_link_token", "reset_password_token", "sessions_revoked_after")
    # Capture the LIST_FIELDS block.
    list_fields_pos = src.find("LIST_FIELDS = {")
    assert list_fields_pos > 0
    list_block_end = src.find("}", list_fields_pos)
    list_block = src[list_fields_pos:list_block_end]
    for s in sensitive:
        assert f'"{s}"' not in list_block, \
            f"LIST_FIELDS allowlist must NOT contain {s!r}"


def test_PhaseV_e_timeline_strips_payload_field():
    """W7 #4 data-safety contract: timeline endpoint MUST return only
    operational metadata, never the `payload` field that may contain
    user-typed content."""
    src = ROUTER.read_text(encoding="utf-8")
    # TIMELINE_FIELDS allowlist must NOT include "payload".
    tl_pos = src.find("TIMELINE_FIELDS = (")
    assert tl_pos > 0
    block_end = src.find(")", tl_pos)
    block = src[tl_pos:block_end]
    assert '"payload"' not in block and "'payload'" not in block, \
        "TIMELINE_FIELDS allowlist must NOT include 'payload' (data-safety contract)"
    # And the endpoint body must use the allowlist explicitly.
    assert "items.append({k: row.get(k) for k in TIMELINE_FIELDS})" in src


def test_PhaseV_f_suspend_blocks_in_get_current_account():
    """The suspension flip in `get_current_account` triggers a 401 with
    the locked ACCOUNT_SUSPENDED detail."""
    src = CORE.read_text(encoding="utf-8")
    assert 'account.get("status") == "suspended"' in src, \
        "get_current_account must check for status=='suspended'"
    assert '"code": "ACCOUNT_SUSPENDED"' in src, \
        "get_current_account must raise 401 with ACCOUNT_SUSPENDED code"
    assert '"message": "Account suspended"' in src, \
        "get_current_account must surface the locked Account suspended message"


def test_PhaseV_g_suspend_safety_blocks_self_suspend():
    """A superadmin MUST NOT be able to suspend themselves (otherwise
    they lock themselves out of the portal)."""
    src = ROUTER.read_text(encoding="utf-8")
    assert 'user_id == _admin.get("id")' in src, \
        "suspend_user must guard against self-suspension"
    assert "Cannot suspend yourself" in src


def test_PhaseV_h_create_supports_passwordful_and_passwordless():
    src = ROUTER.read_text(encoding="utf-8")
    # Passwordful branch — bcrypt hash + auth_provider='password'.
    assert "bcrypt.hashpw" in src
    assert '"auth_provider": "password"' in src or 'doc["auth_provider"] = "password"' in src
    # Passwordless branch.
    assert '"passwordless"' in src


def test_PhaseV_i_create_emits_audit_feature_event():
    src = ROUTER.read_text(encoding="utf-8")
    assert "admin.user.created" in src, \
        "create_user must emit feature_events.admin.user.created"
    assert "admin.user.suspended" in src
    assert "admin.user.restored" in src


def test_PhaseV_j_export_csv_uses_allowlist_columns():
    src = ROUTER.read_text(encoding="utf-8")
    # The CSV writer MUST use the LIST_FIELDS allowlist (not the raw
    # account row) so sensitive fields can never leak.
    assert "DictWriter" in src
    assert "_sanitize_for_list(row)" in src, \
        "export_users_csv must apply the _sanitize_for_list allowlist before writing rows"
    # MIME + filename headers.
    assert 'media_type="text/csv"' in src
    assert "Content-Disposition" in src


def test_PhaseV_k_server_registers_router():
    src = SERVER.read_text(encoding="utf-8")
    assert "admin_users as admin_users_router" in src
    assert "app.include_router(admin_users_router.router)" in src


# ─────────────────────────────────────────────────────────────────────
# Frontend page — locked testids + data-safety surface
# ─────────────────────────────────────────────────────────────────────

def test_PhaseV_l_app_js_registers_admin_users_route():
    src = APP_JS.read_text(encoding="utf-8")
    assert "import AdminUsers" in src or 'lazy(() => import("@/pages/admin/AdminUsers"))' in src
    assert '<Route path="/app/admin/users"' in src


def test_PhaseV_m_page_carries_locked_testids():
    src = PAGE.read_text(encoding="utf-8")
    for testid in (
        "admin-users-page", "admin-users-h1",
        "admin-users-export-csv", "admin-users-create",
        "admin-users-filters", "admin-users-search",
        "admin-users-filter-cohort", "admin-users-filter-trial",
        "admin-users-filter-role", "admin-users-filter-status",
        "admin-users-table", "admin-users-create-dialog",
        "admin-users-create-submit", "admin-users-timeline-dialog",
        "admin-users-timeline-safety",
    ):
        assert testid in src, f"AdminUsers.jsx must carry testid {testid!r}"


def test_PhaseV_n_page_surfaces_data_safety_promise_to_user():
    """The timeline panel must SHOW the superadmin that the timeline
    is telemetry-only, never user content. This is the user-visible
    half of the W7 #4 data-safety contract."""
    src = PAGE.read_text(encoding="utf-8")
    # Locked copy on the timeline drilldown panel.
    assert "Telemetry only — surface + action + when. We never show what the user typed." in src, \
        "Timeline dialog must surface the locked data-safety promise to the superadmin"


def test_PhaseV_o_page_uses_table_layout_with_pagination():
    src = PAGE.read_text(encoding="utf-8")
    assert 'data-testid="admin-users-pagination"' in src
    assert 'data-testid="admin-users-prev-page"' in src
    assert 'data-testid="admin-users-next-page"' in src


# ─────────────────────────────────────────────────────────────────────
# Live integration tests via direct endpoint probes (bypass HTTP)
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_PhaseV_p_timeline_endpoint_strips_payload_in_response():
    """End-to-end: insert a feature_events row with a sensitive
    `payload`, hit the timeline endpoint via TestClient, and assert
    the payload field is NOT in any returned event."""
    os.environ.setdefault("JWT_SECRET", "test-secret-phase-v")
    from core import db  # noqa: WPS433
    from routers.admin_users import user_timeline, _require_superadmin  # noqa: WPS433

    # Seed an account + an event with a "secret" payload.
    test_aid = "phase-v-timeline-probe-acct"
    await db.accounts.delete_many({"id": test_aid})
    await db.feature_events.delete_many({"account_id": test_aid})
    await db.accounts.insert_one({
        "id": test_aid, "email": "phase-v-probe@example.com",
        "email_lc": "phase-v-probe@example.com",
        "status": "active", "is_superadmin": False,
    })
    secret_payload = {
        "user_typed_message": "THIS IS A SECRET MESSAGE — should never leak",
        "doc_body":           "Confidential board pack content",
    }
    await db.feature_events.insert_one({
        "id":          "phase-v-timeline-probe-event",
        "account_id":  test_aid,
        "event_type":  "test.surface.opened",
        "occurred_at": "2026-05-27T10:00:00Z",
        "surface":     "test_surface",
        "payload":     secret_payload,
    })

    # Fake superadmin (the dependency check uses is_superadmin).
    fake_admin: Dict[str, Any] = {"id": "phase-v-superadmin-probe", "is_superadmin": True}

    class _Req:  # minimal stub for the FastAPI Request param (unused by user_timeline body)
        pass

    res = await user_timeline(user_id=test_aid, request=_Req(), page=1, page_size=10, _admin=fake_admin)

    # Cleanup before asserts so a failed assert doesn't leak rows.
    await db.accounts.delete_many({"id": test_aid})
    await db.feature_events.delete_many({"account_id": test_aid})

    assert len(res["items"]) == 1, "timeline must return the seeded event"
    ev = res["items"][0]
    assert ev["event_type"] == "test.surface.opened"
    assert ev["surface"]    == "test_surface"
    # THE CONTRACT: payload must be ABSENT from the response.
    assert "payload" not in ev, \
        "WAVE 7 #4 PROMISE BROKEN: 'payload' field leaked from timeline response"
    # Belt-and-braces: the secret strings must not appear anywhere in
    # the serialized response.
    import json
    blob = json.dumps(res)
    assert "THIS IS A SECRET MESSAGE" not in blob, \
        "WAVE 7 #4 PROMISE BROKEN: user-typed payload content surfaced in timeline JSON"
    assert "Confidential board pack content" not in blob


@pytest.mark.asyncio
async def test_PhaseV_q_list_endpoint_strips_password_hash():
    """List endpoint MUST exclude password_hash from response rows
    (defence in depth — the Mongo projection drops _id; the
    _sanitize_for_list allowlist drops everything else)."""
    os.environ.setdefault("JWT_SECRET", "test-secret-phase-v")
    from core import db  # noqa: WPS433
    from routers.admin_users import list_users  # noqa: WPS433

    test_aid = "phase-v-list-probe-acct"
    await db.accounts.delete_many({"id": test_aid})
    await db.accounts.insert_one({
        "id": test_aid, "email": "phase-v-list-probe@example.com",
        "email_lc": "phase-v-list-probe@example.com",
        "first_name": "List Probe", "logo_name": "Probe Co",
        "declared_role": "ned", "cohort_tag": "phase-v-list-test",
        "trial_status": "active_trial", "status": "active",
        "is_superadmin": False, "created_at": "2026-05-27T10:00:00Z",
        "password_hash": "$2b$12$THIS_HASH_MUST_NOT_LEAK",
        "magic_link_token": "TOK_MUST_NOT_LEAK",
        "reset_password_token": "RESET_MUST_NOT_LEAK",
    })

    fake_admin: Dict[str, Any] = {"id": "phase-v-superadmin-probe", "is_superadmin": True}

    class _Req:
        pass

    res = await list_users(
        request=_Req(), page=1, page_size=50, sort="created_at", order="desc",
        cohort_tag="phase-v-list-test", trial_status=None, role=None, status=None,
        q=None, _admin=fake_admin,
    )

    await db.accounts.delete_many({"id": test_aid})

    assert any(r["id"] == test_aid for r in res["items"])
    import json
    blob = json.dumps(res)
    for sensitive in ("$2b$12$THIS_HASH_MUST_NOT_LEAK",
                      "TOK_MUST_NOT_LEAK",
                      "RESET_MUST_NOT_LEAK"):
        assert sensitive not in blob, \
            f"List endpoint leaked sensitive field token {sensitive!r}"
