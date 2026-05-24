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



# ─────────────────────────────────────────────────────────────────────
# Streaming reidentifier (H2.5 — 2026-05-24).
# ─────────────────────────────────────────────────────────────────────
# The legacy `reidentify()` above takes a whole-text payload. The
# streaming chat path needs a stateful variant: tokens of the form
# `[[ENT_<TYPE>_<NNN>]]` may be split across two or more LLM-emitted
# deltas (e.g. one delta ends with `[[ENT_CREDIT_CA` and the next
# starts with `RD_001]]_at_KPMG`). A whole-text substitution can't
# safely operate on a single delta — it would emit a fragment of the
# token to the user and leak partial label text. Worse, if the
# partial fragment happens to LOOK like the start of a number, the
# user's screen could briefly flash digits before the closing `]]`
# arrives.
#
# `StreamingReidentifier.feed(delta)` returns only the prefix of the
# accumulated buffer that is GUARANTEED not to be the start of a
# pending token. `flush()` returns whatever's left at stream end.
# A hard cap (`_MAX_PENDING_TOKEN_LEN`) ensures that if an opening
# `[[ENT_` never closes (malformed LLM output, runaway token), we
# eventually release the buffer with a log warning — but EVERY
# rendered character is either non-`[` or a verified safe character,
# so no raw PII can leak via overflow.

# Maximum length of an `[[ENT_<TYPE>_<NNN>]]` token. The longest known
# type label today is `UK_NI_NUMBER` (12 chars). 64 chars covers any
# realistic future type label plus the 7-char wrap and 6-digit counter.
_MAX_PENDING_TOKEN_LEN = 64


class StreamingReidentifier:
    """Stateful per-stream rehydrator. NOT thread-safe — one instance
    per LLM stream.

    Usage:
        sr = StreamingReidentifier(token_map)
        async for chunk in stream:
            yield sr.feed(chunk.text)
        yield sr.flush()   # release tail at stream end

    Both `feed()` and `flush()` return a (possibly empty) string of
    user-safe characters. They NEVER emit a partial `[[ENT_...]]`
    fragment — if a token is mid-arrival, the matching characters
    stay buffered until the closing `]]` (or until the buffer
    overflows, see below).

    Args:
        token_map: same shape `reidentify()` accepts; token →
            original value.
        on_overflow: optional callback invoked with the released
            buffer when `_MAX_PENDING_TOKEN_LEN` is exceeded
            without seeing a closing `]]`. Default is a stderr
            warning. Useful for tests + audit-write hooks.
    """

    def __init__(
        self,
        token_map: Dict[str, str],
        *,
        on_overflow=None,  # type: ignore[no-untyped-def]
    ) -> None:
        self._token_map = token_map or {}
        self._buffer = ""
        self._overflow_count = 0
        self._on_overflow = on_overflow

    # ─────────────────────────────────────────────────────────────────
    # Core operations
    # ─────────────────────────────────────────────────────────────────
    def feed(self, delta: str) -> str:
        """Push `delta` into the buffer; return the prefix that's
        guaranteed safe to render to the user."""
        if not delta:
            return ""
        if not self._token_map:
            # Nothing to substitute — pass-through. Cheap, common in
            # `auto` mode for messages without identifiers.
            return delta
        self._buffer += delta
        return self._drain(final=False)

    def flush(self) -> str:
        """Release whatever's still in the buffer at stream end."""
        return self._drain(final=True)

    # ─────────────────────────────────────────────────────────────────
    # Internals
    # ─────────────────────────────────────────────────────────────────
    def _drain(self, *, final: bool) -> str:
        out_parts = []
        buf = self._buffer
        i = 0
        while i < len(buf):
            # Find the next `[` (potential token start).
            lb = buf.find("[", i)
            if lb < 0:
                # No more `[` — rest of buffer is safe.
                out_parts.append(buf[i:])
                i = len(buf)
                break

            # Safe text before the `[`.
            if lb > i:
                out_parts.append(buf[i:lb])
                i = lb

            # Now `buf[i]` == `[`. Determine if this is a real token
            # start `[[ENT_`. We need at least 6 more chars to check.
            tail = buf[i:]
            if len(tail) < 6:
                # Not enough chars to decide — defer unless final.
                if final:
                    out_parts.append(tail)
                    i = len(buf)
                break

            if not tail.startswith("[[ENT_"):
                # Single `[` or `[[` followed by other content; not a
                # token. Emit just the `[` and advance.
                out_parts.append("[")
                i += 1
                continue

            # tail starts with `[[ENT_` — look for closing `]]`.
            close_rel = tail.find("]]")
            if close_rel < 0:
                # Token not yet closed. Hold the rest of the buffer
                # UNLESS we've overflowed.
                if len(tail) >= _MAX_PENDING_TOKEN_LEN:
                    # Malformed / runaway — release safely. We emit
                    # the buffered chars character-by-character so
                    # there's no way a partial token could decode
                    # into raw PII (the original is in `_token_map`
                    # only, not in the buffer itself).
                    self._overflow_count += 1
                    if self._on_overflow is not None:
                        try:
                            self._on_overflow(tail)
                        except Exception:  # noqa: BLE001
                            pass
                    out_parts.append(tail)
                    i = len(buf)
                    break
                if final:
                    out_parts.append(tail)
                    i = len(buf)
                    break
                # Otherwise hold and wait for more data.
                break

            # Token closed at position `i + close_rel + 2` (after `]]`).
            full_tok = tail[: close_rel + 2]
            # Validate shape with the strict regex used by `reidentify`.
            m = _TOKEN_RE.match(full_tok)
            if m is None:
                # Looked like a token but failed validation — emit
                # raw and continue.
                out_parts.append(full_tok)
                i += len(full_tok)
                continue

            # Resolve via token_map / skip list.
            entity_type = m.group(1)
            original = self._token_map.get(full_tok)
            if original is None:
                out_parts.append(full_tok)
            else:
                visible = _visible_placeholder(entity_type, original)
                out_parts.append(visible if visible is not None else original)
            i += len(full_tok)

        # Preserve any unconsumed tail for the next feed().
        self._buffer = buf[i:]
        return "".join(out_parts)

    # ─────────────────────────────────────────────────────────────────
    # Telemetry surface (callers can log this at stream end).
    # ─────────────────────────────────────────────────────────────────
    @property
    def overflow_count(self) -> int:
        return self._overflow_count

    @property
    def buffered_chars(self) -> int:
        return len(self._buffer)
