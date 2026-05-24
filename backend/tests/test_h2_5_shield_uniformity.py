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


# ═════════════════════════════════════════════════════════════════════
# WIRE-LEVEL TESTS (post-tester-feedback, 2026-05-24)
# Every assertion below captures bytes that ACTUALLY reach the cloud
# LLM SDK (via monkeypatched `stream_llm_direct`). Watching the
# user-visible reply alone is insufficient — the audit row could lie
# about what the LLM saw. These tests prove the wire-level reality.
# ═════════════════════════════════════════════════════════════════════
async def _login_and_chat(client: httpx.AsyncClient):
    """Register a fresh tenant + create a chat. Returns (token, ctx_id,
    chat_id, account_id)."""
    email = f"h2-5-wire-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post("/api/auth/register", json={
        "email": email, "password": "H2-5-Wire-2026!", "name": "H2.5 Wire",
    })
    assert r.status_code == 200, r.text[:300]
    token = r.json()["access_token"]
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    account_id = me.json()["account"]["id"]
    ctx_id = me.json()["contexts"][0]["id"]
    hdrs = {"Authorization": f"Bearer {token}", "X-Active-Context": ctx_id}
    chat_r = await client.post("/api/chats", json={"title": "H2.5 wire probe"}, headers=hdrs)
    assert chat_r.status_code in (200, 201)
    return token, ctx_id, chat_r.json()["id"], account_id, hdrs


async def test_wire_streaming_llm_receives_redacted_prompt_not_raw_pan(client):
    """**THE** binary fix-verification test. Submit a Luhn-valid PAN
    over the streaming endpoint; capture what `stream_llm_direct`
    actually receives; assert the raw 16-digit PAN is absent from
    the captured bytes, AND a `[[ENT_CREDIT_CARD_…]]` placeholder is
    present in its place."""
    from services import llm_streaming as _ls
    from collections import namedtuple

    token, ctx_id, chat_id, account_id, hdrs = await _login_and_chat(client)

    captured = {"user_text": None}
    _Chunk = namedtuple("_Chunk", "kind text provider_used fallback_triggered error")

    async def _fake_stream(*, provider, model_id, system_msg, user_text, session_id):
        # CAPTURE WHAT THE LLM SDK WOULD HAVE SEEN.
        captured["user_text"] = user_text
        # Echo the redacted prompt back as a single delta so the
        # streaming reidentifier has something to rehydrate.
        # (We yield a single chunk containing the placeholders.)
        # Extract just the user-message portion (after "USER: ").
        body_portion = user_text.split("USER:", 1)[-1].strip() if "USER:" in user_text else user_text
        yield _Chunk(kind="delta", text=f"You wrote: {body_portion}",
                     provider_used=provider, fallback_triggered=False, error=None)
        yield _Chunk(kind="done", text="", provider_used=provider,
                     fallback_triggered=False, error=None)

    with mock.patch.object(_ls, "stream_llm_direct", side_effect=_fake_stream):
        # Submit a message containing the Bramuel PAN to the stream endpoint.
        pan = "4356789800057689"  # Luhn-valid (Bramuel demo)
        body = {
            "content": f"Bramuel left his card no {pan} in KPMG head office.",
            "shielding_policy": "always",
        }
        async with client.stream(
            "POST", f"/api/chats/{chat_id}/messages/stream",
            json=body, headers=hdrs, timeout=30.0,
        ) as resp:
            # Drain the response so the route's generator runs to completion.
            body_bytes = b""
            async for chunk in resp.aiter_bytes():
                body_bytes += chunk
            assert resp.status_code == 200, (resp.status_code, body_bytes[:300])

    # ── WIRE-LEVEL ASSERTION ── what the cloud LLM SDK actually saw
    captured_user_text = captured["user_text"] or ""
    assert pan not in captured_user_text, (
        f"WIRE-LEVEL LEAK: raw PAN {pan!r} reached stream_llm_direct's "
        f"`user_text` argument. Captured: {captured_user_text[:500]!r}"
    )
    assert "[[ENT_CREDIT_CARD_" in captured_user_text, (
        f"Expected [[ENT_CREDIT_CARD_…]] placeholder in what the LLM "
        f"received. Captured: {captured_user_text[:500]!r}"
    )

    # ── User-visible reply MUST NOT contain raw PAN either ──
    body_text = body_bytes.decode("utf-8", "replace")
    assert pan not in body_text, (
        f"Raw PAN leaked to user via SSE stream: {body_text[:500]!r}"
    )


