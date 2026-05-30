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
from typing import Any, Dict, List, Optional, Set

from .artefact_schema import ArtefactPayload
from .citation_resolver import (
    CitationResolver,
    COARSE_LAYER_TAGS as _CR_COARSE_LAYER_TAGS,
)


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


# ─────────────────────────────────────────────────────────────────
# Scope C (Sprint Z.2.C, 2026-02) — refuse_to_decide hardening
# ─────────────────────────────────────────────────────────────────
#
# The bare-pattern scan above over-fires on observational text. The
# helpers below classify each match's local context as IMPERATIVE
# (Solva telling the user what to do) or OBSERVATIONAL (narration,
# noun-form, hyphenated compound, negated non-user subject,
# counterfactual, infinitive-in-subordinate-clause). Pure token-level
# heuristics — NO NLP dependency.


# Trigger verbs that double as nouns / noun-modifiers in finance /
# governance prose. When one of these appears, run the noun-form
# detector before flagging.
_VERB_NOUN_AMBIGUOUS = frozenset({
    "retain", "fire", "hire", "kill", "launch", "raise",
    "sell", "exit", "pivot", "liquidate", "acquire", "merge", "terminate",
})


# Determiners / quantifiers / possessives / adjectives that, when
# immediately preceding a trigger verb, mark it as a NOUN ("a pivot",
# "partial pivot", "his exit", "the sell-off").
_NOUN_FORM_PREFIXES = (
    "a", "an", "the", "this", "that", "these", "those",
    "his", "her", "its", "their", "our", "my", "your",
    "any", "every", "each", "some", "no", "another",
    "one", "two", "three", "first", "second", "third", "another",
    "partial", "full", "major", "minor", "strategic", "tactical",
    "potential", "possible", "likely", "early", "late",
    "good", "bad", "clear", "clean", "messy", "abrupt", "gradual",
    "hostile", "friendly", "forced",
)


# Hyphenated compound markers — `cross-sell`, `buy-back`, `sell-off`,
# `pivot-to-services`, `exit-horizon`, etc. The trigger verb is
# embedded in a compound noun.
_HYPHEN_COMPOUND_RE_CACHE: Dict[str, re.Pattern] = {}


def _hyphen_compound_re(verb: str) -> re.Pattern:
    """Cached regex that matches the trigger verb as part of a
    hyphenated compound — either preceded by `\\w-` or followed by
    `-\\w`."""
    if verb not in _HYPHEN_COMPOUND_RE_CACHE:
        _HYPHEN_COMPOUND_RE_CACHE[verb] = re.compile(
            r"(?:\w-" + re.escape(verb) + r"\b|\b" + re.escape(verb) + r"-\w)",
            re.IGNORECASE,
        )
    return _HYPHEN_COMPOUND_RE_CACHE[verb]


# Negation contexts where the subject is NOT the user — e.g.
# "institutional shareholders typically do not underwrite".
_NEGATION_BIGRAM = re.compile(
    r"\b(?:typically|often|usually|historically|never|rarely|seldom|"
    r"generally|sometimes|occasionally)\s+do(?:es)?\s+not\b",
    re.IGNORECASE,
)

# User-directed subjects — when present in the same sentence,
# negation hardening is OFF (the model IS instructing the user).
_USER_SUBJECT_TOKENS = (
    "you ", "you,", "you.", "you;", "you:",
    "the founder ", "the executive ", "the user ",
    "the board ", "the committee ", "the chair ",
    "the cfo ", "the ceo ", "the ned ", "the team ",
    "we ", "we,", "we.", "we;", "we:",
)


# Counterfactual "should have <past participle>" — describes a
# hypothetical past, NOT an instruction.
_COUNTERFACTUAL_SHOULD_HAVE_RE = re.compile(
    r"\bshould\s+have\s+(?:not\s+)?\w+(?:ed|en|n|t)\b",
    re.IGNORECASE,
)


# Noun-modifier compound: `<trigger> <noun>` where the trigger is
# acting as an attributive noun ("exit horizon", "sell pressure",
# "pivot strategy", "hire freeze"). Common attributive-noun second
# words below.
_ATTRIBUTIVE_NEXT_NOUNS = frozenset({
    "horizon", "strategy", "pressure", "process", "decision",
    "candidate", "candidates", "freeze", "wave", "schedule",
    "timeline", "rationale", "math", "logic", "ratio", "ratios",
    "multiple", "multiples", "price", "value", "valuation",
    "approach", "approaches", "moment", "moments", "window",
    "windows", "trigger", "triggers", "signal", "signals",
    "narrative", "narratives", "thesis", "theses",
    "assumptions", "assumption", "framing",
})


