"""Paragraph-anchor computation for Reading Viewer (Phase 1, Advisory 2).

Splits a document's `extracted_text` into stable paragraph anchors used by
the Reading view to wire bidirectional scroll-sync between the body and
AKKI's commentary rail, and to render `p.14¶3`-style citation chips.

Algorithm (per the v1 brief, A2):
  1. Page boundaries are detected from form-feed (\\f) characters in the
     extracted text — `documents_service.extract_text` already inserts these
     between PDF / DOCX / pptx pages. If no \\f is present (.txt / .md), the
     whole document is treated as page 1.
  2. Within each page, paragraphs are split on a blank-line boundary
     (`\\n\\s*\\n`). Heading-only blocks (single short upper-case or
     numbered line) are kept as their own paragraph.
  3. Whitespace-only paragraphs are dropped.
  4. Paragraphs longer than 800 chars are split at the nearest sentence
     boundary (".", "!", "?" followed by whitespace) before the limit.
     Falls back to a hard 800-char split if no boundary is found.
  5. char_start / char_end are recorded against the *full* extracted_text,
     not per-page, so the UI can map back to the source for export.
  6. id = sha1(doc_id + "|" + page + "|" + paragraph_number).hexdigest()[:12]
     — stable across re-runs for the same logical input. The doc_id is
     baked in so two different docs with identical text don't collide.
  7. Idempotent: running on the same input twice returns identical output.

Returns a dict shaped:
    {
      "paragraphs": [...],
      "page_count": int,
      "version": int,
      "computed_at": str (iso UTC),
    }

`PARAGRAPH_ANCHOR_VERSION` bumps if the algorithm changes — the cron sweep
uses it to re-compute stale anchors.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

PARAGRAPH_ANCHOR_VERSION = 1

_MAX_PARAGRAPH_CHARS = 800

# Sentence boundary: ., !, or ? followed by whitespace.
_SENTENCE_BOUNDARY = re.compile(r"[.!?](?=\s)")
_BLANK_LINE = re.compile(r"\n\s*\n+")


def _split_long_paragraph(text: str, max_len: int = _MAX_PARAGRAPH_CHARS) -> List[str]:
    """Split a paragraph that exceeds max_len at the nearest sentence
    boundary before the cap. Falls back to hard wrap. Idempotent."""
    if len(text) <= max_len:
        return [text]
    out: List[str] = []
    remaining = text
    while len(remaining) > max_len:
        # Find the last sentence boundary inside the cap window.
        window = remaining[:max_len]
        boundaries = list(_SENTENCE_BOUNDARY.finditer(window))
        if boundaries:
            cut = boundaries[-1].end()  # include the punctuation
        else:
            # No sentence boundary — find the last whitespace as a softer cut.
            ws = window.rfind(" ")
            cut = ws if ws > max_len // 2 else max_len
        chunk = remaining[:cut].rstrip()
        if chunk:
            out.append(chunk)
        remaining = remaining[cut:].lstrip()
    if remaining.strip():
        out.append(remaining.strip())
    return out


def _hash_id(doc_id: str, page: int, paragraph_number: int) -> str:
    raw = f"{doc_id}|{page}|{paragraph_number}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]


def compute_paragraphs(doc_id: str, extracted_text: str) -> Dict[str, Any]:
    """Public entry point.

    Args:
        doc_id: stable document UUID.
        extracted_text: the document's full extracted plain text.

    Returns:
        dict with `paragraphs`, `page_count`, `version`, `computed_at`.
    """
    text = extracted_text or ""
    if not text.strip():
        return {
            "paragraphs": [],
            "page_count": 0,
            "version": PARAGRAPH_ANCHOR_VERSION,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    # Track absolute char offsets across the full extracted_text.
    pages = text.split("\f") if "\f" in text else [text]
    paragraphs: List[Dict[str, Any]] = []
    cursor = 0  # absolute offset in `text`

    for page_idx, page_text in enumerate(pages, start=1):
        # Walk the page, splitting on blank-lines but keeping cursor maths sane.
        # We use `re.finditer` so we can track exact positions of separators.
        # Alternative approach: walk char-by-char. The regex is faster and
        # the offsets from match.span() are exact.
        last_end = 0
        chunks: List[Dict[str, Any]] = []  # raw {text, page_local_start}
        for m in _BLANK_LINE.finditer(page_text):
            chunk = page_text[last_end:m.start()]
            chunks.append({"text": chunk, "page_local_start": last_end})
            last_end = m.end()
        # Tail.
        if last_end < len(page_text):
            chunks.append({
                "text": page_text[last_end:],
                "page_local_start": last_end,
            })

        para_no = 0
        for raw in chunks:
            stripped = raw["text"].strip()
            if not stripped:
                continue
            # Honour the max-paragraph cap.
            sub_chunks = _split_long_paragraph(stripped, _MAX_PARAGRAPH_CHARS)
            # `cursor + raw[page_local_start] + leading-whitespace-len` ≈ char_start.
            # Compute the leading-whitespace adjustment so the offset points
            # at the first non-whitespace character of the paragraph.
            leading_ws = len(raw["text"]) - len(raw["text"].lstrip())
            base_abs_start = cursor + raw["page_local_start"] + leading_ws
            sub_offset_in_chunk = 0
            stripped_text_full = raw["text"][leading_ws:]
            for sub in sub_chunks:
                # Find this sub's offset inside the parent chunk so the
                # absolute char_start tracks the source faithfully even
                # after the long-paragraph split.
                idx = stripped_text_full.find(sub, sub_offset_in_chunk)
                if idx < 0:
                    idx = sub_offset_in_chunk
                abs_start = base_abs_start + idx
                abs_end = abs_start + len(sub)
                para_no += 1
                paragraphs.append({
                    "id": _hash_id(doc_id, page_idx, para_no),
                    "page": page_idx,
                    "paragraph_number": para_no,
                    "text": sub,
                    "char_start": abs_start,
                    "char_end": abs_end,
                })
                sub_offset_in_chunk = idx + len(sub)

        # Advance the absolute cursor past this page (+1 for the form-feed
        # that the page split consumed, except for the final page).
        cursor += len(page_text)
        if page_idx < len(pages):
            cursor += 1  # the \f character

    return {
        "paragraphs": paragraphs,
        "page_count": len(pages),
        "version": PARAGRAPH_ANCHOR_VERSION,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def find_paragraph_for_offset(
    paragraphs: List[Dict[str, Any]], char_offset: int,
) -> Dict[str, Any] | None:
    """Given absolute char_offset, return the paragraph that contains it.
    Used by the citation-contract extension to upgrade page-level cites
    to paragraph-level cites when a sentence-offset is available."""
    for p in paragraphs:
        if p["char_start"] <= char_offset < p["char_end"]:
            return p
    return None
