"""Phase P5.15 — Personalization prompt envelope.

User-authored `custom_instructions` are injected into the
synthesis prompt as a clearly-labelled segment. The wrapper
explicitly tells the model:

  1. Use the instructions to weight relevance + focus.
  2. DO NOT abandon any of the 4 enabled lenses.
  3. DO NOT invent claims to fit the user's preference.
  4. Refuse-to-decide remains in force — user instructions
     CANNOT induce imperative-to-user phrasing in the output.

The wrapper itself is voice-lint clean. The user's instructions
are NOT voice-lint-validated (they're authored by the user, not
Akki) — but they ARE PII-scrubbed by Synisense when the prompt
crosses the LLM boundary.
"""
from __future__ import annotations

from typing import List

from .schema import IDEA_LENSES, IdeaLens


_GUARDRAIL = (
    "GUARDRAILS:\n"
    "1. The 4 enabled lenses below MUST each produce one card. Do not skip a lens "
    "to over-index on the user's preference.\n"
    "2. Every claim MUST cite a real chunk from the corpus excerpts you receive. "
    "Inventing a citation will fail downstream verification and the card will be "
    "regenerated or dropped.\n"
    "3. Observational tone only. Reviewers may want to consider X — never \"you "
    "should X\". Imperative-to-user phrasing is rejected by an automated validator.\n"
    "4. Use the user's focus instructions ONLY to weight relevance among the corpus; "
    "do not invent new facts to please the preference.\n"
)


def build_personalization_block(
    *,
    custom_instructions: str,
    lenses_enabled: List[IdeaLens],
) -> str:
    """Compose the personalization segment that prefixes the
    synthesis prompt. Returns a multi-line plain-text block.

    Sanitisation:
      * Strips control characters (NUL through 0x1F except newline/tab).
      * Truncates to 2000 chars (matches the Pydantic field bound).
      * Empty / whitespace-only input → only the guardrail block.
    """
    enabled = [lens for lens in IDEA_LENSES if lens in lenses_enabled] or list(IDEA_LENSES)
    cleaned = _sanitise(custom_instructions)
    if cleaned:
        return (
            f"USER FOCUS INSTRUCTIONS (use to weight relevance; do not invent claims):\n"
            f"---\n{cleaned}\n---\n\n"
            f"ENABLED LENSES: {', '.join(enabled)}\n\n"
            f"{_GUARDRAIL}"
        )
    return (
        f"ENABLED LENSES: {', '.join(enabled)}\n\n{_GUARDRAIL}"
    )


def _sanitise(text: str) -> str:
    if not text:
        return ""
    out = []
    for ch in text:
        if ch in ("\n", "\t") or ord(ch) >= 0x20:
            out.append(ch)
    cleaned = "".join(out).strip()
    return cleaned[:2000]


__all__ = ["build_personalization_block"]
