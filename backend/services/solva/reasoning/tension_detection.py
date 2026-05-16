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
