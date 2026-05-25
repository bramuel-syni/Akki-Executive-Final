"""J3 (Stages 4-5) — Backend behavior tests.

Spec ref: `AKKI_ONBOARDING_SPEC.md` v1.1 §3 Stages 4-5 + ratified
gaps G24, G25, G27, G28. Folded into the broader J3 chunk per
orchestrator brief: *"Build the upload-door experience per spec §3
Stage 4. Use the existing ClamAV + Shield pipeline."* and *"Build
the Trust Center introduction tour per spec §3 Stage 5 + ratified
G27/G28."*

Behavior tests, NOT source-string tests (closeout §5.8):

  J3.1 — Upload-door routes through the existing ClamAV + Shield
         pipeline. POST a real upload, then GET back the doc + audit
         row. The integration confirms the existing pipeline ran.
         The `first_session.first_doc_uploaded` flag MUST flip.
  J3.2 — Oversized upload returns G25 verbatim 413.
  J3.3 — Empty (text-less) upload returns G24 verbatim 400.
  J3.4 — Stage 5 tour gate: `trust_center_tour.show == true` only
         when the user has uploaded ≥ 1 doc AND has NOT yet
         dismissed the tour.
  J3.5 — POST `/onboarding-status/trust-center-tour/dismiss` flips
         `first_session.trust_center_introduced = true` and the
         next GET on onboarding-status shows `show: false`.
"""
from __future__ import annotations

import io
import os
import sys
import uuid
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

import core as core_mod
from server import app


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


