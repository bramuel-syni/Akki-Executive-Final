"""Phase I.4.c (2026-05-27) — Token vault.

Symmetric Fernet encryption for OAuth refresh + access tokens stored in
`db.user_calendar_credentials`. Single-purpose, single-key — no rotation
machinery (the Synisense shield-map's envelope approach is overkill for
external-provider tokens that we can re-acquire by re-running the OAuth
consent flow).

Key bootstrap:
  • `OAUTH_TOKEN_VAULT_KEY` env var — base64-encoded Fernet key (44 chars).
  • If missing AND `AKKI_ENV != "production"`: auto-generate at boot, log
    loudly so operators see it in dev. Tokens encrypted under this auto-
    key will NOT survive a restart — fine for dev/test.
  • If missing AND `AKKI_ENV == "production"`: refuse to start. Caller
    must invoke `init_vault()` at boot.

Public API:
  init_vault()                  — call once at boot (idempotent).
  encrypt(plaintext: str) -> str  — returns Fernet-token string.
  decrypt(ciphertext: str) -> str — raises on invalid token.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


log = logging.getLogger("akki.crypto.token_vault")

_FERNET: Optional[Fernet] = None


class TokenVaultNotInitialised(RuntimeError):
    """Raised if encrypt/decrypt is called before `init_vault()`."""


class TokenDecryptError(RuntimeError):
    """Raised when a ciphertext cannot be decrypted (key mismatch or
    tampering)."""


def _is_production() -> bool:
    return os.environ.get("AKKI_ENV", "").lower() == "production"


def init_vault() -> None:
    """Idempotent. Loads or auto-generates the Fernet key.

    Production: requires `OAUTH_TOKEN_VAULT_KEY` env var.
    Non-production: auto-generates a per-process key with a loud warning.
    """
    global _FERNET
    if _FERNET is not None:
        return
    key_str = os.environ.get("OAUTH_TOKEN_VAULT_KEY", "").strip()
    if key_str:
        try:
            _FERNET = Fernet(key_str.encode("utf-8"))
            log.info("[token_vault] loaded key from OAUTH_TOKEN_VAULT_KEY env var")
            return
        except (ValueError, TypeError) as e:
            log.error("[token_vault] OAUTH_TOKEN_VAULT_KEY invalid: %s", e)
            if _is_production():
                raise RuntimeError(
                    "OAUTH_TOKEN_VAULT_KEY is set but invalid. Must be a "
                    "base64-encoded Fernet key (44 chars). Generate via "
                    "Fernet.generate_key()."
                ) from e
            # In non-prod, fall through to auto-generate.
    if _is_production():
        raise RuntimeError(
            "OAUTH_TOKEN_VAULT_KEY is required in production. Generate via "
            "`python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'` and set it as an env var."
        )
    # Non-prod auto-generate.
    auto_key = Fernet.generate_key()
    _FERNET = Fernet(auto_key)
    log.warning(
        "[token_vault] OAUTH_TOKEN_VAULT_KEY not set — generated a per-process "
        "key. Tokens encrypted under this key will NOT survive a restart. "
        "Set OAUTH_TOKEN_VAULT_KEY in .env for persistent storage."
    )


def encrypt(plaintext: str) -> str:
    """Encrypt plaintext token. Returns Fernet ciphertext as ASCII string."""
    if _FERNET is None:
        init_vault()
    assert _FERNET is not None
    if not isinstance(plaintext, str):
        raise TypeError("plaintext must be str")
    return _FERNET.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(ciphertext: str) -> str:
    """Decrypt Fernet ciphertext back to plaintext. Raises TokenDecryptError
    on key mismatch / tampering / invalid format."""
    if _FERNET is None:
        init_vault()
    assert _FERNET is not None
    if not isinstance(ciphertext, str):
        raise TypeError("ciphertext must be str")
    try:
        return _FERNET.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        raise TokenDecryptError(
            "Token decryption failed — likely key mismatch or tampering"
        ) from e
