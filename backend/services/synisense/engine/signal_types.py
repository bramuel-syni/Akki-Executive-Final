"""Synisense Engine — canonical signal type catalogue (Phase A).

Locked to the brief's §3.1 categories. Each type carries a short
payload_schema so consumers can validate without hitting the engine.
"""
from __future__ import annotations

from typing import Any, Dict, List

from services.synisense.models import SignalTypeDefinition

_CATALOGUE: List[Dict[str, Any]] = [
    {
        "signal_type": "anomaly_flag",
        "signal_category": "anomaly",
        "description": "Deviation from established behavioural pattern. "
                       "Seeded from cycles whose status indicates trouble "
                       "(draft past activation date, or completed-with-issues).",
        "payload_schema": {
            "trigger": "string",
            "severity": "low|medium|high",
            "delta": "number",
        },
    },
    {
        "signal_type": "life_stage",
        "signal_category": "life_stage",
        "description": "Recognised transition in a tenant's lifecycle. "
                       "Seeded from chat / solva session frequency.",
        "payload_schema": {
            "stage": "onboarding|growth|steady_state|dormant|churn_risk",
            "weeks_in_stage": "integer",
        },
    },
    {
        "signal_type": "churn_risk",
        "signal_category": "risk",
        "description": "Probability the tenant disengages within 30 days. "
                       "Phase A: derived from session-gap heuristic; flagged "
                       "as `seeded_from_chat_sessions` until Phase F.",
        "payload_schema": {
            "risk_score": "number 0..1",
            "leading_indicator": "string",
        },
    },
    {
        "signal_type": "behavioral_vector",
        "signal_category": "profile",
        "description": "Compact numeric vector summarising recent activity "
                       "(7-day rolling window). Phase A: short pseudo-random "
                       "vector deterministically derived from action timestamps.",
        "payload_schema": {
            "vector": "array[number] length=8",
            "window_days": "integer",
        },
    },
    {
        "signal_type": "compliance_trigger",
        "signal_category": "compliance",
        "description": "Event with compliance significance — large transaction, "
                       "regulated activity, threshold breach. Phase A: derived "
                       "from monitor flagged objectives.",
        "payload_schema": {
            "trigger_kind": "string",
            "threshold": "number",
        },
    },
    {
        "signal_type": "operational_health",
        "signal_category": "operational",
        "description": "Aggregate operational state — queue depths, error "
                       "rates, throughput. Phase A: derived from work_studio "
                       "compilation rail counts.",
        "payload_schema": {
            "queue_depth": "integer",
            "error_rate": "number",
        },
    },
]


def catalogue() -> List[SignalTypeDefinition]:
    return [SignalTypeDefinition(**row) for row in _CATALOGUE]


def types_by_category(category: str) -> List[str]:
    return [r["signal_type"] for r in _CATALOGUE
            if r["signal_category"] == category]
