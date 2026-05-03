"""AES-GCM envelope encryption for the Synisense shield map.

Design:
    - Master key (`SYNISENSE_MASTER_KEY`) is hex-encoded 32 bytes, loaded
      at boot. It encrypts per-record DEKs (data encryption keys), never
      original content directly.
    - Each shield-map record has its own 32-byte DEK. The DEK is
      AES-GCM-encrypted under the master key and persisted as `dek_wrapped`.
      Original tokens are AES-GCM-encrypted under the per-record DEK.
    - `key_version` travels alongside every record so we can rotate the
      master key by registering a new version while keeping old versions
      decryptable. Operators set `SYNISENSE_MASTER_KEY_v<N>` env vars for
      historical keys; this module loads all of them at boot.

Public API:
    init_keys()             — call once at boot.
    current_key_version()   — int.
    seal(plaintext: str)    — returns (cipher_b64, nonce_b64).
    unseal(cipher, nonce, key_version, dek_wrapped, dek_nonce) — str | raises.
    new_record_envelope(plaintexts: list[str]) — full envelope with
        versioned wrapped DEK and per-token ciphers.
    unshield(shield_map_id, *, surface, account_id) — server-internal.

Failure modes:
    MasterKeyMissing — raised at boot if the production guard trips.
    KeyVersionUnknown — raised on unseal if `key_version` not registered.
"""
from __future__ import annotations

import base64
import logging
import os
import secrets as _secrets
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger("akki.synisense.encryption")


class MasterKeyMissing(RuntimeError):
    """Raised at boot when no master key is available and the dev escape
    hatch is not enabled. The boot guard converts this into a clear
    refusal-to-start."""


class KeyVersionUnknown(RuntimeError):
    """Raised on unseal when the record's key_version is not registered.
    Operators have purged the historical key without rotating records,
    or the record was written with a future key version."""


@dataclass(frozen=True)
class _KeySlot:
    version: int
    aesgcm: AESGCM


_REGISTRY: Dict[int, _KeySlot] = {}
_CURRENT_VERSION: int = 0
_INSECURE_FALLBACK: bool = False
_INSECURE_NEXT_WARN: float = 0.0

# Stable, fixed key for the dev escape hatch. NEVER use in production.
# 32 hex zeros + a marker so it's obvious in logs. Operators who set
# SYNISENSE_ALLOW_INSECURE=true accept this trade-off.
_DEV_INSECURE_KEY_HEX = (
    "deaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddead"
)


def _is_production() -> bool:
    if os.environ.get("AKKI_ENV", "").lower() == "production":
        return True
    if os.environ.get("BILLING_ENABLED", "").lower() in {"1", "true", "yes"}:
        return True
    return False


def init_keys() -> None:
    """Load `SYNISENSE_MASTER_KEY` (current) and any
    `SYNISENSE_MASTER_KEY_V<N>` historical entries. Refuses boot in
    production when nothing is configured. In dev with the escape
    hatch, falls back to a constant key with a 60-second warning loop.
    Idempotent — safe to call multiple times."""
    global _CURRENT_VERSION, _INSECURE_FALLBACK
    _REGISTRY.clear()

    current_hex = os.environ.get("SYNISENSE_MASTER_KEY", "").strip()
    insecure_ok = os.environ.get("SYNISENSE_ALLOW_INSECURE", "").lower() in {"1", "true", "yes"}

    if not current_hex:
        if _is_production() and not insecure_ok:
            raise MasterKeyMissing(
                "SYNISENSE_MASTER_KEY is required in production. Set the env "
                "var (Azure Key Vault → Container App secret) or, for dev "
                "only, set SYNISENSE_ALLOW_INSECURE=true."
            )
        # Dev escape hatch.
        current_hex = _DEV_INSECURE_KEY_HEX
        _INSECURE_FALLBACK = True
        logger.warning(
            "SYNISENSE: master key missing; using INSECURE dev fallback. "
            "This is only acceptable when SYNISENSE_ALLOW_INSECURE=true."
        )
    else:
        _INSECURE_FALLBACK = False

    _REGISTRY[1] = _KeySlot(version=1, aesgcm=AESGCM(bytes.fromhex(current_hex)))
    _CURRENT_VERSION = 1

    # Historical versions: SYNISENSE_MASTER_KEY_V2 ... V99
    for n in range(2, 100):
        h = os.environ.get(f"SYNISENSE_MASTER_KEY_V{n}", "").strip()
        if not h:
            continue
        try:
            _REGISTRY[n] = _KeySlot(version=n, aesgcm=AESGCM(bytes.fromhex(h)))
            _CURRENT_VERSION = max(_CURRENT_VERSION, n)
        except (ValueError, Exception) as e:  # noqa: BLE001
            logger.error("SYNISENSE_MASTER_KEY_V%d unloadable: %s", n, e)

    logger.info(
        "SYNISENSE keys initialised: current_version=%d registered=%s insecure_fallback=%s",
        _CURRENT_VERSION, sorted(_REGISTRY.keys()), _INSECURE_FALLBACK,
    )