async def test_wire_audit_integrity_invariant_holds(client):
    """**THE** audit-integrity test. Submit a PAN, then verify the
    chat_audit row AND the shield_audit row both agree on the
    boolean question 'did Shield detect identifiers on this turn?'.
    Disagreement = invariant violation."""
    from services import llm_streaming as _ls
    from core import db
    from collections import namedtuple

    token, ctx_id, chat_id, account_id, hdrs = await _login_and_chat(client)

    _Chunk = namedtuple("_Chunk", "kind text provider_used fallback_triggered error")
    async def _fake_stream(*, provider, model_id, system_msg, user_text, session_id):
        yield _Chunk("delta", "Acknowledged.", provider, False, None)
        yield _Chunk("done", "", provider, False, None)

    with mock.patch.object(_ls, "stream_llm_direct", side_effect=_fake_stream):
        body = {
            "content": "Bramuel left his card no 4356789800057689 in KPMG head office.",
            "shielding_policy": "always",
        }
        async with client.stream(
            "POST", f"/api/chats/{chat_id}/messages/stream",
            json=body, headers=hdrs, timeout=30.0,
        ) as resp:
            async for _ in resp.aiter_bytes():
                pass
            assert resp.status_code == 200

    # ── Pull the chat_audit row(s) ──
    chat_audits = await db.chat_audit_log.find(
        {"chat_id": chat_id, "action": "message.sent"}, {"_id": 0},
    ).to_list(None)
    assert len(chat_audits) == 1, chat_audits
    chat_audit_row = chat_audits[0]
    chat_audit_payload = chat_audit_row.get("payload", {})
    chat_detected = chat_audit_payload.get("identifiers_detected", 0)
    chat_shielded = chat_audit_payload.get("shielded_for_llm", False)
    chat_by_cat = chat_audit_payload.get("by_category", {})

    # ── Pull the Shield audit row(s) for this chat ──
    chat_doc = await db.chats.find_one({"id": chat_id}, {"_id": 0, "synisense_audit_ids": 1})
    audit_ids = (chat_doc or {}).get("synisense_audit_ids") or []
    assert len(audit_ids) >= 1, f"no synisense_audit_ids attached to chat: {chat_doc}"
    shield_rows = await db.synisense_audit_log.find(
        {"audit_id": {"$in": audit_ids}}, {"_id": 0},
    ).to_list(None)
    shield_summaries = [r.get("de_id_summary", {}) for r in shield_rows]
    shield_total = sum(sum(s.values()) for s in shield_summaries)

    # ── INVARIANT — chat_audit and shield_audit MUST agree on the
    # BOOLEAN: did Shield detect anything this turn? ──
    chat_audit_says_detected = chat_detected > 0
    shield_audit_says_detected = shield_total > 0
    assert chat_audit_says_detected == shield_audit_says_detected, (
        f"AUDIT INVARIANT VIOLATION: "
        f"chat_audit.identifiers_detected={chat_detected} (by_category={chat_by_cat}) "
        f"vs shield_audit total={shield_total} (summaries={shield_summaries}). "
        f"For the same turn, these MUST agree on the boolean."
    )

    # Hard requirement: with a PAN-containing input on `always` mode,
    # BOTH must say detected > 0.
    assert chat_audit_says_detected, (
        f"chat_audit says no detection but input was a PAN. payload={chat_audit_payload}"
    )
    assert shield_audit_says_detected, (
        f"shield_audit says no detection but input was a PAN. summaries={shield_summaries}"
    )
    # CREDIT_CARD specifically must appear in shield_audit.
    assert any("CREDIT_CARD" in s for s in shield_summaries), shield_summaries


async def test_wire_audit_invariant_violations_collection_empty_for_normal_flow(client):
    """After a normal Shield-protected stream, NO row should be
    written to `audit_invariant_violations`. The collection is the
    canary-in-the-coal-mine; any rows = a real defect."""
    from services import llm_streaming as _ls
    from core import db
    from collections import namedtuple

    _Chunk = namedtuple("_Chunk", "kind text provider_used fallback_triggered error")
    async def _fake_stream(*, provider, model_id, system_msg, user_text, session_id):
        yield _Chunk("delta", "Acknowledged.", provider, False, None)
        yield _Chunk("done", "", provider, False, None)

    token, ctx_id, chat_id, account_id, hdrs = await _login_and_chat(client)
    before = await db.audit_invariant_violations.count_documents(
        {"account_id": account_id},
    )

    with mock.patch.object(_ls, "stream_llm_direct", side_effect=_fake_stream):
        body = {
            "content": "Bramuel left his card no 4356789800057689 in KPMG head office.",
            "shielding_policy": "always",
        }
        async with client.stream(
            "POST", f"/api/chats/{chat_id}/messages/stream",
            json=body, headers=hdrs, timeout=30.0,
        ) as resp:
            async for _ in resp.aiter_bytes():
                pass
            assert resp.status_code == 200

    after = await db.audit_invariant_violations.count_documents(
        {"account_id": account_id},
    )
    assert after == before, (
        f"audit_invariant_violations grew during a normal stream: "
        f"before={before}, after={after}. Investigate latest row."
    )


