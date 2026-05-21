"""Phase E.A — ClamAV gap-fill integration tests.

Replaces / supplements `test_patch_22_clamav.py` (kept for historical
naming continuity). Covers the four acceptance scenarios from the
Phase A dispatch:

  1. EICAR string upload → ScanResult(clean=False, signature="Eicar-Test-Signature")
     + `upload_scan_log` row with scan_result="infected".
  2. Clean payload upload → ScanResult(clean=True) + audit row with scan_result="clean".
  3. Oversize file (> 25 MB) → `FileTooLarge` (HTTP 413) BEFORE clamd contact
     + audit row with scan_result="too_large".
  4. Scanner unreachable → `ClamAVUnreachable` raised
     + audit row with scan_result="unreachable".

Plus a boot-guard test for `assert_safe_boot` covering option (c)
(refuse prod + ALLOW_UNSAFE_UPLOADS=true).

We monkeypatch `clamav_service._scan_blocking` (the synchronous heart
that lives behind the async `scan()` wrapper) rather than the clamd
module itself — clamd may already be imported elsewhere in the
process so a `sys.modules` patch wouldn't take.
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient


EICAR = (
    b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
)


@pytest_asyncio.fixture
async def db_conn():
    mclient = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mclient[os.environ["DB_NAME"]]
    yield db
    mclient.close()


def _make_fake_blocking(*, mode: str):
    from services import clamav_service

    def fake(file_bytes, filename):
        if mode == "unreachable":
            raise clamav_service.ClamAVUnreachable("simulated clamd down")
        if mode == "eicar":
            return clamav_service.ScanResult(
                clean=False, signature="Eicar-Test-Signature", scan_ms=3,
            )
        return clamav_service.ScanResult(clean=True, signature=None, scan_ms=3)
    return fake


@pytest.mark.asyncio
async def test_chunk_phase_e_a_eicar_returns_infected_and_logs(db_conn, monkeypatch):
    from services import clamav_service

    file_id = "test-c19a-eicar"
    await db_conn[clamav_service.UPLOAD_SCAN_LOG_COLLECTION].delete_many({"file_id": file_id})

    monkeypatch.setattr(clamav_service, "_scan_blocking", _make_fake_blocking(mode="eicar"))
    result = await clamav_service.scan(EICAR, "eicar.txt", file_id=file_id, user_id="usr-test")

    assert result.clean is False
    assert result.signature == "Eicar-Test-Signature"

    row = await db_conn[clamav_service.UPLOAD_SCAN_LOG_COLLECTION].find_one({"file_id": file_id}, {"_id": 0})
    assert row is not None
    assert row["scan_result"] == "infected"
    assert row["signature"] == "Eicar-Test-Signature"
    assert row["user_id"] == "usr-test"
    assert row["size_bytes"] == len(EICAR)

    await db_conn[clamav_service.UPLOAD_SCAN_LOG_COLLECTION].delete_many({"file_id": file_id})


@pytest.mark.asyncio
async def test_chunk_phase_e_a_clean_payload_logs_clean(db_conn, monkeypatch):
    from services import clamav_service

    file_id = "test-c19a-clean"
    payload = b"%PDF-1.4\nfake clean pdf payload for testing\n%%EOF\n"
    await db_conn[clamav_service.UPLOAD_SCAN_LOG_COLLECTION].delete_many({"file_id": file_id})

    monkeypatch.setattr(clamav_service, "_scan_blocking", _make_fake_blocking(mode="clean"))
    result = await clamav_service.scan(payload, "report.pdf", file_id=file_id, user_id="usr-test")

    assert result.clean is True
    assert result.signature is None
    row = await db_conn[clamav_service.UPLOAD_SCAN_LOG_COLLECTION].find_one({"file_id": file_id}, {"_id": 0})
    assert row is not None
    assert row["scan_result"] == "clean"
    assert row["filename"] == "report.pdf"
    assert row["size_bytes"] == len(payload)

    await db_conn[clamav_service.UPLOAD_SCAN_LOG_COLLECTION].delete_many({"file_id": file_id})


@pytest.mark.asyncio
async def test_chunk_phase_e_a_oversize_raises_413_before_clamd(db_conn, monkeypatch):
    from services import clamav_service

    file_id = "test-c19a-oversize"
    payload = b"\x00" * (clamav_service.CLAMAV_MAX_FILE_SIZE_BYTES + 1)
    await db_conn[clamav_service.UPLOAD_SCAN_LOG_COLLECTION].delete_many({"file_id": file_id})

    def boom(*a, **kw):
        raise AssertionError("clamd was contacted — 413 must fire first")
    monkeypatch.setattr(clamav_service, "_scan_blocking", boom)

    with pytest.raises(clamav_service.FileTooLarge) as exc:
        await clamav_service.scan(payload, "huge.bin", file_id=file_id, user_id="usr-test")

    assert exc.value.status_code == 413
    assert exc.value.detail["error"] == "file_too_large"
    assert exc.value.detail["received_bytes"] == len(payload)
    assert exc.value.detail["max_size_mb"] == clamav_service.CLAMAV_MAX_FILE_SIZE_MB

    row = await db_conn[clamav_service.UPLOAD_SCAN_LOG_COLLECTION].find_one({"file_id": file_id}, {"_id": 0})
    assert row is not None
    assert row["scan_result"] == "too_large"
    assert row["duration_ms"] == 0

    await db_conn[clamav_service.UPLOAD_SCAN_LOG_COLLECTION].delete_many({"file_id": file_id})


@pytest.mark.asyncio
async def test_chunk_phase_e_a_unreachable_logs_and_raises(db_conn, monkeypatch):
    from services import clamav_service

    file_id = "test-c19a-unreachable"
    payload = b"some bytes"
    await db_conn[clamav_service.UPLOAD_SCAN_LOG_COLLECTION].delete_many({"file_id": file_id})

    monkeypatch.setattr(clamav_service, "ALLOW_UNSAFE_UPLOADS", False)
    monkeypatch.setattr(clamav_service, "AKKI_ENV", "")
    monkeypatch.setattr(clamav_service, "_scan_blocking", _make_fake_blocking(mode="unreachable"))

    with pytest.raises(clamav_service.ClamAVUnreachable):
        await clamav_service.scan(payload, "x.bin", file_id=file_id, user_id="usr-test")

    row = await db_conn[clamav_service.UPLOAD_SCAN_LOG_COLLECTION].find_one({"file_id": file_id}, {"_id": 0})
    assert row is not None
    assert row["scan_result"] == "unreachable"
    assert "simulated clamd down" in (row["signature"] or "")

    await db_conn[clamav_service.UPLOAD_SCAN_LOG_COLLECTION].delete_many({"file_id": file_id})


def test_chunk_phase_e_a_boot_guard_refuses_prod_with_bypass(monkeypatch):
    from services import clamav_service
    monkeypatch.setenv("AKKI_ENV", "production")
    monkeypatch.setenv("ALLOW_UNSAFE_UPLOADS", "true")
    with pytest.raises(RuntimeError) as exc:
        clamav_service.assert_safe_boot()
    assert "incompatible" in str(exc.value).lower()
    assert "production" in str(exc.value).lower()


def test_chunk_phase_e_a_boot_guard_allows_dev_with_bypass(monkeypatch):
    from services import clamav_service
    monkeypatch.setenv("AKKI_ENV", "development")
    monkeypatch.setenv("ALLOW_UNSAFE_UPLOADS", "true")
    assert clamav_service.assert_safe_boot() == "dev-bypass"


def test_chunk_phase_e_a_boot_guard_default_is_enforce(monkeypatch):
    from services import clamav_service
    monkeypatch.delenv("AKKI_ENV", raising=False)
    monkeypatch.delenv("ALLOW_UNSAFE_UPLOADS", raising=False)
    assert clamav_service.assert_safe_boot() == "enforce"
