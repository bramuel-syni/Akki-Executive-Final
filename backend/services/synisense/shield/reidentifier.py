"""Synisense Shield — re-identification (token → original).

Walks the response text once with a single compiled regex matching every
known token in the per-request token map, substituting in O(n). The
token format `[[ENT_<TYPE>_<NNN>]]` is anchored so a hostile LLM
returning a similar-looking string but with the wrong shape (extra
characters, wrong digit count) does NOT trigger an accidental
substitution.

No persisted state — the token map is per-request, lives in memory only,
and is discarded after the route returns.
"""
from __future__ import annotations

import re
from typing import Dict

# Token shape lock — matches what `deidentifier._token_for()` emits.
# Type label allows letters, digits, and underscores (e.g. PHONE_E164).
_TOKEN_RE = re.compile(r"\[\[ENT_[A-Z0-9_]+_\d{3,}\]\]")


def reidentify(text: str, token_map: Dict[str, str]) -> str:
    """Substitute every token in `text` with its original value from
    `token_map`. Unknown tokens (shouldn't happen, but defence in
    depth) are left as-is — the smoke test asserts that NO tokens
    survive in the final response, which catches both leak and
    drift bugs."""
    if not text or not token_map:
        return text

    def _sub(m: re.Match) -> str:
        tok = m.group(0)
        return token_map.get(tok, tok)

    return _TOKEN_RE.sub(_sub, text)
