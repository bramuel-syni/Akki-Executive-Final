"""Solva v2 — Frame Audit (Layer 0) engine.

Wave 2.1 (UAT pack 2026-05-10).

What this is
------------
Before the existing surface/depth/synthesis flow runs, the user's framing
is audited for "missing pieces" — the things a defensible synthesis
will need that the framing didn't supply. The audit is deterministic
(no LLM call in the v1) so it's cheap and stable across sessions.

Why deterministic
-----------------
Two reasons:
  1. We don't want to spend an LLM credit on every session start.
  2. The signals we're checking for are surface-level structural
     features (decision criterion, time horizon, named stakeholders,
     evidence tier). Regex / keyword heuristics catch them well
     enough to surface to the user.

What it returns
---------------
A structured `FrameAuditResult` that the FrameAuditScreen renders as
plain language (per spec rule 27 — NOT a table). The user is then
shown 3 CTAs: Proceed, Get more, Pause.

Severity ladder
---------------
  - "none"      — all checks pass; we render a brief "we have what we
                  need on the surface" line and let the user proceed.
  - "advisory"  — 1-2 missing pieces; flow continues but the audit
                  visibly notes what's thin.
  - "critical"  — 3+ missing pieces or a task-specific killer (e.g. a
                  hypothesis with no falsifiable claim). The "Get more"
                  CTA is the recommended path.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

ENGINE_VERSION = "frame_audit@1.0"


@dataclass
class FrameAuditResult:
    severity: str  # "none" | "advisory" | "critical"
    observations: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    missing_pieces: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# -----------------------------------------------------------------------------
# Heuristics — all lowercase regex against the framing text.
# -----------------------------------------------------------------------------
_DECISION_CRITERION_RX = re.compile(
    r"\b(should we|should i|shall we|do we|whether to|decide|deciding|"
    r"between|choose|choice|trade.?off|option a|option b|two paths|"
    r"three paths|alternatives|either|decision\s+impact|hold\s+or\s+\w+|"
    r"roll\s+back\s+or\s+\w+)\b",
    re.IGNORECASE,
)
_TIME_HORIZON_RX = re.compile(
    r"\b(by q[1-4]|next quarter|this quarter|this year|next year|by\s+\w+\s+\d{4}|"
    r"in the next \d+\s*(?:weeks|months|quarters|years)|by end of|deadline|"
    r"\d{4}\b|january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\b",
    re.IGNORECASE,
)
_STAKEHOLDER_ROLES_RX = re.compile(
    r"\b(the board|board of|ceo|cfo|coo|cro|chair|chairperson|chairman|"
    r"chairwoman|founder|investor[s]?|shareholder[s]?|regulator|"
    r"customer[s]?|client[s]?|the team|leadership team|exec(?:utive)?\s+team|"
    r"head of\s+\w+|director\s+of\s+\w+|vp\s+of\s+\w+)\b",
    re.IGNORECASE,
)
_EVIDENCE_HINT_RX = re.compile(
    r"\b(memo|minute[s]?|report|board pack|deck|financial[s]?|p&l|p and l|"
    r"audit|spreadsheet|email[s]?|correspondence|interview[s]?|survey|data)\b",
    re.IGNORECASE,
)
# A "falsifiable" hypothesis statement looks declarative-future or
# conditional, not introspective. The "if X then Y" pattern allows
# multi-word X (the previous \\w+ was too narrow — natural-language
# hypotheses rarely fit "if pricing then churn"; they read as
# "if the March price hike on tier 2 is the cause then ...").
_HYPOTHESIS_FALSIFIABLE_RX = re.compile(
    r"\b(?:will|won't|will not|would|wouldn't|cannot|can't|"
    r"if\s+.{1,80}?\s+then|implies?|leads? to|results? in)\b",
    re.IGNORECASE | re.DOTALL,
)
# Phase B.2 — hypothesis-specific gap heuristics. Both are required by
# the spec's hypothesis framing checklist (PRODUCT_SPEC.md §5.1).
_BASE_RATE_RX = re.compile(
    r"\b(base\s*rate|comparable[s]?|benchmark[s]?|industry|peer[s]?|"
    r"precedent[s]?|historical(?:ly)?|prior\s+experience|past\s+\w+\s+ago|"
    r"prior\s+cycle|last\s+(?:quarter|year|cycle))\b",
    re.IGNORECASE,
)
_LEADING_INDICATOR_RX = re.compile(
    r"\b(leading\s+indicator[s]?|monitor(?:ing)?|early\s+(?:signal|sign|"
    r"warning|indicator)|watch\s+for|track(?:ing)?|signal[s]?|trip\s*wire|"
    r"trigger\s+(?:point|metric)|threshold|kpi[s]?|metric[s]?\s+to\s+watch)\b",
    re.IGNORECASE,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def audit_framing(
    submodule: str,
    framing_text: str,
    *,
    has_attached_docs: bool = False,
    seed_payload: Optional[Dict[str, Any]] = None,
) -> FrameAuditResult:
    """Run the deterministic frame-audit checks.

    Parameters
    ----------
    submodule
        One of the four task ids. Drives the task-specific killer check.
    framing_text
        The user's intent / framing string (already trimmed).
    has_attached_docs
        True iff the user attached a document at session start
        (intake_seed kind=document, or a doc picker selection).
    seed_payload
        The resolved intake_seed dict (or None). When the seed is a
        document or solva_artefact, that itself counts as evidence
        and the "no evidence hinted" check is suppressed.

    Returns
    -------
    A FrameAuditResult. Caller is expected to persist the
    `to_dict()` form on `solva_v2_sessions.frame_audit_summary`
    AND append a row to `reasoning_audit_log` for the audit chain.
    """
    text = (framing_text or "").strip()
    observations: List[str] = []
    recommendations: List[str] = []
    missing: List[str] = []

    seed_provides_evidence = bool(
        seed_payload and seed_payload.get("kind") in {"document", "solva_artefact"}
    )

    # 1. Decision criterion --------------------------------------------------
    if not _DECISION_CRITERION_RX.search(text):
        # `seek_clarity` and `get_perspective` don't strictly need a
        # decision criterion, but the absence is still worth noting.
        if submodule in {"develop_strategy", "simulate_hypothesis"}:
            observations.append(
                "We don't see a clear decision criterion in your framing — "
                "what would tell us one path is right and another isn't."
            )
            recommendations.append(
                "Name the question we're trying to settle, in one sentence."
            )
            missing.append("decision_criterion")
        else:
            # Soft note for the other two; not counted in `missing`.
            observations.append(
                "Your framing is more situational than decisional — that's "
                "fine for this kind of session."
            )

    # 2. Time horizon -------------------------------------------------------
    if not _TIME_HORIZON_RX.search(text):
        observations.append(
            "There's no time horizon stated — by when does this need to land?"
        )
        recommendations.append(
            "Add a single phrase like \"by Q3\" or \"in the next 60 days\" "
            "if it matters."
        )
        missing.append("time_horizon")

    # 3. Stakeholders -------------------------------------------------------
    if not _STAKEHOLDER_ROLES_RX.search(text):
        observations.append(
            "No stakeholders are named — knowing who is in the room "
            "(or who isn't) often changes the synthesis."
        )
        recommendations.append(
            "Name the two or three people whose view will weigh most heavily."
        )
        missing.append("stakeholders")

    # 4. Evidence hinted ---------------------------------------------------
    if not seed_provides_evidence and not has_attached_docs and not _EVIDENCE_HINT_RX.search(text):
        observations.append(
            "Nothing in your framing points to a written source we can ground in."
        )
        recommendations.append(
            "If you have minutes, financials, or a memo that frames this, "
            "attach it before we go further."
        )
        missing.append("evidence_source")

    # 5. Task-specific killer: simulate_hypothesis needs falsifiability
    if submodule == "simulate_hypothesis" and not _HYPOTHESIS_FALSIFIABLE_RX.search(text):
        observations.append(
            "Your hypothesis isn't yet phrased in a way we can stress-test — "
            "we need a claim that could turn out to be wrong."
        )
        recommendations.append(
            "Restate the hypothesis as \"X will happen because Y\" or "
            "\"if X then Y\" so we can examine where it breaks."
        )
        missing.append("falsifiable_hypothesis")

    # 6. Hypothesis-specific: comparable / base rate ------------------------
    # (Phase B.2 — spec calls for a comparable or base rate hint so the
    # model has something to triangulate against.)
    if submodule == "simulate_hypothesis" and not _BASE_RATE_RX.search(text):
        observations.append(
            "There's no comparable or base rate to triangulate against — "
            "we'd otherwise be reasoning from a single data point."
        )
        recommendations.append(
            "Cite a base rate, an industry comparable, or a prior-cycle "
            "precedent we can weigh the hypothesis against."
        )
        missing.append("base_rate_or_comparable")

    # 7. Hypothesis-specific: leading indicator / monitoring signal --------
    if submodule == "simulate_hypothesis" and not _LEADING_INDICATOR_RX.search(text):
        observations.append(
            "No leading indicator named — if the hypothesis is right, "
            "what's the earliest signal we'd see in the data?"
        )
        recommendations.append(
            "Name the metric or signal you'd watch in the next 30–60 days "
            "to confirm or falsify the claim."
        )
        missing.append("leading_indicator")

    # Severity --------------------------------------------------------------
    if not missing:
        severity = "none"
        summary = (
            "Your framing has the pieces we need on the surface. "
            "We can move into the depth round when you're ready."
        )
    elif len(missing) <= 2:
        severity = "advisory"
        summary = (
            "Your framing is workable, but a couple of pieces are thin. "
            "We've noted them above — you can proceed and we'll work "
            "around the gaps, or sharpen them first."
        )
    else:
        severity = "critical"
        summary = (
            "Your framing is missing several structural pieces a defensible "
            "synthesis will need. We can keep going, but we'd rather you "
            "get a few of these on paper first — it'll change what comes out "
            "the other side."
        )

    return FrameAuditResult(
        severity=severity,
        observations=observations,
        recommendations=recommendations,
        missing_pieces=missing,
        summary=summary,
    )


def audit_to_audit_log_row(
    res: FrameAuditResult,
    *,
    framing_text: str,
    submodule: str,
    iso_now: str,
) -> Dict[str, Any]:
    """Build the reasoning_audit_log row for a frame_audit run.

    Preservation rule 3 — every engine call appends a row with engine
    name + version + in/out hashes + shielded flag + latency + tier.
    Frame audit is deterministic and runs on raw framing text (not
    routed through the LLM), so:
      - shielded = False  (no LLM boundary; nothing to shield)
      - latency_ms = 0    (sync function)
      - tier = "deterministic"
    """
    return {
        "engine": "frame_audit",
        "engine_version": ENGINE_VERSION,
        "tier": "deterministic",
        "model": "deterministic",
        "input_sha": _sha256(framing_text),
        "output_sha": _sha256(res.summary + "|" + ",".join(res.missing_pieces)),
        "shielded": False,
        "latency_ms": 0,
        "tier_label": res.severity,
        "submodule": submodule,
        "missing_pieces": list(res.missing_pieces),
        "ts": iso_now,
    }
