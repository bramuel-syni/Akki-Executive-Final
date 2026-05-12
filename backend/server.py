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
from routers import work_studio_phase_c as work_studio_phase_c_router  # noqa: E402
from routers import work_studio_phase_c2 as work_studio_phase_c2_router  # noqa: E402
from routers import work_studio_from_source as work_studio_from_source_router  # noqa: E402
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
# Phase J (2026-05-12) — Generative Sandbox + Synisense audit metrics.
from routers import sandbox_generation as sandbox_gen_router  # noqa: E402
from routers import synisense_metrics as synisense_metrics_router  # noqa: E402
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
from routers import cycle_manager as cycle_manager_router  # noqa: E402
from routers import cycles as cycles_router  # noqa: E402  # Cycle v2 — multi-cycle master
from routers import quick_actions as quick_actions_router  # noqa: E402  # Cycle Feel pass — telemetry
from routers import team_catalogue as team_catalogue_router  # noqa: E402  # Cycle v2
from routers import cycle_assignments as cycle_assignments_router  # noqa: E402  # Cycle sprint (C3 ASSIGNMENT HANDOFF)
from routers import ned_cycle as ned_cycle_router  # noqa: E402  # Phase E
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
from routers import search as search_router  # noqa: E402  Phase F0 — Universal Search
from routers import website as website_router  # noqa: E402  Phase I1 — Pre-login website
from routers import exco_teams as exco_teams_router  # noqa: E402  HOME sprint — ExCo teams
from routers import portfolio as portfolio_router  # noqa: E402  HOME sprint — portfolio state
from routers import compilations as compilations_router  # noqa: E402  Patch 2B.2 — Compilation Wizard
from routers import home as home_router  # noqa: E402  Patch 3 — Home v2
from routers import monitor_v2 as monitor_v2_router  # noqa: E402  Patch 5 — Objectives & Projects
from routers import streaming_v9 as streaming_v9_router  # noqa: E402  Patch 9 — Streaming phase events
from routers import questions as questions_router  # noqa: E402  Patch 14 — Questions UI
from routers import news as news_router  # noqa: E402  Patch 21 — News feed
from routers import profile as profile_router  # noqa: E402  Patch 25C — /me/profile country


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
app.include_router(work_studio_phase_c_router.router)
app.include_router(work_studio_phase_c2_router.router)
app.include_router(work_studio_from_source_router.router)
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
app.include_router(cycle_manager_router.router)
app.include_router(cycles_router.router)  # Cycle v2 — multi-cycle master
app.include_router(quick_actions_router.router)  # Cycle Feel pass — Quick Action telemetry
app.include_router(team_catalogue_router.router)  # Cycle v2 — team catalogue
app.include_router(cycle_assignments_router.router)  # Cycle sprint — submit/assign/inbox/accept/decline
app.include_router(ned_cycle_router.router)  # Phase E — NED Cycle Manager
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
app.include_router(search_router.router)  # Phase F0 — Universal Search
app.include_router(website_router.router)  # Phase I1 — Pre-login website
# Phase J (2026-05-12) — Generative Sandbox MVP + Synisense audit metrics.
app.include_router(sandbox_gen_router.router)
app.include_router(synisense_metrics_router.router)
# HOME sprint (2026-05-12) — ExCo teams grouping function.
app.include_router(exco_teams_router.router)
app.include_router(portfolio_router.router)
app.include_router(compilations_router.router)  # Patch 2B.2 — Compilation Wizard
app.include_router(home_router.router)  # Patch 3 — Home v2
app.include_router(monitor_v2_router.router)  # Patch 5 — Monitor v2
app.include_router(streaming_v9_router.router)  # Patch 9 — Streaming phase events
app.include_router(questions_router.router)  # Patch 14 — Questions UI
app.include_router(news_router.router)  # Patch 21 — News feed
app.include_router(profile_router.router)  # Patch 25C — /me/profile country


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

    # ─── Phase B.3 streaming-mode banner ────────────────────────────────
    # Print which path each provider will take. `direct_stream` means
    # we have a direct provider key and will use it; `proxy_buffered`
    # means the call falls through to emergentintegrations and arrives
    # as one chunk (rollback path or no-key path).
    try:
        from services.llm_streaming import streaming_mode_per_provider
        _modes = streaming_mode_per_provider()
        logger.info(
            "[chat] streaming: claude=%s gemini=%s gpt=%s",
            _modes["claude"], _modes["gemini"], _modes["gpt"],
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("[chat] streaming mode probe failed: %s", e)

    # ─── Postmark inbound webhook secret guard ──────────────────────────
    # `routers/inbound_email._verify_secret` enforces a constant-time
    # match against the URL `?secret=` parameter. In production we MUST
    # have either POSTMARK_WEBHOOK_SECRET or POSTMARK_SERVER_TOKEN set
    # — otherwise the verifier accepts everything and the route is
    # publicly writable. In non-production, missing secret is loud-WARN.
    _akki_env = (os.environ.get("AKKI_ENV") or "").lower()
    _has_inbound_secret = bool(
        os.environ.get("POSTMARK_WEBHOOK_SECRET")
        or os.environ.get("POSTMARK_SERVER_TOKEN")
    )
    if _akki_env == "production" and not _has_inbound_secret:
        raise RuntimeError(
            "AKKI_ENV=production but neither POSTMARK_WEBHOOK_SECRET nor "
            "POSTMARK_SERVER_TOKEN is set. Inbound email route would be "
            "publicly writable. Set the secret or unset AKKI_ENV before boot."
        )
    if not _has_inbound_secret:
        logger.warning(
            "[postmark] signature verification disabled (no secret in env). "
            "OK in dev; MUST be set in production."
        )

    # Phase G2 (2026-05-11) — HMAC/Basic-Auth boot guard.
    # If AKKI_ENV=production and POSTMARK_USE_HMAC is explicitly
    # disabled, refuse boot — accepting URL-secret in production is a
    # downgrade attack vector.
    try:
        from routers.inbound_email import _verify_inbound_boot_guard
        _verify_inbound_boot_guard()
    except Exception as exc:  # noqa: BLE001
        raise

    # Stripe webhook idempotency + dead-letter indexes (additive).
    try:
        from services.stripe_webhook import ensure_indexes as _stripe_ensure
        await _stripe_ensure(db)
    except Exception as e:  # noqa: BLE001
        import logging as _lg
        _lg.getLogger("akki.startup").warning("stripe idempotency indexes: %s", e)

    # ─── Patch 21 — News aggregator boot ────────────────────────────────
    # Set up the indexes idempotently, then start the background sweep
    # task. Sweep fetches all enabled sources every NEWS_REFRESH_MINUTES
    # (default 30 min) and upserts into `news_items`. TTL on created_at
    # ages items out after NEWS_TTL_DAYS (default 14). If sources file
    # is missing or empty, sweep is a no-op — no crash.
    try:
        from services import news_aggregator as _news_agg
        await _news_agg.setup_indexes(db)
        _news_agg.start_scheduler(db)
        logger.info("[news] aggregator scheduled (every %s minutes)", _news_agg.NEWS_REFRESH_MINUTES)
    except Exception as e:  # noqa: BLE001
        logger.warning("[news] aggregator boot failed (continuing): %s", e)

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
    # Patch 2B.2 — Compilation Wizard.
    await db.compilations.create_index("id", unique=True)
    await db.compilations.create_index([("context_id", 1), ("status", 1), ("created_at", -1)])
    await db.compilations.create_index([("context_id", 1), ("artefact_type", 1)])
    # Patch 3 — Home v2.
    await db.user_recent_views.create_index([("account_id", 1), ("surface_path", 1)], unique=True)
    await db.user_recent_views.create_index([("account_id", 1), ("last_visited_at", -1)])
    await db.user_context_visits.create_index([("account_id", 1), ("context_id", 1)], unique=True)
    # Patch 5 — Monitor v2.
    await db.objectives.create_index("id", unique=True)
    await db.objectives.create_index([("context_id", 1), ("rag_status", 1), ("score", -1)])
    await db.projects.create_index("id", unique=True)
    await db.projects.create_index([("context_id", 1), ("rag_status", 1), ("score", -1)])
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
    # Phase G.1 — lifecycle index. Active landing query filters on state.
    await db.signals.create_index([("context_id", 1), ("state", 1), ("created_at", -1)])
    # Phase G.3 — content_hash dedup. Compound on (context_id, content_hash)
    # makes the find_one in services.signal_dedup O(log n).
    await db.signals.create_index([("context_id", 1), ("content_hash", 1)])
    await db.ask_messages.create_index([("context_id", 1), ("created_at", -1)])
    await db.shares.create_index("id", unique=True)
    await db.shares.create_index([("shared_with_account_id", 1), ("created_at", -1)])
    await db.shares.create_index([("shared_by_account_id", 1), ("created_at", -1)])

    # HOME sprint (2026-05-12) — ExCo teams.
    await exco_teams_router.ensure_exco_indexes()

    # Cycle Manager sprint (2026-02) — assignment handoff collections.
    # See /app/memory/sprints/CYCLE_MANAGER_BRIEF.md §3.3 for the design.
    await db.cycle_assignments.create_index("id", unique=True)
    await db.cycle_assignments.create_index(
        [("brief_id", 1), ("ned_id", 1)], unique=True,
        partialFilterExpression={"status": {"$in": ["pending", "accepted", "declined"]}},
    )
    await db.cycle_assignments.create_index([("ned_id", 1), ("status", 1), ("submitted_at", -1)])
    await db.cycle_assignments.create_index([("context_id", 1), ("cycle_id", 1)])
    await db.cycle_assignments.create_index([("submitter_account_id", 1), ("created_at", -1)])
    await db.ned_packs.create_index("id", unique=True)
    await db.ned_packs.create_index([("ned_id", 1), ("received_at", -1)])
    await db.ned_packs.create_index([("assignment_id", 1)], unique=True)
    # board_status filter on work_studio_briefs (Should-have: my submitted briefs).
    await db.work_studio_briefs.create_index(
        [("submitter_account_id", 1), ("board_status", 1), ("submitted_at", -1)],
    )

    # Cycle Manager v2 sprint (2026-02) — multi-cycle pivot.
    # See /app/memory/sprints/CYCLE_MANAGER_V2_BRIEF.md.
    await db.cycles.create_index("id", unique=True)
    await db.cycles.create_index([("context_id", 1), ("status", 1), ("created_at", -1)])
    await db.cycles.create_index([("context_id", 1), ("title", 1)])
    await db.team_catalogue.create_index("id", unique=True)
    await db.team_catalogue.create_index(
        [("context_id", 1), ("email_lc", 1)], unique=True,
    )
    await db.team_catalogue.create_index([("context_id", 1), ("deleted_at", 1), ("name", 1)])
    await db["_migrations"].create_index("id", unique=True)
    # Cycle Manager Feel pass (Patch 2 of 4) — quick action telemetry.
    await db.quick_action_usage.create_index(
        [("context_id", 1), ("account_id", 1), ("action_key", 1)], unique=True,
    )
    await db.quick_action_usage.create_index([
        ("context_id", 1), ("account_id", 1),
        ("click_count", -1), ("last_used_at", -1),
    ])

    # Run the multi-cycle migration on startup (idempotent).
    try:
        from migrations import _runner as _mig_runner  # type: ignore
        await _mig_runner.run_all()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("akki.server").warning(
            "migration runner failed at boot: %s", exc,
        )

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

    # Phase J (2026-05-12) — Generative Sandbox MVP. New collection
    # distinct from `sandbox_v2_sessions` (that one belongs to the
    # legacy guided tour, now moved to /legacy-sandbox). 24h TTL.
    await db.sandbox_sessions.create_index("id", unique=True)
    await db.sandbox_sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.sandbox_sessions.create_index([("created_at", -1)])

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

    # Phase C.1 / C.2 — Work Studio export rows + Brief revision chain.
    # `work_studio_phase_c_exports` carries the rendered binary + sha256
    # per export call (one row per click of an Export button).
    # `work_studio_briefs` carries the structured Brief metadata + the
    # active_revision_id pointer; one row per (account, source).
    # `work_studio_brief_revisions` carries each revision's full snapshot
    # + diff + validator verdict; many rows per brief, forming the
    # revision tree via `parent_revision_id`.
    await db.work_studio_phase_c_exports.create_index("id", unique=True)
    await db.work_studio_phase_c_exports.create_index(
        [("account_id", 1), ("created_at", -1)],
    )
    await db.work_studio_phase_c_exports.create_index(
        [("brief_id", 1), ("revision_id", 1), ("format", 1)], sparse=True,
    )
    await db.work_studio_briefs.create_index("id", unique=True)
    await db.work_studio_briefs.create_index(
        [("account_id", 1), ("updated_at", -1)],
    )
    await db.work_studio_briefs.create_index(
        [("account_id", 1), ("source_type", 1), ("source_id", 1)], unique=True,
    )
    await db.work_studio_brief_revisions.create_index("id", unique=True)
    await db.work_studio_brief_revisions.create_index(
        [("brief_id", 1), ("created_at", 1)],
    )
    await db.work_studio_brief_revisions.create_index(
        [("account_id", 1), ("brief_id", 1)],
    )

    # Phase C.3 — sparse `brief_id` indexes on the three kind-aware
    # collections so the Decks/Reports listing (and any future "find
    # the artefact backing this brief" query) is O(log n).
    await db.boardpacks.create_index("brief_id", sparse=True)
    await db.decks.create_index("brief_id", sparse=True)
    await db.reports.create_index("brief_id", sparse=True)

    # iter70 — inbound-queue triage (trust-tiered review)
    await db.inbound_queue.create_index("id", unique=True)
    await db.inbound_queue.create_index([("context_id", 1), ("status", 1), ("created_at", -1)])
    await db.inbound_queue.create_index(
        [("context_id", 1), ("inbound_message_id", 1)],
        sparse=True,
    )
    await db.inbound_queue_raw.create_index("queue_id", unique=True)

    # Phase E.0.2 — context_metadata_signatures
    # In-tenant lookup (signature kind + value within a board)
    await db.context_metadata_signatures.create_index(
        [("context_id", 1), ("signature_kind", 1), ("signature_value", 1)]
    )
    # Cross-tenant aggregation lookup (E.0.3 aggregator joins on this)
    await db.context_metadata_signatures.create_index(
        [("signature_kind", 1), ("signature_value", 1), ("created_at", -1)]
    )
    # Idempotency on per-artefact rewrite
    await db.context_metadata_signatures.create_index(
        [("context_id", 1), ("source_artefact_kind", 1), ("source_artefact_id", 1)]
    )

    # Phase E — NED Cycle Manager
    await db.ned_meetings.create_index([("account_id", 1), ("scheduled_at", 1)])
    await db.ned_meetings.create_index([("account_id", 1), ("context_id", 1), ("committee", 1), ("scheduled_at", -1)])
    await db.ned_meeting_notes.create_index([("meeting_id", 1), ("created_at", 1)])
    await db.ned_meeting_notes.create_index([("account_id", 1), ("kind", 1), ("created_at", -1)])
    await db.ned_positions.create_index([("account_id", 1), ("context_id", 1), ("committee", 1), ("created_at", -1)])
    await db.ned_followups.create_index([("account_id", 1), ("status", 1), ("updated_at", -1)])
    await db.ned_followups.create_index([("meeting_id", 1)])

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
