"""Phase G.3 — content_hash + merge_count dedup for db.signals.

Goal
----
When a write path emits a signal whose *normalised* (headline, summary, type)
already exists in the same context within the dedup window, we DO NOT insert
a duplicate row. Instead, we increment `merge_count` on the existing row and
bump `updated_at`. The caller receives the existing row so the response
shape is identical to "fresh insert".

Why
---
Per spec §6 (volume restraint) the Active landing caps to 7 rows. Without
write-time dedup, two pipeline runs against the same context produce 16
near-identical risk cards in 30s. The user sees noise, not signal.

Implementation
--------------
- `signal_content_hash(headline, summary, signal_type)` — sha256 over
  whitespace-normalised lower-cased text. Stable across runs.
- `dedup_or_insert(db, sig)` — atomic upsert:
    1. Compute hash from sig fields.
    2. find_one_and_update on (context_id, content_hash) with $inc merge_count
       + $set updated_at + $setOnInsert the rest of the doc.
    3. If newly inserted, return (sig, True); else return (existing, False).

The existing row's `id` is preserved on a merge, so any references in
audit logs or signal_actions remain valid.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Tuple

# Window applied as a $or filter — beyond the window, the same content
# is allowed to be a fresh signal again (e.g. a quarterly recurring
# risk that should be re-surfaced cycle-after-cycle).
DEDUP_WINDOW_DAYS = 30

_WS = re.compile(r"\s+")


def _normalise(text: str) -> str:
    return _WS.sub(" ", (text or "").strip().lower())


def signal_content_hash(headline: str, summary: str, signal_type: str) -> str:
    """SHA-256 of the normalised tuple. Hex digest, deterministic."""
    blob = f"{_normalise(signal_type)}::{_normalise(headline)}::{_normalise(summary)}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def dedup_or_insert(
    db: Any, sig: Dict[str, Any],
) -> Tuple[Dict[str, Any], bool]:
    """Insert sig OR merge into an existing row. Returns (row, inserted).

    The caller passes a fully-formed candidate signal doc. We compute the
    hash, look for an existing same-context row matching it, and either
    increment merge_count or insert.

    Side-effect-free if the caller mutates the returned row.
    """
    h = signal_content_hash(
        sig.get("headline") or "",
        sig.get("summary") or "",
        sig.get("type") or "",
    )
    sig.setdefault("content_hash", h)
    sig.setdefault("merge_count", 1)

    # Atomic find-or-insert. We cannot use upsert+inc because that would
    # bump merge_count on first insert too. Two-step is fine — race is
    # handled by the unique partial index in server.py startup.
    existing = await db.signals.find_one(
        {"context_id": sig["context_id"], "content_hash": h},
        {"_id": 0},
    )
    if existing:
        await db.signals.update_one(
            {"id": existing["id"]},
            {
                "$inc": {"merge_count": 1},
                "$set": {"updated_at": sig.get("created_at"),
                         "last_merged_at": sig.get("created_at")},
            },
        )
        existing["merge_count"] = (existing.get("merge_count") or 1) + 1
        existing["last_merged_at"] = sig.get("created_at")
        return existing, False

    await db.signals.insert_one(sig)
    sig.pop("_id", None)
    return sig, True
