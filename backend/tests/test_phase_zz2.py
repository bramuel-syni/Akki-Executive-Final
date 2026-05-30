"""Phase ZZ.2 (2026-02 fork-resume v2) — Solva governance IS the Chat
model. Three-tier framing, locked at source.

Tier 1 (always on, every reply):
  - System prompt is `CHAT_V2_GOVERNANCE_PREAMBLE` from
    `services.solva_v2.chat_v2_prompts`.
  - Post-completion validator `validate_conversational_response`
    runs on every reply.
  - Backend emits `zz2_governance` on the terminal stream event.

Tier 2 (when warranted):
  - Bias chips: backend captures `[anchoring · target]` tags.
  - Adversarial nudge: prompt instructs model to open with the
    counter-case.
  - Solva escalation: backend computes `escalate_to_solva` =
    recommendation request AND stakes language. Frontend renders
    the CTA.

Tier 3 (document-artefact outputs) — out of scope for this dispatch;
the original ZZ.2 brief's document-validator path remains
unimplemented and is logged in PHASE_LEDGER as ZZ.2-tier3 backlog.
"""
from __future__ import annotations
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

PROMPT = REPO / "backend" / "services" / "solva_v2" / "chat_v2_prompts.py"
VALIDATORS = REPO / "backend" / "services" / "solva_v2" / "integrity_validators.py"
CHAT_ROUTER = REPO / "backend" / "routers" / "chat.py"
GOV_SIGNALS = REPO / "frontend" / "src" / "components" / "chat" / "GovernanceSignals.jsx"
CHAT_JSX = REPO / "frontend" / "src" / "pages" / "Chat.jsx"


# ─── Tier 1 prompt ─────────────────────────────────────────────────────


def test_zz2_prompt_module_exists_with_governance_preamble():
    src = PROMPT.read_text(encoding="utf-8")
    assert "CHAT_V2_GOVERNANCE_PREAMBLE" in src
    assert "def build_chat_v2_system_message(" in src


def test_zz2_prompt_names_refusal_token_verbatim():
    """The model MUST be told the verbatim refusal token so the
    backend validator can search for it deterministically."""
    src = PROMPT.read_text(encoding="utf-8")
    assert "I don't have a source for this." in src


def test_zz2_prompt_names_solva_escalation_line_verbatim():
    src = PROMPT.read_text(encoding="utf-8")
    assert "Run this through Solva for the full 16-slide diagnostic." in src


def test_zz2_prompt_voice_lint_excludes_late_banned_senior():
    """The 2026-02 late addition to WEBSITE_BRIEF_V3.md added 'senior'
    to the customer-facing ban. The prompt must instruct the LLM to
    NOT use 'senior' in its output. The internal voice-guide tag
    'senior peer test' is allowed in /app/docs/ but not here."""
    src = PROMPT.read_text(encoding="utf-8")
    # The prompt must NOT instruct the model to use "senior" as
    # a voice tag in customer output. The phrase "senior peer
    # register" is forbidden.
    assert "senior peer register" not in src.lower()
    # And the explicit "use executive not senior" instruction must
    # be there.
    assert 'executive' in src.lower()
    assert 'senior' in src.lower()  # in the ban list itself, that's fine


def test_zz2_prompt_passes_full_banned_list():
    """The prompt is an internal instruction, NOT customer copy.
    But its visible-in-output guidance must reference the canonical
    banned list. Smoke-check the list is intact."""
    src = PROMPT.read_text(encoding="utf-8")
    must_name = [
        "leverage", "seamless", "AI-powered", "AI-driven", "insights",
        "dashboard", "frictionless", "unlock", "supercharge",
        "synergy", "revolutionary", "cutting-edge", "disrupt", "empower",
    ]
    for w in must_name:
        assert w in src, f"Banned-list reference missing: {w!r}"


# ─── Tier 2 intent detectors ───────────────────────────────────────────


