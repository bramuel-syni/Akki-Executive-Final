"""P5.16 — Refuse-to-decide validator for inbox-routing rationales.

This file is a re-export of the workbook_analyzer sibling's
validator. The Ideas engine does the same. There is ONE source of
truth for the imperative-rejection regex set across the codebase:
`services.workbook_analyzer.refuse_to_decide`. Future additions to
the banned-vocabulary list land there and propagate to every
consumer via this re-export.

Why re-export instead of import directly at every call site?
Discoverability — when an inbox-routing reader is auditing the
package, they should see the validator in this folder, not have
to track down a workbook_analyzer reference. The single-source
guarantee is preserved by the absence of any local regex
definitions in this file.
"""
from __future__ import annotations

from services.workbook_analyzer.refuse_to_decide import (
    RefuseToDecideViolation,
    validate_no_imperatives,
    safe_neutral_fallback,
)

__all__ = [
    "RefuseToDecideViolation",
    "validate_no_imperatives",
    "safe_neutral_fallback",
]
