"""Triangulation Engine — Solva Phase D, Layer 2.

Pairwise consistency checks across:
  - narrative (Layer 1 + 2 answers)
  - attached evidence (uploaded materials)
  - prior context (Synisense Engine signals)

Two Shield-routed sub-calls:
  1. `solva.layer_2.triangulation.claim_extraction` — extract factual
     claims from the user narrative.
  2. `solva.layer_2.triangulation.entailment_classification` — per
     claim, classify against evidence chunks (entails | contradicts |
     not-mentioned).

Divergences carry source citations and are surfaced in Layer 3 by the
voice tier.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..orchestration.shield_invoker import invoke_via_shield


ENGINE = "triangulation_engine"
ENGINE_VERSION = "triangulation_engine@1.0"


class Divergence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    claim: str
    sources: List[str] = Field(default_factory=list)
    severity: str = "minor"  # minor | material | critical
    divergence_type: str = "narrative_vs_evidence"


class TriangulationOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    overall_consistency: float
    divergences: List[Divergence]
    alignments: List[Dict[str, Any]] = Field(default_factory=list)
    extracted_claims: List[str] = Field(default_factory=list)
    audit_ids: List[str] = Field(default_factory=list)
    orchestration_entries: List[Dict[str, Any]] = Field(default_factory=list)


_SENT = re.compile(r"(?<=[\.\?\!])\s+")


def _parse_claims(body: str) -> List[str]:
    out: List[str] = []
    for line in (body or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\s*(?:\d+[\.\)]|[-*•])\s*(.+)$", line)
        if m:
            out.append(m.group(1).strip(" .;"))
        elif len(line) > 15:
            out.append(line)
    return out[:10]


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENT.split(text or "") if s.strip()]


async def run_triangulation(
    *,
    narrative_text: str,
    evidence_chunks: List[str],
    prior_signals: List[str],
    tenant_id: str,
    user_id: str,
) -> TriangulationOutput:
    orch: List[Dict[str, Any]] = []
    audit_ids: List[str] = []

    # 1. Claim extraction.
    cprompt = json.dumps({
        "task": "extract_factual_claims",
        "narrative": narrative_text[:1800],
        "output_schema": "numbered list of factual claims (1-10 items)",
    }, ensure_ascii=False)
    cres = await invoke_via_shield(
        purpose="solva.layer_2.triangulation.claim_extraction",
        prompt=cprompt,
        tenant_id=tenant_id,
        user_id=user_id,
        layer="layer_2",
        engine=ENGINE + ".claim_extraction",
        engine_version=ENGINE_VERSION,
        input_hash=hashlib.sha256(cprompt.encode()).hexdigest(),
    )
    orch.append(cres.orchestration_entry)
    audit_ids.append(cres.audit_id)
    claims = _parse_claims(cres.response_text or "")
    if not claims:
        # Fallback: split the narrative into sentences.
        claims = _split_sentences(narrative_text)[:5]

    # 2. Entailment classification across all evidence sources.
    evidence_blob = "\n---\n".join((evidence_chunks or [])[:6])
    prior_blob = "\n---\n".join((prior_signals or [])[:6])
    eprompt = json.dumps({
        "task": "entailment_classification",
        "claims": claims,
        "evidence": evidence_blob[:1200],
        "prior_signals": prior_blob[:1200],
        "output_schema": (
            "list of {claim, alignment: entails|contradicts|not_mentioned, source}"
        ),
    }, ensure_ascii=False)
    eres = await invoke_via_shield(
        purpose="solva.layer_2.triangulation.entailment_classification",
        prompt=eprompt,
        tenant_id=tenant_id,
        user_id=user_id,
        layer="layer_2",
        engine=ENGINE + ".entailment_classification",
        engine_version=ENGINE_VERSION,
        input_hash=hashlib.sha256(eprompt.encode()).hexdigest(),
    )
    orch.append(eres.orchestration_entry)
    audit_ids.append(eres.audit_id)

    # 3. Aggregate. Rule-based reading of the entailment response.
    response_lower = (eres.response_text or "").lower()
    contradiction_hits = response_lower.count("contradict")
    entail_hits = response_lower.count("entail")
    total_signal = max(1, contradiction_hits + entail_hits)
    consistency = round(entail_hits / total_signal, 2) if total_signal > 0 else 0.5

    divergences: List[Divergence] = []
    if contradiction_hits and claims:
        # Surface the first claim that overlaps with a "contradict" line.
        for line in (eres.response_text or "").splitlines():
            if "contradict" in line.lower():
                # Find which claim this line is about.
                for c in claims:
                    if c.lower()[:30] in line.lower():
                        divergences.append(Divergence(
                            claim=c,
                            sources=["attached evidence" if evidence_chunks else "prior context"],
                            severity="material",
                            divergence_type="narrative_vs_evidence" if evidence_chunks else "narrative_vs_prior",
                        ))
                        break

    alignments = [
        {"claim": c, "alignment": "entails" if entail_hits else "unknown"}
        for c in claims[:3]
    ]
    return TriangulationOutput(
        overall_consistency=consistency,
        divergences=divergences,
        alignments=alignments,
        extracted_claims=claims,
        audit_ids=audit_ids,
        orchestration_entries=orch,
    )
