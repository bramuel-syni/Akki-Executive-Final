"""Real virus scanning via clamd (ClamAV daemon).

Phase 10 / Item A — production stance is REQUIRED. Phase E.A
hardening (2026-05-21):
  * `CLAMAV_MAX_FILE_SIZE_MB` (default 25 MB) — pre-reject before
    we open the clamd socket. The 413 fires BEFORE any network I/O.
  * `upload_scan_log` Mongo collection — one row per scan attempt
    (clean / infected / error). Forensic surface.
  * `ALLOW_UNSAFE_UPLOADS` is now scoped: honoured ONLY when
    `AKKI_ENV != "production"`. Boot guard `assert_safe_boot()`
    refuses startup if prod + bypass=true; the prod stance is
    "always scan, never silently skip".
  * `CLAMAV_HOST` default flipped from `127.0.0.1` → `clamd`
    (sidecar-DNS convention; docker-compose service name).

Wire: ``INSTREAM`` over a TCP socket — never shell-out to
``clamscan`` (slow, fork-per-request, structured result lost).
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException

logger = logging.getLogger("akki.clamav")

# ── Env-driven config (read at import; `assert_safe_boot` re-reads).
CLAMAV_HOST = os.environ.get("CLAMAV_HOST", "clamd")
CLAMAV_PORT = int(os.environ.get("CLAMAV_PORT", "3310"))
CLAMAV_TIMEOUT_SECONDS = float(os.environ.get("CLAMAV_TIMEOUT_SECONDS", "30"))
CLAMAV_MAX_FILE_SIZE_MB = int(os.environ.get("CLAMAV_MAX_FILE_SIZE_MB", "25"))
CLAMAV_MAX_FILE_SIZE_BYTES = CLAMAV_MAX_FILE_SIZE_MB * 1024 * 1024
ALLOW_UNSAFE_UPLOADS = os.environ.get("ALLOW_UNSAFE_UPLOADS", "").lower() in (
    "1", "true", "yes",
)
AKKI_ENV = (os.environ.get("AKKI_ENV") or "").strip().lower()

UPLOAD_SCAN_LOG_COLLECTION = "upload_scan_log"


class ClamAVUnreachable(RuntimeError):
    """Raised when clamd is not reachable. The router must convert this
    to a 503, not a 200 with a fake clean result."""


class FileTooLarge(HTTPException):
    """Raised BEFORE any clamd I/O when the payload exceeds
    `CLAMAV_MAX_FILE_SIZE_BYTES`. Subclass of HTTPException so FastAPI
    converts it to a 413 response automatically with a descriptive
    JSON body — every upload entry point inherits the same shape."""

    def __init__(self, size_bytes: int, *, max_mb: int = CLAMAV_MAX_FILE_SIZE_MB):
        super().__init__(
            status_code=413,
            detail={
                "error": "file_too_large",
                "reason": (
                    f"File ({size_bytes} bytes) exceeds the upload size "
                    f"limit of {max_mb} MB."
                ),
                "max_size_mb": max_mb,
                "received_bytes": size_bytes,
            },
        )


@dataclass
class ScanResult:
    clean: bool
    signature: Optional[str]
    scan_ms: int
    bypassed: bool = False  # True iff the dev escape hatch returned synthetic clean


# ── Warn-loop state for ALLOW_UNSAFE_UPLOADS (dev only).
_LAST_UNSAFE_WARN_AT = 0.0
_UNSAFE_WARN_LOCK = threading.Lock()


def _warn_unsafe_mode() -> None:
    """Every 60s, print a hard-to-miss warning to stderr. Dev-only."""
    global _LAST_UNSAFE_WARN_AT
    with _UNSAFE_WARN_LOCK:
        nowt = time.time()
        if nowt - _LAST_UNSAFE_WARN_AT < 60:
            return
        _LAST_UNSAFE_WARN_AT = nowt
    sys.stderr.write(
        "\n[ALLOW_UNSAFE_UPLOADS=true] Virus scanning is DISABLED. "
        "Honoured only because AKKI_ENV != 'production'. "
        "This must never appear in a production environment.\n"
    )
    sys.stderr.flush()


def assert_safe_boot() -> str:
    """Boot-time invariant check. Called from server.py startup.

    Refuses the process startup if `ALLOW_UNSAFE_UPLOADS=true` AND
    `AKKI_ENV=production` simultaneously. Returns the active mode
    string so the caller can log it: `"enforce"` (prod or any env
    with bypass off) or `"dev-bypass"` (non-prod with bypass on).
    """
    akki_env = (os.environ.get("AKKI_ENV") or "").strip().lower()
    unsafe = os.environ.get("ALLOW_UNSAFE_UPLOADS", "").lower() in (
        "1", "true", "yes",
    )
    if akki_env == "production" and unsafe:
        raise RuntimeError(
            "AKKI boot guard: ALLOW_UNSAFE_UPLOADS=true is incompatible "
            "with AKKI_ENV=production. Refusing to start — virus "
            "scanning is mandatory in prod. Unset ALLOW_UNSAFE_UPLOADS "
            "(or remove it from your prod env) and restart."
        )
    return "dev-bypass" if (unsafe and akki_env != "production") else "enforce"


def preflight_size_check(size_bytes: int) -> None:
    """Public helper for callers that want to 413 BEFORE buffering the
    body. `scan()` calls this internally too — every code path lands
    on the same 413 body shape."""
    if size_bytes > CLAMAV_MAX_FILE_SIZE_BYTES:
        raise FileTooLarge(size_bytes)


def _scan_blocking(file_bytes: bytes, filename: Optional[str]) -> ScanResult:
    """Synchronous clamd INSTREAM call. Runs in a thread executor so
    the event loop isn't blocked."""
    started = time.time()

    if ALLOW_UNSAFE_UPLOADS and AKKI_ENV != "production":
        _warn_unsafe_mode()
        return ScanResult(clean=True, signature=None, bypassed=True,
                          scan_ms=int((time.time() - started) * 1000))

    try:
        import clamd  # lazy so tests can monkeypatch
    except ImportError as e:  # pragma: no cover
        raise ClamAVUnreachable(f"clamd python package missing: {e}") from e

    try:
        cd = clamd.ClamdNetworkSocket(
            host=CLAMAV_HOST, port=CLAMAV_PORT,
            timeout=CLAMAV_TIMEOUT_SECONDS,
        )
        cd.ping()
    except Exception as e:  # noqa: BLE001
        logger.warning("clamd unreachable at %s:%s: %s", CLAMAV_HOST, CLAMAV_PORT, e)
        raise ClamAVUnreachable(str(e)) from e

    try:
        stream = io.BytesIO(file_bytes)
        result = cd.instream(stream)
    except Exception as e:  # noqa: BLE001
        logger.warning("clamd instream failed (%s): %s", filename, e)
        raise ClamAVUnreachable(f"instream failed: {e}") from e

    stream_result = (result or {}).get("stream") or ("ERROR", None)
    status, signature = stream_result
    scan_ms = int((time.time() - started) * 1000)

    if status == "OK":
        return ScanResult(clean=True, signature=None, scan_ms=scan_ms)
    if status == "FOUND":
        logger.info("clamd FOUND %s in %s", signature, filename)
        return ScanResult(clean=False, signature=signature, scan_ms=scan_ms)
    raise ClamAVUnreachable(f"clamd error status={status!r} sig={signature!r}")


