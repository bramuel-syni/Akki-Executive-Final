"""Phase AA-slice-2 (2026-05-27) — LLM prompt templates.

Pulled out of `extraction.py` so the main service stays under the
500-line auto-slice budget. Two prompts — goals + tasks — each
returns a JSON object with one top-level array.

Template variables (filled via `str.format`):
  `doc_name`     — display name
  `chunk_idx`    — 1-indexed chunk number
  `chunk_total`  — total number of chunks
  `doc_text`     — the chunk's text

Tests source-lock the leading literal of each template so the
prompt contract can't drift silently.
"""
from __future__ import annotations


GOALS_PROMPT_TEMPLATE = (
    "You are reading a strategic / governance document for an "
    "executive team. Extract the BOARD-LEVEL STRATEGIC GOALS the "
    "document tracks — measurable outcomes the company is steering "
    "toward over multiple quarters. Skip operational tasks; those "
    "are extracted by a separate pass.\n\n"
    "DOCUMENT TITLE: {doc_name}\n\n"
    "DOCUMENT TEXT (chunk {chunk_idx} of {chunk_total}):\n"
    "{doc_text}\n\n"
    "Return STRICT JSON ONLY with this exact shape:\n"
    '{{"goals": [\n'
    '  {{\n'
    '    "title":              "<short title, 2-180 chars>",\n'
    '    "description":        "<<=600 chars optional detail>",\n'
    '    "department":         "<ceo|cfo|coo|commercial|board>",\n'
    '    "category":           "<revenue|customer|product|people|operations|compliance>",\n'
    '    "status":             "<on_track|at_risk|off_track|achieved|abandoned>",\n'
    '    "target_value":       "<the target as a string, blank if unknown>",\n'
    '    "target_date":        "<YYYY-MM or Q4 2026, blank if unknown>",\n'
    '    "current_score":      <integer 0-100, 0 if unknown>,\n'
    '    "probability":        <integer 0-100, 0 if unknown>\n'
    '  }}\n'
    ']}}\n\n'
    "Rules: at most 20 goals; ONLY items the board would track; "
    "do NOT invent numbers; use 'on_track' + 'operations' as "
    "defaults under uncertainty."
)


TASKS_PROMPT_TEMPLATE = (
    "You are reading a strategic / governance document for an "
    "executive team. Extract the SPECIFIC WORK ITEMS, PROJECTS, "
    "INITIATIVES the document references — concrete actions the "
    "company is taking. Skip board-level strategic outcomes; those "
    "are extracted by a separate pass.\n\n"
    "DOCUMENT TITLE: {doc_name}\n\n"
    "DOCUMENT TEXT (chunk {chunk_idx} of {chunk_total}):\n"
    "{doc_text}\n\n"
    "Return STRICT JSON ONLY with this exact shape:\n"
    '{{"tasks": [\n'
    '  {{\n'
    '    "title":              "<short title, 2-180 chars>",\n'
    '    "body":               "<<=4000 char description or null>",\n'
    '    "category":           "<revenue|customer|product|people|operations|compliance>",\n'
    '    "owner_role":         "<CEO|CFO|COO|CRO|CTO|CHRO|CMO|CIO|OTHER|null>",\n'
    '    "status":             "<on_track|at_risk|off_track|achieved|not_started>",\n'
    '    "performance_score":  <integer 0-100>,\n'
    '    "probability_score":  <integer 0-100>\n'
    '  }}\n'
    ']}}\n\n'
    "Rules: at most 20 tasks; do NOT invent owners or scores; "
    "use 'not_started' + 'operations' as defaults under "
    "uncertainty; owner_role may be null if the document doesn't "
    "say who's accountable."
)
