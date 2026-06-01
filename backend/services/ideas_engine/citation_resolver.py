"""Phase P5.15 — Ideas citation resolver.

Verifies each `IdeaCitation` against the tenant's real document
corpus:

  1. `document_id` resolves to a document in `documents` collection
     scoped to the tenant's `account_id` (cross-tenant references
     are treated as fabrications — same `citation_unverifiable`
     error code).
  2. If `chunk_id` is given, it resolves to an entry in
     `extractions_log` whose `document_id` matches the citation.

Two failure paths:
  * `CitationUnverifiable` raised on the offender (single-citation api)
  * `verify_many()` collects ALL failures and raises one
    aggregated error so the caller can render a useful diagnostic.

Async because the verification touches Mongo (unlike the
workbook_analyzer resolver which operates on in-memory parsed
sheets).
"""
from __future__ import annotations

from typing import Iterable, List, Optional

from .schema import IdeaCitation


class CitationUnverifiable(ValueError):
    """Raised when an `IdeaCitation` cannot be resolved against
    the tenant's corpus. Message prefix `citation_unverifiable:`
    so upstream tests + UI logic can pattern-match."""
    pass


class IdeasCitationResolver:
    """Per-tenant resolver. Constructed with the live Mongo
    handle. Caches positive document_id lookups for the duration
    of the resolver instance so a batch of citations sharing a
    document_id doesn't hammer Mongo."""

    def __init__(self, db, account_id: str) -> None:
        self._db = db
        self._account_id = account_id
        self._doc_cache: set[str] = set()

    async def _document_exists(self, document_id: str) -> bool:
        if document_id in self._doc_cache:
            return True
        doc = await self._db.documents.find_one(
            {"id": document_id, "account_id": self._account_id},
            {"_id": 0, "id": 1},
        )
        if doc is None:
            return False
        self._doc_cache.add(document_id)
        return True

    async def _chunk_exists(self, chunk_id: str, document_id: str) -> bool:
        row = await self._db.extractions_log.find_one(
            {"id": chunk_id, "document_id": document_id},
            {"_id": 0, "id": 1},
        )
        return row is not None

    async def verify(self, citation: IdeaCitation) -> None:
        if not await self._document_exists(citation.document_id):
            raise CitationUnverifiable(
                f"citation_unverifiable: document_id={citation.document_id!r} not in this tenant's corpus"
            )
        if citation.chunk_id is not None:
            if not await self._chunk_exists(citation.chunk_id, citation.document_id):
                raise CitationUnverifiable(
                    f"citation_unverifiable: chunk_id={citation.chunk_id!r} does not resolve "
                    f"to a chunk of document_id={citation.document_id!r}"
                )

    async def verify_many(self, citations: Iterable[IdeaCitation]) -> None:
        failures: List[str] = []
        for c in citations:
            try:
                await self.verify(c)
            except CitationUnverifiable as e:
                failures.append(str(e))
        if failures:
            raise CitationUnverifiable(
                "citation_unverifiable_batch:\n  - " + "\n  - ".join(failures)
            )


__all__ = ["CitationUnverifiable", "IdeasCitationResolver"]
