"""Phase B.2 — Two-pass method baked into chat.

Holds the verbatim canonical prompts from `/app/docs/MEMO.md` Item 8 plus
deterministic helpers used by `routers/chat.py`:

  • CANONICAL_TWO_PASS_PROMPT     — verbatim from MEMO Item 8
  • CHAT_ADAPTED_FOUR_CHECK_PROMPT — verbatim from MEMO Item 8
  • REFUSAL_TEMPLATES             — the 3 verbatim refusal patterns
  • BANNED_WORDS                  — union of MEMO Item 8 + WEBSITE_BRIEF_V3 §1.3
  • TURN_CLASSES                  — labels
  • classify_turn(...)            — fast heuristic + optional LLM fallback
  • parse_four_check_label(...)   — scan the assistant reply for a labelled
                                    surface line (TENSION:/CONTRADICTION:/…)
  • detect_refusal_reason(...)    — match assistant reply against the 3
                                    refusal templates → one of
                                    {"thin_input","unsourced_claim",
                                     "named_assumption"} or None
  • find_banned_word(...)         — word-boundary regex scan, returns the
                                    first hit or None
  • split_two_pass(...)           — extract pass_1 / pass_2 blocks from the
                                    delimited LLM output
  • build_system_prompt(...)      — assemble the per-turn system message
                                    given the classified turn and
                                    visibility flag

Hard rule from the brief: do NOT paraphrase, shorten, or optimise the
verbatim prompt strings. They are product specs — the model is meant to
see them exactly as written.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("akki.two_pass")


# =============================================================================
# VERBATIM PROMPTS — from /app/docs/MEMO.md Item 8 (lines 325–347, 351–371)
# =============================================================================

CANONICAL_TWO_PASS_PROMPT = """CANONICAL TWO-PASS METHOD PROMPT — paste verbatim

Operate under the two-pass method:

PASS 1 — SOLVE. Apply the four-layer reasoning architecture to the work itself before producing.
- Layer 1 (Surface): Generate 5-7 candidate framings for the task. Each substantively different.
- Layer 2 (Depth): Triangulate against context. Detect tensions and tag severity (CRITICAL / MATERIAL / MINOR).
- Layer 3 (Synthesis): Probability-weight the candidates with confidence intervals. Run sensitivity analysis. Refusal-check: do you have enough to weight scenarios honestly? If not, ask for more before proceeding. Select the winner.
- Layer 4 (Reflection): Three questions — what would change my mind? What's the explanation in six months if I got this wrong? What am I disappointed by?

PASS 2 — BUILD. Once Pass 1 has selected, build the deliverable.
- Honour Pass 1's positioning fully. Do not hedge into other scenarios.
- Apply operating preferences without negotiation.
- Validate the build against Pass 1's implicit acceptance criteria.

OPERATING PREFERENCES:
- No glazing. Stress-test before validating. Lead with what is wrong or missing.
- Direct and concise. First sentence is the substantive answer.
- The Economist test, senior peer test, restraint test must pass.
- Banned words: leverage (verb), empower, AI-powered, insights (noun), dashboard, game-changer, revolutionary, cutting-edge, disrupt, unlock, supercharge, seamless, frictionless, all under one roof, transform (generic), synergy.
- If production reveals Pass 1 was wrong, surface it — don't push through.

When you receive a task, begin with Pass 1 visibly. Show your candidate generation, your triangulation, your weighting, your selection, your reflection. Then proceed to Pass 2."""


CHAT_ADAPTED_FOUR_CHECK_PROMPT = """CHAT-ADAPTED FORM — applies on every substantive user turn, silently

Before responding to the user, evaluate four things in the background:

1. TENSION. Is the user's framing in tension with evidence I can see? With prior conversation? With what they said earlier in this same conversation? Surface the tension only if material.

2. CONTRADICTION. Is what the user is saying internally contradictory, or does it contradict prior context I have? If yes, name it gently.

3. ASSUMPTION. What is the user assuming that may not hold? Is the assumption load-bearing for their framing? If load-bearing and questionable, name it.

4. FRAMING LIMITATION. Is the user asking the right question? Or is there a question underneath theirs that would produce a more useful answer? If yes, briefly offer the reframe before answering the original.

Then respond. The four checks happen silently. The response surfaces them only when material — never as a performance of process. If all four pass cleanly, just answer.

