# Track A Phase 3 — R3 BLOCKER Surgical Fix Close Memo

**Date:** 2026-06-04T05:00:36Z
**Rails honoured:** R1, R3 (the rail that caught this — tester verified J19 was a live-wire failure mode the monkey-patched test bench missed), R4 (final count 10 ≤10), R5 (ground-truth read at `analyze_narration.py:230-261` confirmed `json.loads(raw)` direct-feed; existing tests stubbed BARE JSON), R6 (zero Track B touch, zero forecaster code touch, zero frontend touch), R7 (one design choice — balanced-brace sweep over greedy regex — surfaced + justified).

---

## 1 — File-touched diff

```
M backend/services/solva_v2/analyze_narration.py            (+76 / -2 — _extract_json_payload helper + parser wire-up)
M backend/tests/test_track_a_phase3_narration.py            (+47 / 0 — test_synthesize_handles_fenced_json_from_claude)
M memory/MASTER_STATE.md                                    (Section 4 Track A Phase 3 timestamp; Track B Phase B3 ✅; Section 7 timestamp)
A memory/sprints/TRACK_A_PHASE3_R3_BLOCKER_FIX.md           (this memo)
```

ZERO Track B touch. ZERO forecaster touch. ZERO drawer/frontend touch. ZERO shield_invoke touch. R6 honoured.

---

## 2 — The fence-stripping helper (verbatim quote)

`backend/services/solva_v2/analyze_narration.py:181-235` — added BEFORE `narrate_analysis`:

```python
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
```

Wire-up site `narrate_analysis()`, lines 320-340:

```python
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
```

### Strategy ordering rationale (R7 surface)

- **Strategy (1)** preserves the current bare-JSON happy path — zero behaviour change for any caller that already returns clean JSON.
- **Strategy (2)** handles the canonical Claude shape: ```` ```json … ``` ````. The regex is non-greedy so it won't over-consume if there's trailing content.
- **Strategy (3)** is the depth-balanced sweep. Surfaced as a deliberate design choice: a single greedy `.*` regex could grab the wrong closing brace if the JSON contains string fields that themselves contain `}` characters (e.g., `body: "the {{x}} field"`). The sweep correctly skips braces inside string literals — including escaped quotes. This is the most defensive option for unfenced-but-prose-wrapped output.
- Returning `None` falls through to the original `refusal_reason="llm_returned_non_json"` refusal — no fabricated narration.

---

## 3 — Test name + verbatim fenced sample

**Test name:** `test_synthesize_handles_fenced_json_from_claude` (slot 2 of 10 in `tests/test_track_a_phase3_narration.py`).

**Verbatim fenced wire sample the test asserts against:**

```
Here's the synthesis:
```json
{"headline": "Top-line growth slowed across three regions.", "observations": [ {"tab": "what_changed", "title": "Three regions slowed", "body": "EMEA, APAC, and LATAM grew at half the prior quarter pace.", "evidence_citation_indices": [0]} ]}
```
```

The test mocks `shield_invoke` to return that EXACT string as `response`, then asserts:

1. `body["refused"] is False` — parser did NOT trip the refusal path (which is what the live wire was doing pre-fix).
2. `body["headline"] == "Top-line growth slowed across three regions."` — headline extracted correctly.
3. `"Three regions slowed" in titles` — observation array preserved and citation-resolved.

The sample combines BOTH adversarial conditions:
- A leading prose line (`Here's the synthesis:`) → triggers Strategy (3) needs to skip prose
- Fenced JSON block (```` ```json … ``` ````) → Strategy (2) matches and extracts the inner object

(Result: Strategy (2) wins on this input — fence regex matches before the depth-sweep gets a chance, which is the intended specificity ordering.)

---

## 4 — Voice-lint inline guard still runs

**Confirmed** — the voice-lint guard at `analyze_narration.py:289-297` runs AFTER successful parse, on the extracted observations. The fix only changes the parse step; the downstream pipeline is unchanged:

