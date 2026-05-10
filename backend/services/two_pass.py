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

# Phase B.2 patch (2026-05-05) — server-side deterministic emission of
# the thin-input refusal. The LLM is no longer trusted to choose this
# template; the server detects the trigger condition deterministically,
# fills the bracket from a constrained evidence-list call, and emits
# the memo's exact phrasing verbatim. The template below is the
# substitution form — `{evidence_phrase}` replaces the memo's literal
# bracket placeholder `[specific evidence the user could provide]`.
THIN_INPUT_REFUSAL_TEMPLATE = (
    "I can give you candidate framings, but I don't have enough to weight "
    "them honestly. What would help: {evidence_phrase}."
)

# Static fallback when the constrained evidence-list call fails twice.
THIN_INPUT_FALLBACK_EVIDENCE = (
    "the documents, financials, or context that frames the decision"
)


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
      3. Substantive_analytical iff a decisional/strategy pattern fires
         (must run BEFORE the light-substantive Q-word fallback because
         "Should I sell my company?" and "What should I do about X?"
         start with Q-words but are decisional, not factual — the brief
         (Deliverable 1) lists them under substantive_analytical).
      4. Light substantive iff short (≤ 80 chars) and Q-word + '?'
         OR very short (≤ 40 chars) regardless.
      5. Otherwise None — caller may run an LLM fallback or default.
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

    # Decisional / strategy intent → substantive_analytical (brief
    # Deliverable 1 examples: "what should I do about X?", "is this
    # strategy sound?"). We reuse the THIN_INPUT_PATTERNS regex set so
    # the classifier and the thin-input detector agree on what counts
    # as decisional intent.
    for _name, rx in THIN_INPUT_PATTERNS:
        if rx.search(s):
            return "substantive_analytical"

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

    # Workstream A.3 — platform knowledge corpus. Injected for every
    # non-trivial turn so the model can answer "what is X?" / "how do
    # I Y?" platform questions without hallucinating from generic
    # priors. Keep above the four-check rules so the model is grounded
    # before the silent four-check evaluates the reply.
    try:
        from services.platform_kb import get_platform_kb_block
        parts.append(get_platform_kb_block())
    except Exception:  # noqa: BLE001
        # Failing to load the KB must never break the chat path.
        # Worst case is the pre-A.3 behaviour (no platform answers).
        pass

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


# =============================================================================
# Phase B.2 patch (2026-05-05) — Server-side thin-input detection
# =============================================================================
# Memo Item 8 phrasing is "If the user asks for analysis on something
# where the input is too thin, chat says: '…'" — note "says", not "may
# say". The original B.2 implementation exposed the templates to the
# LLM as authorised response patterns and let the model decide when to
# use them. That's prompt-engineering hope. This block replaces it with
# server-side deterministic detection + verbatim emission. The fix is
# strictly scoped to the thin-input path — `unsourced_claim` and
# `named_assumption` are noted in the report as deferred candidates.
#
# Trigger conditions (ALL must hold):
#   1. turn_class ∈ {substantive_analytical, strategic_deliverable}
#   2. attached_document_ids is empty
#   3. No prior assistant turn carrying substantive content (defined
#      as len(content) ≥ 200 AND action != chat.refused)
#   4. The user message ≤ 280 chars AND matches at least one of the
#      decision/strategy patterns below.
THIN_INPUT_PATTERNS: List[Tuple[str, "re.Pattern"]] = [
    ("decision_should_i",
     re.compile(r"\b(should|do)\s+i\b", re.IGNORECASE)),
    ("what_should",
     re.compile(r"\bwhat\s+should\b", re.IGNORECASE)),
    ("which_option",
     re.compile(r"\bwhich\s+(option|path|direction)\b", re.IGNORECASE)),
    ("is_this_good",
     re.compile(r"\bis\s+(this|it)\s+(a\s+)?(good|sound|smart|wise|right)\b",
                re.IGNORECASE)),
    ("how_decide",
     re.compile(r"\bhow\s+do\s+i\s+(decide|choose|pick)\b", re.IGNORECASE)),
    ("analytic_verbs",
     re.compile(r"\b(diagnose|analyse|analyze|evaluate|assess)\b",
                re.IGNORECASE)),
    ("strategy_nouns",
     re.compile(r"\b(strategy|approach|move|decision)\b", re.IGNORECASE)),
]

