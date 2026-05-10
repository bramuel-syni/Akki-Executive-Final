#!/usr/bin/env python3
"""Backfill `db.chats.context_id` for orphaned rows.

Why this exists
---------------
Workstream A.1 of the UAT pack made the frontend pass `context_id` on
chat creation. Before that fix, three call sites in `Chat.jsx` minted
chats without it, so the active-context filter at `GET /api/chats`
filtered them out and the user perceived their conversations as
"disappearing between sessions" (AC-01).

What this script does
---------------------
For every `db.chats` row where `context_id` is missing or empty:
  1. Look up the owning account.
  2. Resolve the most likely context, in this priority order:
       a. The account's `default_context_id` if it had one at the time
          of the chat's `created_at` (today we use the current value;
          historical default is not tracked, so this is best-effort).
       b. If the account has had only one membership ever, use that
          membership's `context_id`.
       c. Otherwise, leave the chat orphaned and log it for manual
          review (`unresolved`).
  3. Update the row with the resolved context_id and add a marker
     `backfilled_context_at` ISO timestamp so subsequent re-runs are
     idempotent.

Usage
-----
  # Dry run (default) — prints counts + sample rows, no writes.
  python backend/scripts/backfill_chat_context.py

  # Apply.
  python backend/scripts/backfill_chat_context.py --apply

  # Apply, but only for a single account (debugging).
  python backend/scripts/backfill_chat_context.py --apply --account <id>

Everything is logged to stdout in machine-readable JSONL when --apply
is set, so you can pipe it to a file for the audit trail.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend/ is importable regardless of where the script is invoked.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from core import db  # noqa: E402


async def resolve_context_for_account(account_id: str) -> tuple[str | None, str]:
    """Return (context_id_or_None, basis_string)."""
    account = await db.accounts.find_one({"id": account_id}, {"_id": 0, "default_context_id": 1})
    if account and account.get("default_context_id"):
        return account["default_context_id"], "default_context_id"

    memberships = await db.memberships.find(
        {"account_id": account_id, "status": "active"},
        {"_id": 0, "context_id": 1},
    ).to_list(10)
    if len(memberships) == 1:
        return memberships[0]["context_id"], "single_membership"

    if len(memberships) > 1:
        return None, f"ambiguous_{len(memberships)}_memberships"

    return None, "no_memberships"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Write the changes. Default is dry-run.")
    parser.add_argument("--account", default=None,
                        help="Limit to one account_id for debugging.")
    args = parser.parse_args()

    query = {"$or": [{"context_id": None}, {"context_id": ""}, {"context_id": {"$exists": False}}]}
    if args.account:
        query = {"$and": [query, {"account_id": args.account}]}

    total_before = await db.chats.count_documents(query)
    print(f"orphan_count_before={total_before}")

    if total_before == 0:
        print("nothing_to_do")
        return 0

    sample_cursor = db.chats.find(query, {"_id": 0, "id": 1, "account_id": 1, "title": 1, "created_at": 1}).limit(5)
    samples = await sample_cursor.to_list(5)
    print("sample_rows:")
    for s in samples:
        print(f"  {s['id']} acct={s['account_id'][:8]}.. title={s.get('title', '')[:40]!r} created_at={s.get('created_at')}")

    if not args.apply:
        print("dry_run=true\u2014pass --apply to write")
        return 0

    fixed = 0
    unresolved = 0
    backfilled_at = datetime.now(timezone.utc).isoformat()

    cursor = db.chats.find(query, {"_id": 0, "id": 1, "account_id": 1})
    async for row in cursor:
        ctx_id, basis = await resolve_context_for_account(row["account_id"])
        if not ctx_id:
            unresolved += 1
            print(json.dumps({
                "event": "unresolved",
                "chat_id": row["id"],
                "account_id": row["account_id"],
                "basis": basis,
            }))
            continue
        await db.chats.update_one(
            {"id": row["id"]},
            {"$set": {
                "context_id": ctx_id,
                "backfilled_context_at": backfilled_at,
                "backfilled_context_basis": basis,
            }},
        )
        fixed += 1
        print(json.dumps({
            "event": "backfilled",
            "chat_id": row["id"],
            "account_id": row["account_id"],
            "context_id": ctx_id,
            "basis": basis,
        }))

    total_after = await db.chats.count_documents(query)
    print(f"backfilled={fixed}")
    print(f"unresolved={unresolved}")
    print(f"orphan_count_after={total_after}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
