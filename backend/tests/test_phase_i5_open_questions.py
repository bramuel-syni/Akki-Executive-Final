"""Phase I.5 — Open Questions wiring CI guards (2026-05-27).

Locks:
  Pure mapper
    M1.  `map_membership_role_to_bucket` → exhaustive role-bucket map.
    M2.  Unknown / None / empty → 'team' (forward-compat).
    M3.  `format_decomposition_subtext` — empty → "Nothing open."
    M4.  Single-bucket: "3 from CEO" — zero segments omitted.
    M5.  Mixed buckets: "1 from board · 2 from CEO · 4 from team".

  DB-touching deriver
    D1.  `derive_asker_role` resolves through memberships.role
    D2.  Missing account_id → 'team'
    D3.  Missing membership row → 'team'

  Endpoint
    E1.  `_build_questions` returns the `QuestionsDecomposition` model
         with sum-to-count invariant.
    E2.  Subtext format on populated context.
    E3.  Empty state subtext == "Nothing open."
    E4.  Pre-I.5 docs with absent `asker_role` are counted in 'team'
         bucket (matches the backfill rule E2=a).

  Insert-time hook
    H1.  Raising a question via `routers.questions.raise_question`
         writes `asker_role` derived from the caller's membership.role.

  Backfill script
    B1.  Backfill is idempotent — re-run on already-backfilled rows
         is a no-op.

  Negative invariants
    N1.  No `cycles.team[]` references in `services/open_questions`
         (E1=a decision: use memberships, not cycles.team[]).
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
SVC = REPO / "backend" / "services" / "open_questions" / "asker_role_map.py"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ─────────────────────────────────────────────────────────────────
# M1-M5 — Pure mapper / formatter
# ─────────────────────────────────────────────────────────────────

def test_i5_M1_M2_role_bucket_map_pure():
    from services.open_questions.asker_role_map import (
        map_membership_role_to_bucket as fn,
    )
    # M1 — exhaustive map
    assert fn("ned")       == "board"
    assert fn("owner")     == "board"
    assert fn("executive") == "ceo"
    # M2 — unknown/None/empty/whitespace defaults to team
    assert fn(None)        == "team"
    assert fn("")          == "team"
    assert fn("future_role_we_haven_t_invented_yet") == "team"
    # Case-insensitive
    assert fn("NED")       == "board"
    assert fn("  Owner ")  == "board"


def test_i5_M3_M4_M5_subtext_formatter():
    from services.open_questions.asker_role_map import (
        format_decomposition_subtext as fmt,
    )
    # M3 — empty/all-zero
    assert fmt({})                                  == "Nothing open."
    assert fmt({"board": 0, "ceo": 0, "team": 0})   == "Nothing open."
    assert fmt(None)                                 == "Nothing open."
    # M4 — single bucket: zero segments omitted
    assert fmt({"board": 0, "ceo": 3, "team": 0})   == "3 from CEO"
    assert fmt({"board": 1, "ceo": 0, "team": 0})   == "1 from board"
    assert fmt({"board": 0, "ceo": 0, "team": 5})   == "5 from team"
    # M5 — mixed; locked order (board → CEO → team)
    assert fmt({"board": 1, "ceo": 2, "team": 4})   == "1 from board · 2 from CEO · 4 from team"
    assert fmt({"board": 0, "ceo": 2, "team": 4})   == "2 from CEO · 4 from team"
    assert fmt({"board": 3, "ceo": 0, "team": 1})   == "3 from board · 1 from team"


# ─────────────────────────────────────────────────────────────────
# D1-D3 — DB-touching deriver
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
async def i5_actors():
    from core import db, hash_password
    cid = f"i5-ctx-{uuid.uuid4().hex[:8]}"
    now = _iso(datetime.now(timezone.utc))
    accts = {}
    for role_label in ("ned", "owner", "executive", "stranger"):
        uid = f"i5-{role_label}-{uuid.uuid4().hex[:6]}"
        email = f"i5-{role_label}-{uuid.uuid4().hex[:6]}@ex.com"
        await db.accounts.insert_one({
            "id": uid, "email": email, "password_hash": hash_password("Pw!1234567Ab"),
            "name": f"I5 {role_label}", "tier": "executive",
            "declared_role": "executive", "mfa_enrolled": False,
            "is_superadmin": False, "created_at": now,
        })
        if role_label != "stranger":
            await db.memberships.insert_one({
                "account_id": uid, "context_id": cid,
                "role": role_label, "status": "active", "created_at": now,
            })
        accts[role_label] = {"id": uid, "email": email, "pw": "Pw!1234567Ab"}
    # Make the NED also the owner so they can call /api/me/* contextually.
    await db.contexts.insert_one({
        "id": cid, "name": "I5 Test", "type": "executive_personal",
        "owner_id": accts["ned"]["id"], "created_at": now,
    })
    yield {"cid": cid, "accts": accts}
    # Cleanup
    await db.cycle_questions.delete_many({"context_id": cid})
    await db.contexts.delete_one({"id": cid})
    await db.memberships.delete_many({"context_id": cid})
    for a in accts.values():
        await db.accounts.delete_one({"id": a["id"]})


@pytest.mark.asyncio
async def test_i5_D1_deriver_resolves_through_memberships(i5_actors):
    from services.open_questions.asker_role_map import derive_asker_role
    cid = i5_actors["cid"]
    assert await derive_asker_role(i5_actors["accts"]["ned"]["id"],       cid) == "board"
    assert await derive_asker_role(i5_actors["accts"]["owner"]["id"],     cid) == "board"
    assert await derive_asker_role(i5_actors["accts"]["executive"]["id"], cid) == "ceo"


@pytest.mark.asyncio
async def test_i5_D2_missing_account_id_defaults_team():
    from services.open_questions.asker_role_map import derive_asker_role
    assert await derive_asker_role(None, "any-cid")  == "team"
    assert await derive_asker_role("",   "any-cid")  == "team"


@pytest.mark.asyncio
async def test_i5_D3_missing_membership_defaults_team(i5_actors):
    from services.open_questions.asker_role_map import derive_asker_role
    # stranger account has no membership row
    assert await derive_asker_role(
        i5_actors["accts"]["stranger"]["id"], i5_actors["cid"],
    ) == "team"
    # Non-existent account
    assert await derive_asker_role("no-such-account-xx", i5_actors["cid"]) == "team"


# ─────────────────────────────────────────────────────────────────
# E1-E4 — Card 4 endpoint
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_i5_E1_E2_card4_decomposition_shape_and_subtext(i5_actors):
    from core import db
    cid = i5_actors["cid"]
    now_iso = _iso(datetime.now(timezone.utc))
    # Seed 6 open questions: 1 board (ned), 1 board (owner), 2 ceo,
    # 2 team (stranger account_id, will default to team via missing
    # membership).
    seed = [
        ("q1", i5_actors["accts"]["ned"]["id"],       "board"),
        ("q2", i5_actors["accts"]["owner"]["id"],     "board"),
        ("q3", i5_actors["accts"]["executive"]["id"], "ceo"),
        ("q4", i5_actors["accts"]["executive"]["id"], "ceo"),
        ("q5", i5_actors["accts"]["stranger"]["id"],  "team"),
        ("q6", None,                                   "team"),  # legacy: no asker
    ]
    for qid, asker, bucket in seed:
        doc = {
            "id": f"i5-{qid}-{uuid.uuid4().hex[:6]}",
            "context_id": cid, "cycle_id": "i5-cycle",
            "text": f"Question {qid}", "asked_at": now_iso,
            "status": "open",
        }
        if asker:
            doc["asked_by_account_id"] = asker
            doc["asker_role"] = bucket   # post-hook insertion
        # Note: q6 has NO asker_role → must be counted in 'team' via
        # the endpoint's None-bucket fallback.
        await db.cycle_questions.insert_one(doc)

    from routers.company_home import _build_questions
    card = await _build_questions(cid)
    d = card.model_dump()
    # Shape
    assert "decomposition" in d
    assert set(d["decomposition"].keys()) == {"board", "ceo", "team"}
    # Counts
    assert d["decomposition"]["board"] == 2
    assert d["decomposition"]["ceo"]   == 2
    assert d["decomposition"]["team"]  == 2  # 1 explicit + 1 missing-bucket fallback
    assert d["count"] == 6
    # Subtext (E2)
    assert d["subtext"] == "2 from board · 2 from CEO · 2 from team"


@pytest.mark.asyncio
async def test_i5_E3_empty_state_subtext(i5_actors):
    from routers.company_home import _build_questions
    card = await _build_questions(i5_actors["cid"])
    d = card.model_dump()
    assert d["count"] == 0
    assert d["subtext"] == "Nothing open."
    assert d["decomposition"] == {"board": 0, "ceo": 0, "team": 0}


@pytest.mark.asyncio
async def test_i5_E4_legacy_rows_without_asker_role_count_as_team(i5_actors):
    """Pre-I.5 rows (no asker_role field at all) MUST be counted in
    the team bucket so the decomposition sum equals the total count.
    This locks the absence-default behaviour (E2=a, 2026-05-27).
    """
    from core import db
    cid = i5_actors["cid"]
    now_iso = _iso(datetime.now(timezone.utc))
    # Insert a doc deliberately WITHOUT asker_role
    await db.cycle_questions.insert_one({
        "id": f"i5-legacy-{uuid.uuid4().hex[:6]}",
        "context_id": cid, "text": "legacy question",
        "asked_at": now_iso, "status": "open",
    })
    from routers.company_home import _build_questions
    d = (await _build_questions(cid)).model_dump()
    assert d["count"] == 1
    assert d["decomposition"]["team"] == 1
    assert d["decomposition"]["board"] == 0
    assert d["decomposition"]["ceo"] == 0
    assert d["subtext"] == "1 from team"


# ─────────────────────────────────────────────────────────────────
# H1 — Insert-time hook
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_i5_H1_raise_question_writes_asker_role(i5_actors):
    """POST /api/contexts/{cid}/cycles/{cycle_id}/questions writes
    `asker_role` derived from the caller's memberships.role."""
    from server import app  # noqa: F401
    from core import db
    cid = i5_actors["cid"]
    ned_acct = i5_actors["accts"]["ned"]

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        r = await c.post("/api/auth/login",
                         json={"email": ned_acct["email"], "password": ned_acct["pw"]})
        token = r.json()["access_token"]
        hdr = {"Authorization": f"Bearer {token}"}

        r2 = await c.post(
            f"/api/contexts/{cid}/cycles/test-cycle/questions",
            headers=hdr,
            json={"text": "Will my asker_role be derived?"},
        )
        assert r2.status_code in (200, 201), r2.text
        qid = r2.json()["id"]

    # Direct DB inspection — asker_role must be 'board' (ned member)
    doc = await db.cycle_questions.find_one({"id": qid}, {"_id": 0})
    assert doc is not None
    assert doc.get("asker_role") == "board", (
        f"Expected 'board' for ned member, got {doc.get('asker_role')!r}"
    )
    assert doc.get("asked_by_account_id") == ned_acct["id"]


