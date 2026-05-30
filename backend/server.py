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
# Chunk 8 (2026-05-18) — Document Overlay (QA-2026-05-16-029…-036).
from routers import work_studio_overlay as work_studio_overlay_router  # noqa: E402
from routers import work_studio_render as work_studio_render_router  # noqa: E402  # T4.1 (G6)
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
# Phase A (2026-05-13) — Synisense Foundation: new Shield + Engine routers
# under /api/v1/*. Coexists with the legacy in-process pipeline above.
from routers import synisense_shield as synisense_shield_router  # noqa: E402
from routers import synisense_engine as synisense_engine_router  # noqa: E402
from routers import cycle as cycle_router  # noqa: E402
from routers import blog as blog_router  # noqa: E402
from routers import admin_email_provider as admin_email_provider_router  # noqa: E402
from routers import portfolio_data as portfolio_data_router  # noqa: E402
from routers import company_home as company_home_router  # noqa: E402
from routers import events as events_router  # noqa: E402
from routers import oauth_google as oauth_google_router  # noqa: E402
from routers import admin_cohort as admin_cohort_router  # noqa: E402
from routers import auth_magic as auth_magic_router  # noqa: E402
from routers import auth_oauth as auth_oauth_router  # noqa: E402  # Phase U (2026-05-27)
from routers import billing as billing_router  # noqa: E402
# Phase Y (2026-05-27) — First-login onboarding briefs router.
from routers import onboarding_briefs as onboarding_briefs_router  # noqa: E402
# Phase V (2026-05-27) — Admin user CRUD portal router.
from routers import admin_users as admin_users_router  # noqa: E402
from routers import admin_extractions as admin_extractions_router  # noqa: E402
from routers import admin_tenants as admin_tenants_router  # noqa: E402
from routers import account_deletion as account_deletion_router  # noqa: E402
from routers import strategic_goal_evolution as strategic_goal_evolution_router  # noqa: E402
# Phase S (2026-05-27) — Password reset router.
from routers import password_reset as password_reset_router  # noqa: E402
# CLEANUP B2 (2026-05-26): plays_router archived — Plays surface ORPHAN
# per PROVENANCE_TRACE_PLAYS_CYCLE.md. Router moved to
# backend/_archived_legacy/routers/plays.py.archived.
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
from routers import admin_audit_invariant as admin_audit_invariant_router  # noqa: E402  H2.5
from routers import healthz_shield as healthz_shield_router  # noqa: E402  H2.5 follow-up Part B
from routers import healthz_clamav as healthz_clamav_router  # noqa: E402  Hardening Step 1
from routers import trust_center as trust_center_router  # noqa: E402  H3
from routers import observability as observability_router  # noqa: E402  ZZ.4
from routers import cohort_applications as cohort_applications_router  # noqa: E402  M.0c
from routers import admin_shield_backfill as admin_shield_backfill_router  # noqa: E402  H4
from routers import onboarding_status as onboarding_status_router  # noqa: E402  J1
from routers import active_context as active_context_router  # noqa: E402  Phase A — Roles & Company Navigation
from routers import studio as studio_router  # noqa: E402
from routers import studio_blocks as studio_blocks_router  # noqa: E402
from routers import product_features as product_features_router  # noqa: E402
from routers import help as help_router  # noqa: E402  # Phase E — /api/help/features
from routers import early_access as early_access_router  # noqa: E402
# CLEANUP B2 (2026-05-26): cycle_config_router archived — only consumer
# chain (useCycleConfig hook → CycleSettings page → /app/settings/cycle
# route) all archived. Router moved to
# backend/_archived_legacy/routers/cycle_config.py.archived. The
# db.cycle_configs collection persists (solva_v2.py reads from it).
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
from routers import monitor_status_assessment as monitor_status_router  # noqa: E402  Phase F — Update goal
from routers import strategic_goal_assessment as strategic_goal_assessment_router  # noqa: E402  Chunk 12 — Strategic Goal Update Goal flow
from routers import streaming_v9 as streaming_v9_router  # noqa: E402  Patch 9 — Streaming phase events
from routers import feedback as feedback_router  # noqa: E402  Phase R.4 — Feedback widget
from routers import trial_status as trial_status_router  # noqa: E402  Phase R.5.a — Trial status + early-access
from routers import questions as questions_router  # noqa: E402  Patch 14 — Questions UI
from routers import news as news_router  # noqa: E402  Patch 21 — News feed
from routers import profile as profile_router  # noqa: E402  Patch 25C — /me/profile country
# Phase AA-slice-1 (2026-05-27) — tasks/initiatives data model + CRUD.
# Backs Monitor v2 (Phase AA). New `tasks_initiatives` collection.
from routers import tasks_initiatives as tasks_initiatives_router  # noqa: E402


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
# Chunk 8 (2026-05-18) — Document Overlay (QA-2026-05-16-029…-036).
app.include_router(work_studio_overlay_router.router)
app.include_router(work_studio_render_router.router)  # T4.1 (G6) — DOCX/PDF/PPTX on-the-fly render
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
# Phase F (2026-05-26) — Task Manager (rename of Cycle Manager UI).
# Distinct collection `tasks`. Legacy `cycle*` collections + routers
# stay untouched for the Reporting Cycle surface.
from routers import tasks as tasks_router  # noqa: E402
app.include_router(tasks_router.router)
app.include_router(blog_router.router)
app.include_router(admin_email_provider_router.router)
app.include_router(portfolio_data_router.router)
app.include_router(company_home_router.router)
app.include_router(events_router.router)
app.include_router(oauth_google_router.router)
app.include_router(admin_cohort_router.router)
app.include_router(auth_magic_router.router)
app.include_router(auth_oauth_router.router)  # Phase U — Google + Microsoft (mock) OAuth sign-in
app.include_router(billing_router.router)
# Phase Y (2026-05-27) — onboarding briefs.
app.include_router(onboarding_briefs_router.router)
# Phase V (2026-05-27) — admin user CRUD portal.
app.include_router(admin_users_router.router)
app.include_router(admin_extractions_router.router)
app.include_router(admin_tenants_router.router)
app.include_router(account_deletion_router.router)
app.include_router(strategic_goal_evolution_router.router)
# Phase S (2026-05-27) — password reset.
app.include_router(password_reset_router.router)
# CLEANUP B2 (2026-05-26): plays_router include removed — see archive note above.
app.include_router(agenda_router.router)
app.include_router(document_engagement_router.router)
app.include_router(monitor_router.router)
app.include_router(strategic_goals_router.router)
# Phase C — chat-audit-panel router includes `/api/chats/archived`
# which would be shadowed by `/api/chats/{chat_id}` in `chat_router`.
# Registering BEFORE the parameterised chat router so FastAPI matches
# the exact path first.
from routers import chat_audit_panel as _chat_audit_panel  # noqa: E402
app.include_router(_chat_audit_panel.router)
# Phase D — Solva 5-layer pipeline mounted at /api/contexts/{cid}/solva/v2/*
# Distinct from the legacy /api/solva/v2/* paths in routers/solva_v2.py.
from routers import solva_phase_d as _solva_phase_d  # noqa: E402
app.include_router(_solva_phase_d.router)
# Phase D.1 (2026-05-26) — Solva briefing-deck state.
from routers import solva_briefing as _solva_briefing  # noqa: E402
app.include_router(_solva_briefing.router)
# Phase D.2 audit-correction (2026-05-26) — Solva variant-cycle +
# key-usage admin telemetry endpoints.
from routers import solva_telemetry_admin as _solva_telemetry_admin  # noqa: E402
app.include_router(_solva_telemetry_admin.router)
# Phase E (2026-05-16) — observability + migration + export + PDF.
from routers import synisense_observability as _syn_obs  # noqa: E402
from routers import solva_phase_e_polish as _solva_pe  # noqa: E402
app.include_router(_syn_obs.router)
app.include_router(_solva_pe.admin_router)
app.include_router(_solva_pe.solva_export_router)
app.include_router(_solva_pe.chat_pdf_router)

