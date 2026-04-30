"""iter36 tests — audit pack export, doc_evolution share, influence map."""
import io
import json
import os
import subprocess
import tempfile
import time
import zipfile

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://akki-executive.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

BRAMUEL = {"email": "bramuel@syni.ai", "password": "TestBramuel2026!"}
ADMIN = {"email": "admin@akki.ai", "password": "AkkiAdmin2026!"}

TULI_EXEC_HINT = "Tuli"
TULI_DOC1 = "a90b82e3-3fa9-4a26-be0c-d63bdfc51909"


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def bram_token():
    return _login(BRAMUEL)


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def bram_contexts(bram_token):
    r = requests.get(f"{API}/auth/me",
                     headers={"Authorization": f"Bearer {bram_token}"}, timeout=30)
    assert r.status_code == 200
    return r.json().get("contexts", [])


@pytest.fixture(scope="module")
def tuli_exec_ctx(bram_contexts):
    """Tuli Executive (CFO) context."""
    for c in bram_contexts:
        name = c.get("name", "")
        ctype = c.get("type", "")
        role = (c.get("membership") or {}).get("role") or c.get("role")
        if "Tuli" in name and "executive" in ctype.lower():
            return c
        if "Tuli" in name and role == "executive":
            return c
    # fallback: any executive-type context
    for c in bram_contexts:
        if "executive" in c.get("type", "").lower():
            return c
    pytest.skip("No Tuli executive context for Bramuel")


@pytest.fixture(scope="module")
def bram_chat_id(bram_token):
    """Create a chat + send a message so audit has rows."""
    h = {"Authorization": f"Bearer {bram_token}"}
    r = requests.post(f"{API}/chats",
                      json={"title": "TEST iter36 audit export"}, headers=h, timeout=30)
    assert r.status_code in (200, 201), r.text
    cid = r.json()["id"]
    # Send one simple message
    requests.post(f"{API}/chats/{cid}/messages",
                  json={"content": "hello world"}, headers=h, timeout=60)
    return cid


# ─────────────────────────── AUDIT PACK EXPORT ───────────────────────────

class TestAuditExport:
    def test_export_zip_structure(self, bram_token, bram_chat_id):
        h = {"Authorization": f"Bearer {bram_token}"}
        r = requests.get(f"{API}/chats/{bram_chat_id}/audit/export.zip",
                         headers=h, timeout=30)
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/zip")
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd and ".zip" in cd

        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(z.namelist())
        required = {"manifest.txt", "chat.json", "messages.json",
                    "audit_chain.json", "verify.py"}
        missing = required - names
        assert not missing, f"Missing files in zip: {missing}; got {names}"

        # messages.json must have content_sha256, no raw content
        msgs = json.loads(z.read("messages.json").decode())
        assert isinstance(msgs, list) and len(msgs) > 0
        for m in msgs:
            assert "content_sha256" in m, m
            assert "content" not in m or m.get("content") in (None, ""), \
                f"raw content leaked: {m}"

    def test_verify_py_ok_on_untampered(self, bram_token, bram_chat_id):
        h = {"Authorization": f"Bearer {bram_token}"}
        r = requests.get(f"{API}/chats/{bram_chat_id}/audit/export.zip",
                         headers=h, timeout=30)
        assert r.status_code == 200
        with tempfile.TemporaryDirectory() as d:
            zipfile.ZipFile(io.BytesIO(r.content)).extractall(d)
            proc = subprocess.run(["python3", "verify.py"], cwd=d,
                                  capture_output=True, text=True, timeout=30)
            out = (proc.stdout + proc.stderr).strip()
            assert proc.returncode == 0, f"verify.py failed: {out}"
            assert "OK" in out and "verified" in out.lower(), out

    def test_verify_py_detects_tamper(self, bram_token, bram_chat_id):
        h = {"Authorization": f"Bearer {bram_token}"}
        r = requests.get(f"{API}/chats/{bram_chat_id}/audit/export.zip",
                         headers=h, timeout=30)
        with tempfile.TemporaryDirectory() as d:
            zipfile.ZipFile(io.BytesIO(r.content)).extractall(d)
            chain_path = os.path.join(d, "audit_chain.json")
            chain = json.loads(open(chain_path).read())
            assert len(chain) >= 1
            # Mutate a payload field while leaving row_hash intact
            target = chain[-1]
            target.setdefault("payload", {})
            target["payload"]["__tampered__"] = True
            open(chain_path, "w").write(json.dumps(chain))
            proc = subprocess.run(["python3", "verify.py"], cwd=d,
                                  capture_output=True, text=True, timeout=30)
            out = (proc.stdout + proc.stderr).lower()
            assert proc.returncode != 0, f"expected non-zero, got {proc.returncode}: {out}"
            assert "mismatch" in out or "hash" in out, out

    def test_export_appends_audit_exported_row(self, bram_token, bram_chat_id):
        h = {"Authorization": f"Bearer {bram_token}"}
        # read chain before
        before = requests.get(f"{API}/chats/{bram_chat_id}/audit",
                              headers=h, timeout=30)
        assert before.status_code == 200
        rows_before = before.json().get("rows", before.json()) if isinstance(before.json(), dict) else before.json()
        n_before = len(rows_before) if isinstance(rows_before, list) else 0

        # trigger export
        r = requests.get(f"{API}/chats/{bram_chat_id}/audit/export.zip",
                         headers=h, timeout=30)
        assert r.status_code == 200

        time.sleep(0.4)
        after = requests.get(f"{API}/chats/{bram_chat_id}/audit",
                             headers=h, timeout=30)
        rows_after = after.json().get("rows", after.json()) if isinstance(after.json(), dict) else after.json()
        assert isinstance(rows_after, list)
        assert len(rows_after) > n_before, \
            f"no new audit row after export: before={n_before} after={len(rows_after)}"
        latest_actions = [r.get("action") for r in rows_after[-3:]]
        assert any("export" in (a or "") for a in latest_actions), latest_actions

    def test_cross_account_export_404(self, admin_token, bram_chat_id):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.get(f"{API}/chats/{bram_chat_id}/audit/export.zip",
                         headers=h, timeout=30)
        assert r.status_code == 404, f"expected 404 cross-account, got {r.status_code}"


