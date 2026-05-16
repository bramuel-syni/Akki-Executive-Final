"""Synisense Engine — REAL signal derivation (Phase F, 2026-05-16).

Replaces the Phase A seeded stubs with signals derived from real Mongo
collections. Every emitted signal carries:

  derivation_source: "derived_from_<rule>_<collection>"

so it's permanently distinguishable from the seeded stubs
(`seeded_from_*`) and from future real-ingestion signals
(`real_ingestion`).

Per the brief (`SYNISENSE.md` §3) Synisense produces SIGNALS only —
NOT recommendations, narratives, or LLM-derived prose. Every rule
here is deterministic and uses only Mongo data. No Shield calls,
no LLM calls.

Six categories implemented:
- anomaly_flag       — derived_from_cycle_status_anomaly_cycles
- life_stage         — derived_from_session_activity_solva_phase_d_sessions
- churn_risk         — derived_from_engagement_composite_chat_messages
- behavioral_vector  — derived_from_action_log_chat_messages
- compliance_trigger — derived_from_regulatory_keyword_documents
- operational_health — derived_from_cycle_health_composite_cycles

Phase A's `signal_seeder.seed_for_tenant` remains as graceful-
degradation fallback: it's invoked ONLY if `derive_for_tenant`
returns zero signals for a tenant (typically: empty workspace,
new account with no Cycles / Solva sessions / chats). See
`derive_or_seed_for_tenant`.
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from core import db

from services.synisense.engine.signal_seeder import (
    SIGNAL_COLLECTION,
    seed_for_tenant,
)

log = logging.getLogger("synisense.engine.signal_derivation")

# Keyword lists for compliance + anomaly heuristics.
_REGULATORY_KEYWORDS: Tuple[str, ...] = (
    "regulator", "regulatory", "compliance", "fca", "pra", "boe",
    "ecb", "cbk", "cbn", "sarb", "occ", "ofac", "aml", "kyc",
    "sanction", "audit committee", "iso 42001", "nist", "gdpr",
    "eu ai act", "ssm", "basel",
)

_ANOMALY_TRIGGER_STATUSES: Tuple[str, ...] = (
    # Cycle statuses we treat as "trouble": draft past activation window,
    # overdue activation, marked off-track, etc.
    "draft", "stalled", "overdue", "off_track",
)


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat()


def _sig(prefix: str = "sig") -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────
# Rule 1 — anomaly_flag
# Source: cycles where status looks unhealthy OR readiness has fallen
# below a threshold. Emits one signal per unhealthy cycle.
# ─────────────────────────────────────────────────────────────────────
async def _derive_anomaly_flags(tenant_id: str, now: datetime) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    # The tenant's contexts (memberships) — anomaly signals are scoped
    # to contexts the tenant can see.
    tenant_context_ids = await _tenant_context_ids(tenant_id)
    if not tenant_context_ids:
        return out

    cursor = db.cycles.find(
        {"context_id": {"$in": list(tenant_context_ids)}},
        {"_id": 0, "id": 1, "context_id": 1, "title": 1, "status": 1,
         "readiness_pct": 1, "expected_close_at": 1, "updated_at": 1,
         "created_at": 1},
    ).limit(50)
    async for cy in cursor:
        status = (cy.get("status") or "").lower()
        readiness = cy.get("readiness_pct") or 0
        triggered_by: Optional[str] = None
        severity = "low"
        delta = 0.0

        if status in _ANOMALY_TRIGGER_STATUSES:
            triggered_by = f"cycle.status.{status}"
            severity = "high" if status in {"overdue", "off_track"} else "medium"
            delta = 0.6 if severity == "high" else 0.4
        elif isinstance(readiness, (int, float)) and readiness < 40 and status != "completed":
            triggered_by = "cycle.readiness_below_threshold"
            severity = "medium" if readiness >= 20 else "high"
            delta = max(0.0, min(1.0, (50 - readiness) / 100.0))
        else:
            # Stale activity: created >14d ago, still draft, no recent update.
            updated = cy.get("updated_at")
            if status == "draft" and isinstance(updated, datetime):
                age_days = (now - updated).total_seconds() / 86400.0
                if age_days >= 14:
                    triggered_by = "cycle.draft_stale"
                    severity = "low"
                    delta = min(0.5, age_days / 60.0)

        if not triggered_by:
            continue

        out.append({
            "signal_id": _sig(),
            "tenant_id": tenant_id,
            "context_id": cy.get("context_id"),
            "signal_category": "anomaly",
            "signal_type": "anomaly_flag",
            "entity_ref": cy.get("id"),
            "payload": {
                "trigger": triggered_by,
                "severity": severity,
                "delta": round(delta, 3),
                "cycle_title": (cy.get("title") or "")[:140],
            },
            "confidence": round(0.6 + min(delta, 0.3), 3),
            "derivation_source": "derived_from_cycle_status_anomaly_cycles",
            "created_at": _iso(now),
            "expires_at": _iso(now + timedelta(days=7)),
        })
    return out


# ─────────────────────────────────────────────────────────────────────
# Rule 2 — life_stage
# Source: distinct activity timestamps across chat + solva sessions.
# Stages: new_user (<7d ANY activity), engaged (7-30d), steady_state,
# dormant (>60d).
# ─────────────────────────────────────────────────────────────────────
async def _derive_life_stage(tenant_id: str, now: datetime) -> List[Dict[str, Any]]:
    # Earliest + latest "activity" timestamps across collections.
    earliest, latest = await _activity_window(tenant_id)
    if earliest is None or latest is None:
        return []

    days_since_first = (now - earliest).total_seconds() / 86400.0
    days_since_last = (now - latest).total_seconds() / 86400.0

    if days_since_last > 60:
        stage = "dormant"
    elif days_since_first < 7:
        stage = "onboarding"
    elif days_since_first < 30:
        stage = "growth"
    elif days_since_last <= 30:
        stage = "steady_state"
    else:
        stage = "growth"

    return [{
        "signal_id": _sig(),
        "tenant_id": tenant_id,
        "context_id": None,
        "signal_category": "life_stage",
        "signal_type": "life_stage",
        "entity_ref": tenant_id,
        "payload": {
            "stage": stage,
            "weeks_in_stage": max(1, int(min(52, days_since_first / 7.0))),
            "days_since_last_activity": int(days_since_last),
        },
        "confidence": 0.75,
        "derivation_source": "derived_from_session_activity_solva_phase_d_sessions",
        "created_at": _iso(now),
        "expires_at": None,
    }]


# ─────────────────────────────────────────────────────────────────────
# Rule 3 — churn_risk
# Source: composite of recent engagement (chat + Solva), unfilled
# Cycle items, and dormant briefings. 0..1 score.
# ─────────────────────────────────────────────────────────────────────
async def _derive_churn_risk(tenant_id: str, now: datetime) -> List[Dict[str, Any]]:
    # Engagement count over last 30 days.
    cutoff_30 = now - timedelta(days=30)
    cutoff_iso = cutoff_30.isoformat()

    msg_count = await db.chat_messages.count_documents({
        "account_id": tenant_id, "role": "user",
        "created_at": {"$gte": cutoff_30},
    })
    solva_count = await db.solva_phase_d_sessions.count_documents({
        "account_id": tenant_id, "created_at": {"$gte": cutoff_30},
    })

    # Outstanding cycle items in the tenant's contexts.
    tenant_context_ids = await _tenant_context_ids(tenant_id)
    overdue_items = 0
    if tenant_context_ids:
        overdue_items = await db.cycle_questions.count_documents({
            "context_id": {"$in": list(tenant_context_ids)},
            "status": {"$in": ["pending", "in_progress"]},
        })

    # No engagement + no overdue items + no contexts → nothing to
    # assess. Brand-new tenants gracefully fall back to the seeder.
    if msg_count + solva_count + overdue_items == 0 and not tenant_context_ids:
        return []

    # Derive risk: low engagement + many outstanding items → higher risk.
    engagement_score = min(1.0, (msg_count + solva_count * 2) / 30.0)
    overdue_pressure = min(1.0, overdue_items / 20.0)
    risk = round(max(0.0, min(1.0,
        0.55 * (1.0 - engagement_score) + 0.45 * overdue_pressure
    )), 3)

    leading_indicator = (
        "Outstanding cycle items without recent activity"
        if overdue_pressure > engagement_score else
        "Engagement below typical baseline"
        if engagement_score < 0.3 else
        "Engagement stable; no leading indicator above threshold"
    )

    return [{
        "signal_id": _sig(),
        "tenant_id": tenant_id,
        "context_id": None,
        "signal_category": "risk",
        "signal_type": "churn_risk",
        "entity_ref": tenant_id,
        "payload": {
            "risk_score": risk,
            "leading_indicator": leading_indicator,
            "components": {
                "engagement_score_30d": round(engagement_score, 3),
                "overdue_item_pressure": round(overdue_pressure, 3),
                "user_messages_30d": int(msg_count),
                "solva_sessions_30d": int(solva_count),
                "outstanding_cycle_items": int(overdue_items),
            },
            "cutoff_at": cutoff_iso,
        },
        "confidence": 0.7,
        "derivation_source": "derived_from_engagement_composite_chat_messages",
        "created_at": _iso(now),
        "expires_at": _iso(now + timedelta(days=14)),
    }]


# ─────────────────────────────────────────────────────────────────────
# Rule 4 — behavioral_vector
# Source: deterministic 8-float vector derived from action-timestamp
# histograms. Same shape as the seeded vector, but values are REAL
# normalised counts over a 7-day window.
# ─────────────────────────────────────────────────────────────────────
async def _derive_behavioral_vector(tenant_id: str, now: datetime) -> List[Dict[str, Any]]:
    cutoff = now - timedelta(days=7)
    # Eight buckets, each a count we normalise to [0,1].
    user_msgs = await db.chat_messages.count_documents({
        "account_id": tenant_id, "role": "user",
        "created_at": {"$gte": cutoff},
    })
    solva_started = await db.solva_phase_d_sessions.count_documents({
        "account_id": tenant_id, "created_at": {"$gte": cutoff},
    })
    solva_completed = await db.solva_phase_d_sessions.count_documents({
        "account_id": tenant_id,
        "status": "completed",
        "completed_at": {"$gte": cutoff},
    })
    tenant_context_ids = await _tenant_context_ids(tenant_id)
    tc_list = list(tenant_context_ids) if tenant_context_ids else []
    cycles_active = await db.cycles.count_documents({
        "context_id": {"$in": tc_list}, "status": "active",
    }) if tc_list else 0
    docs_uploaded = await db.documents.count_documents({
        "account_id": tenant_id, "created_at": {"$gte": cutoff},
    })
    briefings_approved = await db.briefings.count_documents({
        "account_id": tenant_id, "status": "approved",
        "updated_at": {"$gte": cutoff},
    })
    shield_calls = await db.synisense_audit_log.count_documents({
        "tenant_id": tenant_id, "timestamp": {"$gte": cutoff.isoformat()},
    })
    refusals = await db.synisense_audit_log.count_documents({
        "tenant_id": tenant_id, "outcome": "governance_refused",
        "timestamp": {"$gte": cutoff.isoformat()},
    })

    raw = [
        user_msgs, solva_started, solva_completed, cycles_active,
        docs_uploaded, briefings_approved, shield_calls, refusals,
    ]
    # No activity at all → don't emit a vector. Brand-new tenants
    # gracefully fall back to the Phase A seeder in `derive_or_seed_*`.
    if sum(raw) == 0:
        return []
    # Normalise to [0,1] with a logarithmic ceiling so a busy week
    # doesn't dominate a quieter one.
    def _norm(n: int) -> float:
        return round(min(1.0, math.log1p(max(0, n)) / math.log1p(50)), 4)
    vector = [_norm(int(x)) for x in raw]

    return [{
        "signal_id": _sig(),
        "tenant_id": tenant_id,
        "context_id": None,
        "signal_category": "profile",
        "signal_type": "behavioral_vector",
        "entity_ref": tenant_id,
        "payload": {
            "vector": vector,
            "window_days": 7,
            "components": [
                "user_chat_messages", "solva_started", "solva_completed",
                "active_cycles", "docs_uploaded", "briefings_approved",
                "shield_calls", "shield_refusals",
            ],
        },
        "confidence": 0.8,
        "derivation_source": "derived_from_action_log_chat_messages",
        "created_at": _iso(now),
        "expires_at": None,
    }]


# ─────────────────────────────────────────────────────────────────────
# Rule 5 — compliance_trigger
# Source: documents whose summary/commentary/title contains regulatory
# keywords + cycles that involve an audit/risk committee.
# ─────────────────────────────────────────────────────────────────────
async def _derive_compliance_triggers(tenant_id: str, now: datetime) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    # Documents pass.
    cursor = db.documents.find(
        {"account_id": tenant_id},
        {"_id": 0, "id": 1, "title": 1, "summary": 1,
         "commentary": 1, "context_id": 1, "created_at": 1},
    ).limit(50)
    async for d in cursor:
        haystack = " ".join([
            str(d.get("title") or ""),
            str(d.get("summary") or ""),
            str(d.get("commentary") or ""),
        ]).lower()
        matched = [kw for kw in _REGULATORY_KEYWORDS if kw in haystack]
        if not matched:
            continue
        out.append({
            "signal_id": _sig(),
            "tenant_id": tenant_id,
            "context_id": d.get("context_id"),
            "signal_category": "compliance",
            "signal_type": "compliance_trigger",
            "entity_ref": d.get("id"),
            "payload": {
                "trigger_kind": "regulatory_keyword_in_document",
                "threshold": len(matched),
                "matched_keywords": matched[:8],
                "doc_title": (d.get("title") or "")[:120],
            },
            "confidence": round(0.6 + min(0.3, len(matched) * 0.05), 3),
            "derivation_source": "derived_from_regulatory_keyword_documents",
            "created_at": _iso(now),
            "expires_at": _iso(now + timedelta(days=30)),
        })

    # Cycles in audit / risk committees.
    tenant_context_ids = await _tenant_context_ids(tenant_id)
    if tenant_context_ids:
        cursor = db.cycles.find(
            {"context_id": {"$in": list(tenant_context_ids)},
             "committee_label": {"$regex": "audit|risk", "$options": "i"}},
            {"_id": 0, "id": 1, "context_id": 1, "title": 1,
             "committee_label": 1, "status": 1},
        ).limit(20)
        async for cy in cursor:
            out.append({
                "signal_id": _sig(),
                "tenant_id": tenant_id,
                "context_id": cy.get("context_id"),
                "signal_category": "compliance",
                "signal_type": "compliance_trigger",
                "entity_ref": cy.get("id"),
                "payload": {
                    "trigger_kind": "audit_or_risk_committee_cycle",
                    "threshold": 1,
                    "committee_label": cy.get("committee_label"),
                    "cycle_status": cy.get("status"),
                },
                "confidence": 0.7,
                "derivation_source": "derived_from_regulatory_keyword_documents",
                "created_at": _iso(now),
                "expires_at": _iso(now + timedelta(days=30)),
            })
    return out


# ─────────────────────────────────────────────────────────────────────
# Rule 6 — operational_health
# Composite of: cycle health (% completed), objective on-track rate,
# and signal noise (anomaly signals as % of total).
# ─────────────────────────────────────────────────────────────────────
async def _derive_operational_health(
    tenant_id: str, now: datetime, prior_signals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    tenant_context_ids = await _tenant_context_ids(tenant_id)
    if not tenant_context_ids:
        return []
    tc_list = list(tenant_context_ids)

    cy_total = await db.cycles.count_documents({"context_id": {"$in": tc_list}})
    cy_completed = await db.cycles.count_documents({
        "context_id": {"$in": tc_list}, "status": "completed",
    })
    cy_overdue = await db.cycles.count_documents({
        "context_id": {"$in": tc_list}, "status": {"$in": ["overdue", "off_track", "stalled"]},
    })

    obj_total = await db.objectives.count_documents({"context_id": {"$in": tc_list}})
    obj_green = await db.objectives.count_documents({
        "context_id": {"$in": tc_list}, "rag_status": "green",
    })

    anomaly_count = sum(1 for s in prior_signals if s["signal_type"] == "anomaly_flag")
    signal_total = max(1, len(prior_signals))
    noise_ratio = anomaly_count / signal_total

    completed_rate = cy_completed / cy_total if cy_total else 1.0
    on_track_rate = obj_green / obj_total if obj_total else 1.0
    error_rate = round(min(1.0, cy_overdue / max(1, cy_total) + noise_ratio * 0.3), 3)
    queue_depth = cy_overdue

    return [{
        "signal_id": _sig(),
        "tenant_id": tenant_id,
        "context_id": None,
        "signal_category": "operational",
        "signal_type": "operational_health",
        "entity_ref": tenant_id,
        "payload": {
            "queue_depth": int(queue_depth),
            "error_rate": error_rate,
            "components": {
                "cycle_total": int(cy_total),
                "cycle_completed_rate": round(completed_rate, 3),
                "objective_on_track_rate": round(on_track_rate, 3),
                "anomaly_noise_ratio": round(noise_ratio, 3),
            },
        },
        "confidence": 0.75,
        "derivation_source": "derived_from_cycle_health_composite_cycles",
        "created_at": _iso(now),
        "expires_at": _iso(now + timedelta(days=7)),
    }]


# ─────────────────────────────────────────────────────────────────────
# Helpers.
# ─────────────────────────────────────────────────────────────────────
async def _tenant_context_ids(tenant_id: str) -> set:
    """Set of context_ids the tenant has active membership for."""
    rows = await db.memberships.find(
        {"account_id": tenant_id, "status": "active"},
        {"_id": 0, "context_id": 1},
    ).to_list(length=200)
    return {r["context_id"] for r in rows if r.get("context_id")}


async def _activity_window(tenant_id: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Earliest + latest activity timestamp across chat + solva."""
    earliest: Optional[datetime] = None
    latest: Optional[datetime] = None

    for coll, ts_field in (
        ("chat_messages", "created_at"),
        ("solva_phase_d_sessions", "created_at"),
    ):
        first = await db[coll].find_one(
            {"account_id": tenant_id, ts_field: {"$exists": True}},
            {"_id": 0, ts_field: 1},
            sort=[(ts_field, 1)],
        )
        last = await db[coll].find_one(
            {"account_id": tenant_id, ts_field: {"$exists": True}},
            {"_id": 0, ts_field: 1},
            sort=[(ts_field, -1)],
        )
        for row, slot in ((first, "first"), (last, "last")):
            if not row:
                continue
            ts_val = row.get(ts_field)
            if isinstance(ts_val, str):
                try:
                    ts_val = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
                except ValueError:
                    continue
            if not isinstance(ts_val, datetime):
                continue
            if ts_val.tzinfo is None:
                ts_val = ts_val.replace(tzinfo=timezone.utc)
            if slot == "first" and (earliest is None or ts_val < earliest):
                earliest = ts_val
            if slot == "last" and (latest is None or ts_val > latest):
                latest = ts_val
    return earliest, latest


