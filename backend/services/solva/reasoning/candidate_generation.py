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
_MARKDOWN_BOLD_RE = re.compile(r"\*{2}", re.I)

# Detects an evidence-requirement label that the LLM used to introduce
# the second half of a candidate. Catches all of:
#   "Evidence Requirement: ..."
#   "**Evidence Requirement**: ..."
#   "evidence_requirement**: ..."
#   "Evidence: ..."
_EVIDENCE_LABEL_RE = re.compile(
    r"^[\s·\-\*\u2022]*\**\s*evidence[_\s]*(?:requirement[s]?)?\**\s*[:\-]\s*(.+)$",
    re.I,
)

# Detects an inline description label.
_DESC_LABEL_RE = re.compile(
    r"^[\s·\-\*\u2022]*\**\s*description\**\s*[:\-]\s*(.+)$",
    re.I,
)

# JSON-key-prefix pattern — strips `"description": "` or `"evidence_requirement": "` etc.
_JSON_KEY_PREFIX_RE = re.compile(
    r'^[\s,{]*"(?:description|evidence_requirement|likelihood|category|'
    r'cause|strategy|hypothesis|perspective|reasoning|notes)"\s*:\s*"?',
    re.I,
)


def _strip_label(line: str) -> str:
    """Strip Markdown bold markers, leading bullet chars, and JSON
    key/value scaffolding."""
    s = _MARKDOWN_BOLD_RE.sub("", line)
    s = _JSON_KEY_PREFIX_RE.sub("", s)
    s = re.sub(r"^[\s·\-\*\u2022]+", "", s)
    return s.strip(" .-*·:;\"',")


def _parse_candidates_from_json(body: str, ctype: str) -> List[Candidate]:
    """Try to extract a JSON array/object structure from the LLM
    response. Returns an empty list if no usable JSON is found."""
    if not body:
        return []
    # Look for the first `[` ... last `]` to bound a JSON array.
    start = body.find("[")
    end = body.rfind("]")
    candidates_data: List[Dict[str, Any]] = []
    if start >= 0 and end > start:
        snippet = body[start:end + 1]
        try:
            parsed = json.loads(snippet)
            if isinstance(parsed, list):
                candidates_data = [c for c in parsed if isinstance(c, dict)]
        except (ValueError, TypeError):
            pass
    # Fall back: bracket may be missing. Try whole-body JSON object
    # whose value is a list under any key.
    if not candidates_data:
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                for v in parsed.values():
                    if isinstance(v, list) and all(isinstance(x, dict) for x in v):
                        candidates_data = v
                        break
        except (ValueError, TypeError):
            pass
    out: List[Candidate] = []
    for c in candidates_data[:TARGET_CANDIDATES]:
        desc = str(c.get("description") or c.get("desc") or c.get("name") or "").strip()
        evid = str(
            c.get("evidence_requirement")
            or c.get("evidence")
            or c.get("evidence_needed")
            or ""
        ).strip()
        if not desc or len(desc) < 12:
            continue
        if not evid:
            evid = "evidence from attached material or referenced source"
        out.append(Candidate(
            id=f"cand-{hashlib.sha1(desc.encode('utf-8')).hexdigest()[:10]}",
            candidate_type=ctype,
            description=desc[:240],
            evidence_requirement=evid[:240],
        ))
    return out


