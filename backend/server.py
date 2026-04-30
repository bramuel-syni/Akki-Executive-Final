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
from typing import Any, Dict  # noqa: E402
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
from routers import shares as shares_router  # noqa: E402
from routers import sandbox as sandbox_router  # noqa: E402
from routers import cycle as cycle_router  # noqa: E402
from routers import blog as blog_router  # noqa: E402
from routers import billing as billing_router  # noqa: E402
from routers import plays as plays_router  # noqa: E402
from routers import agenda as agenda_router  # noqa: E402
from routers import document_engagement as document_engagement_router  # noqa: E402
from routers import monitor as monitor_router  # noqa: E402
from routers import strategic_goals as strategic_goals_router  # noqa: E402
from routers import chat as chat_router  # noqa: E402
from routers import influence_map as influence_map_router  # noqa: E402
from routers import admin_health as admin_health_router  # noqa: E402
from routers import admin_sandbox_kpi as admin_sandbox_kpi_router  # noqa: E402
from routers import signal_actions as signal_actions_router  # noqa: E402
from routers import admin_signal_kpi as admin_signal_kpi_router  # noqa: E402
from routers import prepare as prepare_router  # noqa: E402
from routers import inbound_email as inbound_email_router  # noqa: E402
from routers import inbound_queue as inbound_queue_router  # noqa: E402
from routers import enterprise as enterprise_router  # noqa: E402
from routers import llm_quota as llm_quota_router  # noqa: E402
from routers import admin_llm_spend as admin_llm_spend_router  # noqa: E402
from routers import decks as decks_router  # noqa: E402
from routers import solve as solve_router  # noqa: E402
from routers import walkin as walkin_router  # noqa: E402
from routers import admin_auth_events as admin_auth_events_router  # noqa: E402
from routers import solve_engine as solve_engine_router  # noqa: E402
from routers import studio as studio_router  # noqa: E402
from routers import product_features as product_features_router  # noqa: E402


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
app.include_router(shares_router.router)
app.include_router(sandbox_router.router)
app.include_router(cycle_router.router)
app.include_router(blog_router.router)
app.include_router(billing_router.router)
app.include_router(plays_router.router)
app.include_router(agenda_router.router)
app.include_router(document_engagement_router.router)
app.include_router(monitor_router.router)
app.include_router(strategic_goals_router.router)
app.include_router(chat_router.router)
app.include_router(influence_map_router.router)
app.include_router(admin_health_router.router)
app.include_router(admin_sandbox_kpi_router.router)
app.include_router(signal_actions_router.router)
app.include_router(admin_signal_kpi_router.router)
app.include_router(prepare_router.router)
app.include_router(inbound_email_router.router)
app.include_router(inbound_queue_router.router)
app.include_router(enterprise_router.router)
app.include_router(llm_quota_router.router)
app.include_router(admin_llm_spend_router.router)
app.include_router(decks_router.router)
app.include_router(solve_router.router)
app.include_router(walkin_router.router)
app.include_router(admin_auth_events_router.router)
app.include_router(solve_engine_router.router)
app.include_router(studio_router.router)
app.include_router(product_features_router.router)


# -----------------------------------------------------------------------------
# CORS — robust to operator misconfiguration. The two failure modes we've hit:
#   (a) CORS_ORIGINS unset → defaults to "*" → combined with allow_credentials
#       True, Starlette's CORSMiddleware can 400 the preflight (the spec
#       forbids `Access-Control-Allow-Origin: *` with credentials). Symptom on
#       the deployed app: `OPTIONS /api/auth/login → 400` and the browser
#       shows "Failed to fetch" on login.
#   (b) Operator forgot to add the deployed origin to CORS_ORIGINS — same
#       symptom.
# Fix: when wildcard is requested OR no explicit list is provided, fall back
# to `allow_origin_regex=".*"` which lets Starlette echo the actual origin
# back (compatible with credentials per spec). When an explicit list is
# given, prefer that for tighter security.
# -----------------------------------------------------------------------------
cors_origins_env = os.environ.get("CORS_ORIGINS", "").strip()
frontend_url = os.environ.get("FRONTEND_URL", "").strip()

explicit_origins: list[str] = []
wildcard_requested = False

if cors_origins_env:
    raw = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
    if "*" in raw or not raw:
        wildcard_requested = True
        # Keep any non-wildcard entries as a hint — they still get added.
        explicit_origins = [o for o in raw if o != "*"]
    else:
        explicit_origins = raw
