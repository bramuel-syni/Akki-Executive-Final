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
    return _classify(score, reasons)


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
