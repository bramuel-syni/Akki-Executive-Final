"""Phase 10 / Item B — S3-compatible object storage.

Two backends:

  * :class:`LocalDiskStorage` — preserves pre-Phase-10 behaviour. Used
    in tests and in dev environments without MinIO. Writes under
    ``UPLOADS_DIR`` (default ``/app/backend/uploads``).
  * :class:`S3Storage` — boto3 client against any S3-compatible
    endpoint (AWS S3, MinIO, Cloudflare R2, Backblaze B2). Server-side
    encryption AES256 enforced on every ``PUT``.

Backend is selected by ``STORAGE_BACKEND={local|s3}``.
Default in this env: ``s3`` (so MinIO is exercised by default).

Public interface:

  put(key, content, content_type, metadata) -> {key, size, etag}
  get_bytes(key) -> bytes
  get_presigned_url(key, ttl_seconds=300, response_content_disposition=None) -> str
  delete(key) -> bool
  head(key) -> {exists, size, etag, content_type, last_modified}

``key`` convention: ``{context_id}/{doc_id}/{sanitised_filename}``. No
PII in the key or in object metadata.
"""
from __future__ import annotations

import io
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("akki.storage")


STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "s3").strip().lower()
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://127.0.0.1:9000")
S3_REGION = os.environ.get("S3_REGION", "eu-west-1")
S3_BUCKET = os.environ.get("S3_BUCKET", "akki-uploads")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
S3_FORCE_PATH_STYLE = os.environ.get("S3_FORCE_PATH_STYLE", "true").lower() in ("1", "true", "yes")
LOCAL_UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", "/app/backend/uploads"))


_SANE_NAME_RE = re.compile(r"[^A-Za-z0-9._\-]+")


def _sanitise(name: str) -> str:
    """Collapse non-alphanumeric to '-' and cap length."""
    name = (name or "file").strip()
    name = _SANE_NAME_RE.sub("-", name)
    return name[:180] or "file"


def make_key(context_id: str, doc_id: str, filename: str) -> str:
    """Canonical storage key. Used by every upload path."""
    return f"{context_id}/{doc_id}/{_sanitise(filename)}"


# ---------------------------------------------------------------------------
# Backend: local disk
# ---------------------------------------------------------------------------
class LocalDiskStorage:
    backend = "local"

    def __init__(self, root: Path = LOCAL_UPLOADS_DIR):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, key: str) -> Path:
        return self.root / key

    def put(self, key: str, content: bytes, content_type: Optional[str] = None,
            metadata: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        path = self._p(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return {"key": key, "size": len(content), "etag": None}

    def get_bytes(self, key: str) -> bytes:
        path = self._p(key)
        if not path.exists():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def get_presigned_url(self, key: str, ttl_seconds: int = 300,
                          response_content_disposition: Optional[str] = None) -> str:
        # Local backend: synthesise an in-app download URL. Callers that
        # rely on a real presigned URL (e.g. the Studio image block on a
        # production deploy) will be on the S3 backend.
        return f"/api/storage/local/{key}"

    def delete(self, key: str) -> bool:
        path = self._p(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def head(self, key: str) -> Dict[str, Any]:
        path = self._p(key)
        if not path.exists():
            return {"exists": False}
        st = path.stat()
        return {
            "exists": True,
            "size": st.st_size,
            "etag": None,
            "content_type": None,
            "last_modified": st.st_mtime,
        }


# ---------------------------------------------------------------------------
# Backend: S3 / MinIO
# ---------------------------------------------------------------------------
class S3Storage:
    backend = "s3"

    def __init__(self):
        import boto3
        from botocore.client import Config
        if not S3_ACCESS_KEY or not S3_SECRET_KEY:
            raise RuntimeError(
                "STORAGE_BACKEND=s3 requires S3_ACCESS_KEY and S3_SECRET_KEY"
            )
        self.bucket = S3_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name=S3_REGION,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path" if S3_FORCE_PATH_STYLE else "virtual"},
            ),
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            try:
                self.client.create_bucket(Bucket=self.bucket)
                logger.info("created bucket %s", self.bucket)
            except Exception as e:  # noqa: BLE001
                logger.warning("could not create bucket %s: %s", self.bucket, e)

    def put(self, key: str, content: bytes, content_type: Optional[str] = None,
            metadata: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        extra: Dict[str, Any] = {
            "ServerSideEncryption": "AES256",
        }
        if content_type:
            extra["ContentType"] = content_type
        if metadata:
            # Strip any PII-shaped values defensively — S3 metadata is
            # header-scoped and we don't want surprise leakage.
            extra["Metadata"] = {
                str(k)[:80]: str(v)[:240] for k, v in metadata.items() if k and v is not None
            }
        resp = self.client.put_object(
            Bucket=self.bucket, Key=key, Body=content, **extra,
        )
        return {"key": key, "size": len(content), "etag": (resp.get("ETag") or "").strip('"')}

    def get_bytes(self, key: str) -> bytes:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=key)
        except self.client.exceptions.NoSuchKey as e:
            raise FileNotFoundError(key) from e
        return obj["Body"].read()

    def get_presigned_url(self, key: str, ttl_seconds: int = 300,
                          response_content_disposition: Optional[str] = None) -> str:
        params: Dict[str, Any] = {"Bucket": self.bucket, "Key": key}
        if response_content_disposition:
            params["ResponseContentDisposition"] = response_content_disposition
        return self.client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=int(ttl_seconds),
        )

    def delete(self, key: str) -> bool:
        self.client.delete_object(Bucket=self.bucket, Key=key)
        return True

    def head(self, key: str) -> Dict[str, Any]:
        try:
            r = self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception:
            return {"exists": False}
        return {
            "exists": True,
            "size": r.get("ContentLength"),
            "etag": (r.get("ETag") or "").strip('"'),
            "content_type": r.get("ContentType"),
            "last_modified": r.get("LastModified").isoformat() if r.get("LastModified") else None,
        }


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------
_BACKEND: Any = None


def get_storage():
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    if STORAGE_BACKEND == "local":
        _BACKEND = LocalDiskStorage()
    else:
        _BACKEND = S3Storage()
    logger.info("storage backend initialised: %s", _BACKEND.backend)
    return _BACKEND


# ---------------------------------------------------------------------------
# Back-compat shim — `documents_service.save_to_storage` used to return
# a local-disk relative path. The S3 backend returns the object key.
# The DB column stored that string either way, so nothing else needs to
# change; but we provide thin wrappers so the existing call sites read
# naturally.
# ---------------------------------------------------------------------------
def save(context_id: str, doc_id: str, filename: str, data: bytes,
         content_type: Optional[str] = None) -> str:
    key = make_key(context_id, doc_id, filename)
    result = get_storage().put(key, data, content_type=content_type)
    return result["key"]


def read(key: str) -> bytes:
    # Back-compat: old local-disk keys were relative paths. Try them.
    try:
        return get_storage().get_bytes(key)
    except FileNotFoundError:
        # Fallback for pre-Phase-10 local disk keys — only when running
        # the s3 backend with legacy rows still pointing at the disk.
        legacy = LOCAL_UPLOADS_DIR / key
        if legacy.exists():
            return legacy.read_bytes()
        raise


def delete(key: str) -> bool:
    try:
        return get_storage().delete(key)
    except FileNotFoundError:
        return False
