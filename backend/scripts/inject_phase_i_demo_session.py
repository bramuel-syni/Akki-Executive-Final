"""Inject a synthetic completed Solva v2 session for a known account
and print the resume URL so the artefact view can be opened in the
browser. Used for Phase I.3 visual validation.

Usage:  python3 backend/scripts/inject_phase_i_demo_session.py
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, "/app/backend")
from core import db


async def main():
    admin = await db.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0, "id": 1})
    if not admin:
        print("admin@akki.ai not found")
        return
    sid = str(uuid.uuid4())

    rec = {
        "id": sid,
        "account_id": admin["id"],
        "submodule": "develop_strategy",
        "persona": None,
        "cluster_id": "strategy_drift",
        "cluster_label": "Strategy is drifting and nobody wants to say it",
        "intent": (
            "We have a 3-year strategic refresh due. The board wants a 'next era' story but "
            "the CFO is sceptical that we have the cash to back any meaningful pivot."
        ),
        "status": "completed",
        "version": 2,
        "started_at":   "2026-05-05T10:00:00Z",
        "completed_at": "2026-05-05T10:14:00Z",
        "updated_at":   "2026-05-05T10:14:00Z",
        "layer": "reflection",
        "synthesis": {
            "body": (
                "Three scenarios are credible. [T:corpus] Scenario A — keep the current "
                "strategy and double down on cost discipline. [T:comparable]\n\n"
                "Scenario B — partial pivot toward services revenue, capped at 15% of "
                "group capex. [T:domain_prior] Scenario C — full divestment of the "
                "underperforming segment and a focused services bet. [T:user_assertion]"
            ),
            "stripped_text": "...",
            "claims": [
                {"text": "Scenario A — keep the current strategy and double down on cost discipline.",
                 "tier": "corpus", "confidence_pct": 28, "confidence_band": "Unlikely"},
                {"text": "Scenario B — partial pivot toward services revenue, capped at 15% of group capex.",
                 "tier": "comparable", "confidence_pct": 61, "confidence_band": "Likely"},
                {"text": "Scenario C — full divestment of the underperforming segment and a focused services bet.",
                 "tier": "user_assertion", "confidence_pct": 18, "confidence_band": "Unlikely"},
            ],
            "tier_distribution": {"corpus": 1, "comparable": 1, "domain_prior": 0, "user_assertion": 1, "speculation": 0},
            "validation": {"verdict": "validated"},
            "recommendations": [
                "Recommendation 1: Commission the cash-flow stress test by the next board cycle.",
                "Recommendation 2: Brief the chair on the Scenario B scope-cap before committing to capex.",
            ],
        },
        "reasoning_audit_log": [
            {"engine": "candidate_generation", "engine_version": "1.0", "layer": "grounding",
             "tier_labels": ["corpus", "comparable"], "shield_required": True,
             "ts": datetime.now(timezone.utc).isoformat(),
             "output": {"candidates": [{"hypothesis": "Cash-flow constraint", "tentative_tier_hint": "corpus", "weight": 0.35}]}},
            {"engine": "triangulation", "engine_version": "1.0", "layer": "grounding",
             "tier_labels": ["comparable"], "shield_required": True,
             "ts": datetime.now(timezone.utc).isoformat(),
             "output": {"divergences": [{"summary": "User framing assumes growth pivot affordable; comparables suggest cap.", "severity": "medium", "source": "Comparable: PE-owned UK ISP 2022"}]}},
            {"engine": "tension_detector", "engine_version": "1.0", "layer": "synthesis",
             "tier_labels": ["corpus", "comparable"], "shield_required": False,
             "ts": datetime.now(timezone.utc).isoformat(),
             "output": {"tensions": [
                 {"description": "You came in assuming a pivot is the priority; the cash position suggests restraint."},
                 {"description": "You believe the segment can be saved; comparable cases show divestment yields better returns."},
             ]}},
            {"engine": "probability_weighting", "engine_version": "1.0", "layer": "synthesis",
             "tier_labels": ["corpus", "comparable", "user_assertion"], "shield_required": False,
             "ts": datetime.now(timezone.utc).isoformat(),
             "output": {"aggregation_breakdown": {"candidate_weights": 0.40, "triangulation_alignment": 0.35, "prior": 0.15, "counterfactual": 0.10}}},
        ],
        "turns": [],
    }
    await db.solva_v2_sessions.insert_one(rec)
    print(f"Injected session {sid} for account {admin['id']}")
    print(f"URL: /app/solva/session/{sid}")


if __name__ == "__main__":
    asyncio.run(main())
