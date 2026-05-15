"""Synisense protective layer for the Akki Chat surface (Phase C, 2026-05-13).

Three failure-mode detectors run on every assistant turn AFTER the
draft response is produced. Each detector is a single Shield invoke
with a structured-output prompt, scored 0.0–1.0:

  A — **hypothesis_without_structure**: user is asking "if we did X,
      would Y happen?" without grounding. Intervention: insert a
      hypothesis-test framing question BEFORE the draft.
  B — **ungrounded_factual_claim**: assistant draft makes a factual
      claim that isn't supported by session materials. Intervention:
      annotate the offending claim inline with "general-practice
      reference — worth verifying against your data."
  C — **fluency_mistaken_for_diagnosis**: a consequential question
      (capital decision, restructuring, etc.) gets a fluent answer
      with insufficient session evidence. Intervention: offer Solva
      handoff with a one-line rationale.

The three Shield purposes are pre-declared in `ALLOWED_PURPOSES`
(`chat.fm_a.hypothesis_detection`, `chat.fm_b.claim_extraction`,
`chat.fm_c.consequence_classification`). They run concurrently via
`asyncio.gather`.

Output schema (`DetectorBundle.as_protective_event()`):

  - `detector_scores: dict[Literal["A","B","C"], float]`
  - `detectors_fired: list[Literal["A","B","C"]]`  (score ≥ 0.5)
  - `intervention_type: Literal["none","hypothesis_test","annotation",
                                "consequence_check","solva_handoff_offered"]`
  - `template_id: str` — which intervention template was used
  - `annotation_anchors: list[str]` — for Mode B, the claim phrases
    the frontend should superscript

Threshold logic: detectors fire at ≥0.5; intervention precedence is
A > C > B (a hypothesis-test framing is the most important pre-reply
correction; a consequence-handoff is more impactful than an
inline annotation; multiple fires are persisted in `detectors_fired`).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

log = logging.getLogger("akki.chat.protective_layer")

InterventionType = Literal[
    "none",
    "hypothesis_test",
    "annotation",
    "consequence_check",
    "solva_handoff_offered",
]

FIRE_THRESHOLD = 0.5


class ProtectiveEvent(BaseModel):
    """Per-message protective-layer outcome persisted on `chats.protective_layer_events`."""
    message_id: str
    detectors_fired: List[Literal["A", "B", "C"]] = Field(default_factory=list)
    detector_scores: Dict[str, float] = Field(default_factory=dict)
    intervention_type: InterventionType = "none"
    template_id: str = "none.default"
    intervention_text: Optional[str] = None  # human-readable copy shown to user
    annotation_anchors: List[str] = Field(default_factory=list)
    user_follow_through: Optional[Literal["engaged", "ignored", "abandoned"]] = None
    handoff_accepted: Optional[bool] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ─────────────────────────────────────────────────────────────────────
# Detector prompts — keep them terse, structured, JSON-only.
# ─────────────────────────────────────────────────────────────────────
_DETECTOR_A_PROMPT = """\
TASK: A user message is below. Decide whether it presents a HYPOTHESIS
without grounding (e.g. "if we did X, would Y happen?" / "what if..." /
"suppose we...") and lacks specific data or session context to test it
against.

USER MESSAGE:
{user_message}

