"""Phase P5.15 — User Ideas preferences CRUD.

Mongo collection: `user_ideas_preferences` keyed by
(account_id, user_id). In this codebase account.id IS the
user_id, so the composite is effectively unique on account_id
alone — but we keep the dual field for forward compatibility
with future multi-user-per-account models.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .schema import IDEA_LENSES, IdeaLens, UserIdeasPreferences

DEFAULT_PREFERENCES_LENSES: List[IdeaLens] = list(IDEA_LENSES)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_or_default_preferences(
    db, *, account_id: str, user_id: str,
) -> UserIdeasPreferences:
    row = await db.user_ideas_preferences.find_one(
        {"account_id": account_id, "user_id": user_id},
        {"_id": 0},
    )
    if not row:
        return UserIdeasPreferences(
            account_id=account_id,
            user_id=user_id,
            custom_instructions="",
            lenses_enabled=DEFAULT_PREFERENCES_LENSES,
        )
    # Validate the persisted row — defensive against schema drift.
    return UserIdeasPreferences.model_validate(row)


async def upsert_preferences(
    db, *,
    account_id: str,
    user_id: str,
    custom_instructions: str,
    lenses_enabled: List[str],
) -> UserIdeasPreferences:
    # Coerce to the valid lens literal subset; ignore unknowns silently.
    valid = [lens for lens in lenses_enabled if lens in IDEA_LENSES]
    if not valid:
        # Empty / all-invalid input is treated as "all enabled" so the
        # user never lands in a state where the digest is silently empty
        # because of a malformed preference write.
        valid = list(IDEA_LENSES)
    prefs = UserIdeasPreferences(
        account_id=account_id,
        user_id=user_id,
        custom_instructions=(custom_instructions or "")[:2000],
        lenses_enabled=valid,
        updated_at=_now_iso(),
    )
    await db.user_ideas_preferences.update_one(
        {"account_id": account_id, "user_id": user_id},
        {"$set": prefs.model_dump()},
        upsert=True,
    )
    return prefs


__all__ = [
    "DEFAULT_PREFERENCES_LENSES",
    "get_or_default_preferences",
    "upsert_preferences",
]
