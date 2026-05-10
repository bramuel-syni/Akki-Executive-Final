"""Shared 'Continue in Chat' helper.

The original implementation lived inline in
`backend/routers/work_studio_export.py:_create_continue_chat`. Phase B.7
adds the same handoff to the Cycle Manager compilation step
(`routers/cycle_manager.py:draft_compilation`), so the function moves
here and is re-exported from work_studio_export to preserve the
existing import surface for the audit pipeline.

The helper is intentionally generic over `kind`: the Work Studio
callers pass `"brief"` / `"deck"` / `"report"`, and Cycle Manager
passes `"cycle_compilation"`. The chat title and document chip both
label the kind; the audit row records it.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Tuple

from core import db, iso, now

logger = logging.getLogger("akki.continue_chat")


async def create_continue_chat(
    *,
    account_id: str,
    context_id: str,
    kind: str,
    source: str,
    export_id: str,
    file_name: str,
    file_path: str,
    output_format: str,
    extracted_text: str,
    sensitivity_band: str,
) -> Tuple[str, str]:
    """Mint a chat row + an artefact document row. Returns (chat_id, doc_id).

    Both rows carry the active context_id so the chat shows up in the
    SPA's per-context list (Chat.jsx onNewChat parity — Phase B Workstream
    A.1 made the contract explicit: chats without context_id are filtered
    out by the active-context guard at GET /chats).
    """
    chat_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    created_at = iso(now())

    pretty_kind = {
        "brief": "Brief",
        "deck": "Deck",
        "report": "Report",
        "cycle_compilation": "Cycle compilation",
    }.get(kind, kind.replace("_", " ").title())

    chat_row = {
        "id": chat_id,
        "account_id": account_id,
        "title": f"Continue · {pretty_kind} · {file_name[:60]}",
        "model_id": "claude-sonnet-4-5-20250929",
        "shielding_policy": "auto",
        "context_id": context_id,
        "status": "active",
        "message_count": 0,
        "last_message_preview": "",
        "last_message_at": None,
        "created_at": created_at,
        "updated_at": created_at,
        "continue_source": source,
        "continue_artefact_id": export_id,
        "continue_kind": kind,
    }
    await db.chats.insert_one(chat_row)

    band_lower = (sensitivity_band or "INTERNAL").lower()
    doc_row = {
        "id": doc_id,
        "context_id": context_id,
        "name": file_name,
        "original_filename": file_name,
        "mime_type": {
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "pdf":  "application/pdf",
        }.get(output_format, "application/octet-stream"),
        "size_bytes": (Path(file_path).stat().st_size if Path(file_path).exists() else 0),
        "storage_key": f"work_studio_exports/{export_id}.{output_format}",
        "status": "extracted",
        "extracted_text": extracted_text or "",
        "extracted_chars": len(extracted_text or ""),
        "preview": (extracted_text or "")[:320],
        "data_trust": "trusted",
        "doc_type": "work_studio_artefact" if kind != "cycle_compilation" else "cycle_compilation",
        "uploaded_by": account_id,
        "source_channel": source,
        "chat_id": chat_id,
        "synisense_version": 0,
        "body_redacted": None,
        "sensitivity_band": band_lower,
        "sensitivity_score": 0,
        "sensitivity_label": (sensitivity_band or "INTERNAL").upper(),
        "created_at": created_at,
        "updated_at": created_at,
        "work_studio_export_id": export_id,
    }
    await db.documents.insert_one(doc_row)

    return chat_id, doc_id
