"""AKKI Sandbox — thin assembler.

All domain endpoints now live in /app/backend/routers/*.  This module is
responsible for:
  - FastAPI app bootstrap + CORS middleware
  - Startup: Mongo indexes, committee-id backfill, admin seed
  - Shutdown: Mongo client close
  - Router wiring
"""
from __future__ import annotations

from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import logging  # noqa: E402
import os  # noqa: E402
import uuid  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

from core import (  # noqa: E402
    db, client, iso as _iso, now as _now,
    hash_password, verify_password,
    provision_default_context, write_audit,
    APP_NAME,
)

# Routers (import as modules to keep the .include_router calls readable)
from routers import auth as auth_router  # noqa: E402
from routers import contexts as contexts_router  # noqa: E402
from routers import documents as documents_router  # noqa: E402
from routers import misc as misc_router  # noqa: E402
from routers import briefings as briefings_router  # noqa: E402
from routers import learn as learn_router  # noqa: E402
from routers import committees as committees_router  # noqa: E402
from routers import simulate as simulate_router  # noqa: E402
from routers import comments as comments_router  # noqa: E402
from routers import signals_ask as signals_ask_router  # noqa: E402
from routers import lens as lens_router  # noqa: E402
from routers import pipeline as pipeline_router  # noqa: E402
from routers import audit as audit_router  # noqa: E402
from routers import synisense as synisense_router  # noqa: E402


logger = logging.getLogger("akki")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


# -----------------------------------------------------------------------------
# App bootstrap
# -----------------------------------------------------------------------------
app = FastAPI(title=APP_NAME)

# Register routers (all share /api prefix internally)
app.include_router(auth_router.router)
app.include_router(contexts_router.router)
app.include_router(documents_router.router)
app.include_router(misc_router.router)
app.include_router(briefings_router.router)
app.include_router(learn_router.router)
app.include_router(committees_router.router)
app.include_router(simulate_router.router)
app.include_router(comments_router.router)
app.include_router(signals_ask_router.router)
app.include_router(lens_router.router)
app.include_router(pipeline_router.router)
app.include_router(audit_router.router)
app.include_router(synisense_router.router)


# -----------------------------------------------------------------------------
# CORS
# -----------------------------------------------------------------------------
cors_origins_env = os.environ.get("CORS_ORIGINS", "*")
frontend_url = os.environ.get("FRONTEND_URL", "").strip()
if cors_origins_env.strip() == "*" and frontend_url:
    allow_origins = [frontend_url, "http://localhost:3000"]
else:
    allow_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
    if frontend_url and frontend_url not in allow_origins:
        allow_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Startup / shutdown
# -----------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    await db.accounts.create_index("email", unique=True)
    await db.accounts.create_index("id", unique=True)
    await db.contexts.create_index("id", unique=True)
    await db.contexts.create_index("owner_account_id")
    await db.memberships.create_index([("context_id", 1), ("account_id", 1)])
    await db.memberships.create_index("account_id")
    await db.invitations.create_index("token", unique=True)
    await db.invitations.create_index([("context_id", 1), ("email", 1)])
    await db.audit_log.create_index([("context_id", 1), ("created_at", -1)])
    await db.telemetry_events.create_index([("context_id", 1), ("occurred_at", -1)])
    await db.login_attempts.create_index("identifier")
    await db.consent_decisions.create_index([("account_id", 1), ("context_id", 1)])
    await db.organisations.create_index("id", unique=True)
    await db.documents.create_index([("context_id", 1), ("created_at", -1)])
    await db.documents.create_index("id", unique=True)
    await db.signals.create_index([("context_id", 1), ("created_at", -1)])
    await db.signals.create_index("id", unique=True)
    await db.ask_messages.create_index([("context_id", 1), ("created_at", -1)])

    # Backfill: ensure every committee on every context has a stable id.
    async for c in db.contexts.find(
        {"committees": {"$exists": True, "$ne": []}},
        {"_id": 0, "id": 1, "committees": 1},
    ):
        committees = c.get("committees") or []
        mutated = False
        for cm in committees:
            if not cm.get("id"):
                slug = "".join(
                    ch if ch.isalnum() else "-" for ch in (cm.get("name") or "").lower()
                ).strip("-")
                cm["id"] = slug or f"committee-{uuid.uuid4().hex[:6]}"
                mutated = True
        if mutated:
            await db.contexts.update_one({"id": c["id"]}, {"$set": {"committees": committees}})

    # Admin seed
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@akki.ai").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "AkkiAdmin2026!")
    existing = await db.accounts.find_one({"email": admin_email}, {"_id": 0})
    if not existing:
        admin_id = str(uuid.uuid4())
        created_at = _iso(_now())
        admin_doc = {
            "id": admin_id,
            "email": admin_email,
            "name": "AKKI Admin",
            "declared_role": "dual",
            "password_hash": hash_password(admin_password),
            "mfa_enabled": False,
            "mfa_secret": None,
            "default_context_id": None,
            "created_at": created_at,
            "is_superadmin": True,
        }
        await db.accounts.insert_one(admin_doc)
        await provision_default_context(admin_doc, "Syni.ai HQ")
        logger.info(f"Seeded admin account {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.accounts.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}},
        )
        logger.info("Admin password rotated from .env")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
