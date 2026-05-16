"""Candidate Generation — Solva Phase D, Layer 1 + Layer 2 refinement.

Layer 1: produces 5-7 candidates from the framing + situation class +
FAR. Candidates are typed: cause | strategy | hypothesis | perspective
(depending on sub-module). Each carries an `evidence_requirement` field
specifying what would confirm or refute it.

Layer 2 refinement (`refine_candidates`): processes each Layer 2 answer
to adjust weights and add new candidates (max 8 total).

INTERNAL artefact — candidates do not render to the user directly. The
voice tier's `synthesis_renderer` consumes them at Layer 3.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..orchestration.shield_invoker import invoke_via_shield


ENGINE = "candidate_generation"
ENGINE_VERSION = "candidate_generation@1.0"

MAX_CANDIDATES = 8
TARGET_CANDIDATES = 5

SUB_MODULE_TO_CANDIDATE_TYPE: Dict[str, str] = {
    "seek_clarity":        "cause",
    "develop_strategy":    "strategy",
    "simulate_hypothesis": "hypothesis",
    "get_perspective":     "perspective",
}


class Candidate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    candidate_type: str
    description: str
    evidence_requirement: str
    prior_probability: float = 0.2
    weight: float = 0.2
    source: str = "layer_1"


class CandidateGenerationOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    candidates: List[Candidate]
    audit_id: Optional[str] = None
    orchestration_entries: List[Dict[str, Any]] = Field(default_factory=list)


_BULLET_LINE_RE = re.compile(r"^\s*(?:\d+[\.\)]|[-*•])\s*(.+?)\s*$")

# Lines that LLMs prepend before lists. Skipped during parsing.
_PREAMBLE_RE = re.compile(
    r"^\s*(here (are|is)|the following|below (are|is)|candidates?:?$|"
    r"scenarios?:?$|options?:?$|i'll provide|let me|sure[,!.]|"
    r"of course|certainly)",
    re.I,
)

# Markdown bold marker for field labels e.g. "**Description**:".
_MARKDOWN_LABEL_RE = re.compile(
    r"^\s*\*{2}[^*]{1,40}\*{2}\s*:?\s*", re.I,
)


def _parse_candidates_from_text(body: str, ctype: str) -> List[Candidate]:
    """Tolerant parser — accepts bullets, numbered lists, or short lines.

    Skips LLM preambles and strips Markdown field labels. Never emits
    a candidate whose description is shorter than 12 characters."""
    out: List[Candidate] = []
    seen: set[str] = set()
    for line in (body or "").splitlines():
        if _PREAMBLE_RE.match(line):
            continue
        m = _BULLET_LINE_RE.match(line)
        text = m.group(1) if m else line.strip()
        text = _MARKDOWN_LABEL_RE.sub("", text).strip(" -*:")
        if not text or len(text) < 12:
            continue
        # Drop trailing "(evidence: ...)" decoration for the description.
        evid_match = re.search(r"\(\s*evidence[:\-]\s*(.+?)\s*\)", text, re.I)
        evidence = evid_match.group(1) if evid_match else (
            "evidence from attached material or referenced source"
        )
        desc = re.sub(r"\(\s*evidence[:\-].+?\)", "", text, flags=re.I).strip(" .-:;")
        # Reject anything still looking like layer-internal vocabulary.
        if re.search(r"\b(layer\s*[0-9]|frame audit|candidate set)\b", desc, re.I):
            continue
        if desc.lower() in seen:
            continue
        seen.add(desc.lower())
        out.append(Candidate(
            id=f"cand-{hashlib.sha1(desc.encode('utf-8')).hexdigest()[:10]}",
            candidate_type=ctype,
            description=desc[:240],
            evidence_requirement=evidence[:240],
        ))
        if len(out) >= TARGET_CANDIDATES:
            break
    return out


def _fallback_candidates(ctype: str, framing: str, n: int = 5) -> List[Candidate]:
    """Stable fallback set when the LLM didn't return parseable
    candidates. Generic but valid Pydantic shapes."""
    templates = [
        ("internal_capability_gap",      "An internal capability gap that is upstream of the visible symptom."),
        ("external_market_shift",        "An external market shift the user has not fully named."),
        ("stakeholder_misalignment",     "A misalignment between stakeholders that is bending decisions."),
        ("operational_drift",            "Operational drift that has compounded since the last review."),
        ("strategic_assumption_failure", "A strategic assumption that no longer holds against current evidence."),
    ][:n]
    return [
        Candidate(
            id=f"cand-{slug}-{hashlib.sha1((framing + slug).encode()).hexdigest()[:6]}",
            candidate_type=ctype,
            description=desc,
            evidence_requirement="material or document referenced in the user's framing",
            prior_probability=round(1.0 / max(1, n), 2),
            weight=round(1.0 / max(1, n), 2),
        )
        for slug, desc in templates
    ]


async def generate_candidates(
    *,
    framing_text: str,
    sub_module: str,
    situation_class: str,
    far_routing: Dict[str, Any],
    tenant_id: str,
    user_id: str,
    layer_1_answers: Optional[List[Dict[str, Any]]] = None,
) -> CandidateGenerationOutput:
    ctype = SUB_MODULE_TO_CANDIDATE_TYPE.get(sub_module, "cause")
    prompt = json.dumps({
        "task": "candidate_generation",
        "sub_module": sub_module,
        "candidate_type": ctype,
        "situation_class": situation_class,
        "framing": framing_text[:1500],
        "far_routing": far_routing,
        "layer_1_answers": (layer_1_answers or [])[:6],
        "target_count": TARGET_CANDIDATES,
        "output_schema": "list of objects with: description, evidence_requirement",
    }, ensure_ascii=False)
    shield_res = await invoke_via_shield(
        purpose="solva.layer_1.candidate_generation",
        prompt=prompt,
        tenant_id=tenant_id,
        user_id=user_id,
        layer="layer_1",
        engine=ENGINE,
        engine_version=ENGINE_VERSION,
        input_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    )
    parsed = _parse_candidates_from_text(shield_res.response_text or "", ctype)
    if len(parsed) < 3:
        parsed = _fallback_candidates(ctype, framing_text)
    return CandidateGenerationOutput(
        candidates=parsed[:MAX_CANDIDATES],
        audit_id=shield_res.audit_id,
        orchestration_entries=[shield_res.orchestration_entry],
    )


def refine_candidates(
    *,
    existing: List[Dict[str, Any]],
    layer_2_signal: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Pure-rule refinement: bumps weights of candidates aligned with
    the Layer 2 triangulation signal; demotes contradicted ones; caps
    at MAX_CANDIDATES. NO LLM call — deterministic.
    """
    out: List[Dict[str, Any]] = []
    supporting = set(layer_2_signal.get("supporting_candidate_ids") or [])
    contradicting = set(layer_2_signal.get("contradicting_candidate_ids") or [])
    for c in existing:
        cid = c.get("id")
        w = float(c.get("weight", 0.2))
        if cid in supporting:
            w = min(0.9, w + 0.15)
        if cid in contradicting:
            w = max(0.05, w - 0.15)
        c["weight"] = round(w, 3)
        out.append(c)
    # Normalise weights so they sum to ~1.0 (rounding tolerated).
    total = sum(c["weight"] for c in out) or 1.0
    for c in out:
        c["weight"] = round(c["weight"] / total, 3)
    return out[:MAX_CANDIDATES]
