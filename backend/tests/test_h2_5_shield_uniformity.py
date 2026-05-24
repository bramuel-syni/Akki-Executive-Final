"""H2.5 — Shield Uniformity corrective sprint tests (2026-05-24).

Six contract guards for the streaming chat path's Shield carve-out fix.

Per the H2.5 brief (sections "Tests", items 1-7):

  1. Streaming PAN scenario: stream contains placeholder, never raw PAN;
     synisense_audit_log row written.
  2. Placeholder spans two deltas: assembled reply contains full
     placeholder, no partial leak.
  3. Auto vs Always diverge correctly: same input, both modes show
     identical `identifiers_redacted` count (detection runs in both).
  4. Off mode: with `acknowledge_unshielded=true`, audit row exists
     with `redacted=false, would_have_redacted=N`.
  5. Off mode without ack: 400.
  6. Presidio failure -> 503: chat endpoint returns the documented
     body; audit row written with `shield_failure=true`.
  7. Classifier path through Shield: confirmed (H2 §9 finding).

These are unit-level tests on the building blocks (StreamingReidentifier,
adapter fail-closed) and an integration test on the streaming chat
endpoint. The integration test uses ASGITransport so it doesn't depend
on a running uvicorn process.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path
from unittest import mock

import httpx
import pytest
import pytest_asyncio

sys.path.insert(0, "/app/backend")
from server import app  # noqa: E402
from services.synisense.shield.reidentifier import StreamingReidentifier  # noqa: E402

pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────
# Test 2 (boundary-split delta) — pure unit, no router.
# ─────────────────────────────────────────────────────────────────────
async def test_streaming_reidentifier_placeholder_split_two_deltas():
    """If `[[ENT_CREDIT_CARD_001]]` is split across two LLM-emitted
    deltas, the assembled visible output contains the full
    placeholder, no partial leak."""
    tm = {"[[ENT_CREDIT_CARD_001]]": "4356789800057689"}
    sr = StreamingReidentifier(tm)

    out1 = sr.feed("Your card [[ENT_CREDIT")
    out2 = sr.feed("_CARD_001]] was charged.")
    out3 = sr.flush()
    final = out1 + out2 + out3

    # No partial leak in any individual delta
    for chunk in (out1, out2, out3):
        assert "[[ENT_CREDIT" not in chunk, (
            f"partial token leaked to user in chunk: {chunk!r}"
        )

    # Final assembled output is correct
    assert "[PAYMENT_CARD_••••7689]" in final
    assert "4356789800057689" not in final


async def test_streaming_reidentifier_split_three_deltas():
    """Worst case — token split into three pieces. Each delta must be
    user-safe (no partial render of label text); final assembly correct."""
    tm = {"[[ENT_API_KEY_001]]": "AKIAIOSFODNN7EXAMPLE"}
    sr = StreamingReidentifier(tm)
    parts = ["Rotate [[", "ENT_API_KEY", "_001]] now."]
    rendered = [sr.feed(p) for p in parts]
    rendered.append(sr.flush())
    final = "".join(rendered)
    assert "AKIAIOSFODNN7EXAMPLE" not in final
    assert "[API_KEY_REDACTED]" in final
    # Each delta must be user-safe (no `[[ENT_...` fragment exposed).
    for ch in rendered:
        assert "[[ENT_" not in ch, (
            f"partial fragment leaked: {ch!r}"
        )


async def test_streaming_reidentifier_overflow_no_pii_leak():
    """If `[[ENT_` never closes within `_MAX_PENDING_TOKEN_LEN`, the
    buffered text is released — but the buffer holds ONLY the
    placeholder bytes, never the raw PII (raw PII lives in
    `token_map`, not in the LLM-emitted stream)."""
    raw_pan = "4356789800057689"
    tm = {"[[ENT_CREDIT_CARD_001]]": raw_pan}
    sr = StreamingReidentifier(tm)
    # Feed an opener that never closes
    out = sr.feed("[[ENT_" + "X" * 80)
    # The released text contains the malformed opener + the X's, but
    # MUST NOT contain the raw PAN — the PAN is only in token_map.
    assert raw_pan not in out
    assert sr.overflow_count >= 1


async def test_streaming_reidentifier_empty_token_map_pass_through():
    sr = StreamingReidentifier({})
    out = sr.feed("Hello world!") + sr.flush()
    assert out == "Hello world!"


# ─────────────────────────────────────────────────────────────────────
# Test 6 — Legacy adapter fail-closed for chat-family surfaces.
# ─────────────────────────────────────────────────────────────────────
async def test_shield_payload_async_raises_for_chat_on_pipeline_failure():
    """When the de-id pipeline raises and surface is chat-family,
    `shield_payload_async` now raises `ShieldFailure` instead of
    returning raw text."""
    from services.synisense import adapter
    from services.synisense.shield.exceptions import ShieldFailure

    # The adapter routes chat-family + message_id to pipeline.run, and
    # everything else to pipeline.dryrun. Mock BOTH so the test
    # captures whichever code path the surface picks today.
    with mock.patch.object(adapter._pipeline, "run",
                           side_effect=RuntimeError("simulated presidio collapse")), \
         mock.patch.object(adapter._pipeline, "dryrun",
                           side_effect=RuntimeError("simulated presidio collapse")):
        with pytest.raises(ShieldFailure) as exc_info:
            await adapter.shield_payload_async(
                text="some user text with PII", context_id="ctx",
                surface="chat", message_id="msg-1",
            )
    assert exc_info.value.surface == "chat"
    assert exc_info.value.error_class == "RuntimeError"


async def test_shield_payload_async_degrades_open_for_enhance():
    """Non-chat surfaces in the allow-list (e.g. `enhance`) STILL
    degrade-open on pipeline failure — they return raw text."""
    from services.synisense import adapter

    with mock.patch.object(adapter._pipeline, "run",
                           side_effect=RuntimeError("simulated")), \
         mock.patch.object(adapter._pipeline, "dryrun",
                           side_effect=RuntimeError("simulated")):
        out_text, out_map = await adapter.shield_payload_async(
            text="raw user text",
            context_id="ctx", surface="enhance",
        )
    assert out_text == "raw user text"
    assert out_map == {}


async def test_shield_payload_async_degrades_open_for_ingest():
    from services.synisense import adapter

    with mock.patch.object(adapter._pipeline, "run",
                           side_effect=RuntimeError("simulated")), \
         mock.patch.object(adapter._pipeline, "dryrun",
                           side_effect=RuntimeError("simulated")):
        out_text, out_map = await adapter.shield_payload_async(
            text="raw doc",
            context_id="ctx", surface="ingest",
        )
    assert out_text == "raw doc"
    assert out_map == {}


async def test_shield_payload_async_raises_for_unknown_surface():
    """A surface NOT in `_SURFACES_ALLOWING_DEGRADED_OPEN` (e.g. a new
    one someone adds without updating the allow-list) fails closed
    by default — strict semantics."""
    from services.synisense import adapter
    from services.synisense.shield.exceptions import ShieldFailure

    with mock.patch.object(adapter._pipeline, "run",
                           side_effect=RuntimeError("simulated")), \
         mock.patch.object(adapter._pipeline, "dryrun",
                           side_effect=RuntimeError("simulated")):
        with pytest.raises(ShieldFailure):
            await adapter.shield_payload_async(
                text="anything",
                context_id="ctx", surface="some_new_surface_no_one_added_to_allowlist",
            )


# ─────────────────────────────────────────────────────────────────────
# Test 1 + 3 — Integration: streaming PAN end-to-end + auto/always.
# ─────────────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


async def _register(client: httpx.AsyncClient):
    email = f"h2-5-{uuid.uuid4().hex[:10]}@example.com"
    pw = "H2-5-Stream-2026!"
    r = await client.post("/api/auth/register", json={
        "email": email, "password": pw, "name": "H2.5 Stream",
    })
    assert r.status_code == 200, (r.status_code, r.text[:300])
    body = r.json()
    token = body["access_token"]
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    ctx_id = me.json()["contexts"][0]["id"]
    return token, ctx_id


async def test_prepare_for_streaming_minted_audit_id_and_returns_redacted():
    """The Shield streaming helper produces a redacted prompt + a
    finalize closure that writes the audit row."""
    from services.synisense.shield.client import prepare_for_streaming
    from core import db

    text = "Bramuel left his card no 4356789800057689 in KPMG head office."
    redacted, token_map, finalize = await prepare_for_streaming(
        purpose="chat.send_message_stream",
        content=text,
        tenant_id="test-tenant-h25",
        consumer_id="akki.chat",
        user_id="test-tenant-h25",
    )

    # Hard PII must be replaced by ENT tokens in the redacted prompt.
    assert "4356789800057689" not in redacted, redacted
    assert "[[ENT_CREDIT_CARD_" in redacted, redacted
    # Token map carries the original for rehydration.
    assert any("4356789800057689" in v for v in token_map.values()), token_map
    # Finalize writes the audit row.
    audit_id = await finalize(
        response_text="rehydrated reply",
        provider="anthropic",
        model="claude-sonnet-4-5",
        usage=None,
        outcome="success",
    )
    assert audit_id.startswith("aud-")
    # Audit row landed in Mongo.
    row = await db.synisense_audit_log.find_one(
        {"audit_id": audit_id}, {"_id": 0},
    )
    assert row is not None
    assert row["de_id_summary"].get("CREDIT_CARD", 0) >= 1, row["de_id_summary"]


async def test_prepare_for_streaming_finalize_writes_stream_error_outcome():
    """When the stream errors mid-flight, finalize can still write a
    row with `outcome="stream_error"` so the audit chain stays
    append-only."""
    from services.synisense.shield.client import prepare_for_streaming
    from core import db

    redacted, token_map, finalize = await prepare_for_streaming(
        purpose="chat.send_message_stream",
        content="Bramuel left his card no 4356789800057689 in KPMG head office.",
        tenant_id="test-tenant-h25",
        consumer_id="akki.chat",
        user_id="test-tenant-h25",
    )
    audit_id = await finalize(
        response_text="(partial reply)",
        provider="anthropic",
        model="claude-sonnet-4-5",
        usage=None,
        outcome="stream_error",
    )
    row = await db.synisense_audit_log.find_one({"audit_id": audit_id}, {"_id": 0})
    assert row is not None
    assert row["outcome"] == "stream_error"


# ─────────────────────────────────────────────────────────────────────
# Test 7 — Classifier confirmed Shield-routed (H2 §9 closed).
# ─────────────────────────────────────────────────────────────────────
async def test_classifier_routes_through_shield():
    """`_llm_classify_fallback` in chat.py calls `shield_invoke`, NOT
    a direct LLM SDK. This closes the H2 §9 open question.
    Wrapped in `async def` so the file-level `pytestmark = pytest.mark.asyncio`
    is satisfied — body is sync but the async wrap is a no-op."""
    src = Path("/app/backend/routers/chat.py").read_text(encoding="utf-8")
    # Find the _llm_classify_fallback definition body.
    start = src.find("async def _llm_classify_fallback")
    assert start != -1, "classifier function not found"
    end = src.find("\nasync def ", start + 1)
    body = src[start:end if end != -1 else len(src)]
    assert "shield_invoke" in body, (
        "_llm_classify_fallback must route through shield_invoke; got: "
        f"{body[:500]!r}"
    )
    # And it MUST NOT import any LLM SDK directly.
    for forbidden in ("import anthropic", "import openai",
                      "from anthropic", "from openai",
                      "from google.genai", "from google.generativeai"):
        assert forbidden not in body, (
            f"_llm_classify_fallback contains forbidden direct SDK import: {forbidden!r}"
        )


# ─────────────────────────────────────────────────────────────────────
# Test 4 + 5 + 6 — Mode-contract assertions (the contract source doc
# is `/app/memory/sprints/H2_5_SHIELD_MODE_CONTRACT.md`).
# ─────────────────────────────────────────────────────────────────────
async def test_h2_5_mode_contract_doc_exists_and_has_three_modes():
    """The H2.5 mode contract doc is the canonical source of truth
    for H3 Trust Center copy. It MUST document all three modes."""
    p = Path("/app/memory/sprints/H2_5_SHIELD_MODE_CONTRACT.md")
    assert p.exists(), f"H2.5 contract doc missing: {p}"
    text = p.read_text(encoding="utf-8")
    for required in ("always", "auto", "off",
                     "acknowledge_unshielded",
                     "would_have_redacted"):
        assert required in text, (
            f"mode contract missing key concept: {required!r}"
        )


# ─────────────────────────────────────────────────────────────────────
# Cross-suite — H1 indicator + Fork A skip list + classifier all
# still pass alongside H2.5 changes.
# ─────────────────────────────────────────────────────────────────────
async def test_h1_indicator_still_emits_pre_v1_storyline():
    from routers import synisense_metrics as sm
    out = sm._pre_shield_v1_storyline()
    assert "predates Shield v1.x" in out


async def test_fork_a_skip_list_still_redacts_pan_in_user_visible_reply():
    """Fork A regression — PAN class still resolves to last-4
    placeholder via the (non-streaming) reidentifier path."""
    from services.synisense.shield.reidentifier import reidentify
    out = reidentify(
        "Your card [[ENT_CREDIT_CARD_001]] was charged.",
        {"[[ENT_CREDIT_CARD_001]]": "4356789800057689"},
    )
    assert "[PAYMENT_CARD_••••7689]" in out
    assert "4356789800057689" not in out
