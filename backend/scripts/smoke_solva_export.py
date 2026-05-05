"""Pure unit smoke test of the export builder against a hand-built session
dict — exercises the standard artefact + the refusal artefact without
hitting the FastAPI router or the DB.

Run: python3 backend/scripts/smoke_solva_export.py
"""
from __future__ import annotations
import os
import sys
sys.path.insert(0, "/app/backend")

from solva_artefact_export import build_pdf, build_docx, build_artefact_context

STD_SESSION = {
    "id": "11111111-2222-3333-4444-555555555555",
    "submodule": "develop_strategy",
    "persona": None,
    "intent": (
        "We have a 3-year strategic refresh due. The board wants a "
        "'next era' story but the CFO is sceptical that we have the cash to "
        "back any meaningful pivot."
    ),
    "cluster_label": "Strategy is drifting and nobody wants to say it",
    "status": "completed",
    "started_at": "2026-05-05T10:00:00+00:00",
    "completed_at": "2026-05-05T10:14:00+00:00",
    "synthesis": {
        "body": (
            "Three scenarios are credible. [T:corpus] Scenario A — keep the "
            "current strategy and double down on cost discipline. [T:comparable]\n\n"
            "Scenario B — partial pivot toward services revenue, capped at "
            "15% of group capex. [T:domain_prior] Scenario C — full divestment "
            "of the underperforming segment and a focused services bet. [T:user_assertion]"
        ),
        "stripped_text": "...",
        "claims": [
            {
                "text": "Scenario A — keep the current strategy and double down on cost discipline.",
                "tier": "corpus", "confidence_pct": 28, "confidence_band": "Unlikely",
            },
            {
                "text": "Scenario B — partial pivot toward services revenue, capped at 15% of group capex.",
                "tier": "comparable", "confidence_pct": 61, "confidence_band": "Likely",
            },
            {
                "text": "Scenario C — full divestment of the underperforming segment and a focused services bet.",
                "tier": "user_assertion", "confidence_pct": 18, "confidence_band": "Unlikely",
            },
        ],
        "tier_distribution": {"corpus": 1, "comparable": 1, "domain_prior": 0, "user_assertion": 1, "speculation": 0},
        "validation": {"verdict": "validated", "confidence": 88, "validator_provider": "gemini", "validator_model": "gemini-2.5-flash"},
        "recommendations": [
            "Recommendation 1: Commission the cash-flow stress test by the next board cycle.",
            "Recommendation 2: Brief the chair on the Scenario B scope-cap before committing to capex.",
        ],
    },
    "reasoning_audit_log": [
        {"engine": "candidate_generation", "engine_version": "1.0", "layer": "grounding",
         "tier_labels": ["corpus", "comparable"], "shield_required": True,
         "output": {"candidates": [{"hypothesis": "Cash-flow constraint", "tentative_tier_hint": "corpus", "weight": 0.35}]}},
        {"engine": "triangulation", "engine_version": "1.0", "layer": "grounding",
         "tier_labels": ["comparable"], "shield_required": True,
         "output": {"divergences": [{"summary": "User framing assumes growth pivot affordable; comparables suggest cap.", "severity": "medium", "source": "Comparable: PE-owned UK ISP 2022"}]}},
        {"engine": "probability_weighting", "engine_version": "1.0", "layer": "synthesis",
         "tier_labels": ["corpus", "comparable", "user_assertion"], "shield_required": False,
         "output": {"aggregation_breakdown": {"candidate_weights": 0.40, "triangulation_alignment": 0.35, "prior": 0.15, "counterfactual": 0.10}}},
        {"engine": "validator", "engine_version": "1.0", "layer": "synthesis",
         "tier_labels": [], "shield_required": True,
         "output": {"validator_verdict": "validated"}},
    ],
}

REFUSAL_SESSION = {
    **STD_SESSION,
    "id": "99999999-2222-3333-4444-555555555555",
    "status": "blocked_hard",
    "synthesis": None,
    "reasoning_audit_log": [
        {"engine": "candidate_generation", "engine_version": "1.0", "layer": "framing",
         "tier_labels": ["corpus"], "shield_required": True,
         "output": {"candidates": [{"hypothesis": "Cash-flow constraint", "tentative_tier_hint": "corpus", "weight": 0.35}]}},
        {"engine": "refusal", "engine_version": "1.0", "layer": "framing",
         "tier_labels": [], "shield_required": False,
         "output": {
             "verdict": "hard_block",
             "missing_evidence": "We do not have the latest cash-flow forecast nor the segment EBITDA disclosure to weight the divestment scenarios honestly.",
             "next_actions": [
                 "Pull last quarter's segment-level cash flow.",
                 "Get the CFO's draft of the strategic refresh capital ask.",
                 "Return for a full synthesis once both are in hand.",
             ],
         }},
    ],
}


def _write(path, data):
    with open(path, "wb") as f:
        f.write(data)
    print(f"  -> {path}  ({len(data)} bytes)")


def main():
    out_dir = "/tmp/solva_exports"
    os.makedirs(out_dir, exist_ok=True)

    print("[STD] context shape:")
    ctx = build_artefact_context(STD_SESSION)
    print(f"  is_refusal={ctx['is_refusal']}  scenarios={len(ctx['scenarios'])}  diagnosis_paragraphs={len(ctx['diagnosis_paragraphs'])}  recommendations={len(ctx['recommendations'])}  sensitivity={len(ctx['sensitivity_items'])}  tensions={len(ctx['tension_items'])}")

    print("[STD] PDF:")
    _write(f"{out_dir}/std.pdf", build_pdf(STD_SESSION))
    print("[STD] DOCX:")
    _write(f"{out_dir}/std.docx", build_docx(STD_SESSION))

    print("[REFUSAL] context shape:")
    ctx = build_artefact_context(REFUSAL_SESSION)
    print(f"  is_refusal={ctx['is_refusal']}  refusal_candidates={len(ctx.get('refusal_candidates', []))}  refusal_next_actions={len(ctx.get('refusal_next_actions', []))}")

    print("[REFUSAL] PDF:")
    _write(f"{out_dir}/refusal.pdf", build_pdf(REFUSAL_SESSION))
    print("[REFUSAL] DOCX:")
    _write(f"{out_dir}/refusal.docx", build_docx(REFUSAL_SESSION))

    print("OK — outputs in", out_dir)


if __name__ == "__main__":
    main()