# Solva v2 (Slice 2a 2026-05-29) — structured artefact-payload endpoint
# behind the `SOLVA_V2_ENABLED` feature flag.
from routers import solva_v2_artefact as _solva_v2_artefact  # noqa: E402
app.include_router(_solva_v2_artefact.router)
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
# Phase B (2026-05-21) — back-compat /api/webhooks/postmark/inbound mount.
app.include_router(inbound_email_router.backcompat_router)
app.include_router(inbound_queue_router.router)
app.include_router(enterprise_router.router)
app.include_router(llm_quota_router.router)
app.include_router(admin_llm_spend_router.router)
app.include_router(decks_router.router)
# M.4: solva_router + solva_engine_router include_router calls removed.
app.include_router(walkin_router.router)
app.include_router(admin_auth_events_router.router)
app.include_router(admin_journal_router.router)
app.include_router(admin_audit_invariant_router.router)  # H2.5 — Audit-invariant violations panel
app.include_router(healthz_shield_router.router)  # H2.5 follow-up Part B — Shield readiness probe
app.include_router(healthz_clamav_router.router)  # Hardening Step 1 — ClamAV daemon status probe
app.include_router(trust_center_router.router)  # H3 — Trust Center v1
app.include_router(observability_router.router)  # ZZ.4 — Reasoning velocity
app.include_router(cohort_applications_router.router)  # M.0c — Cohort applications scaffold
app.include_router(admin_shield_backfill_router.router)  # H4 — Shield back-fill
app.include_router(onboarding_status_router.router)  # J1 — re-intro banner + tooltips
app.include_router(active_context_router.router)
app.include_router(studio_router.router)
app.include_router(studio_blocks_router.router)
app.include_router(product_features_router.router)
app.include_router(help_router.router)  # Phase E — /api/help/features
app.include_router(early_access_router.router)
# CLEANUP B2 (2026-05-26): cycle_config_router include removed — see archive note above.
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
# Phase A — Synisense Foundation under /api/v1/.
app.include_router(synisense_shield_router.router)
app.include_router(synisense_engine_router.router)
# Phase C — Chat Protective Layer + Audit Panel.
from routers import chat_audit_panel as _chat_audit_panel  # noqa: E402
from routers import documents_async_mirror as _docs_async_mirror  # noqa: E402
app.include_router(_chat_audit_panel.router)
app.include_router(_docs_async_mirror.router)
# HOME sprint (2026-05-12) — ExCo teams grouping function.
app.include_router(exco_teams_router.router)
app.include_router(portfolio_router.router)
app.include_router(compilations_router.router)  # Patch 2B.2 — Compilation Wizard
app.include_router(home_router.router)  # Patch 3 — Home v2
app.include_router(monitor_v2_router.router)  # Patch 5 — Monitor v2
app.include_router(monitor_status_router.router)  # Phase F — Monitor "Update goal"
app.include_router(strategic_goal_assessment_router.router)  # Chunk 12 — Strategic Goal "Update Goal"
app.include_router(streaming_v9_router.router)  # Patch 9 — Streaming phase events
app.include_router(feedback_router.router)  # Phase R.4 — Feedback widget
app.include_router(trial_status_router.router)  # Phase R.5.a — Trial status + early-access
app.include_router(questions_router.router)  # Patch 14 — Questions UI
app.include_router(news_router.router)  # Patch 21 — News feed
app.include_router(profile_router.router)  # Patch 25C — /me/profile country
# Phase AA-slice-1 (2026-05-27) — tasks/initiatives CRUD.
app.include_router(tasks_initiatives_router.router)
# Chunk 2 (2026-05-13) — async job polling for the three long-running
# QA-blocking endpoints (DJ-R03 brief, DJ-R05 signals, CM-R04 cycle
# compilation). Single GET /api/jobs/{job_id}; scoped per-account.
from routers import async_jobs as async_jobs_router  # noqa: E402
app.include_router(async_jobs_router.router)


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
    # ─── Phase E.A — ClamAV boot guard ──────────────────────────────────
    # Refuses to start when AKKI_ENV=production AND
    # ALLOW_UNSAFE_UPLOADS=true. Returns the active mode so we can log
    # it explicitly — operators should see exactly one of these lines
    # in startup logs:
    #     "clamav: enforce mode (prod)"
    #     "clamav: dev escape hatch ARMED — uploads will bypass scan if clamd unreachable"
    from services.clamav_service import assert_safe_boot as _clamav_assert_safe_boot
    _clamav_mode = _clamav_assert_safe_boot()
    if _clamav_mode == "enforce":
        logging.getLogger("akki").info("clamav: enforce mode (prod)")
    else:
        logging.getLogger("akki").warning(
            "clamav: dev escape hatch ARMED — uploads will bypass scan if "
            "clamd unreachable (AKKI_ENV=%r)", os.environ.get("AKKI_ENV") or "(unset)",
        )

    # ─── H2.5 follow-up Part B (2026-05-24) — Shield boot-time warmup ──
    # Loads spaCy + runs a trivial deidentify probe. If ANY exception
    # fires, the process dies and supervisor restarts it. Crash-looping
    # is the CORRECT behaviour when Shield can't initialise — the
    # alternative is silently forwarding PAN to the LLM. Operators can
    # check `/api/healthz/shield` to see the most-recent warmup state.
    if (os.environ.get("AKKI_SKIP_SHIELD_WARMUP") or "").lower() not in ("1", "true", "yes"):
        from services.synisense.shield.deidentifier import warmup_or_die
        await warmup_or_die()

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

    # ─── Phase F (2026-05-16) — Synisense Engine derivation backfill ────
    # One-shot pass on startup. Non-blocking — kicked off as a fire-
    # and-forget task so app boot doesn't wait on derivation IO. If
    # the pass fails for any reason, log + continue (the on-demand
    # /api/v1/engine/admin/derive endpoint remains the canonical
    # path; this is just a convenience refresh).
    try:
        import asyncio as _asyncio_boot
        from services.synisense.engine.derivation_scheduler import (
            run_startup_backfill as _engine_backfill,
        )

        async def _engine_backfill_task():
            try:
                totals = await _engine_backfill()
                logger.info("[engine] derivation backfill done: %s", totals)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[engine] derivation backfill failed: %s: %s",
                               type(exc).__name__, str(exc)[:200])

        _asyncio_boot.create_task(_engine_backfill_task())
    except Exception as e:  # noqa: BLE001
        logger.warning("[engine] derivation backfill scheduling failed: %s", e)

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
    # Phase I.4.a (2026-05-27) — events collection for the new manual
    # entry surface. Compound index keys list-by-context queries
    # sorted by start_at (used by /api/contexts/{cid}/events).
    await db.events.create_index([("context_id", 1), ("start_at", 1)])
    # Phase I.4.c (2026-05-27) — user_calendar_credentials index +
    # init the OAuth token vault (Fernet key from env or auto-gen in non-prod).
    await db.user_calendar_credentials.create_index(
        [("user_id", 1), ("context_id", 1), ("provider", 1)],
        unique=True, partialFilterExpression={"deleted_at": None},
    )
    try:
        from services.crypto import token_vault as _vault
        _vault.init_vault()
    except Exception as _e:
        logger.warning("[startup] token_vault init failed: %s", _e)
    # Phase J (2026-05-27) — `revoked_jtis` blocklist for the JTI
    # revocation path. TTL index on `revoked_at` auto-cleans after the
    # access-token TTL window (8h = 28800s) since a JWT past its `exp`
    # would fail verification anyway — keeping the JTI longer is wasted
    # storage. The lookup index on `jti` makes the verify path O(1).
    await db.revoked_jtis.create_index("jti", unique=True)
    await db.revoked_jtis.create_index(
        "revoked_at", expireAfterSeconds=60 * 60 * 8,
    )
    # Phase R.1 (2026-05-27) — `cohort_invites` collection. Indexes:
    # - `id` UNIQUE for the public invite_id surfaced in admin API.
    # - `magic_link_token` UNIQUE for the consume-endpoint O(1) lookup.
    # - compound `(email, cohort_tag)` for re-issuance scenarios (R.5).
    await db.cohort_invites.create_index("id", unique=True)
    await db.cohort_invites.create_index("magic_link_token", unique=True)
    await db.cohort_invites.create_index([("email", 1), ("cohort_tag", 1)])
    # Phase R.3 (2026-05-27) — `feature_events` collection indexes
    # (TTL 90 days + compound for funnel queries). Best-effort.
    try:
        from services.cohort.feature_events import ensure_indexes as _r3_ensure
        await _r3_ensure()
    except Exception:
        pass

    # Phase AA-slice-1 (2026-05-27) — tasks_initiatives indexes.
    try:
        from routers.tasks_initiatives import ensure_indexes as _aa1_ensure
        await _aa1_ensure()
    except Exception as _e:
        logger.warning("[startup] tasks_initiatives ensure_indexes failed: %s", _e)

    # Phase AA-slice-2 (2026-05-27) — extraction logs/failures indexes.
    try:
        from services.tasks_initiatives.extraction import ensure_indexes as _aa2_ensure
        await _aa2_ensure()
    except Exception as _e:
        logger.warning("[startup] aa2.extraction ensure_indexes failed: %s", _e)

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

    # Chunk 8 (2026-05-18) — Document Overlay foundation migration.
    # Backfills `lifecycle_state="committed", legacy=True` on existing
    # `work_studio_exports` rows. Idempotent.
    try:
        from services.work_studio_overlay import ensure_overlay_migration
        stats = await ensure_overlay_migration(db)
        logging.getLogger("akki.server").info(
            "chunk8 overlay migration: %s", stats,
        )
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("akki.server").warning(
            "chunk8 overlay migration failed: %s", exc,
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

    # Solva v2 artefact (Slice 2b, 2026-05-29) — auto-enable the new
    # 15-element slide-paginated artefact for `admin@akki.ai` ONLY so
    # the founder can eyeball the deck immediately on every fresh pod
    # boot. All other accounts stay OFF (v1 regression-protection real).
    # Cross-account smoke testing uses the `?v2=1` URL override.
    # Idempotent: only sets when the flag is absent OR not already true.
    try:
        existing_flags = (existing or {}).get("feature_flags") or {} if existing else {}
        if not existing_flags.get("solva_v2"):
            await db.accounts.update_one(
                {"email": admin_email},
                {"$set": {"feature_flags.solva_v2": True}},
            )
            logger.info("Solva v2 artefact flag auto-enabled for %s", admin_email)
    except Exception as _e:  # noqa: BLE001
        logger.warning("[startup] Solva v2 admin flag flip failed: %s", _e)

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

    # Chunk 18 (Track 4 item 1, 2026-05-21) — eager-load spaCy NER so
    # the first Shield invocation (commonly an `evolution-diff` or
    # `generate-meta` call) doesn't pay the 1-3s lazy-load cost. The
    # `_ensure_spacy()` helper is process-wide cached + thread-safe;
    # calling it at startup populates the cache once. Wrapped in
    # try/except so a spaCy failure doesn't prevent the app from
    # serving traffic — the lazy path retains the same error
    # handling for individual requests.
    try:
        import asyncio as _asyncio  # noqa: WPS433 — locally scoped
        from services.synisense.shield import deidentifier as _deid  # noqa: WPS433

        def _warm_spacy_sync():
            try:
                _deid._ensure_spacy()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Chunk 18 spaCy warm-up failed: %s", type(exc).__name__)

        # Run spaCy load in a worker thread so the startup event
        # finishes promptly (load itself is CPU-bound; offloading
        # avoids blocking the event loop on a 1-3s import + load).
        loop = _asyncio.get_running_loop()
        loop.run_in_executor(None, _warm_spacy_sync)
        logger.info("Chunk 18 (Track 4 item 1): spaCy NER warm-up scheduled at startup.")
    except Exception as e:  # noqa: BLE001
        logger.warning("Chunk 18 spaCy warm-up scheduling failed: %s", e)

    # ── Chunk 18 (Track 4 item 3, 2026-05-21) — Synisense Engine hourly cron ──
    # Single-instance Mongo-locked APScheduler job that fires
    # `derivation_scheduler.run_hourly_pass()` at the top of every hour
    # UTC. Replicas race to claim the per-(job_id, hour_bucket) lock in
    # `scheduler_locks`; the winner runs the pass and writes a heartbeat
    # row to `scheduler_runs`. Operators can verify liveness via
    # `db.scheduler_runs.find({job_id: "synisense_engine_hourly"})`.
    #
    # Runs INDEPENDENT of AKKI_CRON_SECRET because it's an internal
    # background pass, not a webhook-triggered cron.
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler as _EngSched
        from apscheduler.triggers.cron import CronTrigger as _EngCron
        from services.synisense.engine import scheduler_lock as _engine_lock
        from services.synisense.engine.derivation_scheduler import (
            run_hourly_pass as _engine_hourly,
        )

        await _engine_lock.ensure_indexes()

        async def _fire_engine_hourly_pass():
            await _engine_lock.run_locked(
                job_id="synisense_engine_hourly",
                fn=_engine_hourly,
                bucket=_engine_lock.current_hour_bucket(),
                lease_seconds=3600,
            )

        engine_sched = _EngSched(timezone="UTC")
        engine_sched.add_job(
            _fire_engine_hourly_pass,
            _EngCron(minute=0),  # top of every hour UTC
            id="synisense_engine_hourly",
            replace_existing=True,
        )
        engine_sched.start()
        app.state.engine_scheduler = engine_sched
        logger.info(
            "Chunk 18 (Track 4 item 3): Synisense Engine hourly cron armed (top-of-hour UTC, Mongo-locked, replica=%s).",
            _engine_lock.replica_id(),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Chunk 18 engine hourly cron arm failed: %s: %s", type(e).__name__, e)


@app.on_event("startup")
async def on_startup_demo_seed():
    """Hardening Step 3 (2026-05-25) — auto-apply the
    ``DEMO_T5_BACKLOG`` seed pack on every pod boot so fresh
    preview / restarted prod pods don't require a manual
    ``python -m scripts.seed_backlog_b_demo`` invocation.

    Idempotency: the seed script uses upsert by deterministic
    ``demo-t5backlog-*`` ids, so re-running is safe (delta = 0).

    Fail-soft: every exception is logged and swallowed. The pod
    MUST continue serving traffic even if seeding fails — demo
    data unavailability is preferable to a boot loop.

    Env-guard: ``DISABLE_DEMO_SEED=1`` (or ``true``) skips the
    hook entirely. Default = run. Honours the operator's opt-out
    so prod tenants who don't want demo data tagged in their DB
    can set the flag without a code change.
    """
    log = logging.getLogger("akki.startup")
    disable_flag = (os.environ.get("DISABLE_DEMO_SEED") or "").strip().lower()
    if disable_flag in ("1", "true", "yes", "on"):
        log.info("seed_backlog_b_demo: DISABLE_DEMO_SEED=%r — skipping",
                 os.environ.get("DISABLE_DEMO_SEED"))
        return
    try:
        # Local-import so the seed module + its motor client init are
        # only paid for when seeding runs. Outside the try block,
        # nothing in the module touches Mongo or other shared state.
        from scripts import seed_backlog_b_demo as _seed_mod
        result = await _seed_mod.seed_async(verbose=False)
        deltas = result.get("delta") or {}
        post_counts = result.get("post_counts") or {}
        total_delta = sum(deltas.values())
        total_post = sum(post_counts.values())
        if total_delta == 0 and total_post > 0:
            log.info(
                "seed_backlog_b_demo: seeds present, skipping "
                "(rows=%d, delta=0)", total_post,
            )
        elif total_delta > 0:
            log.info(
                "seed_backlog_b_demo: seeds applied (%d rows inserted "
                "or updated across %d collections; total now %d)",
                total_delta, len([d for d in deltas.values() if d > 0]),
                total_post,
            )
        else:
            log.info(
                "seed_backlog_b_demo: ran but no rows present "
                "(delta=0, post=0) — check seed source data",
            )
    except Exception as exc:  # noqa: BLE001 — fail-soft contract
        log.error(
            "seed_backlog_b_demo: ERROR — %s %s",
            type(exc).__name__, str(exc)[:300],
        )


@app.on_event("shutdown")
async def on_shutdown():
    sched = getattr(app.state, "scheduler", None)
    if sched:
        sched.shutdown(wait=False)
    # Chunk 18 (Track 4 item 3) — stop the engine hourly scheduler too.
    engine_sched = getattr(app.state, "engine_scheduler", None)
    if engine_sched:
        engine_sched.shutdown(wait=False)
    # Phase 15.1: skip closing Motor when running under pytest. Tests use
    # httpx.ASGITransport(app=app) and exit their `async with` block per
    # test, which fires this shutdown event. Closing the module-singleton
    # Motor client here would kill every subsequent test that touches the
    # DB. In production every restart is via supervisor SIGTERM where the
    # container exits regardless, so the close is moot there too.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    client.close()
