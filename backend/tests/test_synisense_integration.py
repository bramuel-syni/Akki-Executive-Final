"""Phase 12.1 integration test — end-to-end dryrun.

Feeds a ~2k-char governance-style document through the pipeline and
asserts:
  - All known regex classes detected.
  - Spans non-overlapping and sorted.
  - Replacement tokens unique per distinct match.
  - Contract shape matches spec.
  - `shield_map_id` is None for mode="redact".
"""
import asyncio
import sys

sys.path.insert(0, "/app/backend")

from services.synisense import dryrun, get_perf_snapshot


SAMPLE = """
To: Board of Directors
From: Elena Chowdhury, Chief Executive Officer
Date: 2026-05-02
Subject: Project Falcon — Q2 readout

Directors,

The Q2 numbers are stronger than plan. Top-line revenue closed at £42,500,000
against a target of £40,000,000, driven by the ramp on Operation Magpie and
faster-than-expected conversion in the UK mid-market.

CFO (Richard Brown) flagged a working-capital risk. Our CFO has escalated to
the Audit Committee; Chair Alice Chen has convened an out-of-cycle session on
2026-05-10 at 10:00.

Contact: richard.brown@akki.example and +44 20 7123 4567. Internal portal at
https://board.akki.example/q2-readout routes through 10.0.0.42.

Bank transfer reference: IBAN GB33BUKB20201555555555. Credit card on file for
expenses: 4111 1111 1111 1111.

SSN for compliance verification: 123-45-6789.

Recommendations:
  1. Accelerate working-capital tightening by 30 days.
  2. Fund the additional sales ramp (£5m) from the war chest.
  3. Refresh succession plan for CRO and COO as Project Falcon matures.

— Elena
""".strip()


def _run():
    return asyncio.run(
        dryrun(SAMPLE, context_id="test-ctx", surface="chat", mode="redact")
    )


def test_contract_shape():
    out = _run()
    assert set(out.keys()) >= {"redacted_text", "spans", "stats", "shield_map_id"}
    assert out["shield_map_id"] is None  # redact mode
    for s in out["spans"]:
        assert set(s.keys()) >= {
            "start", "end", "entity_type", "source", "confidence", "replacement"
        }


def test_spans_non_overlapping_sorted():
    out = _run()
    xs = sorted(out["spans"], key=lambda s: s["start"])
    for a, b in zip(xs, xs[1:]):
        assert a["end"] <= b["start"], f"overlap between {a} and {b}"


def test_replacement_tokens_unique_per_match():
    out = _run()
    by_match = {}
    for s in out["spans"]:
        slice_ = SAMPLE[s["start"]:s["end"]]
        k = (s["entity_type"], slice_)
        by_match.setdefault(k, set()).add(s["replacement"])
    # Same (type, text) pair → same replacement token across the doc.
    for k, v in by_match.items():
        assert len(v) == 1, f"multiple tokens assigned to {k}: {v}"


def test_all_high_precision_classes_detected():
    out = _run()
    types = {s["entity_type"] for s in out["spans"]}
    # Regex-provable classes.
    for cls in ("EMAIL_ADDRESS", "PHONE_NUMBER", "IBAN_CODE",
                "CREDIT_CARD", "US_SSN", "IP_ADDRESS", "URL"):
        assert cls in types, f"missing {cls} in {types}"
    # Presidio / custom classes.
    assert "DEAL_CODENAME" in types
    assert "FINANCIAL_FIGURE_LARGE" in types
    assert "EXECUTIVE_TITLE" in types


def test_stats_populated():
    out = _run()
    s = out["stats"]
    assert s["elapsed_ms"] >= 0
    assert s["regex_hits"] > 0
    assert s["presidio_hits"] > 0
    assert "elapsed_breakdown_ms" in s


def test_perf_buffer_populated():
    _run()
    snap = get_perf_snapshot()
    assert snap["count"] > 0



# ---------------------------------------------------------------------------
# Phase 12.3 ITEM A — DEAL_CODENAME wins over PERSON / ORGANIZATION.
#
# Stock spaCy NER (en_core_web_sm) confidently labels "Project Falcon" as
# PERSON when it sits before a real name, and as ORGANIZATION when it
# sits before a corporate-acquisition phrase. The previous Presidio
# PatternRecognizer for DEAL_CODENAME tied or lost on score, leaving the
# histogram label wrong (redaction still happened, just under the wrong
# category). DEAL_CODENAME has now been promoted to the regex pre-pass;
# the pipeline's `_merge_spans()` gives regex precedence over Presidio,
# so any overlapping PERSON / ORGANIZATION span from spaCy is dropped.
# Both tests below assert (a) DEAL_CODENAME is present in the result,
# and (b) it covers the "Project <X>" / "Operation <X>" surface form.
# ---------------------------------------------------------------------------

def _spans_for(text: str):
    return asyncio.run(
        dryrun(text, context_id="test-ctx", surface="chat", mode="redact")
    )["spans"]


def test_deal_codename_wins_over_person():
    text = "Project Falcon briefed by Sarah Chen yesterday."
    spans = _spans_for(text)
    deal_spans = [s for s in spans if s["entity_type"] == "DEAL_CODENAME"]
    assert deal_spans, [
        (s["entity_type"], text[s["start"]:s["end"]]) for s in spans
    ]
    # The DEAL_CODENAME span must cover "Project Falcon" exactly (no over-
    # reach into the trailing real name, no Presidio PERSON span swallowing
    # the codename).
    found = [text[s["start"]:s["end"]] for s in deal_spans]
    assert any(f == "Project Falcon" for f in found), found
    # And the real PERSON ("Sarah Chen") still gets its own non-overlapping
    # span — the codename win must not cost us downstream PII detection.
    person_spans = [s for s in spans if s["entity_type"] == "PERSON"]
    assert person_spans, [
        (s["entity_type"], text[s["start"]:s["end"]]) for s in spans
    ]


def test_deal_codename_wins_over_organization():
    text = "Project Atlas acquisition of TargetCo closed last quarter."
    spans = _spans_for(text)
    deal_spans = [s for s in spans if s["entity_type"] == "DEAL_CODENAME"]
    assert deal_spans, [
        (s["entity_type"], text[s["start"]:s["end"]]) for s in spans
    ]
    found = [text[s["start"]:s["end"]] for s in deal_spans]
    assert any(f == "Project Atlas" for f in found), found
    # Belt-and-braces: there must be NO span whose entity_type is PERSON
    # or ORGANIZATION that overlaps "Project Atlas" — that was the
    # original miscategorisation. We allow ORGANIZATION on "TargetCo".
    p_a_start = text.index("Project Atlas")
    p_a_end = p_a_start + len("Project Atlas")
    for s in spans:
        if s["entity_type"] in {"PERSON", "ORGANIZATION"}:
            assert s["end"] <= p_a_start or s["start"] >= p_a_end, (
                s, text[s["start"]:s["end"]]
            )
