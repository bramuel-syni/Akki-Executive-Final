"""P5.11.1 — System-wide test pollution cleanup.

Purges synthetic test rows accumulated across multiple sprints from
production and dev Mongo:

  * `cohort_applications`        — rows where email matches test patterns
  * `cohort_magic_links`         — FK cascade off purged applications
  * `cohort_waitlist`            — rows where email matches test patterns
  * `admin_inbox_messages`       — rows where subject AND from match test patterns
  * `cohort_application_audit`   — rows tied to purged application_ids

Dry-run by default. Apply with `--apply`. Filter recency with
`--keep-after=2026-01-01T00:00:00Z` (purges only rows created on or
before that timestamp — protects legitimate recent traffic).

The script writes one audit row to `admin_cleanup_audit` per execution
with mode (dry_run / apply), counts, timestamp, actor=`cleanup_script`.

Usage:
  python3 scripts/cleanup_test_pollution.py                                 # dry run
  python3 scripts/cleanup_test_pollution.py --apply                         # actually delete
  python3 scripts/cleanup_test_pollution.py --apply --keep-after=2026-02-23T00:00:00Z
  python3 scripts/cleanup_test_pollution.py --mongo-url=mongodb://...       # custom DB
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

import pymongo  # noqa: E402


# ─── Pattern catalogue ────────────────────────────────────────────────
# Email patterns matched case-insensitively.
EMAIL_PATTERNS: List[re.Pattern] = [
    re.compile(r"@example\.com$", re.IGNORECASE),
    re.compile(r"@example\.org$", re.IGNORECASE),
    re.compile(r"@test\.[a-z]+$", re.IGNORECASE),
    re.compile(r"^m0c-.+@", re.IGNORECASE),
    re.compile(r"^mx-probe-.+@", re.IGNORECASE),  # leftover from this very phase
    re.compile(r"^r1-tester@", re.IGNORECASE),    # documented test account
    re.compile(r"^phasea-curl@", re.IGNORECASE),  # Phase A curl smoke account
    re.compile(r"@inbound\.akki\.syni\.ai$", re.IGNORECASE),  # leaked inbound aliases
]

# Subject patterns for admin_inbox_messages (must match AND the from_email
# must also match an EMAIL_PATTERN so we never purge a legitimate inbound
# that happens to have a test-shaped subject).
SUBJECT_PATTERNS: List[re.Pattern] = [
    re.compile(r"^\s*inbound test", re.IGNORECASE),
    re.compile(r"^\s*test\s+\d+\b", re.IGNORECASE),
    re.compile(r"^\s*test\s*$", re.IGNORECASE),
    re.compile(r"\bmx-probe\b", re.IGNORECASE),
    re.compile(r"^\s*\[test\]", re.IGNORECASE),
]


def _matches_any(value: str, patterns: List[re.Pattern]) -> bool:
    if not value:
        return False
    return any(p.search(value) for p in patterns)


def _email_is_test(email: str) -> bool:
    return _matches_any(email, EMAIL_PATTERNS)


def _subject_is_test(subject: str) -> bool:
    return _matches_any(subject, SUBJECT_PATTERNS)


# ─── DB ────────────────────────────────────────────────────────────────
def _connect(mongo_url: str, db_name: str):
    client = pymongo.MongoClient(mongo_url)
    return client[db_name]


def _parse_iso(s: str) -> datetime:
    """Parse a `YYYY-MM-DDTHH:MM:SSZ` ISO timestamp into an aware UTC datetime."""
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def _row_created_at(row: Dict[str, Any]) -> str:
    """Return the row's `created_at` as a string suitable for `<=` comparison.
    Mongo rows in this codebase store ISO 8601 strings (e.g.
    `2026-02-23T10:11:12.345678+00:00`)."""
    return str(row.get("created_at") or "")


# ─── Pass 1 — discover targets (dry-run-safe) ─────────────────────────
def discover(db, *, keep_after: datetime) -> Dict[str, Any]:
    """Returns a snapshot of what would be deleted. Pure reads."""
    cutoff_iso = keep_after.isoformat()

    # 1. cohort_applications — test emails.
    app_rows = list(db.cohort_applications.find(
        {"created_at": {"$lte": cutoff_iso}},
        {"_id": 0, "id": 1, "email": 1, "created_at": 1, "organisation": 1},
    ))
    apps_targeted = [r for r in app_rows if _email_is_test(r.get("email", ""))]
    app_ids = {r["id"] for r in apps_targeted if r.get("id")}

    # 2. cohort_magic_links — FK cascade.
    magic_rows = []
    if app_ids:
        magic_rows = list(db.cohort_magic_links.find(
            {"application_id": {"$in": list(app_ids)}},
            {"_id": 0, "id": 1, "application_id": 1, "email": 1},
        ))
    # Also direct-match by email pattern, in case some links have no
    # application_id (legacy seed data).
    extra_magic = list(db.cohort_magic_links.find(
        {"email": {"$regex": "@(example\\.com|example\\.org|test\\.[a-z]+)$",
                   "$options": "i"}},
        {"_id": 0, "id": 1, "email": 1},
    ))
    magic_ids = {r["id"] for r in magic_rows + extra_magic if r.get("id")}

    # 3. cohort_waitlist — test emails.
    wait_rows = list(db.cohort_waitlist.find(
        {"created_at": {"$lte": cutoff_iso}},
        {"_id": 0, "id": 1, "email": 1, "created_at": 1},
    ))
    wait_targeted = [r for r in wait_rows if _email_is_test(r.get("email", ""))]
    wait_ids = {r["id"] for r in wait_targeted if r.get("id")}

    # 4. admin_inbox_messages — test subjects AND test from_email.
    inbox_rows = list(db.admin_inbox_messages.find(
        {"received_at": {"$lte": cutoff_iso}},
        {"_id": 0, "id": 1, "subject": 1, "from_email": 1, "received_at": 1},
    ))
    inbox_targeted = [
        r for r in inbox_rows
        if _subject_is_test(r.get("subject", ""))
        and _email_is_test(r.get("from_email", ""))
    ]
    # Belt-and-braces: also catch rows where ONLY the from_email is a
    # known test alias (e.g. mx-probe-<uuid>@inbound.akki.syni.ai),
    # subject may be anything. Subject filter alone would NOT match;
    # we want this extra net.
    inbox_targeted_extra = [
        r for r in inbox_rows
        if r not in inbox_targeted
        and _email_is_test(r.get("from_email", ""))
    ]
    inbox_targeted_all = inbox_targeted + inbox_targeted_extra
    inbox_ids = {r["id"] for r in inbox_targeted_all if r.get("id")}

    # 5. cohort_application_audit — FK cascade off application_ids.
    audit_count = 0
    if app_ids:
        audit_count = db.cohort_application_audit.count_documents(
            {"application_id": {"$in": list(app_ids)}}
        )

    return {
        "cutoff_iso": cutoff_iso,
        "cohort_applications":      {"count": len(apps_targeted), "rows": apps_targeted},
        "cohort_magic_links":       {"count": len(magic_ids),     "rows": magic_rows + extra_magic},
        "cohort_waitlist":          {"count": len(wait_targeted), "rows": wait_targeted},
        "admin_inbox_messages":     {"count": len(inbox_targeted_all), "rows": inbox_targeted_all},
        "cohort_application_audit": {"count": audit_count,        "rows": []},  # FK only
        "_app_ids":   list(app_ids),
        "_magic_ids": list(magic_ids),
        "_wait_ids":  list(wait_ids),
        "_inbox_ids": list(inbox_ids),
    }


# ─── Pass 2 — apply deletes ──────────────────────────────────────────
def apply(db, snapshot: Dict[str, Any]) -> Dict[str, int]:
    """Execute the deletes. Returns actual delete counts."""
    counts: Dict[str, int] = {}

    if snapshot["_app_ids"]:
        r = db.cohort_applications.delete_many(
            {"id": {"$in": snapshot["_app_ids"]}}
        )
        counts["cohort_applications"] = int(r.deleted_count)
    else:
        counts["cohort_applications"] = 0

    if snapshot["_magic_ids"]:
        r = db.cohort_magic_links.delete_many(
            {"id": {"$in": snapshot["_magic_ids"]}}
        )
        counts["cohort_magic_links"] = int(r.deleted_count)
    else:
        counts["cohort_magic_links"] = 0

    if snapshot["_wait_ids"]:
        r = db.cohort_waitlist.delete_many(
            {"id": {"$in": snapshot["_wait_ids"]}}
        )
        counts["cohort_waitlist"] = int(r.deleted_count)
    else:
        counts["cohort_waitlist"] = 0

    if snapshot["_inbox_ids"]:
        r = db.admin_inbox_messages.delete_many(
            {"id": {"$in": snapshot["_inbox_ids"]}}
        )
        counts["admin_inbox_messages"] = int(r.deleted_count)
    else:
        counts["admin_inbox_messages"] = 0

    if snapshot["_app_ids"]:
        r = db.cohort_application_audit.delete_many(
            {"application_id": {"$in": snapshot["_app_ids"]}}
        )
        counts["cohort_application_audit"] = int(r.deleted_count)
    else:
        counts["cohort_application_audit"] = 0

    return counts


# ─── Audit row ────────────────────────────────────────────────────────
def write_audit(db, *, mode: str, snapshot: Dict[str, Any],
                counts: Dict[str, int], keep_after_iso: str) -> None:
    row = {
        "id": "cln-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "actor": "cleanup_script",
        "mode": mode,  # "dry_run" | "apply"
        "keep_after": keep_after_iso,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "targets": {
            "cohort_applications":      snapshot["cohort_applications"]["count"],
            "cohort_magic_links":       snapshot["cohort_magic_links"]["count"],
            "cohort_waitlist":          snapshot["cohort_waitlist"]["count"],
            "admin_inbox_messages":     snapshot["admin_inbox_messages"]["count"],
            "cohort_application_audit": snapshot["cohort_application_audit"]["count"],
        },
        "deleted": counts,
    }
    db.admin_cleanup_audit.insert_one(row)


# ─── CLI ──────────────────────────────────────────────────────────────
def main() -> int:
    p = argparse.ArgumentParser(description="P5.11.1 — test pollution cleanup")
    p.add_argument("--apply", action="store_true",
                   help="Execute deletes (otherwise: dry run).")
    p.add_argument("--keep-after", default=datetime.now(timezone.utc).isoformat(),
                   help="ISO timestamp; rows created strictly AFTER this are preserved. "
                        "Default: now (purge everything matched).")
    p.add_argument("--mongo-url", default=os.environ.get("MONGO_URL"),
                   help="Mongo URL (defaults to backend/.env).")
    p.add_argument("--db-name", default=os.environ.get("DB_NAME"),
                   help="Mongo DB name (defaults to backend/.env).")
    args = p.parse_args()

    if not args.mongo_url or not args.db_name:
        print("ERROR: MONGO_URL + DB_NAME must be set (env or flag).", file=sys.stderr)
        return 2

    try:
        cutoff = _parse_iso(args.keep_after)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: --keep-after must be ISO 8601. {e}", file=sys.stderr)
        return 2

    db = _connect(args.mongo_url, args.db_name)

    print(f"# cleanup_test_pollution.py")
    print(f"# mode:        {'APPLY (DESTRUCTIVE)' if args.apply else 'DRY-RUN (read-only)'}")
    print(f"# db_name:     {args.db_name}")
    print(f"# keep_after:  {cutoff.isoformat()}")
    print()

    snapshot = discover(db, keep_after=cutoff)

    # Headline summary.
    print("Targets matched:")
    for coll in (
        "cohort_applications",
        "cohort_magic_links",
        "cohort_waitlist",
        "admin_inbox_messages",
        "cohort_application_audit",
    ):
        print(f"  {coll:30s} {snapshot[coll]['count']:>6d} row(s)")
    print()

    # Sample rows (first 5 of each — helps the operator sanity-check).
    SAMPLE = 5
    for coll in ("cohort_applications", "cohort_waitlist"):
        rows = snapshot[coll]["rows"][:SAMPLE]
        if rows:
            print(f"Sample {coll}:")
            for r in rows:
                print(f"  - id={r.get('id', '?'):36s} email={r.get('email','?')}  created_at={r.get('created_at','?')}")
    rows = snapshot["admin_inbox_messages"]["rows"][:SAMPLE]
    if rows:
        print("Sample admin_inbox_messages:")
        for r in rows:
            print(f"  - id={r.get('id', '?'):36s} from={r.get('from_email','?')}  subject={(r.get('subject') or '')[:50]!r}")
    print()

    counts: Dict[str, int] = {k: 0 for k in (
        "cohort_applications", "cohort_magic_links", "cohort_waitlist",
        "admin_inbox_messages", "cohort_application_audit",
    )}

    if args.apply:
        counts = apply(db, snapshot)
        print("Deleted:")
        for coll, n in counts.items():
            print(f"  {coll:30s} {n:>6d} row(s)")
        print()
        write_audit(
            db, mode="apply", snapshot=snapshot,
            counts=counts, keep_after_iso=cutoff.isoformat(),
        )
        print("Audit row appended to `admin_cleanup_audit`.")
    else:
        write_audit(
            db, mode="dry_run", snapshot=snapshot,
            counts=counts, keep_after_iso=cutoff.isoformat(),
        )
        print("DRY-RUN complete. Re-run with --apply to actually delete.")
        print("Audit row (mode=dry_run) appended to `admin_cleanup_audit`.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
