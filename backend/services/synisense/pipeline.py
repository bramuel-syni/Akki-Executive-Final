"""Synisense pipeline — the public entry.

Input/output contract is locked and documented in the package __doc__.
What this module owns:
  - Orchestration of regex → Presidio → LLM fallback.
  - Deterministic replacement-token assignment.
  - Writing the redacted text + spans + stats envelope.
  - Persistence to db.synisense_runs / db.synisense_shield_maps.
  - In-memory perf ring buffer for /api/admin/synisense/perf.
  - Audit log writes.
"""
from __future__ import annotations

import asyncio
import collections
import hashlib
import logging
import os
import statistics
import threading
import time as _time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from . import encryption, llm_fallback, pool, presidio_engine
from . import regex_recognisers

logger = logging.getLogger("akki.synisense.pipeline")

_VALID_SURFACES = {"chat", "ingest", "briefing", "deck", "report",
                   "solve", "solve_v2", "public_read",
                   # Phase 1 (2026-05-05) — added so the Document
                   # Journal lazy-on-click endpoint and the backfill
                   # script (`scripts/backfill_journal_commentary.py`)
                   # can both label their Synisense runs with the
                   # correct surface. Pre-Phase-1, the live path
                   # mis-labelled these as "briefing".
                   "journal_commentary",
                   # Phase J (2026-05-12) — Generative Sandbox MVP.
                   # The unauthenticated /sandbox route shields the
                   # visitor's free-text "situation" field before any
                   # LLM sees it. Defence in depth.
                   "sandbox_generation",
                   # Phase B.2 (2026-05-05) — chat two-pass method.
                   # `chat_classifier` is the surface for the turn-
                   # class probe (text → trivial/light_substantive/
                   # substantive_analytical/strategic_deliverable).
                   # `chat_four_check` is the surface for the silent
                   # tension/contradiction/assumption/framing-limit
                   # evaluation that runs on every light_substantive+
                   # turn. Both surfaces redact-mode-only — the
                   # transcripts they touch are short and bounded.
                   "chat_classifier", "chat_four_check",
                   # Phase B.2 patch (2026-05-05) — server-side thin-
                   # input refusal. `chat_evidence_list` is the surface
                   # for the constrained Gemini Flash call that fills
                   # the `[specific evidence …]` bracket of the verbatim
                   # thin-input refusal template. Bounded output
                   # (3–6 comma-separated items, ≤ 200 chars after
                   # sanitisation).
                   "chat_evidence_list",
                   # Phase G1/G5 (2026-05-11) — Privacy Wall Phase 2c.
                   # `pulse` is the surface for any text rendered into
                   # the Pulse feed or the cross-board aggregator.
                   # Today the across-boards aggregator is metadata-
                   # only and produces no text, but `redact_for_pulse_text`
                   # in `services.privacy_wall` invokes the shield with
                   # this surface tag so every future cross-board text
                   # emission is shielded by default.
                   "pulse"}

# Phase 15.1 anticipates per-engine sub-surfaces under solve_v2 so the perf
# ring buffer can separate (e.g.) triangulation latency from synthesis
# latency. Allow any surface of the form "solve_v2.<segment>" where segment
# is non-empty lowercase [a-z0-9_]. Hyphens and capitals are rejected
# deliberately so engine names stay snake_case.
_SOLVE_V2_SUB_RE = __import__("re").compile(r"^solve_v2\.[a-z0-9_]+$")


def _is_valid_surface(surface: str) -> bool:
    """Return True iff `surface` is in the explicit allow-list OR is a
    well-formed solve_v2 sub-surface."""
    if surface in _VALID_SURFACES:
        return True
    return bool(_SOLVE_V2_SUB_RE.match(surface or ""))
_VALID_MODES = {"redact", "shield_reversible", "passthrough_classify"}

_LOW_CONFIDENCE_THRESHOLD = 0.55

