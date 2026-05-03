"""Regex fast-path recognisers for the Synisense pipeline.

Promoted from `llm_service.py`'s 9-pattern shield ladder. Keep behaviour
identical — Phase 12.1 explicitly avoids changing what the regex layer
flags. New entity types belong in `presidio_engine.py` (custom
recognisers) so we keep the regex layer narrow and fast.

Each pattern returns (start, end, entity_type, replacement_template).
Replacements are deterministic per-document via a counter so the same
original token always maps to the same placeholder within one run.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

# 9 patterns, in priority order (most specific first to avoid overlap).
_PATTERNS: List[Tuple[str, str, str]] = [
    # entity_type, label_short, regex
    ("EMAIL_ADDRESS", "EMAIL", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ("PHONE_NUMBER", "PHONE", r"\+?\d{1,3}[\s.-]?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}"),
    ("IBAN_CODE", "IBAN", r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b"),
    ("CREDIT_CARD", "CARD", r"\b(?:\d[ -]*?){13,19}\b"),
    ("US_SSN", "SSN", r"\b\d{3}-\d{2}-\d{4}\b"),
    ("UK_NHS", "NHS", r"\b\d{3}\s?\d{3}\s?\d{4}\b"),
    ("IP_ADDRESS", "IP", r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    ("URL", "URL", r"\bhttps?://[^\s)]+"),
    ("DATE_TIME_EXACT", "DATE", r"\b\d{4}-\d{2}-\d{2}\b"),
]

_COMPILED = [(et, lbl, re.compile(pat)) for et, lbl, pat in _PATTERNS]


def scan(text: str) -> List[Dict[str, object]]:
    """Return a list of regex hits sorted by start offset, non-overlapping.
    Each hit is shaped:
        {start, end, entity_type, source: 'regex', confidence: 1.0,
         match_text, label_short}
    Caller is responsible for replacement-token assignment (the pipeline
    owns the deterministic counter so replacements stay stable across
    layers).
    """
    if not text:
        return []
    raw: List[Dict[str, object]] = []
    for et, lbl, pat in _COMPILED:
        for m in pat.finditer(text):
            raw.append({
                "start": m.start(), "end": m.end(),
                "entity_type": et, "label_short": lbl,
                "source": "regex", "confidence": 1.0,
                "match_text": m.group(0),
            })
    # Drop overlaps: prefer earlier start, then longer span.
    raw.sort(key=lambda h: (h["start"], -(h["end"] - h["start"])))
    out: List[Dict[str, object]] = []
    last_end = -1
    for h in raw:
        if h["start"] >= last_end:
            out.append(h)
            last_end = h["end"]
    return out
