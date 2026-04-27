"""Best-effort JSON parsing for LLM responses.

Claude (and to a lesser extent the other providers) sometimes wraps strict-
JSON output in markdown fences (```json ... ```) despite explicit JSON-only
instructions. Multiple routers were repeating the same fence-strip + fallback
boilerplate; this consolidates it.

Usage:
    from helpers.llm_json import safe_parse_json

    parsed, raw = safe_parse_json(llm_response_text)
    title = parsed.get("title") or fallback
"""
from __future__ import annotations

import json
from typing import Any, Dict, Tuple


def safe_parse_json(raw: Any) -> Tuple[Dict[str, Any], str]:
    """Parse `raw` as JSON, stripping ```json fences first.

    Returns `(parsed_dict, raw_str)`. `parsed_dict` is `{}` when the response
    cannot be parsed — callers should fall back to `raw_str` (or another
    default) when the dict is empty.
    """
    if raw is None:
        return {}, ""

    raw_str = raw if isinstance(raw, str) else str(raw)
    cleaned = raw_str.strip()

    if cleaned.startswith("```"):
        # ```json\n{...}\n```  →  {...}
        parts = cleaned.split("```", 2)
        if len(parts) >= 2:
            cleaned = parts[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.rsplit("```", 1)[0].strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed, raw_str
        # Non-dict JSON (list, string, etc.) — let the caller handle the raw.
        return {}, raw_str
    except (json.JSONDecodeError, TypeError):
        return {}, raw_str
