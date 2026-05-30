"""Phase P2 D.1 (2026-02) — Sentry backend wiring (no-op when DSN absent).

Initialises sentry-sdk with the FastAPI integration. Strips PII before
events are sent. Returns the active mode (`"live"` / `"noop"`) so
startup logs can show the explicit state operators expect.

Env contract (documented in `P2_d1_sentry_envs.md`):

| Env                              | Meaning                                      |
|----------------------------------|----------------------------------------------|
| SENTRY_DSN                       | Required to enable Sentry. Absent → no-op.   |
| SENTRY_ENVIRONMENT               | `production` / `staging` / `development`    |
| SENTRY_TRACES_SAMPLE_RATE        | Float 0..1 (default 0.0 — no perf data)     |
| SENTRY_PROFILES_SAMPLE_RATE      | Float 0..1 (default 0.0 — no profiling)     |
| SENTRY_SEND_DEFAULT_PII          | Always forced FALSE here regardless of env  |
| SENTRY_RELEASE                   | optional release tag                        |

PII scrubbing is forced ON via `send_default_pii=False` AND an explicit
`before_send` hook that drops common PII fields out of the event body.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


_PII_KEYS = {
    "email", "password", "password_hash", "magic_link_token",
    "reset_password_token", "code_verifier", "Authorization",
    "cookie", "set-cookie", "first_name", "last_name", "full_name",
}


def _scrub(event: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively drop common PII keys before the event leaves the
    process. Conservative: matches dict keys by lowercase substring."""
    def _walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: ("[scrubbed]" if any(p in k.lower() for p in _PII_KEYS) else _walk(v))
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [_walk(x) for x in obj]
        return obj
    return _walk(event)


def init_sentry() -> str:
    """Returns `"live"` when Sentry initialised, `"noop"` otherwise."""
    dsn = (os.environ.get("SENTRY_DSN") or "").strip()
    if not dsn:
        log.info("sentry: noop (SENTRY_DSN unset)")
        return "noop"

    try:
        import sentry_sdk  # noqa: F401
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        def _before_send(event: Dict[str, Any], _hint: Any) -> Optional[Dict[str, Any]]:
            try:
                return _scrub(event)
            except Exception:  # noqa: BLE001
                # If scrubbing fails we DROP the event rather than ship
                # un-scrubbed data.
                return None

        sentry_sdk.init(
            dsn=dsn,
            environment=os.environ.get("SENTRY_ENVIRONMENT", "development").strip(),
            release=(os.environ.get("SENTRY_RELEASE") or None),
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0") or 0.0),
            profiles_sample_rate=float(os.environ.get("SENTRY_PROFILES_SAMPLE_RATE", "0.0") or 0.0),
            send_default_pii=False,
            integrations=[FastApiIntegration(), StarletteIntegration()],
            before_send=_before_send,
        )
        log.info("sentry: live env=%s", os.environ.get("SENTRY_ENVIRONMENT", "development"))
        return "live"
    except Exception as e:  # noqa: BLE001
        log.warning("sentry: init_failed err=%s — continuing in noop mode", str(e)[:200])
        return "noop"