THIN_INPUT_MAX_CHARS = 280


def detect_thin_input(
    *,
    turn_class: str,
    text: str,
    attached_document_ids: List[str],
    prior_substantive_turns: int,
) -> Optional[Dict[str, Any]]:
    """Return trigger metadata if all four conditions hold, else None.

    The shape is intentionally a dict so the caller can pass it straight
    into `payload.detection` for the audit row.
    """
    if turn_class not in ("substantive_analytical", "strategic_deliverable"):
        return None
    if attached_document_ids:
        return None
    if prior_substantive_turns > 0:
        return None
    s = (text or "").strip()
    if not s or len(s) > THIN_INPUT_MAX_CHARS:
        return None
    matched: Optional[str] = None
    for name, rx in THIN_INPUT_PATTERNS:
        if rx.search(s):
            matched = name
            break
    if not matched:
        return None
    return {
        "attached_docs": 0,
        "prior_substantive_turns": int(prior_substantive_turns),
        "pattern_matched": matched,
        "char_len": len(s),
        "turn_class": turn_class,
    }


def sanitize_evidence_phrase(phrase: str) -> Tuple[str, Optional[str]]:
    """Return (phrase, banned_word_hit_or_None).

    Caller is expected to retry the LLM once on a hit; on a second hit,
    drop to `THIN_INPUT_FALLBACK_EVIDENCE`. We:
      • strip enclosing quotes/whitespace and trailing periods,
      • collapse internal whitespace,
      • clip to 175 chars (template wrapper is 103 chars; the
        rendered reply must stay ≤ 280 chars per acceptance bar),
      • when the clip happens mid-item, trim back to the last comma
        boundary so the list reads cleanly.
    """
    if not phrase:
        return "", None
    p = phrase.strip().strip('"').strip("'").rstrip(".").strip()
    p = re.sub(r"\s+", " ", p)
    if len(p) > 175:
        p = p[:175]
        # Trim back to the last clean boundary so we don't end on a
        # half-word like "operations or mora" or a stray space.
        cut = max(p.rfind(", "), p.rfind("; "))
        if cut >= 60:        # keep at least 3-4 items
            p = p[:cut]
        elif p.rfind(" ") >= 60:
            p = p[: p.rfind(" ")]
        p = p.rstrip(",;: ").rstrip()
    hit = find_banned_word(p)
    return p, hit


# =============================================================================
# Workstream C.1 (2026-05-10) — deterministic detection for the other two
# refusal categories. Mirrors `detect_thin_input` shape: a function that
# returns trigger metadata or None. Both run on the ASSEMBLED ASSISTANT
# REPLY (post-stream, post-rehydration), AFTER the four-check, BEFORE
# persistence. When triggered, the caller swaps the visible reply for
# the refusal template and persists a `refusal_reason` audit row.
#
# Both are bypassable when grounding citations are present \u2014 if the
# reply contains `[[cite:` tokens or maps to citation chips, we trust
# the four-check + citation_index_validator over the regex layer.
# =============================================================================

# Numeric-claim patterns: monetary, percentage, bps, plus a
# "[number] (million|billion|customers|users|...)" bucket.
_UNSOURCED_NUMERIC_RX = re.compile(
    r"(\$\s?\d|\d+(?:\.\d+)?\s*(?:million|billion|trillion|m\b|bn\b|%|percent|bps|basis points|customers|users|employees|revenue|profit|EBITDA|MRR|ARR))",
    re.IGNORECASE,
)
# Authorial-attribution patterns ("according to X", "X reports", "data shows").
_UNSOURCED_ATTRIBUTION_RX = re.compile(
    r"\b(according to|data\s+shows|reports?\s+indicate|the\s+(report|paper|study)\s+(says|states|notes|finds|argues))\b",
    re.IGNORECASE,
)
_CITATION_TOKEN_RX = re.compile(r"\[\[cite:[A-Za-z0-9_\-]+\]\]")
_BRACKET_FOOTNOTE_RX = re.compile(r"\[\d{1,3}\]")


