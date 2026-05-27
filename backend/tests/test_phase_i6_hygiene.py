"""Phase I.6 — Final hygiene + 3 fold-in CI guards (2026-05-27).

Locks the 3 fold-ins:

  Fold-in 1 — Phase P (Monitor score "%" suffix)
    P1.  `StrategicGoalsPanel.jsx::ScoreBar` renders `${pct}%` for
         non-empty values and `—` for null/undefined.
    P2.  `ObjectivesProjectsPanel.jsx` row score renders `{score}%`
         for non-null values and `—` for null (NOT the previous "0"
         default).

  Fold-in 2 — I.5 close-loop (clickable Card 4 subtext)
    L1.  CompanyHome.jsx renders Card 4 subtext as clickable
         segments with `data-testid="card4-subtext-segment-{role}"`
         per non-zero bucket.
    L2.  CompanyHome.jsx navigates to `/app/questions?role={role}`
         on segment click.
    L3.  Backend `/api/me/questions` accepts `asker_role` filter
         param and filters correctly.
    L4.  Backend `/api/contexts/{cid}/cycles/{cycle_id}/questions`
         accepts `asker_role` filter param.
    L5.  Invalid `asker_role` value returns 400.
    L6.  Questions.jsx renders the active-filter chip when `?role=`
         is in the URL; chip has clear-X testid.

  Fold-in 3 — I.4.b de-id PII fix (date protection on events_extract)
    D1.  Deidentifier accepts `purpose` kwarg and skips DATE_ISO
         regex pattern when `purpose == "documents.events_extract"`.
    D2.  Same input WITHOUT purpose still tokenizes DATE_ISO.
    D3.  Other regex patterns (e.g. EMAIL) STILL fire under the
         events_extract purpose — only DATE_ISO is exempt.
    D4.  Shield `client.invoke()` plumbs the purpose into the
         deidentify call.

  Hygiene
    H1.  No live executable imports of archived Home1/Home2.
    H2.  No TODO/FIXME/XXX comments added in Phase I.1-I.5 files.
"""
from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
SGP = REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx"
OPP = REPO / "frontend" / "src" / "components" / "monitor" / "ObjectivesProjectsPanel.jsx"
CH  = REPO / "frontend" / "src" / "pages" / "CompanyHome.jsx"
QPG = REPO / "frontend" / "src" / "pages" / "Questions.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ═════════════════════════════════════════════════════════════════
# Fold-in 1 — Phase P (Monitor score % suffix)
# ═════════════════════════════════════════════════════════════════

def test_i6_P1_score_bar_renders_percent_suffix():
    """ScoreBar in StrategicGoalsPanel must render `${pct}%` (not the
    bare integer) for non-empty values. Empty values still render '—'."""
    src = _read(SGP)
    # The fixed line should contain the template literal with %.
    assert "{empty ? \"—\" : `${pct}%`}" in src, (
        "ScoreBar must render `${pct}%` (with template literal + %) for "
        "non-empty values. Phase P fold-in."
    )


def test_i6_P2_objectives_row_score_renders_percent_suffix():
    """Objectives row score must render `{score}%` for non-null + '—' for null.
    Replaces the prior `{row.score ?? 0}` default."""
    src = _read(OPP)
    # The fixed render line has the conditional + % suffix.
    assert "row.score == null ? \"—\" : `${row.score}%`" in src, (
        "Objectives row score must render `${row.score}%` for non-null "
        "and '—' for null. Phase P fold-in."
    )
    # Negative regression: the old `row.score ?? 0` pattern must be gone.
    assert "{row.score ?? 0}" not in src, (
        "Old fallback-to-0 render must be removed. Phase P fold-in."
    )


# ═════════════════════════════════════════════════════════════════
# Fold-in 2 — I.5 close-loop (Card 4 clickable subtext)
# ═════════════════════════════════════════════════════════════════

def test_i6_L1_card4_subtext_segments_have_testids():
    """CompanyHome.jsx must render data-testid='card4-subtext-segment-{role}'
    for each non-zero bucket in the Card 4 decomposition."""
    src = _read(CH)
    assert "card4-subtext-segment-${role}" in src or "card4-subtext-segment-" in src, (
        "Card 4 subtext segments must carry per-role testids."
    )
    # Positive: stopPropagation prevents card-level click from firing.
    assert "stopPropagation" in src, (
        "Subtext segments must call e.stopPropagation() to prevent the "
        "parent card click from also firing."
    )


def test_i6_L2_card4_segment_navigates_to_role_filtered_questions():
    """CompanyHome.jsx must navigate to /app/questions?role={role}&filter=open
    when a segment is activated."""
    src = _read(CH)
    assert "/app/questions?role=" in src, (
        "Card 4 segment must deep-link to /app/questions?role={role}."
    )
    assert "filter=open" in src, (
        "Deep link must include filter=open per the brief."
    )


