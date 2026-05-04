"""Solva v2 — Phase 15.3.5 Track B Item 1.

The no-opinion principle (load-bearing product principle):

    Solva is not supposed to share its thoughts, understanding or
    opinion with the users. During questioning, Solva is limited to the
    parameters of the solution and at no point is the LLM supposed to
    contribute its thinking outside the frame of the Solva model.

This module enforces it deterministically AFTER the LLM responds,
before the response lands in the audit log or is surfaced to the user.

Two surfaces:
  1. `OPINION_FREE_DIRECTIVE` — a constant that should be prepended to
     every Solva v2 system prompt programmatically. Single source of
     truth for the rule we ask the LLM to honour.
  2. `scan(text) -> list[str]` — a deterministic regex sweep that returns
     the list of forbidden phrases the LLM smuggled in despite the
     directive. Empty list = clean.

The orchestrator/engine that needs to enforce the rule wraps its LLM
call with the existing retry-then-fail pattern from synthesis grounding
contract (`MAX_GROUNDING_RETRIES`). Three strikes and the engine raises
a 422 with `{"error": "opinion_language_blocked", "phrases_hit": [...]}`.

The phrase list is locked-by-product. Add to it cautiously — every
addition shifts the false-positive risk up. We tune for high precision
(few false positives) on board-language inputs.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Tuple

OPINION_FREE_DIRECTIVE = (
    "BOARD-GRADE CONSTRAINT — NO FIRST-PERSON OPINION:\n"
    "You are Solva. You are an analytic instrument, not an interlocutor. "
    "You do NOT share thoughts, opinions, or beliefs. You ask precise "
    "questions and synthesize tier-marked claims grounded in the inputs. "
    "First-person opinion language is prohibited. Disallowed phrases "
    "include but are not limited to: 'I think', 'I believe', 'in my "
    "view', 'I'd suggest', 'personally', 'from my perspective', 'in my "
    "opinion', 'I'd argue', 'my take', 'if I had to guess', 'I feel', "
    "'honestly', 'to be candid', 'between us'. If a sentence would "
    "otherwise carry such language, restate it as a tier-marked claim "
    "(corpus / comparable / domain_prior / user_assertion / speculation) "
    "or remove it. Asking a clarifying question is fine; volunteering an "
    "opinion is not.\n"
)

# Locked phrase list. Add cautiously. Each entry is a regex with word-
# boundary anchors so we don't false-positive on substrings.
# We're case-insensitive and tolerate "I'd" / "I would" etc.
FORBIDDEN_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"\bI\s+think\b",                  "i think"),
    (r"\bI\s+believe\b",                "i believe"),
    (r"\bI\s+feel\b",                   "i feel"),
    (r"\bI\s+(?:am|'m|am\s+inclined)\s+inclined\b", "i am inclined"),
    (r"\bI\s+suspect\b",                "i suspect"),
    (r"\bI\s+would\s+(?:argue|suggest|say|recommend)\b",  "i would argue/suggest/say/recommend"),
    (r"\bI'd\s+(?:argue|suggest|say|recommend|venture|guess)\b", "i'd argue/suggest/say/recommend"),
    (r"\bI\s+venture\b",                "i venture"),
    (r"\bin\s+my\s+(?:view|opinion|judgement|judgment|experience|estimation)\b",
                                         "in my view/opinion/judgement"),
    (r"\bfrom\s+my\s+(?:perspective|viewpoint|vantage)\b",
                                         "from my perspective"),
    (r"\bmy\s+(?:take|view|sense|gut|hunch|intuition|opinion)\s+is\b",
                                         "my take/view/sense/gut is"),
    (r"\bpersonally\s*[,:]\s*",         "personally,"),
    # Phase B.3 — also catch standalone "personally" used as an
    # opinion-marker mid-sentence (e.g. "I would personally hold off").
    # Anchored on word boundaries so substrings like "personalised"
    # don't false-trigger.
    (r"\bpersonally\b",                  "personally"),
    (r"\bif\s+I\s+had\s+to\s+guess\b",  "if i had to guess"),
    (r"\bif\s+you\s+ask\s+me\b",        "if you ask me"),
    (r"\bhonestly\s*[,:]",              "honestly,"),
    (r"\bto\s+be\s+(?:honest|candid|frank)\s*[,:]?", "to be honest/candid/frank"),
    (r"\bbetween\s+(?:us|you\s+and\s+me)\s*[,:]?", "between us"),
    (r"\bin\s+all\s+honesty\b",         "in all honesty"),
    (r"\bI\s+lean\s+toward\b",          "i lean toward"),
    (r"\bmy\s+gut\s+(?:says|tells)\b",  "my gut says/tells"),
)


def scan(text: str) -> List[str]:
    """Return the list of distinct forbidden phrases hit in `text`.

    Empty list means the text is clean. Order is the order of first
    appearance in the source text (so the orchestrator can include the
    earliest hit in the retry instruction).
    """
    if not text:
        return []
    hits: List[Tuple[int, str]] = []
    for pat, label in FORBIDDEN_PATTERNS:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            hits.append((m.start(), label))
    # Stable sort by position; dedupe labels preserving first-position order.
    hits.sort(key=lambda x: x[0])
    seen = set()
    out = []
    for _, label in hits:
        if label in seen:
            continue
        seen.add(label)
        out.append(label)
    return out


def is_clean(text: str) -> bool:
    return not scan(text)


def enforce_opinion_free(system_prompt: str) -> str:
    """Prepend the OPINION_FREE_DIRECTIVE to a system prompt.

    Idempotent — if the directive is already at the head, leaves the
    string alone. Useful when callers compose system prompts in stages.
    """
    if system_prompt and OPINION_FREE_DIRECTIVE.split("\n", 1)[0] in system_prompt[:300]:
        return system_prompt
    return OPINION_FREE_DIRECTIVE + "\n" + (system_prompt or "")


def retry_reminder(phrases_hit: Iterable[str]) -> str:
    """Build a retry-instruction block to append to the user-side prompt
    on the next attempt. Names the specific phrases the LLM smuggled in
    so the next attempt knows what to avoid."""
    phrases = list(phrases_hit)
    if not phrases:
        return ""
    enumerated = ", ".join(f"\"{p}\"" for p in phrases[:6])
    return (
        "RETRY: Your previous response contained first-person opinion "
        f"language ({enumerated}). Restate every assertive sentence as a "
        "tier-marked claim or remove it. Do not volunteer opinion."
    )


__all__ = [
    "OPINION_FREE_DIRECTIVE",
    "FORBIDDEN_PATTERNS",
    "scan",
    "is_clean",
    "enforce_opinion_free",
    "retry_reminder",
]
