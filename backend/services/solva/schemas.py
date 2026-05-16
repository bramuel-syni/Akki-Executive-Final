"""Solva Phase D — Pydantic v2 schemas + state machine constants.

Persisted in Mongo collection `solva_phase_d_sessions`. Each record
carries one user_id / account_id (== tenant_id) / context_id triple,
the active sub-module, the layer-state, and per-layer records
(Layer0Record .. Layer4Record).

Every Shield-routed LLM call appends one entry to `synisense_audit_ids`
AND one row to `orchestration_audit_log`. The two arrays are linked
by the `synisense_audit_id` field on each orchestration entry.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


SUB_MODULES = (
    "seek_clarity",
    "develop_strategy",
    "simulate_hypothesis",
    "get_perspective",
)


# `entry` → user landed; sub-module selected; no framing yet.
# `framing` → user submitted initial framing; pending Layer 0.
# `layer_0` → Frame Audit silently running (transient state).
# `layer_1` → SURFACE round (3 questions preferred, 4 max).
# `layer_2` → DEPTH round (3 questions preferred, 4 max).
# `layer_3` → SYNTHESIS rendered to user (no questions).
# `layer_4` → REFLECTION round (3 fixed questions).
# `done` → session complete.
# `refused` → terminal: refusal_logic fired (Phase D fix 2026-05-16).
LAYER_STATES = (
    "entry", "framing", "layer_0", "layer_1", "layer_2",
    "layer_3", "layer_4", "done", "refused",
)
TERMINAL_STATES = ("done", "refused", "abandoned")

LAYER_SEQUENCE: List[str] = [
    "entry", "framing", "layer_0", "layer_1", "layer_2",
    "layer_3", "layer_4", "done",
]


SolvaSessionStatus = Literal["active", "completed", "abandoned", "refused"]


# Routing decision the FAR emits (consumed by the question bank to pick
# the Layer 1 opening question_id).
SUB_MODULE_TO_OPENING_KEY: Dict[str, str] = {
    "seek_clarity":         "seek_clarity.layer_1.opening",
    "develop_strategy":     "develop_strategy.layer_1.opening",
    "simulate_hypothesis":  "simulate_hypothesis.layer_1.opening",
    "get_perspective":      "get_perspective.layer_1.opening",
}


# ─────────────────────────────────────────────────────────────────────
# Layer records — INTERNAL structures the reasoning tier produces.
# These NEVER render to the user as content; voice/ consumes them and
# emits coach-voice templates.
# ─────────────────────────────────────────────────────────────────────
class Layer0Record(BaseModel):
    """Frame Audit Record (FAR) + situation classifier output. INTERNAL."""
    model_config = ConfigDict(extra="ignore")
    verdict: Literal["sufficient", "sufficient_with_caveats", "insufficient"]
    dimensions: List[Dict[str, Any]] = Field(default_factory=list)
    routing_decision: Dict[str, Any] = Field(default_factory=dict)
    situation_class: Optional[str] = None
    situation_class_confidence: Optional[float] = None
    carry_forward_caveats: List[str] = Field(default_factory=list)


class Layer1Record(BaseModel):
    """Surface round: candidate set produced; user answers stored."""
    model_config = ConfigDict(extra="ignore")
    question_ids_asked: List[str] = Field(default_factory=list)
    answers: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_set: List[Dict[str, Any]] = Field(default_factory=list)
    questions_count: int = 0


class Layer2Record(BaseModel):
    """Depth round: triangulation + tension detection; refined candidates."""
    model_config = ConfigDict(extra="ignore")
    question_ids_asked: List[str] = Field(default_factory=list)
    answers: List[Dict[str, Any]] = Field(default_factory=list)
    triangulation_result: Dict[str, Any] = Field(default_factory=dict)
    detected_tensions: List[Dict[str, Any]] = Field(default_factory=list)
    refined_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    questions_count: int = 0


class Layer3Record(BaseModel):
    """Synthesis output — coach-voice prose composed by voice tier."""
    model_config = ConfigDict(extra="ignore")
    scenarios: List[Dict[str, Any]] = Field(default_factory=list)
    sensitivity_drivers: List[Dict[str, Any]] = Field(default_factory=list)
    surfaced_tensions: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_trace: List[Dict[str, Any]] = Field(default_factory=list)
    primary_diagnosis_prose: str = ""
    refusal_flag: bool = False
    refusal_reason: Optional[str] = None
    rendered_synthesis: str = ""


class Layer4Record(BaseModel):
    """Reflection — three locked questions and their answers."""
    model_config = ConfigDict(extra="ignore")
    answers: List[Dict[str, Any]] = Field(default_factory=list)


class OrchestrationEntry(BaseModel):
    """One reasoning-tier model invocation. Cross-references the Shield
    audit row by `synisense_audit_id` when the call was LLM-routed."""
    model_config = ConfigDict(extra="ignore")
    id: str
    layer: str
    engine: str
    engine_version: str
    timestamp: str
    input_hash: Optional[str] = None
    output_summary: Dict[str, Any] = Field(default_factory=dict)
    synisense_audit_id: Optional[str] = None
    shield_required: bool = True
    shield_bypass_reason: Optional[str] = None
    latency_ms: int = 0


class SolvaPhaseDSession(BaseModel):
    """Authoritative session record persisted in `solva_phase_d_sessions`."""
    model_config = ConfigDict(extra="ignore")
    session_id: str
    user_id: str
    account_id: str         # == tenant_id
    context_id: str
    sub_module: Literal[
        "seek_clarity", "develop_strategy",
        "simulate_hypothesis", "get_perspective",
    ]
    status: SolvaSessionStatus = "active"
    layer_state: Literal[
        "entry", "framing", "layer_0", "layer_1",
        "layer_2", "layer_3", "layer_4", "done",
    ] = "entry"
    initial_framing: Optional[str] = None
    layer_0: Optional[Layer0Record] = None
    layer_1: Optional[Layer1Record] = None
    layer_2: Optional[Layer2Record] = None
    layer_3: Optional[Layer3Record] = None
    layer_4: Optional[Layer4Record] = None
    synisense_audit_ids: List[str] = Field(default_factory=list)
    orchestration_audit_log: List[Dict[str, Any]] = Field(default_factory=list)
    schema_version: int = 3  # Phase D shape
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