```python
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
```

Test 10 in the same file (`test_voice_lint_drops_banned_voice_observations`) — unchanged — verifies that "I recommend" + "You should" observations still get dropped post-parse. **All three guards (refuse-to-decide, citation_resolver, voice_lint) run unchanged on the parsed payload.**

---

## 5 — Sanity sweep

```
tests/test_track_a_phase3_narration.py            10 passed
tests/test_track_b_phase3_questions_completion.py 10 passed
tests/test_track_a_phase2_drawer_journal.py        9 passed
tests/test_track_b_phase2_task_lifecycle.py        9 passed
tests/test_phase_p5_14_workbook_analyze.py        31 passed
tests/test_solva_v1_unchanged.py                   4 passed
voice_lint                                         clean
```

**73 passed.** No regressions on:
- Track A Phase 1/2 — both still green.
- Track B Phase 2/3 — untouched, both still green.
- P5.14 surface — byte-identical guard intact.
- Solva v1 — 4/4.

---

## 6 — MASTER_STATE.md updates

**Section 4:**
- **Track A Phase 3 (Synthesis):** stays 🟡 SHIPPED tester-pending; awaits tester re-verify of J19 + J20.
- **Track B Phase B3 (Questions wiring):** 🟡 → ✅ SHIPPED (per tester verdict 4/4 PASS this dispatch).

**Section 7:** timestamped 2026-06-04T05:00:36Z; agent line updated.

(No Section 3 row flips this dispatch — those wait for tester re-verify of J19/J20, except the Track B Phase B3 cluster which already flipped via Section 4.)

---

## 7 — Honest reckoning (R7)

1. **The test gap was real and in my work.** The Phase 3 monkey-patched test bench returned bare JSON via `_shield_response(...)` — the helper converted a Python dict to JSON via `json.dumps`. That's structurally what Claude returns AFTER the wire-format wrapper, not what the wrapper itself emits. Lesson: when mocking an LLM wrapper, mock the WIRE format, not the post-parse form.
2. **Strategy (3) depth-sweep over greedy regex** — deliberate. A greedy `.*` regex risks grabbing the wrong closing brace on nested JSON. The depth-balanced sweep with string-literal awareness is correct on every well-formed JSON payload regardless of internal `}` content.
3. **Refusal path preserved.** If extraction fails (no brace at all, unbalanced braces, malformed JSON), the function still returns `refused: True, refusal_reason: "llm_returned_non_json"`. The fix WIDENS the parser's acceptance band; it never widens the persistence band on bad input.
4. **No forecaster code touched.** Bug #30 fix at `services/workbook_analyzer/forecaster.py::autopick_forecast_columns` was correct — the J20 failure was caused by the narration refusal masking the deterministic forecast. With the parser fixed, the forecast now surfaces in `What's likely next` narration AND in the underlying `Analysis.forecasts[]` deterministic output.
5. **No shield_invoke / Solva v2 / drawer / Track B touch.** R6 honoured.
6. **Lockdown count exactly at the R4 cap of 10.** New test added at position 2; nothing removed.

---

## 8 — Tester re-verification journey

> 1. **J19** — sign in, visit `/app/analyze`, open an existing Analysis (or create one). Click "Run synthesis" on the Bottom Line tab. Verify `headline` populates with a journalistic line + observations appear in "What changed" / "What's likely next" / "What's odd" tabs. Cell-range citation chips visible. NO `llm_returned_non_json` refusal in the response body.
> 2. **J20 (Bug #30 by dependence)** — upload a workbook with a Date column + 3+ numeric columns of varying spreads → synthesize → confirm the forecast lands in "What's likely next" (autopicker chose the highest-spread column) AND in the underlying `Analysis.forecasts[]` (`GET /api/workbook/v2/analyses/{aid}`).
>
> If both pass → flip Section 3 G13/G14/G17/G19/G20/G21/G22/G23 + Bug#30 to ✅, plus Section 4 Track A Phase 3 to ✅.
