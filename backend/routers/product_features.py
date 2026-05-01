"""Public download route for the product-features inventory document.

Serves /app/memory/PRODUCT_FEATURES.md as raw markdown. Two paths:
  - GET /api/product-features      → inline text/markdown (browser preview)
  - GET /api/product-features.md   → attachment (download)

No auth — this is a documentation artefact the user explicitly wants
shareable behind the preview proxy.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

router = APIRouter(prefix="/api", tags=["docs"])

_PRODUCT_DOC_PATH = Path("/app/memory/PRODUCT_FEATURES.md")
_UX_AUDIT_DOC_PATH = Path("/app/memory/UX_ADVISORIES_AUDIT.md")
_UX_ADVISORIES_DOC_PATH = Path("/app/docs/ux-advisories-v1.md")


def _read_doc(path: Path, label: str) -> str:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{label} not found")
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Read failed: {e}")


@router.get("/product-features")
async def product_features_inline():
    """Return markdown inline (browser will preview as text)."""
    body = _read_doc(_PRODUCT_DOC_PATH, "PRODUCT_FEATURES.md")
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/product-features.md")
async def product_features_download():
    """Return markdown as a download (Content-Disposition: attachment)."""
    body = _read_doc(_PRODUCT_DOC_PATH, "PRODUCT_FEATURES.md")
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="PRODUCT_FEATURES.md"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/ux-audit")
async def ux_audit_inline():
    """Return UX_ADVISORIES_AUDIT.md inline (browser will preview as text)."""
    body = _read_doc(_UX_AUDIT_DOC_PATH, "UX_ADVISORIES_AUDIT.md")
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/ux-audit.md")
async def ux_audit_download():
    """Return UX_ADVISORIES_AUDIT.md as a download."""
    body = _read_doc(_UX_AUDIT_DOC_PATH, "UX_ADVISORIES_AUDIT.md")
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="UX_ADVISORIES_AUDIT.md"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/ux-advisories")
async def ux_advisories_inline():
    """Return ux-advisories-v1.md inline (rules doc; mirror of homepage-positioning-v1)."""
    body = _read_doc(_UX_ADVISORIES_DOC_PATH, "ux-advisories-v1.md")
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/ux-advisories.md")
async def ux_advisories_download():
    """Return ux-advisories-v1.md as a download."""
    body = _read_doc(_UX_ADVISORIES_DOC_PATH, "ux-advisories-v1.md")
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="ux-advisories-v1.md"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