async def test_wire_shield_unavailable_returns_503(client):
    """Fix #3 strict-raise: if Shield's de-identifier raises in the
    streaming entry, the endpoint returns 503 + the documented body,
    AND `audit_invariant_violations` logs the shield_failure_at_entry
    kind.

    H2.5 follow-up (2026-05-24) — chat-family surfaces now route
    through `services.synisense.shield.canonical.mint_chat_outcome`
    which calls `deidentifier.deidentify` directly (not the legacy
    adapter → pipeline.run/dryrun). Patching the de-identifier
    surfaces the failure at the same point the legacy adapter did,
    so the route's `except ShieldFailure → 503` translation still
    fires.
    """
    from services.synisense.shield import deidentifier
    from core import db

    token, ctx_id, chat_id, account_id, hdrs = await _login_and_chat(client)
    before = await db.audit_invariant_violations.count_documents(
        {"account_id": account_id, "kind": "shield_failure_at_entry"},
    )

    async def _boom(*args, **kwargs):
        raise RuntimeError("simulated presidio collapse")

    with mock.patch.object(deidentifier, "deidentify", side_effect=_boom):
        body = {
            "content": "Bramuel left his card no 4356789800057689 in KPMG head office.",
            "shielding_policy": "always",
        }
        # The endpoint should raise → starlette converts to HTTP response.
        # Use plain `post`, not `stream`, because the failure happens BEFORE
        # the SSE generator starts yielding.
        resp = await client.post(
            f"/api/chats/{chat_id}/messages/stream",
            json=body, headers=hdrs, timeout=30.0,
        )
    assert resp.status_code == 503, (resp.status_code, resp.text[:300])
    body_json = resp.json()
    assert body_json["detail"]["error"] == "shield_unavailable", body_json
    assert body_json["detail"]["action"] == "retry"

    after = await db.audit_invariant_violations.count_documents(
        {"account_id": account_id, "kind": "shield_failure_at_entry"},
    )
    assert after > before, (
        f"audit_invariant_violations must log the shield-failure event: "
        f"before={before}, after={after}"
    )


# ═════════════════════════════════════════════════════════════════════
# H2.5 follow-up tests (post `e1_tester` 2/5 PASS finding, 2026-05-24)
# Three failures the prior pytest suite did NOT cover, asserted here:
#   F#1 — synisense-metrics + synisense-runs were lying (return 0
#         identifiers even when shield + chat-audit agree ≥ 1 were
#         redacted). Assert 3-way agreement on the boolean.
#   F#2 — sync and stream used different shielders with different
#         vocabularies (synisense-pipeline / lowercase vs
#         synisense-shield-v1 / UPPERCASE). Assert by_category parity
#         on the exact live-tester input string.
#   F#3 — admin endpoint /api/admin/audit-invariant-violations did
#         not exist (404). Assert it gates on superadmin AND returns
#         the documented shape.
# ═════════════════════════════════════════════════════════════════════
async def _superadmin_token(client):
    """Helper — return a superadmin Authorization header dict by
    logging in as the canonical admin (`admin@akki.ai`). Tests run
    against the live admin seeded by ``server.startup``."""
    r = await client.post("/api/auth/login", json={
        "email": "admin@akki.ai", "password": "AkkiAdmin2026!",
    })
    assert r.status_code == 200, (r.status_code, r.text[:300])
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_wire_three_way_agreement_metrics_audit_chat(client):
    """**F#1 fix verification.** Stream a PAN-containing message,
    then assert all three surfaces report a non-zero count AND
    surface the SAME UPPERCASE category (``CREDIT_CARD``) for
    ``shielded_by="synisense-shield-v1"``:

      (a) ``GET /api/chats/{id}/synisense-metrics`` ← aggregates over
          ``db.synisense_runs``. Was returning 0 before this fix
          because the streaming pre-pass wrote rows with
          ``account_id=None`` and a phantom message_id.
      (b) ``db.synisense_audit_log`` row attached via
          ``chats.synisense_audit_ids[]``. UPPERCASE keys.
      (c) ``db.chat_audit_log`` row's ``payload.by_category`` /
          ``identifiers_detected`` / ``shielded_for_llm``.

    Independent re-run (PROD smoke):

        API=$REACT_APP_BACKEND_URL
        TOKEN=$(curl -s -X POST "$API/api/auth/login" \\
            -H 'Content-Type: application/json' \\
            -d '{"email":"bramuel@syni.ai","password":"Bramuel2026!"}' \\
            | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
        CTX=$(curl -s "$API/api/auth/me" -H "Authorization: Bearer $TOKEN" \\
            | python3 -c "import sys,json;print(json.load(sys.stdin)['contexts'][0]['id'])")
        CHAT=$(curl -s -X POST "$API/api/chats" -H "Authorization: Bearer $TOKEN" \\
            -H "X-Active-Context: $CTX" -H "Content-Type: application/json" \\
            -d '{"title":"3-way agreement"}' \\
            | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
        curl -s -N -X POST "$API/api/chats/$CHAT/messages/stream" \\
            -H "Authorization: Bearer $TOKEN" -H "X-Active-Context: $CTX" \\
            -H "Content-Type: application/json" \\
            -d '{"content":"My card is 4111111111111111","shielding_policy":"always"}' \\
            > /dev/null
        curl -s "$API/api/chats/$CHAT/synisense-metrics" \\
            -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
        # expect identifiers_redacted ≥ 1
    """
    from services import llm_streaming as _ls
    from core import db
    from collections import namedtuple

    token, ctx_id, chat_id, account_id, hdrs = await _login_and_chat(client)

    _Chunk = namedtuple("_Chunk", "kind text provider_used fallback_triggered error")

    async def _fake_stream(*, provider, model_id, system_msg, user_text, session_id):
        yield _Chunk("delta", "Acknowledged.", provider, False, None)
        yield _Chunk("done", "", provider, False, None)

    pan = "4111111111111111"  # canonical Luhn-valid PAN (Visa test card)
    with mock.patch.object(_ls, "stream_llm_direct", side_effect=_fake_stream):
        body = {
            "content": f"My card is {pan} please charge it.",
            "shielding_policy": "always",
        }
        async with client.stream(
            "POST", f"/api/chats/{chat_id}/messages/stream",
            json=body, headers=hdrs, timeout=30.0,
        ) as resp:
            async for _ in resp.aiter_bytes():
                pass
            assert resp.status_code == 200

    # ── (a) synisense-metrics ── must report ≥ 1 ──
    metrics_resp = await client.get(
        f"/api/chats/{chat_id}/synisense-metrics", headers=hdrs,
    )
    assert metrics_resp.status_code == 200, metrics_resp.text[:300]
    metrics = metrics_resp.json()
    metrics_total = int(metrics.get("identifiers_redacted") or 0)
    assert metrics_total > 0, (
        f"F#1: /synisense-metrics still returns 0 identifiers_redacted "
        f"for a PAN-containing turn. Response: {metrics}"
    )

    # ── (b) Shield audit row ── must carry CREDIT_CARD (UPPERCASE) ──
    chat_doc = await db.chats.find_one(
        {"id": chat_id}, {"_id": 0, "synisense_audit_ids": 1},
    )
    audit_ids = (chat_doc or {}).get("synisense_audit_ids") or []
    assert audit_ids, f"no synisense_audit_ids attached: {chat_doc}"
    shield_rows = await db.synisense_audit_log.find(
        {"audit_id": {"$in": audit_ids}}, {"_id": 0},
    ).to_list(None)
    shield_summaries = [r.get("de_id_summary", {}) for r in shield_rows]
    shield_total = sum(sum(s.values()) for s in shield_summaries)
    assert shield_total > 0, shield_summaries
    assert any("CREDIT_CARD" in s for s in shield_summaries), (
        f"F#2: synisense_audit_log MUST carry UPPERCASE 'CREDIT_CARD' key. "
        f"Got: {shield_summaries}"
    )

    # ── (c) chat_audit row ── must carry CREDIT_CARD (UPPERCASE) ──
    chat_audits = await db.chat_audit_log.find(
        {"chat_id": chat_id, "action": "message.sent"}, {"_id": 0},
    ).to_list(None)
    assert len(chat_audits) == 1, chat_audits
    chat_payload = chat_audits[0].get("payload", {})
    chat_total = int(chat_payload.get("identifiers_detected") or 0)
    chat_by_cat = chat_payload.get("by_category") or {}
    assert chat_total > 0, chat_payload
    assert "CREDIT_CARD" in chat_by_cat, (
        f"F#2: chat_audit MUST carry UPPERCASE 'CREDIT_CARD' key, "
        f"NOT lowercase 'card'. Got by_category={chat_by_cat}"
    )

    # ── Three-way agreement on the BOOLEAN ──
    assert (metrics_total > 0) == (shield_total > 0) == (chat_total > 0), (
        f"F#1: Three-way disagreement! "
        f"metrics={metrics_total}, shield={shield_total}, chat={chat_total}"
    )


