"""Q4Y P1-C2 (2026-02 fork-resume) — "Use in Chat" CTA wiring.

Coverage:
  1. Source-strict — `LinkedContextIn._check_ctx_type` allow-list
     now includes `question`; `_resolve_linked_context` has the
     `question` branch.
  2. Source-strict — `Questions.jsx` drawer renders
     `question-drawer-use-in-chat` and navigates to
     `/app/chat?ctx_type=question&ctx_id=…`.
  3. `_resolve_linked_context(question, qid, context_id)` returns the
     expected shape with `ctx_type="question"`, sensible title,
     excerpt containing the question + (optional) answer text.
  4. Tenant scoping — calling `_resolve_linked_context` with a
     mismatched `context_id` returns None (the find_one is
     scoped on `context_id` so cross-tenant lookups silently miss
     instead of leaking).
  5. `LinkedContextIn` rejects unknown ctx_type strings + accepts
     `question`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core import db


REPO = Path(__file__).resolve().parent.parent.parent
BE = REPO / "backend"
CHAT_ROUTER = BE / "routers" / "chat.py"
PAGE = REPO / "frontend" / "src" / "pages" / "Questions.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════
# Source-strict
# ═════════════════════════════════════════════════════════════════════
def test_q4y_c2_chat_router_allowlist_includes_question():
    src = _read(CHAT_ROUTER)
    # The _check_ctx_type allowlist now contains `question`.
    assert '"question"' in src
    # The _resolve_linked_context branch exists.
    assert 'if ctx_type == "question":' in src
    assert 'db.cycle_questions.find_one(' in src
    # Q4Y reference comment.
    assert "Q4Y P1-C2" in src


def test_q4y_c2_drawer_button_navigates_to_chat():
    src = _read(PAGE)
    assert 'data-testid="question-drawer-use-in-chat"' in src
    assert '/app/chat?ctx_type=question&ctx_id=' in src
    assert "Use in Chat" in src


# ═════════════════════════════════════════════════════════════════════
# Wire-level — direct call into _resolve_linked_context + validator
# ═════════════════════════════════════════════════════════════════════
async def _seed_question(*, context_id: str, text: str,
                          answer_text: str = "",
                          status: str = "open",
                          asker_role: str = "board") -> str:
    qid = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": qid, "context_id": context_id, "cycle_id": "",
        "assignee_account_id": "any-aid",
        "asker_role": asker_role,
        "text": text, "status": status, "asked_at": now,
        "history": [{"ts": now, "kind": "raised", "actor_id": "any-aid"}],
        "_qa_seed": True,
    }
    if answer_text:
        doc["answer_text"] = answer_text
        doc["answered_at"] = now
    await db.cycle_questions.insert_one(doc)
    return qid


@pytest.mark.asyncio
async def test_q4y_c2_seed_returns_shape_for_open_question():
    from routers.chat import _resolve_linked_context
    cid = f"ctx-c2-{uuid.uuid4().hex[:8]}"
    qid = await _seed_question(
        context_id=cid,
        text="What is the impact of currency hedging on Q4 EBITDA?",
    )
    try:
        seed = await _resolve_linked_context(
            ctx_type="question", ctx_id=qid,
            context_id=cid, account_id="any-aid",
        )
        assert seed is not None
        assert seed["ctx_type"] == "question"
        assert seed["ctx_id"] == qid
        # Title = first 60 chars (no ellipsis if shorter).
        assert "What is the impact of currency hedging on Q4 EBITDA?" == seed["title"]
        # Excerpt carries the body.
        assert "currency hedging" in seed["excerpt"]
        assert "Status: open" in seed["excerpt"]
        assert "asked by board" in seed["excerpt"]
        # Href points back to the Questions page.
        assert seed["href"] == f"/app/questions?q={qid}"
    finally:
        await db.cycle_questions.delete_many({"id": qid})


@pytest.mark.asyncio
async def test_q4y_c2_seed_includes_answer_when_answered():
    from routers.chat import _resolve_linked_context
    cid = f"ctx-c2-{uuid.uuid4().hex[:8]}"
    qid = await _seed_question(
        context_id=cid, text="Will runway hold under scenario B?",
        answer_text="Yes — 14 months at current burn.",
        status="answered",
    )
    try:
        seed = await _resolve_linked_context(
            ctx_type="question", ctx_id=qid,
            context_id=cid, account_id="any-aid",
        )
        assert seed is not None
        assert "Answer so far: Yes — 14 months at current burn." in seed["excerpt"]
        assert "Status: answered" in seed["excerpt"]
    finally:
        await db.cycle_questions.delete_many({"id": qid})


@pytest.mark.asyncio
async def test_q4y_c2_seed_truncates_long_title():
    from routers.chat import _resolve_linked_context
    cid = f"ctx-c2-{uuid.uuid4().hex[:8]}"
    long_text = ("Lorem ipsum dolor sit amet, consectetur adipiscing "
                 "elit, sed do eiusmod tempor incididunt ut labore et "
                 "dolore magna aliqua.")
    qid = await _seed_question(context_id=cid, text=long_text)
    try:
        seed = await _resolve_linked_context(
            ctx_type="question", ctx_id=qid,
            context_id=cid, account_id="any-aid",
        )
        assert seed is not None
        # Title is 60-char snippet + ellipsis.
        assert seed["title"].endswith("…")
        assert len(seed["title"].rstrip("…").rstrip()) <= 60
    finally:
        await db.cycle_questions.delete_many({"id": qid})


@pytest.mark.asyncio
async def test_q4y_c2_seed_returns_none_for_cross_tenant():
    """Cross-tenant guard — `_resolve_linked_context` looks up
    cycle_questions row by `(id, context_id)`. Passing the WRONG
    context_id returns None instead of leaking.

    # negative-leak: locks in tenant isolation for the C2 seed.
    """
    from routers.chat import _resolve_linked_context
    cid_a = f"ctx-c2-A-{uuid.uuid4().hex[:6]}"
    cid_b = f"ctx-c2-B-{uuid.uuid4().hex[:6]}"
    qid = await _seed_question(
        context_id=cid_a, text="Tenant A secret question.",
    )
    try:
        # Look up via wrong context (B) — must return None.
        seed = await _resolve_linked_context(
            ctx_type="question", ctx_id=qid,
            context_id=cid_b, account_id="any-aid",
        )
        assert seed is None
    finally:
        await db.cycle_questions.delete_many({"id": qid})


def test_q4y_c2_validator_accepts_question_and_rejects_unknown():
    """LinkedContextIn pydantic validator allows `question` and
    rejects unknown strings."""
    from routers.chat import LinkedContextIn
    # Accepts.
    inst = LinkedContextIn(ctx_type="question", ctx_id="some-id")
    assert inst.ctx_type == "question"
    # work_studio aliasing remains: work_studio → work_studio_artefact
    inst2 = LinkedContextIn(ctx_type="work_studio", ctx_id="x")
    assert inst2.ctx_type == "work_studio_artefact"
    # Rejects unknown.
    with pytest.raises(Exception):
        LinkedContextIn(ctx_type="bogus_kind", ctx_id="x")
