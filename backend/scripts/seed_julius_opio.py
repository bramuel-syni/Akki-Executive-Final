"""Phase K.3 — seed Julius Opio tester account.

Creates a single dual-role superadmin account with one context of each
of the four types, plus a sponsoring org used by the sponsored seat,
plus the standard six-committee set on every context.

Idempotent. Safe to re-run. Re-running rotates Julius's password to the
canonical value below so credentials handed to the human are reliable.

Usage:
    python3 backend/scripts/seed_julius_opio.py

Logs created vs skipped at every step. Exits 0 on success.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from core import hash_password  # noqa: E402

# ─── canonical credentials (per Phase K.3 spec) ─────────────────────────
TARGET_EMAIL = "juliusaopio@gmail.com"
TARGET_NAME = "Julius Opio"
TARGET_PASSWORD = "Julius@Akki!2026-Exec"
TARGET_ROLE = "dual"
TARGET_PLAN = "enterprise"

# ─── canonical 6-committee set ──────────────────────────────────────────
DEFAULT_COMMITTEES = [
    {"id": "audit",        "name": "Audit Committee",        "your_role": "chair"},
    {"id": "risk",         "name": "Risk Committee",         "your_role": "member"},
    {"id": "nominations",  "name": "Nominations Committee",  "your_role": "member"},
    {"id": "remuneration", "name": "Remuneration Committee", "your_role": "member"},
    {"id": "esg",          "name": "ESG Committee",          "your_role": "member"},
    {"id": "strategy",     "name": "Strategy Committee",     "your_role": "member"},
]

# ─── 4 contexts (one per type) ──────────────────────────────────────────
# Phase L.3: added a 5th — "Julius Opio — Government Executive" — so
# every strategic-pack org_type (Bank / Healthcare / Logistics /
# Technology / Government) has a matching Julius context and the
# strategic mirror section below can ingest all 14 pack documents into
# Julius's tree.
CONTEXT_SPECS = [
    {
        "name": "Julius Opio — Personal NED Seat",
        "type": "ned_personal",
        "industry": "Banking",
        "jurisdiction": "Kenya",
        "sector": "Tier-1 banking · pre-IPO",
        "membership_role": "ned",
        "needs_sponsor": False,
        "strategic_org_type": "bank",
    },
    {
        "name": "Julius Opio — Sponsored NED Seat",
        "type": "ned_sponsored",
        "industry": "Healthcare",
        "jurisdiction": "Kenya",
        "sector": "Multi-site healthcare group",
        "membership_role": "ned",
        "needs_sponsor": True,
        "strategic_org_type": "healthcare",
    },
    {
        "name": "Julius Opio — Executive Role",
        "type": "executive_personal",
        "industry": "Logistics",
        "jurisdiction": "Kenya",
        "sector": "Pan-African logistics",
        "membership_role": "executive",
        "needs_sponsor": False,
        "strategic_org_type": "logistics",
    },
    {
        "name": "Julius Opio — Enterprise Executive",
        "type": "executive_enterprise",
        "industry": "Technology",
        "jurisdiction": "Kenya",
        "sector": "B2B SaaS · listed corporate",
        "membership_role": "executive",
        "needs_sponsor": True,
        "strategic_org_type": "technology",
    },
    {
        # Phase L.3 — gov-specific context type is out of scope per brief;
        # executive_personal keeps the data model consistent. The
        # 6-committee set is preserved on this context too (Strategy &
        # Audit are directly applicable; the rest are formally defined
        # but seldom convened in a ministerial context — kept for
        # consistency with the other four contexts).
        "name": "Julius Opio — Government Executive",
        "type": "executive_personal",
        "industry": "Public Sector",
        "jurisdiction": "Kenya",
        "sector": "Ministry · industrial modernisation",
        "membership_role": "executive",
        "needs_sponsor": False,
        "strategic_org_type": "government",
    },
]

# ─── throwaway sponsor org for the sponsored seats ──────────────────────
SPONSOR_ORG_NAME = "Acme Sponsor Org"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.isoformat()


async def upsert_account(db) -> tuple[dict, str]:
    """Create the Julius account if missing; rotate password if present.

    Returns (account_doc, action) where action ∈ {"created", "updated"}."""
    existing = await db.accounts.find_one({"email": TARGET_EMAIL}, {"_id": 0})
    pw_hash = hash_password(TARGET_PASSWORD)
    now = _iso(_now())

    if existing is None:
        account_id = str(uuid.uuid4())
        doc = {
            "id": account_id,
            "email": TARGET_EMAIL,
            "name": TARGET_NAME,
            "declared_role": TARGET_ROLE,
            "password_hash": pw_hash,
            "mfa_enabled": False,
            "mfa_secret": None,
            "default_context_id": None,
            "is_superadmin": True,
            "is_sandbox": False,
            "plan": TARGET_PLAN,
            "subscription_status": "active",
            "first_session": {"status": "skipped"},
            "created_at": now,
        }
        await db.accounts.insert_one(doc)
        doc.pop("_id", None)
        print(f"  ✚ Account created: {TARGET_EMAIL} (id={account_id})")
        return doc, "created"

    # Account exists — bring fields into canonical state and rotate password.
    update = {
        "name": TARGET_NAME,
        "declared_role": TARGET_ROLE,
        "password_hash": pw_hash,
        "is_superadmin": True,
        "is_sandbox": False,
        "plan": TARGET_PLAN,
        "subscription_status": "active",
        "first_session": existing.get("first_session") or {"status": "skipped"},
        "mfa_enabled": False,
    }
    if not existing.get("first_session", {}).get("status"):
        update["first_session"] = {"status": "skipped"}
    await db.accounts.update_one({"id": existing["id"]}, {"$set": update})
    refreshed = await db.accounts.find_one({"id": existing["id"]}, {"_id": 0})
    print(f"  ↺ Account exists — password rotated + flags reasserted: {TARGET_EMAIL} (id={existing['id']})")
    return refreshed, "updated"


async def upsert_sponsor_org(db) -> str:
    """Create the throwaway sponsoring org if absent. Returns its id."""
    existing = await db.organisations.find_one({"name": SPONSOR_ORG_NAME}, {"_id": 0})
    if existing:
        print(f"  ↺ Sponsor org exists: {SPONSOR_ORG_NAME} (id={existing['id']})")
        return existing["id"]
    org_id = str(uuid.uuid4())
    now = _iso(_now())
    await db.organisations.insert_one({
        "id": org_id,
        "name": SPONSOR_ORG_NAME,
        "kind": "sponsor",
        "status": "active",
        "created_at": now,
    })
    print(f"  ✚ Sponsor org created: {SPONSOR_ORG_NAME} (id={org_id})")
    return org_id


async def upsert_context(
    db, *, account_id: str, spec: dict, sponsor_org_id: str | None,
) -> tuple[dict, str]:
    existing = await db.contexts.find_one(
        {"owner_account_id": account_id, "name": spec["name"]},
        {"_id": 0},
    )
    if existing:
        # Reassert the full committee set + sponsor link in case earlier
        # runs were incomplete.
        update = {"committees": DEFAULT_COMMITTEES, "status": "active"}
        if spec["needs_sponsor"]:
            update["sponsoring_org_id"] = sponsor_org_id
        await db.contexts.update_one({"id": existing["id"]}, {"$set": update})
        print(f"  ↺ Context exists: {spec['name']} (id={existing['id']}) — committees + sponsor reasserted")
        existing.update(update)
        return existing, "updated"

    ctx_id = str(uuid.uuid4())
    now = _iso(_now())
    ctx = {
        "id": ctx_id,
        "name": spec["name"],
        "type": spec["type"],
        "industry": spec["industry"],
        "jurisdiction": spec["jurisdiction"],
        "sector": spec["sector"],
        "sponsoring_org_id": sponsor_org_id if spec["needs_sponsor"] else None,
        "owner_account_id": account_id,
        "status": "active",
        "progress_state": {
            "onboarding_step": 7,
            "onboarding_completed": True,
            "context_object_version": 1,
        },
        "committees": DEFAULT_COMMITTEES,
        "created_at": now,
    }
    await db.contexts.insert_one(ctx)
    ctx.pop("_id", None)
    print(f"  ✚ Context created: {spec['name']} (id={ctx_id}, type={spec['type']})")
    return ctx, "created"


async def upsert_membership(db, *, account_id: str, context_id: str, role: str) -> str:
    existing = await db.memberships.find_one(
        {"account_id": account_id, "context_id": context_id},
        {"_id": 0},
    )
    if existing:
        # Bring it into canonical state — owner / admin / active.
        await db.memberships.update_one(
            {"id": existing["id"]},
            {"$set": {
                "role": role,
                "sub_role": "admin",
                "provisioning": "personal",
                "data_ownership": "account",
                "status": "active",
            }},
        )
        print(f"    ↺ Membership exists: account={account_id[:8]}… ctx={context_id[:8]}…")
        return "updated"
    mid = str(uuid.uuid4())
    await db.memberships.insert_one({
        "id": mid,
        "account_id": account_id,
        "context_id": context_id,
        "role": role,
        "sub_role": "admin",
        "provisioning": "personal",
        "data_ownership": "account",
        "status": "active",
        "created_at": _iso(_now()),
    })
    print(f"    ✚ Membership created: id={mid} (role={role}/admin)")
    return "created"


async def main() -> int:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    print("─" * 64)
    print(" Phase K.3 — seeding Julius Opio tester account")
    print("─" * 64)

    # 1. Account
    print("[1/4] account")
    account, account_action = await upsert_account(db)

    # 2. Sponsor org (only one, used by the two sponsored contexts)
    print("[2/4] sponsor org")
    sponsor_org_id = await upsert_sponsor_org(db)

    # 3. Contexts + memberships
    print("[3/4] contexts + memberships")
    summary = []
    for spec in CONTEXT_SPECS:
        ctx, ctx_action = await upsert_context(
            db,
            account_id=account["id"],
            spec=spec,
            sponsor_org_id=sponsor_org_id,
        )
        m_action = await upsert_membership(
            db,
            account_id=account["id"],
            context_id=ctx["id"],
            role=spec["membership_role"],
        )
        summary.append((spec["name"], spec["type"], ctx_action, m_action))

    # 4. Default-context: pin the personal NED seat as the landing one
    print("[4/4] default context")
    personal_ned = next((c for c in summary if c[1] == "ned_personal"), None)
    if personal_ned:
        ctx_doc = await db.contexts.find_one(
            {"owner_account_id": account["id"], "type": "ned_personal"},
            {"_id": 0, "id": 1},
        )
        if ctx_doc and account.get("default_context_id") != ctx_doc["id"]:
            await db.accounts.update_one(
                {"id": account["id"]},
                {"$set": {"default_context_id": ctx_doc["id"]}},
            )
            print(f"  ↺ default_context_id → {ctx_doc['id']}  ({personal_ned[0]})")
        else:
            print(f"  ↺ default_context_id already correct ({personal_ned[0]})")

    # Counts
    n_contexts = await db.contexts.count_documents({"owner_account_id": account["id"]})
    n_memberships = await db.memberships.count_documents({"account_id": account["id"]})
    print("─" * 64)
    print(f"  account_action       = {account_action}")
    print(f"  contexts owned       = {n_contexts}")
    print(f"  memberships          = {n_memberships}")
    print(f"  is_superadmin        = {account['is_superadmin']}")
    print(f"  plan                 = {account['plan']}")
    print(f"  subscription_status  = {account['subscription_status']}")
    print(f"  declared_role        = {account['declared_role']}")
    print(f"  first_session.status = {account['first_session']['status']}")

    # ── Phase L.3 — strategic mirror ─────────────────────────────────
    # Ingest the full 14-doc Sandbox Strategic Documents Pack into
    # Julius's 5 contexts (the L.3 requirement). Idempotent — existing
    # rows skipped on re-run.
    print("─" * 64)
    print(" Phase L.3 — strategic mirror (14 docs across 5 contexts)")
    print("─" * 64)
    from scripts._strategic_ingest import ingest_strategic_documents

    # Map each pack org_type to Julius's corresponding context name so
    # the ingester writes into his existing tree rather than minting
    # fresh "<Org> · Demo" contexts.
    ctx_name_map = {
        spec["strategic_org_type"]: spec["name"]
        for spec in CONTEXT_SPECS
        if spec.get("strategic_org_type")
    }
    strat_summary = await ingest_strategic_documents(
        account=account,
        context_name_by_org_type=ctx_name_map,
    )
    for org_type, s in strat_summary["by_org_type"].items():
        created = sum(1 for d in s["docs"] if d["action"] == "created")
        skipped = sum(1 for d in s["docs"] if d["action"] == "skipped")
        print(f"  {org_type:12} → '{s['context_name'][:40]:40}' created={created} skipped={skipped}")
    print(f"  docs_created          = {strat_summary['docs_created']}")
    print(f"  docs_skipped          = {strat_summary['docs_skipped']}")
    if strat_summary["sample_replacements"]:
        first = strat_summary["sample_replacements"][0]
        sp = first["span"]
        print(f"  synisense sample      '{(sp.get('match_text') or '')[:40]}'  ({sp.get('entity_type')})")

    n_docs = await db.documents.count_documents({
        "source": "strategic_pack_v1",
        "uploaded_by": account["id"],
    })
    print(f"  julius.docs (pack)    = {n_docs}")

    print("─" * 64)
    print("✅ Seed complete. Credentials:")
    print(f"     email:    {TARGET_EMAIL}")
    print(f"     password: {TARGET_PASSWORD}")
    print("─" * 64)

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
