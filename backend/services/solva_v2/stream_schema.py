"""Solva v2 — Slice 3a (2026-05-29) live reasoning stream event schema.

The Solva v2 deck is a 5-layer-pass artefact. The reasoning stream gives
the founder visceral proof that each slide IS the resolution of a layer
in that pass — not an AI tool returning a result. Every event below
encodes a step Solva's engine actually performed.

Schema is LOCKED. The tester probes by these field names + values. The
frontend's `useSolvaReasoningStream` (Slice 3b) consumes this wire shape
verbatim.

CANONICAL LAYER ENUM
--------------------
Solva's 5-layer pass per `/app/memory/briefs/SOLVA.md` §3.2-3.6:

    L0  frame_audit  — Frame Audit Record (FAR) — gate the framing
    L1  surface       — Candidate generation, framing extraction
    L2  depth         — Triangulation + tension detection
    L3  synthesis     — The diagnosis paragraph + scenarios
    L4  reflection    — 3 fixed reflection questions

LEGACY AUDIT-LOG ROSETTA
------------------------
The reasoning_audit_log was instrumented before the canonical naming
locked. Mapping (used by `stream_synthesizer.py`):

    audit_log.layer == "framing"     → L0 frame_audit
    audit_log.layer == "grounding"   → L1 surface
    audit_log.layer == "hypothesis"  → L2 depth
    audit_log.layer == "synthesis"   → L3 synthesis
    audit_log.layer == "reflection"  → L4 reflection

STEP DESCRIPTION CONTRACT (integrity boundary)
----------------------------------------------
Every `step_description` MUST be:
    1. Observational — uses verbs like `extracting`, `calibrating`,
       `composing`, `triangulating`. Forbidden verbs: `thinking`,
       `pondering`, `feeling`, `sensing`, `looking deeply`.
    2. Grounded — references concrete artefacts (layer name, question
       number, tension number, cluster id, source count).
    3. Imperative-free — never tells the user what to do mid-stream.

The `validate_step_description()` function below enforces this with the
same allowlist pattern as the refuse-to-decide validator in
`integrity_validators.py`. Any emit site that fails validation is
rejected at SSE-emit time — the event simply never reaches the wire.

WIRE FORMAT
-----------
SSE event name = `solva.reasoning`. The data payload is the JSON-dumped
`SolvaStreamEvent.model_dump()` from the Pydantic model below. The
frontend reads `data.layer_id`, `data.step_kind`, `data.slide_kind`
(when present), `data.step_description`.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────────────────────────
# Locked layer + step + slide enums
# ─────────────────────────────────────────────────────────────────


LOCKED_LAYER_IDS = ("L0", "L1", "L2", "L3", "L4")

LAYER_ID_TO_NAME = {
    "L0": "frame_audit",
    "L1": "surface",
    "L2": "depth",
    "L3": "synthesis",
    "L4": "reflection",
}

LAYER_NAME_TO_ID = {v: k for k, v in LAYER_ID_TO_NAME.items()}

# Audit-log → Solva canonical layer rosetta. Used by the synthesizer.
AUDIT_LOG_LAYER_TO_CANONICAL_ID = {
    "framing":    "L0",
    "frame_audit": "L0",
    "grounding":  "L1",
    "surface":    "L1",
    "hypothesis": "L2",
    "depth":      "L2",
    "synthesis":  "L3",
    "reflection": "L4",
}

LOCKED_STEP_KINDS = (
    "layer.start",
    "layer.step.progress",
    "layer.complete",
    "slide.ready",
    "session.complete",
)

# Mirror the locked 15-kind slide enum from artefact_schema.py so a
# slide.ready event can never reference a kind outside that contract.
# Slice 4 (2026-05-29) — added bias_inventory (Trust pillar 2).
# Slice 5 (2026-05-29) — added pre_mortem (Trust pillar 4).
LOCKED_SLIDE_KINDS = frozenset({
    "cover",
    "headline",
    "tensions_overview",
    "per_tension",
    "scenarios_overview",
    "per_scenario_table",
    "sensitivity",
    "reflection",
    "bias_inventory",
    "pathway",
    "pre_mortem",
    "decision_logic",
    "risk_mitigation",
    "methodological_honesty",
    "in_closing",
})


# ─────────────────────────────────────────────────────────────────
# Step-description integrity validator (theatricality rejection)
# ─────────────────────────────────────────────────────────────────


# Observational verbs allowed at the START of a step description.
# The validator does NOT require these — it only forbids theatrical
# / vague openings. The allowlist is documentation, not enforcement.
OBSERVATIONAL_VERBS = (
    "extracting", "extracted",
    "calibrating", "calibrated",
    "composing", "composed",
    "triangulating", "triangulated",
    "weighting", "weighted",
    "scoring", "scored",
    "ranking", "ranked",
    "gating", "gated",
    "rendering", "rendered",
    "synthesizing", "synthesized",
    "mapping", "mapped",
    "validating", "validated",
    "reading", "read",
    "matching", "matched",
    "drafting", "drafted",
    "checking", "checked",
    "auditing", "audited",
    "deriving", "derived",
)

# Theatrical / vague phrases the engine must NOT emit.
# Comparing substring on the lowercase description; word boundaries
# would let "thinking..." slip past as "thinkingful".
FORBIDDEN_PHRASES = (
    "thinking deeply",
    "pondering",
    "feeling out",
    "sensing the",
    "looking deeply",
    "deep thought",
    "intuiting",
    "channeling",
    "let me think",
    "let me consider",
    "let me see",
    "hmm",
    "hidden truth",
    "hidden tensions",  # vague; specific tension numbers are required
    "hidden patterns",
    "exploring possibilities",  # vague — must name what's explored
    "thinking about your situation",
    "your unique",  # flattery vector
    "going to be",
    "would you like",  # imperative
    "you should",      # imperative
    "you must",        # imperative
    "let's",           # imperative ("let's look at...")
)

# Mid-description forbidden words. These are fine inside an
# observational phrase ("we tried 4 candidates") but NEVER as the
# primary verb of a step description.
LEADING_FORBIDDEN_VERBS = re.compile(
    r"^\s*(thinking|pondering|sensing|intuiting|wondering|considering|"
    r"reflecting on|exploring)\b",
    re.IGNORECASE,
)


class StepDescriptionValidationError(ValueError):
    """Raised by `validate_step_description` when a candidate
    description fails the integrity contract."""


def validate_step_description(text: str) -> None:
    """Reject theatrical, vague, or imperative phrasing in a step
    description. Raise `StepDescriptionValidationError` with a precise
    reason. Returns None on success.

    The validator uses BOTH:
        (a) forbidden-phrase substring scan (lowercase)
        (b) leading-verb regex for verbs that imply emotion / vague
            cognition rather than concrete operation
    """
    if not isinstance(text, str):
        raise StepDescriptionValidationError(
            f"step_description must be a string, got {type(text).__name__}"
        )
    stripped = text.strip()
    if not stripped:
        raise StepDescriptionValidationError("step_description must be non-empty")
    if len(stripped) > 200:
        raise StepDescriptionValidationError(
            f"step_description too long ({len(stripped)} > 200 chars) — "
            "keep it observational and concise"
        )
    lower = stripped.lower()
    for needle in FORBIDDEN_PHRASES:
        if needle in lower:
            raise StepDescriptionValidationError(
                f"step_description contains forbidden phrase {needle!r}. "
                "Step descriptions must be observational, grounded, and "
                "imperative-free — describe what the engine IS doing, "
                "not theatrical narration."
            )
    if LEADING_FORBIDDEN_VERBS.match(stripped):
        raise StepDescriptionValidationError(
            "step_description starts with a forbidden vague/emotional "
            "verb. Use observational verbs: " + ", ".join(OBSERVATIONAL_VERBS[:6])
            + " ..."
        )


# ─────────────────────────────────────────────────────────────────
# Pydantic event model (the wire shape)
# ─────────────────────────────────────────────────────────────────


class SolvaStreamEvent(BaseModel):
    """One event in the Solva v2 live reasoning stream.

    Locked field set — frontend reads these names verbatim. Backend
    emitters MUST construct via this model so the integrity validator
    fires before the event reaches the wire.
    """

    event_id:    str = Field(..., description="UUID for this event")
    session_id:  str = Field(..., description="Solva v2 session id")
    layer_id:    str = Field(..., description="One of L0..L4 (Solva canonical)")
    layer_name:  str = Field(..., description="One of frame_audit/surface/depth/synthesis/reflection")
    step_kind:   str = Field(..., description="layer.start / layer.step.progress / layer.complete / slide.ready / session.complete")
    step_description: str = Field(..., description="Observational, grounded, imperative-free description of what the engine just did")
    slide_kind:  Optional[str] = Field(None, description="Locked 15-kind enum value when step_kind == 'slide.ready'")
    sequence:    int = Field(..., ge=0, description="Monotonic sequence within the session — replay clients use this for ordering")
    timestamp:   str = Field(..., description="ISO 8601 UTC timestamp")

    @field_validator("layer_id")
    @classmethod
    def _layer_id_must_be_locked(cls, v: str) -> str:
        if v not in LOCKED_LAYER_IDS:
            raise ValueError(
                f"layer_id={v!r} not in locked enum {LOCKED_LAYER_IDS}"
            )
        return v

    @field_validator("layer_name")
    @classmethod
    def _layer_name_must_be_locked(cls, v: str) -> str:
        if v not in LAYER_NAME_TO_ID:
            raise ValueError(
                f"layer_name={v!r} not in locked enum {tuple(LAYER_NAME_TO_ID)}"
            )
        return v

    @field_validator("step_kind")
    @classmethod
    def _step_kind_must_be_locked(cls, v: str) -> str:
        if v not in LOCKED_STEP_KINDS:
            raise ValueError(
                f"step_kind={v!r} not in locked enum {LOCKED_STEP_KINDS}"
            )
        return v

    @field_validator("slide_kind")
    @classmethod
    def _slide_kind_in_locked_enum(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in LOCKED_SLIDE_KINDS:
            raise ValueError(
                f"slide_kind={v!r} not in locked 15-kind enum"
            )
        return v

    @field_validator("step_description")
    @classmethod
    def _step_description_passes_integrity(cls, v: str) -> str:
        validate_step_description(v)
        return v.strip()

    def model_post_init(self, __context) -> None:  # noqa: D401
        """Cross-field consistency: layer_id and layer_name must agree."""
        if LAYER_ID_TO_NAME[self.layer_id] != self.layer_name:
            raise ValueError(
                f"layer_id={self.layer_id!r} maps to "
                f"{LAYER_ID_TO_NAME[self.layer_id]!r} but layer_name="
                f"{self.layer_name!r} was supplied. Canonical pairs only."
            )
        # slide.ready REQUIRES slide_kind; the other step_kinds must NOT
        # carry one.
        if self.step_kind == "slide.ready" and not self.slide_kind:
            raise ValueError(
                "step_kind='slide.ready' requires a non-null slide_kind"
            )
        if self.step_kind != "slide.ready" and self.slide_kind is not None:
            raise ValueError(
                f"step_kind={self.step_kind!r} must NOT carry slide_kind; "
                "only slide.ready events do."
            )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