def _parse_candidates_from_text(body: str, ctype: str) -> List[Candidate]:
    """Tolerant parser — handles four cloud-LLM response patterns:

      (a) One line per candidate, parenthesised:
              "<desc> (evidence: <req>)"
      (b) One line per candidate, mid-line label:
              "Description: <desc> · Evidence Requirement: <req>"
      (c) Two lines per candidate:
              line N:    "<desc>"
              line N+1:  "Evidence Requirement: <req>"
      (d) JSON array — handled by `_parse_candidates_from_json` first.

    Skips preambles. Rejects internal-vocabulary leaks. Pairs orphan
    evidence-requirement lines onto the preceding candidate.
    """
    # JSON-first path.
    json_out = _parse_candidates_from_json(body, ctype)
    if json_out:
        return json_out

    out: List[Candidate] = []
    pending_desc: Optional[str] = None

    def _emit(desc: str, evidence: str) -> None:
        d = _strip_label(desc)
        e = _strip_label(evidence) if evidence else (
            "evidence from attached material or referenced source"
        )
        if not d or len(d) < 12:
            return
        if re.search(r"\b(layer\s*[0-9]|frame audit|candidate set)\b", d, re.I):
            return
        for existing in out:
            if existing.description.lower() == d.lower():
                return
        out.append(Candidate(
            id=f"cand-{hashlib.sha1(d.encode('utf-8')).hexdigest()[:10]}",
            candidate_type=ctype,
            description=d[:240],
            evidence_requirement=e[:240],
        ))

    for raw_line in (body or "").splitlines():
        line = raw_line.strip()
        if not line or _PREAMBLE_RE.match(line) or len(line) < 12:
            continue
        m = _BULLET_LINE_RE.match(line)
        text = m.group(1) if m else line

        # Pattern (c): orphan evidence line — attach to preceding desc.
        ev_match = _EVIDENCE_LABEL_RE.match(text)
        if ev_match and pending_desc:
            _emit(pending_desc, ev_match.group(1))
            pending_desc = None
            if len(out) >= TARGET_CANDIDATES:
                break
            continue
        if ev_match and not pending_desc:
            continue

        # Pattern (b): "Description: X ... Evidence Requirement: Y"
        ev_split = re.search(
            r"(?:[·\-\*\u2022]\s*)?\**\s*evidence[_\s]*(?:requirement[s]?)?\**\s*[:\-]\s*(.+)$",
            text, re.I,
        )
        if ev_split:
            desc_half = text[:ev_split.start()].strip(" .-*·:;")
            evid_half = ev_split.group(1)
            dm = _DESC_LABEL_RE.match(desc_half)
            if dm:
                desc_half = dm.group(1)
            if pending_desc and not desc_half:
                _emit(pending_desc, evid_half)
                pending_desc = None
            elif desc_half:
                _emit(desc_half, evid_half)
            if len(out) >= TARGET_CANDIDATES:
                break
            continue

        # Pattern (a): parenthesised "(evidence: ...)" — handle inline.
        evid_match = re.search(r"\(\s*evidence[:\-]\s*(.+?)\s*\)", text, re.I)
        if evid_match:
            desc = re.sub(r"\(\s*evidence[:\-].+?\)", "", text, flags=re.I)
            _emit(desc, evid_match.group(1))
            pending_desc = None
            if len(out) >= TARGET_CANDIDATES:
                break
            continue

        # No evidence label on this line — treat as pending description.
        if pending_desc is not None:
            _emit(pending_desc, "")
            if len(out) >= TARGET_CANDIDATES:
                break
        dm = _DESC_LABEL_RE.match(text)
        pending_desc = dm.group(1) if dm else text

    # Flush any trailing pending description.
    if pending_desc and len(out) < TARGET_CANDIDATES:
        _emit(pending_desc, "")
    return out


def _fallback_candidates(ctype: str, framing: str, n: int = 5) -> List[Candidate]:
    """Stable fallback set when the LLM didn't return parseable
    candidates. Generic but valid Pydantic shapes. Tagged as
    `source="fallback_synthetic"` so the refusal evaluator does NOT
    count them as user-anchored grounded candidates."""
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
            source="fallback_synthetic",
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
        "output_schema": (
            "JSON ARRAY of EXACTLY 5 objects. Each object has TWO string "
            "fields: 'description' (the candidate, 1-2 sentences, NO field "
            "labels, NO markdown) and 'evidence_requirement' (what document "
            "or data would confirm or refute it, 1 sentence, anchored to "
            "the user's framing). Return ONLY the JSON array — no preamble, "
            "no markdown fence. Example: "
            '[{"description": "...", "evidence_requirement": "..."}, ...]'
        ),
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
