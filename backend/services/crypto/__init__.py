"""Phase I.4.c (2026-05-27) — services/crypto namespace.

Lightweight crypto helpers separate from `services/synisense/encryption.py`
(which is tuned for the Synisense shield-map's envelope-encryption with
per-record DEKs and master-key rotation — overkill for OAuth tokens).

Current module:
  • `token_vault` — Fernet symmetric encryption for OAuth refresh/access
    tokens. Single stable key from `OAUTH_TOKEN_VAULT_KEY` env var.
"""