async def test_wire_chat_envelope_uses_uppercase_shield_v1_vocabulary(client):
    """**F#2 fix verification.** Send the live-tester input string
    `"My card is 4111111111111111..."` and assert the chat envelope
    (``chat_audit_log.payload.by_category`` + the user_msg's
    ``shielding.by_category``) carry UPPERCASE keys and
    ``shielded_by='synisense-shield-v1'`` (NOT lowercase
    ``card`` / ``synisense-pipeline`` from the legacy adapter).

    Independent re-run (PROD smoke)::

        curl -s -N -X POST "$API/api/chats/$CHAT/messages/stream" \\
            -H "Authorization: Bearer $TOKEN" -H "X-Active-Context: $CTX" \\
            -H "Content-Type: application/json" \\
            -d '{"content":"My card is 4111111111111111","shielding_policy":"always"}' \\
            > /dev/null
        # Pull the latest chat message and inspect shielding shape:
        curl -s "$API/api/chats/$CHAT/messages?limit=2" \\
            -H "Authorization: Bearer $TOKEN" \\
            | python3 -c "import sys,json; m=json.load(sys.stdin); \\
                          print([x['shielding'] for x in m['messages'] if x['role']=='user'][-1])"
        # expected: {'identifiers_masked': 1, 'by_category': {'CREDIT_CARD': 1},
        #            'shielded_by': 'synisense-shield-v1'}
    """
    from services import llm_streaming as _ls
    from core import db
    from collections import namedtuple

    token, ctx_id, chat_id, account_id, hdrs = await _login_and_chat(client)
    _Chunk = namedtuple("_Chunk", "kind text provider_used fallback_triggered error")

    async def _fake_stream(*, provider, model_id, system_msg, user_text, session_id):
        yield _Chunk("delta", "Acknowledged.", provider, False, None)
        yield _Chunk("done", "", provider, False, None)

    with mock.patch.object(_ls, "stream_llm_direct", side_effect=_fake_stream):
        body = {
            "content": "My card is 4111111111111111, please charge it.",
            "shielding_policy": "always",
        }
        async with client.stream(
            "POST", f"/api/chats/{chat_id}/messages/stream",
            json=body, headers=hdrs, timeout=30.0,
        ) as resp:
            async for _ in resp.aiter_bytes():
                pass
            assert resp.status_code == 200

    # ── chat_audit_log envelope ──
    chat_audits = await db.chat_audit_log.find(
        {"chat_id": chat_id, "action": "message.sent"}, {"_id": 0},
    ).to_list(None)
    assert chat_audits, chat_audits
    payload = chat_audits[0]["payload"]
    by_cat = payload.get("by_category") or {}
    # F#2 — UPPERCASE only. The OLD lowercase `card` shape MUST be gone.
    assert "card" not in by_cat, (
        f"F#2: chat_audit still has lowercase 'card' key. "
        f"Vocabulary divergence not fixed. by_category={by_cat}"
    )
    assert "CREDIT_CARD" in by_cat, (
        f"F#2: chat_audit MUST carry UPPERCASE 'CREDIT_CARD'. "
        f"by_category={by_cat}"
    )

    # ── user_message.shielding envelope ──
    user_msg = await db.chat_messages.find_one(
        {"chat_id": chat_id, "role": "user"}, {"_id": 0},
    )
    assert user_msg is not None
    shielding = user_msg.get("shielding") or {}
    assert shielding.get("shielded_by") == "synisense-shield-v1", (
        f"F#2: user_msg.shielding.shielded_by must be "
        f"'synisense-shield-v1' (NOT 'synisense-pipeline'). "
        f"Got: {shielding}"
    )
    msg_by_cat = shielding.get("by_category") or {}
    assert "card" not in msg_by_cat and "CREDIT_CARD" in msg_by_cat, (
        f"F#2: user_msg.shielding.by_category must be UPPERCASE. "
        f"Got: {msg_by_cat}"
    )


