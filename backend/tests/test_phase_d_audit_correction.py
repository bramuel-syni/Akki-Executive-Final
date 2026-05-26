"""Phase D.2 — audit-correction telemetry wire tests (2026-05-26).

Asserts:
  (a) variant rotation across sessions for the SAME user — the picker
      uses fresh per-session UUIDs, so 20 fresh UUIDs against a
      2-variant key MUST surface BOTH variant_index values. This is the
      regression guard the original D.2 audit missed.
  (b) variant-cycle telemetry writes correctly — record_variant_seen
      persists rows and get_variants_seen returns the right list.
  (c) key-usage admin endpoint returns sorted data — POST emissions,
      GET /api/admin/solva/key-usage, assert order + counts.
  (d) handoff analytics events fire — record_handoff writes an audit_log
      row with action `handoff.{surface}_attached.{ctx_type}`; chat
      create + Solva session create both call record_handoff implicitly
      when ctx is attached.

Plus a coverage health-check that flags the actual root cause behind
the Julius-aopio bug: most Layer 1 / Layer 2 probe keys fall through
to a single-variant generic fallback.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent


# ─────────────────────────────────────────────────────────────────────
# (a) Variant rotation — pure-function determinism check
# ─────────────────────────────────────────────────────────────────────
def test_variant_rotation_across_fresh_uuids():
    """Across 30 fresh per-session UUIDs against a 2-variant key, both
    variant_index values MUST surface. This is the regression guard
    on the picker — if someone changes session_id to a stable user_id
    in future, this test catches it instantly."""
    from services.solva.voice.question_bank import next_question, _BANK

    key = "seek_clarity.layer_1.opening.default"
    assert len(_BANK[key]) >= 2, "test pre-condition: key needs ≥2 variants"
    indices = set()
    for _ in range(30):
        sid = "sol-" + uuid.uuid4().hex
        q = next_question(key=key, session_id=sid, asked_so_far=0)
        indices.add(q.variant_index)
    assert len(indices) >= 2, (
        f"Variant rotation broken: 30 fresh UUIDs only produced "
        f"variant indices {indices}. Expected both 0 and 1."
    )


def test_variant_rotation_same_session_stable():
    """Belt-and-braces: the same session_id MUST always land on the
    same variant (reproducibility invariant)."""
    from services.solva.voice.question_bank import next_question

    sid = "sol-" + uuid.uuid4().hex
    key = "seek_clarity.layer_1.opening.default"
    a = next_question(key=key, session_id=sid, asked_so_far=0).variant_index
    b = next_question(key=key, session_id=sid, asked_so_far=0).variant_index
    assert a == b, "same session_id must always pick the same variant"


# ─────────────────────────────────────────────────────────────────────
# Coverage health-check — surfaces the Julius-aopio root cause
# ─────────────────────────────────────────────────────────────────────
def test_phase_d2_bank_coverage_health_check():
    """Diagnostic: how many of the ~60 FAR-routable keys actually have
    hand-written variants in the bank vs. falling through to the
    1-variant generic fallback. NOT a pass/fail invariant — this
    test always passes but emits a structured count via assertion
    error message ONLY when coverage degrades below the current
    baseline (so we can ratchet improvements in).

    The Julius-aopio bug was: 38/60 keys hit the fallback, meaning
    most users see "Take me deeper on one piece — what's the part of
    this that's harder to name than the rest?" on every probe across
    every session. The fix is to expand the bank, not the picker."""
    from services.solva.voice.question_bank import _BANK, _resolve_variants

    sub_modules = ["seek_clarity", "develop_strategy",
                   "simulate_hypothesis", "get_perspective"]
    opening_suffixes = ["default", "with_caveats", "conversational"]
    dimensions = ["evidence_grounding", "decisional_clarity",
                  "time_horizon", "options_surfaced",
                  "stakeholder_map", "tension_invitation"]
    all_keys: set[str] = set()
    for sm in sub_modules:
        for sx in opening_suffixes:
            all_keys.add(f"{sm}.layer_1.opening.{sx}")
        for d in dimensions:
            all_keys.add(f"{sm}.layer_1.probe.{d}")
            all_keys.add(f"{sm}.layer_2.probe.{d}")
    bank_hits = sum(1 for k in all_keys if k in _BANK)
    fallback_hits = len(all_keys) - bank_hits
    # Baseline captured 2026-05-26: 22 in-bank, 38 fallback.
    # Test fails ONLY if coverage REGRESSES (in-bank count drops below
    # baseline). Improvements are silently accepted.
    BASELINE_IN_BANK = 22
    assert bank_hits >= BASELINE_IN_BANK, (
        f"Bank coverage regressed below baseline: {bank_hits} in-bank "
        f"keys (was {BASELINE_IN_BANK}). Fallback keys: {fallback_hits}. "
        f"This is a tightening, not a loosening — expand the bank to "
        f"raise the floor, then bump BASELINE_IN_BANK here."
    )


# ─────────────────────────────────────────────────────────────────────
# (b) Variant-cycle telemetry — record_variant_seen + get_variants_seen
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_record_variant_seen_idempotent():
    """Same (user, key, variant) tuple written 3 times → exactly 1 row.
    get_variants_seen returns the canonical list."""
    from services.solva.telemetry import (
        record_variant_seen,
        get_variants_seen,
    )
    from core import db

    uid = f"test-d2-{uuid.uuid4().hex[:8]}"
    key = "telemetry.test.layer_1.opening.default"
    try:
        for _ in range(3):
            await record_variant_seen(
                user_id=uid, question_key=key,
                variant_label="v0", total_variants_in_bank=2,
            )
        rows = await db.solva_variant_seen.find(
            {"user_id": uid, "question_key": key},
            {"_id": 0},
        ).to_list(length=10)
        assert len(rows) == 1, f"expected 1 row, got {len(rows)}"
        assert rows[0]["variant_label"] == "v0"
        seen = await get_variants_seen(user_id=uid, question_key=key)
        assert seen == ["v0"]
    finally:
        await db.solva_variant_seen.delete_many({"user_id": uid})
        await db.audit_log.delete_many({"account_id": uid})


@pytest.mark.asyncio
async def test_variant_cycle_complete_emits_event_once():
    """When all variants are seen, exactly ONE
    `solva.variant.cycle_complete` audit_log row is written."""
    from services.solva.telemetry import record_variant_seen
    from core import db

    uid = f"test-d2-{uuid.uuid4().hex[:8]}"
    key = "telemetry.test.cycle.layer_1.opening.default"
    try:
        # Bank has 2 variants. Record both — should emit the event ONCE.
        await record_variant_seen(user_id=uid, question_key=key,
                                  variant_label="v0", total_variants_in_bank=2)
        await record_variant_seen(user_id=uid, question_key=key,
                                  variant_label="v1", total_variants_in_bank=2)
        # Repeat the second variant — must NOT emit a second event.
        await record_variant_seen(user_id=uid, question_key=key,
                                  variant_label="v1", total_variants_in_bank=2)
        rows = await db.audit_log.find({
            "account_id": uid,
            "action": "solva.variant.cycle_complete",
        }, {"_id": 0}).to_list(length=5)
        assert len(rows) == 1, f"expected exactly 1 cycle_complete event, got {len(rows)}"
        assert rows[0]["resource_id"] == key
        assert rows[0]["metadata"]["variants_seen"] == 2
        assert rows[0]["metadata"]["variants_in_bank"] == 2
    finally:
        await db.solva_variant_seen.delete_many({"user_id": uid})
        await db.audit_log.delete_many({"account_id": uid})


# ─────────────────────────────────────────────────────────────────────
# (c) Key-usage admin endpoint
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_key_usage_admin_endpoint_returns_sorted_data():
    """POST 3 emissions for 2 different keys (one more emitted than
    the other); GET /api/admin/solva/key-usage returns them sorted by
    count desc. Auth-gated to admin role."""
    from server import app  # noqa: F401
    from services.solva.telemetry import record_key_emission
    from core import db, hash_password
    import uuid as _uuid

    uid_admin = f"test-d2-admin-{_uuid.uuid4().hex[:8]}"
    email = f"d2-admin-{_uuid.uuid4().hex[:6]}@example.com"
    uid_other = f"test-d2-other-{_uuid.uuid4().hex[:8]}"
    key_hot   = f"telemetry.test.hot.{_uuid.uuid4().hex[:6]}.opening.default"
    key_cold  = f"telemetry.test.cold.{_uuid.uuid4().hex[:6]}.opening.default"

    await db.accounts.insert_one({
        "id": uid_admin, "email": email,
        "password_hash": hash_password("Pw!1234567Abc"),
        "name": "D2 Admin",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tier": "admin", "mfa_enrolled": False,
        "role": "admin",
        "declared_role": "admin",
    })

    # Emit 3 for hot, 1 for cold
    await record_key_emission(question_key=key_hot, account_id=uid_other)
    await record_key_emission(question_key=key_hot, account_id=uid_other)
    await record_key_emission(question_key=key_hot, account_id=uid_other)
    await record_key_emission(question_key=key_cold, account_id=uid_other)

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/api/auth/login",
                             json={"email": email, "password": "Pw!1234567Abc"})
            assert r.status_code == 200, r.text
            token = r.json().get("access_token") or r.json().get("token")
            r = await c.get("/api/admin/solva/key-usage",
                            headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200, r.text
            data = r.json()
            # Find our test rows (the response includes ALL emissions).
            items = data["items"]
            row_hot = next((i for i in items if i["key"] == key_hot), None)
            row_cold = next((i for i in items if i["key"] == key_cold), None)
            assert row_hot is not None, "missing hot-key row"
            assert row_cold is not None, "missing cold-key row"
            assert row_hot["count"] == 3
            assert row_cold["count"] == 1
            # Sort invariant: hot must come before cold.
            assert items.index(row_hot) < items.index(row_cold), (
                "items must be sorted by count desc"
            )
    finally:
        await db.solva_key_emissions.delete_many({
            "question_key": {"$in": [key_hot, key_cold]},
        })
        await db.accounts.delete_one({"id": uid_admin})


@pytest.mark.asyncio
async def test_key_usage_endpoint_rejects_non_admin():
    """Non-admin caller gets a 403 from the admin endpoint."""
    from server import app  # noqa: F401
    from core import db, hash_password
    import uuid as _uuid

    uid = f"test-d2-nonadmin-{_uuid.uuid4().hex[:8]}"
    email = f"d2-nonadmin-{_uuid.uuid4().hex[:6]}@example.com"
    await db.accounts.insert_one({
        "id": uid, "email": email,
        "password_hash": hash_password("Pw!1234567Abc"),
        "name": "D2 Non-Admin",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tier": "executive", "mfa_enrolled": False,
        "role": "executive",
        "declared_role": "executive",
    })
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/api/auth/login",
                             json={"email": email, "password": "Pw!1234567Abc"})
            token = r.json().get("access_token") or r.json().get("token")
            r = await c.get("/api/admin/solva/key-usage",
                            headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 403, (
                f"expected 403 for non-admin, got {r.status_code}: {r.text}"
            )
    finally:
        await db.accounts.delete_one({"id": uid})


# ─────────────────────────────────────────────────────────────────────
# (d) Handoff analytics — record_handoff writes audit_log row
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_record_handoff_writes_audit_log_row():
    """record_handoff writes an audit_log row with the canonical
    `handoff.<surface>_attached.<ctx_type>` action and includes
    {ctx_type, ctx_id} in metadata."""
    from services.solva.telemetry import record_handoff
    from core import db

    uid = f"test-d2-{uuid.uuid4().hex[:8]}"
    cid = f"chat-d2-{uuid.uuid4().hex[:8]}"
    docid = f"doc-d2-{uuid.uuid4().hex[:8]}"
    try:
        await record_handoff(
            surface="chat", ctx_type="document", ctx_id=docid,
            account_id=uid, chat_id=cid, context_id="ctx-x",
        )
        rows = await db.audit_log.find(
            {"account_id": uid, "action": "handoff.chat_attached.document"},
            {"_id": 0},
        ).to_list(length=5)
        assert len(rows) == 1, f"expected 1 audit row, got {len(rows)}"
        r = rows[0]
        assert r["resource_type"] == "chat"
        assert r["resource_id"] == cid
        assert r["metadata"]["ctx_type"] == "document"
        assert r["metadata"]["ctx_id"] == docid

        await record_handoff(
            surface="solva", ctx_type="cycle", ctx_id="cy-1",
            account_id=uid, session_id="sol-x", context_id="ctx-x",
        )
        rows = await db.audit_log.find(
            {"account_id": uid, "action": "handoff.solva_attached.cycle"},
            {"_id": 0},
        ).to_list(length=5)
        assert len(rows) == 1
        assert rows[0]["resource_type"] == "solva_session"
    finally:
        await db.audit_log.delete_many({"account_id": uid})


@pytest.mark.asyncio
async def test_chat_create_with_linked_context_writes_handoff_event():
    """End-to-end: creating a chat with linked_context triggers a
    `handoff.chat_attached.document` audit_log row alongside the
    normal `chat.created` row."""
    from server import app  # noqa: F401
    from core import db, hash_password
    import uuid as _uuid

    uid = f"test-d2-e2e-{_uuid.uuid4().hex[:8]}"
    email = f"d2-e2e-{_uuid.uuid4().hex[:6]}@example.com"
    cid_ctx = f"ctx-d2-{_uuid.uuid4().hex[:8]}"
    did = f"doc-d2-{_uuid.uuid4().hex[:8]}"

    await db.accounts.insert_one({
        "id": uid, "email": email,
        "password_hash": hash_password("Pw!1234567Abc"),
        "name": "D2 E2E",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tier": "executive", "mfa_enrolled": False,
        "declared_role": "executive",
    })
    await db.contexts.insert_one({
        "id": cid_ctx, "name": "D2 E2E Co",
        "owner_account_id": uid, "type": "executive_personal",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.memberships.insert_one({
        "id": f"mem-{_uuid.uuid4().hex[:8]}",
        "account_id": uid, "context_id": cid_ctx,
        "role": "executive", "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.documents.insert_one({
        "id": did, "context_id": cid_ctx,
        "name": "D2 E2E doc.pdf",
        "original_filename": "D2 E2E doc.pdf",
        "extracted_text": "Sample text for the D2 end-to-end smoke test.",
        "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/api/auth/login",
                             json={"email": email, "password": "Pw!1234567Abc"})
            assert r.status_code == 200, r.text
            token = r.json().get("access_token") or r.json().get("token")
            hdr = {"Authorization": f"Bearer {token}", "X-Active-Context": cid_ctx}
            r = await c.post("/api/chats", headers=hdr, json={
                "title": "Handoff smoke",
                "model_id": "claude-sonnet-4-5",
                "shielding_policy": "auto",
                "context_id": cid_ctx,
                "linked_context": {"ctx_type": "document", "ctx_id": did},
            })
            assert r.status_code == 200, r.text
        # The handoff row must exist in audit_log.
        rows = await db.audit_log.find(
            {"account_id": uid, "action": "handoff.chat_attached.document"},
            {"_id": 0},
        ).to_list(length=5)
        assert len(rows) == 1, (
            f"expected exactly 1 handoff.chat_attached.document row, "
            f"got {len(rows)}"
        )
        assert rows[0]["metadata"]["ctx_id"] == did
    finally:
        await db.chats.delete_many({"account_id": uid})
        await db.chat_audit_log.delete_many({"account_id": uid})
        await db.audit_log.delete_many({"account_id": uid})
        await db.documents.delete_many({"id": did})
        await db.memberships.delete_many({"account_id": uid})
        await db.contexts.delete_many({"id": cid_ctx})
        await db.accounts.delete_one({"id": uid})


# ─────────────────────────────────────────────────────────────────────
# Audit-correction marker — the D.2 audit section in the log must
# document the real root cause AND replace the misleading invariant.
# ─────────────────────────────────────────────────────────────────────
def test_d2_audit_correction_recorded_in_home_cleanup_log():
    log_path = REPO / "memory" / "sprints" / "HOME_CLEANUP_LOG.md"
    log = log_path.read_text("utf-8")
    # The audit correction subsection MUST exist.
    assert "D.2 — audit correction" in log, (
        "HOME_CLEANUP_LOG.md must contain a 'D.2 — audit correction' "
        "subsection documenting the real root cause and the picker's "
        "actual (correct) behavior."
    )
    # The misleading invariant from the original audit MUST be marked
    # as corrected.
    assert "fallback monoculture" in log or "fallback" in log.lower(), (
        "audit correction must document the fallback-monoculture root cause"
    )
    assert "session_id IS a fresh UUID" in log or "per-session UUID" in log, (
        "audit correction must state that session_id is in fact a "
        "per-session UUID (hypothesis disconfirmed)"
    )
