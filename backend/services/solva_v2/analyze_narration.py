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
from services.workbook_analyzer import _FORECAST_LOW_R2_THRESHOLD


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


def _build_prompt(
    *,
    objective: str,
    blocks: List[_DetBlock],
    workbook_context: Optional[Dict[str, Any]] = None,
    forecast_meta: Optional[Dict[str, Any]] = None,
) -> str:
    """Build the LLM prompt.

    Track A Phase 3 R3v3 (2026-06-04) — surfaces SIGNALS BLOCK /
    FORECAST BLOCK / ANOMALIES BLOCK explicitly, and REQUIREs the
    matching observation tab for each non-empty block:

      • Signals exist → require `what_changed` observation(s).
      • Forecast attempted (autopick succeeded) → require
        `whats_likely_next` observation, even if the deterministic
        forecast vector was empty (engine couldn't fit a line).
      • Anomalies exist → require `whats_odd` observation(s).

    Each block that is empty surfaces an explicit "no X — omit the
    corresponding tab" line so Claude doesn't fabricate tabs that
    have no evidence.
    """
    objective_line = objective.strip() or "(none provided)"

    # Partition deterministic evidence by kind so the prompt can
    # surface each as a labeled block. Indices are preserved across
    # the flat list so observations can still cite by index.
    signal_lines: List[str] = []
    forecast_lines: List[str] = []
    anomaly_lines: List[str] = []
    sim_lines: List[str] = []
    for i, b in enumerate(blocks):
        line = (
            f"[{i}] {b.detail}  (cite={b.citation.get('cell_range') or 'n/a'})"
        )
        if b.kind == "signal":
            signal_lines.append(line)
        elif b.kind == "forecast":
            forecast_lines.append(line)
        elif b.kind == "anomaly":
            anomaly_lines.append(line)
        elif b.kind == "simulation":
            sim_lines.append(line)

    has_signals = bool(signal_lines)
    has_forecast_vector = bool(forecast_lines)
    has_anomalies = bool(anomaly_lines)

    # Forecast tab is required when EITHER (a) the deterministic
    # forecast vector is present OR (b) the autopicker succeeded but
    # the engine returned no projections — in case (b) the prompt
    # tells Claude to narrate what the (date_col, value_col) attempt
    # implies based on signals + anomalies.
    forecast_attempted = bool(forecast_meta and forecast_meta.get("date_col"))
    forecast_required = has_forecast_vector or forecast_attempted

    # ── Workbook context block ────────────────────────────────
    ctx = workbook_context or {}
    date_cols = ctx.get("date_columns") or []
    numeric_cols = ctx.get("numeric_columns") or []
    source_files = ctx.get("source_files") or []
    workbook_ctx_block = ""
    if date_cols:
        workbook_ctx_block = (
            "\nWORKBOOK STRUCTURE\n"
            "The first column is a temporal axis (e.g. dates, months, "
            "quarters). Rows represent points in time, NOT entities or "
            "locations. Narrate trends across periods, not across "
            "entities.\n"
            f"Date columns: {', '.join(date_cols)}\n"
            f"Numeric columns: {', '.join(numeric_cols) or '(none)'}\n"
        )

    # Track A Phase 4 (2026-06-04) — multi-source roster. When the
    # synthesis is over 2+ workbooks, the sheet names in deterministic
    # citations carry a `<filename-stem>::<sheet>` prefix. The roster
    # block tells the LLM which file each prefix maps to so cross-file
    # attribution lands in the narration ("Lighthouse's Q1 contrasts
    # with Apollo's Q1 dip"). Single-file analyses skip the block
    # entirely so the prompt stays identical to Phase 3.
    multi_source_block = ""
    if len(source_files) >= 2:
        roster_lines: List[str] = []
        for sf in source_files:
            label = sf.get("filename", "source")
            if sf.get("parse_failed"):
                roster_lines.append(
                    f"  - {label}: parse failed; ignore for this run."
                )
            else:
                stem = (sf.get("filename") or "source").rsplit(".", 1)[0][:30]
                roster_lines.append(
                    f"  - {label}: sheet-prefix `{stem}::` "
                    f"({sf.get('sheet_count', 0)} sheet(s))"
                )
        multi_source_block = (
            "\nSOURCE FILES (multi-workbook synthesis)\n"
            "This run synthesises evidence across the following "
            "workbooks. Each deterministic citation's sheet name is "
            "prefixed with the source's filename stem and a `::` "
            "separator (e.g. `apollo_q1::Sales`). When attributing a "
            "finding, name the source workbook in plain English (NOT "
            "the prefix) so the narration reads naturally.\n"
            + "\n".join(roster_lines)
            + "\n"
        )

    # ── Three labeled deterministic blocks ────────────────────
    signals_block = "\nSIGNALS BLOCK\n" + (
        "\n".join(signal_lines) if signal_lines else "(no signals — OMIT `what_changed` tab)"
    ) + "\n"
    if forecast_attempted:
        fc_header = (
            f"\nFORECAST BLOCK\n"
            f"Autopicker chose ({forecast_meta['date_col']}, "
            f"{forecast_meta['value_col']}); "
            f"reason: {forecast_meta.get('picker_reason', 'n/a')}.\n"
        )
        if has_forecast_vector:
            fc_body = "\n".join(forecast_lines) + "\n"
        else:
            # Track A Phase 3 R3v4 (2026-06-04) — the prior copy
            # contained the all-caps sentinel "EMPTY" which Claude
            # echoed verbatim into prose ("...EMPTY attempted to model
            # the relationship..."). Rewritten as a humanised sentence
            # with no sentinel tokens.
            fc_body = (
                "The deterministic forecast engine could not fit a "
                f"linear model to ({forecast_meta['date_col']}, "
                f"{forecast_meta['value_col']}) on this workbook. "
                "Narrate what is likely next using the SIGNALS and "
                "ANOMALIES BLOCKS above and below in plain business "
                "language; DO NOT fabricate any numeric projection.\n"
            )
        forecast_block = fc_header + fc_body
    else:
        forecast_block = (
            "\nFORECAST BLOCK\n"
            "(no forecast attempted — OMIT `whats_likely_next` tab)\n"
        )
    anomalies_block = "\nANOMALIES BLOCK\n" + (
        "\n".join(anomaly_lines) if anomaly_lines else "(no anomalies — OMIT `whats_odd` tab)"
    ) + "\n"
    sims_block = ""
    if sim_lines:
        sims_block = "\nSIMULATIONS BLOCK (supporting evidence; group under `whats_likely_next`)\n" + "\n".join(sim_lines) + "\n"

    # ── REQUIREMENTS line (per-block) ────────────────────────
    req_parts: List[str] = []
    if has_signals:
        req_parts.append(
            "`what_changed` (at least one entry; cite the SIGNALS BLOCK)"
        )
    if forecast_required:
        req_parts.append(
            "`whats_likely_next` (at least one entry; narrate the FORECAST BLOCK)"
        )
    if has_anomalies:
        req_parts.append(
            "`whats_odd` (at least one entry; cite the ANOMALIES BLOCK)"
        )
    if req_parts:
        required_tabs_line = (
            "REQUIREMENTS — your `observations` array MUST contain "
            + "; AND ".join(req_parts)
            + ". Omitting a required tab when its block has data is a "
              "contract violation. The bottom-line headline is "
              "mandatory regardless."
        )
    else:
        required_tabs_line = (
            "REQUIREMENTS — every deterministic block is empty; return "
            '`{"headline": "", "observations": []}`.'
        )

    return f"""You are a strategy partner writing the bottom-line read-out for a
McKinsey-style executive briefing memo. You may ONLY narrate the
evidence listed below; do NOT invent figures or claims.

VOICE
- Headline-first. Lead with what happened in plain business
  language: "Q1 actual sales fell 14% YoY across the trade book",
  NOT "the time-series shows a 14% decrease from prior period".
- Translate statistics into so-what language. A 2.11σ outlier is
  "one month broke pattern", not "row 25 is 2.11 standard
  deviations above the mean".
- BANNED in headline and observation body: the words/symbols
  "standard deviation", "σ", "sigma", "variance", "percentile",
  "z-score". (Statisticians read the Sources tab; executives read
  this narration.)
- Frame rows as time periods, not as entities.

Good headline example:
  "Q1 actual sales fell 14% YoY across the trade book despite
   quantity holding +12% — pricing power eroded in three regions."
Bad headline example (rejected):
  "A single location in Revenue recorded revenue more than twice
   the standard deviation above average."

User objective: {objective_line}
{workbook_ctx_block}{multi_source_block}{signals_block}{forecast_block}{anomalies_block}{sims_block}
{required_tabs_line}

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
- Group: what_changed = signals; whats_likely_next = forecast + simulations; whats_odd = anomalies.
- Each observation MUST reference at least one evidence index from the deterministic blocks above.
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


# Track A Phase 3 R3v2 (2026-06-04) — banned statistical jargon in
# headlines. The Sources tab keeps the raw stats; the McKinsey-tone
# headline + observation body must NOT carry them. Symbols/words
# are matched case-insensitively, anchored with word boundaries
# where applicable (the bare 'σ' and 'sigma' are symbol-style and
# always rejected on substring match).
_BANNED_HEADLINE_JARGON: tuple = (
    "σ",
    "sigma",
    "standard deviation",
    "std deviation",
    "std dev",
    "variance",
    "percentile",
    "z-score",
    "z score",
)


def _headline_has_banned_jargon(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(b in lowered for b in _BANNED_HEADLINE_JARGON)


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


def _validate_observation_completeness(
    *,
    observations: List[Dict[str, Any]],
    blocks: List["_DetBlock"],
    forecast_attempted: bool,
) -> Dict[str, bool]:
    """Track A Phase 3 R3v4 (2026-06-04) — post-Shield completeness
    validator.

    Walks the deterministic block set and the final observation list
    (post voice-lint, post banned-jargon, post citation-resolver) and
    returns a dict of `partial_narration_missing_{tab}: true` flags
    for every required tab whose observation is absent.

    Contract:
      • Block has data → tab is required.
      • `forecast_attempted` (autopicker succeeded even if the
        deterministic vector was empty) → `whats_likely_next` is
        required so the FE always renders a forecast surface.
      • Missing observation when block populated → flag fires.
      • Backwards-compat alias `partial_narration_missing_forecast`
        is set when `whats_likely_next` is missing (R3v2 consumers).

    No silent empty — every required tab without a backing
    observation surfaces a flag the FE can render.
    """
    required_tabs: set = set()
    if any(b.kind == "signal" for b in blocks):
        required_tabs.add("what_changed")
    if any(b.kind == "forecast" for b in blocks) or forecast_attempted:
        required_tabs.add("whats_likely_next")
    if any(b.kind == "anomaly" for b in blocks):
        required_tabs.add("whats_odd")

    present: set = set()
    for o in observations:
        tab = o.get("tab") if isinstance(o, dict) else None
        if tab in {"what_changed", "whats_likely_next", "whats_odd"}:
            present.add(tab)

    flags: Dict[str, bool] = {}
    for tab in (required_tabs - present):
        flags[f"partial_narration_missing_{tab}"] = True

    # Track A Phase 3 R3v5 (2026-06-04) — safety-net branch.
    # When the autopicker rejected the workbook (`forecast_attempted=
    # False`) but the LLM still produced ≥1 observation, the user
    # has genuinely lost forward-looking commentary even though no
    # deterministic forecast block was ever attempted. Surface a
    # banner so the FE can render "forecast not attempted on this
    # workbook" instead of a silent single-tab render.
    #
    # IMPORTANT — narrow scope. The safety-net only fires for
    # `whats_likely_next` (the forecast tab's whole point is
    # forward-looking). It does NOT auto-imply `whats_odd` missing:
    # an anomalies block that ran and found zero records is a clean
    # workbook, not a missing tab — firing a flag there would cry
    # wolf on every clean spreadsheet.
    if (
        not forecast_attempted
        and not any(b.kind == "forecast" for b in blocks)
        and len(observations) >= 1
        and "whats_likely_next" not in present
    ):
        flags["partial_narration_missing_whats_likely_next"] = True

    # Backwards-compat alias for R3v2 consumers — fires whenever
    # `whats_likely_next` is missing, by required-tab path OR by
    # the safety-net path above.
    if flags.get("partial_narration_missing_whats_likely_next"):
        flags["partial_narration_missing_forecast"] = True
    return flags


async def narrate_analysis(
    *,
    workbook_analysis: WorkbookAnalysis,
    account_id: str,
    objective: str = "",
    cached: Optional[Dict[str, Any]] = None,
    workbook_context: Optional[Dict[str, Any]] = None,
    forecast_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the narration pipeline. Returns
    `{headline, observations[], citations[], cache_key, refused,
      forecast_meta?, partial_narration_missing_forecast?}`.

    `cached` is the previously-persisted narration object (or None);
    if its `cache_key` matches the current content hash, returns it
    unchanged.

    Track A Phase 3 R3v2 (2026-06-04) — extended signature:
      • `workbook_context`: `{date_columns: [..], numeric_columns: [..]}`
        injected into the prompt so Claude knows rows are points in
        time, NOT entities.
      • `forecast_meta`: `{date_col, value_col, picker_reason}` —
        when present, the prompt REQUIRES a `whats_likely_next`
        observation. If the LLM omits it, we bounded-retry once and
        then set `partial_narration_missing_forecast: true` so the
        FE can surface "forecast not narrated this run".
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

    prompt = _build_prompt(
        objective=objective,
        blocks=blocks,
        workbook_context=workbook_context,
        forecast_meta=forecast_meta,
    )

    async def _invoke_once(prompt_text: str) -> Optional[Dict[str, Any]]:
        try:
            shield_out = await shield_invoke(
                purpose="solva.layer_3.synthesis_rendering",
                content=prompt_text,
                tenant_id=account_id,
                consumer_id="solva",
                user_id=account_id,
                model_preference="analytical",
            )
        except Exception:  # noqa: BLE001
            return None
        raw = shield_out.get("response") or ""
        payload_str = _extract_json_payload(raw)
        if payload_str is None:
            return None
        try:
            return json.loads(payload_str)
        except Exception:  # noqa: BLE001
            return None

    parsed = await _invoke_once(prompt)
    if parsed is None:
        return {
            "headline": "",
            "observations": [],
            "citations": [],
            "cache_key": cache_key,
            "refused": True,
            "refusal_reason": "shield_invoke_failed",
        }

    # Track A Phase 3 R3v3 (2026-06-04) — compute the set of required
    # tabs based on which deterministic blocks have data. Forecast tab
    # is also required when autopick succeeded but the deterministic
    # forecast vector is empty (so the LLM narrates the attempt).
    has_signals = any(b.kind == "signal" for b in blocks)
    has_forecast_vector = any(b.kind == "forecast" for b in blocks)
    has_anomalies = any(b.kind == "anomaly" for b in blocks)
    forecast_attempted = bool(forecast_meta and forecast_meta.get("date_col"))
    required_tabs: set = set()
    if has_signals:
        required_tabs.add("what_changed")
    if has_forecast_vector or forecast_attempted:
        required_tabs.add("whats_likely_next")
    if has_anomalies:
        required_tabs.add("whats_odd")

    def _tabs_present(p: Dict[str, Any]) -> set:
        out: set = set()
        for o in p.get("observations") or []:
            if isinstance(o, dict) and o.get("tab") in {
                "what_changed", "whats_likely_next", "whats_odd",
            }:
                out.add(o["tab"])
        return out

    # Bounded retry (max 1 per synthesize call total). If ANY required
    # tab is missing, retry once with a stern reminder listing the
    # specific missing tabs.
    missing = required_tabs - _tabs_present(parsed)
    if missing:
        retry_prompt = (
            "PREVIOUS ATTEMPT VIOLATED THE REQUIRED-TABS CONTRACT.\n"
            f"Your prior response was missing observations for: "
            f"{sorted(missing)}. Each missing tab has deterministic "
            "block data above and MUST be narrated. Retry now and "
            "include at least one observation for EACH of: "
            f"{sorted(required_tabs)}.\n\n"
        ) + prompt
        retry_parsed = await _invoke_once(retry_prompt)
        if retry_parsed is not None:
            # Accept the retry only if it materially closes the gap
            # (covers MORE of the required tabs than the first try).
            retry_present = _tabs_present(retry_parsed)
            first_present = _tabs_present(parsed)
            if len(retry_present & required_tabs) > len(first_present & required_tabs):
                parsed = retry_parsed

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

    # Banned-jargon-in-headline lockdown (Track A Phase 3 R3v2).
    # The Sources tab carries σ / standard deviation / variance /
    # percentile / z-score; the McKinsey-tone headline must NOT.
    # On hit: blank the headline (NOT the whole narration) — the
    # FE renders the observations + a "headline rejected" note.
    if _headline_has_banned_jargon(headline):
        headline = ""

    # Citation resolver — drops out-of-range references.
    observations = _resolve_citations(observations, blocks)

    # Track A Phase 3 R3v4 (2026-06-04) — explicit post-Shield
    # completeness validator. Walks deterministic blocks vs final
    # observation list and emits per-tab `partial_narration_missing_
    # {tab}` flags. See `_validate_observation_completeness` docstring.
    completeness_flags = _validate_observation_completeness(
        observations=observations,
        blocks=blocks,
        forecast_attempted=bool(forecast_meta and forecast_meta.get("date_col")),
    )

    result: Dict[str, Any] = {
        "headline": headline,
        "observations": observations,
        "citations": [
            {"index": i, "cell_range": b.citation.get("cell_range", ""), "kind": b.kind}
            for i, b in enumerate(blocks)
        ],
        "cache_key": cache_key,
        "refused": False,
    }
    if forecast_meta:
        # Surface the autopicker choice to the FE for observability.
        result["forecast_meta"] = {
            "date_col": forecast_meta.get("date_col"),
            "value_col": forecast_meta.get("value_col"),
            "picker_reason": forecast_meta.get("picker_reason", ""),
            "r2": forecast_meta.get("r2"),  # may be None if engine didn't fit
        }
        # Track A Phase 4 (2026-06-04) — low-R² safety-net flag.
        # Parallel to Phase 3 R3v5's safety-net branch but for forecast
        # QUALITY rather than forecast PRESENCE. When the engine fit a
        # model but R² is below `_FORECAST_LOW_R2_THRESHOLD` (default
        # 0.30 = "noise"), the FE should render the forecast block
        # with a "low confidence" banner — the data fit but the signal
        # is weak. Block is NOT dropped (deterministic engine output
        # preserved); just flagged.
        r2 = forecast_meta.get("r2")
        if r2 is not None and r2 < _FORECAST_LOW_R2_THRESHOLD:
            result["partial_narration_missing_forecast_low_signal"] = True
    # Merge per-tab partial flags into the top-level result dict
    # (NOT inside observations[]). FE consumers read these flags
    # directly off the persisted narration row.
    result.update(completeness_flags)
    return result


__all__ = ["narrate_analysis"]
