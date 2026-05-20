"""Solva session status classifier — Chunk 13 (QA SV-04, 2026-05-21).

Computed-only status bucketing for the Solva sessions list view.
Spec source: `qa_reports/SOLVA_QA_BRIEF_20MAY2026.md#sv-04` —
verbatim 4-bucket definitions (ACTIVE / PAUSED / COMPLETE / REFUSED).

### Why computed, not stored

Phase D + v2 sessions already carry `status`, `layer_state`,
`created_at`, `updated_at`, `completed_at`. The 4-bucket UI status is
derivable from these fields without any new write — so we keep
migration cost zero across 84+ Phase D sessions + 541 orphan v2
sessions.

### 4-bucket rules

| Bucket    | Rule                                                  |
|-----------|-------------------------------------------------------|
| REFUSED   | raw_status in {"refused", "abandoned"}                |
| COMPLETE  | raw_status == "completed" OR layer_state == "done"    |
| PAUSED    | raw_status == "active" AND updated_at age >= 24h      |
| ACTIVE    | raw_status == "active" AND updated_at age < 24h       |

`abandoned → REFUSED` maps the operator-driven session-closure path
(see `routers/solva_phase_d.py:1334`) into the user-facing "refused"
bucket — both share the "session closed without synthesis acceptance"
semantics per the spec definitions table.

### Defensiveness

- `updated_at` may be a `datetime`, an ISO `str`, or missing entirely
  (orphan v2 sessions pre-WS-R16). When missing, we fall back to
  `started_at` / `created_at` and then to ACTIVE.
- A missing or unknown raw status defaults to ACTIVE — a session
  with no terminal marker is by definition still in-flight.

### Public API

- `classify(session_row: dict, *, now: datetime | None = None) -> str`
- `tally(rows: Iterable[dict], *, now: datetime | None = None) -> dict`
- `PAUSE_THRESHOLD_HOURS: int = 24`
- `DISPLAY_BUCKETS: tuple[str, ...] = ("active", "paused", "complete", "refused")`

Both helpers are pure (no DB calls, no I/O) — keeps unit testing
trivial and shields the classifier from schema drift in either
source collection.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

PAUSE_THRESHOLD_HOURS: int = 24
DISPLAY_BUCKETS: Tuple[str, ...] = ("active", "paused", "complete", "refused")


def _coerce_dt(value: Any) -> Optional[datetime]:
    """Best-effort coerce mixed timestamp shapes into an aware datetime.

    Tolerates:
      • naive datetime (assumes UTC)
      • aware datetime
      • ISO 8601 string (`2026-05-20T12:34:56Z` or `+00:00` variants)
      • missing / None / non-coerceable → returns None

    The list endpoint feeds rows from two collections with subtly
    different shapes, so this function is the single coercion seam.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        s = value.strip()
        # `Z` suffix isn't supported by stdlib fromisoformat pre-3.11
        # consistently — replace defensively.
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(s)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _last_activity(session: Dict[str, Any]) -> Optional[datetime]:
    """Pick the most recent activity timestamp available on a row.

    Order of preference:
      1. `updated_at` — written on every state mutation in both
         Phase D + v2 routers.
      2. `started_at` — present on legacy v2 sessions only.
      3. `created_at` — Phase D shape.

    Returns the first that coerces successfully.
    """
    for key in ("updated_at", "started_at", "created_at"):
        dt = _coerce_dt(session.get(key))
        if dt is not None:
            return dt
    return None


def classify(session: Dict[str, Any], *, now: Optional[datetime] = None) -> str:
    """Return the 4-bucket display status for a single session row.

    Returns one of `DISPLAY_BUCKETS`. Never raises — unknown shapes
    default to "active" so the listing keeps rendering even on drift.

    Args:
      session: dict-shaped row from `solva_phase_d_sessions` OR the
        mapped wire shape returned by `list_sessions`. Reads
        `status`, `layer_state`, plus the activity timestamps via
        `_last_activity`.
      now: optional override for the current time (used by tests
        to make pause-threshold assertions deterministic).
    """
    raw_status = (session.get("status") or "").strip().lower()
    layer_state = (session.get("layer_state") or session.get("layer") or "").strip().lower()

    if raw_status == "refused" or raw_status == "abandoned" or layer_state == "refused":
        return "refused"
    if raw_status == "completed" or layer_state == "done":
        return "complete"

    # Everything else → bucket on activity recency.
    last = _last_activity(session)
    if last is None:
        # No timestamp on the row → treat as ACTIVE; the spec defines
        # PAUSED as "a day or more has passed since the last
        # interaction" which we can't claim without a timestamp.
        return "active"
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    age_hours = (ref - last).total_seconds() / 3600.0
    if age_hours >= PAUSE_THRESHOLD_HOURS:
        return "paused"
    return "active"


def tally(rows: Iterable[Dict[str, Any]], *, now: Optional[datetime] = None) -> Dict[str, int]:
    """Return `{all, active, paused, complete, refused}` counts.

    Drives the Chunk-13 tab count badges on the Solva sessions list.
    Caller is responsible for filtering rows by search query (q)
    BEFORE passing them in — counts honour the q filter but NOT the
    status filter (same recipe as Chunk 11 `status_counts`).
    """
    counts = {bucket: 0 for bucket in DISPLAY_BUCKETS}
    counts["all"] = 0
    for row in rows:
        counts["all"] += 1
        bucket = classify(row, now=now)
        counts[bucket] = counts.get(bucket, 0) + 1
    return counts
