"""Track A Phase 3 (2026-06-04) — Solva v2 Analyze narration.

Wraps the deterministic WorkbookAnalysis output (signals,
simulations, forecasts, anomalies) and asks Claude Sonnet via
`shield_invoke` to produce a journalistic, headline-first
narration with cited evidence.

Three guards:

  1. Refuse-to-decide. If the deterministic outputs are empty (no
     signals + no forecasts + no anomalies), we DO NOT call the
     LLM — we return an empty narration object. Refuses to
     invent claims with no evidence.

  2. Citation resolver. Every observation the LLM emits carries
     an `evidence_citation_indices: [int, ...]` list. The
     resolver verifies each index is in-range against the
     deterministic citation pool. Out-of-range indices drop the
     observation (NOT the whole narration). No hallucinated cell
     refs ever persist.

  3. Voice-lint. Customer-copy lint applied to the narration
     output before persist. The lint surface for Phase 3 is the
     observation `body` field; the headline is also linted.

Idempotency: a content hash of (objective + deterministic blocks)
is computed; re-call with the same hash returns the cached
narration from the Analysis row.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from services.synisense.shield.client import invoke as shield_invoke
from services.workbook_analyzer.schema import WorkbookAnalysis


@dataclass
class _DetBlock:
    """Internal aggregation of one deterministic finding +
    its citation. The narration prompt sees these as a flat list."""
    label: str        # short identifier surfaced to the LLM
    kind: str         # signal | forecast | anomaly | simulation
    detail: str       # one-line natural-language summary
    citation: Dict[str, str]  # {"cell_range": "Sheet!A1:B12", "excerpt": ...}


def _collect_deterministic(analysis: WorkbookAnalysis) -> List[_DetBlock]:
    """Build the citation-bearing block list from a WorkbookAnalysis."""
    out: List[_DetBlock] = []
    # Signals
    for s in (analysis.signals or []):
        cite = (s.citations or [None])[0]
        if not cite:
            continue
        out.append(_DetBlock(
            label=f"signal/{s.kind}/{s.title[:40]}",
            kind="signal",
            detail=f"{s.title} — {s.detail}",
            citation={"cell_range": cite.cell_range, "excerpt": cite.excerpt or ""},
        ))
    # Forecasts
    for f in (analysis.forecasts or []):
        cite = (f.citations or [None])[0]
        if not cite or not f.projections:
            continue
        last = f.projections[-1]
        out.append(_DetBlock(
            label=f"forecast/{f.value_column}",
            kind="forecast",
            detail=(
                f"Linear regression on ({f.date_column}, {f.value_column}) — "
                f"slope {f.slope:.4f}, R² {f.r2:.3f}; the +{last['period_index']} "
                f"step projection is {last['value']:.2f} (80% CI {last['ci_low']:.2f}–{last['ci_high']:.2f})."
            ),
            citation={"cell_range": cite.cell_range, "excerpt": cite.excerpt or ""},
        ))
    # Anomalies
    for a in (analysis.anomalies or []):
        cite = (a.citations or [None])[0]
        if not cite:
            continue
        out.append(_DetBlock(
            label=f"anomaly/{a.sheet}/{a.column}/r{a.row_index}",
            kind="anomaly",
            detail=(
                f"Row {a.row_index} of {a.sheet}!{a.column} value={a.value:.2f} "
                f"(z={a.z_score:+.2f}, IQR-distance={a.iqr_distance:+.2f}). {a.rationale}"
            ),
            citation={"cell_range": cite.cell_range, "excerpt": cite.excerpt or ""},
        ))
    # Simulations (no per-block citation; treat as adjuncts to the forecast).
    for m in (analysis.simulations or []):
        out.append(_DetBlock(
            label=f"simulation/{m.column}",
            kind="simulation",
            detail=(
                f"{m.iterations}-iteration Monte Carlo on {m.column}: median "
                f"{m.p50:.2f}; central 80% between {m.p10:.2f} and {m.p90:.2f}."
            ),
            citation={"cell_range": "", "excerpt": ""},
        ))
    return out


def _content_hash(*, objective: str, blocks: List[_DetBlock]) -> str:
    h = hashlib.sha256()
    h.update((objective or "").encode("utf-8"))
    for b in blocks:
        h.update(b.kind.encode())
        h.update(b.label.encode())
        h.update(b.detail.encode())
        h.update(b.citation.get("cell_range", "").encode())
    return h.hexdigest()[:24]


def _build_prompt(*, objective: str, blocks: List[_DetBlock]) -> str:
    objective_line = objective.strip() or "(none provided)"
    evidence_lines = []
    for i, b in enumerate(blocks):
        evidence_lines.append(
            f"[{i}] kind={b.kind} :: {b.detail}  (cite={b.citation.get('cell_range') or 'n/a'})"
        )
    evidence_joined = "\n".join(evidence_lines) if evidence_lines else "(none)"
    return f"""You are an analytical narrator producing an executive read-out of a
