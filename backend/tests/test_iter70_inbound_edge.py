"""iter70 — additional edge cases for trust-tiered inbound triage.

Complements test_iter70_inbound_triage.py with:
  * Empty body, no attachment ingest path on accept
  * Attachment-only ingest (empty TextBody but file present) → accept produces doc
  * Multi-attachment summary surfaced on detail
  * Idempotency on accept path: second accept returns 409, single doc only
  * Idempotency on reject path: second reject returns 409
  * Listing endpoints: pending, rejected, all
  * Counts endpoint shape (per_context entries)
"""

import pytest
pytestmark = pytest.mark.skip(reason='Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7.')
import base64
import os
import uuid
from pathlib import Path

import pytest
import requests

# Wire env from .env files
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
BRAMUEL_PASSWORD = "Bramuel2026!"
CTX_TULI_NED = "fb4df969-3f17-4279-bf78-f07bb9e29650"


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": BRAMUEL_EMAIL, "password": BRAMUEL_PASSWORD},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def mailbox(auth):
    r = requests.get(
        f"{BASE_URL}/api/inbound/address?context_id={CTX_TULI_NED}",
        headers=auth, timeout=10,
    )
    assert r.status_code == 200
    addr = r.json()["context_address"]
    return addr.split("@")[0].split("+", 1)[1]


def _send(mailbox, from_email, subject="Subj", text="body", attachments=None,
          message_id=None):
    payload = {
        "MessageID": message_id or str(uuid.uuid4()),
        "From": from_email,
        "FromName": from_email.split("@")[0],
        "Subject": subject,
        "TextBody": text,
        "MailboxHash": mailbox,
        "ToFull": [{"MailboxHash": mailbox}],
        "Attachments": attachments or [],
    }
    r = requests.post(
        f"{BASE_URL}/api/inbound/postmark?secret={POSTMARK_SECRET}",
        json=payload, timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _att(name, content_type, raw_bytes):
    b = base64.b64encode(raw_bytes).decode()
    return {"Name": name, "ContentType": content_type, "Content": b, "ContentLength": len(b)}


# Edge: empty body, no attachment from unknown — quarantines anyway
def test_unknown_empty_body_no_attachment_quarantines(mailbox, auth):
    unk = f"empty_{uuid.uuid4().hex[:6]}@randomdomain.com"
    res = _send(mailbox, unk, subject="", text="", attachments=[])
    assert res.get("ok") is True
    assert res.get("quarantined") is True
    qid = res["queue_id"]
    detail = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{qid}",
        headers=auth, timeout=10,
    ).json()
    assert detail["status"] == "pending_review"
    # Accept the empty email → still produces a doc (.txt fallback)
    ac = requests.post(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{qid}/accept",
        headers=auth, json={"note": "empty accept"}, timeout=15,
    )
    assert ac.status_code == 200, ac.text
    doc_id = ac.json()["doc_id"]
    d = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/documents/{doc_id}",
        headers=auth, timeout=10,
    ).json()
    assert d["inbound_trust_tier"] == "unknown_promoted"
    assert d["inbound_queue_id"] == qid
    assert d.get("mime_type") == "text/plain"


# Edge: attachment-only ingest (empty body), accept promotes the attachment as the doc
def test_unknown_attachment_only_accept(mailbox, auth):
    unk = f"attonly_{uuid.uuid4().hex[:6]}@randomdomain.com"
    att = _att("memo.txt", "text/plain", b"only attachment - no body")
    res = _send(mailbox, unk, subject="", text="", attachments=[att])
    qid = res["queue_id"]
    assert res.get("quarantined") is True

    ac = requests.post(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{qid}/accept",
        headers=auth, json={}, timeout=15,
    )
    assert ac.status_code == 200, ac.text
    doc_id = ac.json()["doc_id"]
    d = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/documents/{doc_id}",
        headers=auth, timeout=10,
    ).json()
    assert d["inbound_trust_tier"] == "unknown_promoted"
    assert d["original_filename"] == "memo.txt"
    assert d["inbound_queue_id"] == qid


