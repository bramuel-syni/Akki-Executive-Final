"""Synisense — security layer status + live demo endpoint.

Synisense is AKKI's identity-shielding wall between user inputs (documents,
chat questions) and the LLM. This module:

  - reports on what the shielder can detect (so users know what's protected)
  - offers a dry-run endpoint that takes arbitrary text and returns the
    masked version + a category breakdown — the "see it for yourself"
    demonstration NEDs and executives want before they upload a board pack.

The actual shielding logic is in ``llm_service.py`` (shield_payload) and
is used on every LLM call. Nothing here mutates state.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core import get_current_account
from llm_service import shield_payload, shielding_report

router = APIRouter(prefix="/api")


CATEGORIES = [
    {
        "id": "email",
        "label": "Email addresses",
        "description": "RFC-5322 style tokens — e.g. director@company.com",
        "example": "alice.mwalo@firstnationalbank.co.ke",
    },
    {
        "id": "url",
        "label": "URLs",
        "description": "Any http(s):// link — including internal portals and share links.",
        "example": "https://internal.boards.company.com/audit-pack-Q4.pdf",
    },
    {
        "id": "phone",
        "label": "Phone numbers",
        "description": "Kenyan, UK, US, SA formats. Landline or mobile.",
        "example": "+254 722 456 789",
    },
    {
        "id": "natid",
        "label": "Kenyan National ID",
        "description": "Triggered only in ID-context (e.g. 'ID: 29847261').",
        "example": "ID: 29847261",
    },
    {
        "id": "iban",
        "label": "IBAN numbers",
        "description": "International Bank Account Numbers.",
        "example": "GB29NWBK60161331926819",
    },
    {
        "id": "acct",
        "label": "Account numbers",
        "description": "Local bank accounts when preceded by A/c, Account, Acct.",
        "example": "Acct no. 0100123456789",
    },
    {
        "id": "cc",
        "label": "Payment card numbers",
        "description": "13–16 digit sequences that pattern-match a card.",
        "example": "4532 1234 5678 9012",
    },
    {
        "id": "swift",
        "label": "SWIFT/BIC codes",
        "description": "Bank identifier codes used on international transfers.",
        "example": "KCBLKENXXXX",
    },
    {
        "id": "person",
        "label": "Personal names",
        "description": "Honorific + name pairs (Mr/Mrs/Ms/Dr/Prof/Hon). Capped at 20 per payload.",
        "example": "Dr. Jane Wanjiru",
    },
]


@router.get("/synisense/status")
async def synisense_status(current: Dict[str, Any] = Depends(get_current_account)):
    """What the shielder knows and what it does. For the Settings → Security
    page and the Landing trust section."""
    return {
        "engine": "synisense-local",
        "version": "1.0",
        "enabled": True,
        "wraps_every_llm_call": True,
        "reverses_in_output": True,
        "categories": CATEGORIES,
        "notes": (
            "All LLM calls from AKKI pass through Synisense first. Identifiers are "
            "replaced with category-indexed tokens ([EMAIL_1], [PERSON_3] etc.) — "
            "the LLM can still reason about them as entities but never sees the "
            "original values. Tokens are reversed in the returned response before "
            "the user sees it."
        ),
    }


class ShieldDryRunIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


@router.post("/synisense/dryrun")
async def synisense_dry_run(
    body: ShieldDryRunIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Runs the shielder against arbitrary text and returns the masked output
    plus a per-category count. Lets users see the layer for themselves without
    having to trigger an LLM call. Original values are NEVER returned."""
    masked, shield_map = shield_payload(body.text)
    report = shielding_report(shield_map)
    return {
        "original_chars": len(body.text),
        "masked_text": masked,
        "masked_chars": len(masked),
        "report": report,
    }
