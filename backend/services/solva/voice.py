"""Solva v2 voice layer (Phase D).

The ONLY place user-facing strings come from. Three modules:

- `question_bank` : deterministic curated questions per sub-module +
  layer. NO LLM generation here — reproducible by design.
- `synthesis_renderer` : passthrough for the Layer 3 coach-voice
  paragraph produced by `reasoning.probability_weighting_and_synthesis`
  (already coach-voice; this module guards it against single-voice
  invariant breaches and post-processes whitespace).
- `refusal_voice` : templated refusal copy per the brief's §4.7 sample.
- `invariants` : the test-only `assert_no_artefact_leak` helper.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from services.solva.models import (
    FrameAuditRecord, ScenarioRecord, SituationClassRecord, SubModule,
)

log = logging.getLogger("solva.voice")


# ─────────────────────────────────────────────────────────────────────
# Question bank — deterministic, curated, indexed by (sub_module, layer).
# Each entry is a list of question variants; the renderer picks one
# pseudorandomly per session (the FAR thin/thick verdict + situation
# class can also key in for future refinement; Phase D uses sub_module
# + layer + a small position counter).
# ─────────────────────────────────────────────────────────────────────
_QUESTION_BANK: Dict[str, Dict[str, List[Dict[str, str]]]] = {
    "seek_clarity": {
        "framing": [
            {"id": "sc.framing.1", "text":
             "Take a breath. In your own words — what's the actual thing you're trying to "
             "see more clearly? Start anywhere."},
        ],
        "layer_1": [
            {"id": "sc.l1.1", "text":
             "There are a few ways I could read this. Which of these comes closest to the "
             "knot you're sitting with right now?"},
            {"id": "sc.l1.2", "text":
             "If you had to point at the specific moment this started feeling unclear, when "
             "was that — and what changed in your reading of the situation?"},
            {"id": "sc.l1.3", "text":
             "What have you ALREADY ruled out? Sometimes the cleanest signal is what you've "
             "stopped considering."},
        ],
        "layer_2": [
            {"id": "sc.l2.1", "text":
             "What in your own session would CONTRADICT what you're leaning toward? Try to "
             "name one specific thing."},
            {"id": "sc.l2.2", "text":
             "There seems to be a tension here between two things that both matter to you. "
             "Which one are you secretly hoping wins out?"},
        ],
        "layer_4": [
            {"id": "sc.l4.1", "text":
             "Last reflection. If you found out in six months that you'd read this wrong, "
             "what would the explanation most likely be?"},
        ],
    },
    "develop_strategy": {
        "framing": [
            {"id": "ds.framing.1", "text":
             "What strategic move are you considering — and what's the question you can't "
             "yet answer cleanly about it?"},
        ],
        "layer_1": [
            {"id": "ds.l1.1", "text":
             "Here are three angles I could take on this. Which one feels like the work "
             "that hasn't been done yet?"},
            {"id": "ds.l1.2", "text":
             "Who in your context has the strongest counter-position — and what's the most "
             "honest version of their argument?"},
            {"id": "ds.l1.3", "text":
             "Imagine you executed this perfectly. What's the FIRST thing that would have to "
             "be true in your operating environment for it to work?"},
        ],
        "layer_2": [
            {"id": "ds.l2.1", "text":
             "Which of these has the strongest evidence behind it from your own materials, "
             "vs. being general industry-practice belief?"},
            {"id": "ds.l2.2", "text":
             "Where could you be over-fitting to what worked before? Name the pattern you're "
             "leaning on."},
        ],
        "layer_4": [
            {"id": "ds.l4.1", "text":
             "What would have to change in your reading for you to walk back from this "
             "decision in six months — without it feeling like failure?"},
        ],
    },
    "simulate_hypothesis": {
        "framing": [
            {"id": "sh.framing.1", "text":
             "What's the if/then you'd like to test? Say it in one sentence — even if it "
             "feels rough."},
        ],
        "layer_1": [
            {"id": "sh.l1.1", "text":
             "Three readings of this hypothesis — which feels closest to what you actually "
             "want to know?"},
            {"id": "sh.l1.2", "text":
             "What's the SMALLEST observable that would tell you you're WRONG about this?"},
            {"id": "sh.l1.3", "text":
             "What's the version of this hypothesis you'd be embarrassed to find out was "
             "actually true?"},
        ],
        "layer_2": [
            {"id": "sh.l2.1", "text":
             "What in your existing evidence would CONTRADICT this hypothesis if you read "
             "it carefully?"},
        ],
        "layer_4": [
            {"id": "sh.l4.1", "text":
             "If the hypothesis turned out to be wrong, what would you have learned that's "
             "worth more than being right?"},
        ],
    },
    "get_perspective": {
        "framing": [
            {"id": "gp.framing.1", "text":
             "What perspective are you looking for — and from whose vantage point would it "
             "be most useful?"},
        ],
        "layer_1": [
            {"id": "gp.l1.1", "text":
             "Three angles you might be missing — which one feels most uncomfortable to "
             "sit with?"},
            {"id": "gp.l1.2", "text":
             "Whose view on this would you most want, and would least want, to hear? Both "
             "answers tell you something."},
        ],
        "layer_2": [
            {"id": "gp.l2.1", "text":
             "If your strongest critic read this, what's the one thing they'd hold up as "
             "the flaw?"},
        ],
        "layer_4": [
            {"id": "gp.l4.1", "text":
             "What perspective came out of this that surprises you — even slightly?"},
        ],
    },
}


def opening_question(*, sub_module: SubModule) -> Dict[str, str]:
    """Used at the entry/framing layer — first thing the user sees."""
    bank = _QUESTION_BANK.get(sub_module) or _QUESTION_BANK["seek_clarity"]
    framing_qs = bank.get("framing") or [{"id": "fallback.framing",
                                          "text": "Tell me what you're working through."}]
    return dict(framing_qs[0])


def next_question(
    *, sub_module: SubModule, layer: str, position: int = 0,
) -> Optional[Dict[str, str]]:
    """Returns the next question for the given layer, or None if no
    further question (e.g. Layer 3 transitions to synthesis without a
    user prompt)."""
    if layer in {"layer_3", "done", "abandoned", "refused"}:
        return None
    bank = _QUESTION_BANK.get(sub_module) or {}
    qs = bank.get(layer) or []
    if not qs:
        return None
    return dict(qs[position % len(qs)])


def candidate_intro_voice(candidates: List[Dict[str, str]]) -> str:
    """Coach-voice intro that frames the 3 Layer 1 candidates without
    leaking the reasoning module's internal `distinct_axis` field."""
    if len(candidates) >= 3:
        names = [c.get("label", "another angle") for c in candidates[:3]]
        return (
            "There's more than one way to read this. The three I see most clearly are: "
            f"{names[0]}, {names[1]}, and {names[2]}. "
            "Which of those feels closest to the knot you're sitting with?"
        )
    if not candidates:
        return "Let's stay with your framing as it is."
    return "Here's another angle on what you've said — " + candidates[0].get("label", "")


