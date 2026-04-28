"""One-shot production bootstrap.

Run once on a fresh deploy to:
  1. Confirm MongoDB connectivity.
  2. Ensure all required indexes are present.
  3. Seed (or update) the superadmin account from ADMIN_EMAIL / ADMIN_PASSWORD.
  4. Print a sanity summary.

Idempotent — safe to re-run.

Usage:
  python3 /app/backend/scripts/bootstrap_prod.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure /app/backend is on path so we can import core / models.
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
import bcrypt  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
import uuid  # noqa: E402


REQUIRED_ENV = [
    "MONGO_URL", "DB_NAME",
    "JWT_SECRET", "ADMIN_EMAIL", "ADMIN_PASSWORD",
    "EMERGENT_LLM_KEY",
]


def _check_env() -> None:
    missing = [v for v in REQUIRED_ENV if not os.environ.get(v)]
    if missing:
        print(f"❌ Missing required env vars: {', '.join(missing)}")
        print("   Set them in the deployment dashboard and re-run.")
        sys.exit(2)


async def _ensure_indexes(db) -> dict:
    """Idempotently create every index AKKI relies on. Mirrors server.py
    on_startup() so a freshly-bootstrapped DB matches a long-running one."""
    created = []

    async def idx(coll: str, keys, **kwargs):
        try:
            name = await db[coll].create_index(keys, **kwargs)
            created.append(f"{coll}.{name}")
        except Exception as e:  # noqa: BLE001
            created.append(f"{coll}.<exists or error: {type(e).__name__}>")

    # Auth & accounts
    await idx("accounts", "email", unique=True)
    await idx("accounts", "inbound_token", sparse=True)
    await idx("contexts", "inbound_token", sparse=True)

    # Memberships
    await idx("memberships", [("account_id", 1), ("context_id", 1)], unique=True)
    await idx("memberships", [("context_id", 1), ("status", 1)])

    # Documents
    await idx("documents", [("context_id", 1), ("created_at", -1)])
    await idx("documents", [("context_id", 1), ("doc_type", 1)])
    await idx("documents", [("context_id", 1), ("inbound_message_id", 1)])

    # Audit
    await idx("audit_log", [("context_id", 1), ("created_at", -1)])
    await idx("audit_log", [("account_id", 1), ("created_at", -1)])

    # LLM deep tier — race-safe quota requires the unique index.
    await idx(
        "llm_deep_usage",
        [("account_id", 1), ("surface", 1), ("day_utc", 1)],
        unique=True,
    )
    await idx("llm_deep_usage", [("day_utc", 1)])

    # Decks telemetry
    await idx("deck_outlines", [("context_id", 1), ("created_at", -1)])
    await idx("decks", [("context_id", 1), ("created_at", -1)])
    await idx("deck_telemetry", [("created_at", -1)])

    # Cycle / questions
    await idx("questions", [("context_id", 1), ("source", 1), ("text", 1)])

    # Document views & shares
    await idx("document_views", [("doc_id", 1), ("viewed_at", -1)])
    await idx("document_shares", [("doc_id", 1), ("created_at", -1)])

    return {"created": created}


async def _seed_admin(db) -> dict:
    email = os.environ["ADMIN_EMAIL"].strip().lower()
    password = os.environ["ADMIN_PASSWORD"]
    pwd_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    nowiso = datetime.now(timezone.utc).isoformat()

    existing = await db.accounts.find_one(
        {"email": email}, {"_id": 0, "id": 1, "is_superadmin": 1}
    )
    if existing:
        # Idempotent: ensure superadmin flag + refresh password.
        await db.accounts.update_one(
            {"email": email},
            {"$set": {
                "password_hash": pwd_hash,
                "is_superadmin": True,
                "updated_at": nowiso,
            }},
        )
        return {"action": "updated", "id": existing["id"], "email": email}

    rec = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": "AKKI Admin",
        "password_hash": pwd_hash,
        "is_superadmin": True,
        "email_verified": True,
        "created_at": nowiso,
        "updated_at": nowiso,
    }
    await db.accounts.insert_one(rec)
    return {"action": "created", "id": rec["id"], "email": email}


async def _summary(db) -> dict:
    return {
        "accounts": await db.accounts.count_documents({}),
        "contexts": await db.contexts.count_documents({}),
        "documents": await db.documents.count_documents({}),
        "decks": await db.decks.count_documents({}),
        "llm_deep_usage_rows": await db.llm_deep_usage.count_documents({}),
    }


async def main() -> int:
    _check_env()
    print("→ Connecting to MongoDB…")
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    try:
        await db.command("ping")
    except Exception as e:  # noqa: BLE001
        print(f"❌ Mongo ping failed: {e}")
        return 3
    print(f"   OK · db='{os.environ['DB_NAME']}'")

    print("→ Ensuring indexes…")
    idx_result = await _ensure_indexes(db)
    print(f"   {len(idx_result['created'])} indexes ensured.")

    print("→ Seeding superadmin…")
    admin = await _seed_admin(db)
    print(f"   {admin['action']}: {admin['email']} (id {admin['id'][:8]}…)")

    print("→ Database summary:")
    summary = await _summary(db)
    for k, v in summary.items():
        print(f"   {k}: {v}")

    print()
    print("✅ Bootstrap complete. AKKI is ready to serve.")
    print()
    print("   Next:")
    print(f"     1. Sign in at <FRONTEND_URL> as {admin['email']}.")
    print("     2. Visit /admin to see the operator's home.")
    print("     3. Visit /admin/llm-spend to confirm telemetry is wired.")
    print("     4. (Optional) Wire the Postmark inbound URL in your Postmark dashboard.")
    return 0


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
