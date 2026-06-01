"""Phase P5.14 — refuse-to-decide validator for workbook narrations.

A narration is ANY LLM-or-template-generated string that lands in
the analysis surface (signal detail, Monte Carlo narration,
forecast narration, anomaly rationale, report speaker notes).
The validator rejects strings containing imperative-to-user
phrasing — the workbook analyzer follows the same Akki promise
as Solva v2 ("Decisions stay yours").

We DO NOT import Solva v2's validator to keep this package
sibling-clean (so a future Solva v2 refactor cannot regress
workbook narrations). The phrase list is a small subset of
imperatives that frequently slip past LLM constraints in
analytical contexts. Add to the list as recurring failure modes
surface — recurring not "one-off".
"""
from __future__ import annotations

import re
from typing import List, Sequence


class RefuseToDecideViolation(ValueError):
    """Raised when a narration string carries imperative-to-user
    phrasing. The error message names ALL offending phrases so
    upstream code can return a helpful diagnostic."""
    pass


# Patterns are matched case-insensitive, word-boundary aware.
# Each entry: (regex, why)
_IMPERATIVE_PATTERNS: List[tuple[re.Pattern, str]] = [
    (re.compile(r"\byou\s+should\b", re.IGNORECASE),                "imperative 'you should'"),
    (re.compile(r"\byou\s+must\b", re.IGNORECASE),                  "imperative 'you must'"),
    (re.compile(r"\byou\s+need\s+to\b", re.IGNORECASE),             "imperative 'you need to'"),
    (re.compile(r"\byou\s+have\s+to\b", re.IGNORECASE),             "imperative 'you have to'"),
    (re.compile(r"\byou\s+ought\s+to\b", re.IGNORECASE),            "imperative 'you ought to'"),
    (re.compile(r"\b(?:please|kindly)\s+(?:do|take|consider|pursue)\b", re.IGNORECASE), "directive verb"),
    (re.compile(r"^\s*(?:do|take|pursue|implement|execute)\s+(?:the|a|this|that)\b", re.IGNORECASE | re.MULTILINE), "bare-imperative opener"),
    (re.compile(r"\bthe\s+(?:correct|right|best)\s+(?:course|action|move|decision)\s+is\b", re.IGNORECASE), "prescriptive 'the right action is'"),
    (re.compile(r"\bdecide\s+(?:to|on|now)\b", re.IGNORECASE),       "directive 'decide to/on/now'"),
    (re.compile(r"\b(?:we|i)\s+recommend\s+that\s+you\b", re.IGNORECASE), "first-person prescription"),
]


def validate_no_imperatives(text: str, *, label: str = "narration") -> None:
    """Raises `RefuseToDecideViolation` if `text` contains any
    imperative-to-user pattern. Returns silently on clean input.

    The caller MUST run every LLM- or template-generated narration
    string through this before persisting to `workbook_analyses`.
    Persisting an unvalidated narration is a tier-1 promise gap
    (P5 — Decisions stay yours)."""
    if not isinstance(text, str) or not text.strip():
        return
    failures: List[str] = []
    for rx, why in _IMPERATIVE_PATTERNS:
        m = rx.search(text)
        if m:
            failures.append(f"{why} → matched {m.group(0)!r}")
    if failures:
        raise RefuseToDecideViolation(
            f"refuse_to_decide_violation in {label}: {'; '.join(failures)}"
        )


def safe_neutral_fallback(seed_text: str = "") -> str:
    """Stock observational fallback used when the LLM narration
    fails refuse-to-decide validation. Voice-lint clean by
    construction (no banned terms)."""
    return (
        "Here is what the numbers show on their own; reviewers should weigh "
        "the result against context this analysis does not have."
    )


__all__ = [
    "RefuseToDecideViolation",
    "validate_no_imperatives",
    "safe_neutral_fallback",
]