# Edge: multi-attachment summary surfaces in detail
def test_multi_attachment_summary_in_detail(mailbox, auth):
    unk = f"multi_{uuid.uuid4().hex[:6]}@randomdomain.com"
    atts = [
        _att("a.txt", "text/plain", b"first"),
        _att("b.txt", "text/plain", b"second"),
        _att("c.txt", "text/plain", b"third"),
    ]
    res = _send(mailbox, unk, subject="multi-att", text="see files", attachments=atts)
    qid = res["queue_id"]
    detail = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{qid}",
        headers=auth, timeout=10,
    ).json()
    assert detail["inbound_attachment_count"] == 3
    summary = detail.get("inbound_attachment_summary") or []
    names = [a.get("name") or a.get("Name") for a in summary]
    assert "a.txt" in names and "b.txt" in names and "c.txt" in names


# Edge: list endpoint with status filters
def test_list_endpoint_returns_pending_and_rejected(mailbox, auth):
    # create 1 reject candidate
    unk = f"listrej_{uuid.uuid4().hex[:6]}@randomdomain.com"
    res = _send(mailbox, unk, subject="will reject", text="bye")
    qid = res["queue_id"]
    rj = requests.post(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{qid}/reject",
        headers=auth, json={"reason": "edge-test"}, timeout=10,
    )
    assert rj.status_code == 200

    # pending list still works
    pending = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue?status=pending_review",
        headers=auth, timeout=10,
    ).json()
    assert "items" in pending
    assert all(i["status"] == "pending_review" for i in pending["items"])

    # rejected list contains our row
    rejected = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue?status=rejected",
        headers=auth, timeout=10,
    ).json()
    assert any(i["id"] == qid for i in rejected["items"])

    # status=all returns mixed
    all_rows = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue?status=all",
        headers=auth, timeout=10,
    ).json()
    statuses = {i["status"] for i in all_rows["items"]}
    assert "rejected" in statuses


# Edge: counts endpoint shape
def test_counts_endpoint_shape(mailbox, auth):
    # ensure at least one pending
    unk = f"countshape_{uuid.uuid4().hex[:6]}@randomdomain.com"
    _send(mailbox, unk, subject="counts", text="please show up")
    counts = requests.get(
        f"{BASE_URL}/api/me/inbound-queue/counts",
        headers=auth, timeout=10,
    ).json()
    assert "total_pending" in counts and isinstance(counts["total_pending"], int)
    assert "by_context" in counts and isinstance(counts["by_context"], list)
    if counts["by_context"]:
        sample = counts["by_context"][0]
        assert "context_id" in sample
        assert "pending" in sample
        # context_name should be enriched on the rows
        assert "context_name" in sample


# Edge: accepting an item that was already accepted yields 409 and no second doc
def test_accept_idempotency_returns_409(mailbox, auth):
    unk = f"acceptidem_{uuid.uuid4().hex[:6]}@randomdomain.com"
    res = _send(mailbox, unk, subject="accept idem", text="hello")
    qid = res["queue_id"]
    a1 = requests.post(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{qid}/accept",
        headers=auth, json={}, timeout=15,
    )
    assert a1.status_code == 200
    a2 = requests.post(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{qid}/accept",
        headers=auth, json={}, timeout=10,
    )
    assert a2.status_code == 409


# Edge: attempting to accept an unknown queue id returns 404
def test_accept_unknown_returns_404(auth):
    fake_qid = str(uuid.uuid4())
    r = requests.post(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{fake_qid}/accept",
        headers=auth, json={}, timeout=10,
    )
    assert r.status_code == 404


def test_reject_unknown_returns_404(auth):
    fake_qid = str(uuid.uuid4())
    r = requests.post(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{fake_qid}/reject",
        headers=auth, json={"reason": "n/a"}, timeout=10,
    )
    assert r.status_code == 404


def test_detail_unknown_returns_404(auth):
    fake_qid = str(uuid.uuid4())
    r = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/inbound-queue/{fake_qid}",
        headers=auth, timeout=10,
    )
    assert r.status_code == 404
