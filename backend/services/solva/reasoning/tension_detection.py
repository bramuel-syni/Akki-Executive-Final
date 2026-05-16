"""Tension Detection — Solva Phase D, Layer 2.

Phase D scope is BASIC tension detection: hybrid rule + Shield-routed
LLM call that classifies internal inconsistency across the narrative
+ evidence + prior context. Phase E will add auto-activation inside
Simulate Hypothesis (brief §7).
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..orchestration.shield_invoker import invoke_via_shield


ENGINE = "tension_detection"
ENGINE_VERSION = "tension_detection@1.0"


class Tension(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str
    severity: str = "minor"  # minor | material | critical
    category: str = "narrative_evidence"  # narrative_evidence | internal_narrative | prior_context


class TensionDetectionOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tensions: List[Tension]
    audit_id: Optional[str] = None
    orchestration_entries: List[Dict[str, Any]] = Field(default_factory=list)


# Rule-based tension patterns — fire on EITHER narrative-vs-evidence
# or known executive-framing pitfalls.
_RULE_PATTERNS: List[Dict[str, Any]] = [
    {
        "regex": re.compile(r"\b(but|however|on the other hand|whereas)\b.*\b(actually|in fact|in reality)\b", re.I | re.S),
        "category": "internal_narrative",
        "severity": "material",
        "description": "Narrative contains a self-contradiction marker.",
    },
    {
        "regex": re.compile(r"\b(always|never|definitely will|guaranteed)\b", re.I),
        "category": "narrative_evidence",
        "severity": "minor",
        "description": "Absolute language without evidence-backed citation.",
    },
]


async def detect_tensions(
    *,
    narrative_text: str,
    evidence_chunks: List[str],
    tenant_id: str,
    user_id: str,
) -> TensionDetectionOutput:
    rules_fired: List[Tension] = []
    for pat in _RULE_PATTERNS:
        if pat["regex"].search(narrative_text or ""):
            rules_fired.append(Tension(
                description=pat["description"],
                severity=pat["severity"],
                category=pat["category"],
            ))

    prompt = json.dumps({
        "task": "tension_detection",
        "narrative": (narrative_text or "")[:1600],
        "evidence": "\n---\n".join((evidence_chunks or [])[:4])[:1000],
        "guidance": (
            "Identify internal inconsistencies, narrative-vs-evidence "
            "contradictions, and pre-loaded framing. Return at most 3 "
            "tensions, each with description + severity (minor|material|critical) "
            "+ category."
        ),
    }, ensure_ascii=False)
    shield_res = await invoke_via_shield(
        purpose="solva.layer_2.tension_detection",
        prompt=prompt,
        tenant_id=tenant_id,
        user_id=user_id,
        layer="layer_2",
        engine=ENGINE,
        engine_version=ENGINE_VERSION,
        input_hash=hashlib.sha256(prompt.encode()).hexdigest(),
    )
    body = shield_res.response_text or ""
    llm_tensions: List[Tension] = []
    preamble = re.compile(
        r"^\s*(here (are|is)|the following|below (are|is)|tensions?:?$|"
        r"i'll provide|let me|sure[,!.]|of course|certainly)",
        re.I,
    )
    md_label = re.compile(r"\*{2}[^*]{1,40}\*{2}\s*:?\s*", re.I)
    layer_ref = re.compile(r"\b(layer[\s_]?[0-9]+|in the layer\s+[0-9]+)\b", re.I)
    for line in body.splitlines():
        line = line.strip()
        if not line or len(line) < 12 or preamble.match(line):
            continue
        # Tolerant parse: look for lines beginning with bullet or number.
        m = re.match(r"^\s*(?:\d+[\.\)]|[-*•])\s*(.+)$", line)
        if not m:
            continue
        text = md_label.sub("", m.group(1)).strip(" -*:")
        # Strip "Layer N" references — they leak orchestration state to user.
        text = layer_ref.sub("the framing", text)
        severity = "material" if "critical" in text.lower() or "material" in text.lower() else "minor"
        if "contradict" in text.lower() or "inconsistent" in text.lower():
            severity = "material"
        llm_tensions.append(Tension(
            description=text[:200],
            severity=severity,
            category="narrative_evidence",
        ))
        if len(llm_tensions) >= 3:
            break

    return TensionDetectionOutput(
        tensions=(rules_fired + llm_tensions)[:5],
        audit_id=shield_res.audit_id,
        orchestration_entries=[shield_res.orchestration_entry],
    )


def auto_activate(
    *,
    candidates: List[Dict[str, Any]],
    triangulation_result: Dict[str, Any],
    detected_tensions: List[Dict[str, Any]],
    sub_module: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase E Sub-task C (2026-05-16) — decide whether the session
    has surfaced enough tension to ESCALATE in Layer 2 (additional
    probe question + tension-flagged synthesis variant).

    Triggers when ANY of:
      (1) two candidates have weight intervals (±0.10 band) that don't
          overlap;
      (2) one candidate weight > 0.5 AND another > 0.25;
      (3) tension_detection emitted a `material` or `critical` tension;
      (4) triangulation flagged a `material`/`critical` divergence.

    Always-on for `simulate_hypothesis` per brief §3.4.2 — that
    sub-module exists to test claims, so tension acknowledgement is
    its default mode.
    """
    if sub_module == "simulate_hypothesis":
        return {
            "activated": True,
            "reason": "simulate_hypothesis_default",
            "tension_question_key": f"{sub_module}.layer_2.probe.tension_invitation",
            "synthesis_variant": "tension_flagged",
        }

    weights = sorted(
        [(c.get("id"), float(c.get("weight", 0.0))) for c in candidates or []],
        key=lambda x: -x[1],
    )
    if len(weights) >= 2:
        w_a = weights[0][1]
        w_b = weights[1][1]
        # Trigger 1 — non-overlapping intervals (±0.10 band each).
        a_lo, a_hi = w_a - 0.10, w_a + 0.10
        b_lo, b_hi = w_b - 0.10, w_b + 0.10
        if a_lo > b_hi or b_lo > a_hi:
            return {
                "activated": True,
                "reason": "non_overlapping_weight_bands",
                "tension_question_key": f"{sub_module or 'seek_clarity'}.layer_2.probe.tension_invitation",
                "synthesis_variant": "tension_flagged",
            }
        # Trigger 2 — lead > 0.5 with second > 0.25.
        if w_a > 0.5 and w_b > 0.25:
            return {
                "activated": True,
                "reason": "lead_dominant_with_strong_alternate",
                "tension_question_key": f"{sub_module or 'seek_clarity'}.layer_2.probe.tension_invitation",
                "synthesis_variant": "tension_flagged",
            }

    # Trigger 3 — material/critical tension already detected.
    for t in detected_tensions or []:
        if (t.get("severity") or "minor") in ("material", "critical"):
            return {
                "activated": True,
                "reason": "material_tension_detected",
                "tension_question_key": f"{sub_module or 'seek_clarity'}.layer_2.probe.tension_invitation",
                "synthesis_variant": "tension_flagged",
            }

    # Trigger 4 — triangulation contradiction.
    align = (triangulation_result or {}).get("divergences") or []
    if any((d.get("severity") or "minor") in ("material", "critical") for d in align):
        return {
            "activated": True,
            "reason": "triangulation_contradiction",
            "tension_question_key": f"{sub_module or 'seek_clarity'}.layer_2.probe.tension_invitation",
            "synthesis_variant": "tension_flagged",
        }

    return {
        "activated": False,
        "reason": "no_tension_surfaced",
        "tension_question_key": None,
        "synthesis_variant": "neutral",
    }

