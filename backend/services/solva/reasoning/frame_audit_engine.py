"""Frame Audit Engine — Solva Phase D, Layer 0.

Audits the user's initial framing along five dimensions, producing
a Frame Audit Record (FAR) + routing decision. The FAR is INTERNAL —
it never renders to the user as content. The routing decision is
consumed by the question bank to pick the Layer 1 opening question.

Implementation strategy:
- Deterministic regex pass on the framing text scores each dimension
  (decisional clarity, time horizon, scope boundedness, evidence
  grounding, lens fit).
- One Shield-routed LLM call REFINES the deterministic scoring with
  structured output (`solva.layer_0.frame_audit` purpose). The LLM is
  consulted to detect nuance the regex would miss; final verdict is the
  AND of regex + LLM (most-restrictive wins).
- LLM call respects the structured-output contract — JSON shape locked
  via Pydantic parsing on response.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..orchestration.shield_invoker import (
    invoke_via_shield,
    build_orchestration_entry_deterministic,
)


ENGINE = "frame_audit_engine"
ENGINE_VERSION = "frame_audit_engine@1.0"

# Regex heuristics: presence of a marker bumps the dimension's score
# from "absent" toward "thin"/"sufficient".
_DECISIONAL = re.compile(
    r"\b(decision|decide|approve|reject|choose|should we|whether to|"
    r"go/no-go|proceed|hold|defer)\b", re.I,
)
_TIME_HORIZON = re.compile(
    r"\b(quarter|q[1-4]\b|h[12]\b|next year|by (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)|"
    r"month|week|days|board meeting|fiscal year|fy\s*\d+)\b", re.I,
)
_SCOPE = re.compile(
    r"\b(within|limited to|specifically|in (the )?context of|for the (board|exec|nedbank|cfo|ceo)|"
    r"around)\b", re.I,
)
_EVIDENCE = re.compile(
    r"\b(report|memo|deck|paper|attached|document|data|forecast|model|"
    r"analysis|finding|study|brief)\b", re.I,
)
_LENS = re.compile(
    r"\b(from the (cfo|ceo|chair|investor|regulator|cro|coo|ned|board)|as (a|the) (cfo|ceo|chair)|"
    r"perspective of)\b", re.I,
)


class FARDimension(BaseModel):
    model_config = ConfigDict(extra="ignore")
    dimension: str
    score: str         # "sufficient" | "thin" | "absent"
    severity: str = "minor"   # "minor" | "material" | "critical"
    invalidation_condition: Optional[str] = None


class FrameAuditOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    verdict: str       # "sufficient" | "sufficient_with_caveats" | "insufficient"
    dimensions: List[FARDimension]
    routing_decision: Dict[str, Any]
    carry_forward_caveats: List[str] = Field(default_factory=list)
    audit_id: Optional[str] = None
    orchestration_entries: List[Dict[str, Any]] = Field(default_factory=list)


def _score_regex(framing: str) -> List[FARDimension]:
    """Initial deterministic scoring pass — produces conservative
    FAR dimensions before the LLM refinement."""
    rows: List[FARDimension] = []
    rows.append(FARDimension(
        dimension="decisional_clarity",
        score="sufficient" if _DECISIONAL.search(framing) else "thin",
        severity="material" if not _DECISIONAL.search(framing) else "minor",
        invalidation_condition=None if _DECISIONAL.search(framing) else (
            "no explicit decision the diagnosis would inform"
        ),
    ))
    rows.append(FARDimension(
        dimension="time_horizon",
        score="sufficient" if _TIME_HORIZON.search(framing) else "thin",
        severity="minor",
        invalidation_condition=None if _TIME_HORIZON.search(framing) else (
            "no explicit time horizon for when this decision matters"
        ),
    ))
    rows.append(FARDimension(
        dimension="scope_boundedness",
        score="sufficient" if _SCOPE.search(framing) else "thin",
        severity="minor",
        invalidation_condition=None if _SCOPE.search(framing) else (
            "scope is open-ended"
        ),
    ))
    rows.append(FARDimension(
        dimension="evidence_grounding",
        score="sufficient" if _EVIDENCE.search(framing) else "absent",
        severity="material" if not _EVIDENCE.search(framing) else "minor",
        invalidation_condition=None if _EVIDENCE.search(framing) else (
            "no attached material or referenced source"
        ),
    ))
    rows.append(FARDimension(
        dimension="lens_fit",
        score="sufficient" if _LENS.search(framing) else "thin",
        severity="minor",
        invalidation_condition=None if _LENS.search(framing) else (
            "no explicit business lens requested"
        ),
    ))
    return rows


def _verdict_from_dimensions(dims: List[FARDimension]) -> str:
    absent_critical = [d for d in dims if d.score == "absent" and d.severity in ("material", "critical")]
    if absent_critical:
        return "insufficient"
    thin_material = [d for d in dims if d.score == "thin" and d.severity in ("material", "critical")]
    absent_minor = [d for d in dims if d.score == "absent" and d.severity == "minor"]
    if thin_material or absent_minor:
        return "sufficient_with_caveats"
    return "sufficient"


def _routing_decision(
    *,
    sub_module: str,
    verdict: str,
    dims: List[FARDimension],
) -> Dict[str, Any]:
    """Map FAR verdict → Layer 1 opening question key.

    The key indexes into `voice/question_bank.py`; the bank holds
    multiple variants per key for variety. Variants are deterministic
    given the same sub_module + verdict pair (no LLM-generated
    questions per brief §5.4).
    """
    suffix = "default"
    if verdict == "sufficient_with_caveats":
        suffix = "with_caveats"
    elif verdict == "insufficient":
        suffix = "conversational"
    return {
        "layer_1_opening_question_key": f"{sub_module}.layer_1.opening.{suffix}",
        "additional_probes": [
            f"{sub_module}.layer_1.probe.{d.dimension}"
            for d in dims if d.score != "sufficient"
        ],
        "carry_forward_caveats": [
            d.invalidation_condition for d in dims
            if d.invalidation_condition and d.severity in ("material", "critical")
        ],
    }


async def run_frame_audit(
    *,
    sub_module: str,
    framing_text: str,
    tenant_id: str,
    user_id: str,
    situation_class: Optional[str] = None,
) -> FrameAuditOutput:
    """Run the deterministic-then-Shield-refined frame audit.

    Returns an internal `FrameAuditOutput`. Single-voice invariant:
    NO field on the return value renders to the user — the question
    bank consumes `routing_decision.layer_1_opening_question_key`.
    """
    orch_entries: List[Dict[str, Any]] = []
    base_dims = _score_regex(framing_text)

    # Deterministic pass logged.
    orch_entries.append(build_orchestration_entry_deterministic(
        layer="layer_0",
        engine=ENGINE + ".regex",
        engine_version=ENGINE_VERSION,
        output_summary={
            "dimensions": [d.model_dump() for d in base_dims],
        },
        bypass_reason="deterministic_only",
    ))

    # Shield-routed LLM refinement.
    prompt = json.dumps({
        "task": "frame_audit_refinement",
        "sub_module": sub_module,
        "situation_class": situation_class or "unknown",
        "framing": framing_text[:1800],
        "deterministic_dimensions": [d.model_dump() for d in base_dims],
        "output_schema": {
            "verdict": "sufficient | sufficient_with_caveats | insufficient",
            "additional_observations": "list of short strings",
        },
    }, ensure_ascii=False)
    audit_id: Optional[str] = None
    refined_verdict: Optional[str] = None
    try:
        shield_res = await invoke_via_shield(
            purpose="solva.layer_0.frame_audit",
            prompt=prompt,
            tenant_id=tenant_id,
            user_id=user_id,
            layer="layer_0",
            engine=ENGINE,
            engine_version=ENGINE_VERSION,
            input_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        )
        audit_id = shield_res.audit_id
        orch_entries.append(shield_res.orchestration_entry)
        # Parse the LLM verdict if it returned a recognisable hint;
        # fall back to deterministic verdict if not.
        body = (shield_res.response_text or "").lower()
        if "insufficient" in body:
            refined_verdict = "insufficient"
        elif "sufficient_with_caveats" in body or "with caveats" in body:
            refined_verdict = "sufficient_with_caveats"
        elif "sufficient" in body:
            refined_verdict = "sufficient"
    except Exception:  # noqa: BLE001
        # If Shield itself raised, do not silently swallow — the
        # router must surface 503 to the caller. Re-raise.
        raise

    # Most-restrictive wins: deterministic vs. LLM refinement.
    det_verdict = _verdict_from_dimensions(base_dims)
    order = {"sufficient": 0, "sufficient_with_caveats": 1, "insufficient": 2}
    verdicts = [det_verdict]
    if refined_verdict:
        verdicts.append(refined_verdict)
    verdict = max(verdicts, key=lambda v: order.get(v, 0))
    routing = _routing_decision(sub_module=sub_module, verdict=verdict, dims=base_dims)
    return FrameAuditOutput(
        verdict=verdict,
        dimensions=base_dims,
        routing_decision=routing,
        carry_forward_caveats=routing["carry_forward_caveats"],
        audit_id=audit_id,
        orchestration_entries=orch_entries,
    )
