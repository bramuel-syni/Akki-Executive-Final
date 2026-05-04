"""Phase 15.3.5 — reassign Ubora and Afya to NED contexts.

Idempotent. Re-running produces the same DB state.

Per locked Q3 from the human:
  * Ubora Capital Partners (aff5e102-04b8-4948-9f6b-27c9eca1f0d7)
       executive_enterprise → ned_personal   (NED owns the data)
  * Afya Sendwa Health Group (7369d67d-4687-4c4e-aa0a-0ab4590c3764)
       executive_enterprise → ned_sponsored  (sponsoring org owns)
  * Syni Industries (ec4db0c0-dea4-4ed6-81f2-da68994bfff2)
       UNCHANGED — stays executive_enterprise

Also flips admin's membership rows for the two reassigned contexts
to role='ned', sub_role='admin'. Writes a `context.role_changed`
audit-log entry per context so the change appears in the
governance export.

Run as:
    python -m backend.scripts.reassign_demo_contexts_15_3_5
or
    python backend/scripts/reassign_demo_contexts_15_3_5.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

# Make the parent backend/ importable when the script is run directly.
_THIS = os.path.abspath(os.path.dirname(__file__))
_BACKEND = os.path.abspath(os.path.join(_THIS, ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# Load .env so MONGO_URL is available when run from the CLI.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(os.path.join(_BACKEND, ".env"))
except Exception:  # noqa: BLE001
    pass

from core import db  # noqa: E402


REASSIGNMENTS = [
    {
        "context_id": "aff5e102-04b8-4948-9f6b-27c9eca1f0d7",
        "name": "Ubora Capital Partners",
        "new_type": "ned_personal",
    },
    {
        "context_id": "7369d67d-4687-4c4e-aa0a-0ab4590c3764",
        "name": "Afya Sendwa Health Group",
        "new_type": "ned_sponsored",
    },
]
SYNI_ID = "ec4db0c0-dea4-4ed6-81f2-da68994bfff2"  # unchanged — sanity check


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


async def _reassign_one(item):
    cid = item["context_id"]
    new_type = item["new_type"]
    name = item["name"]

    ctx = await db.contexts.find_one({"id": cid}, {"_id": 0, "id": 1, "type": 1, "name": 1})
    if not ctx:
        print(f"  [skip] {name} ({cid}): context not found")
        return False

    old_type = ctx.get("type")
    if old_type == new_type:
        print(f"  [noop] {name}: already type={new_type}")
        # Idempotent — still ensure memberships are role='ned'
        await db.memberships.update_many(
            {"context_id": cid},
            {"$set": {"role": "ned", "updated_at": _iso(datetime.now(timezone.utc))}},
        )
        return True

    # Apply the type change.
    await db.contexts.update_one(
        {"id": cid},
        {"$set": {
            "type": new_type,
            "updated_at": _iso(datetime.now(timezone.utc)),
        }},
    )
    # Flip every membership for this context to role='ned' (admin sub_role
    # preserved if already set; default to 'admin' for the workspace owner).
    membs = await db.memberships.find({"context_id": cid}).to_list(100)
    for m in membs:
        await db.memberships.update_one(
            {"id": m["id"]},
            {"$set": {
                "role": "ned",
                "sub_role": m.get("sub_role") or "admin",
                "updated_at": _iso(datetime.now(timezone.utc)),
            }},
        )
    # Audit row.
    await db.audit_log.insert_one({
        "id": f"role-{cid}-{int(datetime.now(timezone.utc).timestamp())}",
        "action": "context.role_changed",
        "context_id": cid,
        "context_name": name,
        "actor_email": "admin@akki.ai",
        "resource_type": "context",
        "resource_id": cid,
        "metadata": {"old_type": old_type, "new_type": new_type, "phase": "15.3.5"},
        "created_at": _iso(datetime.now(timezone.utc)),
    })
    print(f"  [done] {name}: {old_type} → {new_type}, {len(membs)} memberships re-roled to ned")
    return True


async def main():
    print("Phase 15.3.5 — context-type reassignment (idempotent)")
    for item in REASSIGNMENTS:
        await _reassign_one(item)

    # Sanity-check Syni stays executive_enterprise.
    syni = await db.contexts.find_one({"id": SYNI_ID}, {"_id": 0, "type": 1, "name": 1})
    if syni:
        print(f"  [sanity] Syni Industries.type = {syni.get('type')!r} (expected executive_enterprise)")

    print("done.")


if __name__ == "__main__":
    asyncio.run(main())