# TTL defaults — surface-scoped, with a hard max of 7 days.
_TTL_BY_SURFACE = {
    "ingest": "hours_default",     # 24h, configurable
    "public_read": "hours_one",    # 1h hard
}
_SHIELD_MAP_MAX_DAYS = 7

# Ring buffer for /api/admin/synisense/perf.
_PERF_BUFFER = collections.deque(maxlen=10000)
_PERF_LOCK = threading.Lock()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _shield_map_ttl(surface: str) -> timedelta:
    if surface == "public_read":
        return timedelta(hours=1)
    default_hours = int(os.environ.get("SYNISENSE_SHIELD_MAP_TTL_HOURS", "24"))
    default_hours = max(1, min(default_hours, _SHIELD_MAP_MAX_DAYS * 24))
    return timedelta(hours=default_hours)


def _merge_spans(
    regex_hits: List[Dict[str, Any]],
    presidio_hits: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge the two sources into a single non-overlapping sorted list.
    Regex wins on overlap — the regex layer is the high-precision
    fast-path (9 known patterns with surgical boundaries); Presidio is
    the discovery layer and sometimes greedily labels a pattern plus
    its surrounding context (e.g. 'IBAN GB33BUKB...' → ORGANIZATION).
    Giving regex priority keeps the entity labels accurate on the hard
    cases the legacy shield ladder already knew how to catch.
    """
    accepted: List[Dict[str, Any]] = list(regex_hits)

    def _overlaps(a, b):
        return not (a["end"] <= b["start"] or a["start"] >= b["end"])

    for p in presidio_hits:
        if not any(_overlaps(p, a) for a in accepted):
            accepted.append(p)
    accepted.sort(key=lambda h: (h["start"], -(h["end"] - h["start"])))
    # Final non-overlap pass for Presidio-vs-Presidio collisions.
    out: List[Dict[str, Any]] = []
    last_end = -1
    for h in accepted:
        if h["start"] >= last_end:
            out.append(h)
            last_end = h["end"]
    return out


def _short_label(entity_type: str) -> str:
    # Terse placeholder labels keep redacted text readable.
    return {
        "EMAIL_ADDRESS": "EMAIL",
        "PHONE_NUMBER": "PHONE",
        "IBAN_CODE": "IBAN",
        "CREDIT_CARD": "CARD",
        "US_SSN": "SSN",
        "UK_NHS": "NHS",
        "IP_ADDRESS": "IP",
        "URL": "URL",
        "DATE_TIME_EXACT": "DATE",
        "DATE_TIME": "DATE",
        "PERSON": "PERSON",
        "EMAIL": "EMAIL",
        "LOCATION": "LOC",
        "ORGANIZATION": "ORG",
        "DEAL_CODENAME": "DEAL",
        "EXECUTIVE_TITLE": "TITLE",
        "CHAIR_NAME": "CHAIR",
        "FINANCIAL_FIGURE_LARGE": "FIN",
    }.get(entity_type, entity_type[:8].upper() or "PII")


def _assign_replacements(
    spans: List[Dict[str, Any]], text: str,
) -> List[Dict[str, Any]]:
    """Deterministic per-run replacement tokens. Same match_text gets the
    same token within one run (stable reference), different matches get
    distinct counters."""
    counters: Dict[str, int] = {}
    seen: Dict[str, str] = {}
    out: List[Dict[str, Any]] = []
    for s in spans:
        match_text = s.get("match_text") or text[s["start"]:s["end"]]
        key = f"{s['entity_type']}:{match_text}"
        if key in seen:
            token = seen[key]
        else:
            lbl = _short_label(s["entity_type"])
            counters[lbl] = counters.get(lbl, 0) + 1
            token = f"[{lbl}_{counters[lbl]}]"
            seen[key] = token
        out.append({**s, "replacement": token, "match_text": match_text})
    return out


def _apply_redaction(text: str, spans: List[Dict[str, Any]]) -> str:
    if not spans:
        return text
    # Spans are sorted asc by start; walk right-to-left to preserve offsets.
    result = text
    for s in sorted(spans, key=lambda x: x["start"], reverse=True):
        result = result[:s["start"]] + s["replacement"] + result[s["end"]:]
    return result


async def _execute(
    text: str, *, context_id: str, surface: str, mode: str,
    tier_limit: Optional[int],
    context_people: Optional[List[str]],
) -> Dict[str, Any]:
    """Shared execution path for run() and dryrun(). Does not persist
    or write audit log — those are run()'s responsibility."""
    started = _time.monotonic()

    # Layer 1 — regex fast-path.
    t0 = _time.monotonic()
    regex_hits = regex_recognisers.scan(text)
    t_regex = int((_time.monotonic() - t0) * 1000)

    # Layer 2 — Presidio.
    t0 = _time.monotonic()
    try:
        presidio_hits = presidio_engine.analyze(
            text, context_people=context_people,
        )
    except Exception as e:  # noqa: BLE001
        logger.error("presidio failed (degraded): %s", e)
        presidio_hits = []
    t_presidio = int((_time.monotonic() - t0) * 1000)

    merged = _merge_spans(regex_hits, presidio_hits)

    # Layer 3 — LLM fallback for low-confidence, non-regex spans.
    cap = tier_limit if tier_limit is not None else int(
        os.environ.get("SYNISENSE_LLM_FALLBACK_CAP", "20"))
    concurrency = int(os.environ.get("SYNISENSE_LLM_FALLBACK_CONCURRENCY", "5"))
    timeout_ms = int(os.environ.get("SYNISENSE_LLM_FALLBACK_TIMEOUT_MS", "2000"))
    low_conf = [
        s for s in merged
        if s["source"] == "presidio"
        and float(s.get("confidence") or 0.0) < _LOW_CONFIDENCE_THRESHOLD
    ]
    llm_stats = {"llm_calls": 0, "llm_pii": 0, "llm_not_pii": 0,
                 "llm_uncertain": 0, "llm_skipped_cap": 0}
    if low_conf:
        t0 = _time.monotonic()
        classified, llm_stats = await llm_fallback.classify_low_confidence(
            text, low_conf, cap=cap, concurrency=concurrency, timeout_ms=timeout_ms,
        )
        t_llm = int((_time.monotonic() - t0) * 1000)
        # Replace the low-conf spans in `merged` with classifier output.
        by_key = {(c["start"], c["end"]): c for c in classified}
        new_merged: List[Dict[str, Any]] = []
        for s in merged:
            k = (s["start"], s["end"])
            if k in by_key:
                c = by_key[k]
                # Drop spans the LLM says are not PII; keep pii + uncertain.
                if c.get("llm_verdict") == "not_pii":
                    continue
                s = {**s, **c}
            new_merged.append(s)
        merged = new_merged
    else:
        t_llm = 0

    # Replacements.
    spans_with_repl = _assign_replacements(merged, text)
    redacted_text = _apply_redaction(text, spans_with_repl)

    # Filter the output spans down to the locked contract shape.
    out_spans = [
        {
            "start": s["start"], "end": s["end"],
            "entity_type": s["entity_type"],
            "source": s["source"],
            "confidence": float(s.get("confidence") or 1.0),
            "replacement": s["replacement"],
        }
        for s in spans_with_repl
    ]

    elapsed_ms = int((_time.monotonic() - started) * 1000)
    stats = {
        "elapsed_ms": elapsed_ms,
        "regex_hits": len(regex_hits),
        "presidio_hits": len(presidio_hits),
        "llm_hits": llm_stats.get("llm_pii", 0) + llm_stats.get("llm_uncertain", 0),
        "llm_calls": llm_stats.get("llm_calls", 0),
        "llm_skipped_cap": llm_stats.get("llm_skipped_cap", 0),
        "elapsed_breakdown_ms": {
            "regex": t_regex, "presidio": t_presidio, "llm": t_llm,
        },
    }
    return {
        "redacted_text": redacted_text,
        "spans": out_spans,
        "stats": stats,
        "spans_with_replacement": spans_with_repl,  # internal only
    }


async def dryrun(
    text: str, *, context_id: str = "", surface: str = "chat",
    mode: str = "redact",
    tier_limit: Optional[int] = None,
    context_people: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Execute the pipeline WITHOUT persisting anything. Returns the
    locked contract output plus internal debug fields. Writes to the
    perf ring buffer so admins can benchmark via real traffic."""
    if not _is_valid_surface(surface):
        raise ValueError(f"invalid surface: {surface}")
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid mode: {mode}")
    out = await _execute(
        text, context_id=context_id, surface=surface, mode=mode,
        tier_limit=tier_limit, context_people=context_people,
    )
    _record_perf(surface, out["stats"]["elapsed_ms"])
    out.pop("spans_with_replacement", None)
    out["shield_map_id"] = None
    return out


async def run(
    text: str, *, context_id: str, surface: str,
    mode: str = "redact",
    account_id: Optional[str] = None,
    tier_limit: Optional[int] = None,
    context_people: Optional[List[str]] = None,
    # Phase J.2 — per-message Synisense linking. When chat-family
    # surfaces are persisted via this path, the chat audit UI can
    # render a per-message redaction badge by querying on (chat_id,
    # message_id) instead of approximating by surface+time-window.
    message_id: Optional[str] = None,
    chat_id: Optional[str] = None,
    # SOLVA sprint (2026-05-12) — per-session Solva linking. When the
    # solva_v2 adapter calls into the pipeline, it threads the active
    # session_id through so the artefact UI can render a per-section
    # redaction badge grouped by (session_id, surface).
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute the pipeline AND persist. Returns the locked contract
    output including `shield_map_id` if mode=="shield_reversible".
    Writes `synisense_runs` (always) and `synisense_shield_maps`
    (only for shield_reversible). Audits every run."""
    if not _is_valid_surface(surface):
        raise ValueError(f"invalid surface: {surface}")
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid mode: {mode}")

    inner = await _execute(
        text, context_id=context_id, surface=surface, mode=mode,
        tier_limit=tier_limit, context_people=context_people,
    )
    _record_perf(surface, inner["stats"]["elapsed_ms"])

    shield_map_id: Optional[str] = None
    if mode == "shield_reversible" and inner["spans_with_replacement"]:
        shield_map_id = str(uuid.uuid4())
        originals = [s["match_text"] for s in inner["spans_with_replacement"]]
        replacements = [s["replacement"] for s in inner["spans_with_replacement"]]
        envelope = encryption.new_record_envelope(originals)
        ttl = _shield_map_ttl(surface)
        try:
            from core import db
            await db.synisense_shield_maps.insert_one({
                "id": shield_map_id,
                "context_id": context_id,
                "surface": surface,
                "created_at": _now_utc(),
                "expires_at": _now_utc() + ttl,
                "envelope": envelope,
                "replacements": replacements,
            })
        except Exception as e:  # noqa: BLE001
            logger.error("shield_map persist failed: %s", e)
            shield_map_id = None

    # Always persist the run record (sans original text).
    input_sha = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
    run_id = str(uuid.uuid4())
    spans_audit_view = [
        {k: s[k] for k in ("start", "end", "entity_type", "source", "confidence")}
        for s in inner["spans"]
    ]
    try:
        from core import db
        await db.synisense_runs.insert_one({
            "id": run_id,
            "context_id": context_id,
            "surface": surface,
            "mode": mode,
            "ts": _now_utc(),
            "account_id": account_id,
            "input_sha256": input_sha,
            "spans": spans_audit_view,
            "stats": inner["stats"],
            "shield_map_id": shield_map_id,
            "synisense_version": current_version(),
            # Phase J.2 — chat-family runs are linked to the specific
            # chat_message that triggered them, so the UI can render a
            # per-message redaction badge.
            "message_id": message_id,
            "chat_id": chat_id,
            # SOLVA sprint — per-Solva-session breakdown by surface.
            "session_id": session_id,
        })
    except Exception as e:  # noqa: BLE001
        logger.error("synisense_runs persist failed: %s", e)

    # Audit row. Never carries original text or shield_map_id.
    try:
        from core import write_audit
        await write_audit(
            context_id=context_id,
            account_id=account_id,
            action="synisense.run",
            resource_type="synisense_run",
            resource_id=run_id,
            metadata={
                "surface": surface, "mode": mode,
                "stats": inner["stats"],
                "span_count": len(inner["spans"]),
                "span_types": _histogram(inner["spans"]),
            },
        )
    except Exception:  # noqa: BLE001
        pass

    return {
        "redacted_text": inner["redacted_text"],
        "spans": inner["spans"],
        "stats": inner["stats"],
        "shield_map_id": shield_map_id,
    }


def _histogram(spans: List[Dict[str, Any]]) -> Dict[str, int]:
    h: Dict[str, int] = {}
    for s in spans:
        k = s.get("entity_type") or "UNKNOWN"
        h[k] = h.get(k, 0) + 1
    return h


def _record_perf(surface: str, elapsed_ms: int) -> None:
    with _PERF_LOCK:
        _PERF_BUFFER.append({
            "ts": _now_utc().isoformat(), "surface": surface,
            "elapsed_ms": elapsed_ms,
        })


def get_perf_snapshot() -> Dict[str, Any]:
    """Return p50/p95/p99 over the ring buffer. Empty buffer → zeros."""
    with _PERF_LOCK:
        rows = list(_PERF_BUFFER)
    if not rows:
        return {"count": 0, "p50": 0, "p95": 0, "p99": 0,
                "by_surface": {}, "buffer_size": _PERF_BUFFER.maxlen}
    xs = sorted([r["elapsed_ms"] for r in rows])
    def _pct(p):
        idx = max(0, min(len(xs) - 1, int(len(xs) * p / 100) - 1))
        return xs[idx]
    by_s: Dict[str, List[int]] = {}
    for r in rows:
        by_s.setdefault(r["surface"], []).append(r["elapsed_ms"])
    return {
        "count": len(rows),
        "p50": _pct(50),
        "p95": _pct(95),
        "p99": _pct(99),
        "mean": round(statistics.fmean(xs), 2),
        "max": xs[-1],
        "buffer_size": _PERF_BUFFER.maxlen,
        "by_surface": {
            s: {"count": len(v), "p50": sorted(v)[len(v) // 2],
                "p95": sorted(v)[max(0, int(len(v) * 0.95) - 1)]}
            for s, v in by_s.items()
        },
    }


def get_status_snapshot() -> Dict[str, Any]:
    """Real status body for /api/synisense/status."""
    return {
        "ok": True,
        "mode": "live",
        "key_version": encryption.current_key_version(),
        "insecure_fallback": encryption.is_insecure_fallback(),
        "registered_key_versions": encryption.registered_versions(),
        "model": os.environ.get("SYNISENSE_SPACY_MODEL", "en_core_web_sm"),
        "pool": pool.pool_health(),
        "llm_fallback": {
            "cap_per_doc": int(os.environ.get("SYNISENSE_LLM_FALLBACK_CAP", "20")),
            "concurrency": int(os.environ.get("SYNISENSE_LLM_FALLBACK_CONCURRENCY", "5")),
            "timeout_ms": int(os.environ.get("SYNISENSE_LLM_FALLBACK_TIMEOUT_MS", "2000")),
        },
        "shield_map_ttl": {
            "default_hours": int(os.environ.get("SYNISENSE_SHIELD_MAP_TTL_HOURS", "24")),
            "public_read_hours": 1,
            "max_days": _SHIELD_MAP_MAX_DAYS,
        },
        "version": current_version(),
    }


_VERSION = "12.1.0"


def current_version() -> str:
    return _VERSION
