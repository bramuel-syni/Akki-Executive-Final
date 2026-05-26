"""Admin email-provider health-ping endpoint — 2026-05-26.

Surface for operators to verify SendGrid wiring without sending a
real email. Admin-only. Never logs secret values. NEVER 500s — all
errors land in `warnings[]`.

Endpoint
========

`GET /api/admin/email-provider/health`

Sample response shape:
```json
{
  "active_provider": "sendgrid",
  "from_email_configured": true,
  "inbound_domain_configured": true,
  "basic_auth_configured": true,
  "outbound_smoke": {
    "ok": true,
    "provider_response_ms": 234,
    "sandbox_mode": true
  },
  "inbound_parse": {
    "domain": "inbound.akki.example.com",
    "webhook_path": "/api/inbound/sendgrid",
    "ready": true
  },
  "warnings": []
}
```

Implementation notes
====================
* Outbound smoke uses SendGrid's `mail_settings.sandbox_mode` flag —
  the request is validated by the SendGrid API but no email is
  delivered. Falls back to env-only validation when the SDK is not
  importable or `SENDGRID_API_KEY` is unset.
* `inbound_parse.ready` is true iff `SENDGRID_INBOUND_DOMAIN` is set
  AND the `/api/inbound/sendgrid` route is mounted on the running
  app. We do NOT POST to the inbound route from the health-ping.
* Audit row written:
  `admin.email_provider.health_check` with `metadata.provider` +
  `metadata.warnings_count` (NO secret values).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from core import db, get_current_account

logger = logging.getLogger("akki.admin.email_health")

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def _require_admin(current: Dict[str, Any] = Depends(get_current_account)) -> Dict[str, Any]:
    if not current.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin only.")
    return current


def _route_mounted(request: Request, path: str) -> bool:
    """Return True iff `path` is mounted on the running FastAPI app
    (regardless of method). Used to confirm the inbound parse route
    is live without invoking it."""
    try:
        for r in request.app.routes:
            if getattr(r, "path", None) == path:
                return True
    except Exception:  # noqa: BLE001
        return False
    return False


def _sendgrid_sandbox_smoke(api_key: str, from_email: str) -> Dict[str, Any]:
    """Validate the SendGrid API credential + from address by sending
    a sandbox-mode mail (no actual delivery). SendGrid returns 200 OK
    when the envelope is valid AND `sandbox_mode: true`.

    Returns `{ok, provider_response_ms, sandbox_mode, error?}`.
    """
    start = time.perf_counter()
    try:
        from sendgrid import SendGridAPIClient  # type: ignore
        from sendgrid.helpers.mail import (  # type: ignore
            Mail, Email, To, Content, MailSettings, SandBoxMode,
        )
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "sandbox_mode": False,
            "error": f"sendgrid SDK not importable: {e!s}"[:200],
            "provider_response_ms": None,
        }
    mail = Mail(
        from_email=Email(from_email or "noreply@akki.example.com"),
        to_emails=To("smoke-target@example.com"),
        subject="AKKI health-ping (sandbox)",
        plain_text_content=Content("text/plain", "Sandbox validation only — no delivery."),
    )
    try:
        ms = MailSettings()
        ms.sandbox_mode = SandBoxMode(enable=True)
        mail.mail_settings = ms
    except Exception:  # noqa: BLE001
        # SDK shape changed — fall back to manual JSON injection so we
        # never raise from the health-ping.
        try:
            mail.mail_settings = {"sandbox_mode": {"enable": True}}  # type: ignore
        except Exception:  # noqa: BLE001
            pass
    try:
        sg = SendGridAPIClient(api_key)
        resp = sg.send(mail)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        status = getattr(resp, "status_code", 0)
        ok = 200 <= int(status) < 300
        out: Dict[str, Any] = {
            "ok": ok,
            "provider_response_ms": elapsed_ms,
            "sandbox_mode": True,
        }
        if not ok:
            out["error"] = f"sendgrid status {status}"
        return out
    except Exception as e:  # noqa: BLE001
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "ok": False,
            "provider_response_ms": elapsed_ms,
            "sandbox_mode": True,
            "error": str(e)[:200],
        }


@router.get("/email-provider/health")
async def email_provider_health(
    request: Request,
    current: Dict[str, Any] = Depends(_require_admin),
):
    """Return a health summary of the configured email provider.
    Never raises — errors surface in `warnings[]`. Never returns 500.

    The endpoint deliberately avoids logging secret values (e.g., the
    API key itself). It reports only whether each env var is set.
    """
    warnings: List[str] = []

    sendgrid_key      = (os.environ.get("SENDGRID_API_KEY") or "").strip()
    from_email        = (os.environ.get("SENDGRID_FROM_EMAIL") or "").strip()
    inbound_domain    = (os.environ.get("SENDGRID_INBOUND_DOMAIN") or "").strip()
    inbound_user      = (os.environ.get("SENDGRID_INBOUND_AUTH_USERNAME") or "").strip()
    inbound_pw        = (os.environ.get("SENDGRID_INBOUND_AUTH_PASSWORD") or "").strip()
    resend_key        = (os.environ.get("RESEND_API_KEY") or "").strip()

    # Active provider — mirror the email_service._provider() logic
    # without importing it (we'd rather not couple this admin surface
    # to the service's runtime state).
    forced = (os.environ.get("EMAIL_PROVIDER") or "").strip().lower()
    if forced == "resend" and resend_key:
        active_provider = "resend"
    elif forced == "sendgrid" and sendgrid_key:
        active_provider = "sendgrid"
    elif sendgrid_key:
        active_provider = "sendgrid"
    elif resend_key:
        active_provider = "resend"
    else:
        active_provider = "none"

    from_email_configured     = bool(from_email)
    inbound_domain_configured = bool(inbound_domain)
    basic_auth_configured     = bool(inbound_user and inbound_pw)

    # Warnings — surface common misconfigs.
    if active_provider == "none":
        warnings.append("No email provider configured — set SENDGRID_API_KEY (or RESEND_API_KEY as legacy fallback).")
    if active_provider == "sendgrid" and not from_email_configured:
        warnings.append("SENDGRID_FROM_EMAIL is not set — outbound mail will be rejected by SendGrid.")
    if active_provider == "sendgrid" and not inbound_domain_configured:
        warnings.append("SENDGRID_INBOUND_DOMAIN is not set — F.5 email-reply contributor mode will not function.")
    if active_provider == "sendgrid" and inbound_domain_configured and not basic_auth_configured:
        warnings.append("Basic Auth not configured (recommended for production) — set SENDGRID_INBOUND_AUTH_USERNAME and SENDGRID_INBOUND_AUTH_PASSWORD.")
    if active_provider == "resend":
        warnings.append("Active provider is Resend (legacy). SendGrid is the preferred provider as of 2026-05-26.")

    # Outbound smoke — sandbox-mode SendGrid send (no actual delivery).
    if active_provider == "sendgrid" and sendgrid_key and from_email_configured:
        try:
            outbound = _sendgrid_sandbox_smoke(sendgrid_key, from_email)
        except Exception as e:  # noqa: BLE001
            outbound = {"ok": False, "sandbox_mode": False,
                        "error": f"smoke crashed: {e!s}"[:200],
                        "provider_response_ms": None}
        if not outbound.get("ok"):
            warnings.append("Outbound smoke failed: " + (outbound.get("error") or "unknown error"))
    else:
        outbound = {
            "ok": False,
            "sandbox_mode": False,
            "provider_response_ms": None,
            "error": "skipped — provider/credentials/from-email not all configured",
        }

    # Inbound parse readiness — env vars set + route mounted.
    inbound_route_mounted = _route_mounted(request, "/api/inbound/sendgrid")
    inbound_ready = inbound_domain_configured and inbound_route_mounted
    if active_provider == "sendgrid" and inbound_domain_configured and not inbound_route_mounted:
        warnings.append("Inbound parse route /api/inbound/sendgrid is NOT mounted — server reload required.")

    body: Dict[str, Any] = {
        "active_provider":            active_provider,
        "from_email_configured":      from_email_configured,
        "inbound_domain_configured":  inbound_domain_configured,
        "basic_auth_configured":      basic_auth_configured,
        "outbound_smoke":             outbound,
        "inbound_parse": {
            "domain":          inbound_domain or None,
            "webhook_path":    "/api/inbound/sendgrid",
            "ready":           inbound_ready,
            "route_mounted":   inbound_route_mounted,
        },
        "warnings":                   warnings,
    }

    # Audit row — never log secret values.
    try:
        from datetime import datetime, timezone
        import uuid as _uuid
        await db.audit_log.insert_one({
            "id":           str(_uuid.uuid4()),
            "account_id":   current["id"],
            "action":       "admin.email_provider.health_check",
            "verb":         "read",
            "resource_id":  None,
            "context_id":   None,
            "metadata": {
                "provider":         active_provider,
                "warnings_count":   len(warnings),
                "outbound_ok":      bool(outbound.get("ok")),
                "inbound_ready":    inbound_ready,
            },
            "created_at":  datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:  # noqa: BLE001
        # Audit failure must not 500 the health-ping.
        logger.warning("email-provider health audit log write failed: %s", e)

    return JSONResponse(status_code=200, content=body)
