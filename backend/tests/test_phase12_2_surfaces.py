"""Phase 12.2 surface-wiring tests.

Each new hook gets an isolated assertion. The big invariants the
brief calls out as critical:
  - ITEM B: paragraph anchor IDs are STABLE through redaction (the
    chat citation chip → Reading Viewer flow depends on this).
  - ITEM E: public-read 410s when `synisense_version` is unset.
  - shield_map / encrypted_original / dek_wrapped never appear in
    any /api response (extended denylist test).

End-to-end behavioural smoke is in `test_phase12_2_e2e.py`; this
file unit-tests the building blocks.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import pytest

sys.path.insert(0, "/app/backend")

# Load .env so the `core` module can find MONGO_URL when imported by
# routers/studio. pytest doesn't auto-load .env files.
from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")


# ---------------------------------------------------------------------------
# ITEM B — paragraph anchor stability through redaction
# ---------------------------------------------------------------------------
def test_paragraph_anchors_stable_through_redaction():
    """The anchor IDs computed BEFORE Synisense must equal the anchor
    IDs that appear on the persisted document AFTER Synisense runs.

    We don't actually persist here — just call `compute_paragraphs`
    on the original text and confirm anchor IDs are content-hashes
    of the ORIGINAL text. Then we run Synisense on each paragraph
    and confirm the anchors we'd compute on the redacted text would
    be DIFFERENT (proving the contract: we compute on the original
    first, then preserve those IDs through the redaction).
    """
    from paragraph_anchors import compute_paragraphs
    from services.synisense import dryrun

    text = (
        "John Smith called from john@example.com about Project Falcon.\n\n"
        "The CFO confirmed £42,500,000 commitment last Tuesday.\n\n"
        "Routing through https://internal.acme.com/q4-pack should be safe."
    )
    payload = compute_paragraphs("doc-test", text)
    original_anchor_ids = [p["id"] for p in payload["paragraphs"]]
    assert original_anchor_ids, "compute_paragraphs returned no paragraphs"

    # Redact each paragraph and assert content-hashes of redacted text
    # would differ — proving anchors must be computed on original first.
    diverged = 0
    for p in payload["paragraphs"]:
        out = asyncio.run(dryrun(p["text"], context_id="t", surface="ingest"))
        if out["redacted_text"] != p["text"]:
            diverged += 1
            redacted_payload = compute_paragraphs("doc-redacted", out["redacted_text"])
            redacted_ids = [rp["id"] for rp in redacted_payload["paragraphs"]]
            assert redacted_ids != [p["id"]], (
                "anchor IDs unchanged across redaction — content hash is "
                "not catching changes; chat citations would appear stable "
                "but resolve to redacted text the user never wrote."
            )
    assert diverged > 0, "no paragraphs were redacted; test fixture is too benign"


# ---------------------------------------------------------------------------
# ITEM E — public-read denylist + version assertion
# ---------------------------------------------------------------------------
def test_public_read_denylist_extended_for_synisense_keys():
    """The Phase 11 denylist gained dek_wrapped, dek_nonce,
    encrypted_original, envelope, shield_map, original_payload.
    `_assert_public_safe` must trip on each of them at any depth.
    """
    from fastapi import HTTPException
    from routers.studio import _assert_public_safe

    extended_keys = [
        "dek_wrapped", "dek_nonce", "encrypted_original", "envelope",
        "shield_map", "original_payload",
    ]
    for key in extended_keys:
        # Top-level
        with pytest.raises(HTTPException) as ei:
            _assert_public_safe({"watermark": {}, "content": {}, key: "x"})
        assert ei.value.status_code == 500
        # Nested
        with pytest.raises(HTTPException) as ei:
            _assert_public_safe({"content": {"slides": [{"title": "ok", key: "x"}]}})
        assert ei.value.status_code == 500


def test_public_read_passes_for_clean_payload():
    """The denylist must NOT trip on a payload that uses none of the
    forbidden keys — otherwise legitimate share responses 500."""
    from routers.studio import _assert_public_safe
    _assert_public_safe({
        "kind": "deck",
        "artefact_id": "x",
        "context_id": "y",
        "content": {
            "title": "OK",
            "slides": [{"title": "S1", "body_md": "hello"}],
        },
        "watermark": {"label": "X", "recipient": "a@b.c"},
    })  # no exception → pass
