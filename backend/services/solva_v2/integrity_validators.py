"""Solva v2 — Integrity validators.

Slice 1 of the v2 build, pillar of the integrity boundary. These
validators run AFTER an artefact payload is constructed but BEFORE
it serializes to the renderer. If any validator fails, the payload
is rejected; the failure carries a structured message that the
engine layer (Slice 1b's `payload_builder.py`) uses for prompt-revision
retry (max 1 retry per Trust pillar 3).

Four validators (numbered 1-4 matching Slice 1 spec §4):

  1. citation_lint              — every numerical claim cites a source
  2. confidence_calibration_audit — confidence ≥ 70 names ≥2 triangulating
                                    sources
  3. refuse_to_decide_enforcement — recommendations avoid imperative
                                    phrasing; conditional + observational OK
  4. methodological_honesty_present — all 4 sub-sections populated

The validators are PURE — input is the (already-constructed)
`ArtefactPayload` plus a snapshot of the session's audit log. Output
is `ValidationResult` carrying pass/fail + structured offender list
+ revision_hint string (for retry prompt).

NEVER swallow a failure silently — callers must check `.ok` before
serializing the payload to the renderer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from .artefact_schema import ArtefactPayload


# ─────────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────────


@dataclass
class ValidatorOffender:
    """One specific violation surfaced by a validator."""
    validator: str
    severity: str  # "block" | "warn"
    location: str  # human-readable JSONPath-ish location ("scenarios[1].confidence_pct")
    message: str
    revision_hint: str  # prompt-revision-friendly remediation suggestion


@dataclass
class ValidationResult:
    ok: bool
    offenders: List[ValidatorOffender] = field(default_factory=list)

    @property
    def blocking(self) -> List[ValidatorOffender]:
        return [o for o in self.offenders if o.severity == "block"]

    def revision_hint_bundle(self) -> str:
        """Compose all revision hints into a single prompt-friendly
        block the engine retry can prepend to its next attempt."""
        lines = ["The previous draft was rejected by integrity validators:"]
        for o in self.blocking:
            lines.append(f"  • [{o.validator}] {o.location}: {o.message}")
            lines.append(f"      → {o.revision_hint}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────


# Capture standalone numerical claims — "27%", "3.5x", "12 of 30",
# "$1.2M" — when they appear in a substantive sentence. Skip purely
# structural numbers (slide indices, list numbering).
#
# Note: no trailing `\b` because the unit suffix (`%`, `x`, `×`) is
# already a non-word character; appending `\b` would require a word
# boundary AFTER the non-word char, which fails on text like "27%."
# or "27% in" (non-word → non-word transition).
_NUMERIC_CLAIM_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:%|x|×|k|m|bn|million|billion|months?|years?|weeks?|days?|hours?|customers?|users?|orgs?)",
    re.IGNORECASE,
)

# Imperative phrasings — the model must NEVER tell the user what to do.
# Conditional + observational framings are explicitly OK.
_IMPERATIVE_PATTERNS = (
    r"\byou\s+(?:must|should|need to|have to|ought to)\b",
    r"\b(?:retain|fire|hire|kill|launch|raise|sell|exit|pivot|liquidate|acquire|merge|terminate)\b",
    r"\bdo\s+not\s+\w+",
    r"\bmust\s+(?:not\s+)?\w+",
    r"\bshould\s+(?:not\s+)?\w+",
)

# Allowlisted conditional + observational openers — sentences starting
# with these are presumed safe even if they contain a trigger word.
_CONDITIONAL_OPENERS = (
    "if ", "should ", "when ", "given that ", "given ", "where ",
    "the evidence supports ", "the evidence indicates ", "this picture supports ",
    "consider ", "one option ", "one path ", "investigate ",
)


def _audit_log_ids(session: Dict[str, Any]) -> Set[str]:
    """Build the set of source ids the audit log can resolve to.

    Includes: every audit-log entry's id, every user turn id, every
    attached document id, every comparable id, every solve_clusters
    id."""
    ids: Set[str] = set()
    for entry in (session.get("reasoning_audit_log") or []):
        if isinstance(entry, dict) and entry.get("id"):
            ids.add(str(entry["id"]))
    for t in (session.get("user_turns") or []):
        if isinstance(t, dict) and t.get("id"):
            ids.add(str(t["id"]))
    for d in (session.get("attached_docs") or []):
        if isinstance(d, dict) and d.get("id"):
            ids.add(str(d["id"]))
    for c in (session.get("comparables") or []):
        if isinstance(c, dict) and c.get("id"):
            ids.add(str(c["id"]))
    return ids


def _sentences(text: str) -> List[str]:
    """Naive sentence splitter — sufficient for imperative scanning."""
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


# ─────────────────────────────────────────────────────────────────
# Validator 1 — citation_lint
# ─────────────────────────────────────────────────────────────────


def citation_lint(payload: ArtefactPayload, session: Dict[str, Any]) -> List[ValidatorOffender]:
    """Every numerical claim in the rendered payload MUST cite at least
    one source that resolves to an audit-log id.

    Scope:
      • headline.key_findings[].paragraph_text
      • tensions[].implication + tensions[].prevailing_framing
      • scenarios[].description + scenarios[].label
      • sensitivity_inputs[].impact_explanation + cluster_weight_shift_mechanic
      • pathway[].detail_paragraph
    """
    offenders: List[ValidatorOffender] = []
    log_ids = _audit_log_ids(session)

    def _check(prefix: str, text: str, citations: List[Any]) -> None:
        matches = _NUMERIC_CLAIM_RE.findall(text or "")
        if not matches:
            return
        cited_ids = {getattr(c, "source_input_id", None) for c in (citations or [])}
        cited_ids.discard(None)
        if not cited_ids:
            offenders.append(ValidatorOffender(
                validator="citation_lint",
                severity="block",
                location=prefix,
                message=f"Contains numerical claim(s) {matches!r} but no source citations",
                revision_hint=(
                    f"Add a `source_citations` entry at {prefix} that resolves to an "
                    f"audit_log id from the session. Every number must be traceable."
                ),
            ))
            return
        unresolved = [cid for cid in cited_ids if cid not in log_ids]
        if unresolved:
            offenders.append(ValidatorOffender(
                validator="citation_lint",
                severity="block",
                location=prefix,
                message=f"Citations reference unknown source ids: {unresolved}",
                revision_hint=(
                    f"At {prefix}, every `source_input_id` must match an entry in "
                    f"the session's audit_log / user_turns / attached_docs / comparables. "
                    f"Unknown ids: {unresolved}"
                ),
            ))

    for i, kf in enumerate(payload.headline.key_findings):
        _check(f"headline.key_findings[{i}]", kf.paragraph_text, kf.source_citations)

    for i, t in enumerate(payload.tensions):
        _check(f"tensions[{i}].prevailing_framing", t.prevailing_framing, [])
        _check(f"tensions[{i}].implication", t.implication, [])

    for i, s in enumerate(payload.scenarios):
        _check(f"scenarios[{i}].description", s.description, s.supporting_evidence)

    for i, si in enumerate(payload.sensitivity_inputs):
        _check(f"sensitivity_inputs[{i}].impact_explanation",
               si.impact_explanation, si.source_citations)
        _check(f"sensitivity_inputs[{i}].cluster_weight_shift_mechanic",
               si.cluster_weight_shift_mechanic, si.source_citations)

    for i, p in enumerate(payload.pathway):
        _check(f"pathway[{i}].detail_paragraph", p.detail_paragraph, p.source_citations)
        _check(f"pathway[{i}].action_heading", p.action_heading, p.source_citations)

    return offenders


# ─────────────────────────────────────────────────────────────────
# Validator 2 — confidence_calibration_audit
# ─────────────────────────────────────────────────────────────────


def confidence_calibration_audit(payload: ArtefactPayload, session: Dict[str, Any]) -> List[ValidatorOffender]:
    """Any scenario where `confidence_pct >= 70` must name at least 2
    INDEPENDENT triangulating evidence sources in
    `confidence_calibration_reasoning` AND in `supporting_evidence[]`.

    Independence is approximated by counting distinct `source_kind`
    values OR distinct `source_layer` values across `supporting_evidence`.
    A scenario citing 2 user_turn entries from the same layer is NOT
    independent triangulation.
    """
    offenders: List[ValidatorOffender] = []
    for i, s in enumerate(payload.scenarios):
        if s.confidence_pct < 70:
            continue
        if len(s.supporting_evidence) < 2:
            offenders.append(ValidatorOffender(
                validator="confidence_calibration_audit",
                severity="block",
                location=f"scenarios[{i}]",
                message=(
                    f"confidence_pct={s.confidence_pct} (≥70) but only "
                    f"{len(s.supporting_evidence)} supporting_evidence entry(ies)."
                ),
                revision_hint=(
                    f"Drop confidence_pct to <70 OR add a 2nd independent "
                    f"supporting_evidence entry (different source_kind or source_layer) "
                    f"at scenarios[{i}]."
                ),
            ))
            continue
        distinct_kinds = {e.source_kind for e in s.supporting_evidence}
        distinct_layers = {e.source_layer for e in s.supporting_evidence if e.source_layer}
        independent_signals = max(len(distinct_kinds), len(distinct_layers))
        if independent_signals < 2:
            offenders.append(ValidatorOffender(
                validator="confidence_calibration_audit",
                severity="block",
                location=f"scenarios[{i}]",
                message=(
                    f"confidence_pct={s.confidence_pct} (≥70) but supporting_evidence "
                    f"sources are not independent (all share kind/layer)."
                ),
                revision_hint=(
                    f"At scenarios[{i}], add a supporting_evidence entry from a "
                    f"different source_kind (e.g. corpus + comparable, or user_turn + "
                    f"attached_doc) so the confidence is triangulated, not echoed."
                ),
            ))
        # Calibration reasoning must mention triangulation explicitly.
        if not s.confidence_calibration_reasoning or len(s.confidence_calibration_reasoning) < 40:
            offenders.append(ValidatorOffender(
                validator="confidence_calibration_audit",
                severity="block",
                location=f"scenarios[{i}].confidence_calibration_reasoning",
                message="High-confidence claim lacks substantive calibration reasoning",
                revision_hint=(
                    f"Write a 1-2 sentence calibration explanation at scenarios[{i}] "
                    f"naming the ≥2 triangulating sources by name. E.g. "
                    f"'Confidence high because corpus item X and comparable Y both "
                    f"surface the same signal.'"
                ),
            ))
    return offenders


# ─────────────────────────────────────────────────────────────────
# Validator 3 — refuse_to_decide_enforcement
# ─────────────────────────────────────────────────────────────────


def refuse_to_decide_enforcement(payload: ArtefactPayload, session: Dict[str, Any]) -> List[ValidatorOffender]:
    """Scan pathway[] action_heading + detail_paragraph for imperative
    phrasings. Conditional + observational openers are allowlisted.

    Trust pillar 3 — Solva NEVER tells the user what to do.
    """
    offenders: List[ValidatorOffender] = []

    def _scan_text(prefix: str, text: str) -> None:
        for sentence in _sentences(text):
            normalised = sentence.lower().strip()
            # Conditional opener? Allow.
            if any(normalised.startswith(opener) for opener in _CONDITIONAL_OPENERS):
                continue
            for pat in _IMPERATIVE_PATTERNS:
                m = re.search(pat, normalised)
                if m:
                    offenders.append(ValidatorOffender(
                        validator="refuse_to_decide_enforcement",
                        severity="block",
                        location=prefix,
                        message=(
                            f"Imperative phrasing detected: {m.group(0)!r} in sentence "
                            f"{sentence!r}"
                        ),
                        revision_hint=(
                            f"Rewrite at {prefix} as a conditional or observational "
                            f"statement. Use 'If <data outcome> → then <strategic "
                            f"conclusion>' or 'The evidence supports investigating X' "
                            f"instead of imperative phrasing. Solva does not make "
                            f"decisions for the user."
                        ),
                    ))
                    break

    for i, p in enumerate(payload.pathway):
        _scan_text(f"pathway[{i}].action_heading", p.action_heading)
        _scan_text(f"pathway[{i}].detail_paragraph", p.detail_paragraph)
    for i, kf in enumerate(payload.headline.key_findings):
        _scan_text(f"headline.key_findings[{i}].paragraph_text", kf.paragraph_text)
    for i, t in enumerate(payload.tensions):
        _scan_text(f"tensions[{i}].implication", t.implication)

    return offenders


# ─────────────────────────────────────────────────────────────────
# Validator 4 — methodological_honesty_present
# ─────────────────────────────────────────────────────────────────


def methodological_honesty_present(payload: ArtefactPayload, session: Dict[str, Any]) -> List[ValidatorOffender]:
    """The artefact cannot serialize without all 4 methodological
    honesty sub-sections populated AND substantive (≥1 sentence each).

    Pydantic already enforces `min_length=1`; this validator additionally
    checks that each section is ≥40 chars (the minimum we consider a
    substantive disclaimer)."""
    offenders: List[ValidatorOffender] = []
    mh = payload.methodological_honesty
    sections = {
        "what_report_is": mh.what_report_is,
        "what_report_is_not": mh.what_report_is_not,
        "provisional_nature_paragraph": mh.provisional_nature_paragraph,
        "not_sole_basis_paragraph": mh.not_sole_basis_paragraph,
    }
    for name, text in sections.items():
        if len(text or "") < 40:
            offenders.append(ValidatorOffender(
                validator="methodological_honesty_present",
                severity="block",
                location=f"methodological_honesty.{name}",
                message=f"Sub-section {name!r} is missing or too short ({len(text or '')} chars; need ≥40).",
                revision_hint=(
                    f"Write a substantive 1-2 sentence {name} disclaimer. Mirror the "
                    f"reference template — name what the report IS / IS NOT / what's "
                    f"provisional / why this is not a sole basis for a decision."
                ),
            ))
    if not (0 <= mh.input_confidence_pct <= 100):
        offenders.append(ValidatorOffender(
            validator="methodological_honesty_present",
            severity="block",
            location="methodological_honesty.input_confidence_pct",
            message=f"input_confidence_pct={mh.input_confidence_pct} out of [0,100]",
            revision_hint="Set input_confidence_pct to a value in [0,100].",
        ))
    return offenders


# ─────────────────────────────────────────────────────────────────
# Validators 5-7 — Slice 4 (2026-05-29) Bias Inventory contract
# ─────────────────────────────────────────────────────────────────


# Allowlist of observational openers for `evidence_grounded_reasoning`
# and `suggested_mitigation`. Phrases starting with these (or their
# inflections) are accepted; anything else falls through to the
# imperative scan.
_BIAS_OBSERVATIONAL_OPENERS = (
    "the framing", "the user", "the intake", "the response",
    "the responses", "the evidence", "evidence in", "evidence from",
    "the audit log", "the diagnosis", "this read",
    "indicates", "suggests", "implies", "points to",
    "shows", "surfaces", "reveals", "reflects", "carries",
    "seeking", "testing", "consulting", "inviting", "asking",
    "soliciting", "inviting input", "examining", "checking",
    "validating", "running",
    # Slice 5 — adversarial-counter / pre-mortem observational openers
    "the strongest case", "the case against", "the counter",
    "the steel-man", "the steelman",
    "branch logic", "the branch", "the if-clause", "the conditional",
    "the pathway", "the recommended", "the recommendation",
    "the leading", "the second", "the alternative",
    "thin-evidence", "thin evidence",
    # Slice 6 — cost-asymmetry observational openers
    "this pathway", "this scenario", "this conclusion", "this read",
    "the upside", "the downside", "the cost", "the asymmetry",
    "the operating", "the founder", "the diagnostic",
    "if correct", "if wrong", "if right", "if it's wrong",
    "if this pathway", "if this scenario", "if this conclusion",
    "delivered", "incurred", "absorbed", "reabsorbed",
    "if ", "when ",  # conditionals
)


def bias_inventory_present(payload: ArtefactPayload, session: Dict[str, Any]) -> List[ValidatorOffender]:
    """The Bias Inventory slide is Trust pillar 2 — required on EVERY
    artefact. Even on thin-evidence sessions, the engine must surface
    at least 1 bias entry (with likelihood="low" if appropriate). An
    empty `biases` list is a real bug, not an observational outcome.
    """
    offenders: List[ValidatorOffender] = []
    bi = payload.bias_inventory
    if bi is None:
        offenders.append(ValidatorOffender(
            validator="bias_inventory_present",
            severity="block",
            location="bias_inventory",
            message="Bias inventory slide missing entirely.",
            revision_hint=(
                "Emit a `bias_inventory` section with at least 1 bias "
                "entry. On thin-evidence sessions, surface the most "
                "plausible candidate bias with likelihood='low' rather "
                "than omitting the slide."
            ),
        ))
        return offenders
    if not bi.biases:
        offenders.append(ValidatorOffender(
            validator="bias_inventory_present",
            severity="block",
            location="bias_inventory.biases",
            message="Bias inventory has zero entries.",
            revision_hint=(
                "Add at least 1 BiasItem. On thin-evidence sessions, "
                "surface the most plausible candidate with "
                "likelihood='low'. Trust pillar 2 — Solva ALWAYS names "
                "the biases that may be operating; absence is itself "
                "an integrity failure."
            ),
        ))
    return offenders


def bias_inventory_citation_lint(payload: ArtefactPayload, session: Dict[str, Any]) -> List[ValidatorOffender]:
    """Every bias must cite ≥1 source_input_id resolving to a real
    audit-log entry OR user turn in this session."""
    offenders: List[ValidatorOffender] = []
    bi = payload.bias_inventory
    if bi is None:
        return offenders  # bias_inventory_present catches the absence

    # Build the set of resolvable ids from the session.
    audit_ids: Set[str] = set()
    for a in session.get("reasoning_audit_log") or []:
        if isinstance(a, dict) and a.get("id"):
            audit_ids.add(str(a["id"]))
    for t in session.get("user_turns") or []:
        if isinstance(t, dict) and t.get("id"):
            audit_ids.add(str(t["id"]))

    # Also accept layer tags like "L0" / "L1" / "L2" / "L3" / "L4" + the
    # canonical name forms ("frame_audit", "surface", "depth",
    # "synthesis", "reflection") + legacy audit-log tags. These are
    # coarse-grained references — useful when an engine wants to cite
    # "the Layer 3 synthesis output" rather than a specific entry id.
    coarse_ok = {
        "L0", "L1", "L2", "L3", "L4",
        "frame_audit", "surface", "depth", "synthesis", "reflection",
        "framing", "grounding", "hypothesis",  # legacy
    }

    for i, item in enumerate(bi.biases):
        unresolved = [
            sid for sid in (item.source_input_ids or [])
            if sid not in audit_ids and sid not in coarse_ok
        ]
        if unresolved:
            offenders.append(ValidatorOffender(
                validator="bias_inventory_citation_lint",
                severity="block",
                location=f"bias_inventory.biases[{i}].source_input_ids",
                message=(
                    f"Bias {item.bias_name!r} cites unresolved source ids: "
                    f"{unresolved}. Each id must resolve to an audit-log "
                    f"entry, a user turn, OR a coarse layer tag "
                    f"(L0..L4 / frame_audit / surface / depth / synthesis / reflection)."
                ),
                revision_hint=(
                    f"Replace the unresolved ids in "
                    f"bias_inventory.biases[{i}].source_input_ids with "
                    f"real audit-log entry ids or coarse layer tags. "
                    f"Available audit-log ids: "
                    f"{sorted(audit_ids)[:8]}{'...' if len(audit_ids) > 8 else ''}."
                ),
            ))
    return offenders


def bias_evidence_observational(payload: ArtefactPayload, session: Dict[str, Any]) -> List[ValidatorOffender]:
    """`evidence_grounded_reasoning` and `suggested_mitigation` must be
    observational, not imperative. Reuses the refuse_to_decide
    enforcement allowlist patterns."""
    offenders: List[ValidatorOffender] = []
    bi = payload.bias_inventory
    if bi is None:
        return offenders

    for i, item in enumerate(bi.biases):
        # evidence_grounded_reasoning — scan for imperative patterns.
        for sentence in _sentences(item.evidence_grounded_reasoning):
            normalised = sentence.lower().strip()
            if any(normalised.startswith(opener) for opener in _BIAS_OBSERVATIONAL_OPENERS):
                continue
            if any(normalised.startswith(opener) for opener in _CONDITIONAL_OPENERS):
                continue
            for pat in _IMPERATIVE_PATTERNS:
                m = re.search(pat, normalised)
                if m:
                    offenders.append(ValidatorOffender(
                        validator="bias_evidence_observational",
                        severity="block",
                        location=f"bias_inventory.biases[{i}].evidence_grounded_reasoning",
                        message=(
                            f"Imperative phrasing detected: {m.group(0)!r} in "
                            f"sentence {sentence!r}."
                        ),
                        revision_hint=(
                            "Rewrite as observational. Open with a verb like "
                            "'indicates', 'suggests', 'reveals', 'the framing "
                            "presents'. Solva NAMES the bias and grounds it in "
                            "evidence; it does NOT instruct the founder how to "
                            "correct for it."
                        ),
                    ))
                    break

        # suggested_mitigation — if present, must start with an
        # observational opener AND must not contain imperative phrasing.
        if item.suggested_mitigation:
            normalised = item.suggested_mitigation.lower().strip()
            if not any(normalised.startswith(opener) for opener in _BIAS_OBSERVATIONAL_OPENERS):
                # Check the leading word.
                offenders.append(ValidatorOffender(
                    validator="bias_evidence_observational",
                    severity="block",
                    location=f"bias_inventory.biases[{i}].suggested_mitigation",
                    message=(
                        f"suggested_mitigation must begin with an observational "
                        f"opener (Seeking / Testing / Consulting / Asking / "
                        f"Inviting / Examining). Got: {item.suggested_mitigation[:80]!r}"
                    ),
                    revision_hint=(
                        "Rewrite the mitigation as an observational suggestion. "
                        "E.g. 'Seeking evidence that would falsify the current "
                        "framing would test this assumption' — NEVER 'You should "
                        "seek evidence...'."
                    ),
                ))
                continue
            for pat in _IMPERATIVE_PATTERNS:
                m = re.search(pat, normalised)
                if m:
                    offenders.append(ValidatorOffender(
                        validator="bias_evidence_observational",
                        severity="block",
                        location=f"bias_inventory.biases[{i}].suggested_mitigation",
                        message=(
                            f"Imperative phrasing detected: {m.group(0)!r}."
                        ),
                        revision_hint=(
                            "Replace the imperative with an observational form."
                        ),
                    ))
                    break

    return offenders


# ─────────────────────────────────────────────────────────────────
# Validators 8-9 — Slice 5 (2026-05-29) Adversarial debate + Pre-mortem
# ─────────────────────────────────────────────────────────────────


# Coarse layer tags accepted as source ids by the bias / adversarial /
# pre-mortem citation validators. Mirrored from
# `bias_inventory_citation_lint` so all three Trust pillar validators
# share the same resolution surface.
_COARSE_LAYER_TAGS = {
    "L0", "L1", "L2", "L3", "L4",
    "frame_audit", "surface", "depth", "synthesis", "reflection",
    "framing", "grounding", "hypothesis",  # legacy
}


# Observational openers for `counter_action` (parallel to bias-mitigation
# openers). `Investigating`, `Monitoring`, `Strengthening`, `Pre-
# committing`, `Surfacing` etc. NEVER imperative.
_PRE_MORTEM_COUNTER_OPENERS = (
    "investigating", "investigate ",
    "monitoring", "monitor ",
    "strengthening", "strengthen ",
    "pre-committing", "pre-commit ", "precommitting", "precommit ",
    "surfacing", "surface ",
    "running", "run ",
    "consulting", "consult ",
    "tracking", "track ",
    "checking", "check ",
    "validating", "validate ",
    "soliciting", "solicit ",
    "if ", "when ",  # conditionals
    "the evidence supports ", "the evidence indicates ",
    "this risk shifts ", "this risk reduces ",
)


def _resolve_session_ids(session: Dict[str, Any]) -> Set[str]:
    """Build the set of resolvable source ids from the session
    (audit-log + user_turns). Re-used by the Slice 5 validators."""
    ids: Set[str] = set()
    for a in session.get("reasoning_audit_log") or []:
        if isinstance(a, dict) and a.get("id"):
            ids.add(str(a["id"]))
    for t in session.get("user_turns") or []:
        if isinstance(t, dict) and t.get("id"):
            ids.add(str(t["id"]))
    return ids


def _scan_imperative(text: str, location: str, validator_name: str) -> List[ValidatorOffender]:
    """Scan a text body for imperative phrasings, allowing conditional
    + observational openers. Returns a list of offenders."""
    offenders: List[ValidatorOffender] = []
    for sentence in _sentences(text):
        normalised = sentence.lower().strip()
        if any(normalised.startswith(opener) for opener in _CONDITIONAL_OPENERS):
            continue
        if any(normalised.startswith(opener) for opener in _BIAS_OBSERVATIONAL_OPENERS):
            continue
        for pat in _IMPERATIVE_PATTERNS:
            m = re.search(pat, normalised)
            if m:
                offenders.append(ValidatorOffender(
                    validator=validator_name,
                    severity="block",
                    location=location,
                    message=(
                        f"Imperative phrasing detected: {m.group(0)!r} in "
                        f"sentence {sentence!r}."
                    ),
                    revision_hint=(
                        "Rewrite as observational. Solva NAMES the failure "
                        "mode / counter-case and grounds it in evidence; it "
                        "does NOT instruct the founder how to act."
                    ),
                ))
                break
    return offenders


def adversarial_counter_evidence_grounded(
    payload: ArtefactPayload, session: Dict[str, Any],
) -> List[ValidatorOffender]:
    """Slice 5 contract — every adversarial_counter must:
      • cite ≥2 source_input_ids resolving to real audit-log ids,
        user turn ids, or coarse layer tags. (Schema enforces ≥2
        entries; this validator additionally enforces resolvability
        AND triangulation — at least 2 must resolve.)
      • use observational phrasing in steel_man_position +
        why_it_matters (no imperatives).
    """
    offenders: List[ValidatorOffender] = []
    audit_ids = _resolve_session_ids(session)

    def _check(prefix: str, counter):  # AdversarialCounterCase | None
        if counter is None:
            return
        unresolved = [
            sid for sid in (counter.source_input_ids or [])
            if sid not in audit_ids and sid not in _COARSE_LAYER_TAGS
        ]
        resolved = [s for s in counter.source_input_ids if s not in unresolved]
        if len(resolved) < 2:
            offenders.append(ValidatorOffender(
                validator="adversarial_counter_evidence_grounded",
                severity="block",
                location=f"{prefix}.adversarial_counter.source_input_ids",
                message=(
                    f"Adversarial counter cites only {len(resolved)} resolved source"
                    f"{'s' if len(resolved) != 1 else ''} (need ≥2 for triangulation). "
                    f"Unresolved: {unresolved}."
                ),
                revision_hint=(
                    "Add ≥2 audit-log ids or coarse layer tags so the "
                    "counter is genuinely triangulated, not a vague "
                    "devil's advocate."
                ),
            ))
        offenders.extend(_scan_imperative(
            counter.steel_man_position,
            f"{prefix}.adversarial_counter.steel_man_position",
            "adversarial_counter_evidence_grounded",
        ))
        offenders.extend(_scan_imperative(
            counter.why_it_matters,
            f"{prefix}.adversarial_counter.why_it_matters",
            "adversarial_counter_evidence_grounded",
        ))

    for i, p in enumerate(payload.pathway):
        _check(f"pathway[{i}]", p.adversarial_counter)
    for i, b in enumerate(payload.decision_logic):
        _check(f"decision_logic[{i}]", b.adversarial_counter)
    return offenders


def pre_mortem_present(payload: ArtefactPayload, session: Dict[str, Any]) -> List[ValidatorOffender]:
    """Slice 5 — Trust pillar 4. Pre-mortem slide must be present
    with ≥1 failure mode. An empty failure_modes list is a real
    bug, not an observational outcome."""
    offenders: List[ValidatorOffender] = []
    pm = payload.pre_mortem
    if pm is None:
        offenders.append(ValidatorOffender(
            validator="pre_mortem_present",
            severity="block",
            location="pre_mortem",
            message="Pre-mortem slide missing entirely.",
            revision_hint=(
                "Emit a `pre_mortem` section with at least 1 failure mode. "
                "Trust pillar 4 — Solva ALWAYS imagines how the pathway "
                "could fail."
            ),
        ))
        return offenders
    if not pm.failure_modes:
        offenders.append(ValidatorOffender(
            validator="pre_mortem_present",
            severity="block",
            location="pre_mortem.failure_modes",
            message="Pre-mortem has zero failure modes.",
            revision_hint=(
                "Add at least 1 PreMortemFailureMode. On thin-evidence "
                "sessions, surface the most plausible candidate failure mode."
            ),
        ))
    return offenders


def pre_mortem_failure_evidence_grounded(
    payload: ArtefactPayload, session: Dict[str, Any],
) -> List[ValidatorOffender]:
    """Slice 5 contract — every failure_mode must:
      • cite ≥1 source_input_id resolving to audit-log / user turn /
        coarse layer tag.
      • use observational phrasing in failure_narrative + counter_action.
      • If counter_action is present, must start with one of the
        observational openers (Investigating / Monitoring / etc.)."""
    offenders: List[ValidatorOffender] = []
    pm = payload.pre_mortem
    if pm is None:
        return offenders
    audit_ids = _resolve_session_ids(session)

    for i, fm in enumerate(pm.failure_modes):
        unresolved = [
            sid for sid in (fm.source_input_ids or [])
            if sid not in audit_ids and sid not in _COARSE_LAYER_TAGS
        ]
        if unresolved:
            offenders.append(ValidatorOffender(
                validator="pre_mortem_failure_evidence_grounded",
                severity="block",
                location=f"pre_mortem.failure_modes[{i}].source_input_ids",
                message=(
                    f"Failure mode {fm.failure_kind!r} cites unresolved source "
                    f"ids: {unresolved}. Each id must resolve to an audit-log "
                    f"entry, a user turn, OR a coarse layer tag."
                ),
                revision_hint=(
                    "Replace the unresolved ids with real audit-log entry "
                    "ids or coarse layer tags (L0..L4)."
                ),
            ))
        offenders.extend(_scan_imperative(
            fm.failure_narrative,
            f"pre_mortem.failure_modes[{i}].failure_narrative",
            "pre_mortem_failure_evidence_grounded",
        ))
        if fm.counter_action:
            normalised = fm.counter_action.lower().strip()
            if not any(
                normalised.startswith(opener) for opener in _PRE_MORTEM_COUNTER_OPENERS
            ):
                offenders.append(ValidatorOffender(
                    validator="pre_mortem_failure_evidence_grounded",
                    severity="block",
                    location=f"pre_mortem.failure_modes[{i}].counter_action",
                    message=(
                        f"counter_action must begin with an observational "
                        f"opener (Investigating / Monitoring / Strengthening / "
                        f"Pre-committing / Surfacing). Got: "
                        f"{fm.counter_action[:80]!r}"
                    ),
                    revision_hint=(
                        "Rewrite as observational. E.g. 'Investigating the "
                        "leading indicator earlier would shift this risk' — "
                        "NEVER 'You should investigate...'."
                    ),
                ))
                continue
            offenders.extend(_scan_imperative(
                fm.counter_action,
                f"pre_mortem.failure_modes[{i}].counter_action",
                "pre_mortem_failure_evidence_grounded",
            ))
    return offenders


# ─────────────────────────────────────────────────────────────────
# Validators 11-12 — Slice 6 (2026-05-29) Cost asymmetry
# ─────────────────────────────────────────────────────────────────


def cost_asymmetry_present(
    payload: ArtefactPayload, session: Dict[str, Any],
) -> List[ValidatorOffender]:
    """Slice 6 — Trust pillar 5 (cost asymmetry). The cost asymmetry
    slide is REQUIRED on every artefact and MUST contain ≥2
    scenarios (you cannot have an "asymmetry" with one option).
    The schema's `min_length=2` enforces this at the model level;
    this validator surfaces a friendlier blocking message when the
    upstream engine emits a degenerate payload."""
    offenders: List[ValidatorOffender] = []
    ca = payload.cost_asymmetry
    if ca is None:
        offenders.append(ValidatorOffender(
            validator="cost_asymmetry_present",
            severity="block",
            location="cost_asymmetry",
            message="Cost asymmetry slide missing entirely.",
            revision_hint=(
                "Emit a `cost_asymmetry` section with at least 2 scenarios. "
                "Pillar 5 — Solva ALWAYS surfaces the asymmetry between "
                "'if right' and 'if wrong' on the leading pathways."
            ),
        ))
        return offenders
    if len(ca.scenarios) < 2:
        offenders.append(ValidatorOffender(
            validator="cost_asymmetry_present",
            severity="block",
            location="cost_asymmetry.scenarios",
            message=(
                f"Cost asymmetry has only {len(ca.scenarios)} scenario(s) — "
                f"need ≥2 for a meaningful asymmetry comparison."
            ),
            revision_hint=(
                "Add at least one more scenario so the founder can compare "
                "downside-cost reads side by side."
            ),
        ))
    return offenders


def cost_asymmetry_evidence_grounded(
    payload: ArtefactPayload, session: Dict[str, Any],
) -> List[ValidatorOffender]:
    """Slice 6 contract — every cost asymmetry scenario must:
      • cite ≥1 source_input_id resolving to audit-log / user turn /
        coarse layer tag.
      • use observational phrasing in if_correct_outcome +
        if_wrong_cost (no imperatives)."""
    offenders: List[ValidatorOffender] = []
    ca = payload.cost_asymmetry
    if ca is None:
        return offenders
    audit_ids = _resolve_session_ids(session)

    for i, sc in enumerate(ca.scenarios):
        unresolved = [
            sid for sid in (sc.source_input_ids or [])
            if sid not in audit_ids and sid not in _COARSE_LAYER_TAGS
        ]
        if unresolved:
            offenders.append(ValidatorOffender(
                validator="cost_asymmetry_evidence_grounded",
                severity="block",
                location=f"cost_asymmetry.scenarios[{i}].source_input_ids",
                message=(
                    f"Scenario {sc.pathway_label!r} cites unresolved source "
                    f"ids: {unresolved}. Each id must resolve to an audit-log "
                    f"entry, a user turn, OR a coarse layer tag."
                ),
                revision_hint=(
                    "Replace the unresolved ids with real audit-log entry "
                    "ids or coarse layer tags (L0..L4)."
                ),
            ))
        offenders.extend(_scan_imperative(
            sc.if_correct_outcome,
            f"cost_asymmetry.scenarios[{i}].if_correct_outcome",
            "cost_asymmetry_evidence_grounded",
        ))
        offenders.extend(_scan_imperative(
            sc.if_wrong_cost,
            f"cost_asymmetry.scenarios[{i}].if_wrong_cost",
            "cost_asymmetry_evidence_grounded",
        ))
    return offenders


# ─────────────────────────────────────────────────────────────────
# Composite runner
# ─────────────────────────────────────────────────────────────────


_ALL_VALIDATORS = (
    citation_lint,
    confidence_calibration_audit,
    refuse_to_decide_enforcement,
    methodological_honesty_present,
    bias_inventory_present,
    bias_inventory_citation_lint,
    bias_evidence_observational,
    adversarial_counter_evidence_grounded,
    pre_mortem_present,
    pre_mortem_failure_evidence_grounded,
    cost_asymmetry_present,
    cost_asymmetry_evidence_grounded,
)


def validate_artefact(payload: ArtefactPayload, session: Dict[str, Any]) -> ValidationResult:
    """Run all integrity validators against `payload`. Returns a
    `ValidationResult` whose `.ok` is True iff NO blocking offenders
    were found. Callers MUST check `.ok` before serializing the
    payload to the renderer."""
    offenders: List[ValidatorOffender] = []
    for v in _ALL_VALIDATORS:
        offenders.extend(v(payload, session))
    blocking = [o for o in offenders if o.severity == "block"]
    return ValidationResult(ok=not blocking, offenders=offenders)


__all__ = [
    "ValidatorOffender",
    "ValidationResult",
    "validate_artefact",
    "citation_lint",
    "confidence_calibration_audit",
    "refuse_to_decide_enforcement",
    "methodological_honesty_present",
    "bias_inventory_present",
    "bias_inventory_citation_lint",
    "bias_evidence_observational",
    "adversarial_counter_evidence_grounded",
    "pre_mortem_present",
    "pre_mortem_failure_evidence_grounded",
    "cost_asymmetry_present",
    "cost_asymmetry_evidence_grounded",
]



# ─────────────────────────────────────────────────────────────────
# Phase ZZ.2 (2026-02 fork-resume v2) — conversational validator
# ─────────────────────────────────────────────────────────────────
#
# `validate_conversational_response(text, attached_docs)` mirrors the
# structured-payload validators above but accepts a free-form chat
# reply. Three checks:
#
#   • Numeric-claim grounding: every number in the reply must be
#     followed by EITHER a citation marker OR the refusal token
#     "I don't have a source for this". Numbers that are clearly
#     placeholders (e.g. "step 1", "year 2024", phone-number-shaped)
#     are ignored.
#   • Confidence-named: if the reply contains a directional claim
#     verb ("will", "won't", "should", "the trend is"), it should
#     also contain a confidence range word ("high", "medium",
#     "low", "uncertain"). Warning only — not blocking.
#   • Bias-flag pattern: if the model emitted a `[bias · target]`
#     tag, capture it for the frontend chip renderer.
#
# Output: `ConversationalValidationResult` — a lightweight, post-
# completion structure. Violations are non-blocking by default; the
# Tier 3 caller (document-artefact path) escalates to blocking.

import re as _zz_re


@dataclass
class ConversationalValidationResult:
    ok: bool
    numeric_claims_total: int = 0
    numeric_claims_unsourced: int = 0
    confidence_named: bool = False
    bias_flags: List[str] = field(default_factory=list)  # ["anchoring · Q4 number", ...]
    notes: List[str] = field(default_factory=list)


_NUMBER_RE = _zz_re.compile(r"\b\d+(?:[\.,]\d+)?\s*(?:%|bps|x|m|bn|k)?\b", _zz_re.IGNORECASE)
_PLACEHOLDER_HINTS = ("step ", "year ", "version ", "v.")
_CITATION_HINTS = ("source:", "according to", "per the", "in the document",
                   "from the attached", "(see ", "[doc:", "[source:")
_REFUSAL_TOKEN = "i don't have a source for this"
_CONFIDENCE_WORDS = ("high confidence", "medium confidence", "low confidence",
                     "uncertain", "high", "medium", "low")
_DIRECTIONAL_VERBS = ("will ", "won't ", "should ", "the trend is", "expect")
_BIAS_TAG_RE = _zz_re.compile(r"\[([a-z][a-z\- ]*) · ([^\]]+)\]")


def validate_conversational_response(text: str, attached_docs: List[Dict[str, Any]] | None = None) -> ConversationalValidationResult:
    """Post-completion check on a chat reply. Always returns a
    result; callers decide whether to flag inline or block."""
    out = ConversationalValidationResult(ok=True)
    if not text:
        return out
    lc = text.lower()
    # Numeric grounding
    has_refusal = _REFUSAL_TOKEN in lc
    has_citation_marker = any(h in lc for h in _CITATION_HINTS)
    numbers = [m for m in _NUMBER_RE.finditer(text)]
    # Filter out obvious placeholders by looking at preceding ~6 chars
    real_numbers = []
    for m in numbers:
        head = text[max(0, m.start() - 12): m.start()].lower()
        if any(p in head for p in _PLACEHOLDER_HINTS):
            continue
        real_numbers.append(m)
    out.numeric_claims_total = len(real_numbers)
    if real_numbers and not (has_refusal or has_citation_marker or attached_docs):
        out.numeric_claims_unsourced = len(real_numbers)
        out.notes.append("numeric_claim_without_source")
        out.ok = False
    # Confidence named
    if any(v in lc for v in _DIRECTIONAL_VERBS):
        out.confidence_named = any(c in lc for c in _CONFIDENCE_WORDS)
        if not out.confidence_named:
            out.notes.append("directional_claim_without_confidence_range")
    # Bias flags
    for m in _BIAS_TAG_RE.finditer(text):
        out.bias_flags.append(f"{m.group(1)} · {m.group(2)}")
    return out


__all__.extend([
    "ConversationalValidationResult",
    "validate_conversational_response",
])