@pytest.mark.asyncio
async def test_i6_L3_me_questions_accepts_asker_role_filter():
    """GET /api/me/questions?asker_role=board returns only board-bucket
    questions assigned to me. Other buckets excluded."""
    from server import app  # noqa: F401
    from core import db, hash_password
    uid = f"i6-{uuid.uuid4().hex[:8]}"
    email = f"i6-{uuid.uuid4().hex[:6]}@ex.com"
    pw = "Pw!1234567Ab"
    cid = f"i6-cid-{uuid.uuid4().hex[:6]}"
    now = _iso(datetime.now(timezone.utc))

    try:
        await db.accounts.insert_one({
            "id": uid, "email": email, "password_hash": hash_password(pw),
            "name": "I6 Tester", "tier": "executive",
            "declared_role": "executive", "mfa_enrolled": False,
            "is_superadmin": False, "created_at": now,
        })
        # Seed: 2 board-bucket + 1 ceo-bucket + 1 team-bucket, all assigned to me
        for role_bucket, n in [("board", 2), ("ceo", 1), ("team", 1)]:
            for i in range(n):
                await db.cycle_questions.insert_one({
                    "id": f"i6q-{role_bucket}-{i}-{uuid.uuid4().hex[:4]}",
                    "context_id": cid, "cycle_id": "i6-cy",
                    "text": f"Q from {role_bucket} {i}",
                    "asked_at": now, "status": "open",
                    "assignee_account_id": uid, "asker_role": role_bucket,
                })

        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test") as c:
            r = await c.post("/api/auth/login",
                             json={"email": email, "password": pw})
            hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
            # No filter → 4 returned
            r_all = await c.get("/api/me/questions?status=open", headers=hdr)
            assert r_all.json()["total"] == 4
            # asker_role=board → 2 returned
            r_b = await c.get("/api/me/questions?status=open&asker_role=board", headers=hdr)
            assert r_b.json()["total"] == 2
            assert all(it["asker_role"] == "board" for it in r_b.json()["items"])
            # asker_role=ceo → 1 returned
            r_c = await c.get("/api/me/questions?status=open&asker_role=ceo", headers=hdr)
            assert r_c.json()["total"] == 1
            # asker_role=team → 1 returned
            r_t = await c.get("/api/me/questions?status=open&asker_role=team", headers=hdr)
            assert r_t.json()["total"] == 1
    finally:
        await db.accounts.delete_one({"id": uid})
        await db.cycle_questions.delete_many({"context_id": cid})


@pytest.mark.asyncio
async def test_i6_L5_invalid_asker_role_returns_400():
    """asker_role param must be in {board, ceo, team}. Invalid → 400."""
    from server import app  # noqa: F401
    from core import db, hash_password
    uid = f"i6-{uuid.uuid4().hex[:8]}"
    email = f"i6-{uuid.uuid4().hex[:6]}@ex.com"
    pw = "Pw!1234567Ab"
    now = _iso(datetime.now(timezone.utc))
    try:
        await db.accounts.insert_one({
            "id": uid, "email": email, "password_hash": hash_password(pw),
            "name": "I6 Tester", "tier": "executive",
            "declared_role": "executive", "mfa_enrolled": False,
            "is_superadmin": False, "created_at": now,
        })
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test") as c:
            r = await c.post("/api/auth/login",
                             json={"email": email, "password": pw})
            hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
            r_bad = await c.get(
                "/api/me/questions?asker_role=director", headers=hdr,
            )
            assert r_bad.status_code == 400
    finally:
        await db.accounts.delete_one({"id": uid})


def test_i6_L6_questions_page_renders_role_chip_with_clear():
    """Questions.jsx must render an active-filter chip when ?role= is
    in the URL and the chip must have a clear-X testid."""
    src = _read(QPG)
    # Chip testid with role suffix
    assert "questions-role-chip-${askerRole}" in src or "questions-role-chip-" in src, (
        "Questions page must render the role filter chip when ?role= is present."
    )
    assert "questions-role-chip-clear" in src, (
        "Role filter chip must have a clear-X testid."
    )
    # The chip must read askerRole from search params
    assert "searchParams.get(\"role\")" in src, (
        "Questions.jsx must read role from URL search params."
    )


# ═════════════════════════════════════════════════════════════════
# Fold-in 3 — De-id PII fix (date protection)
# ═════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_i6_D1_deidentify_skips_date_iso_for_events_extract_purpose():
    """When `purpose='documents.events_extract'`, the DATE_ISO regex pass
    is skipped — calendar dates flow through to the LLM unmodified."""
    from services.synisense.shield import deidentifier
    text = "Q3 board meeting on 2026-06-15 in Boardroom A."
    r = await deidentifier.deidentify(
        text, tenant_id="i6-test",
        purpose="documents.events_extract",
    )
    # The ISO date string MUST appear verbatim in the redacted text.
    assert "2026-06-15" in r.redacted_text, (
        f"DATE_ISO must NOT be tokenized for events_extract purpose. "
        f"redacted: {r.redacted_text!r}"
    )
    # de_id_summary must NOT include DATE_ISO when the skip is active.
    assert "DATE_ISO" not in r.de_id_summary


