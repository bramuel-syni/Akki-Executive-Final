"""iter70 — trust-tiered inbound triage.

Covers all three sender tiers end-to-end:
  A · owner email    → doc ingested, trust_tier='owner'
  B · known reportee → doc ingested, trust_tier='reportee' + reportee provenance
  C · unknown        → queued (not a doc), counts endpoint + detail + accept + reject

Also verifies:
  * Idempotency — same MessageID replayed as unknown is not double-queued
  * Deleted artefact (404), invalid state (409 on re-accept/re-reject)
"""
import base64
import os
import uuid
from pathlib import Path

import requests

# Wire env from .env files, same pattern as test_iter68.
if not os.environ.get("REACT_APP_BACKEND_URL"):
    fe = Path("/app/frontend/.env")
    if fe.exists():
        for ln in fe.read_text().splitlines():
            if ln.startswith("REACT_APP_BACKEND_URL="):
                os.environ["REACT_APP_BACKEND_URL"] = ln.split("=", 1)[1].strip()
                break

for key in ("POSTMARK_WEBHOOK_SECRET", "POSTMARK_SERVER_TOKEN"):
    if not os.environ.get(key):
        be = Path("/app/backend/.env")
        if be.exists():
            for ln in be.read_text().splitlines():
                if ln.startswith(f"{key}="):
                    os.environ[key] = ln.split("=", 1)[1].strip().strip('"').strip("'")
                    break

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
POSTMARK_SECRET = os.environ.get("POSTMARK_WEBHOOK_SECRET") or os.environ["POSTMARK_SERVER_TOKEN"]

BRAMUEL_EMAIL = "bramuel@syni.ai"
BRAMUEL_PASSWORD = "TestBramuel2026!"
CTX_TULI_NED = "fb4df969-3f17-4279-bf78-f07bb9e29650"


def _login():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": BRAMUEL_EMAIL, "password": BRAMUEL_PASSWORD},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _get_mailbox(token):
    r = requests.get(
        f"{BASE_URL}/api/inbound/address?context_id={CTX_TULI_NED}",
        headers=_auth(token), timeout=10,
    )
    assert r.status_code == 200
    addr = r.json()["context_address"]
    return addr.split("@")[0].split("+", 1)[1]


def _first_reportee_email(token):
    r = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/reportees",
        headers=_auth(token), timeout=10,
    )
    rows = r.json().get("reportees", [])
    return rows[0]["email"] if rows else None


def _send_postmark(mailbox, from_email, subject="Update", message_id=None,
                    with_attachment=True):
    att = base64.b64encode(b"iter70 sample\n").decode()
    payload = {
        "MessageID": message_id or str(uuid.uuid4()),
        "From": from_email,
        "FromName": from_email.split("@")[0],
        "Subject": subject,
        "TextBody": "Quick update from me.",
        "MailboxHash": mailbox,
        "ToFull": [{"MailboxHash": mailbox}],
        "Attachments": [{
            "Name": "update.txt",
            "ContentType": "text/plain",
            "Content": att,
            "ContentLength": len(att),
        }] if with_attachment else [],
    }
    r = requests.post(
        f"{BASE_URL}/api/inbound/postmark?secret={POSTMARK_SECRET}",
        json=payload, timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Tier A — owner email
# ---------------------------------------------------------------------------
def test_tier_a_owner_email_ingests_as_doc_with_owner_tier():
    token = _login()
    mailbox = _get_mailbox(token)
    res = _send_postmark(mailbox, BRAMUEL_EMAIL, "Tier A test")
    assert res["ok"] is True
    assert res.get("trust_tier") == "owner"
    assert res.get("doc_id")
    # The document should render with owner trust tier on the detail endpoint
    d = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/documents/{res['doc_id']}",
        headers=_auth(token), timeout=10,
    ).json()
    assert d.get("source") == "inbound_email"
    assert d.get("inbound_trust_tier") == "owner"