OUTPUT exactly one JSON object on a single line, no preamble, no
markdown fence:
{{"score": <0.0-1.0>, "rationale": "<≤200 chars>", "framing_question": "<a single ≤180-char question the user should answer BEFORE we attempt the hypothesis>"}}
"""

_DETECTOR_B_PROMPT = """\
TASK: An assistant draft response is below, alongside the session
context (everything the assistant could legitimately know about the
user's data). Identify SHORT phrases in the draft that make factual
claims NOT supported by the session context — these are general-practice
references that should be annotated for the user.

DRAFT RESPONSE:
{draft_response}

SESSION CONTEXT (truncated):
{session_context}

OUTPUT exactly one JSON object on a single line:
{{"score": <0.0-1.0>, "rationale": "<≤200 chars>", "claims": ["<verbatim phrase from the draft>", ...]}}

Limit to ≤3 claim phrases. If nothing qualifies, emit "claims": [].
"""

_DETECTOR_C_PROMPT = """\
TASK: A user is asking a question and got a draft answer. Decide
whether the QUESTION carries strategic/financial/structural CONSEQUENCE
(capital allocation, restructuring, hiring/firing, M&A, regulatory
exposure, board-level call) AND the draft answer is FLUENT but the
session context is THIN (very few materials, no specific numbers).

USER MESSAGE:
{user_message}

DRAFT RESPONSE:
{draft_response}

SESSION CONTEXT (truncated):
{session_context}

OUTPUT exactly one JSON object on a single line:
{{"score": <0.0-1.0>, "rationale": "<≤200 chars>", "handoff_rationale": "<≤180-char one-liner explaining why Solva would help>"}}
"""

# Intervention templates — readable copy shown to the user.
INTERVENTION_TEMPLATES: Dict[str, str] = {
    "A.framing_question": "Before I answer, let's frame this: {framing_question}",
    "B.annotation":        "General-practice reference — worth verifying against your data.",
    "C.solva_handoff":     "This decision carries consequence. Continue in Solva for "
                            "structured reasoning? {handoff_rationale}",
    "none.default":        "No protective interventions for this turn.",
}


class DetectorBundle(BaseModel):
    """Aggregate output across A/B/C; fed straight into ProtectiveEvent."""
    score_a: float = 0.0
    score_b: float = 0.0
    score_c: float = 0.0
    framing_question_a: Optional[str] = None
    claims_b: List[str] = Field(default_factory=list)
    handoff_rationale_c: Optional[str] = None
    rationale_a: Optional[str] = None
    rationale_b: Optional[str] = None
    rationale_c: Optional[str] = None

    def as_protective_event(self, *, message_id: str) -> ProtectiveEvent:
        fired: List[Literal["A", "B", "C"]] = []
        scores: Dict[str, float] = {
            "A": round(self.score_a, 3),
            "B": round(self.score_b, 3),
            "C": round(self.score_c, 3),
        }
        if self.score_a >= FIRE_THRESHOLD:
            fired.append("A")
        if self.score_b >= FIRE_THRESHOLD and self.claims_b:
            fired.append("B")
        if self.score_c >= FIRE_THRESHOLD:
            fired.append("C")

        # Precedence: A > C > B.
        intervention: InterventionType = "none"
        template_id = "none.default"
        intervention_text: Optional[str] = None
        anchors: List[str] = []

        if "A" in fired and self.framing_question_a:
            intervention = "hypothesis_test"
            template_id = "A.framing_question"
            intervention_text = INTERVENTION_TEMPLATES[template_id].format(
                framing_question=self.framing_question_a
            )
        elif "C" in fired and self.handoff_rationale_c:
            intervention = "solva_handoff_offered"
            template_id = "C.solva_handoff"
            intervention_text = INTERVENTION_TEMPLATES[template_id].format(
                handoff_rationale=self.handoff_rationale_c
            )
        elif "B" in fired:
            intervention = "annotation"
            template_id = "B.annotation"
            intervention_text = INTERVENTION_TEMPLATES[template_id]
            anchors = self.claims_b[:3]

        return ProtectiveEvent(
            message_id=message_id,
            detectors_fired=fired,
            detector_scores=scores,
            intervention_type=intervention,
            template_id=template_id,
            intervention_text=intervention_text,
            annotation_anchors=anchors,
        )


# ─────────────────────────────────────────────────────────────────────
# Shield invocations.
# ─────────────────────────────────────────────────────────────────────
def _parse_json_blob(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    raw = raw.strip()
    # Tolerate fenced ```json blocks (some providers wrap output).
    m = re.search(r"\{[^{}]*\}", raw, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


async def _invoke_detector(
    *, purpose: str, prompt: str, tenant_id: str, user_id: str,
) -> Optional[Dict[str, Any]]:
    """Single detector call via Shield. Returns parsed JSON or None
    on any failure. Detector failures are non-fatal — the assistant
    reply still ships."""
    from services.synisense.shield.client import invoke as shield_invoke
    try:
        result = await asyncio.wait_for(
            shield_invoke(
                purpose=purpose, content=prompt,
                tenant_id=tenant_id, consumer_id="chat",
                user_id=user_id, model_preference="balanced",
                internal_caller=True,
            ),
            timeout=12.0,
        )
        return _parse_json_blob(result.get("response") or "")
    except asyncio.TimeoutError:
        log.warning("detector timeout: purpose=%s", purpose)
        return None
    except Exception as exc:  # noqa: BLE001
        log.warning("detector failed: purpose=%s error=%s",
                    purpose, type(exc).__name__)
        return None


async def detect_all(
    *,
    user_message: str,
    draft_response: str,
    session_context: str,
    tenant_id: str,
    user_id: str,
) -> DetectorBundle:
    """Run A/B/C concurrently. Returns a `DetectorBundle` — caller
    converts to `ProtectiveEvent` once it has the message_id."""
    session_context = (session_context or "")[:1800]  # cap for prompt budget

    tasks = [
        _invoke_detector(
            purpose="chat.fm_a.hypothesis_detection",
            prompt=_DETECTOR_A_PROMPT.format(user_message=user_message),
            tenant_id=tenant_id, user_id=user_id,
        ),
        _invoke_detector(
            purpose="chat.fm_b.claim_extraction",
            prompt=_DETECTOR_B_PROMPT.format(
                draft_response=draft_response, session_context=session_context,
            ),
            tenant_id=tenant_id, user_id=user_id,
        ),
        _invoke_detector(
            purpose="chat.fm_c.consequence_classification",
            prompt=_DETECTOR_C_PROMPT.format(
                user_message=user_message, draft_response=draft_response,
                session_context=session_context,
            ),
            tenant_id=tenant_id, user_id=user_id,
        ),
    ]
    a, b, c = await asyncio.gather(*tasks, return_exceptions=False)
    bundle = DetectorBundle()
    if a:
        try:
            bundle.score_a = float(a.get("score") or 0.0)
            bundle.framing_question_a = a.get("framing_question") or None
            bundle.rationale_a = a.get("rationale") or None
        except (TypeError, ValueError):
            pass
    if b:
        try:
            bundle.score_b = float(b.get("score") or 0.0)
            claims = b.get("claims") or []
            if isinstance(claims, list):
                bundle.claims_b = [str(x)[:240] for x in claims if x][:3]
            bundle.rationale_b = b.get("rationale") or None
        except (TypeError, ValueError):
            pass
    if c:
        try:
            bundle.score_c = float(c.get("score") or 0.0)
            bundle.handoff_rationale_c = c.get("handoff_rationale") or None
            bundle.rationale_c = c.get("rationale") or None
        except (TypeError, ValueError):
            pass
    return bundle
