"""Phase 15.1 — layer state-machine fuzz + transition tests.

The state machine in services/solva_v2/state_machine.py is pure (no IO),
so every test here is sync and runs without Mongo. The fuzz pass asserts
that for any random combination of (layer, audit, turns) the machine
either (a) returns None / a valid layer, or (b) raises
InvalidLayerTransition — it never returns garbage and never crashes.

Run:
    pytest /app/backend/tests/test_solva_v2_state_machine.py -v
"""
from __future__ import annotations

import os
import random
import sys

import pytest
from dotenv import load_dotenv

# load .env before any backend imports — services.solva_v2.__init__ pulls in
# llm_adapter which imports core, which requires MONGO_URL at import time.
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
load_dotenv("/app/backend/.env")

from services.solva_v2.state_machine import (  # noqa: E402
    GROUNDING_REQUIRED_ENGINES,
    InvalidLayerTransition,
    LAYERS,
    TERMINAL_LAYER,
    can_post_turn,
    is_terminal,
    next_layer,
)


# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------
ALL_ENGINES = ("triangulation", "candidate_generation", "refusal",
               "probability_weighting", "validator", "llm_primary")

VALID_BANDS = ("Unlikely", "Possible", "Likely", "High-conviction")


def _user_turns(n: int):
    return [{"role": "user", "text": f"u{i}"} for i in range(n)]


def _audit(layer: str, engines):
    return [{"layer": layer, "engine": e} for e in engines]


def _synthesis_complete(claims_count=2, all_banded=True, verdict="validated"):
    claims = []
    for i in range(claims_count):
        c = {"text": f"claim {i}", "tier": "corpus"}
        if all_banded:
            c["confidence_band"] = VALID_BANDS[i % len(VALID_BANDS)]
        claims.append(c)
    return {
        "claims": claims,
        "validation": {"verdict": verdict} if verdict else {},
    }


# ---------------------------------------------------------------------------
# Static transition tests — the documented happy path & explicit guards
# ---------------------------------------------------------------------------
class TestTransitionTable:
    def test_layer_order_locked(self):
        # Phase 15.2: hypothesis layer added between grounding and synthesis
        # (used only by simulate_hypothesis sub-module). Other sub-modules
        # skip it via LAYER_ORDER_BY_SUBMODULE.
        assert LAYERS == ["framing", "grounding", "hypothesis", "synthesis", "reflection"]
        assert TERMINAL_LAYER == "reflection"

    def test_grounding_required_engines_locked(self):
        # Drift guard. If 15.2 adds a fifth required engine the test must
        # fail loudly so the orchestrator and the state machine stay in sync.
        assert GROUNDING_REQUIRED_ENGINES == frozenset({
            "triangulation", "candidate_generation",
        })

    def test_framing_holds_with_no_user_turns(self):
        s = {"layer": "framing", "turns": [], "reasoning_audit_log": []}
        assert next_layer(s) is None

    def test_framing_advances_on_first_user_turn(self):
        s = {"layer": "framing", "turns": _user_turns(1), "reasoning_audit_log": []}
        assert next_layer(s) == "grounding"

    def test_grounding_holds_without_required_engines(self):
        s = {
            "layer": "grounding",
            "turns": _user_turns(2),
            "reasoning_audit_log": _audit("grounding", ["triangulation"]),
        }
        assert next_layer(s) is None

    def test_grounding_holds_without_enough_turns(self):
        s = {
            "layer": "grounding",
            "turns": _user_turns(1),
            "reasoning_audit_log": _audit(
                "grounding", ["triangulation", "candidate_generation"],
            ),
        }
        assert next_layer(s) is None

    def test_grounding_advances_with_engines_and_turns(self):
        s = {
            "layer": "grounding",
            "turns": _user_turns(2),
            "reasoning_audit_log": _audit(
                "grounding", ["triangulation", "candidate_generation"],
            ),
        }
        assert next_layer(s) == "synthesis"

    def test_synthesis_holds_without_claims(self):
        s = {
            "layer": "synthesis",
            "turns": _user_turns(3),
            "reasoning_audit_log": [],
            "synthesis": {"claims": [], "validation": {"verdict": "validated"}},
        }
        assert next_layer(s) is None

    def test_synthesis_holds_without_validator_verdict(self):
        synth = _synthesis_complete(verdict=None)
        s = {
            "layer": "synthesis",
            "turns": _user_turns(3),
            "reasoning_audit_log": [],
            "synthesis": synth,
        }
        assert next_layer(s) is None

    def test_synthesis_holds_without_all_bands(self):
        synth = _synthesis_complete(all_banded=False)
        s = {
            "layer": "synthesis",
            "turns": _user_turns(3),
            "reasoning_audit_log": [],
            "synthesis": synth,
        }
        assert next_layer(s) is None

    def test_synthesis_advances_when_complete(self):
        s = {
            "layer": "synthesis",
            "turns": _user_turns(3),
            "reasoning_audit_log": [],
            "synthesis": _synthesis_complete(),
        }
        assert next_layer(s) == "reflection"

    def test_reflection_is_terminal(self):
        s = {"layer": "reflection", "turns": _user_turns(3), "reasoning_audit_log": []}
        assert next_layer(s) is None
        assert is_terminal(s) is True

    def test_unknown_layer_raises(self):
        s = {"layer": "chaos", "turns": [], "reasoning_audit_log": []}
        with pytest.raises(InvalidLayerTransition):
            next_layer(s)


