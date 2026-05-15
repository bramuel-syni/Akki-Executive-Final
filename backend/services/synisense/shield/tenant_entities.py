"""Synisense Shield — tenant entity dictionary (Phase A).

What it does:
- **Harvest** at startup (or on `/api/v1/engine/admin/reseed`) — read
  the existing Mongo collections to extract tenant-specific proper
  nouns:
  - `accounts.company_name`, `accounts.full_name`
  - `contexts.name`, `contexts.organization_name`
  - proper-noun-looking substrings from `cycles.title`
- **Persist** in `synisense_tenant_entities` with fields:
  `tenant_id, entity_text, entity_type, source_collection, harvested_at`.
- **Lookup** at de-id time — `lookup_in_text(text, tenant_id=...)`
  returns a list of hits the deidentifier merges into its overall
  span list (priority 2: above spaCy, below regex).

The lookup runs BEFORE spaCy so a name spaCy never saw (e.g. "Lemasy")
is still redacted as long as it was harvested into the dictionary.

Matching:
- Case-insensitive.
- Whole-token boundary (`\b<text>\b`, escaped).
- Longest-match-first to avoid one entity swallowing another's prefix.

The harvester is intentionally generous — it errs on over-collection
because false positives in the dictionary cost only a token, while
false negatives cost privacy.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core import db

log = logging.getLogger("synisense.shield.tenant_entities")

ENTITY_COLLECTION = "synisense_tenant_entities"

# In-memory cache keyed by tenant_id. Refreshed on harvest. The list
# is sorted by length-desc so the longest match always wins.
_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_CACHE_LOADED_AT: Dict[str, float] = {}
_CACHE_TTL_SECONDS = 300  # 5 min — refresh-on-harvest is the canonical path

# Proper-noun harvest pattern — sequences of capitalised words ≥2 chars.
_PROPER_NOUN_RE = re.compile(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]+){0,3}\b")

# Stop-list — extremely common English words that would be over-redacted
# if treated as proper nouns. Kept narrow (the LIST is short by design).
_STOP_WORDS = {
    "The", "And", "But", "For", "With", "From", "This", "That",
    "When", "Where", "What", "Why", "How",
}


def _extract_proper_nouns(text: str) -> List[str]:
    if not text:
        return []
    out: List[str] = []
    for m in _PROPER_NOUN_RE.finditer(text):
        token = m.group(0).strip()
        first = token.split()[0]
        if first in _STOP_WORDS:
            continue
        out.append(token)
    return out


async def harvest(tenant_id: str) -> Dict[str, int]:
    """Harvest tenant-known entities from existing Mongo collections,
    write to `synisense_tenant_entities` (replace-by-tenant), refresh
    the in-memory cache, return counts."""
    counts = {"accounts.company_name": 0, "accounts.full_name": 0,
              "contexts.name": 0, "contexts.organization_name": 0,
              "cycles.title": 0}
    rows: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    # Accounts — Phase A binds tenant_id := account_id (see route docs),
    # so we harvest the row whose id == tenant_id.
    acc = await db.accounts.find_one({"id": tenant_id}, {"_id": 0})
    if acc:
        for field, key in (("company_name", "ORG"), ("full_name", "PERSON")):
            val = acc.get(field)
            if isinstance(val, str) and val.strip():
                rows.append({
                    "tenant_id": tenant_id,
                    "entity_text": val.strip(),
                    "entity_type": key,
                    "source_collection": f"accounts.{field}",
                    "harvested_at": now,
                })
                counts[f"accounts.{field}"] += 1

    # Contexts where this account is the owner.
    ctx_cursor = db.contexts.find(
        {"owner_account_id": tenant_id},
        {"_id": 0, "name": 1, "organization_name": 1, "id": 1},
    )
    async for ctx in ctx_cursor:
        for field, key in (("name", "ORG"), ("organization_name", "ORG")):
            val = ctx.get(field)
            if isinstance(val, str) and val.strip():
                rows.append({
                    "tenant_id": tenant_id,
                    "entity_text": val.strip(),
                    "entity_type": key,
                    "source_collection": f"contexts.{field}",
                    "harvested_at": now,
                })
                counts[f"contexts.{field}"] += 1

        # Cycles scoped to this context.
        ctx_id = ctx.get("id")
        if ctx_id:
            cy_cursor = db.cycles.find(
                {"context_id": ctx_id}, {"_id": 0, "title": 1},
            )
            async for cy in cy_cursor:
                title = cy.get("title")
                for noun in _extract_proper_nouns(title or ""):
                    rows.append({
                        "tenant_id": tenant_id,
                        "entity_text": noun,
                        "entity_type": "ORG",
                        "source_collection": "cycles.title",
                        "harvested_at": now,
                    })
                    counts["cycles.title"] += 1

    # Replace this tenant's rows wholesale.
    await db[ENTITY_COLLECTION].delete_many({"tenant_id": tenant_id})
    if rows:
        await db[ENTITY_COLLECTION].insert_many(rows)

    # Refresh cache.
    await _reload_cache(tenant_id)
    log.info("synisense.tenant_entities: harvested %d rows for tenant=%s",
             sum(counts.values()), tenant_id)
    return counts


async def register(
    *,
    tenant_id: str,
    entity_text: str,
    entity_type: str = "ORG",
    source_collection: str = "manual.register",
) -> None:
    """Manually register a single entity. Used by tests and by the
    `/admin/reseed` endpoint for custom seed data."""
    entity_text = (entity_text or "").strip()
    if not entity_text:
        return
    now = datetime.now(timezone.utc).isoformat()
    await db[ENTITY_COLLECTION].update_one(
        {"tenant_id": tenant_id, "entity_text": entity_text},
        {"$set": {
            "tenant_id": tenant_id,
            "entity_text": entity_text,
            "entity_type": entity_type,
            "source_collection": source_collection,
            "harvested_at": now,
        }},
        upsert=True,
    )
    await _reload_cache(tenant_id)


async def _reload_cache(tenant_id: str) -> None:
    cursor = db[ENTITY_COLLECTION].find(
        {"tenant_id": tenant_id},
        {"_id": 0, "entity_text": 1, "entity_type": 1},
    )
    rows = [r async for r in cursor]
    rows.sort(key=lambda r: -len(r.get("entity_text") or ""))
    _CACHE[tenant_id] = rows
    _CACHE_LOADED_AT[tenant_id] = time.monotonic()


async def _ensure_cache(tenant_id: str) -> List[Dict[str, Any]]:
    last = _CACHE_LOADED_AT.get(tenant_id)
    if last is None or (time.monotonic() - last) > _CACHE_TTL_SECONDS:
        await _reload_cache(tenant_id)
    return _CACHE.get(tenant_id, [])


async def lookup_in_text(text: str, *, tenant_id: str) -> List[Dict[str, Any]]:
    """Return regex-style hits `[{start, end, type, match}]` for every
    tenant-known entity found in `text`. Longest-match-first; overlaps
    resolved at the caller side by the deidentifier."""
    if not text:
        return []
    catalogue = await _ensure_cache(tenant_id)
    if not catalogue:
        return []
    hits: List[Dict[str, Any]] = []
    occupied: List[tuple] = []  # (start, end) ranges already claimed

    for row in catalogue:
        entity_text = row.get("entity_text") or ""
        entity_type = row.get("entity_type") or "ORG"
        if not entity_text:
            continue
        pattern = re.compile(
            r"(?<![A-Za-z0-9_])" + re.escape(entity_text) + r"(?![A-Za-z0-9_])",
            re.IGNORECASE,
        )
        for m in pattern.finditer(text):
            s, e = m.start(), m.end()
            # Skip if overlap with already-claimed region.
            if any(s < oe and e > os for os, oe in occupied):
                continue
            hits.append({"start": s, "end": e, "type": entity_type, "match": m.group(0)})
            occupied.append((s, e))
    return hits


def _force_clear_cache_for_test(tenant_id: Optional[str] = None) -> None:
    """Test-only."""
    if tenant_id is None:
        _CACHE.clear()
        _CACHE_LOADED_AT.clear()
    else:
        _CACHE.pop(tenant_id, None)
        _CACHE_LOADED_AT.pop(tenant_id, None)