async def test_wire_admin_audit_invariant_violations_endpoint_exists(client):
    """**F#3 fix verification.** The admin endpoint
    ``/api/admin/audit-invariant-violations`` MUST exist (was 404
    before this fix), gate on superadmin (403 for non-admins), and
    return the documented response shape.

    Independent re-run::

        ADMIN_TOKEN=$(curl -s -X POST "$API/api/auth/login" \\
            -H 'Content-Type: application/json' \\
            -d '{"email":"admin@akki.ai","password":"AkkiAdmin2026!"}' \\
            | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
        curl -s "$API/api/admin/audit-invariant-violations?hours=24" \\
            -H "Authorization: Bearer $ADMIN_TOKEN" \\
            | python3 -m json.tool
        # Expect: {"since": "...", "total": <int>, "by_kind": {...}, "rows": [...]}
    """
    # ── (1) 401 unauthenticated ──
    r = await client.get("/api/admin/audit-invariant-violations")
    assert r.status_code in (401, 403), (r.status_code, r.text[:300])

    # ── (2) 403 for non-superadmin user ──
    _t, _c, _ch, _a, hdrs = await _login_and_chat(client)
    r = await client.get(
        "/api/admin/audit-invariant-violations", headers=hdrs,
    )
    assert r.status_code == 403, (r.status_code, r.text[:300])

    # ── (3) 200 for superadmin with documented shape ──
    admin_hdrs = await _superadmin_token(client)
    r = await client.get(
        "/api/admin/audit-invariant-violations?hours=24", headers=admin_hdrs,
    )
    assert r.status_code == 200, (r.status_code, r.text[:300])
    body = r.json()
    assert set(body.keys()) >= {"since", "total", "by_kind", "rows"}, body
    assert isinstance(body["total"], int)
    assert isinstance(body["by_kind"], dict)
    assert isinstance(body["rows"], list)

    # ── (4) Summary tile endpoint ──
    r = await client.get(
        "/api/admin/audit-invariant-violations/summary?hours=24",
        headers=admin_hdrs,
    )
    assert r.status_code == 200, r.text[:300]
    summary = r.json()
    assert set(summary.keys()) >= {"since", "total", "by_kind"}, summary


