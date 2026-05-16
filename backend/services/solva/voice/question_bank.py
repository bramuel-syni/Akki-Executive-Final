"""Question bank — deterministic, coach-voice questions.

NO LLM-generated questions per brief §5.4. Every question variant is
hand-written; selection is by `(sub_module, layer, key)` plus a
deterministic hash-based variant picker (so the same session + step
always lands on the same variant — reproducible without bias toward
LLM language drift).

Question keys map 1:1 to the FAR's routing_decision output. Examples:

    seek_clarity.layer_1.opening.default
    seek_clarity.layer_1.opening.with_caveats
    seek_clarity.layer_1.opening.conversational
    seek_clarity.layer_1.probe.evidence_grounding
    ...
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class QuestionRecord:
    key: str
    text: str
    variant_index: int


# Phase D core question bank. Each key has 2-3 variants. The voice
# layer picks deterministically (hash(session_id + key) % len(variants)).
_BANK: Dict[str, List[str]] = {
    # ── seek_clarity ───────────────────────────────────────────────
    "seek_clarity.layer_1.opening.default": [
        "Walk me through what's making you uncertain right now — when did you first notice it, and what made it feel like something to bring here?",
        "Tell me about the moment the question started to sit uneasily. What were you reading or hearing at the time?",
    ],
    "seek_clarity.layer_1.opening.with_caveats": [
        "You've named the shape of this. Before we narrow, what would the picture look like if the most obvious explanation turned out to be wrong?",
        "There's something workable in the framing. To make sure we sharpen the right thing — what's the piece you'd be most unhappy to be wrong about?",
    ],
    "seek_clarity.layer_1.opening.conversational": [
        "Before we put more weight on this, I want to make sure I'm hearing the same thing you are. What does this situation look like to the person sitting beside you in the room?",
        "Let's take a step back. If you were briefing a NED who's coming to this cold, what would you tell them about how things stand?",
    ],
    # ── develop_strategy ───────────────────────────────────────────
    "develop_strategy.layer_1.opening.default": [
        "You're weighing a direction. Walk me through the options as you see them, and what each one would deliver if it played out cleanly.",
        "Tell me about the options on the table — and which one you'd lean toward if you had to call it tonight.",
    ],
    "develop_strategy.layer_1.opening.with_caveats": [
        "You've named the directions. Before we test them — which option, if it succeeded, would you most struggle to live with?",
        "Let's sharpen one thing first. Of the options you've named, which one are you assuming is the safe choice?",
    ],
    "develop_strategy.layer_1.opening.conversational": [
        "Before we weigh moves, I want to make sure we're testing the right set. What was on the table that you've already set aside, and why?",
        "Help me see the whole field. What options are you considering, and what's on the table that you haven't named yet?",
    ],
    # ── simulate_hypothesis ────────────────────────────────────────
    "simulate_hypothesis.layer_1.opening.default": [
        "Tell me the hypothesis. What is the if-then you're testing, and what's the evidence that put you onto it?",
        "Walk me through your hypothesis. What's the claim, and what would the world look like if it's right?",
    ],
    "simulate_hypothesis.layer_1.opening.with_caveats": [
        "Your hypothesis is workable. Before we test it — what's the piece of the framing you'd defend hardest if I pushed on it?",
        "There's a real claim in here. To make sure we test the right thing, what assumption is the hypothesis quietly resting on?",
    ],
    "simulate_hypothesis.layer_1.opening.conversational": [
        "Before we run the test, I want to make sure we're testing the right thing. When you say it would happen — are you treating the cause as a given, or is the cause part of what we're testing?",
        "Help me sharpen the hypothesis first. What would have to be true for this to be the right thing to be testing?",
    ],
    # ── get_perspective ────────────────────────────────────────────
    "get_perspective.layer_1.opening.default": [
        "You've asked for a different lens on this. Walk me through what you want this perspective to reveal that your current view doesn't.",
        "Tell me what you're hoping the new perspective will surface — a blind spot, a durability check, something else?",
    ],
    "get_perspective.layer_1.opening.with_caveats": [
        "The lens you've named will work. Before we apply it — what's the decision this perspective is meant to inform?",
        "We can take the angle you've asked for. To make it useful, what's the call you're trying to feed?",
    ],
    "get_perspective.layer_1.opening.conversational": [
        "Before we step into the new lens, I want to be sure it'll show us something. What would this perspective have to reveal to be worth the detour?",
        "Help me with the framing first. What decision is this perspective feeding, and what would change if the view came back contrary to what you expect?",
    ],

    # ── Layer 2 generic probes (per dimension that flagged thin/absent) ──
    "seek_clarity.layer_2.probe.evidence_grounding": [
        "Is there a document or memo you've been turning over in your head when you think about this? Tell me about what's in it.",
        "What's been written down about this so far? Even an email thread is useful.",
    ],
    "seek_clarity.layer_2.probe.decisional_clarity": [
        "If this diagnosis came back, what's the call you'd make on the back of it?",
        "Who do you owe an answer to on this, and by when?",
    ],
    "seek_clarity.layer_2.probe.time_horizon": [
        "By when does this need to be settled — and what changes if it slips?",
        "What's the next moment this becomes harder to ignore?",
    ],
    "develop_strategy.layer_2.probe.evidence_grounding": [
        "Is there work that's already been done on this — a paper, a model, a prior debate?",
        "What's the data you'd cite if you had to defend the option you'd lean toward?",
    ],
    "simulate_hypothesis.layer_2.probe.evidence_grounding": [
        "What's the evidence you'd point to that this hypothesis is the right one to test, rather than the second-best alternative?",
        "Has anyone done this test before — formally or informally — that we should be reading?",
    ],
    "get_perspective.layer_2.probe.evidence_grounding": [
        "Whose view do you most want challenged in this — and what would they say if they were in the room?",
        "Is there a stakeholder whose position on this you've assumed but never asked for?",
    ],
    # Generic fallback (any sub-module / probe miss)
    "_generic.layer_1.opening": [
        "Tell me about how this lands for you right now.",
    ],
    "_generic.layer_2.probe": [
        "Take me deeper on one piece — what's the part of this that's harder to name than the rest?",
    ],
}


# Three locked Reflection questions — brief §3.6. NEVER vary.
LOCKED_REFLECTION_QUESTIONS: List[str] = [
    "Are you disappointed by this diagnosis, and if so, why?",
    "What would have to be true for you to be wrong about your prior framing?",
    "What would the explanation be in six months if you ignore this diagnosis and the situation continues?",
]


def _resolve_variants(key: str) -> List[str]:
    if key in _BANK:
        return _BANK[key]
    # Heuristic fallback by suffix.
    if key.endswith(".opening.default") or key.endswith(".opening.with_caveats") or \
       key.endswith(".opening.conversational"):
        return _BANK["_generic.layer_1.opening"]
    return _BANK["_generic.layer_2.probe"]


def next_question(*, key: str, session_id: str, asked_so_far: int) -> QuestionRecord:
    """Pick a question variant deterministically.

    `asked_so_far` lets the layer step through different variants on
    successive turns when the same key is re-issued.
    """
    variants = _resolve_variants(key)
    seed = f"{session_id}|{key}|{asked_so_far}"
    digest = hashlib.sha1(seed.encode("utf-8")).digest()
    idx = (digest[0] + asked_so_far) % len(variants)
    return QuestionRecord(key=key, text=variants[idx], variant_index=idx)
