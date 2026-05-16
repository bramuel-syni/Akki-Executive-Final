"""Situation Class Classifier — Solva Phase D, Layer 0.

Picks one of ~30 canonical executive situation classes for the framing.
Each class has a versioned audit profile + candidate template that
later reasoning models read (the brief calls these "data, not code"
per §4.2). The classifier itself runs deterministic keyword matching
PLUS a Shield-routed LLM call that picks the closest class when
the keyword pass scores below threshold.

The class is INTERNAL — never rendered to the user. It informs
candidate generation and the question bank's per-class variants.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..orchestration.shield_invoker import (
    invoke_via_shield,
    build_orchestration_entry_deterministic,
)


ENGINE = "situation_class_classifier"
ENGINE_VERSION = "situation_class_classifier@1.0"


# 30 canonical executive classes per brief §4.2.
SITUATION_CLASSES: Dict[str, List[str]] = {
    # class_id: keywords list (case-insensitive substring match)
    "customer_concentration_risk":       ["concentration", "top customer", "key account", "anchor client"],
    "capital_allocation":                ["capital", "buyback", "dividend", "leverage", "balance sheet"],
    "team_capacity_gap":                 ["capacity", "headcount", "team", "hiring", "burnout"],
    "competitive_positioning":           ["competitor", "competitive", "market share", "rival", "positioning"],
    "board_succession":                  ["succession", "chair retire", "ned exit", "incoming ceo"],
    "regulatory_shift":                  ["regulator", "regulation", "compliance", "licence"],
    "revenue_underperformance":          ["revenue miss", "guidance miss", "shortfall", "topline"],
    "tech_debt_or_outage":               ["tech debt", "outage", "incident", "cyber", "breach", "platform"],
    "people_conduct":                    ["misconduct", "harassment", "investigation", "ethics"],
    "performance_management":            ["performance review", "underperforming", "kpi miss"],
    "ma_thesis":                         ["acquisition", "acquire", "merger", "m&a", "deal", "target company"],
    "founder_transition":                ["founder", "step back", "step down"],
    "ceo_succession":                    ["ceo retire", "successor", "next ceo"],
    "strategy_drift":                    ["strategic drift", "five-year plan", "vision", "drifted"],
    "risk_blindspot":                    ["blind spot", "blindspot", "tail risk", "unhedged"],
    "board_dynamics":                    ["board dynamics", "chair ", "non-executive", "ned "],
    "fundraising":                       ["fundrais", "rights issue", "raise capital", "investor round"],
    "product_pivot":                     ["pivot", "product strategy", "feature cut"],
    "customer_churn":                    ["churn", "lapse", "attrition", "renewal rate"],
    "operational_efficiency":            ["efficiency", "cost-out", "automation", "throughput"],
    "supply_chain_disruption":           ["supply chain", "supplier", "logistics", "shortage"],
    "market_entry":                      ["market entry", "expansion", "new market", "geographic"],
    "talent_retention":                  ["retention", "key talent", "departure", "leaver"],
    "esg_or_sustainability":             ["esg", "sustainab", "carbon", "emissions"],
    "data_or_ai_strategy":               ["data strategy", "ai strategy", "machine learning"],
    "pricing_strategy":                  ["pricing", "discount", "list price"],
    "brand_or_reputation":               ["brand", "reputation", "press"],
    "litigation_or_legal":               ["litigation", "lawsuit", "court", "settlement"],
    "investment_thesis":                 ["investment thesis", "portfolio company", "deal review"],
    "other_strategic":                   [],  # catch-all
}

DEFAULT_CLASS = "other_strategic"


class SituationClassOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    situation_class: str
    confidence: float
    keyword_matches: List[str] = Field(default_factory=list)
    audit_id: Optional[str] = None
    orchestration_entries: List[Dict[str, Any]] = Field(default_factory=list)


def _score_keyword_pass(text: str) -> Dict[str, Any]:
    """Score every class by keyword hits. Returns the best match + all hits."""
    lower = (text or "").lower()
    best_class = DEFAULT_CLASS
    best_score = 0
    matches: List[str] = []
    for cid, kws in SITUATION_CLASSES.items():
        if not kws:
            continue
        hits = [k for k in kws if k in lower]
        if hits:
            score = len(hits)
            if score > best_score:
                best_score = score
                best_class = cid
                matches = hits
    return {"class_id": best_class, "score": best_score, "matches": matches}


async def classify_situation(
    *,
    framing_text: str,
    tenant_id: str,
    user_id: str,
) -> SituationClassOutput:
    orch: List[Dict[str, Any]] = []
    det = _score_keyword_pass(framing_text)
    orch.append(build_orchestration_entry_deterministic(
        layer="layer_0",
        engine=ENGINE + ".keyword_pass",
        engine_version=ENGINE_VERSION,
        output_summary={"class_id": det["class_id"], "score": det["score"]},
    ))

    # Confidence: 1.0 for ≥2 keyword hits, 0.6 for 1 hit, 0.0 otherwise.
    if det["score"] >= 2:
        return SituationClassOutput(
            situation_class=det["class_id"],
            confidence=1.0,
            keyword_matches=det["matches"],
            orchestration_entries=orch,
        )

    # LLM refinement under `solva.layer_0.situation_classification`.
    prompt = json.dumps({
        "task": "classify_situation",
        "framing": framing_text[:1800],
        "allowed_classes": list(SITUATION_CLASSES.keys()),
        "guidance": "Pick ONE class id from allowed_classes. If none fit, pick 'other_strategic'.",
    }, ensure_ascii=False)
    shield_res = await invoke_via_shield(
        purpose="solva.layer_0.situation_classification",
        prompt=prompt,
        tenant_id=tenant_id,
        user_id=user_id,
        layer="layer_0",
        engine=ENGINE,
        engine_version=ENGINE_VERSION,
        input_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    )
    orch.append(shield_res.orchestration_entry)
    body = (shield_res.response_text or "").lower()

    chosen = DEFAULT_CLASS
    confidence = 0.0
    for cid in SITUATION_CLASSES.keys():
        if cid in body:
            chosen = cid
            confidence = 0.7
            break
    if det["score"] == 1 and chosen == DEFAULT_CLASS:
        # Keyword-pass winner survives if the LLM didn't beat it.
        chosen = det["class_id"]
        confidence = 0.6

    return SituationClassOutput(
        situation_class=chosen,
        confidence=confidence,
        keyword_matches=det["matches"],
        audit_id=shield_res.audit_id,
        orchestration_entries=orch,
    )
