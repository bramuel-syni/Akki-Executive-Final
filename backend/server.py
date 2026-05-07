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
from routers import work_studio_export as work_studio_export_router  # noqa: E402
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
from routers import pulse as pulse_router  # noqa: E402
from routers import admin_signal_kpi as admin_signal_kpi_router  # noqa: E402
from routers import prepare as prepare_router  # noqa: E402
from routers import inbound_email as inbound_email_router  # noqa: E402
from routers import inbound_queue as inbound_queue_router  # noqa: E402
from routers import enterprise as enterprise_router  # noqa: E402
from routers import llm_quota as llm_quota_router  # noqa: E402
from routers import admin_llm_spend as admin_llm_spend_router  # noqa: E402
from routers import decks as decks_router  # noqa: E402
# M.4: solva v1 (routers/solva.py interest stub + routers/solva_engine.py
# forensic GETs) deleted. Solva v2 is the only Solva surface now.
from routers import walkin as walkin_router  # noqa: E402
from routers import admin_auth_events as admin_auth_events_router  # noqa: E402
from routers import admin_journal as admin_journal_router  # noqa: E402
from routers import active_context as active_context_router  # noqa: E402  Phase A — Roles & Company Navigation
from routers import studio as studio_router  # noqa: E402
from routers import studio_blocks as studio_blocks_router  # noqa: E402
from routers import product_features as product_features_router  # noqa: E402
from routers import early_access as early_access_router  # noqa: E402
from routers import cycle_config as cycle_config_router  # noqa: E402
from routers import daily_review as daily_review_router  # noqa: E402
from routers import first_session as first_session_router  # noqa: E402
from routers import depth as depth_router  # noqa: E402
from routers import governance as governance_router  # noqa: E402
from routers import solva_v2 as solva_v2_router  # noqa: E402  Phase 15.0 — Solva v2 POC (feature-flagged)


logger = logging.getLogger("akki")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


