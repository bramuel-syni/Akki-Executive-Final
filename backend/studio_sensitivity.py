"""Studio · sensitivity & exposure scoring.

iter64 — the user's feedback was that the merged 'Decks + Reports' Studio
should auto-score every saved artefact's confidentiality so the board
member knows exactly how careful to be when sharing. The rule is simple
and deterministic so users can trust it; LLM is used ONLY as a tiebreaker
when keyword scanning is ambiguous.

Classification ladder (matches NACD/IoD industry conventions):
  - PUBLIC       — safe to share externally
  - INTERNAL     — safe within the company / board members
  - CONFIDENTIAL — board + named recipients only
  - RESTRICTED   — chair / SID / specific NEDs only

Score 0-100 (higher = more sensitive). Maps to classification:
  0-24   → PUBLIC
  25-49  → INTERNAL
  50-74  → CONFIDENTIAL
  75-100 → RESTRICTED

Heuristics (deterministic):
  +20 if any deal/M&A keyword
  +20 if any conduct/HR/dismissal keyword
  +15 if any litigation/regulator keyword
  +15 if any unannounced financial figure pattern (£XXm, $XX bn)
  +15 if any restructure/redundancy/layoff keyword
  +10 if any whistleblower/conflict-of-interest keyword
  +10 if any customer/contract concentration keyword
  +5  if any individual exec named (heuristic — capitalised first+last)
  +5  if any specific date in next 90 days (likely unannounced)

Caps at 100. The reasons[] list surfaces what triggered each bump so the
board member can sanity-check the classification.

Exposure score (0-100):
  raw = unique_readers * 12  +  share_count * 18  +  external_share_count * 22
  raw += days_since_creation > 14 ? 10 : 0     # information staleness
  capped at 100. Higher = more eyes have seen this.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


SENSITIVITY_RULES: List[Tuple[str, int, str]] = [
    (r"\b(acquisition|acquir(e|ing)|merger|m[&\.]?a|takeover|target company|tender offer|due diligence|definitive agreement)\b",
     20, "M&A or deal language"),
    (r"\b(misconduct|harassment|disciplinary|dismissed?|terminated?|allegation|whistleblow|whistle.?blower)\b",
     20, "Conduct or HR sensitivity"),
    (r"\b(litigation|lawsuit|subpoena|regulator(y)?|enforcement|fine|sanction|penalty|breach|investigation)\b",
     15, "Litigation or regulatory"),
    (r"(£|\$|€|R|KSh)\s?[\d,\.]+\s?(?:m|bn|million|billion|thousand)\b",
     15, "Specific unannounced financial figures"),
    (r"\b(restructur|reorganis|redundanc|layoff|downsiz|headcount.{0,12}reduc)\w*",
     15, "Restructure or redundancy"),
    (r"\b(conflict of interest|undisclosed|insider|material non.?public|MNPI|whistleblow)\w*",
     10, "Insider / MNPI signal"),
    (r"\b(customer concentration|top customer|key account|major contract|contract loss)\b",
     10, "Customer or contract concentration"),
    (r"\b(price.?sensitive|pre-?announce(d|ment)?|under embargo|not yet disclosed)\b",
     10, "Price-sensitive / pre-announcement"),
    (r"\b(succession|CEO transition|CFO transition|chair transition|stepping down|resignation)\b",
     10, "Leadership succession"),
]

# Floor mechanism (Phase 8 calibration fix).
#
# A pattern that matches here imposes a MINIMUM classification band on
# the artefact, regardless of the additive numeric score. M&A language
# was previously worth +20, which left the artefact in PUBLIC because
# the INTERNAL band starts at 25 — quietly under-classifying material
# that a board would never share publicly. The floor is the honest
# fix: the additive score remains for transparency, but the final band
# is `max(band_from_score, highest_floor_matched)`.
#
# Order is irrelevant; the highest floor wins.
SENSITIVITY_FLOORS: List[Tuple[str, str, str]] = [
    # Restricted-only patterns are deliberately conservative — we let the
    # citation-source floor (Restricted source ⇒ confidential) and the
    # additive scoring above push into RESTRICTED rather than do it on
    # keyword alone.
    (r"\b(material non.?public|MNPI|board.?confidential|chair.?eyes.?only|insider information|undisclosed material|not yet disclosed)\b",
     "confidential", "Board-confidential / non-public material information"),
    (r"\b(under embargo|pre-?announce(d|ment)?|price.?sensitive)\b",
     "confidential", "Embargoed / price-sensitive disclosure"),
    (r"\b(acquisition|acquir(e|ing)|merger|m[&\.]?a|takeover|target company|tender offer|due diligence|definitive agreement)\b",
     "internal", "M&A / deal language"),
    (r"\b(litigation|lawsuit|subpoena|regulator(y)?|enforcement|investigation)\b",
     "internal", "Litigation or regulatory exposure"),
    (r"\b(misconduct|harassment|disciplinary|allegation|whistleblow|whistle.?blower)\b",
     "internal", "Conduct or HR sensitivity"),
]

BAND_ORDER = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
BAND_KEYS_BY_RANK = ["public", "internal", "confidential", "restricted"]

CLASSIFICATION_BANDS = [
    (0,  24, "public",       "Public"),
    (25, 49, "internal",     "Internal"),
    (50, 74, "confidential", "Confidential"),
    (75, 100, "restricted",  "Restricted"),
]


def _extract_text(artefact: Dict[str, Any]) -> str:
    """Coalesce whatever an artefact carries into one searchable blob."""
    bits: List[str] = []
    for key in ("title", "subtitle", "intent", "research_question",
                "objective", "opening_paragraph", "closing_note",
                "synthesis", "lockin"):
        v = artefact.get(key)
        if isinstance(v, str):
            bits.append(v)
        elif isinstance(v, dict):
            body = v.get("body")
            if isinstance(body, str):
                bits.append(body)
    for s in (artefact.get("slides") or []):
        if isinstance(s, dict):
            bits.extend([str(s.get("title", "")), str(s.get("body_md", "")),
                         str(s.get("key_message", ""))])
    for it in (artefact.get("items") or []):
        if isinstance(it, dict):
            bits.extend([str(it.get("evidence", "")), str(it.get("question", ""))])
    return " \n ".join(b for b in bits if b)


def score_sensitivity(artefact: Dict[str, Any]) -> Dict[str, Any]:
    """Score a Studio artefact (deck, brief, report) for confidentiality.
    Returns {score, classification, label, reasons}."""
    text = _extract_text(artefact)
    score = 0
    reasons: List[str] = []
    if not text:
        return _classify(0, ["No content yet"])

    for pattern, weight, why in SENSITIVITY_RULES:
        try:
            if re.search(pattern, text, flags=re.IGNORECASE):
                score += weight
                reasons.append(why)
        except re.error:
            continue

    # Named-individual heuristic: first-last cap'd words near a role title
    # (e.g. "John Smith, CFO"). Catches "Bramuel Mwalo, CEO".
    named = re.findall(
        r"\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b\s*(?:,|\(|·|\s)\s*(?:CEO|CFO|COO|CHRO|chair|Chair|director|Director)",
        text,
    )
    if named:
        score += 5
        reasons.append("Named exec or director")

    # Specific dates within 90 days (looser — any year-month-day pattern).
    if re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text):
        score += 5
        reasons.append("Specific dated event")

    # Cap and dedupe reasons (preserve order)
    score = min(score, 100)
    seen = set()
    reasons = [r for r in reasons if not (r in seen or seen.add(r))]
    verdict = _classify(score, reasons)

    # ── Floor mechanism (Phase 8 calibration fix) ──────────────────────
    # The additive score is honest about what was matched, but it can
    # under-classify when a single canonical pattern (M&A, MNPI, embargo)
    # appears alone. Lift the band to the highest matching floor so the
    # trust badge is never quieter than the content it labels.
    floor_rank = -1
    floor_reason: str | None = None
    for pattern, floor_band, why in SENSITIVITY_FLOORS:
        try:
            if re.search(pattern, text, flags=re.IGNORECASE):
                rank = BAND_ORDER.get(floor_band, -1)
                if rank > floor_rank:
                    floor_rank = rank
                    floor_reason = why
        except re.error:
            continue
    if floor_rank >= 0:
        current_rank = BAND_ORDER.get(verdict["classification"], 0)
        if floor_rank > current_rank:
            new_band = BAND_KEYS_BY_RANK[floor_rank]
            # Pin the score to the band's lower bound so downstream UIs
            # render a coherent number alongside the lifted label.
            band_floor_score = {"public": 0, "internal": 25, "confidential": 50, "restricted": 75}[new_band]
            verdict["classification"] = new_band
            verdict["label"] = new_band.capitalize()
            verdict["score"] = max(verdict.get("score", 0), band_floor_score)
            if floor_reason:
                verdict.setdefault("reasons", []).append(f"Floor: {floor_reason}")
            verdict["floor_applied"] = floor_reason
    return verdict


async def score_sensitivity_with_llm_tiebreaker(
    artefact: Dict[str, Any],
    *,
    fallback_only: bool = True,
) -> Dict[str, Any]:
    """Iter66 — opt-in LLM tiebreaker. Calls the regex scorer first; if the
    result lands in the ambiguous "internal" band (25-49) AND the artefact
    text is long enough to warrant a second look, escalates to a single
    standard-tier LLM call asking for one of the four classifications +
    a one-line reason. The LLM result is folded into the regex result
    only if it bumps to a HIGHER band (LLM downgrades are ignored — the
    regex floor is conservative on purpose).

    `fallback_only=True` (default) means: never escalate if the regex
    already returned a confident band (public / confidential / restricted).
    Set to False to force-call the LLM on every artefact (e.g. for
    investigative re-scoring).
    """
    base = score_sensitivity(artefact)
    if fallback_only and base["classification"] != "internal":
        return base

    text = _extract_text(artefact)
    if len(text) < 200:
        # Short content rarely benefits from LLM disambiguation.
        return base

    try:
        from llm_service import call_llm, parse_json_response
    except Exception:
        return base

    user_query = (
        "Classify the following business text for board-room confidentiality. "
        "Pick exactly one of: public, internal, confidential, restricted. "
        "Use 'restricted' only if the text would compromise market position, "
        "harm individuals, or breach disclosure rules if leaked. Use 'public' "
        "if it could appear unredacted in a published report. Return JSON: "
        "{\"classification\":\"<one>\", \"reason\":\"<one short line>\"}.\n\n"
        f"Text:\n{text[:3000]}"
    )
    try:
        out = await call_llm(
            module="studio.sensitivity_tiebreaker",
            user_query=user_query,
            response_format="json",
            tier="standard",
        )
        parsed = parse_json_response(out.get("response", ""))
    except Exception:
        return base

    if not isinstance(parsed, dict):
        return base

    llm_class = (parsed.get("classification") or "").lower().strip()
    llm_reason = (parsed.get("reason") or "").strip()
    band_order = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
    if llm_class not in band_order:
        return base
    if band_order[llm_class] <= band_order.get(base["classification"], 0):
        # LLM agrees or wants to downgrade — preserve the regex result.
        return base

    # LLM bumped to a higher band. Promote, but mark the source.
    new_score_floor = {"confidential": 50, "restricted": 75}.get(llm_class, base["score"])
    new_score = max(base["score"], new_score_floor)
    new_reasons = list(base["reasons"]) + [f"LLM tiebreaker · {llm_reason or llm_class}"]
    bumped = _classify(min(new_score, 100), new_reasons)
    bumped["llm_tiebreaker_used"] = True
    return bumped


def _classify(score: int, reasons: List[str]) -> Dict[str, Any]:
    for lo, hi, key, label in CLASSIFICATION_BANDS:
        if lo <= score <= hi:
            return {
                "score": score,
                "classification": key,
                "label": label,
                "reasons": reasons,
            }
    return {"score": score, "classification": "internal", "label": "Internal", "reasons": reasons}


def exposure_score(*, unique_readers: int, share_count: int,
                   external_share_count: int = 0,
                   days_since_creation: int = 0) -> Dict[str, Any]:
    """Calculate the information exposure score for a Studio artefact.
    Higher = more eyes have seen it. Caps at 100."""
    raw = unique_readers * 12 + share_count * 18 + external_share_count * 22
    if days_since_creation > 14:
        raw += 10
    raw = max(0, min(raw, 100))
    band = "low" if raw < 30 else "moderate" if raw < 65 else "high"
    return {
        "score": raw,
        "band": band,
        "inputs": {
            "unique_readers": unique_readers,
            "share_count": share_count,
            "external_share_count": external_share_count,
            "days_since_creation": days_since_creation,
        },
    }