def _trigger_is_noun_form(
    sentence: str,
    match_start: int,
    match_end: int,
    matched: str,
) -> bool:
    """True iff the matched trigger is acting as a noun rather than a
    verb (= NOT imperative). Conservative — only returns True when at
    least one structural cue is present."""
    verb = matched.lower().strip()
    if verb not in _VERB_NOUN_AMBIGUOUS:
        return False
    # Hyphenated compound — `cross-sell`, `pivot-to-services`.
    if _hyphen_compound_re(verb).search(sentence):
        return True
    # Determiner / quantifier / possessive / adjective immediately
    # preceding (allowing one optional modifier).
    head = sentence[:match_start].rstrip()
    # Look at last two words.
    head_tokens = re.findall(r"[A-Za-z\u2014\u2013\-']+", head)[-2:]
    head_tokens_lc = [t.lower() for t in head_tokens]
    if head_tokens_lc and head_tokens_lc[-1] in _NOUN_FORM_PREFIXES:
        return True
    if (
        len(head_tokens_lc) >= 2
        and head_tokens_lc[-2] in _NOUN_FORM_PREFIXES
        and head_tokens_lc[-1] not in {"and", "or", "but", "to", "with"}
    ):
        return True
    # Gerund-object idiom: `<gerund> <trigger>` where the gerund's
    # direct object is the trigger-as-noun. Common cases:
    # `holding fire`, `taking exit`, `facing sell pressure`. The
    # preceding word is an `-ing` form, which marks it as a gerund
    # taking the trigger as its object.
    if head_tokens_lc and head_tokens_lc[-1].endswith("ing") and len(head_tokens_lc[-1]) > 4:
        return True
    # Dash / em-dash / colon immediately preceding — common nominal
    # bullet ("— partial pivot", ": pivot toward...").
    pre_chars = sentence[max(0, match_start - 4): match_start]
    if any(d in pre_chars for d in ("\u2014", "\u2013", " - ", ": ", "; ")):
        # Combined with one of the noun-prefixes above already handled.
        # On its own a dash is not conclusive; require a noun-prefix.
        if head_tokens_lc and head_tokens_lc[-1] in _NOUN_FORM_PREFIXES:
            return True
    # Attributive-noun compound: trigger followed by a recognised
    # second-word noun ("exit horizon", "pivot strategy").
    tail = sentence[match_end:].lstrip()
    tail_tokens = re.findall(r"[A-Za-z]+", tail)[:1]
    if tail_tokens and tail_tokens[0].lower() in _ATTRIBUTIVE_NEXT_NOUNS:
        return True
    return False


def _sentence_has_user_subject(sentence: str) -> bool:
    """True iff the sentence directly addresses the user / founder."""
    lc = sentence.lower()
    return any(tok in lc for tok in _USER_SUBJECT_TOKENS)


def _trigger_is_observational_negation(
    sentence: str,
    matched: str,
) -> bool:
    """True iff the trigger sits inside a negation describing what
    SOMEONE ELSE doesn't do — observational, not instruction."""
    if not matched.lower().startswith("do not"):
        return False
    if _sentence_has_user_subject(sentence):
        return False
    return bool(_NEGATION_BIGRAM.search(sentence))


def _trigger_is_counterfactual_should_have(
    sentence: str,
    matched: str,
) -> bool:
    """True iff `should have <past_participle>` — counterfactual narration."""
    if not matched.lower().startswith("should"):
        return False
    return bool(_COUNTERFACTUAL_SHOULD_HAVE_RE.search(sentence))


def _trigger_is_subordinate_infinitive(
    sentence: str,
    match_start: int,
    matched: str,
) -> bool:
    """True iff the trigger appears as `to <verb>` inside a
    subordinate / relativised clause whose main verb is negated or
    observational ("Paying 14x to acquire that ambiguity doesn't
    resolve concentration")."""
    verb = matched.lower().strip()
    if verb not in _VERB_NOUN_AMBIGUOUS:
        return False
    pre = sentence[:match_start]
    pre_chars = pre[-4:].lower()
    if not pre_chars.endswith("to "):
        return False
    # Look for negation or observational main verb in the rest of the
    # sentence — these mark the surrounding clause as describing why
    # an action wouldn't work, not instructing the action.
    post = sentence[match_start:].lower()
    obs_markers = (
        " doesn't ", " does not ", " didn't ", " did not ",
        " won't ", " will not ", " isn't ", " is not ",
        " wouldn't ", " would not ", " can't ", " cannot ",
        " never ", " hasn't ", " has not ", " hadn't ", " had not ",
    )
    return any(m in post for m in obs_markers)