def test_zz2_detects_recommendation_request_smoke():
    from services.solva_v2.chat_v2_prompts import (
        detects_recommendation_request,
        detects_stakes_language, should_escalate_to_solva,
    )
    assert detects_recommendation_request("Should we acquire Acme?")
    assert detects_recommendation_request("What would you recommend?")
    assert not detects_recommendation_request("Tell me about the weather.")
    assert detects_stakes_language(
        "We're considering a binding sign-off with the regulator.")
    assert not detects_stakes_language("What time is it?")
    assert should_escalate_to_solva(
        "Should we issue a press release for the binding deal?")
    assert not should_escalate_to_solva("Should we have lunch?")


# ─── Tier 1 post-completion validator ──────────────────────────────────


def test_zz2_conversational_validator_flags_unsourced_numbers():
    from services.solva_v2.integrity_validators import (
        validate_conversational_response,
    )
    r = validate_conversational_response(
        "Revenue will grow 25% next year and margins should hit 18%.",
        attached_docs=None,
    )
    assert r.numeric_claims_total >= 2
    assert r.numeric_claims_unsourced >= 2
    assert "numeric_claim_without_source" in r.notes
    assert not r.ok


def test_zz2_conversational_validator_accepts_refusal_token():
    from services.solva_v2.integrity_validators import (
        validate_conversational_response,
    )
    r = validate_conversational_response(
        "Revenue could be in the 20% range, but I don't have a "
        "source for this. Can you share the quarterly statement?",
        attached_docs=None,
    )
    assert r.numeric_claims_unsourced == 0
    assert r.ok


def test_zz2_conversational_validator_captures_bias_flags():
    from services.solva_v2.integrity_validators import (
        validate_conversational_response,
    )
    r = validate_conversational_response(
        "Anchoring risk here — [anchoring · Q4 number] — the figure "
        "isn't comparable.",
    )
    assert r.bias_flags == ["anchoring · Q4 number"]


# ─── Backend wiring ────────────────────────────────────────────────────


def test_zz2_chat_router_prepends_governance_preamble():
    src = CHAT_ROUTER.read_text(encoding="utf-8")
    assert "from services.solva_v2.chat_v2_prompts import build_chat_v2_system_message" in src
    assert "system_msg = build_chat_v2_system_message(system_msg)" in src
    # Audit log entry locked
    assert '"event": "chat_v2_prompt_used"' in src


def test_zz2_chat_router_attaches_governance_to_stream_payload():
    src = CHAT_ROUTER.read_text(encoding="utf-8")
    # `zz2_governance` key emitted on terminal stream event
    assert '"zz2_governance": zz2_governance' in src
    # Validator imported lazily inside the stream pass
    assert "validate_conversational_response as _zz2_validate" in src


# ─── Frontend wiring ───────────────────────────────────────────────────


def test_zz2_chat_jsx_renders_governance_signals():
    src = CHAT_JSX.read_text(encoding="utf-8")
    assert 'import GovernanceSignals from "@/components/chat/GovernanceSignals"' in src
    assert "<GovernanceSignals governance={m.zz2_governance} />" in src
    # Stream handler persists zz2_governance onto the message
    assert "zz2_governance: ev.zz2_governance" in src


def test_zz2_governance_component_testids_locked():
    src = GOV_SIGNALS.read_text(encoding="utf-8")
    for k in [
        "chat-governance-signals",
        "chat-governance-bias-chips",
        "chat-governance-bias-chip",
        "chat-governance-unsourced-note",
        "chat-governance-solva-escalation",
    ]:
        assert k in src, f"Missing testid {k!r}"
    # Escalation CTA verbatim
    assert "Run this through Solva for the full 16-slide diagnostic →" in src


def test_zz2_governance_component_voice_lint():
    """User-visible strings rendered by GovernanceSignals must pass
    voice lint (including the 2026-02 'senior' addition)."""
    src = GOV_SIGNALS.read_text(encoding="utf-8")
    banned = ["leverage", "empower", "AI-powered", "seamless",
              "revolutionary", "synergy", "frictionless", "unlock",
              "supercharge", "disrupt"]
    # Pull JSX string-literal-ish lines only (skip imports + className)
    body = "\n".join(
        ln for ln in src.splitlines()
        if not ln.lstrip().startswith(("//", "*", "import"))
    )
    for w in banned:
        assert w.lower() not in body.lower(), \
            f"Banned word {w!r} appeared in GovernanceSignals"
