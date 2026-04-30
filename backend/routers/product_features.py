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

_DOC_PATH = Path("/app/memory/PRODUCT_FEATURES.md")


def _read_doc() -> str:
    if not _DOC_PATH.exists():
        raise HTTPException(status_code=404, detail="PRODUCT_FEATURES.md not found")
    try:
        return _DOC_PATH.read_text(encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Read failed: {e}")


@router.get("/product-features")
async def product_features_inline():
    """Return markdown inline (browser will preview as text)."""
    body = _read_doc()
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
    body = _read_doc()
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="PRODUCT_FEATURES.md"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