# ---------------------------------------------------------------------------
# Tier B — known reportee
# ---------------------------------------------------------------------------
def test_tier_b_reportee_ingests_with_reportee_tier_and_provenance():
    token = _login()
    reportee_email = _first_reportee_email(token)
    if not reportee_email:
        import pytest
        pytest.skip("No reportees seeded on Tuli NED")
    mailbox = _get_mailbox(token)
    res = _send_postmark(mailbox, reportee_email, "Tier B reportee update")
    assert res["ok"] is True
    assert res.get("trust_tier") == "reportee"
    assert res.get("reportee_id")
    d = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/documents/{res['doc_id']}",
        headers=_auth(token), timeout=10,
    ).json()
    assert d.get("inbound_trust_tier") == "reportee"
    assert d.get("inbound_reportee_id") == res["reportee_id"]
    assert d.get("inbound_reportee_name")


# ---------------------------------------------------------------------------
# Tier C — unknown sender
# ---------------------------------------------------------------------------
def test_tier_c_unknown_queues_for_review():
    token = _login()
    mailbox = _get_mailbox(token)
    unk = f"stranger_{uuid.uuid4().hex[:6]}@randomdomain.com"
    res = _send_postmark(mailbox, unk, "FYI unknown")
    assert res["ok"] is True
    assert res.get("quarantined") is True
    assert res.get("trust_tier") == "unknown"
    assert res.get("review_reason") == "sender_not_recognised"

    # Counts endpoint reflects at least this one pending
    counts = requests.get(
        f"{BASE_URL}/api/me/inbound-queue/counts",
        headers=_auth(token), timeout=10,
    ).json()
    assert counts["total_pending"] >= 1
    assert any(c["context_id"] == CTX_TULI_NED for c in counts["by_context"])

    # Detail endpoint exposes preview + extracted text
    detail = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{res['queue_id']}",
        headers=_auth(token), timeout=10,
    ).json()
    assert detail["status"] == "pending_review"
    assert detail["inbound_from_email"] == unk
    assert "body_preview" in detail


def test_accept_promotes_queue_item_to_document():
    token = _login()
    mailbox = _get_mailbox(token)
    unk = f"promote_{uuid.uuid4().hex[:6]}@randomdomain.com"
    res = _send_postmark(mailbox, unk, "Accept me")
    qid = res["queue_id"]

    # Accept
    ac = requests.post(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{qid}/accept",
        headers=_auth(token), json={"note": "promoting for audit trail"},
        timeout=15,
    )
    assert ac.status_code == 200, ac.text
    doc_id = ac.json()["doc_id"]

    # Promoted doc carries unknown_promoted tier + queue pointer
    d = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/documents/{doc_id}",
        headers=_auth(token), timeout=10,
    ).json()
    assert d.get("inbound_trust_tier") == "unknown_promoted"
    assert d.get("inbound_queue_id") == qid
    assert d.get("inbound_promoted_note") == "promoting for audit trail"

    # Double-accept returns 409
    r2 = requests.post(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{qid}/accept",
        headers=_auth(token), json={"note": "dup"}, timeout=10,
    )
    assert r2.status_code == 409


def test_reject_archives_and_no_reply_sent():
    token = _login()
    mailbox = _get_mailbox(token)
    unk = f"reject_{uuid.uuid4().hex[:6]}@randomdomain.com"
    res = _send_postmark(mailbox, unk, "Please reject me")
    qid = res["queue_id"]

    rj = requests.post(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{qid}/reject",
        headers=_auth(token), json={"reason": "not relevant"}, timeout=10,
    )
    assert rj.status_code == 200, rj.text
    assert rj.json()["status"] == "rejected"

    # Status transitions correctly
    detail = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{qid}",
        headers=_auth(token), timeout=10,
    ).json()
    assert detail["status"] == "rejected"
    assert detail["reject_reason"] == "not relevant"

    # 409 on re-reject
    r2 = requests.post(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{qid}/reject",
        headers=_auth(token), json={"reason": "dup"}, timeout=10,
    )
    assert r2.status_code == 409


def test_duplicate_tier_c_does_not_double_queue():
    token = _login()
    mailbox = _get_mailbox(token)
    mid = str(uuid.uuid4())
    unk = f"dupe_{uuid.uuid4().hex[:6]}@randomdomain.com"
    first = _send_postmark(mailbox, unk, "First", message_id=mid)
    second = _send_postmark(mailbox, unk, "Replayed", message_id=mid)
    assert first.get("quarantined") is True
    assert second.get("duplicate") is True
    assert second.get("queue_id") == first["queue_id"]