# ---------------------------------------------------------------------------
# can_post_turn / assert_can_post_turn
# ---------------------------------------------------------------------------
class TestCanPostTurn:
    def test_active_session_below_terminal_can_post(self):
        s = {"status": "active", "layer": "framing"}
        assert can_post_turn(s) is True

    def test_completed_session_cannot_post(self):
        s = {"status": "completed", "layer": "reflection"}
        assert can_post_turn(s) is False

    def test_abandoned_session_cannot_post(self):
        s = {"status": "abandoned", "layer": "framing"}
        assert can_post_turn(s) is False

    def test_active_at_terminal_layer_cannot_post(self):
        s = {"status": "active", "layer": "reflection"}
        assert can_post_turn(s) is False

    def test_missing_status_treated_as_inactive(self):
        s = {"layer": "framing"}
        assert can_post_turn(s) is False


# ---------------------------------------------------------------------------
# Fuzz pass — 100 random sessions, none should ever crash or return garbage.
# ---------------------------------------------------------------------------
class TestFuzz:
    """Coverage tracked via a counter dict that asserts the machine
    actually exercised every transition path during the fuzz run."""

    def _random_session(self, rng: random.Random):
        layer = rng.choice([*LAYERS, "chaos", ""])  # 2 / 6 invalid
        n_turns = rng.randint(0, 6)
        n_engines = rng.randint(0, 4)
        engines = rng.sample(ALL_ENGINES, k=min(n_engines, len(ALL_ENGINES)))
        audit_layer = rng.choice([*LAYERS, "chaos"])
        # Synthesis state varies independently.
        synth = None
        roll = rng.random()
        if roll < 0.25:
            synth = None
        elif roll < 0.50:
            synth = {"claims": [], "validation": {}}
        elif roll < 0.75:
            synth = _synthesis_complete(
                claims_count=rng.randint(1, 4),
                all_banded=rng.random() > 0.4,
                verdict=rng.choice(["validated", "qualified", None]),
            )
        else:
            # Pathological: claims with no band field at all.
            synth = {"claims": [{"text": "x", "tier": "corpus"}],
                     "validation": {"verdict": "validated"}}
        return {
            "layer": layer,
            "turns": _user_turns(n_turns),
            "reasoning_audit_log": _audit(audit_layer, engines),
            "synthesis": synth,
            "id": "fuzz-" + str(rng.randint(0, 1 << 32)),
        }

    # ------------------------------------------------------------------
    # Stratified pre-samples — guarantee at least one hit per coverage
    # bucket regardless of random seed, then layer randomized fuzz on top.
    # The brief required min 50 iterations; we run 16 stratified + 100
    # randomized = 116 iterations.
    # ------------------------------------------------------------------
    def _stratified_samples(self):
        """Hand-crafted shapes that exercise every coverage bucket exactly."""
        return [
            # raised_invalid x2
            {"layer": "chaos", "turns": [], "reasoning_audit_log": [],
             "synthesis": None, "id": "strat-1"},
            {"layer": "", "turns": [], "reasoning_audit_log": [],
             "synthesis": None, "id": "strat-2"},
            # returned_none x4 (one per layer where holding is valid)
            {"layer": "framing", "turns": [], "reasoning_audit_log": [],
             "synthesis": None, "id": "strat-3"},
            {"layer": "grounding", "turns": _user_turns(2),
             "reasoning_audit_log": _audit("grounding", ["triangulation"]),
             "synthesis": None, "id": "strat-4"},
            {"layer": "synthesis", "turns": _user_turns(3),
             "reasoning_audit_log": [],
             "synthesis": {"claims": [], "validation": {}}, "id": "strat-5"},
            {"layer": "reflection", "turns": _user_turns(3),
             "reasoning_audit_log": [], "synthesis": None, "id": "strat-6"},
            # advanced_grounding x4 (a few permutations)
            *[
                {"layer": "framing", "turns": _user_turns(n),
                 "reasoning_audit_log": [], "synthesis": None,
                 "id": f"strat-g-{n}"}
                for n in (1, 2, 3, 4)
            ],
            # advanced_synthesis x4 (vary engines and turn count)
            *[
                {
                    "layer": "grounding",
                    "turns": _user_turns(n),
                    "reasoning_audit_log": _audit(
                        "grounding", ["triangulation", "candidate_generation"],
                    ),
                    "synthesis": None,
                    "id": f"strat-s-{n}",
                }
                for n in (2, 3, 4, 5)
            ],
            # advanced_reflection x2 (vary verdict)
            {
                "layer": "synthesis", "turns": _user_turns(3),
                "reasoning_audit_log": [],
                "synthesis": _synthesis_complete(verdict="validated"),
                "id": "strat-r-1",
            },
            {
                "layer": "synthesis", "turns": _user_turns(3),
                "reasoning_audit_log": [],
                "synthesis": _synthesis_complete(verdict="qualified"),
                "id": "strat-r-2",
            },
        ]

    def test_fuzz_100plus_iterations_never_returns_garbage(self):
        rng = random.Random(15001)  # deterministic seed
        coverage = {
            "raised_invalid": 0,
            "returned_none": 0,
            "advanced_grounding": 0,
            "advanced_synthesis": 0,
            "advanced_reflection": 0,
        }
        all_samples = self._stratified_samples() + [
            self._random_session(rng) for _ in range(100)
        ]
        for s in all_samples:
            try:
                nxt = next_layer(s)
            except InvalidLayerTransition:
                coverage["raised_invalid"] += 1
                continue
            assert nxt is None or nxt in LAYERS, (
                f"next_layer returned non-None / non-LAYERS value: {nxt!r} on {s!r}"
            )
            if nxt is None:
                coverage["returned_none"] += 1
            elif nxt == "grounding":
                coverage["advanced_grounding"] += 1
            elif nxt == "synthesis":
                coverage["advanced_synthesis"] += 1
            elif nxt == "reflection":
                coverage["advanced_reflection"] += 1
        # Every coverage bucket must be hit at least once. The 16 stratified
        # samples guarantee this regardless of random seed.
        for k, v in coverage.items():
            assert v > 0, f"fuzz coverage gap: {k} never hit (this should be impossible)"
        # And the totals must add up to the full sample size.
        assert sum(coverage.values()) == len(all_samples)
        assert len(all_samples) >= 50, "brief required min 50 iterations"

    def test_fuzz_can_post_turn_never_crashes(self):
        """Independent fuzz on can_post_turn — it must accept arbitrary
        dicts (status / layer absent or junk) without raising."""
        rng = random.Random(15002)
        for _ in range(60):
            s = {
                "status": rng.choice(["active", "completed", "abandoned", None,
                                      "", "chaos"]),
                "layer": rng.choice([*LAYERS, "chaos", None]),
                "id": "x",
            }
            result = can_post_turn(s)
            assert isinstance(result, bool)
