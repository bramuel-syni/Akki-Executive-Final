"""Presidio-based NER layer with custom board-specific recognisers.

The analyzer runs in the calling process today (process pool wiring is
in pool.py — disabled in 12.1 because warming the pool inside a uvicorn
reloader-watched process trips fork issues; tracked as a known gap).
Lazy-loaded module-singleton on first call.

Custom recognisers added on top of stock English PII pack:
  - EXECUTIVE_TITLE     — common C-suite + chair / board-level titles
  - CHAIR_NAME          — names seeded from contexts.people (per-call)
  - FINANCIAL_FIGURE_LARGE — £/$/€ amounts >=7 figures

Phase 12.3 ITEM A — DEAL_CODENAME ("Project Falcon", "Operation Magpie")
moved to the regex pre-pass in `regex_recognisers.py`. Stock spaCy NER
inside Presidio kept beating the previous PatternRecognizer's score
during Presidio's internal merge, so the histogram label landed wrong
even though redaction itself happened. Putting DEAL_CODENAME in the
regex layer lets the pipeline's `_merge_spans()` give it deterministic
precedence over any Presidio NER call on the same text — the merge
rule is regex-wins-on-overlap, by design.

Presidio is configured to use `en_core_web_sm` (locked per Phase 12.1).
Flip the env var `SYNISENSE_SPACY_MODEL` to override without code change.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger("akki.synisense.presidio")

_LOCK = threading.Lock()
_ANALYZER = None  # type: ignore[assignment]


def _ensure_spacy_model(model_name: str) -> None:
    """Make sure the spaCy model is importable; download it if missing.

    Deployment fix (2026-05-12) — spaCy language models are no longer
    pinned in `/app/backend/requirements.txt` because the deployer's
    pip-compile/freeze step rewrites `package @ url` to `package==version`
    form, which fails to resolve against PyPI (the models live only on
    GitHub releases). Instead, we lazy-download the model at first use.
    A successful download in the sandbox image (where the model is
    already installed) is a no-op — `spacy.load` returns immediately.
    """
    try:
        import spacy
        spacy.load(model_name)
        return
    except OSError:
        # Model not installed — fall through to the download path.
        pass
    except ImportError:
        # spaCy itself isn't installed — let _build_analyzer raise its
        # own clearer ImportError below; nothing we can do here.
        return

    logger.warning(
        "spaCy model %s not present; running 'python -m spacy download %s'…",
        model_name, model_name,
    )
    try:
        subprocess.run(
            [sys.executable, "-m", "spacy", "download", model_name],
            check=True,
        )
        logger.info("spaCy model %s downloaded successfully.", model_name)
    except subprocess.CalledProcessError as exc:
        logger.error(
            "spaCy model %s download failed (rc=%s). Presidio will raise on first analyze call.",
            model_name, exc.returncode,
        )


def _build_analyzer():  # noqa: ANN202 — Presidio types are heavy
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, PatternRecognizer, Pattern
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    model_name = os.environ.get("SYNISENSE_SPACY_MODEL", "en_core_web_sm")
    _ensure_spacy_model(model_name)
    nlp_conf = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": model_name}],
    }
    nlp_engine = NlpEngineProvider(nlp_configuration=nlp_conf).create_engine()

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers(nlp_engine=nlp_engine, languages=["en"])

    # ── DEAL_CODENAME has moved to the regex pre-pass — see
    # `regex_recognisers.py`. Removed from Presidio in Phase 12.3 ITEM A
    # to keep the taxonomy single-sourced and avoid the score-tie merge
    # bug that mislabelled "Project Falcon" as PERSON / ORGANIZATION.

    # ── EXECUTIVE_TITLE — surfaced job-titles that often sit beside names.
    registry.add_recognizer(PatternRecognizer(
        supported_entity="EXECUTIVE_TITLE",
        patterns=[Pattern(
            name="executive_title",
            regex=(
                r"\b(?:Chief\s+(?:Executive|Financial|Operating|Risk|People|Information|"
                r"Marketing|Technology|Strategy)\s+Officer|CEO|CFO|COO|CRO|CIO|CMO|CTO|CSO|"
                r"Chair(?:man|woman)?|Non[-\s]?Executive\s+Director|NED|Senior\s+Independent\s+Director|"
                r"Company\s+Secretary)\b"
            ),
            score=0.75,
        )],
    ))

    # ── FINANCIAL_FIGURE_LARGE — £, $ or € amounts >= 7 figures.
    # Conservative: only commas-as-thousands-separators or trailing m/bn suffixes.
    registry.add_recognizer(PatternRecognizer(
        supported_entity="FINANCIAL_FIGURE_LARGE",
        patterns=[
            Pattern(
                name="fin_figure_commas",
                regex=r"[£$€]\s?\d{1,3}(?:,\d{3}){2,}(?:\.\d+)?",
                score=0.8,
            ),
            Pattern(
                name="fin_figure_mn_bn",
                regex=r"[£$€]\s?\d+(?:\.\d+)?\s*(?:m|mn|bn|billion|million)\b",
                score=0.8,
            ),
        ],
    ))

    analyzer = AnalyzerEngine(registry=registry, nlp_engine=nlp_engine, supported_languages=["en"])
    return analyzer


def get_analyzer():  # noqa: ANN202
    global _ANALYZER
    if _ANALYZER is not None:
        return _ANALYZER
    with _LOCK:
        if _ANALYZER is None:
            _ANALYZER = _build_analyzer()
            logger.info("Presidio analyzer ready (model=%s)",
                        os.environ.get("SYNISENSE_SPACY_MODEL", "en_core_web_sm"))
    return _ANALYZER


def analyze(
    text: str,
    *,
    context_people: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Run Presidio analysis. Returns spans:
        [{start, end, entity_type, score, source: 'presidio'}]
    `context_people` is an optional list of names from `contexts.people`
    that will be matched as CHAIR_NAME on top of stock PERSON detection.
    """
    if not text:
        return []
    analyzer = get_analyzer()
    raw = analyzer.analyze(text=text, language="en")
    spans: List[Dict[str, Any]] = [
        {
            "start": r.start, "end": r.end,
            "entity_type": r.entity_type, "confidence": float(r.score),
            "source": "presidio",
        }
        for r in raw
    ]
    # CHAIR_NAME context-seeded from per-call list. Done outside Presidio
    # because the list changes per-context and we don't want to rebuild
    # the analyzer registry on every call.
    if context_people:
        for name in context_people:
            n = name.strip()
            if len(n) < 3:
                continue
            for m in re.finditer(r"\b" + re.escape(n) + r"\b", text):
                spans.append({
                    "start": m.start(), "end": m.end(),
                    "entity_type": "CHAIR_NAME", "confidence": 0.95,
                    "source": "presidio",
                })
    spans.sort(key=lambda s: (s["start"], -(s["end"] - s["start"])))
    return spans
