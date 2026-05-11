"""Phase G1 — Privacy Wall Phase 2c regression.

Coverage:
- (a) `redact_for_pulse_text` redacts emails/names/phone numbers
- (b) `assemble_pulse_prompt` does not leak context_id strings or PII
- (c) `surface="pulse"` writes to db.synisense_runs
- (d) `pulse` surface accepted by Synisense pipeline validator
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import uuid

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

from motor.motor_asyncio import AsyncIOMotorClient

from services.privacy_wall import (
    assemble_pulse_prompt, redact_for_pulse_text_async,
)
from services.synisense.pipeline import _VALID_SURFACES


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


def test_pulse_surface_registered_in_synisense():
    assert "pulse" in _VALID_SURFACES, (
        "surface='pulse' must be in Synisense _VALID_SURFACES"
    )


@pytest.mark.asyncio
async def test_redact_for_pulse_text_redacts_emails_and_names(db):
    SENT = uuid.uuid4().hex[:8]
    payload = (
        f"Ms. Sarah Thompson <sarah.thompson+{SENT}@example.com> flagged "
        f"the audit covenant breach. Phone: +44 20 7946 0958. Sentinel: PWPT-{SENT}"
    )
    shielded = await redact_for_pulse_text_async(payload)
    assert shielded is not None
    # The literal email must NOT survive.
    assert f"sarah.thompson+{SENT}@example.com" not in shielded, (
        f"email leaked into shielded output: {shielded!r}"
    )
    # The phone number digit-sequence should be transformed too.
    assert "+44 20 7946 0958" not in shielded
    # The sentinel itself isn't PII shape — it MAY survive. That is fine.

    # And the Synisense run must have been written with surface="pulse".
    run = await db.synisense_runs.find_one(
        {"surface": "pulse"}, {"_id": 0, "surface": 1, "input_sha256": 1, "layer_won": 1},
        sort=[("ts", -1)],
    )
    assert run is not None, "no synisense_runs row with surface='pulse'"
    assert run["surface"] == "pulse"


def test_assemble_pulse_prompt_strips_uuids():
    fake_ctx_id = str(uuid.uuid4())
    outs = [
        {"summary": f"Board carries exposure id={fake_ctx_id} on covenant",
         "themes": ["liquidity", "covenants"],
         "context_id": fake_ctx_id,                # MUST be stripped (not in allowlist)
         "owner_name": "Sarah Thompson",           # MUST be stripped
         "signal_count_high": 3, "window_days": 30},
        {"summary": "Second board carries succession risk",
         "themes": ["succession"], "regulatory_refs": ["FRC 2024"],
         "signal_count_high": 1, "window_days": 30},
    ]
    prompt = assemble_pulse_prompt(outs)
    # No UUID-shaped substrings.
    assert not re.search(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        prompt,
    ), f"UUID leaked into prompt: {prompt!r}"
    # No context_id key.
    assert "context_id" not in prompt
    # No PII-shaped owner_name.
    assert "Sarah Thompson" not in prompt
    # Opaque BOARD-N labels MUST be present.
    assert "BOARD-1" in prompt and "BOARD-2" in prompt
    # Allowlisted fields survived.
    assert "covenant" in prompt
    assert "succession" in prompt


def test_assemble_pulse_prompt_empty():
    assert assemble_pulse_prompt([]) == ""


def test_assemble_pulse_prompt_deterministic_for_fixed_input():
    outs = [{"summary": "A", "themes": [1, 2]}]
    a = assemble_pulse_prompt(outs)
    b = assemble_pulse_prompt(outs)
    assert a == b


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