def detect_unsourced_claim(
    *,
    reply_text: str,
    has_grounding: bool,
    has_attached_docs: bool,
) -> Optional[Dict[str, Any]]:
    """Return trigger metadata if the reply makes a sourced-style claim
    without backing it with a citation, else None.

    Bypass conditions:
      - reply already contains a `[[cite:...]]` token (model cited)
      - reply contains a `[<n>]` footnote marker (citation pipeline)
      - the chat HAS grounding paragraphs OR attached docs AND the model
        cited at least one of them (the four-check covers the rest)
    """
    if not reply_text or len(reply_text) < 40:
        return None

    # Already cited \u2014 nothing to do.
    if _CITATION_TOKEN_RX.search(reply_text) or _BRACKET_FOOTNOTE_RX.search(reply_text):
        return None

    numeric_hit = _UNSOURCED_NUMERIC_RX.search(reply_text)
    attr_hit = _UNSOURCED_ATTRIBUTION_RX.search(reply_text)
    if not (numeric_hit or attr_hit):
        return None

    # If the user explicitly attached grounding, give the model the
    # benefit of the doubt \u2014 the four-check and the citation pipeline
    # already evaluate this. The deterministic detector is for the
    # ungrounded path, where the reply is a numeric / attributed claim
    # the model invented.
    if has_grounding or has_attached_docs:
        return None

    matched_pattern = "numeric" if numeric_hit else "attribution"
    matched_text = (numeric_hit or attr_hit).group(0)
    return {
        "pattern_matched": matched_pattern,
        "matched_text": matched_text[:80],
        "char_len": len(reply_text),
        "has_grounding": False,
        "has_attached_docs": False,
        "deterministic": True,
    }


# Capitalised name pairs (LastName / FirstLast) followed by a verb of
# intent. Single-cap names are common nouns at sentence start; require
# either two consecutive caps OR a possessive form ("Sarah's plan",
# "the CEO's intent").
_NAMED_PERSON_INTENT_RX = re.compile(
    # Group 1: a CapWord+CapWord pair OR a possessive CapWord's
    r"\b((?:[A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20})+)|(?:[A-Z][a-z]{1,20}'s))"
    # ...followed by a verb of intent / belief / plan within ~30 chars
    r"\s+\w{0,30}?\b(will|intends|believes|plans?\s+to|is\s+concerned|thinks|wants|expects|fears|opposes|supports|prefers)\b",
)
# Stop-list: phrases that match the regex but are not personal claims.
_NAMED_INTENT_STOPLIST = {
    "United States", "United Kingdom", "European Union",
    "Federal Reserve", "Wall Street", "New York", "South Africa",
}


def detect_named_assumption(
    *,
    reply_text: str,
    has_grounding: bool,
    has_attached_docs: bool,
) -> Optional[Dict[str, Any]]:
    """Return trigger metadata if the reply makes a definitive intent /
    belief / plan claim about a named individual without citation.

    Same bypass conditions as `detect_unsourced_claim`.
    """
    if not reply_text or len(reply_text) < 40:
        return None

    if _CITATION_TOKEN_RX.search(reply_text) or _BRACKET_FOOTNOTE_RX.search(reply_text):
        return None

    if has_grounding or has_attached_docs:
        return None

    m = _NAMED_PERSON_INTENT_RX.search(reply_text)
    if not m:
        return None

    name = m.group(1).strip()
    if name in _NAMED_INTENT_STOPLIST:
        return None

    verb = m.group(2).lower()
    return {
        "matched_name": name[:60],
        "matched_verb": verb,
        "char_len": len(reply_text),
        "has_grounding": False,
        "has_attached_docs": False,
        "deterministic": True,
    }


