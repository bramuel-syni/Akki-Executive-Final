"""
Phase D.1 — Executive Cycle Manager · Compilation pipeline.

Replaces the legacy heuristic compilation (which concatenated owner-prefixed
truncations into bullets) with a real two-pass LLM synthesis that produces
the structure the spec demands:

  * Executive summary (80–120 words, peer-toned, declarative)
  * Per-agenda-item synthesis with the strongest contribution surfaced
  * Outstanding items list
  * Next-cycle adjustments
  * Cross-cycle pattern observations  (omitted on first cycle per call #2)

Output is a Solva-shaped envelope so `build_brief_from_solva` can produce
a normal `Brief` dataclass downstream — meaning the cycle output flows
through the C.1 generators and the C.2 enhance loop without parallel
plumbing.

Tier-marker discipline (call #1) — reuse Solva's 5 tiers verbatim:
  contribution               → [T:corpus]
  cross-cycle observation    → [T:comparable]
  next-cycle adjustment      → [T:speculation]
  user-asserted intent       → [T:user_assertion]
  domain knowledge / norm    → [T:domain_prior]

The drafter prompt is anchored on the Solva drafter grammar from
work_studio/enhance.py; voice rules are from the Executive Cycle
Manager Spec (brisk, declarative, peer-toned, operational, no
marketing fluff, no hedging, no "I'd suggest").
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from llm_service import call_llm, parse_json_response, validate_independent

logger = logging.getLogger("akki.cycle.synthesis")

ALLOWED_TIERS = ("user_assertion", "corpus", "domain_prior", "speculation", "comparable")

_DRAFTER_SYSTEM = (
    "You are AKKI's executive cycle compiler. You read a cycle envelope "
    "(agenda, scored contributions from named team members, readiness "
    "state, optionally prior-cycle history) and produce a board-grade "
    "synthesis the executive can carry into the next meeting with only "
    "light edits.\n\n"
    "VOICE — non-negotiable:\n"
    "  * Brisk, declarative, peer-toned, operational. Write to a CFO who "
    "    reads ten of these a week.\n"
    "  * No marketing fluff. No hedging ('it would seem', 'arguably'). "
    "    No 'I'd suggest'. No 'leverage', 'synergies', 'going forward', "
    "    'in order to'. No exclamation marks.\n"
    "  * Three-phrase rhythm where it earns its place: orient · distil · "
    "    recommend. Do not force this on every paragraph.\n\n"
    "TIER MARKERS — non-negotiable:\n"
    "  Every factual sentence MUST carry exactly one tier marker from this "
    "  closed list, written verbatim with brackets:\n"
    "    [T:corpus]          — claims drawn from a team member's "
    "                          contribution body\n"
    "    [T:user_assertion]  — claims the executive has stated as fact\n"
    "    [T:comparable]      — cross-cycle observations or industry "
    "                          comparators\n"
    "    [T:domain_prior]    — claims that follow from corporate-governance "
    "                          domain priors (eg fiduciary duty, audit "
    "                          conventions)\n"
    "    [T:speculation]     — forward-leaning recommendations or what-if "
    "                          framings\n"
    "  Made-up tier names are NOT citations. The five above are the closed "
    "  list. If you cannot validly cite a sentence, do not write it.\n\n"
    "OUTPUT — strict JSON ONLY. No prose, no code fences, no commentary. "
    "Field names, types, and shape must match exactly:\n"
    "  {\n"
    "    \"executive_summary\":     <string, 80–120 words, "
    "                                tier-marked claims throughout>,\n"
    "    \"agenda_synthesis\":      [\n"
    "      { \"agenda_item_id\":           <string>,\n"
    "        \"agenda_item_label\":        <string>,\n"
    "        \"synthesis\":                <string, 60–120 words, tier-"
    "                                       marked>,\n"
    "        \"strongest_contribution\":   { \"team_member_id\": <string>,\n"
    "                                       \"team_member_name\": <string>,\n"
    "                                       \"rationale\": <string, 1 "
    "                                                     sentence> }\n"
    "      }, ...\n"
    "    ],\n"
    "    \"outstanding_items\":     [<string with [T:...] marker>, ...],\n"
    "    \"next_cycle_adjustments\":[\n"
    "      { \"ordinal\": <int>,\n"
    "        \"text\":    <string with [T:speculation] or other valid "
    "                     marker> }, ...\n"
    "    ],\n"
    "    \"cross_cycle_observations\": [<string>, ...]   "
    "      // OMIT THIS KEY ENTIRELY when no prior cycles are supplied\n"
    "  }\n"
)


def _build_drafter_prompt(envelope: Dict[str, Any]) -> str:
    """Compose the user-prompt section of the call. The drafter system
    prompt above carries the voice + tier rules; this prompt carries the
    cycle data."""
    has_prior = bool(envelope.get("prior_cycles"))
    return (
        f"CYCLE CONTEXT:\n"
        f"  Workspace:  {envelope.get('context_name') or '—'}\n"
        f"  Executive:  {envelope.get('executive_name') or '—'}\n"
        f"  Agenda:     {envelope.get('agenda', {}).get('title') or '—'}\n"
        f"  Period:     {envelope.get('period') or '—'}\n"
        f"  Readiness:  {(envelope.get('readiness') or {}).get('overall', 0)}% overall\n"
        f"  Storyline:  {' · '.join((envelope.get('readiness') or {}).get('storyline') or []) or '—'}\n"
        f"\n"
        f"AGENDA ITEMS, SCORED CONTRIBUTIONS, AND TEAM:\n"
        + json.dumps({
            "agenda": envelope.get("agenda") or {},
            "team": envelope.get("team") or [],
            "contributions": envelope.get("contributions") or [],
        }, indent=2, default=str)
        + (
            "\n\nPRIOR CYCLES (for cross-cycle observations):\n"
            + json.dumps(envelope.get("prior_cycles") or [], indent=2, default=str)
            if has_prior else
            "\n\nFIRST CYCLE — no prior history. OMIT the "
            "`cross_cycle_observations` field entirely from the JSON."
        )
        + "\n\n"
        + "Return STRICT JSON. Match the shape in the system prompt exactly. "
        + ("Include " if has_prior else "OMIT ") + "the `cross_cycle_observations` field."
    )


def _coerce_synthesis(parsed: Any, envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Defensively shape the drafter output into the canonical envelope.
    Drops fields with the wrong type rather than raising — the validator
    pass and the caller's structure-check are the safety nets."""
    if not isinstance(parsed, dict):
        return {}
    out: Dict[str, Any] = {}
    if isinstance(parsed.get("executive_summary"), str):
        out["executive_summary"] = parsed["executive_summary"].strip()
    if isinstance(parsed.get("agenda_synthesis"), list):
        clean: List[Dict[str, Any]] = []
        for entry in parsed["agenda_synthesis"]:
            if not isinstance(entry, dict):
                continue
            item: Dict[str, Any] = {
                "agenda_item_id": str(entry.get("agenda_item_id") or "").strip(),
                "agenda_item_label": str(entry.get("agenda_item_label") or "").strip(),
                "synthesis": str(entry.get("synthesis") or "").strip(),
            }
            sc = entry.get("strongest_contribution")
            if isinstance(sc, dict):
                item["strongest_contribution"] = {
                    "team_member_id": str(sc.get("team_member_id") or "").strip(),
                    "team_member_name": str(sc.get("team_member_name") or "").strip(),
                    "rationale": str(sc.get("rationale") or "").strip(),
                }
            if item["agenda_item_id"] and item["synthesis"]:
                clean.append(item)
        out["agenda_synthesis"] = clean
    if isinstance(parsed.get("outstanding_items"), list):
        out["outstanding_items"] = [str(x).strip() for x in parsed["outstanding_items"] if str(x).strip()]
    if isinstance(parsed.get("next_cycle_adjustments"), list):
        adjs: List[Dict[str, Any]] = []
        for r in parsed["next_cycle_adjustments"]:
            if isinstance(r, dict):
                t = str(r.get("text") or "").strip()
                if t:
                    adjs.append({
                        "ordinal": int(r.get("ordinal") or len(adjs) + 1),
                        "text": t,
                    })
            elif isinstance(r, str) and r.strip():
                adjs.append({"ordinal": len(adjs) + 1, "text": r.strip()})
        out["next_cycle_adjustments"] = adjs
    # Cross-cycle: omit when first cycle (call #2 — honest empty)
    if envelope.get("prior_cycles") and isinstance(parsed.get("cross_cycle_observations"), list):
        out["cross_cycle_observations"] = [str(x).strip() for x in parsed["cross_cycle_observations"] if str(x).strip()]
    return out


