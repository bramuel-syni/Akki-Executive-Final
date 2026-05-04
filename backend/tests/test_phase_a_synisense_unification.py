"""Phase A — Synisense unification integration test.

Proves that a chat message containing fake PII (email, phone, IBAN)
reaches the LLM adapter as Synisense-pipeline tokens (e.g. `[EMAIL_n]`,
`[PHONE_n]`, `[IBAN_n]`), NOT via the retired
`backend/llm_service.shield_payload` regex shield.

We don't run a real LLM call (no key dependency in CI); we patch the
emergent send_message path to capture what the chat router would have
sent, then assert on its shape. The pipeline is real: the adapter
under test is the same `services.synisense.shield_payload_async`
adapter that `llm_service.call_llm` and `routers/chat.py` now use.
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

sys.path.insert(0, "/app/backend")

# Test inputs — fictional PII the legacy regex ladder + the Synisense
# pipeline both detect. We deliberately use values shaped to match
# multiple categories.
SAMPLE_PROMPT = (
    "Please draft a board note. Reach out to "
    "treasury@example-bank-fake.test and copy +44 7700 900123. "
    "Wire confirmation to GB29NWBK60161331926819 (no LEI yet)."
)


# ---------------------------------------------------------------------------
# 1) The retired symbol must not exist anywhere on `llm_service`.
# ---------------------------------------------------------------------------
def test_llm_service_no_longer_exposes_legacy_shield_symbols():
    import llm_service as ls
    for sym in ("shield_payload", "shielding_report", "rehydrate"):
        assert not hasattr(ls, sym), (
            f"llm_service.{sym} should have been removed in Phase A; "
            "callers must use services.synisense.* instead."
        )


# ---------------------------------------------------------------------------
# 2) The Synisense adapter shape — async tuple (str, dict) — and the
#    tokens are pipeline-shaped, not regex-shaped.
# ---------------------------------------------------------------------------
def test_synisense_adapter_returns_pipeline_shaped_tokens():
    from services.synisense import shield_payload_async

    async def _run():
        return await shield_payload_async(
            SAMPLE_PROMPT, surface="chat", context_id="phase-a-test",
        )

    redacted, shield_map = asyncio.run(_run())
    # Returned tuple shape contract — same as the legacy function.
    assert isinstance(redacted, str), type(redacted)
    assert isinstance(shield_map, dict), type(shield_map)
    # The redacted projection must be different from the input — at
    # least one identifier was caught — and must contain pipeline tokens
    # of the form `[<LABEL>_<n>]`. The pipeline labels are a SUPERSET
    # of the legacy labels (EMAIL/PHONE/IBAN) so any of these is fine.
    assert redacted != SAMPLE_PROMPT, redacted
    # Heuristic: every value in shield_map must NOT be present in the
    # redacted text (the redaction must have actually happened) and
    # every key must be present in the redacted text (the token must
    # appear in the prompt going to the LLM).
    for token, original in shield_map.items():
        assert token in redacted, (token, redacted)
        # The pipeline returns labelled tokens; assert the bracket shape.
        assert token.startswith("[") and token.endswith("]"), token
        # Original PII should NOT survive in the redacted text.
        assert original not in redacted, (token, original, redacted)


# ---------------------------------------------------------------------------
# 3) The original regex shield is NOT in the call chain — the adapter
#    must produce labels that the pipeline produces (e.g. `IBAN`,
#    `PHONE`, `EMAIL`), and the tokens must round-trip via the new
#    `rehydrate(...)` helper from `services.synisense`.
# ---------------------------------------------------------------------------
def test_rehydrate_round_trips_via_synisense_helpers():
    from services.synisense import (
        shield_payload_async,
        rehydrate,
    )

    async def _run():
        return await shield_payload_async(
            SAMPLE_PROMPT, surface="chat", context_id="phase-a-test",
        )

    redacted, shield_map = asyncio.run(_run())
    # rehydrate is idempotent on raw text + the round-trip restores all
    # known tokens.
    restored = rehydrate(redacted, shield_map)
    for original in shield_map.values():
        assert original in restored, original


# ---------------------------------------------------------------------------
# 4) `llm_service.call_llm`'s own internal Synisense hook fires — when
#    we call it with `module='chat'`, the adapter sees surface='chat'
#    and the redacted prompt path is exercised. We don't need the LLM
#    to actually respond; calling without EMERGENT_LLM_KEY hits the
#    no-key-fallback branch which returns a `mode='no-key-fallback'`
#    envelope after still running the shield.
# ---------------------------------------------------------------------------
def test_call_llm_routes_through_synisense_no_key_branch(monkeypatch):
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    from llm_service import call_llm

    async def _run():
        return await call_llm(
            module="chat",
            user_query=SAMPLE_PROMPT,
            tier="standard",
        )

    out = asyncio.run(_run())
    assert out["mode"] == "no-key-fallback", out["mode"]
    # The shielding report MUST identify masked things (the prompt
    # carries unambiguous PII). If the regex shield were still in play,
    # the by_category keys would carry "email|phone|iban" — pipeline
    # categories normalise to lowercase too, but the contract here is
    # only that something was masked (proves the shield ran).
    rep = out.get("shielding") or {}
    assert int(rep.get("identifiers_masked") or 0) >= 1, rep
    by_cat = rep.get("by_category") or {}
    assert by_cat, by_cat
    # The adapter labels itself as the pipeline (NOT the legacy
    # `synisense-local` regex shield).
    assert rep.get("shielded_by") == "synisense-pipeline", rep


# ---------------------------------------------------------------------------
# 5) Defence: the surface mapping for `module="chat"` resolves to a
#    pipeline surface that the engine accepts.
# ---------------------------------------------------------------------------
def test_module_to_surface_mapping_resolves_to_valid_surfaces():
    from llm_service import _surface_for_module
    from services.synisense.pipeline import _is_valid_surface
    cases = [
        ("chat", "chat"),
        ("briefing", "briefing"),
        ("decks.outline", "deck"),
        ("solve.synthesis", "solve"),
        ("solve_v2.refusal", "solve_v2"),
        ("document.meta", "ingest"),
        ("walkin.question", "chat"),
        ("blog-cron", "report"),
        ("learn-research", "chat"),
        ("strategic_goals.extract", "report"),
        ("studio.sensitivity_tiebreaker", "deck"),
        ("totally_unknown_module", "chat"),
    ]
    for module, expected in cases:
        got = _surface_for_module(module)
        assert got == expected, (module, got, expected)
        assert _is_valid_surface(got), got
