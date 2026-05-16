"""Probability Weighting — Solva Phase D, Layer 3.

Two Shield-routed LLM calls:
  1. `solva.layer_3.scenario_narrative_generation` — render 3-5
     scenarios from the refined candidate set.
  2. `solva.layer_3.synthesis_rendering` — produce the coach-voice
     primary diagnosis prose (consumed by `voice/synthesis_renderer`).

Probability assignment + confidence intervals are DETERMINISTIC
(no LLM). The 4 inputs (candidate weights, triangulation alignment,
class priors, counterfactual robustness) are aggregated by a rule
function. Weights normalise to 1.0.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from ..orchestration.shield_invoker import (
    invoke_via_shield,
    build_orchestration_entry_deterministic,
)


ENGINE = "probability_weighting"
ENGINE_VERSION = "probability_weighting@1.0"

CALIBRATION_VERSION = "phase_d.v0"  # locked for Phase D; Phase E retunes.


class Scenario(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    description: str
    weight: float
    confidence_interval_low: float
    confidence_interval_high: float


class SensitivityDriver(BaseModel):
    model_config = ConfigDict(extra="ignore")
    input_name: str
    shift_potential: float
    description: str


class ProbabilityWeightingOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    scenarios: List[Scenario]
    sensitivity_drivers: List[SensitivityDriver]
    calibration_version: str = CALIBRATION_VERSION
    audit_ids: List[str] = Field(default_factory=list)
    orchestration_entries: List[Dict[str, Any]] = Field(default_factory=list)


def _aggregate_weights(
    *,
    candidates: List[Dict[str, Any]],
    triangulation_alignment: float,
    class_priors: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """Compute one probability per candidate from the four inputs.

    Weights set:
      - candidate.weight             (0.50)
      - triangulation_alignment      (0.25 — boosts all if high consistency)
      - class_prior                  (0.15 — boost when candidate id matches a prior)
      - counterfactual_robustness    (0.10 — approximated by candidate type spread)
    """
    priors = class_priors or {}
    raw: Dict[str, float] = {}
    for c in candidates:
        cw = float(c.get("weight", 0.2))
        prior = float(priors.get(c.get("id", ""), 0.2))
        cf = 0.1  # uniform Phase D — Phase E calibrates per type.
        score = (0.50 * cw) + (0.25 * triangulation_alignment) + (0.15 * prior) + (0.10 * cf)
        raw[c.get("id", "cand-unknown")] = max(0.0, score)
    total = sum(raw.values()) or 1.0
    return {k: v / total for k, v in raw.items()}


def _confidence_interval(weight: float, evidence_strength: float) -> Tuple[float, float]:
    """Wider intervals when evidence_strength is low."""
    half_width = (1.0 - max(0.0, min(1.0, evidence_strength))) * 0.20 + 0.05
    low = max(0.0, weight - half_width)
    high = min(1.0, weight + half_width)
    return round(low, 2), round(high, 2)


async def weight_scenarios(
    *,
    candidates: List[Dict[str, Any]],
    triangulation_alignment: float,
    sub_module: str,
    framing_text: str,
    tenant_id: str,
    user_id: str,
    class_priors: Optional[Dict[str, float]] = None,
) -> ProbabilityWeightingOutput:
    orch: List[Dict[str, Any]] = []
    audit_ids: List[str] = []

    # Step 1: scenario narrative generation (Shield-routed).
    sprompt = json.dumps({
        "task": "scenario_narratives",
        "sub_module": sub_module,
        "candidates": candidates[:5],
        "guidance": (
            "For each candidate, write ONE short scenario narrative (≤2 sentences) "
            "naming the situation if that candidate is the dominant explanation. "
            "Avoid hedging."
        ),
    }, ensure_ascii=False)
    sres = await invoke_via_shield(
        purpose="solva.layer_3.scenario_narrative_generation",
        prompt=sprompt,
        tenant_id=tenant_id,
        user_id=user_id,
        layer="layer_3",
        engine=ENGINE + ".scenario_narrative",
        engine_version=ENGINE_VERSION,
        input_hash=hashlib.sha256(sprompt.encode()).hexdigest(),
    )
    orch.append(sres.orchestration_entry)
    audit_ids.append(sres.audit_id)

    # Step 2: deterministic probability assignment.
    weights = _aggregate_weights(
        candidates=candidates,
        triangulation_alignment=triangulation_alignment,
        class_priors=class_priors,
    )
    orch.append(build_orchestration_entry_deterministic(
        layer="layer_3",
        engine=ENGINE + ".probability_assignment",
        engine_version=ENGINE_VERSION,
        output_summary={
            "calibration_version": CALIBRATION_VERSION,
            "weights": weights,
            "triangulation_alignment": triangulation_alignment,
        },
    ))

    # Step 3: parse narratives + assemble scenarios.
    narratives = _split_into_chunks(sres.response_text or "", n=max(3, len(candidates)))
    scenarios: List[Scenario] = []
    evidence_strength = max(0.1, triangulation_alignment)
    for i, cand in enumerate(candidates[:5]):
        w = weights.get(cand["id"], 1.0 / max(1, len(candidates)))
        low, high = _confidence_interval(w, evidence_strength)
        narrative = narratives[i] if i < len(narratives) else cand.get("description", "")
        scenarios.append(Scenario(
            id="scn-" + cand["id"][-8:],
            name=cand.get("description", "Candidate scenario")[:60],
            description=narrative[:300],
            weight=round(w, 3),
            confidence_interval_low=low,
            confidence_interval_high=high,
        ))

    # Step 4: sensitivity drivers — pick the candidates whose weight
    # delta is largest if we perturb triangulation_alignment by ±0.2.
    drivers = _sensitivity_perturb(candidates, triangulation_alignment, class_priors)
    orch.append(build_orchestration_entry_deterministic(
        layer="layer_3",
        engine=ENGINE + ".sensitivity",
        engine_version=ENGINE_VERSION,
        output_summary={"drivers": [d.model_dump() for d in drivers]},
    ))

    return ProbabilityWeightingOutput(
        scenarios=scenarios,
        sensitivity_drivers=drivers,
        audit_ids=audit_ids,
        orchestration_entries=orch,
    )


def _split_into_chunks(text: str, n: int) -> List[str]:
    """Split LLM response into roughly N narrative chunks. Tolerant
    to bulleted, numbered, or paragraph formats. Skips LLM preambles
    and Markdown field labels."""
    preamble = re.compile(
        r"^\s*(here (are|is)|the following|below (are|is)|"
        r"scenarios?:?$|candidates?:?$|i'll provide|let me|sure[,!.]|"
        r"of course|certainly)",
        re.I,
    )
    md_label = re.compile(r"\*{2}[^*]{1,40}\*{2}\s*:?\s*", re.I)
    lines = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s or preamble.match(s):
            continue
        s = md_label.sub("", s)
        lines.append(s)
    chunks: List[str] = []
    for ln in lines:
        m = re.match(r"^\s*(?:\d+[\.\)]|[-*•])\s*(.+)$", ln)
        if m:
            chunks.append(m.group(1))
        elif len(ln) > 25:
            chunks.append(ln)
    return chunks[:max(1, n)]


def _sensitivity_perturb(
    candidates: List[Dict[str, Any]],
    alignment: float,
    priors: Optional[Dict[str, float]],
) -> List[SensitivityDriver]:
    base = _aggregate_weights(
        candidates=candidates, triangulation_alignment=alignment, class_priors=priors,
    )
    drivers: List[SensitivityDriver] = []
    # Perturb triangulation_alignment.
    new_high = _aggregate_weights(
        candidates=candidates, triangulation_alignment=min(1.0, alignment + 0.2),
        class_priors=priors,
    )
    diff = max(abs(new_high.get(k, 0) - base.get(k, 0)) for k in base) if base else 0.0
    drivers.append(SensitivityDriver(
        input_name="triangulation_alignment",
        shift_potential=round(diff, 3),
        description="If new evidence aligned more strongly with the narrative, weights shift here.",
    ))
    return drivers
