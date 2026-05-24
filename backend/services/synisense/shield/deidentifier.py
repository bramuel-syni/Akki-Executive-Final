"""Synisense Shield — de-identification pipeline (Phase A).

Three-layer stack, in priority order:

  1) **Regex pass** — deterministic patterns (MONEY, EMAIL, PHONE_E164,
     IBAN, ACCOUNT_NUM, DATE_ISO, IP, URL, SSN). Replaced first because
     they are unambiguous AND because we don't want spaCy to chunk a
     ten-digit phone number into a "PRODUCT" or similar mistake.

  2) **Tenant entity dictionary** — case-insensitive longest-match
     against the per-tenant entity catalogue harvested from existing
     Mongo (`accounts`, `contexts`, `cycles`). Runs BEFORE spaCy so
     user-known proper nouns are always caught regardless of whether
     spaCy recognises them.

  3) **Local spaCy NER** — `en_core_web_trf` preferred (transformer),
     falls back to `en_core_web_sm` on ImportError/OSError per the
     Phase A brief. Covers PERSON, ORG, GPE, PRODUCT, NORP, FAC,
     EVENT, LAW.

Every detected entity is replaced with an opaque stable token of the
shape ``[[ENT_<TYPE>_<NNN>]]`` where ``<NNN>`` is a per-request
zero-padded counter and ``<TYPE>`` is the canonical type label. The
caller receives the redacted text plus a `{token: original_value}` map
which `reidentifier.reidentify()` reverses on the response path.

**Fail-closed semantics** (course correction directive): if spaCy
cannot be loaded OR the tenant dictionary lookup throws, this module
raises `ServiceUnavailable`. The Shield route MUST surface this as
`503 SERVICE_UNAVAILABLE` to the consumer. Raw content NEVER reaches
the outbound LLM under any failure mode.

Performance target: <1s end-to-end on a 500-word document on CPU.
Measured in tests via `time.perf_counter`.
"""
from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from services.synisense.exceptions import ServiceUnavailable

log = logging.getLogger("synisense.shield.deidentifier")


# ─────────────────────────────────────────────────────────────────────
# Regex layer — Phase A locked patterns.
# Token type labels follow the brief verbatim (uppercase).
# ─────────────────────────────────────────────────────────────────────
#
# Demo-blocker patch (2026-02): added Luhn-validated CREDIT_CARD layer
# (runs BEFORE ACCOUNT_NUM so 13-19 digit Luhn-valid runs are tagged
# correctly), UK_NI_NUMBER, and API_KEY families. The audit panel
# label map in `routers/chat_audit_panel.py:_ENTITY_LABEL` carries the
# user-visible prose for each new type.

def _luhn_valid(digits_only: str) -> bool:
    """Standard mod-10 Luhn check. `digits_only` must already be a
    digit-only string (callers normalise away spaces/dashes). Returns
    True iff the run passes Luhn — i.e. is a plausible payment-card
    PAN rather than a generic 13-19 digit number."""
    if not digits_only or not digits_only.isdigit():
        return False
    total = 0
    parity = len(digits_only) % 2
    for i, ch in enumerate(digits_only):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# Patterns whose hits are POST-FILTERED by an extra predicate before
# being treated as redactions. Keys map the entity type to a predicate
# that takes the raw match text and returns True iff it should redact.
_REGEX_VALIDATORS: Dict[str, Any] = {
    # CREDIT_CARD: digits-only Luhn check. Filters out random 13-19
    # digit runs (order numbers, IDs) that happen to match the shape.
    "CREDIT_CARD": lambda raw: _luhn_valid(re.sub(r"[\s\-]", "", raw)),
}


