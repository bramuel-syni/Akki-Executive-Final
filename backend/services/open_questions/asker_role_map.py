"""Phase I.5 — Asker-role taxonomy for Open Questions Card 4 (2026-05-27).

Maps a question's `asked_by_account_id` (within a given context) to one
of 3 buckets that drive the CompanyHome Card 4 subtext:

  "X from board · Y from CEO · Z from team"

Derivation source is `db.memberships(account_id, context_id)`.role —
the canonical context-scoped role truth source. (Cross-check at I.5
brief established that `cycles.team[]` does not exist in live data —
escalation E1 decided 2026-05-27.)

Mapping (E1=a, locked 2026-05-27):

  memberships.role        → bucket
  ─────────────────────────────────
  "ned"                   → "board"
  "owner"                 → "board"   (owners are NED chairs in this app)
  "executive"             → "ceo"
  <missing membership>    → "team"    (conservative default)
  <future role not listed> → "team"   (forward-compat: never assume)

Module is pure-mapping + 1 thin DB lookup helper for unit-testability —
no FastAPI imports, no router-level concerns.
"""
from __future__ import annotations

from typing import Optional

from core import db


# Asker-role bucket constants (single source of truth for tests +
# downstream consumers).
ASKER_ROLE_BOARD = "board"
ASKER_ROLE_CEO   = "ceo"
ASKER_ROLE_TEAM  = "team"

ASKER_ROLE_BUCKETS = (ASKER_ROLE_BOARD, ASKER_ROLE_CEO, ASKER_ROLE_TEAM)


# memberships.role → bucket lookup. Anything NOT in this dict falls
# through to ASKER_ROLE_TEAM (the conservative default).
_ROLE_TO_BUCKET = {
    "ned":       ASKER_ROLE_BOARD,
    "owner":     ASKER_ROLE_BOARD,
    "executive": ASKER_ROLE_CEO,
}


def map_membership_role_to_bucket(role: Optional[str]) -> str:
    """Pure mapper — no DB hit. Used directly for unit tests."""
    if not role or not isinstance(role, str):
        return ASKER_ROLE_TEAM
    return _ROLE_TO_BUCKET.get(role.strip().lower(), ASKER_ROLE_TEAM)


async def derive_asker_role(
    account_id: Optional[str],
    context_id: str,
) -> str:
    """Look up the asker's role in the context's memberships and map
    to the 3-bucket taxonomy.

    Behavior:
      • `account_id` is None / empty → 'team' (default; per E2 backfill
        convention).
      • No membership row for `(account_id, context_id)` → 'team'.
      • Membership found but `role` is in `_ROLE_TO_BUCKET` → mapped bucket.
      • Membership found but `role` is unknown → 'team' (forward-compat).

    NEVER raises. The Card 4 surface must keep rendering even if the
    role-lookup fails for any reason.
    """
    if not account_id:
        return ASKER_ROLE_TEAM
    try:
        m = await db.memberships.find_one(
            {"account_id": account_id, "context_id": context_id},
            {"_id": 0, "role": 1},
        )
    except Exception:
        return ASKER_ROLE_TEAM
    if not m:
        return ASKER_ROLE_TEAM
    return map_membership_role_to_bucket(m.get("role"))


def format_decomposition_subtext(decomposition: dict) -> str:
    """Render the Card 4 subtext string from the bucket-count dict.

    Empty / all-zero  → 'Nothing open.'
    Otherwise         → join non-zero segments with ' · ':
        '1 from board · 2 from CEO · 4 from team'
        (zero segments are omitted; e.g. '3 from CEO · 1 from team')

    The bucket order is locked: board → CEO → team. Renamed label
    casing ('from CEO' not 'from ceo') matches the brief spec.
    """
    if not isinstance(decomposition, dict):
        return "Nothing open."
    board = int(decomposition.get(ASKER_ROLE_BOARD) or 0)
    ceo   = int(decomposition.get(ASKER_ROLE_CEO)   or 0)
    team  = int(decomposition.get(ASKER_ROLE_TEAM)  or 0)
    if board == 0 and ceo == 0 and team == 0:
        return "Nothing open."
    segments = []
    if board: segments.append(f"{board} from board")
    if ceo:   segments.append(f"{ceo} from CEO")
    if team:  segments.append(f"{team} from team")
    return " · ".join(segments)