_TIER_MARKER_RE = re.compile(
    r"\[T\s*:\s*(user[_-]?assertion|corpus|domain[_-]?prior|speculation|comparable)\s*\]",
    re.IGNORECASE,
)


def _extract_claims_with_tiers(text: str) -> List[Dict[str, Any]]:
    """Walk the synthesised prose, capturing every sentence that carries
    a tier marker. Produces the {text, tier, confidence_pct, confidence_band}
    shape that build_brief_from_solva consumes."""
    if not text:
        return []
    # Split on sentence boundaries.
    sentences = re.split(r"(?<=[\.\!\?])\s+(?=[A-Z\(\"'])", text.strip())
    out: List[Dict[str, Any]] = []
    for s in sentences:
        s = s.strip()
        m = _TIER_MARKER_RE.search(s)
        if not m:
            continue
        tier_raw = m.group(1).lower().replace("-", "_")
        # Normalise to the closed-list spelling.
        tier = {
            "user_assertion": "user_assertion",
            "corpus": "corpus",
            "domain_prior": "domain_prior",
            "speculation": "speculation",
            "comparable": "comparable",
        }.get(tier_raw, "corpus")
        confidence_pct = {
            "user_assertion": 95,
            "corpus": 80,
            "comparable": 65,
            "domain_prior": 60,
            "speculation": 40,
        }[tier]
        confidence_band = {
            "user_assertion": "high", "corpus": "high",
            "comparable": "medium", "domain_prior": "medium",
            "speculation": "low",
        }[tier]
        out.append({
            "text": s,
            "tier": tier,
            "confidence_pct": confidence_pct,
            "confidence_band": confidence_band,
        })
    return out