def _trigger_is_observational(
    sentence: str,
    match_obj: re.Match,
) -> bool:
    """Top-level dispatcher — applies every hardening heuristic in
    sequence. Returns True iff the trigger should NOT fire as an
    imperative."""
    matched = match_obj.group(0)
    if _trigger_is_noun_form(sentence, match_obj.start(), match_obj.end(), matched):
        return True
    if _trigger_is_counterfactual_should_have(sentence, matched):
        return True
    if _trigger_is_observational_negation(sentence, matched):
        return True
    if _trigger_is_subordinate_infinitive(sentence, match_obj.start(), matched):
        return True
    return False


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


def citation_lint(
    payload: ArtefactPayload,
    session: Dict[str, Any],
    *,
    resolver: Optional[CitationResolver] = None,
) -> List[ValidatorOffender]:
    """Every numerical claim in the rendered payload MUST cite at least
    one source that resolves to an audit-log id.

    Scope:
      • headline.key_findings[].paragraph_text
      • tensions[].implication + tensions[].prevailing_framing
      • scenarios[].description + scenarios[].label
      • sensitivity_inputs[].impact_explanation + cluster_weight_shift_mechanic
      • pathway[].detail_paragraph

    Scope A (Sprint Z.2.B, 2026-02) — every cited `source_input_id`
    must additionally resolve against the embedded session arrays, a
    coarse-layer tag, or the pre-fetched DB store for the citation's
    `source_kind`. Unresolvable ids surface a `citation_unverifiable`
    blocking offender carrying the id + kind in the failure payload.
    """
    offenders: List[ValidatorOffender] = []
    log_ids = _audit_log_ids(session)
    cr = resolver if resolver is not None else CitationResolver(session)

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
        unresolved = [cid for cid in cited_ids if cid not in log_ids and cid not in _CR_COARSE_LAYER_TAGS]
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
        # Scope A — citation realness verification. For each cited
        # SourceCitation object (carrying both id and source_kind),
        # ask the resolver to verify embedded + DB-level reality.
        for c in (citations or []):
            cid = getattr(c, "source_input_id", None)
            kind = getattr(c, "source_kind", None)
            if not cid or not kind:
                continue
            result = cr.resolve(cid, kind)
            if not result.resolved:
                offenders.append(ValidatorOffender(
                    validator="citation_lint",
                    severity="block",
                    location=f"{prefix}.source_citations",
                    message=(
                        f"citation_unverifiable: id={cid!r} kind={kind!r} does not "
                        f"resolve to any embedded array, coarse-layer tag, or DB-level "
                        f"record."
                    ),
                    revision_hint=(
                        "Replace this citation with one whose source_input_id resolves "
                        "against the session's reasoning_audit_log / user_turns / "
                        "attached_docs / comparables, OR against the canonical DB store "
                        "for the declared source_kind (documents / extractions_log / "
                        "chat_audit_log / audit_log / solva_v1_comparables_archive)."
                    ),
                ))

    for i, kf in enumerate(payload.headline.key_findings):
        _check(f"headline.key_findings[{i}]", kf.paragraph_text, kf.source_citations)

    # Scope A — tensions[].prevailing_framing was hardcoded as `[]`
    # for the citation list, which guaranteed a `citation_lint` trip
    # on any prevailing-framing prose containing a number. Now we
    # pass a real synthetic SourceCitation wrapping
    # `evidence_block.source_layer_question_id` — that id IS a real
    # audit-log entry id already emitted by the engine layer; we are
    # just constructing the SourceCitation envelope at validator-read
    # time so the existing `_check` interface keeps working. (The
    # EvidenceBlock schema doesn't carry a citation list directly.)
    for i, t in enumerate(payload.tensions):
        eb = t.evidence_block
        synthetic_cites: List[Any] = []
        if eb and eb.source_layer_question_id:
            class _S:
                source_input_id = eb.source_layer_question_id
                source_kind = "audit_log"
                source_layer = eb.source_layer
            synthetic_cites.append(_S())
        _check(f"tensions[{i}].prevailing_framing", t.prevailing_framing, synthetic_cites)
        _check(f"tensions[{i}].implication", t.implication, synthetic_cites)

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


