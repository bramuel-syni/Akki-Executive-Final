"""Synisense Engine — signal seeder (Phase A).

Derives plausible signals from existing Mongo collections so the engine
has content from day one. Every row inserted MUST carry:

- `derivation_source` : `"seeded_from_<collection>"` — proves these are
  not real-ingestion signals. Phase F (real wiring) will produce
  signals with `derivation_source: "real_ingestion"` and the
  distinction is permanent in the row.
- `confidence`        : 0.5 — flat for seed data; Phase F will produce
  varying confidence per signal.

The seeder is idempotent — it wipes only `derivation_source: seeded_*`
rows for the given tenant before reseeding. Real signals are never
touched.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core import db

log = logging.getLogger("synisense.engine.signal_seeder")

SIGNAL_COLLECTION = "synisense_signals"


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat()


def _deterministic_vector(seed: str, length: int = 8) -> List[float]:
    """Stable 8-float vector from a string seed. Phase A only — Phase F
    replaces with real behavioural vector."""
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    return [round(h[i] / 255.0, 4) for i in range(length)]


async def seed_for_tenant(tenant_id: str) -> Dict[str, int]:
    """Idempotent seed pass for one tenant. Returns per-type counts."""
    # Wipe prior seeded rows for this tenant (keep real-ingestion rows).
    await db[SIGNAL_COLLECTION].delete_many({
        "tenant_id": tenant_id,
        "derivation_source": {"$regex": "^seeded_from_"},
    })

    now = datetime.now(timezone.utc)
    seeded: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}

    # ── anomaly_flag ── from cycles where status looks unhealthy.
    cycles_cursor = db.cycles.find(
        {"$or": [{"status": "completed"}, {"status": "draft"}, {"status": "active"}]},
        {"_id": 0, "id": 1, "context_id": 1, "title": 1, "status": 1,
         "created_at": 1, "owner_account_id": 1},
    ).limit(20)
    async for cy in cycles_cursor:
        # Only seed for cycles whose owner is this tenant. Skip stray rows.
        if cy.get("owner_account_id") != tenant_id:
            # Fallback: cycles in contexts this tenant owns.
            ctx_id = cy.get("context_id")
            if ctx_id:
                ctx = await db.contexts.find_one(
                    {"id": ctx_id, "owner_account_id": tenant_id},
                    {"_id": 0},
                )
                if not ctx:
                    continue
            else:
                continue
        status = cy.get("status") or "unknown"
        if status not in {"draft", "completed"}:
            continue
        seeded.append({
            "signal_id": "sig-" + uuid.uuid4().hex,
            "tenant_id": tenant_id,
            "context_id": cy.get("context_id"),
            "signal_category": "anomaly",
            "signal_type": "anomaly_flag",
            "entity_ref": cy.get("id"),
            "payload": {
                "trigger": f"cycle.status.{status}",
                "severity": "medium" if status == "draft" else "low",
                "delta": 0.5,
            },
            "confidence": 0.5,
            "derivation_source": "seeded_from_cycles",
            "created_at": _iso(now),
            "expires_at": _iso(now + timedelta(days=7)),
        })

    # ── life_stage ── from solva_v2_sessions activity density.
    session_count = await db.solva_v2_sessions.count_documents({"account_id": tenant_id})
    if session_count > 0:
        if session_count >= 20:
            stage = "steady_state"
        elif session_count >= 5:
            stage = "growth"
        else:
            stage = "onboarding"
        seeded.append({
            "signal_id": "sig-" + uuid.uuid4().hex,
            "tenant_id": tenant_id,
            "context_id": None,
            "signal_category": "life_stage",
            "signal_type": "life_stage",
            "entity_ref": tenant_id,
            "payload": {"stage": stage, "weeks_in_stage": min(52, session_count // 2)},
            "confidence": 0.5,
            "derivation_source": "seeded_from_solva_v2_sessions",
            "created_at": _iso(now),
            "expires_at": None,
        })

    # ── churn_risk ── placeholder, clearly marked.
    seeded.append({
        "signal_id": "sig-" + uuid.uuid4().hex,
        "tenant_id": tenant_id,
        "context_id": None,
        "signal_category": "risk",
        "signal_type": "churn_risk",
        "entity_ref": tenant_id,
        "payload": {
            "risk_score": 0.18,
            "leading_indicator": "PLACEHOLDER — Phase F will wire real signal",
        },
        "confidence": 0.5,
        "derivation_source": "seeded_from_chat_sessions",
        "created_at": _iso(now),
        "expires_at": _iso(now + timedelta(days=30)),
    })

    # ── behavioral_vector ── deterministic per-tenant short vector.
    seeded.append({
        "signal_id": "sig-" + uuid.uuid4().hex,
        "tenant_id": tenant_id,
        "context_id": None,
        "signal_category": "profile",
        "signal_type": "behavioral_vector",
        "entity_ref": tenant_id,
        "payload": {
            "vector": _deterministic_vector(tenant_id),
            "window_days": 7,
        },
        "confidence": 0.5,
        "derivation_source": "seeded_from_action_log",
        "created_at": _iso(now),
        "expires_at": None,
    })

    if seeded:
        await db[SIGNAL_COLLECTION].insert_many(seeded)

    for s in seeded:
        counts[s["signal_type"]] = counts.get(s["signal_type"], 0) + 1

    log.info("synisense.engine: seeded %d signals for tenant=%s", len(seeded), tenant_id)
    return counts
