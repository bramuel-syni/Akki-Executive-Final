"""P5.11 — Notify gating + sister CSRF fixes + cleanup hygiene.

Source-strict + light runtime lockdowns covering:

  P5.11.1 — `scripts/cleanup_test_pollution.py` exposes the right
            CLI surface (dry-run default; --apply destructive;
            --keep-after recency guard; audit-row writer).
  P5.11.2 — `COHORT_NOTIFY_DISABLED` is honoured in the three notify
            entry points, AND the pytest session auto-sets it via
            conftest. One runtime test mocks SendGridAPIClient and
            asserts no real send happens when the flag is set.
  P5.11.4 — Sister raw-fetch sites now inject `X-CSRF-Token`. The
            sandbox and sensitivity-demo endpoints stay OUT of the
            CSRF allowlist (security invariant).
"""
from __future__ import annotations

import importlib
import os
import re
import sys
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))


# ─────────────────────────────────────────────────────────────────
# P5.11.1 — Cleanup script surface
# ─────────────────────────────────────────────────────────────────


def test_cleanup_script_exists_and_is_python():
    p = REPO / "scripts" / "cleanup_test_pollution.py"
    assert p.exists(), "cleanup_test_pollution.py missing"
    text = p.read_text(encoding="utf-8")
    assert text.startswith('"""'), "cleanup script must lead with a docstring"


def test_cleanup_script_dry_run_is_default():
    """`--apply` MUST be explicit; the parser default must NOT be set."""
    src = (REPO / "scripts" / "cleanup_test_pollution.py").read_text(encoding="utf-8")
    # The arg MUST be `action="store_true"` (default=False) — i.e. dry-run wins.
    assert 'p.add_argument("--apply", action="store_true"' in src, (
        "--apply must be a store_true flag (dry-run is the default)"
    )


def test_cleanup_script_supports_keep_after():
    src = (REPO / "scripts" / "cleanup_test_pollution.py").read_text(encoding="utf-8")
    assert 'p.add_argument("--keep-after"' in src
    # The default MUST be `datetime.now(timezone.utc).isoformat()` (i.e. now).
    assert "datetime.now(timezone.utc).isoformat()" in src


def test_cleanup_script_writes_audit_row():
    """Every run (dry or apply) MUST insert into `admin_cleanup_audit`."""
    src = (REPO / "scripts" / "cleanup_test_pollution.py").read_text(encoding="utf-8")
    assert "db.admin_cleanup_audit.insert_one" in src
    assert '"mode"' in src and '"dry_run"' in src and '"apply"' in src


def test_cleanup_script_targets_all_required_collections():
    src = (REPO / "scripts" / "cleanup_test_pollution.py").read_text(encoding="utf-8")
    for coll in (
        "cohort_applications",
        "cohort_magic_links",
        "cohort_waitlist",
        "admin_inbox_messages",
        "cohort_application_audit",
    ):
        assert coll in src, f"cleanup script does not target {coll}"


# ─────────────────────────────────────────────────────────────────
# P5.11.2 — Notify gating
# ─────────────────────────────────────────────────────────────────


