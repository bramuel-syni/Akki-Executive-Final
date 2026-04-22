"""
LLM Proxy + Synisense Shielding (mock) — AKKI M0.

BRD v3.0 §17–18: every outbound LLM call MUST route through Synisense for
identity shielding. Synisense replaces entity/personal identifiers with opaque
refs, dispatches to the LLM, rehydrates refs in the response.

Mock behaviour for M0:
- `shield_payload()` scans for obvious PII-ish strings and swaps them for
  placeholders.
- `call_llm()` logs the shield map and returns a mocked structured response.
- A real Synisense service will replace the mock starting at M5.
"""
from __future__ import annotations

import os
import re
import uuid
from typing import Any, Dict, Optional, Tuple

AKKI_SYSTEM_PROMPT = (
    "You are AKKI, an intelligence layer for non-executive directors and "
    "operating executives. You ground every factual claim in the caller's "
    "verified data. You never fabricate numbers, sources, or evidence. "
    "When data trust is Weak, you flag it explicitly. You speak with the "
    "gravitas of a board advisor — concise, direct, evidence-led."
)

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
_URL_RE = re.compile(r"https?://\S+")


def shield_payload(text: str) -> Tuple[str, Dict[str, str]]:
    """Replace obvious PII strings with opaque refs. Returns (shielded, map)."""
    shield_map: Dict[str, str] = {}
    def _swap_email(m: re.Match) -> str:
        ref = f"<ident:{uuid.uuid4().hex[:8]}>"
        shield_map[ref] = m.group(0)
        return ref
    def _swap_url(m: re.Match) -> str:
        ref = f"<url:{uuid.uuid4().hex[:8]}>"
        shield_map[ref] = m.group(0)
        return ref
    shielded = _EMAIL_RE.sub(_swap_email, text)
    shielded = _URL_RE.sub(_swap_url, shielded)
    return shielded, shield_map


def rehydrate(text: str, shield_map: Dict[str, str]) -> str:
    """Reverse the shield map on a response."""
    out = text
    for ref, original in shield_map.items():
        out = out.replace(ref, original)
    return out


def build_prompt_layers(
    module: str,
    user_query: str,
    context_object: Optional[Dict[str, Any]] = None,
    session_context: Optional[Dict[str, Any]] = None,
    data_trust: Optional[Dict[str, Any]] = None,
    system_override: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "layer_1_system": system_override or AKKI_SYSTEM_PROMPT,
        "layer_2_context_object": context_object or {"note": "Context object empty (pre-M2)"},
        "layer_3_module": module,
        "layer_4_session_context": session_context or {},
        "layer_5_data_trust": data_trust or {"overall": "unrated"},
        "layer_6_user_query": user_query,
    }


async def call_llm(
    module: str,
    user_query: str,
    context_object: Optional[Dict[str, Any]] = None,
    session_context: Optional[Dict[str, Any]] = None,
    data_trust: Optional[Dict[str, Any]] = None,
    system_override: Optional[str] = None,
) -> Dict[str, Any]:
    """M0 scaffolding: shields payload, returns mocked structured response.

    Contract matches Synisense-shielded LLM proxy — real implementation lands
    at M5 and swaps the mock for an Anthropic call via emergentintegrations.
    """
    layers = build_prompt_layers(
        module=module, user_query=user_query, context_object=context_object,
        session_context=session_context, data_trust=data_trust, system_override=system_override,
    )
    shielded_query, shield_map = shield_payload(user_query)
    mocked = (
        f"[AKKI mock — module={module}] "
        f"I received your shielded query: \"{shielded_query[:140]}\". "
        f"Running in M0 scaffolding mode. Real LLM via Synisense proxy wires in at M5 "
        f"(provider={'anthropic' if os.environ.get('EMERGENT_LLM_KEY') else 'none'})."
    )
    response = rehydrate(mocked, shield_map)

    return {
        "layers": layers,
        "response": response,
        "mode": "mock-scaffolding",
        "sources": [],
        "shielding": {
            "identifiers_masked": len(shield_map),
            "shielded_by": "mock-synisense",
        },
        "synisense_verified": False,
        "synisense_verification_id": None,
    }
