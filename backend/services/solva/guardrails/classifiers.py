"""Guardrail classifiers — Phase E Sub-task B (2026-05-16).

Three Shield-routed classifiers + a deterministic regex pre-filter.
Together they form a ladder:

    pre_filter (regex) ──┐
    jailbreak_clf  ──────┼──── decide(...) ──> ok | blocked_soft | blocked_hard
    therapy_clf    ──────┤
    coaching_clf   ──────┘

Each classifier returns a confidence score (0.0–1.0). `decide()`
applies the priority order: jailbreak > therapy > coaching.

Outcomes:
  - HARD on jailbreak ≥ 0.6 OR pre_filter hostility match.
  - SOFT on therapy ≥ 0.7 OR coaching ≥ 0.7.
  - OK otherwise.

Templates are LOCKED product copy. Coach-voice, restrained.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..orchestration.shield_invoker import invoke_via_shield


ENGINE_JAILBREAK = "jailbreak_classifier@1.0"
ENGINE_THERAPY = "therapy_classifier@1.0"
ENGINE_COACHING = "coaching_classifier@1.0"


# Deterministic regex pre-filter — fires on obvious hostile / jailbreak
# patterns BEFORE we waste an LLM call. Pattern source: common
# documented prompt-injection vocabulary.
_HOSTILE_RE = re.compile(
    r"\b(ignore\s+(?:all|previous|prior|the|every)(?:\s+\w+){0,3}?\s+(?:instructions?|prompts?|rules?)|"
    r"disregard\s+(?:the|your|all|every)(?:\s+\w+){0,3}?\s+(?:system|prior|previous)?(?:\s+prompt|instructions?|rules?)|"
    r"jailbreak|"
    r"forget\s+(?:everything|all|previous)(?:\s+\w+){0,3}?|"
    r"you\s+are\s+now\s+[a-z]+|"
    r"pretend\s+(?:to be|you are|that you)|"
    r"act\s+as\s+(?:a|an|the)\s+\w+|"
    r"reveal\s+(?:your|the|all|hidden)\s+(?:system\s+prompt|hidden\s+prompt|instructions?)|"
    r"override\s+(?:safety|guard|filter|restriction)|"
    r"developer\s+mode|"
    r"dan\s+mode)\b",
    re.IGNORECASE,
)

# Coarse abusive-content pre-filter. Conservative — only catches
# unambiguous slurs / explicit threats. Borderline content goes to
# the LLM classifier.
_ABUSIVE_RE = re.compile(
    r"\b(kill (yourself|your)|kys|"
    r"i (want|wish) you (would|to) die|"
    r"fuck (you|off|this)|"
    r"shut (the )?(fuck )?up)\b",
    re.IGNORECASE,
)


class GuardrailOutcome(str, Enum):
    OK = "ok"
    BLOCKED_SOFT = "blocked_soft"
    BLOCKED_HARD = "blocked_hard"


class ClassifierScore(BaseModel):
    model_config = ConfigDict(extra="ignore")
    classifier: str
    score: float
    rationale: str = ""
    audit_id: Optional[str] = None


@dataclass
class GuardrailDecision:
    outcome: GuardrailOutcome
    primary_classifier: str
    rendering: str
    scores: List[ClassifierScore]
    audit_ids: List[str]
    orchestration_entries: List[Dict[str, Any]]


BLOCKED_HARD_TEMPLATES = {
    "jailbreak": (
        "What you've sent looks like an attempt to bypass the rails I run on, "
        "rather than a question I can reason about. I'll step out of it. "
        "If there's a strategic situation behind this, let's start there."
    ),
    "abusive": (
        "I'm built for executive reasoning, not for content like this. "
        "I'll step out. If there's a real question, I'm here for that."
    ),
    "off_product": (
        "What you've brought is outside the situations I'm built to reason "
        "about. Try posing it as a decision you're weighing, a hypothesis "
        "you're testing, or a perspective you want challenged."
    ),
}


BLOCKED_SOFT_TEMPLATES = {
    "therapy": (
        "I hear you. What you've described sounds heavier than a strategic "
        "question — closer to the personal weight a clinician would be "
        "better placed to hold. I can stay in the executive lane, but I "
        "want to flag it. If you'd like to rephrase as a business "
        "decision, I'll work on that with you."
    ),
    "coaching": (
        "What you're asking is closer to personal coaching than executive "
        "diagnosis. I can take the question, but I'll frame the read as a "
        "scenario you're weighing — not as advice on who you are as a "
        "leader. Tell me the decision behind it."
    ),
}


async def _run_classifier(
    *,
    purpose: str,
    engine: str,
    input_text: str,
    classifier_name: str,
    tenant_id: str,
    user_id: str,
) -> ClassifierScore:
    """Invoke ONE Shield-routed classifier. Returns a confidence score
    parsed from the LLM response (extracts the first 0.xx number found
    OR maps yes/no to 1.0/0.0)."""
    prompt = json.dumps({
        "task": f"{classifier_name}_classification",
        "input": (input_text or "")[:1800],
        "guidance": (
            f"Classify whether the input shows {classifier_name} intent. "
            "Return a JSON object: "
            '{"score": <float 0.0-1.0>, "rationale": "<one sentence>"}. '
            "Be strict — only score above 0.5 if intent is clear."
        ),
    }, ensure_ascii=False)
    result = await invoke_via_shield(
        purpose=purpose,
        prompt=prompt,
        tenant_id=tenant_id,
        user_id=user_id,
        layer="guardrails",
        engine=engine,
        engine_version=engine,
        input_hash=hashlib.sha256(prompt.encode()).hexdigest(),
    )
    body = (result.response_text or "").strip()
    score = 0.0
    rationale = ""
    # Try JSON parse first.
    try:
        # Find JSON object boundaries.
        s = body.find("{")
        e = body.rfind("}")
        if s >= 0 and e > s:
            parsed = json.loads(body[s:e + 1])
            score = float(parsed.get("score", 0.0))
            rationale = str(parsed.get("rationale", ""))
    except (ValueError, TypeError):
        pass
    if score == 0.0:
        # Fallback: look for a 0.XX or "yes" pattern.
        m = re.search(r"\b(0\.\d{1,3}|1\.0|0)\b", body)
        if m:
            try:
                score = float(m.group(1))
            except ValueError:
                pass
        elif re.search(r"\byes\b", body, re.I):
            score = 1.0
    score = max(0.0, min(1.0, score))
    return ClassifierScore(
        classifier=classifier_name,
        score=score,
        rationale=rationale[:200],
        audit_id=result.audit_id,
    )


async def run_guardrail_ladder(
    *,
    input_text: str,
    tenant_id: str,
    user_id: str,
    skip_llm: bool = False,
) -> GuardrailDecision:
    """Run the full guardrail ladder. Returns the decision + audit
    trail.

    `skip_llm=True` short-circuits the classifiers and returns OK after
    the regex pre-filter — used by deterministic tests that don't have
    a live Shield mock for these new purposes.
    """
    audit_ids: List[str] = []
    orch_entries: List[Dict[str, Any]] = []
    scores: List[ClassifierScore] = []

    # Regex pre-filter — instant decisions.
    if _HOSTILE_RE.search(input_text or ""):
        return GuardrailDecision(
            outcome=GuardrailOutcome.BLOCKED_HARD,
            primary_classifier="pre_filter.jailbreak",
            rendering=BLOCKED_HARD_TEMPLATES["jailbreak"],
            scores=[ClassifierScore(classifier="pre_filter.jailbreak", score=1.0,
                                    rationale="hostile pattern matched")],
            audit_ids=[],
            orchestration_entries=[],
        )
    if _ABUSIVE_RE.search(input_text or ""):
        return GuardrailDecision(
            outcome=GuardrailOutcome.BLOCKED_HARD,
            primary_classifier="pre_filter.abusive",
            rendering=BLOCKED_HARD_TEMPLATES["abusive"],
            scores=[ClassifierScore(classifier="pre_filter.abusive", score=1.0,
                                    rationale="abusive pattern matched")],
            audit_ids=[],
            orchestration_entries=[],
        )

    if skip_llm or not (input_text or "").strip():
        return GuardrailDecision(
            outcome=GuardrailOutcome.OK,
            primary_classifier="pre_filter",
            rendering="",
            scores=[],
            audit_ids=[],
            orchestration_entries=[],
        )

    # Three Shield-routed classifiers in PARALLEL.
    results = await asyncio.gather(
        _run_classifier(
            purpose="solva.guardrails.jailbreak_detection",
            engine=ENGINE_JAILBREAK,
            input_text=input_text,
            classifier_name="jailbreak",
            tenant_id=tenant_id, user_id=user_id,
        ),
        _run_classifier(
            purpose="solva.guardrails.therapy_detection",
            engine=ENGINE_THERAPY,
            input_text=input_text,
            classifier_name="therapy",
            tenant_id=tenant_id, user_id=user_id,
        ),
        _run_classifier(
            purpose="solva.guardrails.coaching_detection",
            engine=ENGINE_COACHING,
            input_text=input_text,
            classifier_name="coaching",
            tenant_id=tenant_id, user_id=user_id,
        ),
        return_exceptions=True,
    )

    for r in results:
        if isinstance(r, Exception):
            # If a classifier raised, treat as OK — don't block on
            # infrastructure failure. Logged but not user-blocking.
            continue
        scores.append(r)
        if r.audit_id:
            audit_ids.append(r.audit_id)

    by_name = {s.classifier: s.score for s in scores}

    # Decision priority — jailbreak first, then therapy, then coaching.
    if by_name.get("jailbreak", 0.0) >= 0.6:
        return GuardrailDecision(
            outcome=GuardrailOutcome.BLOCKED_HARD,
            primary_classifier="jailbreak",
            rendering=BLOCKED_HARD_TEMPLATES["jailbreak"],
            scores=scores, audit_ids=audit_ids, orchestration_entries=orch_entries,
        )
    if by_name.get("therapy", 0.0) >= 0.7:
        return GuardrailDecision(
            outcome=GuardrailOutcome.BLOCKED_SOFT,
            primary_classifier="therapy",
            rendering=BLOCKED_SOFT_TEMPLATES["therapy"],
            scores=scores, audit_ids=audit_ids, orchestration_entries=orch_entries,
        )
    if by_name.get("coaching", 0.0) >= 0.7:
        return GuardrailDecision(
            outcome=GuardrailOutcome.BLOCKED_SOFT,
            primary_classifier="coaching",
            rendering=BLOCKED_SOFT_TEMPLATES["coaching"],
            scores=scores, audit_ids=audit_ids, orchestration_entries=orch_entries,
        )

    return GuardrailDecision(
        outcome=GuardrailOutcome.OK,
        primary_classifier="none",
        rendering="",
        scores=scores, audit_ids=audit_ids, orchestration_entries=orch_entries,
    )