def _envelope_to_solva_shape(synth: Dict[str, Any], envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Convert the synthesised cycle envelope into the Solva-session
    shape that `build_brief_from_solva` understands. The Brief schema
    is single-source-of-truth; we inherit it instead of forking."""
    body_chunks: List[str] = []
    if synth.get("executive_summary"):
        body_chunks.append(synth["executive_summary"])
    body_chunks.append("")  # paragraph break
    for entry in synth.get("agenda_synthesis", []):
        label = entry.get("agenda_item_label") or "Agenda item"
        body_chunks.append(f"## {label}")
        body_chunks.append(entry.get("synthesis") or "")
        sc = entry.get("strongest_contribution") or {}
        if sc.get("team_member_name"):
            body_chunks.append(
                f"_Strongest contribution: {sc['team_member_name']} — "
                f"{sc.get('rationale', '').rstrip('.')}._"
            )
        body_chunks.append("")
    if synth.get("outstanding_items"):
        body_chunks.append("## Outstanding")
        for it in synth["outstanding_items"]:
            body_chunks.append(f"- {it}")
        body_chunks.append("")
    if synth.get("cross_cycle_observations"):
        body_chunks.append("## Cross-cycle pattern")
        for obs in synth["cross_cycle_observations"]:
            body_chunks.append(f"- {obs}")
        body_chunks.append("")
    body = "\n".join(body_chunks).strip()

    # Recommendations — dict-shape (build_brief_from_solva tolerates both
    # post-D.1 fix; we still emit dicts because this is a fresh path).
    recommendations = [
        {"ordinal": r["ordinal"], "text": r["text"]}
        for r in synth.get("next_cycle_adjustments") or []
    ]

    claims = _extract_claims_with_tiers(body)

    return {
        "id": envelope.get("source_id") or envelope.get("agenda_id") or "cycle",
        # `develop_strategy` is the closest existing submodule fit — the
        # cycle compilation IS a strategy reading. The C.2 picker treats
        # it identically to a Solva strategy session for refining.
        "submodule": "develop_strategy",
        "intent": (envelope.get("agenda") or {}).get("title") or "Cycle compilation",
        "synthesis": {
            "body": body,
            "claims": claims,
            "recommendations": recommendations,
            "validation": {
                "verdict": "informational",
                "confidence": 70,
                "validator_provider": "akki.cycle.synthesis",
                "validator_model": "two_pass",
            },
        },
    }


# ---------------------------------------------------------------------------
# Two-pass entry point
# ---------------------------------------------------------------------------
async def synthesise_cycle(
    *,
    envelope: Dict[str, Any],
    account_id: str,
    context_id: Optional[str],
) -> Dict[str, Any]:
    """Run drafter + validator over the cycle envelope. Returns:
        {solva_shaped_envelope, raw_synth, validation, llm_audit}

    Caller hands `solva_shaped_envelope` to `build_brief_from_solva`
    to produce a `Brief` dataclass, then to `ensure_brief_persisted`
    to mint the brief_id.
    """
    user_prompt = _build_drafter_prompt(envelope)
    drafter = await call_llm(
        module="cycle.compilation",
        user_query=user_prompt,
        system_override=_DRAFTER_SYSTEM,
        session_context={
            "context_id": context_id or "",
            "agenda_id": (envelope.get("agenda") or {}).get("id") or "",
        },
        response_format="json",
        tier="standard",
    )
    drafter_raw = drafter.get("response") or ""
    parsed = parse_json_response(drafter_raw) or {}
    synth = _coerce_synthesis(parsed, envelope)

    if not synth.get("executive_summary") or not synth.get("agenda_synthesis"):
        # Drafter failure — never fall back to placeholder text. Surface
        # the error to the caller so the route returns 502.
        return {
            "ok": False,
            "error": "drafter_failed",
            "drafter_raw_excerpt": (drafter_raw or "")[:600],
            "llm_audit": {"drafter": {
                "mode": drafter.get("mode"), "model": drafter.get("model"),
                "tier": drafter.get("tier"),
            }, "validator": None},
        }

    # Independent validator pass. The cycle compilation is informational
    # by nature — flagged-but-not-refused outcomes are normal. We surface
    # the verdict but do not block.
    validator_text = (synth.get("executive_summary") + "\n\n" +
                      "\n\n".join(e.get("synthesis", "")
                                  for e in synth.get("agenda_synthesis", [])))[:6000]
    independent = await validate_independent(
        kind="cycle_compilation",
        content=validator_text,
        objective=f"Cycle: {(envelope.get('agenda') or {}).get('title') or 'cycle'}",
        surface="cycle.compilation",
        account_id=account_id,
    )

    solva_shaped = _envelope_to_solva_shape(synth, envelope)

    return {
        "ok": True,
        "synth": synth,
        "solva_shaped_envelope": solva_shaped,
        "validation": {
            "verdict": independent.get("verdict") or "qualified",
            "confidence": independent.get("confidence"),
            "validator_provider": independent.get("validator_provider"),
            "validator_model": independent.get("validator_model"),
            "notes": independent.get("notes") or [],
        },
        "llm_audit": {
            "drafter": {
                "mode": drafter.get("mode"),
                "model": drafter.get("model"),
                "tier": drafter.get("tier"),
                "fallback_triggered": drafter.get("fallback_triggered", False),
            },
            "validator": {
                "provider": independent.get("validator_provider"),
                "model": independent.get("validator_model"),
            },
        },
    }