async def _register(c: httpx.AsyncClient, prefix: str):
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    r = await c.post("/api/auth/register", json={
        "email": email, "password": "Password123!@#",
        "name": f"{prefix.title()} Tester",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    return body["access_token"], body["account"], body["contexts"][0]["id"]


# ── J3.1 — first_doc_uploaded flag flips on successful upload ───────
@pytest.mark.asyncio
async def test_j3_1_first_doc_uploaded_flag_flips_on_successful_upload():
    """A real upload through the existing ClamAV + Shield pipeline
    must flip `accounts.{id}.first_session.first_doc_uploaded` to
    True. This is the spec §3 Stage 4 gate that turns on the Stage
    5 Trust Center tour."""
    async with _client() as c:
        token, account, ctx_id = await _register(c, "j3-fdu")
        h = {"Authorization": f"Bearer {token}"}
        # Pre-condition: flag is False.
        acct_pre = await core_mod.db.accounts.find_one(
            {"id": account["id"]}, {"_id": 0, "first_session": 1},
        )
        assert not (acct_pre.get("first_session") or {}).get("first_doc_uploaded")
        # Upload a small valid text file.
        body = b"Hello board. Margin trend up 4%. Next steps: review Q3 capital plan."
        files = {
            "file": ("hello.txt", io.BytesIO(body), "text/plain"),
        }
        r = await c.post(
            f"/api/contexts/{ctx_id}/documents",
            files=files, headers=h,
        )
        assert r.status_code == 200, r.text
        # Post-condition: flag flipped.
        acct_post = await core_mod.db.accounts.find_one(
            {"id": account["id"]}, {"_id": 0, "first_session": 1},
        )
        fs = acct_post.get("first_session") or {}
        assert fs.get("first_doc_uploaded") is True, fs
        assert fs.get("first_doc_uploaded_at"), fs
        # Audit chain — document.uploaded row exists.
        audit = await core_mod.db.audit_log.find_one(
            {"action": "document.uploaded", "account_id": account["id"]},
            {"_id": 0},
        )
        assert audit is not None


# ── J3.2 — G25 verbatim oversized 413 ───────────────────────────────
@pytest.mark.asyncio
async def test_j3_2_g25_oversized_upload_returns_verbatim_413():
    """Spec §3 Stage 4 (ratified G25): >50 MB → 413 with verbatim
    'That file is larger than 50 MB. Please split it or upload a
    smaller version.'"""
    async with _client() as c:
        token, account, ctx_id = await _register(c, "j3-big")
        h = {"Authorization": f"Bearer {token}"}
        # 51 MB synthetic payload — just over the limit.
        big = b"x" * (51 * 1024 * 1024)
        files = {"file": ("big.txt", io.BytesIO(big), "text/plain")}
        r = await c.post(
            f"/api/contexts/{ctx_id}/documents",
            files=files, headers=h,
        )
        assert r.status_code == 413, r.text
        assert r.json()["detail"] == (
            "That file is larger than 50 MB. Please split it or upload a smaller version."
        ), r.json()


# ── J3.3 — G24 verbatim empty-doc 400 ───────────────────────────────
@pytest.mark.asyncio
async def test_j3_3_g24_empty_text_upload_returns_verbatim_400():
    """Spec §3 Stage 4 (ratified G24): empty extractable text → 400
    with verbatim 'That file doesn't have any text we can read.
    Please upload a different file.'"""
    async with _client() as c:
        token, account, ctx_id = await _register(c, "j3-empty")
        h = {"Authorization": f"Bearer {token}"}
        # Whitespace-only file — extracts to empty text.
        files = {
            "file": ("blank.txt", io.BytesIO(b"   \n\n   \t  \n"), "text/plain"),
        }
        r = await c.post(
            f"/api/contexts/{ctx_id}/documents",
            files=files, headers=h,
        )
        assert r.status_code == 400, r.text
        assert r.json()["detail"] == (
            "That file doesn't have any text we can read. Please upload a different file."
        ), r.json()


# ── J3.4 — Stage 5 tour gate ────────────────────────────────────────
@pytest.mark.asyncio
async def test_j3_4_trust_center_tour_show_gates_on_first_doc_uploaded():
    """`trust_center_tour.show` is True only AFTER the user has
    uploaded at least one document. The Stage 4 → Stage 5 dependency
    is the spec contract."""
    async with _client() as c:
        token, account, ctx_id = await _register(c, "j3-gate")
        h = {"Authorization": f"Bearer {token}"}
        # Pre-upload: show must be False.
        r1 = await c.get("/api/users/me/onboarding-status", headers=h)
        assert r1.status_code == 200, r1.text
        tour1 = r1.json().get("trust_center_tour") or {}
        assert tour1.get("show") is False, tour1
        # Upload one doc to flip the flag.
        files = {"file": ("hi.txt", io.BytesIO(b"Hello board."), "text/plain")}
        r2 = await c.post(
            f"/api/contexts/{ctx_id}/documents",
            files=files, headers=h,
        )
        assert r2.status_code == 200, r2.text
        # Post-upload: show must flip to True.
        r3 = await c.get("/api/users/me/onboarding-status", headers=h)
        tour3 = r3.json().get("trust_center_tour") or {}
        assert tour3.get("show") is True, tour3
        assert tour3.get("first_doc_uploaded") is True
        assert tour3.get("trust_center_introduced") is False


# ── J3.5 — dismiss flips trust_center_introduced ────────────────────
@pytest.mark.asyncio
async def test_j3_5_dismiss_tour_flips_flag_and_hides_tour_on_next_visit():
    """POST `/onboarding-status/trust-center-tour/dismiss` flips
    `first_session.trust_center_introduced = true` (idempotent).
    Subsequent GET shows `trust_center_tour.show: false`."""
    async with _client() as c:
        token, account, ctx_id = await _register(c, "j3-dism")
        h = {"Authorization": f"Bearer {token}"}
        # Upload + ensure tour visible.
        files = {"file": ("hi.txt", io.BytesIO(b"Hello."), "text/plain")}
        await c.post(
            f"/api/contexts/{ctx_id}/documents",
            files=files, headers=h,
        )
        # Confirm visible.
        r_pre = await c.get("/api/users/me/onboarding-status", headers=h)
        assert (r_pre.json().get("trust_center_tour") or {}).get("show") is True
        # Dismiss.
        r_dis = await c.post(
            "/api/users/me/onboarding-status/trust-center-tour/dismiss",
            headers=h,
        )
        assert r_dis.status_code == 200, r_dis.text
        tour_now = r_dis.json().get("trust_center_tour") or {}
        assert tour_now.get("show") is False
        assert tour_now.get("trust_center_introduced") is True
        # Idempotent — second dismiss is fine.
        r_dis2 = await c.post(
            "/api/users/me/onboarding-status/trust-center-tour/dismiss",
            headers=h,
        )
        assert r_dis2.status_code == 200, r_dis2.text
        # Persistence on next GET.
        r_post = await c.get("/api/users/me/onboarding-status", headers=h)
        tour_post = r_post.json().get("trust_center_tour") or {}
        assert tour_post.get("show") is False
        # DB-level confirmation.
        acct = await core_mod.db.accounts.find_one(
            {"id": account["id"]}, {"_id": 0, "first_session": 1},
        )
        fs = acct.get("first_session") or {}
        assert fs.get("trust_center_introduced") is True
        assert fs.get("trust_center_introduced_at")