# ─────────────────────────────────────────────────────────────────────
# Public API.
# ─────────────────────────────────────────────────────────────────────
async def derive_for_tenant(tenant_id: str) -> Dict[str, int]:
    """Run all 6 rules and write `derived_from_*` signals to Mongo.

    Idempotent — wipes prior `derivation_source: ^derived_from_` rows
    for this tenant before inserting. Real-ingestion signals (Phase F
    + 1, future) are never touched.
    """
    await db[SIGNAL_COLLECTION].delete_many({
        "tenant_id": tenant_id,
        "derivation_source": {"$regex": "^derived_from_"},
    })

    now = _now()
    all_signals: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}

    rule_outputs: List[Tuple[str, List[Dict[str, Any]]]] = []
    rule_outputs.append(("anomaly_flag",       await _derive_anomaly_flags(tenant_id, now)))
    rule_outputs.append(("life_stage",         await _derive_life_stage(tenant_id, now)))
    rule_outputs.append(("churn_risk",         await _derive_churn_risk(tenant_id, now)))
    rule_outputs.append(("behavioral_vector",  await _derive_behavioral_vector(tenant_id, now)))
    rule_outputs.append(("compliance_trigger", await _derive_compliance_triggers(tenant_id, now)))

    # operational_health depends on the prior signals.
    prior = [s for _, sigs in rule_outputs for s in sigs]
    rule_outputs.append(("operational_health", await _derive_operational_health(tenant_id, now, prior)))

    for label, sigs in rule_outputs:
        counts[label] = len(sigs)
        all_signals.extend(sigs)

    if all_signals:
        await db[SIGNAL_COLLECTION].insert_many(all_signals)

    log.info(
        "synisense.engine.derivation: tenant=%s derived=%d (%s)",
        tenant_id, len(all_signals),
        ", ".join(f"{k}={v}" for k, v in counts.items() if v),
    )
    return counts


async def derive_or_seed_for_tenant(tenant_id: str) -> Dict[str, Any]:
    """Phase F primary path with graceful degradation.

    Returns `{"derived": {...}, "fallback_used": bool, "seeded": {...}}`.
    If derivation produces zero signals (workspace empty, brand-new
    account), the Phase A seeder runs as a fallback so the engine
    never reports zero-content to consumers.
    """
    derived = await derive_for_tenant(tenant_id)
    total_derived = sum(derived.values())
    if total_derived > 0:
        return {"derived": derived, "fallback_used": False, "seeded": {}}

    log.info(
        "synisense.engine.derivation: tenant=%s no derived signals — "
        "falling back to Phase A seeder", tenant_id,
    )
    seeded = await seed_for_tenant(tenant_id)
    return {"derived": derived, "fallback_used": True, "seeded": seeded}