Apply the operating preferences from the canonical method:
- No glazing. Don't open with affirmation phrases.
- Lead with the substantive answer in the first sentence.
- If evidence is thin, name it; do not fabricate to look helpful.
- Banned words apply (leverage, empower, AI-powered, insights as noun, etc.).

The framework's job is to guard the user against fabrication and the LLM against misdirection. Apply it on every substantive turn."""


# Three refusal templates — verbatim from MEMO Item 8 (lines 381–383).
# Stored as authorised response patterns the LLM is told it MAY use when
# the four-check determines that an honest answer requires evidence the
# user has not provided.
REFUSAL_TEMPLATES = {
    "thin_input": (
        "I can give you candidate framings, but I don't have enough to "
        "weight them honestly. What would help: [specific evidence the "
        "user could provide]."
    ),
    "unsourced_claim": (
        "This claim isn't supported by what I can see. We'd need "
        "[specific source] to include it."
    ),
    "named_assumption": (
        # Memo describes this third path as "names the assumptions before
        # answering" rather than a fixed sentence. We instruct the model
        # to begin its reply with one of the two cue phrases below so the
        # detector can score the refusal reason and the audit row can
        # carry refusal_reason="named_assumption".
        "ASSUMPTION: [load-bearing assumption named here]. Given that, "
        "[answer that depends on the assumption]."
    ),
}


# =============================================================================
# Banned-word list — union of MEMO Item 8 OPERATING PREFERENCES (line 344)
# and /app/docs/WEBSITE_BRIEF_V3.md §1.3 (lines 28–45). De-duplicated;
# variants the v3 brief calls out explicitly are enumerated alongside the
# memo root term so the regex word-boundary scan catches them.
#
# Conservative philosophy: word-boundary match only, case-insensitive.
# Verb-vs-noun ("leverage as a verb", "insights as a noun"), generic-use
# qualifiers ("solutions used generically", "transform used generically",
# "end-to-end as a feature claim") cannot be enforced without an LLM —
# we flag any hit and let the retry path (Deliverable 5) ask the model
# to rephrase. Per the brief: "Do not add or remove words based on taste."
# =============================================================================
BANNED_WORDS: List[str] = [
    # MEMO Item 8 OPERATING PREFERENCES
    "leverage",                # verb-only per brief; enforced as plain match
    "empower",
    "empowering",
    "AI-powered",
    "insights",                # noun-only per brief; plain match
    "dashboard",
    "game-changer",
    "game-changing",
    "revolutionary",
    "revolutionise",
    "revolutionize",
    "cutting-edge",
    "disrupt",
    "disruptive",
    "unlock",
    "unlocking",
    "supercharge",
    "supercharged",
    "seamless",
    "frictionless",
    "all under one roof",
    "transform",               # generic-use per brief; plain match
    "transformation",
    "synergy",
    "synergistic",
    # WEBSITE_BRIEF_V3 §1.3 additions not in the memo
    "AI-driven",
    "solutions",               # generic-use per brief
    "end-to-end",              # feature-claim per brief
    "one-stop-shop",
]

# Pre-compile a single word-boundary regex. Hyphenated entries like
# "cutting-edge" are escaped so the dash is literal; the boundary
# anchors handle the surrounding whitespace correctly. Phrase entries
# ("all under one roof", "one-stop-shop") match as fixed strings with
# whitespace tolerated by the trailing/leading anchors.
def _build_banned_re() -> re.Pattern:
    parts = []
    for w in BANNED_WORDS:
        # Use \b boundaries; for phrases keep them as the regex
        # word-boundary handling already covers the leading/trailing
        # word characters at each end.
        parts.append(r"\b" + re.escape(w) + r"\b")
    return re.compile("(" + "|".join(parts) + ")", re.IGNORECASE)


_BANNED_RE = _build_banned_re()


def find_banned_word(text: str) -> Optional[str]:
    """Return the first banned-word hit (lowercase, normalised) or None."""
    if not text:
        return None
    m = _BANNED_RE.search(text)
    if not m:
        return None
    return m.group(1).lower()


# =============================================================================
# Turn classifier
# =============================================================================
TURN_CLASSES = (
    "trivial",
    "light_substantive",
    "substantive_analytical",
    "strategic_deliverable",
)

