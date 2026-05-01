"""Citation references helper — Reading Viewer Phase 1.

Builds the `references[]` array attached additively to signals / ask /
briefings response objects, alongside the existing `[doc:xxx]` inline
tokens (the inline tokens stay; this is purely additive).

Each reference shape:
    { doc_id, doc_title, page, paragraph_id, paragraph_number }

`paragraph_id` and `paragraph_number` are nullable — populated when the
underlying answer carries a sentence-offset that lands inside a known
paragraph. Otherwise the UI falls back to page-level rendering.

For v1 the LLM prompts have not been retrained to emit paragraph-level
cites yet, so most references will be page=null + paragraph_id=null and
the UI will show `[doc:Q4 Pack]` rather than `p.14¶3`. That's the
graceful fallback the brief contemplates.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def build_references(
    sources: Iterable[Dict[str, Any]],
    docs_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Map each `sources[]` entry (existing shape: {doc_id, doc_name, ...})
    to the new `references[]` shape. Safe with missing fields and is
    additive — does not mutate the input."""
    if not sources:
        return []
    refs: List[Dict[str, Any]] = []
    for s in sources:
        if not isinstance(s, dict):
            continue
        doc_id = s.get("doc_id")
        if not doc_id:
            continue
        # Source shape varies (`doc_name` historically; some places use
        # `doc_title`). Prefer `doc_name`, fall back to docs_by_id lookup,
        # then to doc_title or just the id.
        doc_title = s.get("doc_name") or s.get("doc_title")
        if not doc_title and docs_by_id and doc_id in docs_by_id:
            d = docs_by_id[doc_id]
            doc_title = d.get("name") or d.get("title")
        refs.append({
            "doc_id": doc_id,
            "doc_title": doc_title or doc_id,
            "page": s.get("page"),                  # may be None at v1
            "paragraph_id": s.get("paragraph_id"),  # may be None at v1
            "paragraph_number": s.get("paragraph_number"),  # may be None
        })
    return refs
