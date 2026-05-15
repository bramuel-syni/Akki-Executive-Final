"""Solva v2 — Pydantic v2 models (Phase D).

All structured outputs from reasoning modules use these. NO module
returns free-form text; the voice renderer is the only place
user-visible strings come from.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SubModule = Literal[
    "seek_clarity", "develop_strategy", "simulate_hypothesis", "get_perspective",
]
LayerState = Literal[
    "entry", "framing", "layer_0", "layer_1", "layer_2",
    "layer_3", "layer_4", "done", "refused", "abandoned",
]
SituationClass = Literal[
    "decision_with_evidence",
    "decision_without_evidence",
    "exploration",
    "hypothesis_test",
    "perspective_seeking",
    "out_of_scope",
]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────
# Per-layer structured records (INTERNAL — never user-visible).
# ─────────────────────────────────────────────────────────────────────
class FrameAuditRecord(BaseModel):
    """Layer 0 output. INTERNAL — never user-visible. The single-voice
    invariant test asserts none of these fields appear in user payloads."""
    model_config = ConfigDict(extra="forbid")
    framing_thickness_score: float = Field(ge=0.0, le=1.0)
    evidence_density_score: float = Field(ge=0.0, le=1.0)
    decision_stakes_score: float = Field(ge=0.0, le=1.0)
    has_specific_artefact: bool
    surfaced_constraints: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    verdict: Literal["thick_enough", "thin", "refuse"]
    rationale: str  # INTERNAL


class SituationClassRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: SituationClass
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str  # INTERNAL


class Layer0Record(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frame_audit: FrameAuditRecord
    situation: SituationClassRecord
    timestamp: str = Field(default_factory=_iso_now)


class CandidateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    description: str  # INTERNAL — voice renderer translates to coach copy
    distinct_axis: str  # what makes this candidate distinct from the others


class Layer1Record(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_set: List[CandidateRecord]
    user_answers: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: str = Field(default_factory=_iso_now)


class TriangulationClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim: str
    source_type: Literal["session_evidence", "general_practice", "unknown"]
    entailment: Literal["supports", "contradicts", "tangential"]
    confidence: float = Field(ge=0.0, le=1.0)


class TensionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    axis: str
    severity: Literal["low", "medium", "high"]
    description: str  # INTERNAL


class Layer2Record(BaseModel):
    model_config = ConfigDict(extra="forbid")
    triangulation: List[TriangulationClaim]
    tensions: List[TensionRecord] = Field(default_factory=list)
    user_answers: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: str = Field(default_factory=_iso_now)


class ScenarioRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    probability: float = Field(ge=0.0, le=1.0)
    upside_band: str
    downside_band: str
    leading_indicator: str
    narrative: str  # coach-voice; renderable to the user


class Layer3Record(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenarios: List[ScenarioRecord]
    synthesis_paragraph: str  # coach-voice; THIS is the user-visible synthesis
    evidence_trace: List[str] = Field(default_factory=list)  # short bullets
    timestamp: str = Field(default_factory=_iso_now)


class ReflectionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    what_would_change_mind: Optional[str] = None
    six_month_regret_explanation: Optional[str] = None
    what_disappoints: Optional[str] = None
    timestamp: str = Field(default_factory=_iso_now)


class Layer4Record(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reflection: ReflectionRecord
    timestamp: str = Field(default_factory=_iso_now)


class OrchestrationEntry(BaseModel):
    """Internal model-invocation log (audit trail of which reasoning
    module ran, with which Shield audit_id, in which order). Hidden
    from the user but persisted on the session."""
    model_config = ConfigDict(extra="forbid")
    timestamp: str
    layer: LayerState
    module: str
    shield_audit_id: Optional[str] = None
    elapsed_ms: int
    outcome: Literal["success", "refusal", "error"]
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────
# Session document (Mongo `solva_v2_sessions` extension).
# ─────────────────────────────────────────────────────────────────────
class SolvaSession(BaseModel):
    model_config = ConfigDict(extra="allow")  # allow legacy fields to coexist
    id: str
    user_id: str
    context_id: str
    account_id: str
    sub_module: SubModule
    status: Literal["active", "completed", "abandoned", "refused"] = "active"
    layer_state: LayerState = "entry"
    initial_framing: Optional[str] = None
    layer_0: Optional[Layer0Record] = None
    layer_1: Optional[Layer1Record] = None
    layer_2: Optional[Layer2Record] = None
    layer_3: Optional[Layer3Record] = None
    layer_4: Optional[Layer4Record] = None
    synisense_audit_ids: List[str] = Field(default_factory=list)
    orchestration_audit_log: List[OrchestrationEntry] = Field(default_factory=list)
    pending_question: Optional[Dict[str, Any]] = None
    refusal_reason: Optional[str] = None
    refusal_voice: Optional[str] = None  # user-facing refusal copy
    created_at: str = Field(default_factory=_iso_now)
    updated_at: str = Field(default_factory=_iso_now)
    completed_at: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────
# API request/response models.
# ─────────────────────────────────────────────────────────────────────
class CreateSessionRequest(BaseModel):
    sub_module: SubModule


class SubmitFramingRequest(BaseModel):
    framing: str = Field(min_length=4, max_length=4000)


class AnswerQuestionRequest(BaseModel):
    question_id: str
    answer: str = Field(min_length=1, max_length=8000)


class SessionStateResponse(BaseModel):
    """User-visible session state — voice templates only. Internal
    reasoning records are STRIPPED before serialisation."""
    id: str
    sub_module: SubModule
    status: Literal["active", "completed", "abandoned", "refused"]
    layer_state: LayerState
    coach_voice_prompt: Optional[str] = None
    pending_question: Optional[Dict[str, Any]] = None
    synthesis: Optional[str] = None  # final coach-voice paragraph (Layer 3+)
    scenarios_voice: List[Dict[str, str]] = Field(default_factory=list)
    refusal_voice: Optional[str] = None
    synisense_audit_ids: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