# Heuristic patterns. Trivial set is tight on purpose — anything outside
# falls through to substantive paths.
_TRIVIAL_RE = re.compile(
    r"^\s*("
    r"thanks(?:\s+(?:very\s+)?(?:much|a\s*lot|a\s*ton))?"
    r"|thank\s+you(?:\s+(?:very\s+)?(?:much|a\s*lot))?"
    r"|thx|ty|cheers|noted|got\s+it|gotcha|copy(?:\s*that)?"
    r"|ok(?:ay)?|alright|sure|yeah|yep|yes|nope|no(?:\s*thanks)?"
    r"|cool|nice|great|perfect|sounds\s*good|appreciate(?:d)?(?:\s+it)?"
    r")\s*[!.,]*\s*$",
    re.IGNORECASE,
)

# Strategic deliverable verbs/objects (match BOTH a verb AND an object).
_STRAT_VERBS = (
    "draft", "write", "compose", "produce", "generate", "create",
    "prepare", "put together", "build", "author",
)
_STRAT_OBJECTS = (
    "memo", "deck", "report", "brief", "briefing", "paper",
    "position paper", "policy paper", "document", "letter", "email",
    "presentation", "proposal", "summary", "minutes", "white paper",
    "board pack", "boardpack", "one-pager", "one pager",
    "speech", "statement",
)

_STRAT_VERB_RE = re.compile(
    r"\b(" + "|".join(re.escape(v) for v in _STRAT_VERBS) + r")\b",
    re.IGNORECASE,
)
_STRAT_OBJ_RE = re.compile(
    r"\b(" + "|".join(re.escape(o) for o in _STRAT_OBJECTS) + r")\b",
    re.IGNORECASE,
)

# Q-word starts for light-substantive heuristic.
_QWORD_RE = re.compile(
    r"^\s*(what|when|where|who|which|can|could|will|would|is|are|do|"
    r"does|did|how|why|should|may|might)\b",
    re.IGNORECASE,
)


def heuristic_classify(text: str) -> Optional[str]:
    """Return a class label if the heuristic is confident, else None.

    Confidence rules (in order):
      1. Tight trivial regex over the whole stripped string (≤ ~25 chars
         range, but the regex is the source of truth).
      2. Strategic deliverable iff (verb AND object) match anywhere.
      3. Light substantive iff short (≤ 80 chars) and Q-word + '?'
         OR very short (≤ 40 chars) regardless.
      4. Otherwise None — caller may run an LLM fallback or default.
    """
    if not text:
        return None
    s = text.strip()
    if not s:
        return None

    if _TRIVIAL_RE.match(s):
        return "trivial"

    has_verb = bool(_STRAT_VERB_RE.search(s))
    has_obj = bool(_STRAT_OBJ_RE.search(s))
    if has_verb and has_obj:
        return "strategic_deliverable"

    if len(s) <= 80:
        if _QWORD_RE.match(s) and "?" in s:
            return "light_substantive"
        if len(s) <= 40:
            return "light_substantive"

    return None  # ambiguous


def classify_turn(
    text: str,
    *,
    force_class: Optional[str] = None,
    llm_fallback: Optional[Callable[[str], Awaitable[Optional[str]]]] = None,
    fallback_timeout_ms: int = 350,
) -> Dict[str, Any]:
    """Synchronous classifier (heuristic + override only).

    The async wrapper `classify_turn_async` adds the optional LLM
    fallback for ambiguous cases under a wall-clock budget. p95 ≤ 400 ms
    is satisfied by the heuristic on every cleanly-matched case (sub-1 ms)
    and a fast-fail timeout on the LLM path. On classifier error or
    timeout, default to substantive_analytical (per the brief).
    """
    t0 = time.monotonic()
    if force_class in TURN_CLASSES:
        return {
            "turn_class": force_class,
            "source": "forced",
            "latency_ms": 0,
        }
    h = heuristic_classify(text)
    if h is not None:
        return {
            "turn_class": h,
            "source": "heuristic",
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }
    return {
        "turn_class": "substantive_analytical",
        "source": "default_ambiguous",
        "latency_ms": int((time.monotonic() - t0) * 1000),
    }