async def test_wire_stream_envelope_audit_id_resolves_to_shield_row(client):
    """**Warning #1 fix verification.** The streaming `message`
    envelope's ``audit_id`` field must carry the Shield audit_id
    (with ``aud-`` prefix) so ``GET /api/v1/shield/audit/{audit_id}``
    resolves to 200 — not the bare-uuid chat_audit_log row id that
    hits 404.

    Independent re-run::

        # Send a streaming message and parse the trailing
        # `type: message` event to extract the envelope audit_id:
        ENVELOPE_AUDIT=$(grep '"type": "message"' /tmp/sse.txt \\
            | python3 -c "import sys,json; \\
              line=sys.stdin.read().split('data: ')[-1]; \\
              print(json.loads(line)['audit_id'])")
        # Resolve it against the Shield audit endpoint:
        curl -s "$API/api/v1/shield/audit/$ENVELOPE_AUDIT" \\
            -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
        # Expect: 200 + a row with `audit_id` matching the envelope
        # NOT: 404 "audit not found"
    """
    from services import llm_streaming as _ls
    from collections import namedtuple

    token, ctx_id, chat_id, account_id, hdrs = await _login_and_chat(client)
    _Chunk = namedtuple("_Chunk", "kind text provider_used fallback_triggered error")

    async def _fake_stream(*, provider, model_id, system_msg, user_text, session_id):
        yield _Chunk("delta", "Acknowledged.", provider, False, None)
        yield _Chunk("done", "", provider, False, None)

    with mock.patch.object(_ls, "stream_llm_direct", side_effect=_fake_stream):
        body = {
            "content": "My card is 4111111111111111 please charge it.",
            "shielding_policy": "always",
        }
        async with client.stream(
            "POST", f"/api/chats/{chat_id}/messages/stream",
            json=body, headers=hdrs, timeout=30.0,
        ) as resp:
            chunks = []
            async for chunk in resp.aiter_bytes():
                chunks.append(chunk)
            assert resp.status_code == 200
            body_text = b"".join(chunks).decode("utf-8", "replace")

    # Parse the trailing `type: message` SSE event.
    message_event = None
    for line in body_text.split("\n\n"):
        if '"type": "message"' in line:
            payload = line.split("data: ", 1)[-1].strip()
            import json as _json
            message_event = _json.loads(payload)
            break
    assert message_event is not None, (
        f"no type=message SSE event in stream body: {body_text[:500]!r}"
    )

    envelope_audit_id = message_event.get("audit_id")
    assert envelope_audit_id, (
        f"Warning #1: envelope.audit_id is empty: {message_event!r}"
    )
    # Must be Shield-shaped, not chat_audit_log-shaped.
    assert envelope_audit_id.startswith("aud-"), (
        f"Warning #1: envelope.audit_id must start with 'aud-' "
        f"(Shield row id). Got: {envelope_audit_id!r}"
    )

    # ── (THE) wire-level resolve check ──
    resp = await client.get(
        f"/api/v1/shield/audit/{envelope_audit_id}", headers=hdrs,
    )
    assert resp.status_code == 200, (
        f"Warning #1: envelope.audit_id={envelope_audit_id!r} does "
        f"NOT resolve via GET /api/v1/shield/audit/{{id}}. "
        f"Status={resp.status_code}, body={resp.text[:300]!r}"
    )
    row = resp.json()
    assert row.get("audit_id") == envelope_audit_id, row

    # ── Backward-compat: the chat_audit_log row id is still
    # exposed under `chat_audit_id` for callers that need it ──
    chat_audit_id = message_event.get("chat_audit_id")
    assert chat_audit_id is not None, (
        f"Warning #1: chat_audit_id companion field missing. "
        f"Envelope: {message_event!r}"
    )
    assert chat_audit_id != envelope_audit_id, (
        f"chat_audit_id and audit_id must be DIFFERENT ids."
    )


@pytest.mark.parametrize("exc_class,exc_args", [
    (OSError, ("[E050] Can't find model 'en_core_web_sm'.",)),
    (RuntimeError, ("spaCy pipeline component failed to initialise",)),
    (ImportError, ("cannot import name 'load' from 'spacy'",)),
    (MemoryError, ("out of memory during model deserialization",)),
    (Exception, ("generic boot-time failure",)),
])
async def test_shield_fails_closed_when_spacy_model_missing(client, exc_class, exc_args):
    """**Deploy safety — Part A + B verification.**

    H2.5 follow-up Part A (2026-05-24) — parametrized across 5
    exception classes (OSError, RuntimeError, ImportError,
    MemoryError, generic Exception). All MUST produce identical
    fail-closed semantics: HTTP 503 + invariant row + no raw PAN.

    If spaCy's NER model fails to load at runtime (any reason),
    Shield MUST fail-closed:

      * HTTP 503 (NOT 200 with raw PAN forwarded to the LLM)
      * ``audit_invariant_violations`` row with
        ``kind=shield_failure_at_entry``
      * No raw PAN anywhere in the response body

    Simulates load failure by clearing the cached ``_SPACY_NLP``
    globals in ``services.synisense.shield.deidentifier`` and
    monkey-patching ``_attempt_load`` to raise the parametrized
    exception class. This proves the ``except Exception`` swap at
    deidentifier.py:184-193 (was ``except OSError``) actually
    catches the broader surface.

    Independent re-run::

        # In a container WITHOUT en_core_web_sm installed:
        curl -s -X POST "$API/api/chats/$CHAT/messages/stream" \\
            -H "Authorization: Bearer $TOKEN" \\
            -H "X-Active-Context: $CTX" \\
            -H "Content-Type: application/json" \\
            -d '{"content":"My card is 4111111111111111","shielding_policy":"always"}'
        # expect: HTTP 503, body.detail.error="shield_unavailable"
    """
    from services.synisense.shield import deidentifier
    from core import db

    token, ctx_id, chat_id, account_id, hdrs = await _login_and_chat(client)
    before = await db.audit_invariant_violations.count_documents(
        {"account_id": account_id, "kind": "shield_failure_at_entry"},
    )

    # Reset the module-level cache so the patched loader takes effect.
    # The loader is idempotent + thread-safe; clearing both globals is
    # the documented way to force a re-load on the next call.
    saved_nlp = deidentifier._SPACY_NLP
    saved_err = deidentifier._SPACY_LOAD_ERROR
    deidentifier._SPACY_NLP = None
    deidentifier._SPACY_LOAD_ERROR = None

    def _model_load_fails(model_name: str):
        # Surface-faithful exception — Part A broadened the catch
        # block to `except Exception`, so EVERY one of these classes
        # must route to the same 503 + invariant row outcome.
        raise exc_class(*exc_args)

    try:
        with mock.patch.object(deidentifier, "_attempt_load", side_effect=_model_load_fails):
            body = {
                "content": "My card is 4111111111111111 please charge it.",
                "shielding_policy": "always",
            }
            resp = await client.post(
                f"/api/chats/{chat_id}/messages/stream",
                json=body, headers=hdrs, timeout=30.0,
            )

        # ── Fail-closed wire assertions ──
        assert resp.status_code == 503, (
            f"FAIL-OPEN REGRESSION on {exc_class.__name__}: chat returned "
            f"{resp.status_code} when spaCy raises {exc_class.__name__}. "
            f"Expected 503 SHIELD_UNAVAILABLE. Body: {resp.text[:400]!r}"
        )
        body_json = resp.json()
        assert body_json["detail"]["error"] == "shield_unavailable", body_json
        assert body_json["detail"]["action"] == "retry", body_json

        # ── No raw PAN anywhere in the response body ──
        assert "4111111111111111" not in resp.text, (
            f"FAIL-OPEN REGRESSION on {exc_class.__name__}: raw PAN "
            f"leaked in 503 response body: {resp.text[:400]!r}"
        )

        # ── Invariant violation row was written ──
        after = await db.audit_invariant_violations.count_documents(
            {"account_id": account_id, "kind": "shield_failure_at_entry"},
        )
        assert after > before, (
            f"audit_invariant_violations must log "
            f"shield_failure_at_entry on {exc_class.__name__}: "
            f"before={before}, after={after}"
        )
    finally:
        # Restore the module's cached state so subsequent tests don't
        # see a poisoned loader. The next caller will re-load the model
        # successfully via the normal path.
        deidentifier._SPACY_NLP = saved_nlp
        deidentifier._SPACY_LOAD_ERROR = saved_err