_REGEX_PATTERNS: List[Tuple[str, re.Pattern]] = [
    # MONEY — currency symbols + amount, or amount + ISO code. Capture
    # the whole match including currency. Order matters: this MUST run
    # before bare-number patterns.
    ("MONEY", re.compile(
        r"(?:[\$€£¥₹]\s?\d{1,3}(?:[,\s]\d{3})*(?:\.\d{1,2})?|"
        r"\d{1,3}(?:[,\s]\d{3})*(?:\.\d{1,2})?\s?(?:USD|EUR|GBP|JPY|INR|CHF|CAD|AUD|NZD))"
    )),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    # API_KEY — runs early so a Bearer/JWT/AKIA token isn't shredded by
    # a more permissive downstream pattern. Several distinct families
    # in one combined alternation; ALL families produce the same
    # token type ("API_KEY") with the same redacted placeholder.
    ("API_KEY", re.compile(
        # AWS access-key ids (always 20 chars, AKIA prefix).
        r"\bAKIA[0-9A-Z]{16}\b"
        # Stripe-style secret/publishable keys (sk_live_, sk_test_, pk_live_, pk_test_, rk_).
        r"|\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b"
        # GitHub personal-access / fine-grained / app tokens.
        r"|\bgh[ps]_[A-Za-z0-9]{36,}\b"
        # SendGrid (SG.<22-char>.<43-char>).
        r"|\bSG\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\b"
        # Slack tokens (xoxb-, xoxa-, xoxp-, xoxr-, xoxs-).
        r"|\bxox[abprso]-[A-Za-z0-9\-]{10,}\b"
        # JWTs (header.payload.signature, all base64url).
        r"|\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b"
        # `Bearer <opaque>` — keep the Bearer prefix in the match so
        # the placeholder fully replaces it.
        r"|\bBearer\s+[A-Za-z0-9._\-]{20,}\b"
        # OpenAI-style sk-... keys (covers both classic and project keys).
        r"|\bsk-[A-Za-z0-9_\-]{20,}\b"
    )),
    # PHONE_E164 — E.164-ish (+ prefix, 10–15 digits with optional
    # spaces/dashes/parens). The course correction names this explicitly.
    ("PHONE_E164", re.compile(
        r"\+\d{1,3}[\s.\-]?\(?\d{2,4}\)?[\s.\-]?\d{3,4}[\s.\-]?\d{3,4}"
    )),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")),
    # CREDIT_CARD — 13 to 19 digits with optional space/dash
    # separators. Luhn-validated downstream via _REGEX_VALIDATORS so
    # non-card 16-digit numbers (order ids, etc.) don't false-positive.
    # MUST run BEFORE ACCOUNT_NUM so Luhn-valid runs claim the span
    # first (same priority + same span → first emitter wins).
    ("CREDIT_CARD", re.compile(r"\b(?:\d[\s\-]?){12,18}\d\b")),
    # ACCOUNT_NUM — bank-account-shaped runs of 8–17 digits. Matched
    # AFTER MONEY and CREDIT_CARD so prices and PANs aren't swallowed.
    ("ACCOUNT_NUM", re.compile(r"\b\d{8,17}\b")),
    # UK_NI_NUMBER — National Insurance Number, two prefix letters
    # (with several disallowed letters per HMRC rules), six digits,
    # one trailing letter A-D. Case-insensitive in practice.
    ("UK_NI_NUMBER", re.compile(
        r"\b[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]\b", re.IGNORECASE,
    )),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("DATE_ISO", re.compile(r"\b\d{4}-\d{2}-\d{2}\b")),
    ("IP", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("URL", re.compile(r"\bhttps?://[^\s)>\]]+")),
]

# spaCy entity types we redact. Locked to the course-correction list.
_SPACY_TYPES_KEPT = {"PERSON", "ORG", "GPE", "PRODUCT", "NORP", "FAC", "EVENT", "LAW"}


# ─────────────────────────────────────────────────────────────────────
# spaCy model loader (lazy + thread-safe).
#
# Tries `en_core_web_trf` first per the brief, falls back to
# `en_core_web_sm` on ImportError (spacy-transformers missing) or
# OSError (model not installed and can't fetch). The fallback is
# explicitly permitted by the brief.
# ─────────────────────────────────────────────────────────────────────
_SPACY_NLP = None
_SPACY_MODEL_NAME: Optional[str] = None
_SPACY_LOAD_ERROR: Optional[str] = None
_SPACY_LOCK = threading.Lock()


def _attempt_load(model_name: str):
    """Try `spacy.load(model_name)`. For the heavy `en_core_web_trf`
    model we ONLY attempt loading if `spacy-transformers` is already
    importable — otherwise we'd kick off a ~2GB torch+transformers
    install that doesn't fit the dev container. The Phase A brief
    explicitly permits the `en_core_web_sm` fallback in that case.

    H2.5 follow-up Part A (2026-05-24) — broadened ``except OSError``
    to ``except Exception``. Asymmetric cost analysis: the regulatory
    cost of fail-OPEN (PAN leaking to the LLM because the model load
    raised something we didn't expect — e.g. ``MemoryError`` at OOM,
    ``ImportError`` on a corrupt wheel, ``RuntimeError`` from a
    miswired spaCy plugin) vastly outweighs the UX cost of
    fail-CLOSED on benign exceptions. The caller catches this
    Exception and reroutes to the ``en_core_web_sm`` retry path; if
    THAT also raises, ``_ensure_spacy`` returns ``None`` and the
    pipeline raises ``ServiceUnavailable`` → HTTP 503."""
    import spacy  # noqa: WPS433 — lazy by design
    if model_name == "en_core_web_trf":
        try:
            import spacy_transformers  # noqa: F401
        except ImportError as exc:
            raise OSError(
                "spacy-transformers not installed — skipping en_core_web_trf "
                "to avoid a 2GB torch install. Falling back to en_core_web_sm."
            ) from exc
    try:
        return spacy.load(model_name)
    except Exception as exc:  # noqa: BLE001 — see docstring; fail-closed by design
        # Originally `except OSError` — broadened to Exception so a
        # MemoryError / ImportError / RuntimeError at load time also
        # routes to the sm fallback (and ultimately to 503) instead of
        # bubbling unhandled out of `_ensure_spacy` and silently
        # leaving the cache empty.
        log.warning(
            "synisense.shield: %s load raised %s: %s — attempting download",
            model_name, type(exc).__name__, str(exc)[:200],
        )
        subprocess.run(  # noqa: S603 — known model, no shell
            [sys.executable, "-m", "spacy", "download", model_name],
            check=True, capture_output=True, timeout=120,
        )
        return spacy.load(model_name)


def _ensure_spacy() -> Any:
    """Lazy-load spaCy with trf → sm fallback. Idempotent + thread-safe.

    Returns the loaded `nlp` object. Caches the result process-wide. On
    failure, sets `_SPACY_LOAD_ERROR` and returns `None`; callers
    surface `ServiceUnavailable` so we stay fail-closed.
    """
    global _SPACY_NLP, _SPACY_MODEL_NAME, _SPACY_LOAD_ERROR
    if _SPACY_NLP is not None:
        return _SPACY_NLP
    if _SPACY_LOAD_ERROR is not None:
        # Failed previously — don't retry on the hot path.
        return None
    with _SPACY_LOCK:
        if _SPACY_NLP is not None:
            return _SPACY_NLP
        # Try trf first.
        for candidate in ("en_core_web_trf", "en_core_web_sm"):
            try:
                _SPACY_NLP = _attempt_load(candidate)
                _SPACY_MODEL_NAME = candidate
                if candidate == "en_core_web_sm":
                    log.warning(
                        "synisense.shield: using en_core_web_sm fallback "
                        "(F1 ≈ 0.86 vs ~0.91 for trf). To upgrade, install "
                        "spacy-transformers + en_core_web_trf."
                    )
                log.info("synisense.shield: spaCy NER ready (model=%s)", candidate)
                return _SPACY_NLP
            except Exception as exc:  # noqa: BLE001
                last = f"{type(exc).__name__}: {str(exc)[:200]}"
                log.warning("synisense.shield: %s failed (%s)", candidate, last)
                _SPACY_LOAD_ERROR = last
                # H2.5 follow-up Part A (2026-05-24) — log shield-init
                # failures to `audit_invariant_violations` so operators
                # see WHICH exception class is hitting the wild (the
                # admin endpoint surfaces this collection).
                # Best-effort; failure here must NOT mask the fail-
                # closed contract.
                try:
                    import uuid as _uuid
                    from datetime import datetime as _dt, timezone as _tz
                    from core import db as _db
                    import asyncio as _asyncio
                    _coro = _db.audit_invariant_violations.insert_one({
                        "id": "iv-" + _uuid.uuid4().hex,
                        "kind": "shield_init_failure",
                        "surface": "shield.deidentifier",
                        "channel": "boot_or_lazy",
                        "model_candidate": candidate,
                        "error_class": type(exc).__name__,
                        "error_message": str(exc)[:400],
                        "ts": _dt.now(_tz.utc).isoformat(),
                    })
                    # `_ensure_spacy` is sync; the Motor call returns
                    # a coroutine. Schedule it on the running loop if
                    # one exists; otherwise skip (test contexts often
                    # call this from threads without a loop).
                    try:
                        loop = _asyncio.get_event_loop()
                        if loop.is_running():
                            _asyncio.ensure_future(_coro)
                        else:
                            loop.run_until_complete(_coro)
                    except Exception:  # noqa: BLE001
                        _coro.close()
                except Exception:  # noqa: BLE001
                    pass
                continue
        return None


def get_spacy_model_name() -> Optional[str]:
    """Test/admin probe."""
    return _SPACY_MODEL_NAME


def get_spacy_load_error() -> Optional[str]:
    """Test/admin probe."""
    return _SPACY_LOAD_ERROR


# ─────────────────────────────────────────────────────────────────────
# H2.5 follow-up Part B (2026-05-24) — Boot-time Shield warmup.
# ─────────────────────────────────────────────────────────────────────
# Called from FastAPI's startup event. On failure, raises so the
# process dies; supervisor restarts it and keeps crash-looping until
# ops fixes the model. Plus exposes the latest warmup state so
# `GET /api/healthz/shield` can answer truthfully without re-running
# the load.
# ─────────────────────────────────────────────────────────────────────
_WARMUP_AT: Optional[str] = None
_WARMUP_DURATION_MS: Optional[int] = None
_WARMUP_OK: bool = False
_WARMUP_ERROR: Optional[str] = None


def get_warmup_state() -> Dict[str, Any]:
    """Snapshot of the latest warmup outcome for the healthz endpoint."""
    import importlib
    model_version: Optional[str] = None
    try:
        if _SPACY_MODEL_NAME:
            pkg = importlib.import_module(_SPACY_MODEL_NAME)
            model_version = getattr(pkg, "__version__", None) or None
    except Exception:  # noqa: BLE001
        model_version = None
    return {
        "ready": _WARMUP_OK and _SPACY_NLP is not None,
        "model_loaded": _SPACY_NLP is not None,
        "model_name": _SPACY_MODEL_NAME,
        "model_version": model_version,
        "last_warmup_at": _WARMUP_AT,
        "last_warmup_duration_ms": _WARMUP_DURATION_MS,
        "last_warmup_error": _WARMUP_ERROR,
    }


async def warmup_or_die() -> None:
    """Boot-time gate. Loads spaCy + runs a no-op deidentify on a
    trivial string. On ANY exception, raises so the process dies and
    supervisor restarts it — crash-looping is correct behaviour when
    Shield can't initialise, because the alternative is silently
    forwarding PAN to the LLM.

    Sets module-level ``_WARMUP_*`` globals so
    ``GET /api/healthz/shield`` reads the most recent warmup snapshot
    without re-running the load on every hit.
    """
    from datetime import datetime as _dt, timezone as _tz
    global _WARMUP_AT, _WARMUP_DURATION_MS, _WARMUP_OK, _WARMUP_ERROR

    started = time.perf_counter()
    try:
        nlp = _ensure_spacy()
        if nlp is None:
            raise RuntimeError(
                f"Shield warmup: spaCy model unavailable "
                f"({_SPACY_LOAD_ERROR or 'unknown'})"
            )
        # Trivial round-trip — proves the pipeline actually runs.
        result = await deidentify("warmup probe", tenant_id="__warmup__")
        if not isinstance(result.redacted_text, str):
            raise RuntimeError(
                f"Shield warmup: unexpected DeIdResult shape: {type(result)!r}"
            )
        _WARMUP_OK = True
        _WARMUP_ERROR = None
        _WARMUP_DURATION_MS = int((time.perf_counter() - started) * 1000)
        _WARMUP_AT = _dt.now(_tz.utc).isoformat()
        log.info(
            "synisense.shield: warmup OK (model=%s, %d ms)",
            _SPACY_MODEL_NAME, _WARMUP_DURATION_MS,
        )
    except Exception as exc:  # noqa: BLE001 — see docstring; re-raised
        _WARMUP_OK = False
        _WARMUP_ERROR = f"{type(exc).__name__}: {str(exc)[:300]}"
        _WARMUP_DURATION_MS = int((time.perf_counter() - started) * 1000)
        _WARMUP_AT = _dt.now(_tz.utc).isoformat()
        log.error(
            "synisense.shield: WARMUP FAILED (%s) — process will exit",
            _WARMUP_ERROR,
        )
        raise


def _force_clear_cache_for_test() -> None:
    """Test-only hook to reset the module-level cache between tests."""
    global _SPACY_NLP, _SPACY_MODEL_NAME, _SPACY_LOAD_ERROR
    _SPACY_NLP = None
    _SPACY_MODEL_NAME = None
    _SPACY_LOAD_ERROR = None


# ─────────────────────────────────────────────────────────────────────
# Public API.
# ─────────────────────────────────────────────────────────────────────
class DeIdResult:
    __slots__ = ("redacted_text", "token_map", "de_id_summary",
                 "dilution_score", "exposure_reduction_score", "elapsed_ms")

    def __init__(self, redacted_text: str, token_map: Dict[str, str],
                 de_id_summary: Dict[str, int], dilution_score: float,
                 exposure_reduction_score: float, elapsed_ms: int) -> None:
        self.redacted_text = redacted_text
        self.token_map = token_map
        self.de_id_summary = de_id_summary
        self.dilution_score = dilution_score
        self.exposure_reduction_score = exposure_reduction_score
        self.elapsed_ms = elapsed_ms

    def as_dict(self) -> Dict[str, Any]:
        return {
            "redacted_text": self.redacted_text,
            "token_map": self.token_map,
            "de_id_summary": self.de_id_summary,
            "dilution_score": self.dilution_score,
            "exposure_reduction_score": self.exposure_reduction_score,
            "elapsed_ms": self.elapsed_ms,
        }


async def deidentify(content: str, *, tenant_id: str) -> DeIdResult:
    """Three-layer de-identification.

    Fail-closed: any unrecoverable failure raises `ServiceUnavailable`.
    The caller (the Shield route) MUST translate that to a 503.
    """
    start = time.perf_counter()
    if not content:
        return DeIdResult(
            redacted_text="", token_map={}, de_id_summary={},
            dilution_score=0.0, exposure_reduction_score=0.0, elapsed_ms=0,
        )

    original = content
    original_len = len(original)
    original_words = max(1, len(re.findall(r"\S+", original)))

    # Collect every hit, then resolve overlaps preferring higher priority.
    # Priority: regex > tenant_dict > spaCy.
    hits: List[Dict[str, Any]] = []

    # Layer 1 — regex.
    for label, pat in _REGEX_PATTERNS:
        validator = _REGEX_VALIDATORS.get(label)
        for m in pat.finditer(original):
            raw_match = m.group(0)
            if validator is not None and not validator(raw_match):
                # E.g. CREDIT_CARD shape matched but Luhn failed —
                # drop the hit so a downstream pattern (ACCOUNT_NUM)
                # can still claim the span if it overlaps. Hits with
                # no validator pass through unchanged.
                continue
            hits.append({
                "start": m.start(), "end": m.end(),
                "type": label, "match": raw_match, "priority": 1,
            })

    # Layer 2 — tenant entity dictionary.
    try:
        from services.synisense.shield.tenant_entities import lookup_in_text
        tenant_hits = await lookup_in_text(original, tenant_id=tenant_id)
        for h in tenant_hits:
            hits.append({**h, "priority": 2})
    except Exception as exc:  # noqa: BLE001
        # Fail-closed.
        raise ServiceUnavailable(
            f"tenant_entities lookup failed: {type(exc).__name__}: {str(exc)[:200]}"
        ) from exc

    # Layer 3 — local spaCy NER.
    nlp = _ensure_spacy()
    if nlp is None:
        raise ServiceUnavailable(
            "spaCy model unavailable: " + (_SPACY_LOAD_ERROR or "unknown")
        )
    # spaCy is sync + can be slow. Run it on a worker thread so we don't
    # block the event loop. The model itself releases the GIL during
    # the transformer forward pass.
    try:
        doc = await asyncio.to_thread(nlp, original)
    except Exception as exc:  # noqa: BLE001
        raise ServiceUnavailable(
            f"spaCy inference failed: {type(exc).__name__}: {str(exc)[:200]}"
        ) from exc

    for ent in doc.ents:
        if ent.label_ not in _SPACY_TYPES_KEPT:
            continue
        hits.append({
            "start": ent.start_char, "end": ent.end_char,
            "type": ent.label_, "match": ent.text, "priority": 3,
        })

    # Resolve overlaps: prefer lower priority number (higher priority).
    # Same priority → prefer earlier start, longer span.
    hits.sort(key=lambda h: (h["start"], h["priority"], -(h["end"] - h["start"])))
    resolved: List[Dict[str, Any]] = []
    last_end = -1
    for h in hits:
        if h["start"] >= last_end:
            resolved.append(h)
            last_end = h["end"]
        elif h["priority"] < resolved[-1]["priority"] and h["end"] > resolved[-1]["start"]:
            # Higher-priority hit overlaps a lower-priority one already
            # accepted — replace if the new span dominates.
            if h["start"] <= resolved[-1]["start"] and h["end"] >= resolved[-1]["end"]:
                resolved[-1] = h
                last_end = h["end"]

    # Token assignment: stable per-document counter per type.
    # Same original value within a document → same token (dedup map).
    counters: Dict[str, int] = {}
    text_to_token: Dict[Tuple[str, str], str] = {}  # (type, normalized_text) → token
    token_map: Dict[str, str] = {}                   # token → original_value
    summary: Dict[str, int] = {}  # count of UNIQUE entity tokens per type

    def _token_for(entity_type: str, original_text: str) -> str:
        key = (entity_type, original_text.strip().lower())
        if key in text_to_token:
            return text_to_token[key]
        counters[entity_type] = counters.get(entity_type, 0) + 1
        tok = f"[[ENT_{entity_type}_{counters[entity_type]:03d}]]"
        text_to_token[key] = tok
        token_map[tok] = original_text
        summary[entity_type] = summary.get(entity_type, 0) + 1
        return tok

    # Build redacted text — walk left-to-right.
    parts: List[str] = []
    cursor = 0
    chars_replaced = 0
    tokens_inserted = 0
    for h in sorted(resolved, key=lambda x: x["start"]):
        parts.append(original[cursor:h["start"]])
        tok = _token_for(h["type"], h["match"])
        parts.append(tok)
        cursor = h["end"]
        chars_replaced += (h["end"] - h["start"])
        tokens_inserted += 1
    parts.append(original[cursor:])
    redacted = "".join(parts)

    # Scoring (course-correction formulas).
    exposure_reduction = (chars_replaced / original_len * 100.0) if original_len else 0.0
    exposure_reduction = max(0.0, min(100.0, exposure_reduction))
    dilution = (tokens_inserted / original_words * 100.0) if original_words else 0.0
    dilution = max(0.0, min(100.0, dilution))

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return DeIdResult(
        redacted_text=redacted,
        token_map=token_map,
        de_id_summary=summary,
        dilution_score=round(dilution, 2),
        exposure_reduction_score=round(exposure_reduction, 2),
        elapsed_ms=elapsed_ms,
    )