# ─────────────────────────── DOC EVOLUTION SHARE ───────────────────────────

class TestDocEvolutionShare:
    def test_share_doc_evolution_success(self, bram_token, tuli_exec_ctx):
        h = {"Authorization": f"Bearer {bram_token}"}
        ctx_id = tuli_exec_ctx["id"]
        # Make sure DOC1 is in this context — try finding a doc with evolution diff
        docs_r = requests.get(f"{API}/contexts/{ctx_id}/documents",
                              headers=h, timeout=30)
        if docs_r.status_code != 200:
            pytest.skip(f"cannot list docs: {docs_r.status_code}")
        docs = docs_r.json()
        if isinstance(docs, dict):
            docs = docs.get("documents") or docs.get("items") or []
        # Prefer DOC1 if present, else any doc with related_doc_id
        candidate = None
        for d in docs:
            if d.get("id") == TULI_DOC1:
                candidate = d
                break
        if not candidate:
            for d in docs:
                if d.get("related_doc_id") and d.get("evolution_diff"):
                    candidate = d
                    break
        if not candidate:
            pytest.skip("No doc with cached evolution_diff in Tuli context")

        body = {
            "item_type": "doc_evolution",
            "item_id": candidate["id"],
            "to_email": "delivered@resend.dev",
            "delivery_method": "akki_notification",
            "message": "TEST iter36 evolution share",
        }
        r = requests.post(f"{API}/contexts/{ctx_id}/shares",
                          json=body, headers=h, timeout=30)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        data = r.json()
        # delivered / queued / sent — any successful status is fine
        status = str(data.get("status") or data.get("delivery_status") or "").lower()
        assert any(s in status for s in ("deliver", "sent", "queued", "ok", "success")) \
            or data.get("id"), data

    def test_share_doc_evolution_404_when_missing(self, bram_token, tuli_exec_ctx):
        h = {"Authorization": f"Bearer {bram_token}"}
        ctx_id = tuli_exec_ctx["id"]
        body = {
            "item_type": "doc_evolution",
            "item_id": "does-not-exist-xyz",
            "to_email": "delivered@resend.dev",
            "delivery_method": "akki_notification",
        }
        r = requests.post(f"{API}/contexts/{ctx_id}/shares",
                          json=body, headers=h, timeout=30)
        assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"


# ─────────────────────────── INFLUENCE MAP ───────────────────────────

class TestInfluenceMap:
    def test_shape(self, bram_token, tuli_exec_ctx):
        h = {"Authorization": f"Bearer {bram_token}"}
        ctx_id = tuli_exec_ctx["id"]
        r = requests.get(f"{API}/contexts/{ctx_id}/influence-map?days=30",
                         headers=h, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("nodes", "edges", "people", "top_docs", "totals", "window_days"):
            assert key in data, f"missing {key}"
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        assert data["window_days"] == 30
        # Each edge has source/target/kind/weight
        for e in data["edges"][:5]:
            assert {"source", "target", "kind", "weight"} <= set(e.keys()), e

    def test_default_days_is_30(self, bram_token, tuli_exec_ctx):
        h = {"Authorization": f"Bearer {bram_token}"}
        ctx_id = tuli_exec_ctx["id"]
        r = requests.get(f"{API}/contexts/{ctx_id}/influence-map",
                         headers=h, timeout=30)
        assert r.status_code == 200
        assert r.json()["window_days"] == 30

    def test_days_validation_422(self, bram_token, tuli_exec_ctx):
        h = {"Authorization": f"Bearer {bram_token}"}
        ctx_id = tuli_exec_ctx["id"]
        r = requests.get(f"{API}/contexts/{ctx_id}/influence-map?days=400",
                         headers=h, timeout=30)
        assert r.status_code == 422, f"expected 422, got {r.status_code}"
        r0 = requests.get(f"{API}/contexts/{ctx_id}/influence-map?days=0",
                          headers=h, timeout=30)
        assert r0.status_code == 422

    def test_cross_context_isolation(self, admin_token, tuli_exec_ctx):
        h = {"Authorization": f"Bearer {admin_token}"}
        ctx_id = tuli_exec_ctx["id"]
        r = requests.get(f"{API}/contexts/{ctx_id}/influence-map?days=30",
                         headers=h, timeout=30)
        assert r.status_code in (403, 404), \
            f"expected 403/404 cross-tenant, got {r.status_code}"

    def test_empty_narrow_window(self, bram_token, tuli_exec_ctx):
        """days=1 on a context that likely has no fresh activity → empty-ish ok."""
        h = {"Authorization": f"Bearer {bram_token}"}
        ctx_id = tuli_exec_ctx["id"]
        r = requests.get(f"{API}/contexts/{ctx_id}/influence-map?days=1",
                         headers=h, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["nodes"], list)
        assert isinstance(d["edges"], list)