# ─────────────────────────────────────────────────────────────────────
# Refusal voice — templated coach copy per the brief.
# ─────────────────────────────────────────────────────────────────────
_REFUSAL_TEMPLATES: Dict[str, str] = {
    "evidence_insufficient": (
        "I want to be honest with you. What you've given me so far is closer to an "
        "instinct than a framing I can build on — and if I pressed forward, I'd be "
        "manufacturing analysis on top of air. That wouldn't serve you. Take a few "
        "minutes, anchor the question to something specific (a number, a moment, a "
        "person, a constraint), and come back. I'll meet you where you are."
    ),
    "high_stakes_low_evidence": (
        "This carries real consequence, and right now there isn't enough on the table "
        "for me to reason it through honestly. I don't want to give you the comfort "
        "of a clean answer when the underlying evidence isn't there. Could you bring "
        "the specifics? Even a paragraph of context changes what we can do here."
    ),
    "out_of_scope": (
        "This is outside what Solva is built for. Solva works through decisions where "
        "you're weighing a real choice with real stakes. If you'd like to think about "
        "this more openly, the Chat surface is the better room for it."
    ),
}


def refusal_voice(reason: str) -> str:
    return _REFUSAL_TEMPLATES.get(reason, _REFUSAL_TEMPLATES["evidence_insufficient"])


# ─────────────────────────────────────────────────────────────────────
# Synthesis renderer — passes Layer 3 paragraph through after guardrails.
# ─────────────────────────────────────────────────────────────────────
def render_synthesis(*, layer_3_paragraph: str) -> str:
    """Last-mile guardrails on the synthesis text. Strips any
    accidental field-name leaks, normalises whitespace. Does NOT
    invoke an LLM."""
    if not layer_3_paragraph:
        return ""
    s = layer_3_paragraph.strip()
    # Strip field names that would betray the reasoning artefacts.
    for forbidden in [
        "framing_thickness_score", "evidence_density_score",
        "decision_stakes_score", "candidate_set", "FAR ", "verdict:",
        "distinct_axis", "entailment:", "source_type:",
    ]:
        s = s.replace(forbidden, "")
    # Collapse whitespace.
    s = re.sub(r"\s+", " ", s).strip()
    return s


def render_scenarios_voice(scenarios: List[ScenarioRecord]) -> List[Dict[str, str]]:
    """User-visible scenario strip — narrative only; probability shown
    as percentage label. NO internal field names."""
    out: List[Dict[str, str]] = []
    for s in scenarios:
        out.append({
            "name": s.name,
            "narrative": s.narrative,
            "probability_label": f"{int(round(s.probability * 100))}%",
            "leading_indicator": s.leading_indicator,
        })
    return out
