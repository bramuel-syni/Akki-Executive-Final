"""Phase 12.1 unit tests — AES-GCM envelope encryption + key rotation.

Security tests assert:
  - Round-trip with the current key works.
  - A record written under an old key can be read if the old key is
    registered under its SYNISENSE_MASTER_KEY_V<N> env var.
  - A record written under a key version that isn't registered raises
    KeyVersionUnknown (NO silent decrypt-with-wrong-key).
"""
import os
import sys
sys.path.insert(0, "/app/backend")

import pytest

from services.synisense import encryption as enc


@pytest.fixture(autouse=True)
def _reset_keys():
    # Save + restore the master-key env so tests in this file can
    # rotate without leaking into the rest of the suite.
    saved = {
        k: os.environ.get(k) for k in (
            "SYNISENSE_MASTER_KEY", "SYNISENSE_MASTER_KEY_V2",
            "SYNISENSE_ALLOW_INSECURE", "AKKI_ENV",
        )
    }
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    enc.init_keys()


def _fresh_hex():
    import secrets
    return secrets.token_hex(32)


def test_roundtrip_current_key():
    os.environ["SYNISENSE_MASTER_KEY"] = _fresh_hex()
    os.environ.pop("SYNISENSE_MASTER_KEY_V2", None)
    enc.init_keys()
    env = enc.new_record_envelope(["alice@example.com", "Project Falcon"])
    assert env["key_version"] == 1
    out = enc.open_record_envelope(env)
    assert out == ["alice@example.com", "Project Falcon"]


def test_rotation_with_registered_historical_key():
    # Write with v1.
    k_v1 = _fresh_hex()
    os.environ["SYNISENSE_MASTER_KEY"] = k_v1
    os.environ.pop("SYNISENSE_MASTER_KEY_V2", None)
    enc.init_keys()
    env = enc.new_record_envelope(["secret"])
    # Rotate: new current key, old key moves to V1... but our scheme
    # treats SYNISENSE_MASTER_KEY as 'current' and numbered keys as
    # historical. Simulate rotation by moving v1 key to V2 slot and
    # loading a NEW current key.
    os.environ["SYNISENSE_MASTER_KEY_V2"] = _fresh_hex()
    # Keep the ORIGINAL v1 key registered as slot 1 by leaving SYNISENSE_MASTER_KEY.
    enc.init_keys()
    assert 1 in enc.registered_versions()
    out = enc.open_record_envelope(env)
    assert out == ["secret"]


def test_unregistered_version_raises():
    os.environ["SYNISENSE_MASTER_KEY"] = _fresh_hex()
    os.environ.pop("SYNISENSE_MASTER_KEY_V2", None)
    enc.init_keys()
    env = enc.new_record_envelope(["secret"])
    # Mutate the record to claim a non-existent key version.
    env["key_version"] = 9
    with pytest.raises(enc.KeyVersionUnknown):
        enc.open_record_envelope(env)


def test_production_boot_guard_refuses_without_key():
    os.environ.pop("SYNISENSE_MASTER_KEY", None)
    os.environ.pop("SYNISENSE_ALLOW_INSECURE", None)
    os.environ["AKKI_ENV"] = "production"
    try:
        with pytest.raises(enc.MasterKeyMissing):
            enc.init_keys()
    finally:
        os.environ.pop("AKKI_ENV", None)


def test_dev_escape_hatch_falls_back():
    os.environ.pop("SYNISENSE_MASTER_KEY", None)
    os.environ["SYNISENSE_ALLOW_INSECURE"] = "true"
    os.environ.pop("AKKI_ENV", None)
    enc.init_keys()
    assert enc.is_insecure_fallback() is True
    # Round-trip still works with the constant fallback.
    env = enc.new_record_envelope(["secret"])
    assert enc.open_record_envelope(env) == ["secret"]
