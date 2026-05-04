"""Phase 15.2 — tension_detector unit tests.

Pinned scope:
  - cross-session input MUST raise CrossSessionTensionInputError immediately
    (decision #7: single-context only, no cross-context detection until
    Phase 14 ships the Privacy Wall).
  - happy-path: well-formed inputs produce a tensions list with the
    expected schema (id / description / contradiction_source / severity).
  - LLM fallback parsing: code-fenced JSON, malformed source labels,
    out-of-range severities, non-list evidence — all normalised cleanly.
  - empty result: zero detected tensions still emits an audit entry with
    `tensions: []` so synthesis can proceed.
  - Adapter is fully stubbed; no live LLM, no Mongo.

Run:
    pytest /app/backend/tests/test_solva_v2_tension_detector.py -v
"""
from __future__ import annotations

import os
import sys
import uuid
from typing import Any, Dict, List

import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.solva_v2.engines import tension_detector as td  # noqa: E402
from services.solva_v2.engines.tension_detector import (  # noqa: E402
    CrossSessionTensionInputError, ENGINE_VERSION, SURFACE,
)


# ---------------------------------------------------------------------------
# Adapter stub (mirrors the engines_unit pattern)
# ---------------------------------------------------------------------------
class _StubResult:
    def __init__(self, text: str, surface: str, engine: str, layer: str, turn_id: str,
                 engine_version: str, attempt: int):
        self.text = text
        self.model = "stub"
        self.provider = "stub"
        self.tier_requested = "fast"
        self.tier_served = "fast"
        self.latency_ms = 1
        self.synisense_run_id = f"syn-{uuid.uuid4().hex[:8]}"
        self.input_hash = "deadbeef"
        self.mode = "live"
        self.validation = None
        self.reasoning_audit_entry = {
            "id": str(uuid.uuid4()),
            "turn_id": turn_id,
            "layer": layer,
            "engine": engine,
            "engine_version": engine_version,
            "input_hash": "deadbeef",
            "output": {
                "text_length": len(text),
                "response_mode": "live",
                "tier_requested": "fast",
                "tier_served": "fast",
                "quota_downgraded": False,
                "attempt": attempt,
            },
            "tier_labels": [],
            "latency_ms": 1,
            "model": "stub",
            "provider": "stub",
            "created_at": "2026-05-04T05:00:00+00:00",
            "synisense_run_id": self.synisense_run_id,
            "shield_required": True,
            "shield_bypassed_reason": None,
        }


def _stub(text: str):
    async def fn(**kwargs):
        return _StubResult(
            text=text, surface=kwargs["surface"], engine=kwargs["engine"],
            layer=kwargs["layer"], turn_id=kwargs["turn_id"],
            engine_version=kwargs.get("engine_version") or "tension_detector@1.0",
            attempt=1,
        )
    return fn


@pytest.fixture
def session() -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "intent": "Q3 missed because of churn timing or pricing pressure?",
    }


# ---------------------------------------------------------------------------
# Engine identity
# ---------------------------------------------------------------------------
def test_engine_version_is_1_0():
    assert ENGINE_VERSION == "tension_detector@1.0"
    assert SURFACE == "solve_v2.tension_detector"


# ---------------------------------------------------------------------------
# CRITICAL: cross-session guard
# ---------------------------------------------------------------------------
class TestCrossSessionGuard:
    """Decision #7 hard contract — single-context only.

    Mixed-session inputs MUST raise BEFORE the LLM is called.
    """

    @pytest.mark.asyncio
    async def test_user_turn_from_other_session_raises(self, monkeypatch, session):
        # Stub never gets called — the guard fires first.
        called = {"flag": False}

        async def llm_should_not_run(**kwargs):
            called["flag"] = True
            return _StubResult("{}", **{k: v for k, v in kwargs.items()
                                         if k in ("surface", "engine", "layer",
                                                  "turn_id", "engine_version")},
                               attempt=1)
        monkeypatch.setattr(
            "services.solva_v2.engines.llm_adapter_proxy.shielded_call",
            llm_should_not_run,
        )

        # User turn from a DIFFERENT session.
        foreign_turn = {
            "role": "user", "text": "leaked from another session",
            "session_id": str(uuid.uuid4()),  # different from session["id"]
        }
        with pytest.raises(CrossSessionTensionInputError) as excinfo:
            await td.run(
                session=session, turn_id="t1",
                user_turns=[foreign_turn],
                triangulation_output={"comparables": []},
                candidate_hypotheses=[],
            )
        assert "expected session_id" in str(excinfo.value)
        assert called["flag"] is False  # LLM must NOT have been called

    @pytest.mark.asyncio
    async def test_comparable_from_other_session_raises(self, monkeypatch, session):
        called = {"flag": False}

        async def llm_should_not_run(**kwargs):
            called["flag"] = True
        monkeypatch.setattr(
            "services.solva_v2.engines.llm_adapter_proxy.shielded_call",
            llm_should_not_run,
        )
        foreign_comparable = {"id": "cmp-1", "label": "Foreign comparable",
                              "session_id": str(uuid.uuid4())}
        with pytest.raises(CrossSessionTensionInputError):
            await td.run(
                session=session, turn_id="t1",
                user_turns=[],
                triangulation_output={"comparables": [foreign_comparable]},
                candidate_hypotheses=[],
            )
        assert called["flag"] is False

    @pytest.mark.asyncio
    async def test_candidate_from_other_session_raises(self, monkeypatch, session):
        async def llm_should_not_run(**kwargs):
            raise AssertionError("LLM must not be called")
        monkeypatch.setattr(
            "services.solva_v2.engines.llm_adapter_proxy.shielded_call",
            llm_should_not_run,
        )
        foreign_candidate = {"hypothesis": "...", "session_id": "other"}
        with pytest.raises(CrossSessionTensionInputError):
            await td.run(
                session=session, turn_id="t1",
                user_turns=[], triangulation_output={"comparables": []},
                candidate_hypotheses=[foreign_candidate],
            )

    @pytest.mark.asyncio
    async def test_inputs_without_session_id_field_are_accepted(self, monkeypatch, session):
        """Inputs that don't declare session_id at all are accepted (they
        are inline content with no provenance to verify)."""
        monkeypatch.setattr(
            "services.solva_v2.engines.llm_adapter_proxy.shielded_call",
            _stub('{"tensions": []}'),
        )
        result = await td.run(
            session=session, turn_id="t1",
            user_turns=[{"role": "user", "text": "no session_id key"}],
            triangulation_output={"comparables": [{"label": "no session_id"}]},
            candidate_hypotheses=[{"hypothesis": "no session_id"}],
        )
        assert result["output"]["tension_count"] == 0


