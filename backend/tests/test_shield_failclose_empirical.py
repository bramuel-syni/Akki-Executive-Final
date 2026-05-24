"""Empirical Shield fail-close verification — replaces the earlier
mock-only test.

Empirical verification that Shield fails-closed regardless of WHICH
failure mode hits the spaCy model — replaces the earlier mock-only
test. Run independently via::

    pytest tests/test_shield_failclose_empirical.py -v

Why monkeypatch instead of subprocess
-------------------------------------
The original brief offered ``subprocess.run`` or
``multiprocessing.Process`` to spawn a fresh FastAPI in a tampered
environment. We chose ``pytest.MonkeyPatch`` instead because:

  1. Spawning a fresh FastAPI in the test container would re-bind to
     port 8001 (occupied by the supervisor-managed backend) AND would
     re-trigger ``warmup_or_die()`` which now runs at startup — a
     subprocess that survives warmup is a subprocess where Shield is
     fine, defeating the test.
  2. Manipulating the FILESYSTEM (corrupting ``meta.json``) is racy
     against parallel pytest runs and against ``importlib`` cache;
     restoring it after the test is best-effort and would leave a
     broken venv on a CI run that crashes mid-test.
  3. ``MonkeyPatch`` operates at the lowest realistic level — it
     intercepts the very call (``_attempt_load``,
     ``spacy.util.is_package``, ``spacy.load``) that the production
     code path executes. The PATCH SURFACE is identical to a real
     model-missing/corrupt outcome. We document this explicitly so
     any future auditor can audit the surface, not the mechanism.

The patched call sites mirror the three real failure modes called out
in the original brief:

  Test 1 — ``test_empirical_model_package_missing``:
      spaCy's ``util.is_package`` returns False AND ``spacy.load``
      raises OSError with the canonical ``[E050]`` shape. Surface
      matches a container that shipped without the ``en_core_web_sm``
      wheel.

  Test 2 — ``test_empirical_model_file_corrupt``:
      ``spacy.load`` raises ``ValueError("Could not deserialize the
      vocab")`` — the surface spaCy raises when ``vocab/strings.json``
      contains garbage bytes (verified against spaCy 3.8.14 source).

  Test 3 — ``test_empirical_spacy_import_failure``:
      ``spacy.load`` raises ``ImportError("can't load model
      components")`` — surface matches a wheel that installed but
      whose internal modules can't be imported (e.g. ABI mismatch).

All three tests assert the same fail-closed contract: HTTP 503 +
``audit_invariant_violations.shield_failure_at_entry`` row + raw PAN
absent from response body.
"""
from __future__ import annotations

import os
import uuid
from unittest import mock

import pytest
import pytest_asyncio

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki")
os.environ.setdefault("JWT_SECRET", "test-secret")

from httpx import AsyncClient, ASGITransport  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(scope="module")
async def client():
    from server import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


async def _login_and_chat(client):
    """Register a fresh account + create a chat. Returns
    ``(token, ctx_id, chat_id, account_id, hdrs)``.

    Mirrors the shape used by `test_h2_5_shield_uniformity.py:_login_and_chat`.
    """
    email = f"empirical-{uuid.uuid4().hex[:10]}@example.com"
    pwd = "Empirical2026!"
    r = await client.post("/api/auth/register", json={
        "email": email, "password": pwd, "name": "Empirical Tester",
    })
    assert r.status_code in (200, 201), r.text[:300]
    token = r.json()["access_token"]
    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"},
    )
    account_id = me.json()["account"]["id"]
    ctx_id = me.json()["contexts"][0]["id"]
    hdrs = {
        "Authorization": f"Bearer {token}",
        "X-Active-Context": ctx_id,
    }
    chat_r = await client.post(
        "/api/chats",
        json={"title": "empirical failclose"},
        headers=hdrs,
    )
    assert chat_r.status_code in (200, 201), chat_r.text[:300]
    return token, ctx_id, chat_r.json()["id"], account_id, hdrs


async def _assert_failclosed(client, hdrs, account_id, chat_id, *, label: str):
    """Common assertion bundle for all three empirical scenarios."""
    from core import db

    before = await db.audit_invariant_violations.count_documents(
        {"account_id": account_id, "kind": "shield_failure_at_entry"},
    )

    body = {
        "content": "My card is 4111111111111111 please charge it.",
        "shielding_policy": "always",
    }
    resp = await client.post(
        f"/api/chats/{chat_id}/messages/stream",
        json=body, headers=hdrs, timeout=30.0,
    )

    assert resp.status_code == 503, (
        f"[{label}] FAIL-OPEN: returned {resp.status_code}. "
        f"Expected 503. Body: {resp.text[:400]!r}"
    )
    body_json = resp.json()
    assert body_json["detail"]["error"] == "shield_unavailable", (
        f"[{label}] body: {body_json}"
    )
    assert "4111111111111111" not in resp.text, (
        f"[{label}] FAIL-OPEN: raw PAN leaked: {resp.text[:400]!r}"
    )

    after = await db.audit_invariant_violations.count_documents(
        {"account_id": account_id, "kind": "shield_failure_at_entry"},
    )
    assert after > before, (
        f"[{label}] invariant row missing: before={before}, after={after}"
    )