def current_key_version() -> int:
    if _CURRENT_VERSION == 0:
        init_keys()
    return _CURRENT_VERSION


def is_insecure_fallback() -> bool:
    return _INSECURE_FALLBACK


def registered_versions() -> List[int]:
    return sorted(_REGISTRY.keys())


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def new_record_envelope(plaintexts: List[str]) -> Dict[str, object]:
    """Build a fresh envelope for a shield-map record. Returns:
        {
          'key_version': int,
          'dek_wrapped': str (base64),
          'dek_nonce':   str (base64),
          'entries': [
             {'cipher': b64, 'nonce': b64}
          ],
        }
    `entries[i]` corresponds to `plaintexts[i]`. Replacements are NOT
    persisted here — the caller knows them.
    """
    if _CURRENT_VERSION == 0:
        init_keys()
    dek = AESGCM.generate_key(bit_length=256)
    dek_nonce = _secrets.token_bytes(12)
    master = _REGISTRY[_CURRENT_VERSION].aesgcm
    dek_wrapped = master.encrypt(dek_nonce, dek, associated_data=None)
    aes = AESGCM(dek)
    entries: List[Dict[str, str]] = []
    for pt in plaintexts:
        nonce = _secrets.token_bytes(12)
        ct = aes.encrypt(nonce, pt.encode("utf-8"), associated_data=None)
        entries.append({"cipher": _b64(ct), "nonce": _b64(nonce)})
    return {
        "key_version": _CURRENT_VERSION,
        "dek_wrapped": _b64(dek_wrapped),
        "dek_nonce": _b64(dek_nonce),
        "entries": entries,
    }


def open_record_envelope(envelope: Dict[str, object]) -> List[str]:
    """Reverse of new_record_envelope. Returns the plaintext list.
    Raises KeyVersionUnknown if the envelope's key_version isn't
    registered."""
    kv = int(envelope.get("key_version") or 0)
    if kv not in _REGISTRY:
        raise KeyVersionUnknown(
            f"key_version={kv} not registered (have: {sorted(_REGISTRY.keys())})"
        )
    master = _REGISTRY[kv].aesgcm
    dek = master.decrypt(
        _unb64(str(envelope["dek_nonce"])),
        _unb64(str(envelope["dek_wrapped"])),
        associated_data=None,
    )
    aes = AESGCM(dek)
    out: List[str] = []
    for e in (envelope.get("entries") or []):
        out.append(
            aes.decrypt(
                _unb64(str(e["nonce"])),
                _unb64(str(e["cipher"])),
                associated_data=None,
            ).decode("utf-8")
        )
    return out


async def unshield(
    shield_map_id: str, *, surface: str, account_id: Optional[str] = None,
) -> Dict[str, str]:
    """Server-internal reversal. Returns {replacement: original}.
    Writes a `synisense.unshield` audit row. NEVER expose this through
    a public-facing API — the only caller is the Reading Viewer's
    rehydration path inside the same process.
    """
    from core import db, write_audit
    rec = await db.synisense_shield_maps.find_one({"id": shield_map_id})
    if not rec:
        return {}
    plaintexts = open_record_envelope(rec.get("envelope") or {})
    replacements: List[str] = list(rec.get("replacements") or [])
    if len(plaintexts) != len(replacements):
        logger.error("shield map %s shape mismatch %d/%d",
                     shield_map_id, len(plaintexts), len(replacements))
        return {}
    mapping = dict(zip(replacements, plaintexts))
    try:
        await write_audit(
            context_id=rec.get("context_id"),
            account_id=account_id,
            action="synisense.unshield",
            resource_type="synisense_shield_map",
            resource_id=shield_map_id,
            metadata={"surface": surface, "span_count": len(replacements)},
        )
    except Exception:  # noqa: BLE001
        pass
    return mapping
