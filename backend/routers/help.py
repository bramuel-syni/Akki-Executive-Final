"""Phase E — `/api/help/features` route.

Serves the canonical AKKI product spec (`/app/memory/AKKI_PRODUCT_SPEC.md`,
currently v1.1) so the React `/help` page can render it inline. Mirrors
the no-auth `product_features` router (this is product-overview material
— the same audience that lands on the website nav reads it).

CLEANUP B1 (2026-05-26): source switched from the deprecated
`AKKI_FEATURES_AND_FUNCTIONALITY.md` (which `AKKI_PRODUCT_SPEC.md` §1.4
explicitly strips of authority) to the canonical spec. The route stays
alive to preserve the `/help` page; only the body source changed.

Response envelope is JSON because the React FE uses `react-markdown`
to render the body and also needs the document metadata (last
modified timestamp, char/word counts) for the page header.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

router = APIRouter(prefix="/api/help", tags=["help"])

_FEATURES_DOC = Path("/app/memory/AKKI_PRODUCT_SPEC.md")


def _read_doc() -> str:
    if not _FEATURES_DOC.exists():
        raise HTTPException(
            status_code=404,
            detail="AKKI_PRODUCT_SPEC.md not found",
        )
    try:
        return _FEATURES_DOC.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"read failed: {type(exc).__name__}",
        )


def _doc_metadata(markdown: str) -> dict:
    """Derive title (first H1) + word/char counts from the body."""
    title = "AKKI Product Spec"
    for line in markdown.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return {
        "title": title,
        "char_count": len(markdown),
        "word_count": len(markdown.split()),
    }


@router.get("/features")
async def get_help_features():
    """Return the product spec as JSON envelope for the React
    `/help` page to render."""
    markdown = _read_doc()
    stat = _FEATURES_DOC.stat()
    last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    meta = _doc_metadata(markdown)
    return {
        "title": meta["title"],
        "last_modified": last_modified,
        "char_count": meta["char_count"],
        "word_count": meta["word_count"],
        "markdown": markdown,
    }


@router.get("/features.md")
async def get_help_features_raw():
    """Same content, served as raw `text/markdown` for direct browser
    download / sharing. Keeps the route family consistent with
    `/api/product-features.md`."""
    markdown = _read_doc()
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": (
                'inline; filename="AKKI_PRODUCT_SPEC.md"'
            ),
        },
    )
