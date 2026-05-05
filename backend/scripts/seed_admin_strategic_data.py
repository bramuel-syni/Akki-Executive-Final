"""Phase L.2 — seed strategic-layer documents into the admin account.

Creates one demo context per pack organisation (Bank, Healthcare,
Logistics, Technology, Government) owned by `admin@akki.ai` and
ingests all 14 strategic documents through the Synisense pipeline +
studio_sensitivity ladder.

Idempotent. Safe to re-run. Existing docs (matched on context_id +
title + source="strategic_pack_v1") are skipped.

Usage:
    python3 backend/scripts/seed_admin_strategic_data.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

ADMIN_EMAIL = os.environ.get("AKKI_ADMIN_EMAIL", "admin@akki.ai")


def _fmt_kv(k: str, v) -> str:  # trivial printer
    return f"  {k:26} {v}"


async def main() -> int:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    # Make the core module see the same client (it initialises its own
    # via os.environ on module load — which is fine; both point at the
    # same DB).
    db = client[os.environ["DB_NAME"]]

    print("─" * 72)
    print(" Phase L.2 — seeding strategic documents into admin account")
    print("─" * 72)

    admin = await db.accounts.find_one({"email": ADMIN_EMAIL}, {"_id": 0})
    if admin is None:
        print(f"✗ admin account '{ADMIN_EMAIL}' not found — run /app/backend/server.py boot-seed first.")
        client.close()
        return 1
    print(_fmt_kv("admin account", f"{admin['email']} (id={admin['id']})"))

    # Late import so the env is loaded before the helper initialises
    # motor / services / Synisense pool.
    from scripts._strategic_ingest import ingest_strategic_documents

    summary = await ingest_strategic_documents(account=admin)

    print("─" * 72)
    print(" Per-org-type summary")
    print("─" * 72)
    for org_type, s in summary["by_org_type"].items():
        created = sum(1 for d in s["docs"] if d["action"] == "created")
        skipped = sum(1 for d in s["docs"] if d["action"] == "skipped")
        print(f"  {org_type:12}  ctx='{s['context_name']:50}' created={created} skipped={skipped}")

    # Totals
    print("─" * 72)
    print(_fmt_kv("contexts_created",   summary["contexts_created"]))
    print(_fmt_kv("contexts_existing",  summary["contexts_existing"]))
    print(_fmt_kv("docs_created",       summary["docs_created"]))
    print(_fmt_kv("docs_skipped",       summary["docs_skipped"]))

    # Sample Synisense replacements
    print("─" * 72)
    print(" Synisense sample replacements (proof that the pipeline ran)")
    print("─" * 72)
    if not summary["sample_replacements"]:
        print("  (no replacements produced on this run — re-ingest produced no new docs, or body had no spans)")
    else:
        for s in summary["sample_replacements"]:
            sp = s["span"]
            match = (sp.get("match_text") or "")[:40]
            replacement = (sp.get("replacement") or "")
            replacement = replacement[:40] if replacement else "[redacted via SYNI_*]"
            print(f"  [{s['org_type']:12}] {s['doc_title'][:50]:50} "
                  f"  {sp.get('entity_type','?'):12}  "
                  f"'{match}' → '{replacement}'")

    # Mongo cross-check
    n_ctx = await db.contexts.count_documents({"owner_account_id": admin["id"]})
    n_docs = await db.documents.count_documents({
        "context_id": {"$in": [c["id"] async for c in db.contexts.find(
            {"owner_account_id": admin["id"]}, {"_id": 0, "id": 1},
        )]},
        "source": "strategic_pack_v1",
    })
    print("─" * 72)
    print(_fmt_kv("admin.contexts (owned)", n_ctx))
    print(_fmt_kv("admin.documents (pack)", n_docs))
    print("─" * 72)
    print("✅ Seed complete.")

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
