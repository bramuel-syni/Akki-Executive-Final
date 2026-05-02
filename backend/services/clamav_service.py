"""Real virus scanning via clamd (ClamAV daemon).

Phase 10 / Item A.  Replaces ``documents_service.virus_scan_stub``.

Production stance: the scanner is REQUIRED. If clamd is unreachable
we block the upload (503). We do NOT fall through to a stub. A
dev-only escape hatch exists via ``ALLOW_UNSAFE_UPLOADS=true`` (off by
default); when set, we skip scanning AND print a stderr warning every
60 seconds so it is impossible to forget.

Wire: ``INSTREAM`` over a TCP socket — never shell-out to ``clamscan``
(slow, fork-per-request, and we lose the structured result).
"""
from __future__ import annotations

import io
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("akki.clamav")

CLAMAV_HOST = os.environ.get("CLAMAV_HOST", "127.0.0.1")
CLAMAV_PORT = int(os.environ.get("CLAMAV_PORT", "3310"))
CLAMAV_TIMEOUT_SECONDS = float(os.environ.get("CLAMAV_TIMEOUT_SECONDS", "30"))
ALLOW_UNSAFE_UPLOADS = os.environ.get("ALLOW_UNSAFE_UPLOADS", "").lower() in ("1", "true", "yes")


class ClamAVUnreachable(RuntimeError):
    """Raised when clamd is not reachable. The router must convert this
    to a 503, not a 200 with a fake clean result."""


@dataclass
class ScanResult:
    clean: bool
    signature: Optional[str]
    scan_ms: int


# Warn-loop state for ALLOW_UNSAFE_UPLOADS.
_LAST_UNSAFE_WARN_AT = 0.0
_UNSAFE_WARN_LOCK = threading.Lock()


def _warn_unsafe_mode() -> None:
    """Every 60 s, print a hard-to-miss warning to stderr. Dev-only."""
    global _LAST_UNSAFE_WARN_AT
    with _UNSAFE_WARN_LOCK:
        now = time.time()
        if now - _LAST_UNSAFE_WARN_AT < 60:
            return
        _LAST_UNSAFE_WARN_AT = now
    sys.stderr.write(
        "\n[ALLOW_UNSAFE_UPLOADS=true] Virus scanning is DISABLED. "
        "This must never appear in a production environment.\n"
    )
    sys.stderr.flush()


def scan(file_bytes: bytes, filename: Optional[str] = None) -> ScanResult:
    """Scan a buffer via clamd INSTREAM.

    Returns a :class:`ScanResult`. Raises :class:`ClamAVUnreachable`
    if the daemon can't be reached or refuses the stream. The caller
    (HTTP router) is responsible for translating that to a 503 and
    writing the audit row.
    """
    started = time.time()
    if ALLOW_UNSAFE_UPLOADS:
        _warn_unsafe_mode()
        return ScanResult(clean=True, signature=None, scan_ms=int((time.time() - started) * 1000))

    try:
        import clamd  # lazy so tests can monkeypatch
    except ImportError as e:  # pragma: no cover
        raise ClamAVUnreachable(f"clamd python package missing: {e}") from e

    try:
        cd = clamd.ClamdNetworkSocket(host=CLAMAV_HOST, port=CLAMAV_PORT, timeout=CLAMAV_TIMEOUT_SECONDS)
        cd.ping()
    except Exception as e:  # noqa: BLE001
        logger.warning("clamd unreachable at %s:%s: %s", CLAMAV_HOST, CLAMAV_PORT, e)
        raise ClamAVUnreachable(str(e)) from e

    try:
        # INSTREAM — buffered. `instream` accepts a file-like.
        stream = io.BytesIO(file_bytes)
        result = cd.instream(stream)
    except Exception as e:  # noqa: BLE001
        logger.warning("clamd instream failed (%s): %s", filename, e)
        raise ClamAVUnreachable(f"instream failed: {e}") from e

    # clamd returns {'stream': ('OK', None)} or {'stream': ('FOUND', 'Eicar-Signature')}
    stream_result = (result or {}).get("stream") or ("ERROR", None)
    status, signature = stream_result
    scan_ms = int((time.time() - started) * 1000)

    if status == "OK":
        return ScanResult(clean=True, signature=None, scan_ms=scan_ms)
    if status == "FOUND":
        logger.info("clamd FOUND %s in %s", signature, filename)
        return ScanResult(clean=False, signature=signature, scan_ms=scan_ms)
    # ERROR or anything else — treat as unreachable, don't pretend-clean.
    raise ClamAVUnreachable(f"clamd error status={status!r} sig={signature!r}")


def healthcheck() -> dict:
    """Small diagnostic for the /admin/health surface. Never raises."""
    if ALLOW_UNSAFE_UPLOADS:
        return {"ok": False, "mode": "unsafe", "host": CLAMAV_HOST, "port": CLAMAV_PORT}
    try:
        import clamd
        cd = clamd.ClamdNetworkSocket(host=CLAMAV_HOST, port=CLAMAV_PORT, timeout=3)
        version = cd.version()
        return {"ok": True, "mode": "clamd", "version": version, "host": CLAMAV_HOST, "port": CLAMAV_PORT}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "mode": "unreachable", "error": str(e), "host": CLAMAV_HOST, "port": CLAMAV_PORT}
