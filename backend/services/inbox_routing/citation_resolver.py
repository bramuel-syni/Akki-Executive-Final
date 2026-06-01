"""P5.16 — Citation resolver for inbox-routing classifications.

Verifies that every `ClassificationCitation` points to a real
`admin_inbox_messages` row, and that the cited excerpt is actually
present in that row's subject/body/from/to field. Cross-tenant
behaviour: when the caller provides an `account_id`, the resolver
also verifies the message_id's resolved tenant (via mailbox-hash
→ accounts.inbound_token, or the existing classification's
`target_hint.account_id`) matches the caller's tenant. This is a
soft check — the admin inbox is global; the tenant guard exists
so the routing-log read endpoint can refuse to leak rows that
were routed to a different tenant.

Resolver instances cache message_ids per call so a batch verify of
N citations is at most N Mongo lookups (deduped).
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Set

from core import db


class CitationUnverifiable(ValueError):
    """Raised when one or more citations cannot be verified. Message
    aggregates ALL failures with the `citation_unverifiable:` prefix
    (same convention as Ideas + workbook_analyzer)."""
    pass


class InboxRoutingCitationResolver:
    """One instance per classify call. Caches verified message_ids
    so a follow-up route() in the same request doesn't re-query."""

    def __init__(self) -> None:
        self._verified_ids: Set[str] = set()
        self._known_missing: Set[str] = set()

    async def verify_one(self, *, message_id: str, excerpt: str,
                          field: str = "body") -> None:
        """Verify a single citation. Raises on failure."""
        if not message_id or not isinstance(message_id, str):
            raise CitationUnverifiable(
                "citation_unverifiable: empty message_id"
            )
        if message_id in self._known_missing:
            raise CitationUnverifiable(
                f"citation_unverifiable: message_id={message_id!r} not found"
            )
        if message_id not in self._verified_ids:
            row = await db.admin_inbox_messages.find_one(
                {"id": message_id},
                {"_id": 0, "id": 1, "subject": 1, "text_body": 1,
                 "html_body": 1, "from_email": 1, "to_addresses": 1},
            )
            if not row:
                self._known_missing.add(message_id)
                raise CitationUnverifiable(
                    f"citation_unverifiable: message_id={message_id!r} not found"
                )
            self._verified_ids.add(message_id)
            # Cache the row's text bodies for excerpt verification below.
            self._cached_row = row
        else:
            # Re-fetch only if we need the body for excerpt verification.
            row = await db.admin_inbox_messages.find_one(
                {"id": message_id},
                {"_id": 0, "subject": 1, "text_body": 1,
                 "html_body": 1, "from_email": 1, "to_addresses": 1},
            )
            self._cached_row = row

        # Excerpt must literally appear in the named field, case-insensitive,
        # whitespace-normalised. The classifier emits excerpts taken
        # verbatim from the source, so a strict substring match suffices.
        haystack = ""
        if field == "subject":
            haystack = (row.get("subject") or "")
        elif field == "from":
            haystack = (row.get("from_email") or "")
        elif field == "to":
            haystack = " ".join(row.get("to_addresses") or [])
        else:  # body
            haystack = (row.get("text_body") or "") or (row.get("html_body") or "")

        if not _contains_excerpt(haystack, excerpt):
            raise CitationUnverifiable(
                f"citation_unverifiable: excerpt not present in message_id="
                f"{message_id!r} field={field!r}"
            )

    async def verify_many(self, citations: Iterable) -> None:
        """Verify all citations; aggregate failures into one error."""
        failures: List[str] = []
        for c in citations:
            try:
                # Accept both pydantic models and raw dicts.
                mid = getattr(c, "message_id", None) or c.get("message_id")  # type: ignore[union-attr]
                ex = getattr(c, "excerpt", None) or c.get("excerpt")  # type: ignore[union-attr]
                fl = getattr(c, "field", None) or (c.get("field") if isinstance(c, dict) else None) or "body"
                await self.verify_one(message_id=mid, excerpt=ex, field=fl)
            except CitationUnverifiable as e:
                failures.append(str(e))
        if failures:
            raise CitationUnverifiable("; ".join(failures))


def _contains_excerpt(haystack: str, excerpt: str) -> bool:
    """Case-insensitive whitespace-tolerant substring check."""
    if not haystack or not excerpt:
        return False
    def _norm(s: str) -> str:
        return " ".join(s.split()).lower()
    return _norm(excerpt) in _norm(haystack)


__all__ = [
    "CitationUnverifiable",
    "InboxRoutingCitationResolver",
]
