"""Regex fast-path recognisers for the Synisense pipeline.

Promoted from `llm_service.py`'s 9-pattern shield ladder. Keep behaviour
identical for the legacy 9 — Phase 12.1 explicitly avoided changing what
that layer flags. New entity types belong in `presidio_engine.py` (custom
recognisers) so we keep the regex layer narrow and fast.

Phase 12.3 ITEM A — DEAL_CODENAME promoted from a Presidio
PatternRecognizer to a regex pre-pass. Stock Presidio NER consistently
labelled "Project Falcon" / "Project Atlas" as PERSON or ORGANIZATION
because spaCy's `en_core_web_sm` returns those with confidence ≥ 0.85,
which beat the custom DEAL_CODENAME PatternRecognizer's tied score
inside Presidio's internal merge. Redaction still happened, but the
histogram label was wrong, polluting the TrustPanel narrative. The
pipeline's `_merge_spans()` already gives regex precedence over
Presidio (regex hits added first; overlapping Presidio spans skipped),
so detecting "Project <X>" in the regex layer is the deterministic fix
without monkey-patching Presidio internals. The Presidio
PatternRecognizer for DEAL_CODENAME is removed in tandem to keep the
taxonomy single-sourced.

Each pattern returns (start, end, entity_type, replacement_template).
Replacements are deterministic per-document via a counter so the same
original token always maps to the same placeholder within one run.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

# Patterns, in priority order (most specific first to avoid overlap).
# DEAL_CODENAME is broader than the legacy 9 — it deliberately sits last
# so it never accidentally swallows a more specific pattern that begins
# with a capital word (it doesn't, today, but the ordering is the
# defensive choice).
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
    # Phase 12.3 ITEM A — board codename detection. Matches "Project Foo"
    # and "Operation Foo Bar" with up to two trailing PascalCase tokens.
    # Word-boundary anchors keep accidental contamination off when the
    # phrase appears mid-sentence.
    ("DEAL_CODENAME", "DEAL",
     r"\b(?:Project|Operation)\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2}\b"),
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
