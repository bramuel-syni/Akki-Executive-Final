"""Phase P5.14 — Workbook Analyzer service package.

Sibling system to Solva v2 — NOT an extension. The Solva v2 engine
+ artefact schema remain byte-identical. The workbook analyzer
carries its own citation kind (`workbook_cell`), its own report
schema, and its own resolver. The only Solva v2 surface this
package leans on is the LLM adapter (`shielded_call`) — the
canonical shielded-LLM entry point. Every LLM call from the
analyzer goes through that adapter so the `no_direct_llm_calls`
CI guard stays green.

Public surface:

  WorkbookAnalysis        — root Pydantic doc persisted in Mongo
  WorkbookCitation        — workbook_cell citation type
  parse_workbook          — xlsx / csv parser
  WorkbookCitationResolver — cell-range resolver (rejects fabricated locations)
  extract_signals_for     — deterministic + (optional) shielded narration
  run_monte_carlo         — pure numpy, deterministic seed
  run_forecast            — numpy linear regression baseline
  detect_anomalies        — z-score + IQR with optional shielded commentary
  build_pptx_report       — python-pptx deck with chair-readable speaker notes
  validate_no_imperatives — refuse-to-decide check (raises on imperative-to-user)
"""
from .schema import (
    WorkbookAnalysis,
    WorkbookCitation,
    WorkbookSheet,
    WorkbookColumn,
    WorkbookSignal,
    MonteCarloRun,
    ForecastRun,
    AnomalyRow,
    NarrationBlock,
)
from .parser import parse_workbook
from .citation_resolver import (
    WorkbookCitationResolver,
    CitationUnverifiable,
)
from .monte_carlo import run_monte_carlo
from .forecaster import run_forecast
from .anomaly_detector import detect_anomalies
from .signal_extractor import extract_signals_for
from .refuse_to_decide import validate_no_imperatives, RefuseToDecideViolation
from .report_builder import build_pptx_report

__all__ = [
    "WorkbookAnalysis",
    "WorkbookCitation",
    "WorkbookSheet",
    "WorkbookColumn",
    "WorkbookSignal",
    "MonteCarloRun",
    "ForecastRun",
    "AnomalyRow",
    "NarrationBlock",
    "parse_workbook",
    "WorkbookCitationResolver",
    "CitationUnverifiable",
    "run_monte_carlo",
    "run_forecast",
    "detect_anomalies",
    "extract_signals_for",
    "validate_no_imperatives",
    "RefuseToDecideViolation",
    "build_pptx_report",
]
