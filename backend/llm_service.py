"""LLM proxy + mock-Synisense shielding (M5 — real Claude via Emergent Universal Key).

Shielding contract (unchanged from M0):
  - shield_payload() masks obvious PII
  - rehydrate() unmasks
  - Every outbound LLM call is routed through this module

At M5, the actual LLM call is wired via emergentintegrations (Claude Sonnet 4.5).
Real Synisense service replaces the mock via URL swap in a later build.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("akki.llm")

AKKI_SYSTEM_PROMPT = (
    "You are AKKI, an intelligence layer for non-executive directors and "
    "operating executives. You ground every factual claim in the caller's "
    "verified data. You never fabricate numbers, sources, or evidence. "
    "When data trust is Weak, you flag it explicitly. You speak with the "
    "gravitas of a board advisor — concise, direct, evidence-led. "
    "When you reference a document, cite it by doc_id in square brackets like [doc:abc123]."
)

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
_URL_RE = re.compile(r"https?://\S+")


def shield_payload(text: str) -> Tuple[str, Dict[str, str]]:
    shield_map: Dict[str, str] = {}
    def _swap_email(m):
        ref = f"<ident:{uuid.uuid4().hex[:8]}>"; shield_map[ref] = m.group(0); return ref
    def _swap_url(m):
        ref = f"<url:{uuid.uuid4().hex[:8]}>"; shield_map[ref] = m.group(0); return ref
    shielded = _EMAIL_RE.sub(_swap_email, text)
    shielded = _URL_RE.sub(_swap_url, shielded)
    return shielded, shield_map


def rehydrate(text: str, shield_map: Dict[str, str]) -> str:
    out = text
    for ref, original in shield_map.items():
        out = out.replace(ref, original)
    return out


def build_prompt_layers(
    module: str, user_query: str,
    context_object: Optional[Dict[str, Any]] = None,
    session_context: Optional[Dict[str, Any]] = None,
    data_trust: Optional[Dict[str, Any]] = None,
    system_override: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "layer_1_system": system_override or AKKI_SYSTEM_PROMPT,
        "layer_2_context_object": context_object or {"note": "Context object empty"},
        "layer_3_module": module,
        "layer_4_session_context": session_context or {},
        "layer_5_data_trust": data_trust or {"overall": "unrated"},
        "layer_6_user_query": user_query,
    }


def _assemble_user_prompt(layers: Dict[str, Any]) -> str:
    ctx_obj = json.dumps(layers["layer_2_context_object"], indent=2, default=str)
    sess = json.dumps(layers["layer_4_session_context"], indent=2, default=str)
    dt = json.dumps(layers["layer_5_data_trust"], indent=2, default=str)
    return (
        f"[MODULE] {layers['layer_3_module']}\n\n"
        f"[CONTEXT OBJECT]\n{ctx_obj}\n\n"
        f"[SESSION CONTEXT]\n{sess}\n\n"
        f"[DATA TRUST]\n{dt}\n\n"
        f"[USER REQUEST]\n{layers['layer_6_user_query']}"
    )


async def call_llm(
    module: str, user_query: str,
    context_object: Optional[Dict[str, Any]] = None,
    session_context: Optional[Dict[str, Any]] = None,
    data_trust: Optional[Dict[str, Any]] = None,
    system_override: Optional[str] = None,
    response_format: str = "text",   # "text" or "json"
) -> Dict[str, Any]:
    """Shielded call. Returns {layers, response, mode, sources, shielding, synisense_verified}.

    response_format="json" instructs Claude to return valid JSON only.
    """
    layers = build_prompt_layers(
        module=module, user_query=user_query,
        context_object=context_object, session_context=session_context,
        data_trust=data_trust, system_override=system_override,
    )
    user_prompt = _assemble_user_prompt(layers)
    shielded_prompt, shield_map = shield_payload(user_prompt)

    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    system_msg = layers["layer_1_system"]
    if response_format == "json":
        system_msg += (
            "\n\nIMPORTANT: Respond with valid JSON only. No prose, no code fences, "
            "no markdown. Just the JSON object."
        )

    if not emergent_key:
        return {
            "layers": layers, "mode": "no-key-fallback",
            "response": "[LLM unavailable — no key configured]",
            "sources": [],
            "shielding": {"identifiers_masked": len(shield_map), "shielded_by": "mock-synisense"},
            "synisense_verified": False,
            "synisense_verification_id": None,
        }

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        session_id = (session_context or {}).get("session_id") or str(uuid.uuid4())
        chat = LlmChat(
            api_key=emergent_key,
            session_id=session_id,
            system_message=system_msg,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        msg = UserMessage(text=shielded_prompt)
        raw = await chat.send_message(msg)
        raw_text = raw if isinstance(raw, str) else str(raw)
        rehydrated = rehydrate(raw_text, shield_map)
        return {
            "layers": layers, "mode": "live",
            "response": rehydrated,
            "sources": [],
            "shielding": {"identifiers_masked": len(shield_map), "shielded_by": "mock-synisense"},
            "synisense_verified": False,  # becomes true when real Synisense wires in
            "synisense_verification_id": None,
        }
    except Exception as e:
        logger.exception("LLM call failed")
        return {
            "layers": layers, "mode": "error",
            "response": f"[LLM error: {type(e).__name__}: {e}]",
            "sources": [],
            "shielding": {"identifiers_masked": len(shield_map), "shielded_by": "mock-synisense"},
            "synisense_verified": False,
            "synisense_verification_id": None,
            "error": str(e),
        }


def parse_json_response(text: str) -> Optional[Any]:
    """Best-effort JSON extraction from LLM response."""
    if not text:
        return None
    # Strip code fences if Claude included them
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    # Find first { or [ and last } or ]
    try:
        return json.loads(t)
    except Exception:
        pass
    first = min([i for i in [t.find("{"), t.find("[")] if i >= 0], default=-1)
    last = max(t.rfind("}"), t.rfind("]"))
    if first >= 0 and last > first:
        try:
            return json.loads(t[first:last + 1])
        except Exception:
            return None
    return None