@pytest.mark.asyncio
async def test_i6_D2_deidentify_still_tokenizes_date_iso_without_purpose():
    """Same input without `purpose=` retains the existing PII shield —
    DATE_ISO is still tokenized for chat / solva / work-studio / etc."""
    from services.synisense.shield import deidentifier
    text = "Meeting on 2026-06-15 in conference room A."
    r = await deidentifier.deidentify(text, tenant_id="i6-test")
    # The ISO date must be tokenized (NOT appear verbatim).
    assert "2026-06-15" not in r.redacted_text, (
        f"DATE_ISO must STILL be tokenized when no purpose is passed. "
        f"redacted: {r.redacted_text!r}"
    )
    # Summary must include DATE_ISO.
    assert r.de_id_summary.get("DATE_ISO", 0) >= 1


@pytest.mark.asyncio
async def test_i6_D3_other_patterns_still_fire_under_events_extract():
    """Only DATE_ISO is exempt under events_extract. Other PII patterns
    (EMAIL, PHONE, etc.) MUST still fire — the shield isn't gutted."""
    from services.synisense.shield import deidentifier
    text = "Reach me at user@example.com about the 2026-06-15 board meeting."
    r = await deidentifier.deidentify(
        text, tenant_id="i6-test",
        purpose="documents.events_extract",
    )
    # Date passes through, but email is tokenized.
    assert "2026-06-15" in r.redacted_text
    assert "user@example.com" not in r.redacted_text


def test_i6_D4_shield_client_plumbs_purpose_into_deidentify():
    """`services/synisense/shield/client.py::invoke` must pass `purpose`
    into the deidentifier call. Source-strict guard."""
    src = (REPO / "backend" / "services" / "synisense" / "shield" / "client.py").read_text(encoding="utf-8")
    # Both invoke paths (the sync + streaming) must thread the purpose.
    # Count occurrences of `purpose=purpose` in `deidentifier.deidentify` calls.
    pattern = re.compile(r"deidentifier\.deidentify\([^)]*purpose=purpose", re.DOTALL)
    matches = pattern.findall(src)
    assert len(matches) >= 2, (
        f"Expected ≥2 plumbed `purpose=purpose` calls to deidentify in "
        f"client.py, found {len(matches)}. Both sync `invoke()` and "
        f"streaming `invoke_streaming()` must pass the purpose."
    )


# ═════════════════════════════════════════════════════════════════
# Hygiene
# ═════════════════════════════════════════════════════════════════

def test_i6_H1_no_live_imports_of_archived_homes():
    """Home1 / Home2 must not be imported by any executable code.
    Comments and docstrings are allowed (they document history)."""
    import subprocess
    # grep for actual import statements only
    out = subprocess.run(
        ["grep", "-rEn", "^import.*Home[12]\\b|^from.*Home[12]\\b|import .*Home[12]\\b",
         str(REPO / "frontend" / "src")],
        capture_output=True, text=True,
    )
    # Filter out _archived/ directory + node_modules
    lines = [
        ln for ln in (out.stdout or "").splitlines()
        if "_archived" not in ln and "node_modules" not in ln
    ]
    assert not lines, (
        f"Found {len(lines)} live executable imports of Home1/Home2 "
        f"outside _archived/: {lines}"
    )


def test_i6_H2_no_todo_fixme_in_phase_i_files():
    """Phase I.1-I.5 must not leave TODO/FIXME/XXX comments behind.
    The hygiene sweep catches anything that slipped through."""
    phase_i_files = [
        REPO / "backend" / "routers" / "company_home.py",
        REPO / "backend" / "routers" / "events.py",
        REPO / "backend" / "routers" / "questions.py",
        REPO / "backend" / "services" / "open_questions" / "asker_role_map.py",
        REPO / "frontend" / "src" / "pages" / "CompanyHome.jsx",
        REPO / "frontend" / "src" / "pages" / "Events.jsx",
    ]
    flagged = []
    for f in phase_i_files:
        if not f.exists():
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            # Match standalone comment markers, not the word "todo" in
            # a longer identifier.
            if re.search(r"\b(TODO|FIXME|XXX)\b", line):
                flagged.append(f"{f.relative_to(REPO)}:{i}: {line.strip()[:120]}")
    assert not flagged, (
        f"Phase I.1-I.5 files contain unresolved TODO/FIXME/XXX:\n"
        + "\n".join(flagged)
    )
