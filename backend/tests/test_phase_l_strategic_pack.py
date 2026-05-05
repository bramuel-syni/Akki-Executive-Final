"""Phase L — Strategic Documents Pack ingestion tests.

Covers:
  L.1 — corpus surface: pick_strategic_documents / pick_cycle_snapshot
        enrichment / pick_studio_sources include_strategic flag
  L.2 — admin seed idempotence + Synisense + sensitivity wiring
  L.3 — Julius seed extension to 5 contexts + 14 docs mirror
  L.4 — GET /api/contexts/{cid}/documents/{did} surfaces body_redacted,
        synisense_version, sensitivity_score, sensitivity_band, doc_kind
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
SEED_ADMIN = ROOT / "scripts" / "seed_admin_strategic_data.py"
SEED_JULIUS = ROOT / "scripts" / "seed_julius_opio.py"

ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PW = "AkkiAdmin2026!"
JULIUS_EMAIL = "juliusaopio@gmail.com"
JULIUS_PW = "Julius@Akki!2026-Exec"
BACKEND = os.environ.get("BACKEND_URL", "http://localhost:8001")


def _run_script(path: Path) -> str:
    proc = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, (
        f"{path.name} exited {proc.returncode}\n"
        f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
    )
    return proc.stdout


# ─────────────────────────────────────────────────────────────────────────
# L.1 — corpus surface
# ─────────────────────────────────────────────────────────────────────────
def test_strategic_corpus_health():
    from sandbox_v2_strategic import strategic_corpus_health
    h = strategic_corpus_health()
    assert h["total_docs"] == 14
    assert h["by_org_type"] == {
        "bank": 3, "healthcare": 3, "logistics": 3,
        "technology": 2, "government": 3,
    }
    assert h["source"] == "strategic_pack_v1"
    assert set(h["by_kind"]) >= {
        "strategic_plan", "framework", "strategy",
        "theory_of_change", "investment_thesis", "political_economy",
    }


def test_pick_strategic_documents_returns_three_for_bank():
    from sandbox_v2_strategic import pick_strategic_documents
    docs = pick_strategic_documents("bank")
    assert len(docs) == 3
    titles = [d["title"] for d in docs]
    assert any("Five-Year Strategic Plan" in t for t in titles)
    assert all(d["org_type"] == "bank" for d in docs)
    assert all(400 <= len(d["body"].split()) <= 800 for d in docs)


def test_pick_strategic_documents_unknown_org_returns_empty():
    from sandbox_v2_strategic import pick_strategic_documents
    assert pick_strategic_documents("nonexistent") == []
    assert pick_strategic_documents("") == []


def test_pick_strategic_documents_kind_filter():
    from sandbox_v2_strategic import pick_strategic_documents
    plans = pick_strategic_documents("logistics", kind="strategic_plan")
    assert len(plans) == 1
    assert plans[0]["kind"] == "strategic_plan"


def test_pick_studio_sources_default_unchanged():
    from sandbox_v2_corpus import pick_studio_sources
    out = pick_studio_sources("ceo", "bank")
    assert len(out) == 3, "default must stay 3 to preserve Step 3 UI contract"
    assert all(s.get("strategic") is False for s in out)


def test_pick_studio_sources_include_strategic_splices_pack():
    from sandbox_v2_corpus import pick_studio_sources
    out = pick_studio_sources("ceo", "bank", include_strategic=True)
    assert len(out) == 6, "3 tactical + 3 strategic"
    assert sum(1 for s in out if s["strategic"]) == 3


def test_pick_cycle_snapshot_carries_strategic_plan_refs():
    from sandbox_v2_corpus import pick_cycle_snapshot
    snap = pick_cycle_snapshot("ceo", "bank")
    assert "strategic_plan_refs" in snap
    assert "strategic_baseline_source" in snap
    assert len(snap["strategic_plan_refs"]) == 3
    assert "Mara Heritage Bank" in snap["strategic_baseline_source"]
    # Existing UI contract preserved
    assert isinstance(snap["strategic_baseline"], list)
    assert all(isinstance(x, str) for x in snap["strategic_baseline"])


# ─────────────────────────────────────────────────────────────────────────
# L.2 / L.3 — seed scripts
# ─────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_admin_seed_idempotent_after_second_run():
    out1 = _run_script(SEED_ADMIN)
    out2 = _run_script(SEED_ADMIN)
    assert "✅ Seed complete." in out1
    assert "✅ Seed complete." in out2
    # Second run must not create any docs
    assert "docs_created               0" in out2 or "docs_created                0" in out2


@pytest.mark.asyncio
async def test_julius_seed_now_carries_5_contexts_and_14_docs():
    _run_script(SEED_JULIUS)
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    julius = await db.accounts.find_one({"email": JULIUS_EMAIL}, {"_id": 0, "id": 1})
    assert julius is not None
    n_ctx = await db.contexts.count_documents({"owner_account_id": julius["id"]})
    assert n_ctx == 5, f"Julius must own exactly 5 contexts; got {n_ctx}"
    n_docs = await db.documents.count_documents({
        "source": "strategic_pack_v1", "uploaded_by": julius["id"],
    })
    assert n_docs == 14, f"Julius must have exactly 14 strategic docs; got {n_docs}"
    # Check each pack org_type is represented in Julius's docs
    docs = [d async for d in db.documents.find(
        {"source": "strategic_pack_v1", "uploaded_by": julius["id"]},
        {"_id": 0, "context_id": 1, "doc_kind": 1, "name": 1},
    )]
    titles = [d["name"] for d in docs]
    for required in (
        "Five-Year Strategic Plan",         # Bank
        "Pre-IPO Strategic Plan 2025-2028", # Healthcare
        "Pre-IPO Strategic Plan — Path to Listing",  # Logistics
        "Series A Investment Thesis",       # Technology
        "Sector Strategic Plan 2024-2029",  # Government
    ):
        assert any(required in t for t in titles), f"missing {required}"
    client.close()


@pytest.mark.asyncio
async def test_synisense_ran_on_strategic_docs_admin():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    admin = await db.accounts.find_one({"email": ADMIN_EMAIL}, {"_id": 0, "id": 1})
    docs = [d async for d in db.documents.find(
        {"source": "strategic_pack_v1", "uploaded_by": admin["id"]},
        {"_id": 0, "name": 1, "extracted_text": 1, "body_redacted": 1,
         "synisense_version": 1, "sensitivity_score": 1, "sensitivity_band": 1},
    )]
    assert len(docs) == 14
    for d in docs:
        assert d["synisense_version"] == 1
        assert d["body_redacted"], f"body_redacted empty on {d['name']}"
        # Synisense must have produced *some* redaction — the pack is full
        # of org names, dates, and personnel references.
        assert d["body_redacted"] != d["extracted_text"], (
            f"no redaction on {d['name']}"
        )
        # Sensitivity floor must have lifted everything to internal+
        assert d["sensitivity_band"] in {"internal", "confidential", "restricted"}
    client.close()


# ─────────────────────────────────────────────────────────────────────────
# L.4 — document detail endpoint surfaces body_redacted etc.
# ─────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_get_document_detail_surfaces_strategic_artefacts():
    async with httpx.AsyncClient(base_url=BACKEND, timeout=15.0) as ac:
        r = await ac.post("/api/auth/login",
                          json={"email": JULIUS_EMAIL, "password": JULIUS_PW})
        assert r.status_code == 200
        data = r.json()
        tok = data["access_token"]
        H = {"Authorization": f"Bearer {tok}"}
        sample_doc_id = None
        sample_ctx_id = None
        for ctx in data["contexts"]:
            rd = await ac.get(f"/api/contexts/{ctx['id']}/documents", headers=H)
            if rd.status_code != 200:
                continue
            payload = rd.json()
            items = payload if isinstance(payload, list) else (payload.get("items") or payload.get("documents") or [])
            strategic = [d for d in items if d.get("source") == "strategic_pack_v1"]
            if strategic:
                sample_doc_id = strategic[0]["id"]
                sample_ctx_id = ctx["id"]
                break
        assert sample_doc_id, "Julius must have at least one strategic doc visible"

        rd = await ac.get(
            f"/api/contexts/{sample_ctx_id}/documents/{sample_doc_id}",
            headers=H,
        )
        assert rd.status_code == 200
        d = rd.json()
        assert d["extracted_text"]
        assert d["body_redacted"]
        assert d["body_redacted"] != d["extracted_text"]
        assert d["synisense_version"] == 1
        assert isinstance(d["sensitivity_score"], int)
        assert d["sensitivity_band"] in {"internal", "confidential", "restricted"}
        assert d["doc_kind"] in {
            "strategic_plan", "framework", "strategy",
            "theory_of_change", "investment_thesis", "political_economy",
        }


def test_admin_seed_log_format():
    out = _run_script(SEED_ADMIN)
    assert "Per-org-type summary" in out
    assert "admin.documents (pack)" in out
    assert "✅ Seed complete." in out