# ---------------------------------------------------------------------------
# Happy path + parser variants
# ---------------------------------------------------------------------------
class TestHappyPath:
    @pytest.mark.asyncio
    async def test_two_tensions_normalised_correctly(self, monkeypatch, session):
        body = (
            '{"tensions": ['
            '{"description": "User says churn timing; comparable bank found pricing pressure", '
            '"contradiction_source": "user_vs_comparable", "severity": "high", '
            '"evidence": ["user turn 2: timing", "comparable A: pricing"]},'
            '{"description": "Two comparables disagree on pricing elasticity", '
            '"contradiction_source": "comparable_vs_comparable", "severity": "medium", '
            '"evidence": []}'
            ']}'
        )
        monkeypatch.setattr(
            "services.solva_v2.engines.llm_adapter_proxy.shielded_call",
            _stub(body),
        )
        result = await td.run(
            session=session, turn_id="t1",
            user_turns=[{"role": "user", "text": "churn timing was the cause"}],
            triangulation_output={"comparables": [
                {"id": "A", "label": "Mid-cap bank", "thesis": "pricing pressure"},
            ]},
            candidate_hypotheses=[
                {"hypothesis": "churn timing", "tentative_tier_hint": "user_assertion"},
                {"hypothesis": "pricing pressure", "tentative_tier_hint": "comparable"},
            ],
        )
        out = result["output"]
        assert out["tension_count"] == 2
        assert {t["contradiction_source"] for t in out["tensions"]} == {
            "user_vs_comparable", "comparable_vs_comparable",
        }
        assert all(t["id"] for t in out["tensions"])
        assert out["sources_distribution"] == {
            "user_vs_comparable": 1, "comparable_vs_comparable": 1,
        }
        # Severities preserved + valid.
        sevs = [t["severity"] for t in out["tensions"]]
        assert "high" in sevs and "medium" in sevs

    @pytest.mark.asyncio
    async def test_zero_tensions_still_records_audit(self, monkeypatch, session):
        monkeypatch.setattr(
            "services.solva_v2.engines.llm_adapter_proxy.shielded_call",
            _stub('{"tensions": []}'),
        )
        result = await td.run(
            session=session, turn_id="t1",
            user_turns=[], triangulation_output={"comparables": []},
            candidate_hypotheses=[],
        )
        assert result["output"]["tension_count"] == 0
        assert result["output"]["tensions"] == []
        # Audit entry still emitted so the orchestrator + state machine
        # see that the tension_detector engine ran.
        ae = result["audit_entry"]
        assert ae["engine"] == "tension_detector"
        assert ae["engine_version"] == "tension_detector@1.0"
        assert ae["layer"] == "hypothesis"
        assert ae["output"]["tension_count"] == 0
        assert ae["output"]["tensions"] == []
        assert ae["shield_required"] is True
        assert ae["synisense_run_id"]


