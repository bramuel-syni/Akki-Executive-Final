"""Health · ClamAV daemon status probe.

Hardening Step 1 (2026-05-25). Lightweight unauthenticated endpoint
at ``GET /api/healthz/clamav`` that lets ops + load balancers verify
the clamd daemon's reachability + recent scan distribution WITHOUT
shell access.

Same stance as ``/api/healthz/shield`` (H2.5 follow-up Part B): this
is a **status report**, not a gate. HTTP 200 in every branch —
including ``unreachable`` and ``unknown``. Probes that want a
strict gate should inspect ``clamd_daemon`` in the body.

Response shape::

    {
      "clamd_daemon": "alive" | "unreachable" | "unknown",
      "clamd_ping_response_ms": <number or null>,
      "last_scan_at_utc": "<iso 8601>" | null,
      "scans_last_24h": {
        "ok": <n>, "infected": <n>, "bypassed": <n>, "error": <n>
      },
      "checked_at_utc": "<iso 8601>",
      "preflight_size_check_active": true,
      "debug": { "exception_class": "<ClassName>" }  // only on "unknown"
    }

Implementation contract: this file MUST NOT modify
``services/clamav_service.py``. It only reads constants
(``CLAMAV_HOST``, ``CLAMAV_PORT``, ``CLAMAV_TIMEOUT_SECONDS``,
``CLAMAV_MAX_FILE_SIZE_MB``, ``ClamAVUnreachable``,
``UPLOAD_SCAN_LOG_COLLECTION``) and calls the same lazy-import
pattern (``import clamd`` inside the handler) used by
``_scan_blocking``. The clamd ping is conducted via a fresh
``ClamdNetworkSocket(timeout=3)`` so we never block on the
production 30s timeout in a health probe.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import APIRouter

from core import db
from services.clamav_service import (
    CLAMAV_HOST,
    CLAMAV_PORT,
    UPLOAD_SCAN_LOG_COLLECTION,
    ClamAVUnreachable,
)

router = APIRouter(prefix="/api/healthz", tags=["healthz"])

# Health-probe-specific timeout. Shorter than the upload-path
# ``CLAMAV_TIMEOUT_SECONDS`` (30s) so a stuck clamd can't hang
# the readiness probe.
_PROBE_TIMEOUT_SECONDS = 3


def _ping_clamd() -> Dict[str, Any]:
    """Issue a clamd PING. Returns one of:
      * ``{"daemon": "alive", "ms": <int>}``
      * ``{"daemon": "unreachable", "ms": None}``
      * ``{"daemon": "unknown", "ms": None, "exception_class": "<name>"}``

    Never raises. Probe failures classify rather than 500."""
    started = time.time()
    try:
        # Lazy import to match `services.clamav_service._scan_blocking`'s
        # tolerance pattern — the python package may be absent in dev
        # containers that haven't installed it. That's treated as
        # `unreachable` (consistent with the upload path).
        import clamd
    except ImportError:
        return {"daemon": "unreachable", "ms": None}

    # The `clamd` package raises its OWN `clamd.ConnectionError` class
    # which does NOT inherit from Python's built-in `ConnectionError`.
    # We catch both here so a refused / unreachable socket maps to the
    # "unreachable" bucket rather than the catch-all "unknown" bucket.
    _ClamdConnError = getattr(clamd, "ConnectionError", None)
    _ClamdError = getattr(clamd, "ClamdError", None)
    unreachable_exc_types: tuple = (
        ConnectionError, ConnectionRefusedError, OSError, TimeoutError,
    )
    if _ClamdConnError is not None and _ClamdConnError is not ConnectionError:
        unreachable_exc_types = unreachable_exc_types + (_ClamdConnError,)
    if _ClamdError is not None:
        # ClamdError covers protocol-level errors too (ResponseError,
        # BufferTooLongError) — those still mean the upload-path
        # couldn't successfully scan, so we classify as unreachable.
        unreachable_exc_types = unreachable_exc_types + (_ClamdError,)

    try:
        cd = clamd.ClamdNetworkSocket(
            host=CLAMAV_HOST,
            port=CLAMAV_PORT,
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
        cd.ping()
    except ClamAVUnreachable:
        return {"daemon": "unreachable", "ms": None}
    except unreachable_exc_types:
        return {"daemon": "unreachable", "ms": None}
    except Exception as exc:  # noqa: BLE001
        # Anything else — surface the class for operator triage but
        # still classify as `unknown` (not `unreachable`) so an
        # operator knows it's not a plain network issue.
        return {
            "daemon": "unknown",
            "ms": None,
            "exception_class": exc.__class__.__name__,
        }
    ms = int((time.time() - started) * 1000)
    return {"daemon": "alive", "ms": ms}


async def _scan_histogram_24h() -> Dict[str, Any]:
    """Compute the last-24h scan-result histogram + most-recent scan
    timestamp from ``upload_scan_log``. Returns null/zero on empty.

    The ``scan_result`` field on the collection carries one of:
    ``clean`` · ``infected`` · ``bypassed`` · ``unreachable`` ·
    ``too_large``. The endpoint reports four buckets:
      * ``ok``        = ``clean``
      * ``infected``  = ``infected``
      * ``bypassed``  = ``bypassed``
      * ``error``     = ``unreachable`` + ``too_large`` (anything else
                        is also folded here)
    """
    coll = db[UPLOAD_SCAN_LOG_COLLECTION]
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=24)).isoformat()
    counts = {"ok": 0, "infected": 0, "bypassed": 0, "error": 0}
    # 24h histogram.
    async for row in coll.find(
        {"scanned_at": {"$gte": cutoff}}, {"_id": 0, "scan_result": 1},
    ):
        result = (row.get("scan_result") or "").lower()
        if result == "clean":
            counts["ok"] += 1
        elif result == "infected":
            counts["infected"] += 1
        elif result == "bypassed":
            counts["bypassed"] += 1
        else:
            counts["error"] += 1
    # Most-recent scan, regardless of age.
    last_row = await coll.find_one(
        {}, {"_id": 0, "scanned_at": 1},
        sort=[("scanned_at", -1)],
    )
    last_scan = (last_row or {}).get("scanned_at")
    return {"last_scan_at_utc": last_scan, "scans_last_24h": counts}


@router.get("/clamav")
async def healthz_clamav():
    """Read-only ClamAV daemon health-status snapshot. No auth —
    designed for Kubernetes liveness/readiness probes + ops
    dashboards.

    ALWAYS returns HTTP 200. Probes that want a strict gate should
    branch on ``clamd_daemon`` in the body (``alive`` is the only
    healthy state)."""
    ping = _ping_clamd()
    hist = await _scan_histogram_24h()
    body: Dict[str, Any] = {
        "clamd_daemon": ping["daemon"],
        "clamd_ping_response_ms": ping["ms"],
        "last_scan_at_utc": hist["last_scan_at_utc"],
        "scans_last_24h": hist["scans_last_24h"],
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        # The preflight size check is a hard-coded service constant
        # (``CLAMAV_MAX_FILE_SIZE_BYTES``). It is ALWAYS active in
        # the upload path — no env flag can disable it.
        "preflight_size_check_active": True,
    }
    if ping["daemon"] == "unknown" and "exception_class" in ping:
        body["debug"] = {"exception_class": ping["exception_class"]}
    return body