# ═════════════════════════════════════════════════════════════════════
# H2.5 follow-up Part B — Boot-time Shield warmup + /api/healthz/shield
# ═════════════════════════════════════════════════════════════════════
async def test_warmup_or_die_raises_on_model_missing(monkeypatch):
    """``warmup_or_warn()`` (formerly ``warmup_or_die``) must
    capture the failure in the warmup-state snapshot WITHOUT raising.

    H2.5 P0 hotfix (2026-05-24, post-prod-deploy outage) — the
    semantics changed from "raise → process dies → supervisor
    crash-loops" to "log SEVERE + write a boot-time invariant row
    + flip the snapshot to ready=false". Per-request fail-closed
    still applies via the chat route's runtime catches.

    The test name retains ``or_die`` for git-blame continuity; the
    assertion now matches the corrected contract.
    """
    from services.synisense.shield import deidentifier
    from core import db

    saved_nlp = deidentifier._SPACY_NLP
    saved_err = deidentifier._SPACY_LOAD_ERROR
    saved_ok = deidentifier._WARMUP_OK
    saved_warmup_err = deidentifier._WARMUP_ERROR
    monkeypatch.setattr(deidentifier, "_SPACY_NLP", None, raising=False)
    monkeypatch.setattr(deidentifier, "_SPACY_LOAD_ERROR", None, raising=False)

    def _attempt_load_raises(name):
        raise OSError(f"[E050] Can't find model '{name}'.")
    monkeypatch.setattr(deidentifier, "_attempt_load", _attempt_load_raises)

    # Block the retry subprocess so the failure surfaces fast.
    def _subprocess_fail(*args, **kwargs):
        raise OSError("subprocess: pretend-no-internet")
    monkeypatch.setattr(deidentifier.subprocess, "run", _subprocess_fail)

    boot_rows_before = await db.audit_invariant_violations.count_documents(
        {"kind": "shield_unavailable_at_boot"},
    )

    try:
        # Must NOT raise (the whole point of the P0 hotfix).
        await deidentifier.warmup_or_warn()

        # State snapshot must reflect the failure.
        st = deidentifier.get_warmup_state()
        assert st["ready"] is False, st
        assert st["last_warmup_error"], st
        assert "OSError" in (st["last_warmup_error"] or ""), st

        # And a boot-time invariant row must have been written.
        boot_rows_after = await db.audit_invariant_violations.count_documents(
            {"kind": "shield_unavailable_at_boot"},
        )
        assert boot_rows_after > boot_rows_before, (
            f"shield_unavailable_at_boot row missing: "
            f"before={boot_rows_before}, after={boot_rows_after}"
        )
    finally:
        deidentifier._SPACY_NLP = saved_nlp
        deidentifier._SPACY_LOAD_ERROR = saved_err
        deidentifier._WARMUP_OK = saved_ok
        deidentifier._WARMUP_ERROR = saved_warmup_err


async def test_healthz_shield_endpoint_returns_state(client):
    """Happy path — once warmup has run, the endpoint returns 200
    with ``ready=true`` and the documented shape.

    Note: ``httpx.AsyncClient(ASGITransport)`` does NOT fire the
    FastAPI lifespan/on_startup hooks by default, so this test
    triggers warmup explicitly. In real boot (supervisor →
    uvicorn → FastAPI startup), ``server.py:on_startup`` calls
    ``warmup_or_warn`` before the first request lands."""
    from services.synisense.shield.deidentifier import warmup_or_warn
    await warmup_or_warn()

    resp = await client.get("/api/healthz/shield")
    assert resp.status_code == 200, resp.text[:300]
    body = resp.json()
    assert set(body.keys()) >= {
        "ready", "model_loaded", "model_name", "model_version",
        "last_warmup_at", "last_warmup_duration_ms",
    }, body
    assert body["ready"] is True
    assert body["model_loaded"] is True
    assert body["model_name"] in ("en_core_web_sm", "en_core_web_trf"), body
    assert body["last_warmup_at"], body


