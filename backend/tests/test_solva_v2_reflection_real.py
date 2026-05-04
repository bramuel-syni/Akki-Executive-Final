"""Phase 15.3 — Reflection engine unit + light-integration tests.

Covers:
  * LOCKED_QUESTIONS is exactly the 3 questions specified by decision #14.
  * `build_system_prompt` renders the synthesis body + intent and tier
    rules verbatim.
  * Engine version is `reflection@1.0` (no placeholder).
  * Module surface is `solve_v2.reflection`.
  * The exported `LOCKED_QUESTIONS` is a list of 3 strings.
  * No first-person opinion phrasing in the system prompt itself
    (Phase 15.3.5 preview — keeps prompts disciplined ahead of the
    no-opinion principle work).

End-to-end coverage of the reflection layer firing inside a session is
already provided by `test_solva_v2_shield_invariant.py::
test_invariant_holds_across_full_session` which drives 3 turns through
a full Seek Clarity session and asserts `engine='reflection'` is
present in the audit log.
"""
from services.solva_v2.engines import reflection


# Exact text per Phase 15.3 decision #14. Locked.
EXPECTED = [
    "What could be wrong about this diagnosis?",
    "What would change the answer in 30 days?",
    "What is the first sign you should watch for?",
]


def test_locked_questions_are_exact_and_in_order():
    assert reflection.LOCKED_QUESTIONS == EXPECTED


def test_engine_metadata_is_15_3():
    assert reflection.ENGINE == "reflection"
    assert reflection.ENGINE_VERSION == "reflection@1.0"
    assert reflection.SURFACE == "solve_v2.reflection"


def test_locked_questions_count_is_three():
    assert len(reflection.LOCKED_QUESTIONS) == 3
    for q in reflection.LOCKED_QUESTIONS:
        assert isinstance(q, str)
        assert q.endswith("?")


def test_build_system_prompt_includes_intent_and_synthesis():
    prompt = reflection.build_system_prompt(
        intent="Test intent body.",
        synthesis_body="Test diagnosis body.",
    )
    assert "REFLECTION" in prompt
    assert "Test intent body." in prompt
    assert "Test diagnosis body." in prompt
    # Tier rules must be enumerated explicitly — synthesis writers rely
    # on these to label every assertive sentence.
    for tier in (
        "corpus", "comparable", "domain_prior", "user_assertion", "speculation",
    ):
        assert tier in prompt, f"tier {tier!r} missing from prompt"
    # 1–3 sentences is a hard cap.
    assert "1–3 sentences" in prompt or "1 to 3 sentences" in prompt


def test_build_system_prompt_includes_tier_marker_format():
    prompt = reflection.build_system_prompt(intent="x", synthesis_body="y")
    # Each assertive sentence must end with [T:tier]. The instruction
    # text must show the format so the model produces it.
    assert "[T:" in prompt


def test_system_prompt_no_first_person_opinion_language():
    """Phase 15.3.5 preview — the reflection system prompt itself must
    not model first-person opinion. Solva is an instrument, not an
    interlocutor."""
    prompt = reflection.build_system_prompt(intent="x", synthesis_body="y")
    forbidden = (
        "i think", "i believe", "in my view", "personally",
        "from my perspective", "my opinion",
    )
    lowered = prompt.lower()
    for phrase in forbidden:
        assert phrase not in lowered, \
            f"reflection system prompt contains forbidden phrase {phrase!r}"


def test_run_one_signature_is_stable():
    """Make sure the public function signature is the one the
    orchestrator wires. Defensive — catches drift if someone refactors."""
    import inspect
    sig = inspect.signature(reflection.run_one)
    expected = {
        "session", "turn_id", "question", "question_index",
        "intent", "synthesis_body", "account_id",
    }
    assert set(sig.parameters.keys()) == expected, \
        f"run_one signature drift; got {set(sig.parameters.keys())}"


def test_run_signature_is_stable():
    import inspect
    sig = inspect.signature(reflection.run)
    expected = {"session", "turn_id", "intent", "synthesis_body", "account_id"}
    assert set(sig.parameters.keys()) == expected, \
        f"run signature drift; got {set(sig.parameters.keys())}"
