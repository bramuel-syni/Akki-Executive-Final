"""Phase E guardrails tier — jailbreak / therapy / coaching classifiers.

Brings Phase D parity with the legacy `routers/solva_v2.py` safety
ladder. Three Shield-routed classifiers + a router-level orchestrator
that decides between three outcomes:

  * `ok`            — input is substantive executive content, proceed.
  * `blocked_soft`  — input is borderline (therapy/coaching tone, mild
                       hostility, low-quality but not abusive); proceed
                       with an empathetic but redirecting coach reply.
  * `blocked_hard`  — input is hostile, abusive, jailbreak-attempt, or
                       clearly off-product (e.g. "Ignore previous
                       instructions and …"). Refuse outright with a
                       templated coach voice copy.

Each classifier is a thin wrapper around `shield.client.invoke()` with
a dedicated `solva.guardrails.*` purpose. The classifiers run
in PARALLEL (asyncio.gather) on every framing + every answer.

All user-visible strings ("blocked_hard_template" / "blocked_soft_template")
go through the single-voice invariant scanner — same contract as Layer 3
voice tier.
"""
from .classifiers import (
    run_guardrail_ladder,
    GuardrailOutcome,
    GuardrailDecision,
    BLOCKED_HARD_TEMPLATES,
    BLOCKED_SOFT_TEMPLATES,
)

__all__ = [
    "run_guardrail_ladder",
    "GuardrailOutcome",
    "GuardrailDecision",
    "BLOCKED_HARD_TEMPLATES",
    "BLOCKED_SOFT_TEMPLATES",
]