async def _log_scan(
    *, file_id: Optional[str], user_id: Optional[str],
    filename: Optional[str], size_bytes: int,
    scan_result: str, signature: Optional[str], duration_ms: int,
) -> None:
    """Best-effort write to `upload_scan_log`. Never raises — a logging
    failure must not block a clean upload from proceeding."""
    try:
        from core import db as _db
        await _db[UPLOAD_SCAN_LOG_COLLECTION].insert_one({
            "file_id": file_id or f"unscanned-{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "filename": filename,
            "size_bytes": size_bytes,
            "scan_result": scan_result,
            "signature": signature,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": duration_ms,
        })
    except Exception as exc:  # noqa: BLE001
        logger.warning("upload_scan_log write failed (non-fatal): %s",
                       exc.__class__.__name__)


async def scan(
    file_bytes: bytes,
    filename: Optional[str] = None,
    *,
    file_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> ScanResult:
    """Async scan + audit-log entry. The canonical upload-scan helper.

    • Size > `CLAMAV_MAX_FILE_SIZE_BYTES` → raise `FileTooLarge` (413)
      BEFORE any clamd contact. Logs `scan_result="too_large"`.
    • Otherwise runs `_scan_blocking` in an executor and writes a row
      to `upload_scan_log` regardless of outcome.
    • `ClamAVUnreachable` bubbles to the caller; the audit row is
      written with `scan_result="unreachable"` before re-raising.
    • Clean → "clean". Infected → "infected" + signature.

    Backward compat: legacy callers that pass only `(file_bytes,
    filename)` still work — `file_id` is generated, `user_id` is None.
    """
    size = len(file_bytes)
    if size > CLAMAV_MAX_FILE_SIZE_BYTES:
        await _log_scan(
            file_id=file_id, user_id=user_id, filename=filename,
            size_bytes=size, scan_result="too_large",
            signature=None, duration_ms=0,
        )
        raise FileTooLarge(size)

    started = time.time()
    try:
        scan_result = await asyncio.get_event_loop().run_in_executor(
            None, _scan_blocking, file_bytes, filename,
        )
    except ClamAVUnreachable as exc:
        await _log_scan(
            file_id=file_id, user_id=user_id, filename=filename,
            size_bytes=size, scan_result="unreachable",
            signature=str(exc)[:200],
            duration_ms=int((time.time() - started) * 1000),
        )
        raise

    if scan_result.bypassed:
        # Dev-bypass branch — clamd wasn't actually consulted.
        await _log_scan(
            file_id=file_id, user_id=user_id, filename=filename,
            size_bytes=size, scan_result="bypassed",
            signature=None, duration_ms=scan_result.scan_ms,
        )
        return scan_result

    await _log_scan(
        file_id=file_id, user_id=user_id, filename=filename,
        size_bytes=size,
        scan_result="clean" if scan_result.clean else "infected",
        signature=scan_result.signature,
        duration_ms=scan_result.scan_ms,
    )
    return scan_result


def healthcheck() -> Dict[str, Any]:
    """Small diagnostic for the /admin/health surface. Never raises."""
    if ALLOW_UNSAFE_UPLOADS and AKKI_ENV != "production":
        return {"ok": False, "mode": "dev-bypass",
                "host": CLAMAV_HOST, "port": CLAMAV_PORT}
    try:
        import clamd
        cd = clamd.ClamdNetworkSocket(
            host=CLAMAV_HOST, port=CLAMAV_PORT, timeout=3,
        )
        version = cd.version()
        return {"ok": True, "mode": "enforce", "version": version,
                "host": CLAMAV_HOST, "port": CLAMAV_PORT,
                "max_file_size_mb": CLAMAV_MAX_FILE_SIZE_MB}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "mode": "unreachable", "error": str(e),
                "host": CLAMAV_HOST, "port": CLAMAV_PORT}
