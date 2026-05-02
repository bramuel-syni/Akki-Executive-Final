"""Document extraction + storage pipeline.

Phase 10 changes:
  * ``virus_scan_stub`` is gone. Callers should invoke
    ``services.clamav_service.scan`` directly and translate
    :class:`ClamAVUnreachable` to a 503 with an audit row.
  * ``save_to_storage`` / ``read_from_storage`` / ``delete_from_storage``
    delegate to ``services.storage_service`` which swaps between
    local disk (tests) and S3/MinIO (prod) by the ``STORAGE_BACKEND``
    env var. The DB column continues to store the opaque key.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Optional, Tuple

from services import storage_service

ACCEPT_EXT = {".pdf", ".docx", ".txt", ".md", ".rtf"}
MAX_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_EXTRACT_CHARS = 200_000


def save_to_storage(context_id: str, doc_id: str, filename: str, data: bytes,
                    content_type: Optional[str] = None) -> str:
    """Store bytes through the configured storage backend; return key."""
    return storage_service.save(context_id, doc_id, filename, data, content_type=content_type)


def read_from_storage(key: str) -> bytes:
    return storage_service.read(key)


def delete_from_storage(key: str) -> None:
    storage_service.delete(key)


def extract_text(data: bytes, filename: str, mime_type: str) -> Tuple[str, Optional[str]]:
    """Return (text, error). Text is truncated to MAX_EXTRACT_CHARS."""
    ext = Path(filename).suffix.lower()
    try:
        if ext == ".pdf" or mime_type == "application/pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages = []
            for page in reader.pages:
                try:
                    pages.append(page.extract_text() or "")
                except Exception:
                    continue
            return ("\n\n".join(pages))[:MAX_EXTRACT_CHARS], None
        if ext == ".docx" or "officedocument.wordprocessingml" in (mime_type or ""):
            from docx import Document as DocxDocument
            d = DocxDocument(io.BytesIO(data))
            text = "\n".join(p.text for p in d.paragraphs if p.text)
            return text[:MAX_EXTRACT_CHARS], None
        if ext in (".txt", ".md", ".rtf") or (mime_type or "").startswith("text/"):
            try:
                return data.decode("utf-8", errors="replace")[:MAX_EXTRACT_CHARS], None
            except Exception as e:
                return "", f"decode failed: {e}"
        return "", f"Unsupported file type: {ext}"
    except Exception as e:
        return "", f"extraction failed: {e}"


def make_preview(text: str, max_len: int = 320) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:max_len] + ("…" if len(cleaned) > max_len else "")
