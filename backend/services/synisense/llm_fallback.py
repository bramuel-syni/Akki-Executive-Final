"""Re-export shim for the relocated legacy LLM-NER fallback.

The implementation moved to
`services/synisense/shield/_legacy_llm_fallback.py` as part of
Phase B (LLM Call Migration, 2026-05-13). The Phase 12.1 Presidio
pipeline still references this module; once Phase B+ retires that
pipeline this shim can be deleted.

New code should NOT import from here — the Phase A Shield pipeline
already does its own local-spaCy NER.
"""
from services.synisense.shield._legacy_llm_fallback import (  # noqa: F401
    classify_low_confidence,
)
