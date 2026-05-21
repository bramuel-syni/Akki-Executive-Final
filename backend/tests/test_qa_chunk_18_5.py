"""Chunk 18.5 — Track 4 cold-start fix + orphan probe + shield-internal CI guard.

Coverage:
  • Item 1 (cold-start) — `_legacy_llm_fallback._classify_one` no longer
    bypasses the gateway; routes through `llm_router.invoke()` and
    honours `SYNISENSE_LLM_MODE=mock`.
  • Item 1 (cold-start) — `litellm` + `get_integration_proxy_url`
    moved to module-level in `llm_router.py` so the first prod call
    doesn't pay the import-cache lookup cost.
  • Item 4 (orphans) — probe + dormant migration script behave as
    advertised on an empty `solva_sessions` collection.
  • CI guard — shield-internal hardening: only `llm_router.py` may
    import provider SDKs.

Anchor: `/app/memory/sprints/CHUNK_18_5_STATE.md`.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient


# Async tests carry an explicit @pytest.mark.asyncio decorator below.
# Sync tests (static-source checks + CI guard) intentionally do not so
# pytest-asyncio doesn't warn about them.


@pytest_asyncio.fixture
async def db_conn():
    mclient = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mclient[os.environ["DB_NAME"]]
    yield db
    mclient.close()


# =====================================================================
# Item 1 — Cold-start: legacy fallback now routes through llm_router
# =====================================================================

@pytest.mark.asyncio
async def test_chunk18_5_legacy_fallback_honours_mock_mode():
    """`_legacy_llm_fallback._classify_one` should produce a result in
    mock mode WITHOUT touching the real LLM API. Pre-fix this path
    bypassed `SYNISENSE_LLM_MODE=mock` and spent 5-13s per call."""
    from services.synisense.shield._legacy_llm_fallback import _classify_one

    saved = os.environ.get("SYNISENSE_LLM_MODE", "")
    os.environ["SYNISENSE_LLM_MODE"] = "mock"
    try:
        span = {
            "start": 18, "end": 30,
            "entity_type": "PERSON",
            "confidence": 0.4,
            "source": "presidio",
        }
        text = "Email me about Bramuel Otieno for the audit committee."
        result = await _classify_one(text, span, timeout_ms=2000)
        # Verdict should be one of the allowed values even from the
        # router's echo fallback (the regex extractor doesn't find
        # JSON in the echo, so it defaults to "uncertain" — and that's
        # the contract).
        assert result["llm_verdict"] in {"pii", "not_pii", "uncertain"}
        assert "elapsed_ms" in result
        # Critical: NOT the "no_emergent_key" branch (which the new
        # router code path no longer emits — it would mean the function
        # took the old direct-LlmChat branch by mistake).
        assert result.get("llm_reason") != "no_emergent_key"
    finally:
        if saved:
            os.environ["SYNISENSE_LLM_MODE"] = saved
        else:
            os.environ.pop("SYNISENSE_LLM_MODE", None)


@pytest.mark.asyncio
async def test_chunk18_5_legacy_fallback_routes_through_llm_router():
    """Mock `llm_router.invoke` and confirm `_classify_one` calls it,
    proving the legacy direct-LlmChat path was retired."""
    from services.synisense.shield import _legacy_llm_fallback as lf

    fake = AsyncMock(return_value=('{"verdict":"pii","type":"PERSON"}', "gemini:mock", "gemini-2.5-flash:mock"))
    with patch("services.synisense.shield._legacy_llm_fallback.llm_router.invoke", new=fake):
        span = {"start": 0, "end": 4, "entity_type": "PERSON",
                "confidence": 0.4, "source": "presidio"}
        result = await lf._classify_one("Anna Smith called.", span, timeout_ms=2000)
        assert result["llm_verdict"] == "pii"
        assert result["llm_suggested_type"] == "PERSON"
    fake.assert_called_once()


@pytest.mark.asyncio
async def test_chunk18_5_legacy_fallback_no_direct_llmchat_import():
    """Static check — the legacy fallback file no longer imports
    `LlmChat` / `UserMessage` directly. The new code path goes through
    `llm_router.invoke` which is the canonical SDK call site."""
    src_path = Path(__file__).resolve().parents[1] / "services" / "synisense" / "shield" / "_legacy_llm_fallback.py"
    src = src_path.read_text(encoding="utf-8")
    # The file references LlmChat ONLY in the docstring, which the
    # `_line_in_docstring` heuristic of the CI guard ignores. Here we
    # check there's no live import line.
    for line_no, line in enumerate(src.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"') or stripped.startswith("'"):
            continue
        assert "from emergentintegrations.llm" not in stripped, (
            f"_legacy_llm_fallback.py:{line_no} still has a direct "
            f"emergentintegrations.llm import — must route via llm_router"
        )
        assert not re.match(r"^\s*LlmChat\s*\(", line), (
            f"_legacy_llm_fallback.py:{line_no} still constructs LlmChat directly"
        )


def test_chunk18_5_litellm_at_module_level_in_router():
    """The `litellm` + `get_integration_proxy_url` imports were lifted
    from per-call to module-level (Chunk 18.5 cold-start). Static
    check the module-level probe exists and the per-call import has
    been removed."""
    src_path = Path(__file__).resolve().parents[1] / "services" / "synisense" / "shield" / "llm_router.py"
    src = src_path.read_text(encoding="utf-8")
    # Module-level probe pattern.
    assert "_LITELLM_AVAILABLE" in src
    assert "import litellm" in src
    # The previous per-call lazy import comment hint should be gone.
    assert "import litellm  # noqa: WPS433 — local import, lighter cold path" not in src
    # The per-call `from emergentintegrations.llm.utils import get_integration_proxy_url`
    # inside `invoke_with_metering` should have been promoted.
    invoke_body = src.split("async def invoke_with_metering")[1] if "async def invoke_with_metering" in src else ""
    assert "from emergentintegrations.llm.utils import get_integration_proxy_url" not in invoke_body, (
        "get_integration_proxy_url should be a module-level import, not per-call"
    )


# =====================================================================
# Item 4 — Orphan probe + dormant migration
# =====================================================================

@pytest.mark.asyncio
async def test_chunk18_5_solva_legacy_orphan_count_is_zero(db_conn):
    """Live state check — `solva_sessions` has no pending orphans.

    If a future seed re-introduces legacy rows this will fail loudly
    and the dormant `migrate_solva_legacy_to_phase_d` script becomes
    the ops response.
    """
    from scripts.probe_solva_legacy_orphans import probe

    result = await probe()
    assert "solva_sessions" in result
    assert "summary" in result
    summary = result["summary"]
    assert summary["pending_orphans"] == 0, (
        f"Expected 0 pending orphans, got {summary['pending_orphans']}. "
        f"Run `python -m scripts.migrate_solva_legacy_to_phase_d` to clear."
    )
    assert summary["migration_needed"] is False


@pytest.mark.asyncio
async def test_chunk18_5_migration_script_idempotent_on_empty_collection(db_conn):
    """Migration script returns 0-everything on an empty source
    collection. Confirms the script is safe to leave dormant in the
    repo and runnable as a no-op verification."""
    from scripts.migrate_solva_legacy_to_phase_d import migrate

    # Ensure source is empty for this test (we don't want a stray
    # legacy row from another test to inflate the result).
    await db_conn["solva_sessions"].delete_many({"id": {"$regex": "^test-chunk18-5"}})

    result = await migrate(dry_run=True)
    assert result["total"] == 0
    assert result["migrated"] == 0
    assert result["archived_only"] == 0
    assert result["skipped"] == 0


@pytest.mark.asyncio
async def test_chunk18_5_migration_script_handles_unmappable_row(db_conn):
    """A legacy row missing `context_id` lands in `archived_only`, not
    `migrated`. Counted, audited, but never written to Phase D."""
    from scripts.migrate_solva_legacy_to_phase_d import migrate

    # Seed one unmappable row + one mappable row.
    test_marker = "test-chunk18-5-unmappable"
    await db_conn["solva_sessions"].delete_many({"id": {"$regex": "^test-chunk18-5"}})
    await db_conn["solva_sessions_archived"].delete_many({"id": {"$regex": "^test-chunk18-5"}})
    await db_conn["solva_migration_audit"].delete_many({"legacy_id": {"$regex": "^test-chunk18-5"}})
    await db_conn["solva_phase_d_sessions"].delete_many({"id": {"$regex": "^phd-legacy-test-chunk18-5"}})

    await db_conn["solva_sessions"].insert_many([
        {"id": f"{test_marker}-no-ctx", "account_id": "acc-1",
         "state": "active"},  # missing context_id → archived_only
        {"id": f"{test_marker}-ok", "account_id": "acc-1",
         "context_id": "ctx-1", "state": "complete",
         "layers": {"layer_0": {"frame": "test"}}},
    ])

    result = await migrate(dry_run=False)
    assert result["total"] >= 2
    assert result["archived_only"] >= 1
    assert result["migrated"] >= 1

    # The mappable row landed in Phase D.
    phd_row = await db_conn["solva_phase_d_sessions"].find_one(
        {"context_id": "ctx-1", "account_id": "acc-1",
         "migrated_from": "solva_sessions"},
        {"_id": 0},
    )
    assert phd_row is not None
    assert phd_row["status"] == "complete"

    # Audit rows exist for both.
    audits = await db_conn["solva_migration_audit"].find(
        {"legacy_id": {"$regex": "^test-chunk18-5"}}, {"_id": 0},
    ).to_list(10)
    statuses = [a["status"] for a in audits]
    assert "migrated" in statuses
    assert "archived_only" in statuses

    # Idempotent — re-running marks both as already_migrated.
    result2 = await migrate(dry_run=False)
    assert result2["already_migrated"] >= 2

    # Cleanup.
    await db_conn["solva_sessions"].delete_many({"id": {"$regex": "^test-chunk18-5"}})
    await db_conn["solva_sessions_archived"].delete_many({"id": {"$regex": "^test-chunk18-5"}})
    await db_conn["solva_migration_audit"].delete_many({"legacy_id": {"$regex": "^test-chunk18-5"}})
    await db_conn["solva_phase_d_sessions"].delete_many({"context_id": "ctx-1", "account_id": "acc-1", "migrated_from": "solva_sessions"})


# =====================================================================
# CI guard hardening — shield-internal direct-LLM-call ban
# =====================================================================

BACKEND = Path(__file__).resolve().parents[1]
SHIELD = BACKEND / "services" / "synisense" / "shield"

# Inside `shield/`, only the two approved gateway entry points may
# import provider SDKs:
#   • `llm_router.py`  — non-streaming sync invoke (returns full text).
#   • `streaming.py`   — streaming counterpart (final-event token usage).
# Every other shield file must route through one of these two — and
# external code must route through `client.invoke()` (which itself
# wraps `llm_router.invoke()`). This was the Chunk 18.5 lesson:
# `_legacy_llm_fallback.py` lived INSIDE `shield/` but bypassed the
# gateway with its own LlmChat call — the original external-scope
# guard waived it because the file path matched `shield/`. The fix
# was both architectural (route fallback through `llm_router`) AND a
# tightened guard scope (this test).
SHIELD_ALLOWED_DIRECT_LLM = {
    str(SHIELD / "llm_router.py"),
    str(SHIELD / "streaming.py"),
}

SHIELD_FORBIDDEN_PATTERNS = [
    ("emergentintegrations.llm import",
     re.compile(r"(?:^|\W)(?:from|import)\s+emergentintegrations\.llm\b")),
    ("emergentintegrations.llm.utils import",
     re.compile(r"(?:^|\W)(?:from|import)\s+emergentintegrations\.llm\.utils\b")),
    ("LlmChat(",
     re.compile(r"(?:^|\W)LlmChat\s*\(")),
    ("UserMessage(",
     re.compile(r"(?:^|\W)UserMessage\s*\(")),
    ("openai.ChatCompletion / .chat / .completions",
     re.compile(r"(?:^|\W)openai\.(?:ChatCompletion|chat|completions)\b")),
    ("anthropic.Anthropic( / .messages",
     re.compile(r"(?:^|\W)anthropic\.(?:Anthropic\s*\(|messages\b)")),
    ("genai.GenerativeModel",
     re.compile(r"(?:^|\W)genai\.GenerativeModel\b")),
    ("google.generativeai import",
     re.compile(r"(?:^|\W)(?:from|import)\s+google\.generativeai\b")),
    ("litellm.completion / .acompletion",
     re.compile(r"(?:^|\W)litellm\.(?:completion|acompletion)\b")),
    ("litellm bare import",
     re.compile(r"(?:^|\W)import\s+litellm\b")),
]


_TRIPLE = re.compile(r'("""|\'\'\')')