class TestParserResilience:
    @pytest.mark.asyncio
    async def test_invalid_severity_defaults_to_medium(self, monkeypatch, session):
        body = (
            '{"tensions": [{"description": "x is contradicted by y", '
            '"contradiction_source": "user_vs_corpus", "severity": "URGENT", '
            '"evidence": []}]}'
        )
        monkeypatch.setattr(
            "services.solva_v2.engines.llm_adapter_proxy.shielded_call",
            _stub(body),
        )
        r = await td.run(session=session, turn_id="t1",
                         user_turns=[], triangulation_output=None,
                         candidate_hypotheses=None)
        assert r["output"]["tensions"][0]["severity"] == "medium"

    @pytest.mark.asyncio
    async def test_invalid_source_falls_back_to_user_vs_comparable(self, monkeypatch, session):
        body = (
            '{"tensions": [{"description": "real tension", '
            '"contradiction_source": "made_up_label", "severity": "low"}]}'
        )
        monkeypatch.setattr(
            "services.solva_v2.engines.llm_adapter_proxy.shielded_call",
            _stub(body),
        )
        r = await td.run(session=session, turn_id="t1",
                         user_turns=[], triangulation_output=None,
                         candidate_hypotheses=None)
        assert r["output"]["tensions"][0]["contradiction_source"] == "user_vs_comparable"

    @pytest.mark.asyncio
    async def test_code_fenced_json_parses(self, monkeypatch, session):
        body = (
            '```json\n{"tensions": [{"description": "fenced", '
            '"contradiction_source": "user_vs_user", "severity": "low"}]}\n```'
        )
        monkeypatch.setattr(
            "services.solva_v2.engines.llm_adapter_proxy.shielded_call",
            _stub(body),
        )
        r = await td.run(session=session, turn_id="t1",
                         user_turns=[], triangulation_output=None,
                         candidate_hypotheses=None)
        assert r["output"]["tension_count"] == 1
        assert r["output"]["tensions"][0]["contradiction_source"] == "user_vs_user"

    @pytest.mark.asyncio
    async def test_unparseable_response_yields_zero_tensions(self, monkeypatch, session):
        monkeypatch.setattr(
            "services.solva_v2.engines.llm_adapter_proxy.shielded_call",
            _stub("the model went wandering and produced prose"),
        )
        r = await td.run(session=session, turn_id="t1",
                         user_turns=[], triangulation_output=None,
                         candidate_hypotheses=None)
        assert r["output"]["tension_count"] == 0
        assert r["output"]["tensions"] == []

    @pytest.mark.asyncio
    async def test_empty_description_dropped(self, monkeypatch, session):
        body = (
            '{"tensions": ['
            '{"description": "real one", "contradiction_source": "user_vs_corpus", "severity": "high"},'
            '{"description": "  ", "contradiction_source": "user_vs_corpus", "severity": "high"},'
            '{"description": "", "contradiction_source": "user_vs_corpus", "severity": "high"}'
            ']}'
        )
        monkeypatch.setattr(
            "services.solva_v2.engines.llm_adapter_proxy.shielded_call",
            _stub(body),
        )
        r = await td.run(session=session, turn_id="t1",
                         user_turns=[], triangulation_output=None,
                         candidate_hypotheses=None)
        assert r["output"]["tension_count"] == 1


class TestStateMachineIntegration:
    """Confirm the state machine accepts a hypothesis-layer audit entry
    from the tension_detector and advances grounding -> hypothesis ->
    synthesis only when tension_detector has fired."""

    def test_simulate_hypothesis_flow_includes_hypothesis_layer(self):
        from services.solva_v2.state_machine import (
            LAYER_ORDER_BY_SUBMODULE, next_layer,
        )
        flow = LAYER_ORDER_BY_SUBMODULE["simulate_hypothesis"]
        assert flow == ["framing", "grounding", "hypothesis", "synthesis", "reflection"]

        # Grounding -> hypothesis: requires triangulation + candidate_generation.
        s = {
            "submodule": "simulate_hypothesis",
            "layer": "grounding",
            "turns": [{"role": "user", "text": "x"}, {"role": "user", "text": "y"}],
            "reasoning_audit_log": [
                {"layer": "grounding", "engine": "triangulation"},
                {"layer": "grounding", "engine": "candidate_generation"},
            ],
            "synthesis": None,
        }
        assert next_layer(s) == "hypothesis"

        # Hypothesis -> synthesis: requires tension_detector.
        s_hypo = {
            "submodule": "simulate_hypothesis",
            "layer": "hypothesis",
            "turns": [{"role": "user", "text": "x"}, {"role": "user", "text": "y"}],
            "reasoning_audit_log": [
                {"layer": "hypothesis", "engine": "tension_detector"},
            ],
            "synthesis": None,
        }
        assert next_layer(s_hypo) == "synthesis"

        # Hypothesis without tension_detector audit: stays.
        s_nope = {**s_hypo, "reasoning_audit_log": []}
        assert next_layer(s_nope) is None

    def test_seek_clarity_flow_skips_hypothesis_layer(self):
        from services.solva_v2.state_machine import LAYER_ORDER_BY_SUBMODULE
        flow = LAYER_ORDER_BY_SUBMODULE["seek_clarity"]
        assert "hypothesis" not in flow