# ─────────────────────────────────────────────────────────────────
# B1 — Backfill script idempotency
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_i5_B1_backfill_idempotent(i5_actors):
    from core import db
    cid = i5_actors["cid"]
    now_iso = _iso(datetime.now(timezone.utc))
    # Seed: 2 docs without asker_role, 1 already-backfilled
    await db.cycle_questions.insert_many([
        {"id": "bf-1", "context_id": cid, "text": "q1",
         "asked_at": now_iso, "status": "open",
         "asked_by_account_id": i5_actors["accts"]["ned"]["id"]},
        {"id": "bf-2", "context_id": cid, "text": "q2",
         "asked_at": now_iso, "status": "open"},  # no asker_account
        {"id": "bf-3", "context_id": cid, "text": "q3",
         "asked_at": now_iso, "status": "open",
         "asker_role": "ceo"},  # already set
    ])
    from scripts.backfill_asker_role import main as backfill
    res1 = await backfill()
    # Scanned should be 2 (bf-3 has asker_role already)
    assert res1["total"] == 2
    assert res1["board"] == 1   # bf-1 ned → board
    assert res1["team"]  == 1   # bf-2 no asker → team
    # Verify written values
    bf1 = await db.cycle_questions.find_one({"id": "bf-1"}, {"_id": 0})
    bf2 = await db.cycle_questions.find_one({"id": "bf-2"}, {"_id": 0})
    bf3 = await db.cycle_questions.find_one({"id": "bf-3"}, {"_id": 0})
    assert bf1["asker_role"] == "board"
    assert bf2["asker_role"] == "team"
    assert bf3["asker_role"] == "ceo"   # untouched
    # Re-run: no-op (total scanned = 0)
    res2 = await backfill()
    assert res2["total"] == 0


# ─────────────────────────────────────────────────────────────────
# N1 — Source-strict negative invariant
# ─────────────────────────────────────────────────────────────────

def test_i5_N1_no_cycles_team_references_in_asker_role_map():
    """E1=a (2026-05-27) decided to use db.memberships as the role
    source, NOT cycles.team[] (which doesn't exist in live data).
    Source-strict guard against accidentally re-introducing the
    cycles.team[] lookup pattern in EXECUTABLE code.

    Strips docstrings + comments first so this guard doesn't fire on
    the module docstring that DOCUMENTS the design decision (the
    docstring legitimately discusses why cycles.team[] isn't used).
    """
    import re as _re
    src = SVC.read_text(encoding="utf-8")
    code = _re.sub(r'"""[\s\S]*?"""', "", src)
    code = _re.sub(r"#[^\n]*", "", code)
    for forbidden in ("cycles.team", "cycle.team", "team[]", "cycle['team']", "cycle[\"team\"]"):
        assert forbidden not in code, (
            f"`{forbidden}` reintroduces a lookup source that does "
            f"not exist in live data — E1=a locked memberships as the "
            f"truth source."
        )
    # Positive: memberships IS the source
    assert "memberships" in code, "asker_role_map must use db.memberships."
