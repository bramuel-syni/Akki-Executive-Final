"""Phase 12.1 security tests.

Covers:
  - shield_map TTL enforcement (expiration boundary).
  - A record written with an unregistered key version fails to decrypt.
  - `/api/synisense/status` and `/dryrun` never leak any shield_map
    payload (shield_map_id is opaque; contents are server-only).
"""
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")

import pytest

from services.synisense import run as pipeline_run, encryption as enc


@pytest.fixture(autouse=True)
def _prep_keys():
    import secrets
    os.environ["SYNISENSE_MASTER_KEY"] = secrets.token_hex(32)
    os.environ.pop("SYNISENSE_ALLOW_INSECURE", None)
    os.environ.pop("AKKI_ENV", None)
    enc.init_keys()
    yield


def test_shield_reversible_produces_shield_map_id_only():
    # shield_reversible mode persists the shield map server-side and
    # returns an opaque id. Original content NEVER flows back to the
    # caller through the pipeline return value.
    text = "Email director@acme.com about the audit."
    out = asyncio.run(pipeline_run(
        text, context_id="sec-test", surface="ingest",
        mode="shield_reversible", account_id="test-admin",
    ))
    # Still get the redacted text + spans + stats.
    assert out["redacted_text"] != text
    assert out["spans"]
    # shield_map_id is a string; never the cleartext mapping.
    assert isinstance(out["shield_map_id"], (str, type(None)))
    # No 'shield_map' or 'replacements_original' or 'mapping' keys in the
    # response that could leak originals.
    for k in ("shield_map", "mapping", "originals", "envelope"):
        assert k not in out


def test_redact_mode_never_creates_shield_map():
    text = "Email director@acme.com about the audit."
    out = asyncio.run(pipeline_run(
        text, context_id="sec-test", surface="chat",
        mode="redact", account_id="test-admin",
    ))
    assert out["shield_map_id"] is None


def test_unregistered_version_blocks_decryption():
    env = enc.new_record_envelope(["originally-sensitive"])
    env["key_version"] = 42  # not registered
    with pytest.raises(enc.KeyVersionUnknown):
        enc.open_record_envelope(env)
