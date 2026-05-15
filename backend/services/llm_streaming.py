"""Re-export shim for the relocated streaming module.

The implementation moved to `services/synisense/shield/streaming.py` as
part of Phase B (LLM Call Migration, 2026-05-13). This file remains
ONLY to keep existing imports working without forcing a sweep across
every call site. New code should import from
`services.synisense.shield.streaming` directly.

The CI guard (`tests/test_no_direct_llm_calls_outside_shield.py`)
considers this file Shield-adjacent because it only re-exports —
it does NOT import the SDK itself.
"""
from services.synisense.shield.streaming import (  # noqa: F401
    LlmStreamChunk,
    collect_llm_text,
    provider_for_model,
    streaming_mode_per_provider,
    stream_llm_direct,
)
