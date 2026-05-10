"""
Phase C.2 — Work Studio Brief enhance loop.

Two-pass LLM revision of a persisted Brief:

  Pass 1 — DRAFTER. Claude Sonnet 4.5 (via `llm_service.call_llm` with
           `tier="standard"`). Receives the parent Brief snapshot +
           instruction + scope. Returns a STRICT-JSON revised snapshot
           preserving structure, fields, and tier markers.

  Pass 2 — VALIDATOR. Gemini 2.5 Flash (independent family, via
           `llm_service.validate_independent`). Independently reads the
           revised text and judges drift. Plus a deterministic local
           guardrail: count "claims" in the revised text that are NEW
           relative to the parent AND lack a tier marker
           (`[T:user_assertion|corpus|domain_prior|speculation|comparable]`).
           Any uncited new claim → verdict "refused".

Hard contracts:
  * The revised snapshot MUST keep the same set of section_ids the
    parent had unless `scope` is `recommendations` (where adding rows
    is allowed) or `whole_brief` (where adding/removing sections is
    allowed). Section IDs are stable across enhances per
    `persistence.brief_to_dict`.
  * Tier markers `[T:...]` in the parent text MUST survive the revise
    pass verbatim where the underlying sentence survives.
  * Refused revisions are still persisted (so the user can inspect
    why) but `set_active` cannot point at them.

This module does NOT mutate `brief.py`, the C.1 generators, or any
Solva submodule logic — it operates solely on the dict snapshot.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from llm_service import call_llm, parse_json_response, validate_independent

logger = logging.getLogger("akki.work_studio.enhance")


# ---------------------------------------------------------------------------
# Tier-marker grammar (synced with services/solva_v2/grounding_contract.py)
# ---------------------------------------------------------------------------
ALLOWED_TIERS = (
    "user_assertion", "corpus", "domain_prior", "speculation", "comparable",
)
# Permissive matcher — case-insensitive, hyphen/underscore tolerant. This is
# what we use to *detect* markers; for emit-side instructions we tell the
# LLM to use the exact `[T:<tier>]` form.
_TIER_MARKER_RE = re.compile(
    r"\[T\s*:\s*(user[_-]?assertion|corpus|domain[_-]?prior|speculation|comparable)\s*\]",
    re.IGNORECASE,
)
# A "looks-like-an-assertion" sentence carries something attributable: a
# numeral, percentage, $/£/€/KES amount, an "according to" / "report" /
# "study" cue, or a named third-party house (IPSOS, McKinsey, Deloitte,
# Bain, Gartner, IDC). The regex is intentionally heuristic — false
# positives are fine for the validator (more refusals on the cautious
# side); false negatives are not (we'd miss a fabricated claim).
#
# A standalone year (`2026`) is *not* an assertive cue — analyses are
# riddled with dates that aren't claims. A year combined with a citation
# verb / a currency / a percentage / a named third-party house is what
# we flag.
_ASSERTIVE_CUE_RE = re.compile(
    r"(?:\b\d{1,3}(?:[,\.]\d{3})*(?:\.\d+)?\s*(?:%|percent|bps|basis\s*points)\b"
    r"|\b(?:USD|EUR|GBP|KES|KSh|\$|£|€|Rs)\s*\d"
    r"|\baccording\s+to\b|\breport(?:s|ed)?\b|\bstud(?:y|ies)\b|\bsurvey\b"
    r"|\bIPSOS\b|\bMcKinsey\b|\bDeloitte\b|\bBain\b|\bGartner\b|\bIDC\b"
    r"|\bWHO\b|\bWorld\s+Bank\b|\bIMF\b|\bUN\b|\bOECD\b"
    r"|\bcite[ds]?\b|\bquote[ds]?\b)",
    re.IGNORECASE,
)


def _strip_markers(text: str) -> str:
    return _TIER_MARKER_RE.sub("", text or "").strip()


def _split_sentences(text: str) -> List[str]:
    if not text:
        return []
    # Naive sentence splitter — adequate for body paragraphs and bullets.
    parts = re.split(r"(?<=[\.\!\?])\s+(?=[A-Z\(\"'])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _all_text_in_brief(snap: Dict[str, Any]) -> str:
    """Concatenate every prose field that COULD carry a claim, for the
    new-vs-old assertion check.

    Excludes `title` and `subtitle` — those are metadata labels, not
    claims; including them produces false positives because they often
    contain dates and currency strings ('Strategy Memo: ... Q3 2026 …
    30M USD …') that look assertive but are descriptive headers.
    """
    parts: List[str] = []
    for key in ("cover_lead_paragraph", "closing_recap", "framework_spine"):
        if snap.get(key):
            parts.append(str(snap[key]))
    for sec in snap.get("sections") or []:
        # Section title/kicker are also labels; skip them.
        for para in (sec.get("body_paragraphs") or []):
            parts.append(para)
        for b in (sec.get("bullets") or []):
            parts.append(b)
        for tbl in (sec.get("tables") or []):
            # Table cells can carry claims; rows yes, headers/title no.
            for row in (tbl.get("rows") or []):
                parts.extend(row)
    return "\n".join(parts)


def _normalised_sentences(snap: Dict[str, Any]) -> set[str]:
    """Lowercased, marker-stripped sentence set for membership checks."""
    text = _all_text_in_brief(snap)
    out: set[str] = set()
    for s in _split_sentences(text):
        norm = re.sub(r"\s+", " ", _strip_markers(s)).strip().lower()
        if len(norm) >= 8:
            out.add(norm)
    return out


# ---------------------------------------------------------------------------
# Validator — local deterministic check
# ---------------------------------------------------------------------------
def count_uncited_new_claims(
    parent_snap: Dict[str, Any], revised_snap: Dict[str, Any],
) -> Tuple[int, List[str]]:
    """Return (count, examples). A "claim" is a sentence that:
       - is NEW relative to parent (not a substring match), and
       - looks assertive (numeral / cited-source cue / dated reference), and
       - does NOT carry a recognised tier marker.

    Examples are returned for the validator-reason field (max 3, truncated).
    """
    parent_set = _normalised_sentences(parent_snap)
    revised_text = _all_text_in_brief(revised_snap)
    sentences = _split_sentences(revised_text)
    examples: List[str] = []
    count = 0
    for raw in sentences:
        norm = re.sub(r"\s+", " ", _strip_markers(raw)).strip().lower()
        if len(norm) < 8:
            continue
        if norm in parent_set:
            continue                # surviving sentence — fine
        # Substring tolerance: if the parent already contains this
        # sentence as a fragment of a longer paragraph, accept it.
        if any(norm in p_norm or p_norm in norm
               for p_norm in parent_set if len(p_norm) > 20):
            continue
        if not _ASSERTIVE_CUE_RE.search(raw):
            continue                # new but non-assertive — fine
        if _TIER_MARKER_RE.search(raw):
            continue                # new, assertive, but cited — fine
        # Fabricated tier markers (e.g. `[T:third_party_report]`) won't
        # match _TIER_MARKER_RE because the tier name is outside the
        # allow-list. They are NOT accepted as citation.
        count += 1
        if len(examples) < 3:
            examples.append(raw[:240])
    return count, examples


def count_section_changes(
    parent_snap: Dict[str, Any], revised_snap: Dict[str, Any],
) -> int:
    """Return the number of sections whose content (any field) changed."""
    parent_secs = {s.get("section_id"): s
                   for s in (parent_snap.get("sections") or [])}
    revised_secs = {s.get("section_id"): s
                    for s in (revised_snap.get("sections") or [])}
    changed = 0
    for sid in set(parent_secs) | set(revised_secs):
        a = parent_secs.get(sid) or {}
        b = revised_secs.get(sid) or {}
        if a != b:
            changed += 1
    return changed


# ---------------------------------------------------------------------------
# Section-by-section diff
# ---------------------------------------------------------------------------
def _section_to_text(sec: Dict[str, Any]) -> str:
    chunks: List[str] = []
    if sec.get("title"):
        chunks.append(f"# {sec['title']}")
    if sec.get("kicker"):
        chunks.append(f"({sec['kicker']})")
    for p in sec.get("body_paragraphs") or []:
        chunks.append(p)
    for b in sec.get("bullets") or []:
        chunks.append(f"• {b}")
    for tbl in sec.get("tables") or []:
        chunks.append(f"[Table: {tbl.get('title','')}] "
                      f"headers={tbl.get('headers') or []} "
                      f"rows={len(tbl.get('rows') or [])}")
    return "\n".join(chunks).strip()


def compute_section_diff(
    parent_snap: Dict[str, Any], revised_snap: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Section-level diff. Each entry: {section_id, change_type, before, after}.
    change_type ∈ {modified, added, removed}.
    """
    parent_secs = {s.get("section_id"): s
                   for s in (parent_snap.get("sections") or [])}
    out: List[Dict[str, Any]] = []
    # Preserve order of revised sections, then any orphans from parent.
    seen: set[str] = set()
    for sec in revised_snap.get("sections") or []:
        sid = sec.get("section_id")
        seen.add(sid)
        if sid not in parent_secs:
            out.append({
                "section_id": sid, "change_type": "added",
                "before": "", "after": _section_to_text(sec),
            })
        else:
            before = _section_to_text(parent_secs[sid])
            after = _section_to_text(sec)
            if before != after:
                out.append({
                    "section_id": sid, "change_type": "modified",
                    "before": before, "after": after,
                })
    for sid, sec in parent_secs.items():
        if sid not in seen:
            out.append({
                "section_id": sid, "change_type": "removed",
                "before": _section_to_text(sec), "after": "",
            })

    # Whole-brief envelope diffs (title/subtitle/cover/closing). Use a
    # synthetic section_id so the UI can render them alongside.
    for env_id, key in (
        ("__envelope:title", "title"),
        ("__envelope:subtitle", "subtitle"),
        ("__envelope:cover_lead_paragraph", "cover_lead_paragraph"),
        ("__envelope:closing_recap", "closing_recap"),
        ("__envelope:framework_spine", "framework_spine"),
    ):
        before = (parent_snap.get(key) or "")
        after = (revised_snap.get(key) or "")
        if before != after:
            out.append({
                "section_id": env_id,
                "change_type": "modified" if before and after
                              else ("added" if after else "removed"),
                "before": before, "after": after,
            })
    return out


# ---------------------------------------------------------------------------
# Drafter prompt
# ---------------------------------------------------------------------------
_DRAFTER_SYSTEM = (
    "You are AKKI Work Studio's enhance drafter. Your job is to revise a "
    "structured executive brief in response to a specific instruction from "
    "the executive. You return STRICT JSON ONLY — the same shape as the "
    "input snapshot — with the requested changes applied.\n\n"
    "RULES — non-negotiable:\n"
    "1. Preserve every section_id you receive. Do not rename, reorder, or "
    "   remove sections unless the scope is `whole_brief`.\n"
    "2. Tier markers in the parent text MUST be preserved verbatim where the "
    "   underlying sentence survives. Tier markers look like `[T:user_assertion]`, "
    "   `[T:corpus]`, `[T:domain_prior]`, `[T:speculation]`, `[T:comparable]`. "
    "   Only those five tier names are valid.\n"
    "3. NEVER introduce a factual claim (a sentence with a numeral, a "
    "   percentage, a currency figure, a 'according to', 'report', "
    "   'study', or a named third party) WITHOUT a valid tier marker. "
    "   If you would need to add such a claim to satisfy the user's "
    "   instruction, you MUST refuse: emit JSON `{\"refused\": true, "
    "   \"reason\": \"<one short sentence>\"}` and nothing else.\n"
    "4. Tier markers you invent are not citations. The five allowed tier "
    "   names are the closed list above.\n"
    "5. Output format: STRICT JSON. No prose, no code fences, no markdown, "
    "   no commentary. Just the revised snapshot object (or the refusal "
    "   object). Field names and types must match the input exactly.\n"
    "6. Maintain Financial Times tone — dry, professional, peer-toned. "
    "   No filler ('leverage', 'synergies', 'going forward', "
    "   'in order to'). No exclamation marks."
)


def _build_drafter_prompt(
    parent_snap: Dict[str, Any], instruction: str, scope: str,
) -> str:
    return (
        f"INSTRUCTION FROM THE EXECUTIVE:\n{instruction.strip()}\n\n"
        f"SCOPE: {scope}\n"
        + ("  - whole_brief: you may edit any field, add or remove sections.\n"
           if scope == "whole_brief" else "")
        + ("  - recommendations: only edit sections whose kicker is "
           "'THE RECOMMENDATION' or 'ACTION', and you may add or remove "
           "bullets/rows within those.\n"
           if scope == "recommendations" else "")
        + ("  - exec_summary: only edit the cover (title, subtitle, "
           "cover_lead_paragraph) and any section whose kicker is "
           "'EXECUTIVE BRIEF' or 'WHY THIS MATTERS'.\n"
           if scope == "exec_summary" else "")
        + (f"  - section:<id>: only edit the section with that section_id "
           f"(scope was '{scope}').\n"
           if scope.startswith("section:") else "")
        + "\n"
        + "PARENT SNAPSHOT (revise this):\n"
        + json.dumps(parent_snap, indent=2, default=str)
        + "\n\n"
        + "Return STRICT JSON: the full revised snapshot, identical shape, "
          "with your edits applied. Or the refusal object per rule #3."
    )


# ---------------------------------------------------------------------------
# Two-pass enhance
# ---------------------------------------------------------------------------
async def enhance_brief_two_pass(
    *,
    parent_snapshot: Dict[str, Any],
    instruction: str,
    scope: str,
    account_id: str,
    context_id: Optional[str],
    brief_id: str,
) -> Dict[str, Any]:
    """Run drafter + validator. Returns:
        {revised_snapshot, validation, claims_changed,
         claims_added_without_citation, llm_audit, drafter_refused: bool}
    """
    if not isinstance(parent_snapshot, dict):
        raise TypeError("parent_snapshot must be a dict")
    if scope not in {"whole_brief", "recommendations", "exec_summary"} \
            and not scope.startswith("section:"):
        raise ValueError(f"unsupported scope: {scope!r}")

    user_prompt = _build_drafter_prompt(parent_snapshot, instruction, scope)

    drafter = await call_llm(
        module="work_studio.enhance",
        user_query=user_prompt,
        system_override=_DRAFTER_SYSTEM,
        session_context={"context_id": context_id or "",
                         "brief_id": brief_id, "scope": scope},
        response_format="json",
        tier="standard",
    )
    drafter_raw = drafter.get("response") or ""
    drafter_audit = {
        "mode": drafter.get("mode"),
        "model": drafter.get("model"),
        "tier": drafter.get("tier"),
        "provider_used": drafter.get("provider_used"),
        "fallback_triggered": drafter.get("fallback_triggered", False),
    }

    parsed = parse_json_response(drafter_raw)
    if parsed is None:
        # Drafter produced unparseable output — treat as refusal.
        return {
            "revised_snapshot": parent_snapshot,
            "drafter_refused": True,
            "validation": {
                "verdict": "refused",
                "reason": "Drafter returned unparseable output; no revision applied.",
                "validator_provider": "n/a",
                "validator_model": "n/a",
                "uncited_examples": [],
                "validator_notes": [],
            },
            "claims_changed": 0,
            "claims_added_without_citation": 0,
            "llm_audit": {"drafter": drafter_audit, "validator": None},
        }

    # Drafter explicit refusal path.
    if isinstance(parsed, dict) and parsed.get("refused") is True:
        return {
            "revised_snapshot": parent_snapshot,  # echo parent so the row is renderable
            "drafter_refused": True,
            "validation": {
                "verdict": "refused",
                "reason": str(parsed.get("reason") or
                             "Drafter refused — instruction would require uncited claims."),
                "validator_provider": "n/a",
                "validator_model": "n/a",
                "uncited_examples": [],
                "validator_notes": [],
            },
            "claims_changed": 0,
            "claims_added_without_citation": 0,
            "llm_audit": {"drafter": drafter_audit, "validator": None},
        }

    if not isinstance(parsed, dict):
        return {
            "revised_snapshot": parent_snapshot,
            "drafter_refused": True,
            "validation": {
                "verdict": "refused",
                "reason": "Drafter returned a non-object payload.",
                "validator_provider": "n/a",
                "validator_model": "n/a",
                "uncited_examples": [],
                "validator_notes": [],
            },
            "claims_changed": 0,
            "claims_added_without_citation": 0,
            "llm_audit": {"drafter": drafter_audit, "validator": None},
        }

    # Coerce minimal shape — keep all parent keys; overlay edited ones.
    # This protects against the drafter accidentally dropping fields.
    revised = dict(parent_snapshot)
    for k, v in parsed.items():
        if k in {"sections", "title", "subtitle", "cover_lead_paragraph",
                 "closing_recap", "framework_spine", "host_org_line",
                 "audience", "company_label", "document_type", "programme",
                 "version", "date_text", "closing_brand_line",
                 "depth", "fidelity"}:
            revised[k] = v
    # Re-stamp section_ids: any section the drafter omitted gets carried
    # over from parent unchanged. Any new sections without ids get one.
    revised["sections"] = _reconcile_sections(
        parent_snapshot.get("sections") or [],
        revised.get("sections") or [],
    )

    # Local validator — the deterministic guardrail.
    uncited_count, uncited_examples = count_uncited_new_claims(
        parent_snapshot, revised,
    )
    sections_changed = count_section_changes(parent_snapshot, revised)

    # Local validator's first verdict.
    if uncited_count > 0:
        local_verdict = "refused"
        local_reason = (
            f"{uncited_count} new assertive sentence(s) lack a recognised "
            f"tier marker. Examples: "
            + " || ".join(f"'{e}'" for e in uncited_examples[:2])
        )
    else:
        local_verdict = "validated"
        local_reason = "No uncited claims introduced."

    # Independent-family validator (Gemini 2.5 Flash). Advisory — never
    # promotes a refused verdict to validated. Can downgrade validated
    # to qualified if the model has a quality concern.
    revised_text = _all_text_in_brief(revised)[:6000]
    independent = await validate_independent(
        kind="work_studio_brief_revision",
        content=revised_text,
        objective=f"Enhance instruction: {instruction[:200]}",
        surface="work_studio.enhance",
        account_id=account_id,
    )
    independent_verdict = (independent.get("verdict") or "qualified").lower()
    independent_notes = independent.get("notes") or []

    # Resolve final verdict.
    #   local refused → final refused (deterministic guard wins).
    #   else local validated → use independent verdict (validated|qualified).
    #     a "flagged" from independent maps to "qualified" here — we don't
    #     promote independent flags to refusal because the deterministic
    #     guard is the citation-truth oracle.
    if local_verdict == "refused":
        final_verdict = "refused"
        final_reason = local_reason
    else:
        if independent_verdict == "flagged":
            final_verdict = "qualified"
        elif independent_verdict in {"validated", "qualified"}:
            final_verdict = independent_verdict
        else:
            final_verdict = "qualified"
        final_reason = local_reason
        if independent_notes:
            final_reason += " · independent: " + " ".join(independent_notes[:2])[:200]

    return {
        "revised_snapshot": revised,
        "drafter_refused": False,
        "validation": {
            "verdict": final_verdict,
            "reason": final_reason,
            "validator_provider": independent.get("validator_provider") or "n/a",
            "validator_model": independent.get("validator_model") or "n/a",
            "uncited_examples": uncited_examples,
            "validator_notes": independent_notes,
        },
        "claims_changed": sections_changed,
        "claims_added_without_citation": uncited_count,
        "llm_audit": {
            "drafter": drafter_audit,
            "validator": {
                "provider": independent.get("validator_provider"),
                "model": independent.get("validator_model"),
                "raw_verdict": independent_verdict,
                "raw_confidence": independent.get("confidence"),
            },
        },
    }


def _reconcile_sections(
    parent_sections: List[Dict[str, Any]], drafter_sections: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Make sure every section the drafter returned has a section_id, and
    re-stamp any that drifted. Sections from the parent that the drafter
    omitted are NOT carried over here — under `whole_brief` scope the
    drafter is allowed to drop sections; the diff captures it as
    `removed`. Caller-side scope enforcement is responsible for
    rejecting illegal removals.
    """
    parent_titles = {(s.get("title") or "").strip().lower(): s.get("section_id")
                     for s in parent_sections}
    used_ids: Dict[str, int] = {}
    out: List[Dict[str, Any]] = []
    for sec in drafter_sections:
        if not isinstance(sec, dict):
            continue
        sid = (sec.get("section_id") or "").strip()
        if not sid:
            # Drafter dropped the id — try to map by title to the parent.
            sid = parent_titles.get((sec.get("title") or "").strip().lower(), "")
        if not sid:
            from .persistence import slugify
            sid = slugify(sec.get("title") or "section")
        used_ids[sid] = used_ids.get(sid, 0) + 1
        if used_ids[sid] > 1:
            sid = f"{sid}-{used_ids[sid]}"
        sec = dict(sec)
        sec["section_id"] = sid
        # Defensive: ensure list-typed fields are lists.
        sec["body_paragraphs"] = list(sec.get("body_paragraphs") or [])
        sec["bullets"] = list(sec.get("bullets") or [])
        sec["tables"] = list(sec.get("tables") or [])
        out.append(sec)
    return out