def test_conftest_sets_cohort_notify_disabled_for_test_session():
    src = (REPO / "backend" / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert 'os.environ.setdefault("COHORT_NOTIFY_DISABLED", "true")' in src


def test_cohort_notify_disabled_is_actually_set_in_this_session():
    """The runtime side of the conftest assertion above. Belt-and-braces."""
    assert os.environ.get("COHORT_NOTIFY_DISABLED", "").lower() == "true", (
        "conftest.py did not set COHORT_NOTIFY_DISABLED for this pytest session"
    )


def test_cohort_email_service_honours_disable_flag_at_import():
    src = (REPO / "backend" / "services" / "cohort_email.py").read_text(encoding="utf-8")
    assert "COHORT_NOTIFY_DISABLED" in src
    assert "_notify_disabled" in src
    # The guard MUST fire INSIDE `_send_via_sendgrid` BEFORE the
    # SendGridAPIClient import — otherwise we'd still consume the
    # SDK dependency at runtime.
    pre_send = src.split("def _send_via_sendgrid", 1)[1].split("api_key = ", 1)[0]
    assert "_notify_disabled" in pre_send, (
        "_send_via_sendgrid must check _notify_disabled BEFORE reading SENDGRID_API_KEY"
    )


def test_cohort_applications_notify_founder_honours_disable_flag():
    src = (REPO / "backend" / "routers" / "cohort_applications.py").read_text(encoding="utf-8")
    func = src.split("def _notify_founder", 1)[1].split("def ", 1)[0]
    assert "COHORT_NOTIFY_DISABLED" in func, (
        "_notify_founder must read COHORT_NOTIFY_DISABLED"
    )
    # The early-return MUST happen BEFORE `_parse_founder_recipients` runs.
    pre_recipients = func.split("recipients = _parse_founder_recipients", 1)[0]
    assert "COHORT_NOTIFY_DISABLED" in pre_recipients


def test_website_router_honours_disable_flag_on_both_notify_paths():
    src = (REPO / "backend" / "routers" / "website.py").read_text(encoding="utf-8")
    # The shared helper must exist:
    assert "_notify_disabled" in src
    # The early-access notify MUST gate on it:
    early_block = src.split('EARLY_ACCESS_NOTIFY_EMAIL"', 1)[1].split("send_email(", 1)[0]
    assert "_notify_disabled" in early_block, (
        "early-access notify path does not call _notify_disabled() before sending"
    )
    # The contact notify MUST gate on it:
    contact_block = src.split('CONTACT_NOTIFY_EMAIL"', 1)[1].split("send_email(", 1)[0]
    assert "_notify_disabled" in contact_block, (
        "contact notify path does not call _notify_disabled() before sending"
    )


def test_cohort_email_send_returns_test_mode_disabled_when_flag_set(monkeypatch):
    """Mock SendGrid client. With `COHORT_NOTIFY_DISABLED=true`,
    `_send_via_sendgrid` MUST return without instantiating the
    SendGridAPIClient class. We assert by mocking the class
    constructor and confirming it was NEVER called."""
    monkeypatch.setenv("COHORT_NOTIFY_DISABLED", "true")
    # `services.cohort_email` reads env at call-time (not import-time
    # for the flag), so re-import is unnecessary, but the SDK
    # constructor is imported INSIDE _send_via_sendgrid — we patch
    # at the package path it imports from.
    mod = importlib.import_module("services.cohort_email")
    fake_send = mock.MagicMock()
    with mock.patch.dict("sys.modules", clear=False):
        with mock.patch("sendgrid.SendGridAPIClient", fake_send):
            out = mod._send_via_sendgrid(
                to_email="probe@example.com",
                subject="probe",
                plain_body="hello",
            )
    assert out["status"] == "test_mode_disabled", out
    assert out["reason"] == "COHORT_NOTIFY_DISABLED"
    assert fake_send.call_count == 0, (
        f"SendGridAPIClient was instantiated {fake_send.call_count} time(s); "
        "the disable flag should have short-circuited"
    )


# ─────────────────────────────────────────────────────────────────
# P5.11.4 — Sister CSRF fixes
# ─────────────────────────────────────────────────────────────────


def test_sandbox_api_js_imports_ensure_csrf_token():
    src = (REPO / "frontend" / "src" / "sandbox" / "api.js").read_text(encoding="utf-8")
    assert re.search(
        r"import\s*\{[^}]*\bensureCsrfToken\b[^}]*\}\s*from\s*[\"']@/lib/api[\"']",
        src,
    ), "sandbox/api.js does not import ensureCsrfToken"


def test_sandbox_api_js_sends_csrf_header_on_post():
    src = (REPO / "frontend" / "src" / "sandbox" / "api.js").read_text(encoding="utf-8")
    # The whole file MUST request CSRF + set the header (the create
    # helper may pull either inline or through a shared `_csrfHeaders`
    # helper at top-of-file).
    assert "await ensureCsrfToken()" in src, (
        "sandbox/api.js does not await ensureCsrfToken()"
    )
    assert '"X-CSRF-Token"' in src, (
        "sandbox/api.js does not set X-CSRF-Token header"
    )
    # And the POST helper MUST reach the headers either inline or via
    # the shared helper.
    create_block = src.split("createSandboxSession", 1)[1].split("export async function getSandbox", 1)[0]
    has_inline = "await ensureCsrfToken()" in create_block
    has_helper = "_csrfHeaders()" in create_block
    assert has_inline or has_helper, (
        "createSandboxSession does not request CSRF headers"
    )


def test_sandbox_api_js_sends_csrf_header_on_delete():
    src = (REPO / "frontend" / "src" / "sandbox" / "api.js").read_text(encoding="utf-8")
    delete_block = src.split("deleteSandboxSession", 1)[1]
    assert "await ensureCsrfToken()" in delete_block, (
        "deleteSandboxSession does not await ensureCsrfToken()"
    )
    assert '"X-CSRF-Token"' in delete_block, (
        "deleteSandboxSession does not set X-CSRF-Token header"
    )


def test_enterprise_feature_imports_ensure_csrf_token():
    src = (REPO / "frontend" / "src" / "components" / "marketing" / "EnterpriseFeature.jsx").read_text(encoding="utf-8")
    assert re.search(
        r"import\s*\{[^}]*\bensureCsrfToken\b[^}]*\}\s*from\s*[\"']@/lib/api[\"']",
        src,
    ), "EnterpriseFeature.jsx does not import ensureCsrfToken"


def test_enterprise_feature_sends_csrf_header_on_post():
    src = (REPO / "frontend" / "src" / "components" / "marketing" / "EnterpriseFeature.jsx").read_text(encoding="utf-8")
    score_block = src.split("const score = async", 1)[1].split("const onChange", 1)[0]
    assert "await ensureCsrfToken()" in score_block, (
        "EnterpriseFeature.score() does not await ensureCsrfToken()"
    )
    assert '"X-CSRF-Token"' in score_block, (
        "EnterpriseFeature.score() does not set X-CSRF-Token header"
    )


def test_sister_endpoints_are_not_in_csrf_allowlist():
    """Security invariant: the sandbox + public-sensitivity-demo
    routes are state-changing POSTs/DELETEs and MUST remain CSRF-
    protected. They MUST NOT appear in the allowlist."""
    src = (REPO / "backend" / "services" / "csrf.py").read_text(encoding="utf-8")
    for path in (
        "/api/sandbox-gen",
        "/api/public/studio/sensitivity-demo",
    ):
        assert path not in src, (
            f"{path} MUST NOT be in the CSRF allowlist "
            "(state-changing public endpoint — keep CSRF protection)"
        )
