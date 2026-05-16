"""Refusal voice — coach-voice copy for Solva's discipline of declining
to produce a probability-weighted diagnosis when evidence is thin.

Templates per brief §4.7 + §5.3. NO LLM call — these strings are
locked product copy. Candidate descriptions surfaced via
`candidates_to_surface` are sanitized via
`synthesis_renderer._sanitize_internal_string` to strip Markdown
labels, layer references, and Shield `[[ENT_*]]` placeholders before
they reach user-visible prose.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..reasoning.refusal_logic import RefusalReason
from .synthesis_renderer import (
    _sanitize_internal_string,
    _strip_entity_placeholders,
    _strip_macro_names,
)


_WHAT_WOULD_HELP: Dict[str, List[str]] = {
    "seek_clarity": [
        "any memo or document where this situation is described in concrete terms",
        "minutes from the meeting where this first surfaced",
        "a written brief from whoever flagged it",
    ],
    "develop_strategy": [
        "the financials behind the options under consideration",
        "minutes from the prior round of debate",
        "a comparable case where a similar choice was made and the outcome is known",
    ],
    "simulate_hypothesis": [
        "a written version of the hypothesis with at least one falsifiable claim",
        "the data or analysis the hypothesis rests on",
        "a comparable case that succeeded or failed under the same conditions",
    ],
    "get_perspective": [
        "the framing or memo you want perspectives on",
        "a list of stakeholders whose views are needed",
        "any prior boardroom or executive correspondence on the topic",
    ],
}


def render_refusal(
    *,
    sub_module: str,
    reason: RefusalReason,
    candidates_to_surface: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Compose the refusal coach-voice paragraph. Editorial; calm,
    confident, not apologetic per brief §5.5."""
    candidates = candidates_to_surface or []
    cand_count = len(candidates)

    lines: List[str] = []
    if reason == RefusalReason.INSUFFICIENT_EVIDENCE:
        count_text = str(cand_count) if cand_count else "a few"
        lines.append(
            f"I don't have enough to weight scenarios honestly here. "
            f"The framings worth examining are clear — there are {count_text} of them — "
            f"but without evidence on the pieces that distinguish them, I'd be guessing at probabilities."
        )
    elif reason == RefusalReason.CONTRADICTORY_EVIDENCE_AT_SCALE:
        lines.append(
            "Across the candidates I'd want to weigh, the evidence pulls hard in different "
            "directions — enough that any single synthesis would have to override what the material "
            "is telling us. I won't do that on your behalf."
        )
    elif reason == RefusalReason.FAR_INSUFFICIENT_UNRESOLVED:
        lines.append(
            "The framing didn't sharpen enough as we went — the missing pieces stayed missing. "
            "A probability-weighted read at this point would be more performance than diagnosis."
        )
    elif reason == RefusalReason.OUT_OF_SCOPE:
        lines.append(
            "What you've brought sits outside the situation classes I'm calibrated for. "
            "I'd rather say so than synthesise something that sounds right but isn't anchored."
        )
    elif reason == RefusalReason.LOW_TRIANGULATION_CONSISTENCY:
        lines.append(
            "The narrative and the evidence are pulling in directions weak enough that I can't "
            "stand a probability-weighted reading on them. I'd rather hold than overclaim."
        )
    else:
        lines.append(
            "I'm holding back on a probability-weighted synthesis. The footing isn't there."
        )

    # What I CAN give you — sanitised candidate descriptions.
    if candidates:
        lines.append("")
        lines.append("Here's what I can put on the table.")
        names: List[str] = []
        for c in candidates[:4]:
            raw = str(c.get("description") or "").strip()
            if not raw:
                continue
            cleaned = _sanitize_internal_string(raw)
            cleaned, _ = _strip_entity_placeholders(cleaned)
            cleaned = cleaned.strip(" .-*·:;")
            if cleaned:
                # Cap length so the refusal stays scannable.
                names.append(cleaned[:140])
        if names:
            lines.append(" · ".join(names))

    # What would change the picture.
    lines.append("")
    helps = _WHAT_WOULD_HELP.get(sub_module, _WHAT_WOULD_HELP["seek_clarity"])
    lines.append("What would change the picture:")
    for h in helps:
        lines.append(f"  · {h}")

    body = "\n".join(lines).strip()
    body, _ = _strip_entity_placeholders(body)
    body = _strip_macro_names(body)
    return body