# -----------------------------------------------------------------------------
# App bootstrap
# -----------------------------------------------------------------------------
# M.4 #10 — FastAPI introspection mounted under /api so the K8s ingress
# (which only forwards /api/* to backend:8001) can serve them. Production
# disables redoc but keeps /api/docs + /api/openapi.json reachable.
app = FastAPI(
    title=APP_NAME,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

# Register routers (all share /api prefix internally)
app.include_router(auth_router.router)
app.include_router(contexts_router.router)
app.include_router(documents_router.router)
app.include_router(misc_router.router)
app.include_router(briefings_router.router)
app.include_router(work_studio_export_router.router)
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
app.include_router(pulse_router.router)
app.include_router(admin_signal_kpi_router.router)
app.include_router(prepare_router.router)
app.include_router(inbound_email_router.router)
app.include_router(inbound_queue_router.router)
app.include_router(enterprise_router.router)
app.include_router(llm_quota_router.router)
app.include_router(admin_llm_spend_router.router)
app.include_router(decks_router.router)
# M.4: solva_router + solva_engine_router include_router calls removed.
app.include_router(walkin_router.router)
app.include_router(admin_auth_events_router.router)
app.include_router(admin_journal_router.router)
app.include_router(active_context_router.router)
app.include_router(studio_router.router)
app.include_router(studio_blocks_router.router)
app.include_router(product_features_router.router)
app.include_router(early_access_router.router)
app.include_router(cycle_config_router.router)
app.include_router(daily_review_router.router)
app.include_router(first_session_router.router)
app.include_router(depth_router.router)
app.include_router(governance_router.router)

# Solva v2 — production reasoning surface. Open to every authenticated
# account. Registered AFTER all v1 routers so nothing is shadowed.
app.include_router(solva_v2_router.router)


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
    # ─── Phase 10 boot-level guards ─────────────────────────────────────
    billing_enabled = (os.environ.get("BILLING_ENABLED") or "").lower() in ("1", "true", "yes")
    if billing_enabled and not (os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")):
        # Fail loud and fail at boot — a half-configured billing surface
        # is worse than a disabled one. The operator flips BILLING_ENABLED
        # to false or supplies STRIPE_SECRET_KEY.
        raise RuntimeError(
            "BILLING_ENABLED=true but STRIPE_SECRET_KEY is unset. "
            "Set STRIPE_SECRET_KEY or disable billing before boot."
        )
    # Stripe webhook idempotency + dead-letter indexes (additive).
    try:
        from services.stripe_webhook import ensure_indexes as _stripe_ensure
        await _stripe_ensure(db)
    except Exception as e:  # noqa: BLE001
        import logging as _lg
        _lg.getLogger("akki.startup").warning("stripe idempotency indexes: %s", e)

    # ─── Phase 12.1 Synisense boot guard ────────────────────────────────
    # Master key required in production. Dev escape hatch:
    # SYNISENSE_ALLOW_INSECURE=true falls back to a constant key with a
    # 60-second stderr warning loop. Production is detected as
    # BILLING_ENABLED=true OR AKKI_ENV=production.
    try:
        from services.synisense.encryption import init_keys as _syn_init, is_insecure_fallback
        _syn_init()
        if is_insecure_fallback():
            # Arm the periodic warning loop so the noise stays loud.
            import asyncio as _asyncio
            import logging as _lg

            async def _syn_nag_loop():
                _log = _lg.getLogger("akki.synisense")
                while True:
                    _log.warning(
                        "SYNISENSE running with INSECURE dev fallback key. "
                        "Set SYNISENSE_MASTER_KEY before production boot."
                    )
                    await _asyncio.sleep(60)
            _asyncio.create_task(_syn_nag_loop())

        # Phase 12.2 — warm the spaCy model at boot so first-request
        # latency is close to the warm p50 (~7ms) rather than the
        # cold load (~2s). We run the warmup in a thread so the boot
        # path doesn't block on the model load. Logs `synisense
        # warmup ready event=ready surface=boot elapsed_ms=N` when
        # done.
        import asyncio as _asyncio
        import logging as _lg
        import time as _time

        async def _syn_warmup():
            _log = _lg.getLogger("akki.synisense")
            t0 = _time.monotonic()
            try:
                from services.synisense import presidio_engine as _pe
                # Run model load in a thread \u2014 it's CPU-bound and
                # blocking, but we don't care if it takes 2s as long
                # as it doesn't block the event loop.
                await _asyncio.to_thread(_pe.get_analyzer)
                # Tiny dummy analyse to lock in the JIT paths.
                await _asyncio.to_thread(_pe.analyze, "Warmup John at john@example.com")
                elapsed = int((_time.monotonic() - t0) * 1000)
                _log.info(
                    "synisense warmup ready event=ready surface=boot elapsed_ms=%d",
                    elapsed,
                )
            except Exception as e:  # noqa: BLE001
                _log.warning("synisense warmup failed: %s", e)

        _asyncio.create_task(_syn_warmup())
    except Exception as e:  # noqa: BLE001
        # If the production guard in init_keys() raised MasterKeyMissing
        # we re-raise to refuse boot. Anything else is a non-fatal load
        # issue — log and continue so the rest of the app is still up.
        from services.synisense.encryption import MasterKeyMissing as _MKM
        if isinstance(e, _MKM):
            raise RuntimeError(str(e)) from e
        import logging as _lg
        _lg.getLogger("akki.startup").error("synisense init failed: %s", e)

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

    # Early-access registrations (public marketing intake)
    await db.early_access_registrations.create_index("email", unique=True)
    await db.early_access_registrations.create_index([("created_at", -1)])

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
    # M.4 — Solva v1 (`solve_*`) collections renamed to
    # `solva_v1_*_archive` and treated as forensic read-only. The
    # boot-time index creation + seed_solve_clusters / seed_solve_comparables
    # invocations were removed: the v1 forensic GETs were retired in M.4
    # (routers/solva.py + routers/solva_engine.py deleted), so nothing
    # reads those collections at runtime.

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
    await db.boardpacks.create_index([("context_id", 1), ("status", 1), ("created_at", -1)])

    # Phase 11 ITEM B — validator soft-cap counter. Unique compound on
    # (day_utc, surface) makes concurrent increments race-safe.
    await db.llm_validator_usage.create_index(
        [("day_utc", 1), ("surface", 1)], unique=True,
    )

    # Phase 12.1 — Synisense runs + shield maps.
    # `synisense_runs` carries per-execution audit-lite records (no
    # original text, SHA-256 of input instead). Index by context +
    # surface + time so the governance TrustPanel can cheaply roll up
    # spans-per-week histograms in 12.2.
    await db.synisense_runs.create_index([("context_id", 1), ("ts", -1)])
    await db.synisense_runs.create_index([("surface", 1), ("ts", -1)])
    await db.synisense_runs.create_index("input_sha256")
    # `synisense_shield_maps` carries AES-GCM envelope-encrypted originals.
    # TTL index on `expires_at` reclaims entries automatically; the
    # application sets `expires_at` per-surface (1h public_read, 24h
    # default, 7d hard max). Mongo's TTL monitor checks hourly.
    await db.synisense_shield_maps.create_index("id", unique=True)
    await db.synisense_shield_maps.create_index(
        "expires_at", expireAfterSeconds=0,
    )
    await db.synisense_shield_maps.create_index([("context_id", 1), ("created_at", -1)])

    # Phase J — Sandbox v2 sessions (UX rebuild). 7-day TTL; the user's
    # Welcome answers + per-step state persist for cross-tab resume.
    # Distinct collection from `sandbox_pickups`; v2 is a different surface.
    await db.sandbox_v2_sessions.create_index("id", unique=True)
    await db.sandbox_v2_sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.sandbox_v2_sessions.create_index([("created_at", -1)])

    # Inbound-email idempotency
    await db.accounts.create_index("inbound_token", sparse=True)
    await db.contexts.create_index("inbound_token", sparse=True)

    # Phase 15.0 — Solva v2 POC. Separate collection from v1 solve_sessions;
    # v1 data is never migrated or touched. Indexes mirror the access
    # patterns in routers/solva_v2.py (list-my-sessions, get-by-id-and-account).
    await db.solva_v2_sessions.create_index("id", unique=True)
    await db.solva_v2_sessions.create_index([("account_id", 1), ("started_at", -1)])
    await db.solva_v2_sessions.create_index([("account_id", 1), ("status", 1)])
    await db.solva_v2_sessions.create_index([("account_id", 1), ("version", 1)])

    # Phase 15.1 — Solva v2 cycle handoff queue (Daily Review feeder).
    await db.solva_cycle_handoff_queue.create_index("id", unique=True)
    await db.solva_cycle_handoff_queue.create_index([("account_id", 1), ("status", 1), ("created_at", -1)])
    await db.solva_cycle_handoff_queue.create_index("session_id")
    # M.4 — solve_handoffs index removed. Solva v2 idempotency now lives
    # in solva_cycle_handoff_queue; the v1 collection is archived as
    # solva_v1_handoffs_archive.

    # Phase 15.1 — retry telemetry. TTL 30 days; aggregated 24h on the
    # admin LLM spend dashboard, grouped by surface.
    await db.llm_retry_log.create_index("created_at", expireAfterSeconds=30 * 24 * 3600)
    await db.llm_retry_log.create_index([("surface", 1), ("created_at", -1)])

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

    # Phase 15.3.5 cutover — feature flag dropped. The boot-time admin
    # auto-flip is no longer needed because Solva v2 is now open to every
    # authenticated account. The `solva_v2_poc` field in `db.accounts`
    # is left intact for forensic parity but unused.

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

            # ── Daily 03:00 UTC — Paragraph anchors sweep (Reading Viewer
            # Phase 1, Advisory 2). Computes paragraph[] for any docs that
            # are missing anchors or have stale anchors_version. Lazy-on-read
            # also fills the same shape; the cron is the catch-all for docs
            # that haven't been opened yet.
            async def _fire_paragraph_anchors_sweep():
                try:
                    async with httpx.AsyncClient(timeout=600.0) as ac:
                        resp = await ac.post(
                            "http://localhost:8001/api/cron/paragraph-anchors-sweep",
                            headers={"X-Cron-Secret": cron_secret},
                        )
                    logger.info("Paragraph anchors sweep cron: status=%s body=%s",
                                resp.status_code, (resp.text or "")[:200])
                except Exception as e:  # noqa: BLE001
                    logger.warning("Paragraph anchors sweep cron failed: %s", e)

            scheduler.add_job(
                _fire_paragraph_anchors_sweep,
                CronTrigger(hour=3, minute=0),
                id="paragraph_anchors_daily",
                replace_existing=True,
            )

            # ── Daily 04:00 UTC — Solva v2 stale-session sweep (Phase 15.3
            # decision #11). Marks active v2 sessions idle > 30 days as
            # abandoned with abandoned_reason="stale_30d". Idempotent.
            async def _fire_solva_v2_stale_sweep():
                try:
                    async with httpx.AsyncClient(timeout=120.0) as ac:
                        resp = await ac.post(
                            "http://localhost:8001/api/solva/v2/cron/stale-session-sweep",
                            headers={"X-Cron-Secret": cron_secret},
                        )
                    logger.info("Solva v2 stale-session sweep: status=%s body=%s",
                                resp.status_code, (resp.text or "")[:200])
                except Exception as e:  # noqa: BLE001
                    logger.warning("Solva v2 stale-session sweep failed: %s", e)

            scheduler.add_job(
                _fire_solva_v2_stale_sweep,
                CronTrigger(hour=4, minute=0),
                id="solva_v2_stale_session_daily",
                replace_existing=True,
            )

            # ── Phase B.1 — Chat 30-day retention sweep (daily 03:30 UTC) ──
            # Soft-deleted chats (status='archived' + deleted_at older
            # than 30 days) get hard-removed; one chat.hard_deleted
            # audit row per chat is appended to keep the SHA-256 chain
            # intact. Same APScheduler/in-process caveat as the other
            # jobs — Phase G adds Mongo-lock leader election for the
            # multi-replica case.
            async def _fire_chat_retention_sweep():
                try:
                    from routers.chat import run_chat_retention_sweep
                    summary = await run_chat_retention_sweep()
                    logger.info("Chat retention sweep: %s", summary)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Chat retention sweep failed: %s", e)

            scheduler.add_job(
                _fire_chat_retention_sweep,
                CronTrigger(hour=3, minute=30),
                id="chat_retention_daily",
                replace_existing=True,
            )

            scheduler.start()
            app.state.scheduler = scheduler
            logger.info("Schedulers armed: Exco360 (Tue 10:00) + Influence Digest (Mon 08:00) + Paragraph Anchors (daily 03:00) + Chat Retention (daily 03:30) + Solva v2 Stale (daily 04:00) UTC.")
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not arm weekly scheduler: %s", e)
    else:
        logger.info("AKKI_CRON_SECRET not set — weekly scheduler skipped.")


@app.on_event("shutdown")
async def on_shutdown():
    sched = getattr(app.state, "scheduler", None)
    if sched:
        sched.shutdown(wait=False)
    # Phase 15.1: skip closing Motor when running under pytest. Tests use
    # httpx.ASGITransport(app=app) and exit their `async with` block per
    # test, which fires this shutdown event. Closing the module-singleton
    # Motor client here would kill every subsequent test that touches the
    # DB. In production every restart is via supervisor SIGTERM where the
    # container exits regardless, so the close is moot there too.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    client.close()