# Verbatim refusal phrasing for the two new categories. Keep these
# in lockstep with `REFUSAL_TEMPLATES` above; the detector caller
# emits these strings directly.
UNSOURCED_CLAIM_DETERMINISTIC_REFUSAL = (
    "I don't have a sourced figure for that. What you can do: attach "
    "the underlying document, and I'll cite directly."
)
NAMED_ASSUMPTION_DETERMINISTIC_REFUSAL = (
    "I shouldn't characterise {name}'s position without a source. If "
    "you have minutes or correspondence, attach them and I'll work "
    "from there."
)


def render_named_assumption_refusal(name: str) -> str:
    """Insert the matched name into the refusal template.

    Caller is responsible for sanitising the name (e.g. capping length).
    """
    safe_name = (name or "this person").strip()[:60] or "this person"
    return NAMED_ASSUMPTION_DETERMINISTIC_REFUSAL.format(name=safe_name)


# =============================================================================
# Workstream B.2 (2026-05-10) — first-message auto-naming
# =============================================================================
# Cheap heuristic title generator. Avoids an extra LLM call per chat
# (which would add ~600 ms to first-message TTFT and burn one classifier
# credit each conversation). Works on the user's first message; the
# router calls this AFTER user_msg persistence and BEFORE the LLM call.
#
# Examples (input -> output):
#   "What is Auto-Shield?"                  -> "Auto-Shield"
#   "Tell me about Solva"                   -> "Solva"
#   "How do I configure billing?"           -> "Configure billing"
#   "summarise this report"                 -> "Summarise this report"

_TITLE_LEAD_STRIP = re.compile(
    r"^(?:please\s+)?"
    r"(?:can\s+you|could\s+you|tell\s+me\s+about|explain|describe|"
    r"what\s+is|what\s+are|what's|how\s+do\s+i|how\s+can\s+i|"
    r"how\s+do\s+you|how\s+does|why\s+(?:do|does|is|are)|"
    r"give\s+me|show\s+me|walk\s+me\s+through)\s+",
    re.IGNORECASE,
)
_TITLE_TRAIL_PUNCT = re.compile(r"[\s\.\?\!\,;:\-\u2014\u2013]+$")
_TITLE_WS = re.compile(r"\s+")
_DEFAULT_TITLES_TO_REPLACE = {"", "new conversation", "untitled", "new chat"}


def heuristic_title_from_message(text: str, *, max_chars: int = 60) -> Optional[str]:
    """Derive a short conversation title from the user's first message.

    Returns None if the input is too thin to derive a meaningful title.
    """
    if not text:
        return None
    s = text.strip()
    if len(s) < 6:
        return None
    # Take only the first sentence, capped.
    for delim in ("? ", "! ", ". ", "\n"):
        idx = s.find(delim)
        if 0 < idx < max_chars + 20:
            s = s[: idx + 1]
            break
    s = _TITLE_LEAD_STRIP.sub("", s)
    s = _TITLE_TRAIL_PUNCT.sub("", s)
    s = _TITLE_WS.sub(" ", s).strip()
    if not s:
        return None
    if len(s) > max_chars:
        cut = s.rfind(" ", 0, max_chars)
        s = (s[:cut] if cut >= max_chars - 20 else s[:max_chars]).rstrip(" ,.;:")
    if not s:
        return None
    # Capitalise the first letter only; preserve the rest of the casing
    # because brand names ("Auto-Shield", "Solva") matter.
    s = s[0].upper() + s[1:] if len(s) > 1 else s.upper()
    return s


def should_auto_rename(current_title: Optional[str]) -> bool:
    """True iff the chat's current title is a placeholder we own."""
    if not current_title:
        return True
    return current_title.strip().lower() in _DEFAULT_TITLES_TO_REPLACE