def _line_in_docstring(text: str, line_no: int) -> bool:
    lines = text.splitlines()
    upto = "\n".join(lines[: line_no - 1])
    return (len(_TRIPLE.findall(upto)) % 2) == 1


def test_no_direct_llm_calls_inside_shield_except_router():
    """Phase B+ companion guard — within `services/synisense/shield/`,
    only `llm_router.py` is allowed to import provider SDKs.

    Chunk 18.5 exposed the failure mode the original guard missed:
    `_legacy_llm_fallback.py` lived INSIDE `shield/` (so the
    external-scope guard waived it) but bypassed the gateway just as
    badly as any external caller would — it imported `LlmChat`
    directly and ran up to 20 cloud LLM calls per de-id pre-pass,
    AND it failed to honour `SYNISENSE_LLM_MODE=mock`.

    Architectural lesson: shield-internal files can leak as easily as
    external callers — guard scope must include `shield/` itself.
    """
    violations: list[str] = []
    for path in SHIELD.rglob("*.py"):
        sp = str(path)
        if sp in SHIELD_ALLOWED_DIRECT_LLM:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            for label, pat in SHIELD_FORBIDDEN_PATTERNS:
                if pat.search(line):
                    if _line_in_docstring(text, line_no):
                        continue
                    rel = path.relative_to(BACKEND)
                    violations.append(
                        f"{rel}:{line_no}  [{label}]  {line.strip()[:140]}"
                    )

    assert not violations, (
        "Shield-internal invariant breach — only `llm_router.py` may "
        "import provider SDKs. All other shield files MUST route "
        "through `services.synisense.shield.llm_router.invoke(...)`. "
        f"\n\n{len(violations)} violation(s):\n  " + "\n  ".join(violations)
    )
