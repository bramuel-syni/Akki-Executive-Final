"""Synisense Shield — re-identification (token → original).

Walks the response text once with a single compiled regex matching every
known token in the per-request token map, substituting in O(n). The
token format `[[ENT_<TYPE>_<NNN>]]` is anchored so a hostile LLM
returning a similar-looking string but with the wrong shape (extra
characters, wrong digit count) does NOT trigger an accidental
substitution.

## 2026-05-24 patch — PII-class skip list (user trust)

The Shield's original design rehydrated EVERY token in the user-visible
LLM reply, so the user could keep working on their own data (PERSON
names, ORG references, etc. stayed continuous across the conversation).
But for "hard PII" classes — payment cards, SSNs, API keys, NI numbers
— that behavior made it LOOK like the LLM had received the raw PII,
even though the audit trail proves it never did.

This module now distinguishes:

* **Contextual classes** (PERSON, ORG, GPE, PRODUCT, NORP, FAC, EVENT,
  LAW, DATE_ISO, MONEY, URL) — rehydrate to the original value so the
  user reads their own names / organisations back. Continuity matters.

* **Hard-PII classes** (CREDIT_CARD, ACCOUNT_NUM, SSN, UK_NI_NUMBER,
  IBAN, API_KEY, EMAIL, PHONE_E164, IP) — **stay redacted in the
  user-visible reply**. The placeholder format is type-specific
  (e.g. `[PAYMENT_CARD_••••7689]` preserves the last 4 digits for
  recognisability without leaking the full PAN; `[API_KEY_REDACTED]`
  leaks no structure at all because partial tokens are still useful
  to an attacker).

The cryptographic audit trail is unchanged — `token_map` still holds
the originals so the Shield's `request_hash` / `response_hash` cover
what the LLM ACTUALLY saw (the placeholder). Only the user-rendering
layer changes.

No persisted state — the token map is per-request, lives in memory only,
and is discarded after the route returns.
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

# Token shape lock — matches what `deidentifier._token_for()` emits.
# Type label allows letters, digits, and underscores (e.g. PHONE_E164).
_TOKEN_RE = re.compile(r"\[\[ENT_([A-Z0-9_]+)_(\d{3,})\]\]")


# Per-class visible-placeholder strategy. Each entry decides what the
# user-visible reply shows for that class. Tuple shape:
#   (strategy, optional_arg)
#
# strategy ∈ {
#   "rehydrate"   — substitute the original value (default behavior;
#                   used implicitly for any class NOT in this map).
#   "last4"       — show f"[<LABEL>_••••<last4>]" using the last 4
#                   characters of the original value (numeric or
#                   alphanumeric — whichever the original had).
#   "redacted"    — show f"[<LABEL>_REDACTED]" with no portion of the
#                   original leaked.
# }
# `optional_arg` is the user-facing LABEL used inside the bracket.
#
# IMPORTANT: this list MUST be kept in lockstep with the entity-label
# map in `routers/chat_audit_panel.py:_ENTITY_LABEL` so the audit-panel
# prose and the inline placeholder agree on what each class is called.
_VISIBLE_STRATEGY: Dict[str, Tuple[str, str]] = {
    # ── Hard PII — keep redacted in user-visible reply ──
    "CREDIT_CARD":  ("last4",    "PAYMENT_CARD"),
    "ACCOUNT_NUM":  ("last4",    "ACCOUNT_NUM"),
    "SSN":          ("last4",    "SSN"),
    "IBAN":         ("last4",    "IBAN"),
    "PHONE_E164":   ("last4",    "PHONE"),
    "UK_NI_NUMBER": ("redacted", "UK_NI"),
    "API_KEY":      ("redacted", "API_KEY"),
    "EMAIL":        ("redacted", "EMAIL"),
    "IP":           ("redacted", "IP"),
    # ── Contextual classes ──
    # PERSON, ORG, GPE, PRODUCT, NORP, FAC, EVENT, LAW, DATE_ISO, MONEY,
    # URL → no entry here → default `rehydrate` strategy.
}


def _last_n_digits(s: str, n: int = 4) -> str:
    """Return the last `n` digit characters of `s`. Falls back to the
    last `n` alphanumeric characters if there aren't enough digits
    (e.g. an IBAN check-digit suffix). Returns the empty string when
    `s` has no usable characters."""
    digits = re.findall(r"\d", s or "")
    if len(digits) >= n:
        return "".join(digits[-n:])
    alnum = re.findall(r"[A-Za-z0-9]", s or "")
    if len(alnum) >= n:
        return "".join(alnum[-n:])
    return "".join(alnum)


def _visible_placeholder(entity_type: str, original: str) -> Optional[str]:
    """Return the user-visible placeholder for `entity_type` if the
    class is in the skip list, else `None` (which signals the caller
    to rehydrate to the original value)."""
    strat = _VISIBLE_STRATEGY.get(entity_type)
    if strat is None:
        return None
    mode, label = strat
    if mode == "last4":
        suffix = _last_n_digits(original, 4)
        if suffix:
            return f"[{label}_••••{suffix}]"
        return f"[{label}_REDACTED]"
    if mode == "redacted":
        return f"[{label}_REDACTED]"
    return None  # unknown strategy → default to rehydrate (safe fallback)


def reidentify(text: str, token_map: Dict[str, str]) -> str:
    """Substitute every token in `text` with the appropriate user-
    visible form.

    For contextual classes (PERSON, ORG, etc.) the original value is
    restored. For hard-PII classes (CREDIT_CARD, SSN, API_KEY, …) the
    user-visible placeholder from `_VISIBLE_STRATEGY` is rendered
    instead. Unknown tokens (shouldn't happen, defence-in-depth) are
    left as-is — the smoke tests assert that NO bare `[[ENT_…]]`
    survives in the final response, catching both leak and drift bugs.
    """
    if not text or not token_map:
        return text

    def _sub(m: re.Match) -> str:
        tok = m.group(0)
        entity_type = m.group(1)
        original = token_map.get(tok)
        if original is None:
            # Token not in map — unknown / drift. Keep as-is (callers
            # can assert against bare tokens in tests).
            return tok
        visible = _visible_placeholder(entity_type, original)
        if visible is not None:
            return visible
        return original

    return _TOKEN_RE.sub(_sub, text)