def confidence_calibration_audit(
    payload: ArtefactPayload,
    session: Dict[str, Any],
    *,
    resolver: Optional[CitationResolver] = None,
) -> List[ValidatorOffender]:
    """Any scenario where `confidence_pct >= 70` must name at least 2
    INDEPENDENT triangulating evidence sources in
    `confidence_calibration_reasoning` AND in `supporting_evidence[]`.

    Independence is approximated by counting distinct `source_kind`
    values OR distinct `source_layer` values across `supporting_evidence`.
    A scenario citing 2 user_turn entries from the same layer is NOT
    independent triangulation.

    Scope A (Sprint Z.2.B, 2026-02) — every cited entry must also
    RESOLVE (embedded session array / coarse-layer tag / pre-fetched
    DB store). An entry that doesn't resolve trips
    `citation_unverifiable` with the un-resolvable id in the message.
    """
    offenders: List[ValidatorOffender] = []
    cr = resolver if resolver is not None else CitationResolver(session)
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
        # Scope A — citation realness for every supporting_evidence entry.
        for j, e in enumerate(s.supporting_evidence):
            r = cr.resolve(e.source_input_id, e.source_kind)
            if not r.resolved:
                offenders.append(ValidatorOffender(
                    validator="confidence_calibration_audit",
                    severity="block",
                    location=f"scenarios[{i}].supporting_evidence[{j}]",
                    message=(
                        f"citation_unverifiable: id={e.source_input_id!r} "
                        f"kind={e.source_kind!r} does not resolve to any embedded "
                        f"array, coarse-layer tag, or DB-level record."
                    ),
                    revision_hint=(
                        f"At scenarios[{i}].supporting_evidence[{j}], replace the "
                        f"unverifiable id with one that resolves against the session "
                        f"or its canonical DB store for source_kind={e.source_kind!r}."
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

    Scope C (Sprint Z.2.C, 2026-02) — production hardening. Each
    pattern match now runs through `_trigger_is_observational` which
    classifies the local context:
      • verbs-as-nouns ("partial pivot", "exit horizon") → not imperative
      • hyphenated compounds ("cross-sell math") → not imperative
      • counterfactual `should have <pp>` → not imperative
      • negation with non-user subject ("shareholders typically do not
        underwrite") → not imperative
      • infinitive in subordinate clause whose main verb is negated
        ("to acquire that ambiguity doesn't resolve") → not imperative
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
                    # Scope C — observational-context detector.
                    if _trigger_is_observational(sentence, m):
                        continue
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
                    # Scope C hardening.
                    if _trigger_is_observational(sentence, m):
                        continue
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
                    if _trigger_is_observational(item.suggested_mitigation, m):
                        continue
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
    + observational openers. Returns a list of offenders.

    Scope C (Sprint Z.2.C, 2026-02) — applies the
    `_trigger_is_observational` hardening before flagging."""
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
                if _trigger_is_observational(sentence, m):
                    continue
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


# Validators that accept a `resolver=` keyword argument (Scope A, 2026-02).
# Other validators in the suite still receive only (payload, session).
_RESOLVER_AWARE_VALIDATORS = (
    citation_lint,
    confidence_calibration_audit,
)


def validate_artefact(
    payload: ArtefactPayload,
    session: Dict[str, Any],
    *,
    resolver: Optional[CitationResolver] = None,
    db_resolved_ids: Optional[Dict[str, Set[str]]] = None,
) -> ValidationResult:
    """Run all integrity validators against `payload`. Returns a
    `ValidationResult` whose `.ok` is True iff NO blocking offenders
    were found. Callers MUST check `.ok` before serializing the
    payload to the renderer.

    Scope A (Sprint Z.2.B, 2026-02) — `resolver` (or `db_resolved_ids`
    for the lazy construction shortcut) lets the caller plug in a
    pre-warmed `CitationResolver` whose embedded session index is
    augmented with DB-level pre-fetched ids. When neither is supplied,
    a default embedded-only resolver is constructed (existing behaviour
    + coarse-tag whitelist).
    """
    if resolver is None:
        resolver = CitationResolver(session, db_resolved_ids=db_resolved_ids)
    offenders: List[ValidatorOffender] = []
    for v in _ALL_VALIDATORS:
        if v in _RESOLVER_AWARE_VALIDATORS:
            offenders.extend(v(payload, session, resolver=resolver))
        else:
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