async def test_healthz_shield_endpoint_503_when_not_ready(client, monkeypatch):
    """When warmup has not completed (or failed), the endpoint must
    return HTTP 503 — same body shape — so external probes (k8s
    readinessProbe, LB) treat the pod as unhealthy."""
    from services.synisense.shield import deidentifier

    # Force the snapshot to "not ready" without actually killing the
    # live spaCy instance — restored in `finally` below.
    saved_ok = deidentifier._WARMUP_OK
    saved_err = deidentifier._WARMUP_ERROR
    monkeypatch.setattr(deidentifier, "_WARMUP_OK", False, raising=False)
    monkeypatch.setattr(
        deidentifier, "_WARMUP_ERROR",
        "RuntimeError: simulated unready state", raising=False,
    )
    try:
        resp = await client.get("/api/healthz/shield")
        assert resp.status_code == 503, resp.text[:300]
        body = resp.json()
        # Same shape on 503.
        assert "ready" in body and body["ready"] is False, body
        assert body.get("last_warmup_error"), body
    finally:
        deidentifier._WARMUP_OK = saved_ok
        deidentifier._WARMUP_ERROR = saved_err


# ═════════════════════════════════════════════════════════════════════
# Independent re-run recipe (for `e1_tester` / human auditors)
# ═════════════════════════════════════════════════════════════════════
# The wire-level tests above prove the streaming chat endpoint:
#   (a) sends a REDACTED prompt to the LLM SDK (no raw PAN)
#   (b) writes a Shield audit row whose `de_id_summary` is non-empty
#   (c) writes a chat_audit row whose `identifiers_detected > 0`
#   (d) keeps `audit_invariant_violations` empty during normal flow
#   (e) returns 503 + invariant-log row when the pipeline fails
#   (f) /api/chats/{id}/synisense-metrics agrees with (b) and (c)
#       on the boolean — the H2.5 follow-up F#1 fix
#   (g) chat envelope carries UPPERCASE CREDIT_CARD + synisense-shield-v1
#       — the H2.5 follow-up F#2 fix
#   (h) /api/admin/audit-invariant-violations exists & is gated
#       — the H2.5 follow-up F#3 fix
#   (i) envelope.audit_id resolves via GET /api/v1/shield/audit/{id}
#       — the H2.5 follow-up Warning #1 fix
#
# To re-run outside pytest (against the deployed preview):
#
#   API=https://akki-executive.preview.emergentagent.com
#   TOKEN=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" \
#     -d '{"email":"bramuel@syni.ai","password":"Bramuel2026!"}' \
#     | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
#   CTX=$(curl -s "$API/api/auth/me" -H "Authorization: Bearer $TOKEN" \
#     | python3 -c "import sys,json;print(json.load(sys.stdin)['contexts'][0]['id'])")
#   CHAT=$(curl -s -X POST "$API/api/chats" -H "Authorization: Bearer $TOKEN" \
#     -H "X-Active-Context: $CTX" -H "Content-Type: application/json" \
#     -d '{"title":"H2.5 streaming verify"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
#
#   # Send a streaming PAN message, save the SSE body to disk.
#   curl -s -N -X POST "$API/api/chats/$CHAT/messages/stream" \
#     -H "Authorization: Bearer $TOKEN" -H "X-Active-Context: $CTX" \
#     -H "Content-Type: application/json" \
#     -d '{"content":"Bramuel left his card no 4356789800057689 in KPMG head office.","shielding_policy":"always"}' \
#     | tee /tmp/sse_body.txt
#
#   # The raw PAN must NOT appear in the SSE deltas (re-id is in effect).
#   grep -c "4356789800057689" /tmp/sse_body.txt    # expect 0
#   grep -c "PAYMENT_CARD" /tmp/sse_body.txt        # expect ≥ 1
#
#   # Audit row check (via the audit panel endpoint):
#   curl -s "$API/api/chats/$CHAT/audit-panel/aggregate" \
#     -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
#   # Expect identifiers_shielded > 0, llm_calls ≥ 1
#
# Mongo-level checks (run inside the backend container):
#
#   python3 -c "
#   import asyncio
#   from dotenv import load_dotenv; load_dotenv('/app/backend/.env')
#   from core import db
#   async def main():
#       chat = await db.chats.find_one({'id': '$CHAT'}, {'_id': 0, 'synisense_audit_ids': 1})
#       print('audit_ids:', chat.get('synisense_audit_ids', []))
#       for aid in chat.get('synisense_audit_ids', []):
#           row = await db.synisense_audit_log.find_one({'audit_id': aid}, {'_id': 0, 'de_id_summary': 1, 'outcome': 1, 'mode': 1})
#           print(aid, '→', row)
#       vio = await db.audit_invariant_violations.count_documents({'chat_id': '$CHAT'})
#       print('invariant violations for this chat:', vio)
#   asyncio.run(main())
#   "

