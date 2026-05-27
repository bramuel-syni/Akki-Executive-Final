"""Phase R.1 (2026-05-27) — Cohort magic-link token shape.

Opaque random token, 32-byte url-safe (~256 bits of entropy). Single-use
is enforced atomically by `find_one_and_update` on the `cohort_invites`
row at consume time (see `routers/auth_magic.py`). No HMAC layer — the
DB lookup IS the validity check, and 256 bits is unguessable.

Mirrors the existing contributor-invitation pattern at
`services/tasks/contributor_invitation_service.py::_gen_token()`.
"""
from __future__ import annotations

import secrets


COHORT_INVITE_TTL_DAYS = 14
COHORT_TRIAL_DEFAULT_DAYS = 21


def gen_magic_token() -> str:
    """256 bits of urandom entropy, base64-url encoded (43 chars)."""
    return secrets.token_urlsafe(32)
