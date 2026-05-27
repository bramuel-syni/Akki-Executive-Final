"""Phase I.2 — Company Home data wiring CI guard (2026-05-27).

Locks the I.2 contract:

  Backend:
    T1.  Both endpoints exist and require auth.
    T2.  `/api/me/company-home/readiness?context_id=…` returns
         `{readiness_percent: int|null, open_task_count: int}`
         with sensible shape across seeded data + empty cases.
    T3.  `/api/me/company-home/attention?context_id=…` returns the
         5-card shape; every card has non-null `count` and
         non-empty `subtext`.
    T4.  Card 4 (questions) subtext does NOT pre-wire I.5
         asker-role decomposition phrasing.
    T5.  Card 5 (events) is always count=0 + "No events scheduled".

  Frontend wire:
    T6.  `CompanyHome.jsx` imports `api` from `@/lib/api` and
         fires GETs to both endpoints.
    T7.  Readiness strip carries `data-testid="company-home-readiness"`.
    T8.  All 5 card placeholders bind to live data (count + subtext).
    T9.  Click routing uses the canonical context-filtered routes per
         card; `events` card is a no-op.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
COMPANY_HOME = REPO / "frontend" / "src" / "pages" / "CompanyHome.jsx"
ROUTER       = REPO / "backend" / "routers" / "company_home.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ═════════════════════════════════════════════════════════════════
# Backend live tests
# ═════════════════════════════════════════════════════════════════

@pytest.fixture
async def i2_actor():
    from core import db, hash_password
    uid = f"i2-{uuid.uuid4().hex[:8]}"
    email = f"i2-{uuid.uuid4().hex[:6]}@example.com"
    pw = "Pw!1234567Abc"
    cid = f"i2-ctx-{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)
    now_iso = _iso(now)

    await db.accounts.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(pw),
        "name": "I2 Tester", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False, "created_at": now_iso,
    })
    await db.contexts.insert_one({
        "id": cid, "name": "I2 Test Co",
        "type": "executive_personal", "owner_id": uid,
        "created_at": now_iso,
    })
    await db.memberships.insert_one({
        "account_id": uid, "context_id": cid, "status": "active",
        "role": "executive", "created_at": now_iso,
    })

    # Seed tasks: 2 with readiness 60, 1 with readiness 90 (compile-eligible).
    await db.tasks.insert_many([
        {"id": f"i2-t-{i}", "context_id": cid, "state": "active",
         "readiness_score": score, "created_at": now_iso}
        for i, score in enumerate([60, 60, 90])
    ])
    # Seed drafts: 1 ned + 2 cycle, all status="draft". Oldest is 5d.
    await db.ned_followups.insert_one({
        "id": f"i2-ned-{uuid.uuid4().hex[:6]}",
        "context_id": cid, "status": "draft",
        "created_at": _iso(now - timedelta(days=5)),
    })
    await db.cycle_followups.insert_many([
        {"id": f"i2-cy-{i}", "context_id": cid, "status": "draft",
         "created_at": _iso(now - timedelta(days=d))}
        for i, d in enumerate([1, 2])
    ])
    # Seed pulse signals: 2 risk + 1 opportunity in last 7d.
    await db.signals.insert_many([
        {"id": f"i2-sig-r1", "context_id": cid, "type": "risk",
         "created_at": _iso(now - timedelta(days=1))},
        {"id": f"i2-sig-r2", "context_id": cid, "type": "risk",
         "created_at": _iso(now - timedelta(days=2))},
        {"id": f"i2-sig-o1", "context_id": cid, "type": "opportunity",
         "created_at": _iso(now - timedelta(days=3))},
    ])
    # Seed cycle_questions: 2 open + 1 closed.
    await db.cycle_questions.insert_many([
        {"id": f"i2-q-{i}", "context_id": cid, "status": status,
         "created_at": now_iso}
        for i, status in enumerate(["open", "open", "closed"])
    ])

    yield {"uid": uid, "email": email, "password": pw, "cid": cid}

    # Teardown.
    await db.accounts.delete_one({"id": uid})
    await db.contexts.delete_one({"id": cid})
    await db.memberships.delete_many({"account_id": uid})
    await db.tasks.delete_many({"context_id": cid})
    await db.ned_followups.delete_many({"context_id": cid})
    await db.cycle_followups.delete_many({"context_id": cid})
    await db.signals.delete_many({"context_id": cid})
    await db.cycle_questions.delete_many({"context_id": cid})


async def _login(c, actor):
    r = await c.post("/api/auth/login",
                     json={"email": actor["email"], "password": actor["password"]})
    tok = r.json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


# ── T1. Auth gate ─────────────────────────────────────────────────
@pytest.mark.asyncio
@pytest.mark.parametrize("path", [
    "/api/me/company-home/readiness?context_id=any",
    "/api/me/company-home/attention?context_id=any",
])
async def test_i2_endpoints_require_auth(path):
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        r = await c.get(path)
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_i2_endpoints_403_on_non_member(i2_actor):
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i2_actor)
        # Forge a context_id the user is not a member of.
        for path in (
            "/api/me/company-home/readiness?context_id=not-a-member-ctx",
            "/api/me/company-home/attention?context_id=not-a-member-ctx",
        ):
            r = await c.get(path, headers=hdr)
            assert r.status_code == 403, f"{path} → {r.status_code}"


# ── T2. Readiness shape + math ────────────────────────────────────
@pytest.mark.asyncio
async def test_i2_readiness_returns_weighted_average(i2_actor):
    from server import app  # noqa: F401
    cid = i2_actor["cid"]
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i2_actor)
        r = await c.get(
            f"/api/me/company-home/readiness?context_id={cid}", headers=hdr,
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "readiness_percent" in body and "open_task_count" in body
    # Seeded: 3 tasks @ scores 60, 60, 90 → avg=70.
    assert body["readiness_percent"] == 70
    assert body["open_task_count"] == 3
    # Range guard.
    assert 0 <= body["readiness_percent"] <= 100


@pytest.mark.asyncio
async def test_i2_readiness_returns_null_when_no_open_tasks():
    from core import db, hash_password
    from server import app  # noqa: F401

    uid = f"i2e-{uuid.uuid4().hex[:8]}"
    email = f"i2e-{uuid.uuid4().hex[:6]}@example.com"
    pw = "Pw!1234567Abc"
    cid = f"i2e-ctx-{uuid.uuid4().hex[:6]}"
    now_iso = _iso(datetime.now(timezone.utc))
    await db.accounts.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(pw),
        "name": "I2 Empty", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False, "created_at": now_iso,
    })
    await db.contexts.insert_one({
        "id": cid, "name": "I2 Empty Co", "type": "executive_personal",
        "owner_id": uid, "created_at": now_iso,
    })
    await db.memberships.insert_one({
        "account_id": uid, "context_id": cid, "status": "active",
        "role": "executive", "created_at": now_iso,
    })
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test") as c:
            r = await c.post("/api/auth/login",
                             json={"email": email, "password": pw})
            tok = r.json()["access_token"]
            r = await c.get(
                f"/api/me/company-home/readiness?context_id={cid}",
                headers={"Authorization": f"Bearer {tok}"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["readiness_percent"] is None
        assert body["open_task_count"] == 0
    finally:
        await db.accounts.delete_one({"id": uid})
        await db.contexts.delete_one({"id": cid})
        await db.memberships.delete_many({"account_id": uid})


# ── T3. Attention shape + counts ─────────────────────────────────
@pytest.mark.asyncio
async def test_i2_attention_returns_all_five_cards_with_seeded_counts(i2_actor):
    from server import app  # noqa: F401
    cid = i2_actor["cid"]
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i2_actor)
        r = await c.get(
            f"/api/me/company-home/attention?context_id={cid}", headers=hdr,
        )
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("drafts", "reports", "pulse", "questions", "events"):
        assert key in body, f"missing card `{key}` in {body}"
        assert "count" in body[key]
        assert "subtext" in body[key]
        assert isinstance(body[key]["count"], int)
        assert body[key]["count"] >= 0
        assert isinstance(body[key]["subtext"], str)
        assert body[key]["subtext"], f"card `{key}` subtext is empty"

    # Drafts: 1 ned + 2 cycle = 3. Oldest is 5d → subtext kicks the
    # "Send today" branch.
    assert body["drafts"]["count"] == 3
    assert "Send today" in body["drafts"]["subtext"]
    assert body["drafts"]["oldest_days"] >= 4

    # Reports: 1 task >= 80 readiness.
    assert body["reports"]["count"] == 1
    assert body["reports"]["subtext"] == "All ≥80% · Commit now"

    # Pulse: 2 risk + 1 opportunity → 3 total; "2 critical · 1 opportunities".
    assert body["pulse"]["count"] == 3
    assert body["pulse"]["critical"] == 2
    assert body["pulse"]["opportunities"] == 1
    assert "critical" in body["pulse"]["subtext"]
    assert "opportunit" in body["pulse"]["subtext"]

    # Questions: 2 open. Phase I.5 (2026-05-27) — these 2 fixture rows
    # have no `asker_role` / no `asked_by_account_id`, so they fall to
    # the conservative-default team bucket per I.5 E2=a. Subtext is
    # now the decomposition, not "Awaiting clarification".
    assert body["questions"]["count"] == 2
    assert body["questions"]["subtext"] == "2 from team"
    assert body["questions"]["decomposition"] == {"board": 0, "ceo": 0, "team": 2}

    # Events: hardcoded 0 + empty state.
    assert body["events"]["count"] == 0
    assert body["events"]["subtext"] == "No events scheduled"


# ── T4. Questions card does NOT pre-wire I.5 role decomposition ──
def _strip_py_strings_and_comments(src: str) -> str:
    """Strip Python triple-quoted strings + `#` line comments so the
    forbidden-token scan only inspects EXECUTABLE code (not docstrings
    that document what the OUT_OF_SCOPE forbids)."""
    # Drop triple-double-quoted blocks (docstrings).
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    # Drop triple-single-quoted blocks.
    src = re.sub(r"'''[\s\S]*?'''", "", src)
    # Drop `# …` line comments.
    src = re.sub(r"#[^\n]*", "", src)
    return src


def test_i2_questions_card_uses_asker_role_decomposition_post_i5():
    """Phase I.2 originally locked OUT asker-role decomposition (Card 4
    was count-only with subtext "Awaiting clarification"). Phase I.5
    (2026-05-27) LANDED the decomposition — this guard now flips from
    negative ('decomposition must NOT appear') to positive ('the
    contract IS present and matches the I.5 shape').

    Institutional memory: the invariant's intent has evolved. I.5
    decided 2026-05-27 (E6=confirm) that this test rewrite is part of
    the I.5 dispatch — the I.2 guard kept us honest mid-flight; I.5
    locks the positive contract going forward.

    The positive guard asserts (against `routers/company_home.py`):
      • A `QuestionsDecomposition` shape with `board / ceo / team` fields
      • The aggregation queries `db.cycle_questions.aggregate` over
        `asker_role` (NOT a simple count_documents call)
      • Subtext formatting comes from
        `services.open_questions.asker_role_map.format_decomposition_subtext`
      • The old count-only subtext literal "Awaiting clarification" is
        GONE from the router source (replaced by formatter call)
    """
    src = _read(ROUTER)
    src_code = _strip_py_strings_and_comments(src)

    # Positive: decomposition model + aggregation present
    assert "class QuestionsDecomposition" in src, (
        "I.5 must expose the QuestionsDecomposition Pydantic model."
    )
    assert "decomposition" in src_code, (
        "I.5 router must wire `decomposition` into the questions card."
    )
    assert ".aggregate(" in src_code, (
        "I.5 must use Mongo `aggregate` to group by asker_role — a "
        "simple count_documents does not yield the bucket split."
    )
    assert "asker_role" in src_code, (
        "I.5 must reference `asker_role` in the company_home router."
    )

    # Negative regression: the old "Awaiting clarification" literal
    # must not survive — its replacement is the decomposition string.
    assert "Awaiting clarification" not in src, (
        "I.5 should remove the count-only `Awaiting clarification` "
        "subtext — it was the I.2 placeholder. Decomposition replaces it."
    )

    # Frontend: CompanyHome reads subtext as a free-form string, so
    # we don't need to assert the bucket labels are in JSX. We DO
    # confirm the surface still renders a subtext element (DOM
    # contract preserved).
    fe = _read(COMPANY_HOME)
    assert "company-home-attention-${card.id}-subtext" in fe \
        or "company-home-attention-" in fe, (
        "CompanyHome.jsx subtext data-testid pattern must remain — "
        "the new I.5 subtext flows through the same element."
    )


# ── T5. Events card never falls back to tasks collection ────────
# This guard was originally written when _build_events() returned
# a hardcoded empty state in I.2. Post-I.4.a (2026-05-27) the helper
# queries the new `events` collection. The negative invariant
# (`tasks` collection MUST NOT be used as an events source) is what
# we still want to enforce — that was the OUT_OF_SCOPE locked in
# both I.2 AND I.4.a briefs.
def test_i2_events_card_never_falls_back_to_tasks_collection():
    src = _read(ROUTER)
    # The empty-state string survives somewhere (used when events
    # collection has no rows in the 14-day window).
    assert "No events scheduled" in src
    stripped = _strip_py_strings_and_comments(src)
    # Match the I.4.a helper signature (takes a cid param). Old
    # signature was `_build_events()` (no args).
    m = re.search(
        r"def _build_events\([^)]*\)[\s\S]*?return CardEvents\(",
        stripped,
    )
    assert m, "_build_events function not found (after comment strip)"
    body = m.group(0)
    # The executable body must NOT read from the tasks collection.
    for f in ("final_due_date", "tasks.find_one", "db.tasks", "tasks.aggregate"):
        assert f not in body, (
            f"_build_events must NOT touch `{f}` — tasks are NOT an "
            "events source. Locked OUT in both the I.2 and I.4.a briefs."
        )


# ═════════════════════════════════════════════════════════════════
# Frontend wire tests
# ═════════════════════════════════════════════════════════════════

# ── T6. Frontend fires GETs to both endpoints ────────────────────
def test_i2_frontend_fetches_both_endpoints():
    src = _read(COMPANY_HOME)
    assert 'from "@/lib/api"' in src, "CompanyHome must import the api client"
    assert "/me/company-home/readiness" in src, (
        "CompanyHome must fetch readiness."
    )
    assert "/me/company-home/attention" in src, (
        "CompanyHome must fetch attention."
    )


# ── T7. Readiness testid renamed to canonical I.2 form ───────────
def test_i2_readiness_strip_carries_canonical_testid():
    src = _read(COMPANY_HOME)
    assert 'data-testid="company-home-readiness"' in src
    # The value child keeps its testid.
    assert 'data-testid="company-home-readiness-value"' in src


# ── T8. AttentionCard renders live count + subtext bindings ──────
def test_i2_attention_card_renders_live_count_and_subtext():
    src = _read(COMPANY_HOME)
    # The card receives a `data` prop (live API row).
    assert "function AttentionCard({ card, data, onOpen })" in src
    # The count expression reads `data.count`.
    assert "data?.count" in src or "data?.[\"count\"]" in src
    # The subtext expression reads `data.subtext`.
    assert "data?.subtext" in src or "data?.[\"subtext\"]" in src
    # The main render still mounts every card with `data` bound.
    assert "attention?.[card.id]" in src


# ── T9. Click routing uses context-filtered surface routes ──────
def test_i2_click_routing_uses_context_filtered_routes_per_card():
    src = _read(COMPANY_HOME)
    # The route resolver function.
    assert "_routeForCard" in src
    # Each card's route shape (verbatim).
    # Phase I.4.a (2026-05-27): events card now routes to /app/events
    # (was no-op in I.2). The 4 other markers are unchanged.
    for marker in (
        "/app/work-studio?tab=drafts&context_id=",
        "/app/task-manager?filter=ready_to_compile&context_id=",
        "/app/pulse?context_id=",
        "/app/questions?status=open&context_id=",
        "/app/events?context_id=",
    ):
        assert marker in src, f"missing route marker `{marker}`"
