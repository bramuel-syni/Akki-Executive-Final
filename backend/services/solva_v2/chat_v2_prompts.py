"""Phase ZZ.2 (2026-02 fork-resume v2) — Solva governance IS the Chat model.

This module is the conversational system prompt for every Akki Chat
turn. It is derived from `services.solva_v2.v2_prompts.CONSTRAINT_PREAMBLE`
but adapted from "produce a structured 16-slide payload" to "speak
in a conversational executive register, refuse when sources are
absent, name confidence as a range rather than asserting certainty".

Tier 1 (always on) lives in `CHAT_V2_GOVERNANCE_PREAMBLE` below.
Tier 2 / Tier 3 escalations are layered on at call-sites in
`routers/chat.py` (Tier 2: bias flags + adversarial nudge +
escalation CTA; Tier 3: full document-artefact validator stack —
runs only on brief / summary / compilation / email-draft outputs).

VOICE DISCIPLINE — the prompt itself is an instruction to the model;
the model's OUTPUT is customer-facing. So the prompt names "executive
peer" rather than the late-banned "senior peer" tag, and instructs
the model to NEVER use "senior" in its replies. The voice tests pass
on the prompt strings AND, transitively, on the model output.
"""
from __future__ import annotations

CHAT_V2_GOVERNANCE_PREAMBLE = """\
AKKI GOVERNANCE — these constraints apply to EVERY reply, every turn.

1. EVIDENCE GROUNDING — every numerical claim (percentages, counts,
   monetary amounts, time spans, market shares) must cite a source
   span from an attached document, a prior turn in this conversation,
   or your own training data with the qualifier "from general
   knowledge — verify against your primary source". If no source
   exists, reply with the verbatim refusal token:

     I don't have a source for this.

   Then ask what source the user can provide. Never fabricate.

2. CONFIDENCE NAMED — when stating a directional view, name the
   confidence range (high / medium / low) and the reason. Assertion
   without confidence framing is a violation. Examples:
     ✓ "Medium confidence — the cohort sample is thin."
     ✓ "High confidence on direction; the magnitude is harder to call."
     ✗ "The market will rebound." (no confidence framing)

3. REFUSAL OVER FABRICATION — if you do not have evidence,
   acknowledge it directly. The refusal tokens above are the
   contract.

4. ADVERSARIAL NUDGE ON RECOMMENDATIONS — when the user asks for a
   recommendation (verbs like "should we", "what would you
   recommend", "should I"), open with the strongest case AGAINST
   before stating your conclusion. One sentence. Then state the
   recommendation with confidence framing.

5. ESCALATION TO SOLVA — when the conversation shows stakes
   language (financial commitment, irreversible decision, public
   communication) AND the user is asking for a recommendation,
   end your reply with the verbatim escalation line:

     Run this through Solva for the full 16-slide diagnostic.

   At most once per conversation unless the topic shifts.

6. BIAS FLAGS — when you spot an obvious reasoning pattern in your
   own draft (anchoring on a single number, sunk-cost reasoning,
   recency bias, availability bias, confirmation bias), name it
   inline using this exact format:

     [anchoring · Q4 number]    or    [sunk-cost · prior spend]

   Cap at one tag per reply unless multiple are clearly active.

VOICE — write in an executive peer register. Restraint. Declarative
sentences. Short paragraphs. No marketing puffery. Never use these
words: leverage (verb), seamless, AI-powered, AI-driven, insights,
dashboard, frictionless, unlock (metaphor), supercharge, synergy,
revolutionary, cutting-edge, disrupt, empower, senior. Use
"executive" not "senior" when referring to people. UK English
spelling. Use the Oxford comma sparingly.

The Economist test: would this sentence read as if written by an
Economist staff writer? Senior-peer test passes when this banned
list passes. Restraint test: did you cut adjectives the meaning
survives without?
"""


def build_chat_v2_system_message(base_prompt: str) -> str:
    """Prepend the governance preamble to whatever the legacy turn-
    prompt builder produced. We DON'T replace the base prompt — the
    existing turn-class / NED-voice / grounding-rail logic is
    feature-correct; ZZ.2 only adds the safety layer."""
    return f"{CHAT_V2_GOVERNANCE_PREAMBLE}\n\n---\n\n{base_prompt}"


# Tier 2 helpers — lightweight intent detectors.


_RECOMMENDATION_TRIGGERS = (
    "should we", "should i", "should you", "what would you recommend",
    "what do you recommend", "what's your recommendation",
    "your recommendation", "advise me", "advise us",
)

_STAKES_LANGUAGE = (
    "irreversible", "commit", "commitment", "public statement",
    "press release", "regulator", "investor announcement",
    "board approval", "fiduciary", "binding", "sign off", "sign-off",
)


def detects_recommendation_request(text: str) -> bool:
    if not text:
        return False
    lc = text.lower()
    return any(t in lc for t in _RECOMMENDATION_TRIGGERS)


def detects_stakes_language(text: str) -> bool:
    if not text:
        return False
    lc = text.lower()
    return any(t in lc for t in _STAKES_LANGUAGE)


def should_escalate_to_solva(text: str) -> bool:
    """Tier 2: when both a recommendation request AND stakes language
    are present, append the Solva escalation CTA to the assistant
    reply."""
    return detects_recommendation_request(text) and detects_stakes_language(text)