else:
    # No CORS_ORIGINS set at all — be permissive so a fresh deploy doesn't
    # block login. Operator can tighten by setting CORS_ORIGINS later.
    wildcard_requested = True

if frontend_url and frontend_url not in explicit_origins:
    explicit_origins.append(frontend_url)

# Local dev origin should always be allowed regardless of env config.
for default in ("http://localhost:3000", "http://127.0.0.1:3000"):
    if default not in explicit_origins:
        explicit_origins.append(default)

cors_kwargs: Dict[str, Any] = {
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    "allow_headers": ["*"],
    "expose_headers": ["*"],
    "max_age": 600,
}
if wildcard_requested:
    # Regex form is credentials-compatible because Starlette echoes the
    # request's Origin into Access-Control-Allow-Origin instead of using "*".
    cors_kwargs["allow_origin_regex"] = ".*"
    cors_kwargs["allow_origins"] = explicit_origins  # also accept explicit
else:
    cors_kwargs["allow_origins"] = explicit_origins

app.add_middleware(CORSMiddleware, **cors_kwargs)
logger.info(
    "CORS configured: wildcard=%s, explicit_origins=%s",
    wildcard_requested, explicit_origins,
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
    await db.shares.create_index("id", unique=True)
    await db.shares.create_index([("shared_with_account_id", 1), ("created_at", -1)])
    await db.shares.create_index([("shared_by_account_id", 1), ("created_at", -1)])

    # Document engagement indexes
    await db.document_views.create_index(
        [("doc_id", 1), ("account_id", 1), ("day", 1)], unique=True,
    )
    await db.document_views.create_index([("doc_id", 1), ("viewed_at", -1)])
    await db.document_shares.create_index([("doc_id", 1), ("created_at", -1)])

    # Deep-tier (Opus) usage — unique key per (account, surface, day) is what
    # makes the race-safe quota path in llm_tier_quota.py actually safe.
    await db.llm_deep_usage.create_index(
        [("account_id", 1), ("surface", 1), ("day_utc", 1)], unique=True,
    )
    await db.llm_deep_usage.create_index([("day_utc", 1)])

    # Iter61 — auth observability. Sampled events for the
    # /admin/auth/events panel. Time-ordered queries are the only access
    # pattern, so a single descending index on `at` is enough.
    await db.auth_events.create_index([("at", -1)])

    # Iter61 — Solve sessions. Resume queries are scoped per account and
    # ordered by recency; admin views by cluster. Two indexes is enough.
    await db.solve_sessions.create_index([("account_id", 1), ("updated_at", -1)])
    await db.solve_sessions.create_index([("cluster_id", 1), ("started_at", -1)])
    await db.solve_clusters.create_index("id", unique=True)

    # Iter61 — seed the cluster taxonomy. Idempotent; operator edits in
    # Mongo survive redeploys.
    try:
        from solve_clusters_seed import seed_solve_clusters
        seed_result = await seed_solve_clusters(db)
        if seed_result["seeded_count"]:
            logger.info("Seeded %d Solve clusters: %s",
                        seed_result["seeded_count"], seed_result["ids"])
    except Exception as e:  # noqa: BLE001
        logger.warning("Solve cluster seeding skipped: %s", e)

    # Iter62 Wave 3 — curated comparables corpus for Triangulation v2.
    # Indexed on cluster_id + sector_tag so the engine can pick the closest
    # 2-3 anonymised diagnoses per Pro Synthesis call.
    await db.solve_comparables.create_index("id", unique=True)
    await db.solve_comparables.create_index([("cluster_id", 1), ("sector_tag", 1)])
    try:
        from solve_comparables_seed import seed_solve_comparables
        cmp_result = await seed_solve_comparables(db)
        if cmp_result["seeded_count"]:
            logger.info("Seeded %d Solve comparables: %s",
                        cmp_result["seeded_count"], cmp_result["ids"])
    except Exception as e:  # noqa: BLE001
        logger.warning("Solve comparables seeding skipped: %s", e)

    # Iter62 Wave 2 — Solve handoff artefacts created from completed sessions
    # (briefings, decks, cycle questions). One row per handoff; idempotent
    # within a session via natural key on (session_id, target).
    await db.solve_handoffs.create_index([("account_id", 1), ("created_at", -1)])
    await db.solve_handoffs.create_index([("session_id", 1), ("target", 1)])

    # Iter62 — monthly free-tier deep-synthesis grant for non-Pro users.
    # One row per (account_id, month_utc); the engine increments at first
    # use and decisions whether to allow further free deep calls.
    await db.solve_free_grants.create_index(
        [("account_id", 1), ("month_utc", 1)], unique=True
    )

    # Iter64 — Studio surface (Decks + Reports + Briefings unified).
    # Read-receipt tracking is keyed on (artefact_kind, artefact_id, account_id, day_utc).
    # Compound unique index gives idempotent dedup at the upsert site.
    await db.studio_views.create_index(
        [("artefact_kind", 1), ("artefact_id", 1), ("account_id", 1), ("day_utc", 1)],
        unique=True,
    )
    await db.studio_views.create_index([("context_id", 1), ("artefact_kind", 1)])
    await db.studio_shares.create_index([("artefact_kind", 1), ("artefact_id", 1)])
    await db.studio_shares.create_index([("context_id", 1), ("created_at", -1)])
    await db.decks.create_index([("context_id", 1), ("created_at", -1)])
    await db.briefings.create_index([("context_id", 1), ("status", 1), ("created_at", -1)])

    # Inbound-email idempotency
    await db.accounts.create_index("inbound_token", sparse=True)
    await db.contexts.create_index("inbound_token", sparse=True)

    # iter70 — inbound-queue triage (trust-tiered review)
    await db.inbound_queue.create_index("id", unique=True)
    await db.inbound_queue.create_index([("context_id", 1), ("status", 1), ("created_at", -1)])
    await db.inbound_queue.create_index(
        [("context_id", 1), ("inbound_message_id", 1)],
        sparse=True,
    )
    await db.inbound_queue_raw.create_index("queue_id", unique=True)

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

    # ── Tuesday 10am scheduler — auto-drafts the weekly Exco360 article.
    # In-process APScheduler. Single-replica deploys only; for HA, route
    # this to an external scheduled-trigger calling /api/blog/cron/weekly.
    cron_secret = os.environ.get("AKKI_CRON_SECRET")
    if cron_secret:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger
            import httpx

            async def _fire_weekly_cron():
                try:
                    async with httpx.AsyncClient(timeout=180.0) as ac:
                        resp = await ac.post(
                            "http://localhost:8001/api/blog/cron/weekly",
                            headers={"X-Cron-Secret": cron_secret},
                        )
                    logger.info("Weekly cron fired: status=%s body=%s",
                                resp.status_code, (resp.text or "")[:200])
                except Exception as e:  # noqa: BLE001
                    logger.warning("Weekly cron call failed: %s", e)

            scheduler = AsyncIOScheduler(timezone="UTC")
            # Tuesdays at 10:00 UTC. The user's market is East Africa
            # (UTC+3) — 10:00 UTC = 13:00 EAT. Adjust the timezone string
            # if a different reference is required.
            scheduler.add_job(
                _fire_weekly_cron,
                CronTrigger(day_of_week="tue", hour=10, minute=0),
                id="exco360_weekly",
                replace_existing=True,
            )

            # ── Monday 08:00 UTC — Influence Digest. Lands at the start
            # of the week so executives walk in knowing who read what.
            async def _fire_influence_digest():
                try:
                    async with httpx.AsyncClient(timeout=300.0) as ac:
                        resp = await ac.post(
                            "http://localhost:8001/api/cron/weekly-digest",
                            headers={"X-Cron-Secret": cron_secret},
                        )
                    logger.info("Influence digest cron: status=%s body=%s",
                                resp.status_code, (resp.text or "")[:200])
                except Exception as e:  # noqa: BLE001
                    logger.warning("Influence digest cron failed: %s", e)

            scheduler.add_job(
                _fire_influence_digest,
                CronTrigger(day_of_week="mon", hour=8, minute=0),
                id="influence_digest_weekly",
                replace_existing=True,
            )

            scheduler.start()
            app.state.scheduler = scheduler
            logger.info("Schedulers armed: Exco360 (Tue 10:00) + Influence Digest (Mon 08:00) UTC.")
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not arm weekly scheduler: %s", e)
    else:
        logger.info("AKKI_CRON_SECRET not set — weekly scheduler skipped.")


@app.on_event("shutdown")
async def on_shutdown():
    sched = getattr(app.state, "scheduler", None)
    if sched:
        sched.shutdown(wait=False)
    client.close()
