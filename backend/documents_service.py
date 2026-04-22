"""Document extraction + storage pipeline (M3).

Current implementation:
- Local disk storage (shaped like S3 — swap via STORAGE_BACKEND env later)
- pypdf for PDFs, python-docx for .docx, raw text for .txt/.md
- Virus scan is a stub (ClamAV integration in M4)
- Returns extracted text (truncated to ~200KB) and a preview snippet
"""
from __future__ import annotations

import io
import os
import re
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple

STORAGE_ROOT = Path(os.environ.get("UPLOADS_DIR", "/app/backend/uploads"))
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

ACCEPT_EXT = {".pdf", ".docx", ".txt", ".md", ".rtf"}
MAX_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_EXTRACT_CHARS = 200_000


def virus_scan_stub(data: bytes, filename: str) -> Tuple[bool, Optional[str]]:
    """Returns (clean, reason_if_unclean). Real ClamAV wires in M4."""
    if b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in data[:8192]:
        return False, "EICAR test signature detected"
    return True, None


def save_to_storage(context_id: str, doc_id: str, filename: str, data: bytes) -> str:
    """Store bytes on disk; return storage key."""
    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", filename)[:200]
    ext = Path(safe_name).suffix.lower()
    context_dir = STORAGE_ROOT / context_id
    context_dir.mkdir(parents=True, exist_ok=True)
    path = context_dir / f"{doc_id}{ext}"
    path.write_bytes(data)
    return str(path.relative_to(STORAGE_ROOT))


def read_from_storage(key: str) -> bytes:
    return (STORAGE_ROOT / key).read_bytes()


def delete_from_storage(key: str) -> None:
    path = STORAGE_ROOT / key
    if path.exists():
        path.unlink()


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