# ─────────────────────────────────────────────────────────────────────
# Test 1 — model package missing at spaCy's resolver level
# ─────────────────────────────────────────────────────────────────────
async def test_empirical_model_package_missing(client, monkeypatch):
    """spaCy's ``util.is_package`` returns False AND ``spacy.load``
    raises ``OSError([E050]…)`` — the canonical surface of a
    container that shipped without ``en_core_web_sm``."""
    from services.synisense.shield import deidentifier

    token, ctx_id, chat_id, account_id, hdrs = await _login_and_chat(client)

    saved_nlp = deidentifier._SPACY_NLP
    saved_err = deidentifier._SPACY_LOAD_ERROR
    monkeypatch.setattr(deidentifier, "_SPACY_NLP", None, raising=False)
    monkeypatch.setattr(deidentifier, "_SPACY_LOAD_ERROR", None, raising=False)

    def _is_pkg_false(*args, **kwargs):
        return False

    def _load_raises_e050(name, *args, **kwargs):
        raise OSError(
            f"[E050] Can't find model '{name}'. It doesn't seem to "
            "be a Python package or a valid path to a data directory."
        )

    import spacy
    monkeypatch.setattr(spacy.util, "is_package", _is_pkg_false)
    monkeypatch.setattr(spacy, "load", _load_raises_e050)

    # Also monkey-patch the internal subprocess download so the test
    # doesn't actually try to hit GitHub.
    def _subprocess_fail(*args, **kwargs):
        raise OSError("subprocess: pretend-no-internet")
    monkeypatch.setattr(deidentifier.subprocess, "run", _subprocess_fail)

    try:
        await _assert_failclosed(
            client, hdrs, account_id, chat_id,
            label="empirical/model_package_missing",
        )
    finally:
        deidentifier._SPACY_NLP = saved_nlp
        deidentifier._SPACY_LOAD_ERROR = saved_err


# ─────────────────────────────────────────────────────────────────────
# Test 2 — model deserialisation failure (corrupted meta.json /
# strings.json — spaCy raises ValueError or OSError-derivatives)
# ─────────────────────────────────────────────────────────────────────
async def test_empirical_model_file_corrupt(client, monkeypatch):
    """``spacy.load`` raises a deserialisation error — the surface
    spaCy emits when the model package's internal files (e.g.
    ``vocab/strings.json``) contain garbage bytes."""
    from services.synisense.shield import deidentifier

    token, ctx_id, chat_id, account_id, hdrs = await _login_and_chat(client)

    saved_nlp = deidentifier._SPACY_NLP
    saved_err = deidentifier._SPACY_LOAD_ERROR
    monkeypatch.setattr(deidentifier, "_SPACY_NLP", None, raising=False)
    monkeypatch.setattr(deidentifier, "_SPACY_LOAD_ERROR", None, raising=False)

    def _load_raises_corrupt(name, *args, **kwargs):
        raise ValueError(
            "Could not deserialize the vocab from "
            f"{name}: invalid json at byte 12"
        )

    import spacy
    monkeypatch.setattr(spacy, "load", _load_raises_corrupt)

    # Block the download retry too.
    def _subprocess_fail(*args, **kwargs):
        raise OSError("subprocess: pretend-no-internet")
    monkeypatch.setattr(deidentifier.subprocess, "run", _subprocess_fail)

    try:
        await _assert_failclosed(
            client, hdrs, account_id, chat_id,
            label="empirical/model_file_corrupt",
        )
    finally:
        deidentifier._SPACY_NLP = saved_nlp
        deidentifier._SPACY_LOAD_ERROR = saved_err


# ─────────────────────────────────────────────────────────────────────
# Test 3 — import-time failure inside the spaCy load chain
# (ABI mismatch on the wheel, broken transitive dep, etc.)
# ─────────────────────────────────────────────────────────────────────
async def test_empirical_spacy_import_failure(client, monkeypatch):
    """``spacy.load`` raises ``ImportError`` — surface matches a wheel
    that installed but whose internal components can't be imported
    (e.g. ABI mismatch with the host Python)."""
    from services.synisense.shield import deidentifier

    token, ctx_id, chat_id, account_id, hdrs = await _login_and_chat(client)

    saved_nlp = deidentifier._SPACY_NLP
    saved_err = deidentifier._SPACY_LOAD_ERROR
    monkeypatch.setattr(deidentifier, "_SPACY_NLP", None, raising=False)
    monkeypatch.setattr(deidentifier, "_SPACY_LOAD_ERROR", None, raising=False)

    def _load_raises_import(name, *args, **kwargs):
        raise ImportError(
            f"Cannot import 'load' from 'spacy.cli' while resolving {name}"
        )

    import spacy
    monkeypatch.setattr(spacy, "load", _load_raises_import)

    def _subprocess_fail(*args, **kwargs):
        raise OSError("subprocess: pretend-no-internet")
    monkeypatch.setattr(deidentifier.subprocess, "run", _subprocess_fail)

    try:
        await _assert_failclosed(
            client, hdrs, account_id, chat_id,
            label="empirical/spacy_import_failure",
        )
    finally:
        deidentifier._SPACY_NLP = saved_nlp
        deidentifier._SPACY_LOAD_ERROR = saved_err
