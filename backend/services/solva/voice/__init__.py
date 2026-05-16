"""Phase D voice tier — coach-voice surface."""
from .question_bank import next_question, QuestionRecord, LOCKED_REFLECTION_QUESTIONS
from .synthesis_renderer import render_synthesis, render_acknowledgement
from .refusal_voice import render_refusal
from .invariants import (
    scan_for_internal_artefacts,
    SingleVoiceViolation,
    INTERNAL_ARTEFACT_TERMS,
)

__all__ = [
    "next_question",
    "QuestionRecord",
    "LOCKED_REFLECTION_QUESTIONS",
    "render_synthesis",
    "render_acknowledgement",
    "render_refusal",
    "scan_for_internal_artefacts",
    "SingleVoiceViolation",
    "INTERNAL_ARTEFACT_TERMS",
]
