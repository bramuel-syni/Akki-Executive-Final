"""iter34 backend tests:
  · POST /api/contexts/{cid}/shares with item_type='doc_summary'
  · PATCH /api/contexts/{cid}/documents/{did} with related_doc_id
  · POST /api/contexts/{cid}/documents/{did}/evolution-diff
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

CTX_ID = "2ceb9fde-a202-4891-adb1-ecf47dfe2258"  # Tuli CFO
DOC1   = "a90b82e3-3fa9-4a26-be0c-d63bdfc51909"  # already has akki_summary + linked to DOC2
DOC2   = "9f5ab479-abf2-4516-bc04-4f6dabb5557a"

EMAIL = "bramuel@syni.ai"
PWD   = "TestBramuel2026!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PWD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# --------------------------------------------------------------------------
# Module: shares router — doc_summary item_type
# --------------------------------------------------------------------------
class TestDocSummaryShare:
    def test_share_doc_summary_to_self_rejected(self, session):
        r = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/shares",
            json={
                "item_type": "doc_summary",
                "item_id": DOC1,
                "to_email": EMAIL,
                "delivery_method": "akki_notification",
            },
            timeout=20,
        )
        assert r.status_code == 400, r.text
        assert "yourself" in r.json().get("detail", "").lower()

    def test_share_doc_summary_no_summary_returns_404(self, session):
        # find a doc in the context that doesn't have akki_summary
        r = session.get(f"{BASE_URL}/api/contexts/{CTX_ID}/documents", timeout=20)
        assert r.status_code == 200
        docs = r.json() if isinstance(r.json(), list) else r.json().get("documents", [])
        target = None
        for d in docs:
            if d.get("id") in (DOC1, DOC2):
                continue
            # Fetch full doc (list endpoint may not include akki_summary)
            full = session.get(
                f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{d['id']}", timeout=20
            )
            if full.status_code == 200 and not (full.json().get("akki_summary") or {}).get("tldr"):
                target = d["id"]
                break
        if not target:
            pytest.skip("No doc without akki_summary found; cannot test 404 path")
        r = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/shares",
            json={
                "item_type": "doc_summary",
                "item_id": target,
                "to_email": "TEST_iter34@example.com",
                "delivery_method": "akki_notification",
            },
            timeout=20,
        )
        assert r.status_code == 404, r.text

    def test_share_doc_summary_via_notification_creates_mention(self, session):
        # share to admin@akki.ai -> resolves to AKKI account -> mention row
        r = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/shares",
            json={
                "item_type": "doc_summary",
                "item_id": DOC1,
                "to_email": "admin@akki.ai",
                "subject": "TEST_iter34 doc summary share",
                "message": "AKKI's read on this doc",
                "delivery_method": "akki_notification",
            },
            timeout=20,
        )
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert body.get("item_type") == "doc_summary"
        assert body.get("status") == "delivered"
        assert body.get("shared_with_email") == "admin@akki.ai"

    def test_share_doc_summary_email_delivery(self, session):
        r = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/shares",
            json={
                "item_type": "doc_summary",
                "item_id": DOC1,
                "to_email": "TEST_iter34_external@example.com",
                "delivery_method": "email",
            },
            timeout=30,
        )
        assert r.status_code in (200, 201), r.text
        assert r.json().get("delivery_method") == "email"


# --------------------------------------------------------------------------
# Module: documents router — PATCH related_doc_id (evolution chain)
# --------------------------------------------------------------------------
class TestEvolutionLink:
    def test_patch_self_link_rejected(self, session):
        r = session.patch(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{DOC1}",
            json={"related_doc_id": DOC1},
            timeout=20,
        )
        assert r.status_code == 400, r.text
        assert "predecessor" in r.json().get("detail", "").lower() or "own" in r.json().get("detail", "").lower()

    def test_patch_neither_field_rejected(self, session):
        r = session.patch(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{DOC1}",
            json={},
            timeout=20,
        )
        assert r.status_code == 400, r.text

    def test_patch_unknown_predecessor_404(self, session):
        r = session.patch(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{DOC1}",
            json={"related_doc_id": "00000000-0000-0000-0000-000000000000"},
            timeout=20,
        )
        assert r.status_code == 404, r.text

    def test_patch_cycle_rejected(self, session):
        # DOC1 already linked to DOC2. Try to link DOC2 -> DOC1, which would
        # form a cycle.
        r = session.patch(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{DOC2}",
            json={"related_doc_id": DOC1},
            timeout=20,
        )
        assert r.status_code == 400, r.text
        assert "cycle" in r.json().get("detail", "").lower()

    def test_patch_link_persists(self, session):
        # Re-affirm DOC1 -> DOC2 link (idempotent) and verify GET reflects it
        r = session.patch(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{DOC1}",
            json={"related_doc_id": DOC2},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("related_doc_id") == DOC2
        # GET to verify persistence
        g = session.get(f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{DOC1}", timeout=20)
        assert g.status_code == 200
        assert g.json().get("related_doc_id") == DOC2


# --------------------------------------------------------------------------
# Module: documents router — POST evolution-diff
# --------------------------------------------------------------------------
class TestEvolutionDiff:
    def test_diff_no_link_returns_null(self, session):
        # Pick a doc that has no related_doc_id
        r = session.get(f"{BASE_URL}/api/contexts/{CTX_ID}/documents", timeout=20)
        docs = r.json() if isinstance(r.json(), list) else r.json().get("documents", [])
        target = None
        for d in docs:
            if d.get("id") in (DOC1,):
                continue
            full = session.get(
                f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{d['id']}", timeout=20
            )
            if full.status_code == 200 and not full.json().get("related_doc_id"):
                target = d["id"]
                break
        if not target:
            pytest.skip("No unlinked doc available")
        r = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{target}/evolution-diff",
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("previous_doc") is None
        assert body.get("diff") is None

    def test_diff_returns_full_payload(self, session):
        t0 = time.time()
        r = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{DOC1}/evolution-diff",
            timeout=120,
        )
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("previous_doc"), "previous_doc must be populated"
        assert body["previous_doc"]["id"] == DOC2
        diff = body.get("diff")
        assert diff and isinstance(diff, dict)
        assert isinstance(diff.get("what_changed"), str)
        assert isinstance(diff.get("added_or_strengthened"), list)
        assert isinstance(diff.get("weakened_or_removed"), list)
        assert isinstance(diff.get("questions_for_management"), list)
        # Caps per spec: <=5, <=5, <=3
        assert len(diff["added_or_strengthened"]) <= 5
        assert len(diff["weakened_or_removed"]) <= 5
        assert len(diff["questions_for_management"]) <= 3
        print(f"[evolution-diff] elapsed={elapsed:.1f}s")

    def test_diff_cached_hit_is_fast(self, session):
        t0 = time.time()
        r = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{DOC1}/evolution-diff",
            timeout=20,
        )
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        # Cache hit should be quick (<5s)
        assert elapsed < 8, f"cache hit too slow: {elapsed:.1f}s"

    def test_diff_doc_not_found_404(self, session):
        r = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/00000000-0000-0000-0000-000000000000/evolution-diff",
            timeout=20,
        )
        assert r.status_code == 404, r.text
