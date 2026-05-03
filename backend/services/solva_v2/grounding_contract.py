"""Solva v2 — 5-tier grounding contract parser (Phase 15.0).

CONTRACT (the parser IS the contract)
-------------------------------------
Every non-question sentence in a Solva v2 synthesis output MUST carry exactly
one tier marker of the form `[T:<tier>]`, placed at the end of the sentence,
immediately before the terminating punctuation OR directly after it.

The five locked tiers (no synonyms, no new names):
    - corpus          claim grounded in user-supplied content (documents,
                      intent, prior turns)
    - comparable      claim grounded in a curated comparable from
                      db.solve_comparables
    - domain_prior    claim drawn from general boardroom / industry domain
                      knowledge the model brings
    - user_assertion  restatement of something the user explicitly asserted
    - speculation     a hypothesis or possibility offered tentatively

Valid examples:
    "Revenue slipped 14% last quarter [T:corpus]."
    "A comparable mid-cap bank found the cause was onboarding friction [T:comparable]."
    "The board may be avoiding the pricing question [T:speculation]."

Questions do not require markers. The model can end a paragraph with a
question to the user without tagging it.

Retry protocol (orchestrator-side, not parser-side):
    attempt 1 -> parse -> if invalid, re-prompt with missing/bad list
    attempt 2 -> parse -> if invalid, re-prompt once more
    attempt 3 -> parse -> if invalid, return structured error
                         {error: "grounding_contract_violation",
                          untagged_sentences, malformed_markers}

Versioning: this module exposes `CONTRACT_VERSION` so audit entries can
record which parser version produced the `claims[]` array.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional

# -----------------------------------------------------------------------------
# Locked tier vocabulary. Do not add without a roadmap amendment.
# -----------------------------------------------------------------------------
TIER_NAMES: List[str] = [
    "corpus",
    "comparable",
    "domain_prior",
    "user_assertion",
    "speculation",
]
TIER_SET = set(TIER_NAMES)

# Matches any [T:word] whether or not the word is a valid tier; we match
# broadly so malformed markers surface rather than being silently ignored.
TIER_MARKER_RE = re.compile(r"\[T:([a-zA-Z_]+)\]")

# Splits a body into sentences while keeping the sentence-ending punctuation
# attached to the sentence it terminates. Handles '.', '?', '!'.
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\[\"'(])")

CONTRACT_VERSION = "solva_v2_grounding@1.0"


@dataclass
class Claim:
    text: str
    tier: str
    # confidence_* are null in 15.0; probability_weighting engine arrives in 15.1
    confidence_band: Optional[str] = None
    confidence_pct: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ParseResult:
    valid: bool
    claims: List[Claim] = field(default_factory=list)
    untagged_sentences: List[str] = field(default_factory=list)
    malformed_markers: List[Dict[str, str]] = field(default_factory=list)
    stripped_text: str = ""
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "claims": [c.to_dict() for c in self.claims],
            "untagged_sentences": self.untagged_sentences,
            "malformed_markers": self.malformed_markers,
            "stripped_text": self.stripped_text,
            "raw_text": self.raw_text,
            "contract_version": CONTRACT_VERSION,
        }


def _split_sentences(text: str) -> List[str]:
    if not text:
        return []
    # Normalise whitespace first
    t = re.sub(r"\s+", " ", text).strip()
    if not t:
        return []
    # Use the split regex but keep the sentence boundary by re-joining.
    # Simple approach: split on lookbehind for [.!?] followed by whitespace.
    parts = SENTENCE_SPLIT_RE.split(t)
    # Collapse blanks
    return [p.strip() for p in parts if p.strip()]


def _is_question(sentence: str) -> bool:
    s = sentence.rstrip()
    return s.endswith("?")


def _strip_trailing_punct_for_claim(sentence: str) -> str:
    # Keep the inner text intelligible; trim just the terminal punctuation
    # so downstream rendering can re-append.
    return re.sub(r"[\s.]+$", "", sentence).strip()


def parse(synthesis_body: str) -> ParseResult:
    """Walk the synthesis body. Extract tier-tagged claims.

    Contract: every non-question sentence must carry exactly one valid
    [T:<tier>] marker. Violations populate untagged_sentences and
    malformed_markers; `valid` is True only when both are empty.
    """
    sentences = _split_sentences(synthesis_body)
    claims: List[Claim] = []
    untagged: List[str] = []
    malformed: List[Dict[str, str]] = []

    for sent in sentences:
        if _is_question(sent):
            continue
        # Short sentences under 12 chars are treated as connective / headers
        # and not required to carry a marker. This avoids flagging things
        # like "Three points." or markdown list headers.
        if len(sent) < 12:
            continue
        markers = TIER_MARKER_RE.findall(sent)
        if not markers:
            untagged.append(sent)
            continue
        # First marker wins; duplicate markers do NOT fail parse.
        primary = markers[0].strip()
        if primary not in TIER_SET:
            malformed.append({"sentence": sent, "bad_tier": primary})
            continue
        # Strip ALL tier markers from the claim text for storage.
        stripped = TIER_MARKER_RE.sub("", sent).strip()
        stripped = _strip_trailing_punct_for_claim(stripped)
        if stripped:
            claims.append(Claim(text=stripped, tier=primary))

    stripped_text = TIER_MARKER_RE.sub("", synthesis_body).strip() if synthesis_body else ""
    valid = len(untagged) == 0 and len(malformed) == 0
    return ParseResult(
        valid=valid,
        claims=claims,
        untagged_sentences=untagged,
        malformed_markers=malformed,
        stripped_text=stripped_text,
        raw_text=synthesis_body or "",
    )


def summarise_tier_distribution(claims: List[Claim]) -> Dict[str, int]:
    """Return a count of claims per tier, zero-filled for all 5 tiers."""
    dist = {name: 0 for name in TIER_NAMES}
    for c in claims:
        dist[c.tier] = dist.get(c.tier, 0) + 1
    return dist


def input_hash(shielded_text: str) -> str:
    """sha256 of the shielded (post-Synisense) input. Never the raw input."""
    return hashlib.sha256((shielded_text or "").encode("utf-8")).hexdigest()


# -----------------------------------------------------------------------------
# Model-facing prompt. Appended to every synthesis system_message.
# -----------------------------------------------------------------------------
GROUNDING_CONTRACT_PROMPT = (
    "\n\n"
    "GROUNDING CONTRACT (mandatory, non-negotiable):\n"
    "Every assertive sentence you write MUST end with exactly one tier\n"
    "marker: [T:corpus], [T:comparable], [T:domain_prior], [T:user_assertion],\n"
    "or [T:speculation]. Place the marker directly before the sentence's\n"
    "terminating punctuation.\n\n"
    "Tier definitions:\n"
    "  - [T:corpus]         claim grounded in content the user has shared\n"
    "                       (their intent, prior turns, documents)\n"
    "  - [T:comparable]     claim grounded in the curated comparable\n"
    "                       diagnoses provided to you in the context\n"
    "  - [T:domain_prior]   claim drawn from general boardroom or industry\n"
    "                       domain knowledge\n"
    "  - [T:user_assertion] restatement of something the user asserted\n"
    "  - [T:speculation]    a hypothesis or possibility offered tentatively\n\n"
    "Questions you put to the user and imperative sentences (\"Consider X.\")\n"
    "do not require markers.\n\n"
    "Example of compliant output:\n"
    "  Revenue slipped 14% last quarter [T:corpus]. A comparable mid-cap bank\n"
    "  found the cause was onboarding friction [T:comparable]. The board may\n"
    "  be avoiding the pricing question [T:speculation]. What does the\n"
    "  activation-rate dashboard show?\n\n"
    "Do NOT omit markers. Do NOT invent new tier names. Do NOT place markers\n"
    "mid-sentence. Do NOT tag questions.\n"
)


GROUNDING_RETRY_PROMPT = (
    "\n\nYour previous response violated the grounding contract. Specifically:\n"
    "  - Untagged sentences (each must end with a [T:<tier>] marker): {untagged}\n"
    "  - Malformed markers (tier must be one of {valid_tiers}): {malformed}\n\n"
    "Rewrite the synthesis with every assertive sentence carrying exactly one\n"
    "valid tier marker. Keep the substance; fix only the tagging.\n"
)