deterministic spreadsheet analysis. You may ONLY narrate the evidence
listed below; do NOT invent figures or claims.

User objective: {objective_line}

Deterministic evidence (each numbered; cite by index):
{evidence_joined}

Return STRICT JSON with this shape (no markdown fences):
{{
  "headline": "ONE journalistic sentence summarizing the bottom line. Lead with the most surprising finding.",
  "observations": [
    {{
      "tab": "what_changed" | "whats_likely_next" | "whats_odd",
      "title": "Headline-first 6-12 word title",
      "body": "Plain-English paragraph framing the evidence for a non-analyst executive. Frame anomalies as 'this Friday in February drove 3% of annual sales, may want to investigate', NOT as 'row 20657 is 84σ above mean'.",
      "evidence_citation_indices": [<int>, ...]
    }}
  ]
}}

Rules:
- Output JSON only (no prose around it).
- Group: what_changed = signals; whats_likely_next = forecasts + simulations; whats_odd = anomalies.
- Each observation MUST reference at least one evidence index from the list above.
- If the evidence list is empty or contains no signals/forecasts/anomalies, return
  {{"headline": "", "observations": []}}.
- Do not use the words "suggest", "recommend", "should", "advise", or "I think".
"""


def _resolve_citations(observations: List[Dict[str, Any]], blocks: List[_DetBlock]) -> List[Dict[str, Any]]:
    """Filter to observations whose citation indices ALL resolve to
    real deterministic blocks. Drops out-of-range obs entirely (no
    silent rewrites)."""
    out: List[Dict[str, Any]] = []
    n = len(blocks)
    for obs in observations:
        idxs = obs.get("evidence_citation_indices") or []
        if not isinstance(idxs, list) or not idxs:
            continue
        if not all(isinstance(i, int) and 0 <= i < n for i in idxs):
            continue  # citation_resolver refusal
        # Attach resolved citation objects so the FE doesn't need
        # an extra round-trip.
        resolved = []
        for i in idxs:
            resolved.append({
                "index":      i,
                "cell_range": blocks[i].citation.get("cell_range", ""),
                "excerpt":    blocks[i].citation.get("excerpt", ""),
                "kind":       blocks[i].kind,
            })
        obs["citations"] = resolved
        out.append(obs)
    return out


def _voice_lint(text: str) -> bool:
    """Phase 3 voice-lint stub for LLM-emitted narration. Mirrors
    the scripts/lint_voice.py banned-word set; rejects narration
    that uses imperative voice or "I think"-style hedging."""
    banned = (" suggest", " recommend", " should", " advise", " I think", " I recommend")
    lowered = " " + text.lower()
    return not any(b in lowered for b in banned)


def _extract_json_payload(raw: str) -> Optional[str]:
    """Track A Phase 3 R3 BLOCKER fix (2026-06-04).

    Claude Sonnet (and several other models behind shield_invoke)
    routinely wrap structured output in markdown fences:

        ```json
        {"headline": ...}
        ```

    or with leading prose:

        Here's the analysis:
        ```json
        {"headline": ...}
        ```

    The previous parser passed `raw` straight to `json.loads`, which
    raised on every fenced response — surfaced as
    `refusal_reason="llm_returned_non_json"` even when the LLM had
    produced clean JSON. The synthesize endpoint then persisted an
    empty narration, masking even the deterministic forecast output
    (Bug #30 J20 also failed by dependence).

    This helper walks four candidate-extraction strategies, in order
    of specificity, and returns the first one that parses. None →
    caller falls back to the refusal path.
    """
    if not raw:
        return None
    text = raw.strip()

    # (1) Bare JSON object — current happy path, preserved.
    if text.startswith("{") and text.endswith("}"):
        return text

    # (2) ```json … ``` fenced block (case-insensitive language hint).
    m = re.search(r"```(?:json|JSON|Json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # (3) Leading prose, then a top-level JSON object somewhere in the
    #     string. Use a depth-balanced sweep starting at the first `{`
    #     so we capture the entire object even if it contains nested
    #     `}`s (the regex above is non-greedy and may stop short).
    first_brace = text.find("{")
    if first_brace >= 0:
        depth = 0
        in_string = False
        escape = False
        for i in range(first_brace, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[first_brace:i + 1]

    return None


async def narrate_analysis(
    *,
    workbook_analysis: WorkbookAnalysis,
    account_id: str,
    objective: str = "",
    cached: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the narration pipeline. Returns
    `{headline, observations[], citations[], cache_key, refused}`.

    `cached` is the previously-persisted narration object (or None);
    if its `cache_key` matches the current content hash, returns it
    unchanged.
    """
    blocks = _collect_deterministic(workbook_analysis)
    citeable = [b for b in blocks if b.kind in {"signal", "forecast", "anomaly"}]
    cache_key = _content_hash(objective=objective, blocks=blocks)

    # Idempotency — same content hash → return cached.
    if cached and cached.get("cache_key") == cache_key:
        return cached

    # Refuse-to-decide — no citeable evidence → empty narration.
    if not citeable:
        return {
            "headline": "",
            "observations": [],
            "citations": [],
            "cache_key": cache_key,
            "refused": True,
            "refusal_reason": "no_deterministic_evidence",
        }

    prompt = _build_prompt(objective=objective, blocks=blocks)
    try:
        shield_out = await shield_invoke(
            purpose="solva.layer_3.synthesis_rendering",
            content=prompt,
            tenant_id=account_id,
            consumer_id="solva",
            user_id=account_id,
            model_preference="analytical",
        )
    except Exception:  # noqa: BLE001
        # Shield refusal / LLM unavailable → empty narration, NOT fabricated.
        return {
            "headline": "",
            "observations": [],
            "citations": [],
            "cache_key": cache_key,
            "refused": True,
            "refusal_reason": "shield_invoke_failed",
        }

    raw = shield_out.get("response") or ""
    payload_str = _extract_json_payload(raw)
    if payload_str is None:
        return {
            "headline": "",
            "observations": [],
            "citations": [],
            "cache_key": cache_key,
            "refused": True,
            "refusal_reason": "llm_returned_non_json",
        }
    try:
        parsed = json.loads(payload_str)
    except Exception:  # noqa: BLE001
        return {
            "headline": "",
            "observations": [],
            "citations": [],
            "cache_key": cache_key,
            "refused": True,
            "refusal_reason": "llm_returned_non_json",
        }

    headline = str(parsed.get("headline") or "").strip()
    observations = parsed.get("observations") or []
    if not isinstance(observations, list):
        observations = []

    # Voice-lint pass — drop any observation that uses banned voice.
    observations = [
        o for o in observations
        if isinstance(o, dict)
        and _voice_lint(str(o.get("body") or ""))
        and _voice_lint(str(o.get("title") or ""))
    ]
    if not _voice_lint(headline):
        headline = ""

    # Citation resolver — drops out-of-range references.
    observations = _resolve_citations(observations, blocks)

    return {
        "headline": headline,
        "observations": observations,
        "citations": [
            {"index": i, "cell_range": b.citation.get("cell_range", ""), "kind": b.kind}
            for i, b in enumerate(blocks)
        ],
        "cache_key": cache_key,
        "refused": False,
    }


__all__ = ["narrate_analysis"]