async def classify_turn_async(
    text: str,
    *,
    force_class: Optional[str] = None,
    llm_fallback: Optional[Callable[[str], Awaitable[Optional[str]]]] = None,
    fallback_timeout_ms: int = 350,
) -> Dict[str, Any]:
    """Async classifier — heuristic first, optional LLM fallback under budget."""
    import asyncio as _asyncio
    t0 = time.monotonic()
    if force_class in TURN_CLASSES:
        return {"turn_class": force_class, "source": "forced", "latency_ms": 0}
    h = heuristic_classify(text)
    if h is not None:
        return {
            "turn_class": h,
            "source": "heuristic",
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }
    if llm_fallback is None:
        return {
            "turn_class": "substantive_analytical",
            "source": "default_ambiguous",
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }
    try:
        cls = await _asyncio.wait_for(
            llm_fallback(text),
            timeout=fallback_timeout_ms / 1000.0,
        )
        if cls in TURN_CLASSES:
            return {
                "turn_class": cls,
                "source": "llm",
                "latency_ms": int((time.monotonic() - t0) * 1000),
            }
        return {
            "turn_class": "substantive_analytical",
            "source": "default_llm_invalid",
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }
    except _asyncio.TimeoutError:
        return {
            "turn_class": "substantive_analytical",
            "source": "default_llm_timeout",
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("two_pass classifier llm_fallback error: %s", e.__class__.__name__)
        return {
            "turn_class": "substantive_analytical",
            "source": "default_llm_error",
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }


# =============================================================================
# Reply post-processing helpers
# =============================================================================
_FOUR_CHECK_LABELS = ("TENSION", "CONTRADICTION", "ASSUMPTION", "FRAMING LIMITATION")
_FOUR_CHECK_RE = re.compile(
    r"^\s*(" + "|".join(_FOUR_CHECK_LABELS) + r"):\s",
    re.IGNORECASE,
)


def parse_four_check_label(reply: str) -> Optional[str]:
    """Return the labelled four-check finding ("TENSION" etc.) if the
    reply opens with one of the four labels followed by a colon. Else None.
    """
    if not reply:
        return None
    m = _FOUR_CHECK_RE.match(reply.lstrip())
    if not m:
        return None
    return m.group(1).upper()


# Phrase fingerprints for refusal detection. We match on robust verbatim
# substrings (case-insensitive) rather than the entire template so the
# model can adapt the bracketed `[specific evidence …]` slot.
_THIN_INPUT_FP = (
    "candidate framings",
    "don't have enough to weight",
)
_UNSOURCED_FP = (
    "isn't supported by what i can see",
    "we'd need",
)


_REFUSAL_TAG_RE = re.compile(
    r"^\s*\[\[\s*REFUSAL\s*:\s*(thin_input|unsourced_claim|named_assumption)\s*\]\]\s*\n?",
    re.IGNORECASE,
)


def extract_refusal_tag(reply: str) -> Tuple[Optional[str], str]:
    """If the LLM emitted a [[REFUSAL:reason]] tag at the top of its
    reply, return (reason, reply_with_tag_stripped). Otherwise (None, reply).
    """
    if not reply:
        return None, reply or ""
    m = _REFUSAL_TAG_RE.match(reply)
    if not m:
        return None, reply
    return m.group(1).lower(), reply[m.end():]


def detect_refusal_reason(reply: str) -> Optional[str]:
    """Return the refusal reason label or None.

    Order:
      1. Explicit `[[REFUSAL:<reason>]]` tag at the top — most reliable.
      2. Verbatim fingerprint match (legacy memo phrasings).
      3. Permissive fallback for paraphrased refusals: the model often
         says "I can't include that claim" or "I don't have enough"
         without using the exact memo phrasing. We match a small set
         of robust paraphrase fingerprints and only return a reason
         when at least two corroborating phrases are present.
      4. Reply opens with `ASSUMPTION:` → named_assumption.
    """
    if not reply:
        return None
    tag, _ = extract_refusal_tag(reply)
    if tag:
        return tag
    s = reply.lower()
    if all(fp in s for fp in (fp.lower() for fp in _THIN_INPUT_FP)):
        return "thin_input"
    if all(fp in s for fp in (fp.lower() for fp in _UNSOURCED_FP)):
        return "unsourced_claim"
    # Permissive fallbacks (require 2-of-N hits to avoid false positives)
    thin_paraphrases = (
        "don't have enough", "not enough to answer", "not enough information",
        "candidate framings", "weight them honestly",
        "what would help", "share the specifics",
    )
    if sum(1 for fp in thin_paraphrases if fp in s) >= 2:
        return "thin_input"
    unsourced_paraphrases = (
        "isn't supported", "is not supported", "i can't include",
        "i cannot include", "no basis to", "i don't have your",
        "we'd need", "we would need", "haven't shared", "have not shared",
        "to include it", "to back that claim", "without evidence",
    )
    if sum(1 for fp in unsourced_paraphrases if fp in s) >= 2:
        return "unsourced_claim"
    label = parse_four_check_label(reply)
    if label == "ASSUMPTION":
        return "named_assumption"
    return None


# Two-pass output delimiters. We instruct the LLM to emit Pass 1 / Pass 2
# wrapped in these markers so we can split deterministically post-call.
PASS_1_MARKER = "===PASS_1==="
PASS_2_MARKER = "===PASS_2==="


def split_two_pass(raw: str) -> Tuple[Optional[str], str]:
    """Return (pass_1, pass_2). pass_1 is None when the markers are absent.

    The contract is permissive — if the model omits the markers we
    treat the whole output as Pass 2 (so the user still gets an answer)
    and the audit row will record `pass_1=None`.
    """
    if not raw:
        return None, ""
    if PASS_1_MARKER in raw and PASS_2_MARKER in raw:
        try:
            after_p1 = raw.split(PASS_1_MARKER, 1)[1]
            p1, rest = after_p1.split(PASS_2_MARKER, 1)
            return p1.strip(), rest.strip()
        except Exception:  # noqa: BLE001
            pass
    if PASS_2_MARKER in raw:
        before, after = raw.split(PASS_2_MARKER, 1)
        return (before.strip() or None), after.strip()
    return None, raw.strip()


# Trigger phrases that turn on visible Pass 1 even without the
# UI toggle. Memo Item 8 §"Open questions" instinct: "think harder"
# forces the full canonical method; "show your reasoning" surfaces
# the silent checks. We extend with "walk me through" per the brief.
_VISIBLE_PASS_1_CUES_RE = re.compile(
    r"\b("
    r"think\s+harder|reason\s+in\s+full|show\s+your\s+reasoning|"
    r"walk\s+me\s+through|talk\s+me\s+through|"
    r"explain\s+your\s+thinking|show\s+(?:me\s+)?your\s+work"
    r")\b",
    re.IGNORECASE,
)


def has_visible_pass_1_cue(text: str) -> bool:
    return bool(_VISIBLE_PASS_1_CUES_RE.search(text or ""))


# =============================================================================
# System-prompt assembly
# =============================================================================
_BASE_VOICE = (
    "You are AKKI, a calm, editorial intelligence partner for executives "
    "and non-executive directors. Tone: precise, neutral, no hype, "
    "Economist-style cadence. When tokens like [EMAIL_1] or [PERSON_3] "
    "appear, treat each as a stable referent — reason about it without "
    "asking the user what it means; the system will rehydrate the real "
    "value before the user reads your reply."
)


_OPERATING_VOICE = (
    "OPERATING PREFERENCES (apply on every reply):\n"
    "- No glazing. Don't open with affirmation phrases.\n"
    "- Lead with the substantive answer in the first sentence.\n"
    "- If evidence is thin, name it; do not fabricate to look helpful.\n"
    "- Banned words apply (leverage, empower, AI-powered, insights as "
    "noun, dashboard, seamless, unlock, etc.) — see canonical list.\n"
    "- The Economist test, senior peer test, restraint test must pass."
)


_FOUR_CHECK_OUTPUT_RULE = (
    "If a four-check finding is material, prefix your reply with a single "
    "labelled sentence: \"TENSION: …\" or \"CONTRADICTION: …\" or "
    "\"ASSUMPTION: …\" or \"FRAMING LIMITATION: …\". Otherwise, just "
    "answer — never narrate that the four checks ran."
)


_REFUSAL_BLOCK = (
    "AUTHORISED REFUSAL PATTERNS (use one when the four-check shows you do "
    "not have enough to answer honestly — never fabricate to look helpful):\n"
    f"- Thin analysis input: \"{REFUSAL_TEMPLATES['thin_input']}\"\n"
    f"- Unsourced draft claim: \"{REFUSAL_TEMPLATES['unsourced_claim']}\"\n"
    "- Load-bearing assumption: name the assumption first by opening with "
    "\"ASSUMPTION: <the assumption>.\" then proceed.\n"
    "\n"
    "REFUSAL TAG (mandatory when you refuse): If — and only if — you are "
    "applying one of the three refusal patterns above, the FIRST line of "
    "your reply MUST be a single tag on its own line:\n"
    "  [[REFUSAL:thin_input]]      — when the analysis input is too thin\n"
    "  [[REFUSAL:unsourced_claim]] — when the user asks you to include a\n"
    "                                claim you cannot evidence\n"
    "  [[REFUSAL:named_assumption]] — when you must name a load-bearing\n"
    "                                 assumption to answer honestly\n"
    "The system strips the tag before the user reads your reply, so the "
    "user sees only your refusal text — but the audit log records the "
    "category structurally. Do NOT use the tag if you are answering "
    "normally; the tag is exclusively for refusals."
)


def build_system_prompt(
    *,
    turn_class: str,
    show_pass_1: bool,
    has_grounding: bool,
) -> str:
    """Assemble the per-turn system message.

    Layering:
      • Base voice always.
      • Operating preferences (banned-word reminder) always.
      • Four-check (CHAT_ADAPTED_FOUR_CHECK_PROMPT) for light_substantive
        and above (silent — surfaced only if material).
      • Refusal patterns block for light_substantive and above.
      • Canonical two-pass + delimiter rule for strategic_deliverable.
      • Grounding rail when context-tethered.
    """
    parts: List[str] = [_BASE_VOICE]

    if has_grounding:
        parts.append(
            "A [GROUNDING] block follows containing extracted paragraphs from "
            "the user's documents. Cite ONLY using the inline marker "
            "[[cite:<anchor_id>]] where <anchor_id> appears in the block. "
            "Never invent anchor ids. If the answer is not in the grounding "
            "block, say so plainly rather than guessing."
        )

    parts.append(_OPERATING_VOICE)

    # Trivial turns: no four-check, no refusal block, just answer.
    if turn_class == "trivial":
        return "\n\n".join(parts)

    # light_substantive / substantive_analytical / strategic_deliverable
    parts.append(CHAT_ADAPTED_FOUR_CHECK_PROMPT)
    parts.append(_FOUR_CHECK_OUTPUT_RULE)
    parts.append(_REFUSAL_BLOCK)

    if turn_class == "strategic_deliverable":
        parts.append(CANONICAL_TWO_PASS_PROMPT)
        if show_pass_1:
            parts.append(
                "OUTPUT FORMAT (mandatory, two-pass deliverable):\n"
                "Line 1 of your reply MUST be exactly:\n"
                f"  {PASS_1_MARKER}\n"
                "Then write Pass 1 reasoning (candidate framings, "
                "triangulation, weighting, reflection). Then on a new "
                "line write exactly:\n"
                f"  {PASS_2_MARKER}\n"
                "Then write the deliverable below the second marker. "
                "Both markers are REQUIRED on every reply at this turn "
                "class — even if Pass 1 is brief, you must emit the "
                "markers so the system can split the passes for the "
                "audit log. The user will see Pass 1 in a collapsible "
                "panel above the deliverable."
            )
        else:
            parts.append(
                "OUTPUT FORMAT (mandatory, two-pass deliverable):\n"
                "Line 1 of your reply MUST be exactly:\n"
                f"  {PASS_1_MARKER}\n"
                "Then write Pass 1 reasoning (candidate framings, "
                "triangulation, weighting, reflection). Then on a new "
                "line write exactly:\n"
                f"  {PASS_2_MARKER}\n"
                "Then write the deliverable below the second marker. "
                "Both markers are REQUIRED on every reply at this turn "
                "class — even if Pass 1 is brief, you must emit the "
                "markers so the system can record the reasoning for "
                "audit. The user will see ONLY the deliverable; Pass 1 "
                "is recorded for audit but not shown."
            )

    return "\n\n".join(parts)


# =============================================================================
# Banned-word retry instruction
# =============================================================================
def banned_word_retry_instruction(banned_word: str) -> str:
    """Return the system-message used for the single retry call."""
    return (
        "Your previous output contained the banned word "
        f"'{banned_word}'. Regenerate the reply with the SAME content "
        "but without using that word or any of its variants. Banned "
        "words: " + ", ".join(BANNED_WORDS) + "."
    )
