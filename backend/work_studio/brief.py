"""
Work Studio brief — the structured intermediate format every generator
ingests. Same input → DOCX, PPTX, PDF.

Phase C.1 (2026-05-10). Built around the user's two reference samples
(MYDAWA Board Briefing PPTX and WeDeliver Concept Note DOCX) so the
shape of the brief mirrors what those references express:

  - cover block (title, subtitle, host, version, date, audience)
  - sidebar metadata (company · document_type · programme) for PPTX
  - framework spine — three-word structural device (e.g.
    "CONNECT · RESOURCE · DELIVER") used by DOCX & DOCX-derived PDF
  - sections with: title, optional kicker, body paragraphs, optional
    bullets, optional tables (rows of cells)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# Tone/depth user-facing labels. Picker exposes the same values.
DEPTH_EXECUTIVE = "executive_brief"
DEPTH_BOARD     = "board_summary"
DEPTH_DEEP      = "deep_dive"
DEPTHS = (DEPTH_EXECUTIVE, DEPTH_BOARD, DEPTH_DEEP)

FIDELITY_LOW    = "low"
FIDELITY_HIGH   = "high"
FIDELITIES = (FIDELITY_LOW, FIDELITY_HIGH)

FORMAT_DOCX     = "docx"
FORMAT_PPTX     = "pptx"
FORMAT_PDF      = "pdf"
FORMATS = (FORMAT_DOCX, FORMAT_PPTX, FORMAT_PDF)


@dataclass
class BriefTable:
    """A structured table. headers + rows of cells. Rendered as a real
    docx/pptx table at high fidelity, falls back to a bulleted list at
    low fidelity."""
    title: str
    headers: List[str]
    rows: List[List[str]]


@dataclass
class BriefSection:
    title: str
    kicker: Optional[str] = None              # short ALL-CAPS label
    body_paragraphs: List[str] = field(default_factory=list)
    bullets: List[str] = field(default_factory=list)
    tables: List[BriefTable] = field(default_factory=list)


@dataclass
class Brief:
    title: str
    subtitle: str = ""
    company_label: str = "Akki"               # left sidebar 1st token (PPTX)
    document_type: str = "Board Briefing"     # left sidebar 2nd token
    programme: Optional[str] = None           # left sidebar 3rd token
    version: str = "v1.0"
    date_text: str = ""                       # human "March 2026"
    host_org_line: Optional[str] = None       # DOCX cover block
    audience: Optional[str] = None
    framework_spine: Optional[str] = None     # "CONNECT · RESOURCE · DELIVER"
    cover_lead_paragraph: Optional[str] = None
    sections: List[BriefSection] = field(default_factory=list)
    closing_recap: Optional[str] = None
    closing_brand_line: Optional[str] = None
    # Provenance — surfaced in the export footer for governance.
    source_id: str = ""
    source_type: str = ""
    depth: str = DEPTH_BOARD
    fidelity: str = FIDELITY_HIGH

    def with_depth(self, depth: str) -> "Brief":
        self.depth = depth
        return self

    def with_fidelity(self, fidelity: str) -> "Brief":
        self.fidelity = fidelity
        return self


# ---------------------------------------------------------------------------
# Builder — Solva session → Brief.
#
# This is the only source-type wired in C.1. cycle_compilation lands in
# Phase D; chat_artefact is a thin pass-through. The shape of the brief
# is driven by the chosen depth so a single Solva session can produce
# six different layouts (3 depth × 2 fidelity) without re-querying.
# ---------------------------------------------------------------------------

# Insight copy for the picker. FT-toned. Each option carries a one-line
# peer-toned description of what the user will get.
PICKER = {
    "depth": [
        {"id": DEPTH_EXECUTIVE, "label": "Executive Brief",
         "insight": "One page. The decision, the tension, the call. Read in two minutes."},
        {"id": DEPTH_BOARD, "label": "Board Summary",
         "insight": "Five to eight pages. The full board pack arc — framing, evidence, options, recommended call. Read in ten."},
        {"id": DEPTH_DEEP, "label": "Deep Dive",
         "insight": "Fifteen-plus pages. Every supporting argument, every claim, every cited source. Read in an hour."},
    ],
    "fidelity": [
        {"id": FIDELITY_LOW, "label": "Low Fidelity (Draft)",
         "insight": "Quick, structured prose. Headings and bullets. Good for circulation and feedback before the work is final."},
        {"id": FIDELITY_HIGH, "label": "High Fidelity (Board Grade)",
         "insight": "Cover, persistent sidebars, structured tables, board-grade typography. Ship-ready."},
    ],
    "format": [
        {"id": FORMAT_DOCX, "label": "Word",
         "insight": "For commentary and inline edits. Track-changes friendly."},
        {"id": FORMAT_PPTX, "label": "PowerPoint",
         "insight": "For the room. One slide per decision point, side-bar branded."},
        {"id": FORMAT_PDF, "label": "PDF",
         "insight": "For circulation. Locked layout, identical on every machine."},
    ],
}


def _bullets_from_recommendations(recs: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for r in recs[:6]:
        text = (r.get("text") or "").strip()
        if text:
            out.append(f"Recommendation {r.get('ordinal') or len(out) + 1}: {text}")
    return out


def _table_kpi_contract(claims: List[Dict[str, Any]]) -> Optional[BriefTable]:
    """Translate Solva claim-tier markers into the MYDAWA-style KPI Contract
    table: KPI · Baseline · Target · Cadence. We synthesise where the claim
    text is qualitative — better to ship a *structured* table than a free-
    form bullet list, per the user's quality bar."""
    rows: List[List[str]] = []
    for c in claims[:6]:
        ctext = (c.get("text") or c.get("claim") or "").strip()
        if not ctext:
            continue
        tier = (c.get("tier") or c.get("source_tier") or "").strip()
        kpi = ctext if len(ctext) <= 60 else ctext[:57] + "…"
        cadence = "Monthly" if "monthly" in ctext.lower() else (
            "Quarterly" if "quarter" in ctext.lower() else "Per cycle")
        rows.append([kpi, "—", "—", cadence + (f" · {tier}" if tier else "")])
    if not rows:
        return None
    return BriefTable(
        title="Claim cadence",
        headers=["Claim", "Baseline", "Target", "Cadence · Tier"],
        rows=rows,
    )


def _table_what_gets_done(recs: List[Dict[str, Any]]) -> Optional[BriefTable]:
    """The MYDAWA "What gets done" device — # · What · Why it matters · Owner · By."""
    rows: List[List[str]] = []
    for i, r in enumerate(recs[:6]):
        text = (r.get("text") or "").strip()
        if not text:
            continue
        # Heuristic split: take first sentence as "what", rest as "why".
        if "." in text:
            first, rest = text.split(".", 1)
            what = (first + ".").strip()
            why = rest.strip() or "—"
        else:
            what, why = text, "—"
        rows.append([str(i + 1), what[:90], why[:90], "Sponsor", "Next cycle"])
    if not rows:
        return None
    return BriefTable(
        title="What gets done",
        headers=["#", "What", "Why it matters", "Owner", "By"],
        rows=rows,
    )


def build_brief_from_solva(session: Dict[str, Any], *,
                           company_label: str, document_type: str,
                           programme: Optional[str], depth: str,
                           fidelity: str) -> Brief:
    """Translate a persisted Solva v2 session document into a Brief shaped
    for the requested depth + fidelity."""
    sub = session.get("submodule") or "seek_clarity"
    intent = (session.get("intent") or "").strip()
    syn = session.get("synthesis") or {}
    body = (syn.get("body") or syn.get("text") or "").strip()
    claims = syn.get("claims") or []
    recs = syn.get("recommendations") or []
    validation = syn.get("validation") or {}
    persona = session.get("persona") or ""

    submodule_titles = {
        "seek_clarity":        "Clarity Read",
        "develop_strategy":    "Strategy Memo",
        "simulate_hypothesis": "Hypothesis Stress-Test",
        "get_perspective":     "Perspective Read",
    }
    sub_title = submodule_titles.get(sub, "Solva Memo")

    title = f"{sub_title}: {(intent[:70] + ('…' if len(intent) > 70 else '')) or '—'}"
    subtitle = (
        f"From a {persona} lens" if (sub == "get_perspective" and persona)
        else f"Synthesised from a Solva {sub.replace('_', ' ')} session"
    )

    framework_spine = {
        "seek_clarity":        "OBSERVE · DIAGNOSE · DECIDE",
        "develop_strategy":    "FRAME · WEIGH · COMMIT",
        "simulate_hypothesis": "STATE · STRESS-TEST · ACT",
        "get_perspective":     "CONTRAST · REVEAL · DECIDE",
    }.get(sub, "OBSERVE · DIAGNOSE · DECIDE")

    brief = Brief(
        title=title,
        subtitle=subtitle,
        company_label=company_label,
        document_type=document_type,
        programme=programme,
        version="v1.0",
        date_text="",  # left blank so file is byte-deterministic
        host_org_line=f"{company_label} · {document_type}",
        audience="Board, executive team, and named sponsors",
        framework_spine=framework_spine,
        cover_lead_paragraph=intent or body[:240],
        source_id=session.get("id") or "",
        source_type="solva_session",
        depth=depth,
        fidelity=fidelity,
    )

    # Turn the synthesis body paragraphs into prose paragraphs.
    body_paras = [p.strip() for p in body.split("\n\n") if p.strip()]

    # Section construction by depth ----------------------------------------
    if depth == DEPTH_EXECUTIVE:
        # 1-page / 1-3 slides. Single decision-tension-call section.
        brief.sections = [
            BriefSection(
                title="The decision, the tension, the call",
                kicker="EXECUTIVE BRIEF",
                body_paragraphs=body_paras[:2] or [body[:600]],
                bullets=_bullets_from_recommendations(recs)[:3],
            ),
        ]
        brief.closing_recap = (
            f"Validation: {validation.get('verdict','—')} "
            f"({validation.get('confidence','—')}% confidence)."
        )
        brief.closing_brand_line = f"{company_label} · {document_type}"
    elif depth == DEPTH_BOARD:
        # 5-8 pages / 8-12 slides — the full board pack arc.
        brief.sections = [
            BriefSection(title="The framing", kicker="WHY THIS MATTERS",
                         body_paragraphs=[intent] if intent else []),
            BriefSection(title="What we found", kicker="THE EVIDENCE",
                         body_paragraphs=body_paras[:3]),
            BriefSection(title="Where the weight sits", kicker="ANALYSIS",
                         body_paragraphs=body_paras[3:5] or body_paras[:1]),
            BriefSection(title="Recommended call", kicker="THE RECOMMENDATION",
                         bullets=_bullets_from_recommendations(recs)),
            BriefSection(title="What gets done", kicker="ACTION",
                         tables=[t for t in [_table_what_gets_done(recs)] if t],
                         bullets=(_bullets_from_recommendations(recs)
                                  if not _table_what_gets_done(recs) else [])),
            BriefSection(
                title="Validation",
                kicker="HOW WE'RE SURE",
                body_paragraphs=[
                    f"Verdict: {validation.get('verdict','—')}.",
                    f"Confidence: {validation.get('confidence','—')}%.",
                    f"Validator: {validation.get('validator_provider','—')} "
                    f"({validation.get('validator_model','—')}).",
                ],
            ),
        ]
        brief.closing_recap = (
            f"This memo was synthesised from a Solva {sub.replace('_',' ')} session "
            f"and carries a {validation.get('verdict','—')} verdict at "
            f"{validation.get('confidence','—')}% confidence."
        )
        brief.closing_brand_line = f"{company_label} · {document_type}"
    elif depth == DEPTH_DEEP:
        # 15+ pages / 18+ slides — every supporting argument.
        kpi_table = _table_kpi_contract(claims)
        action_table = _table_what_gets_done(recs)
        brief.sections = [
            BriefSection(title="The framing", kicker="WHY THIS MATTERS",
                         body_paragraphs=[intent] if intent else []),
            BriefSection(title="The starting position", kicker="CURRENT STATE",
                         body_paragraphs=body_paras[:1]),
            BriefSection(title="What we found — first read", kicker="THE EVIDENCE",
                         body_paragraphs=body_paras[1:3]),
            BriefSection(title="What we found — second read", kicker="THE EVIDENCE",
                         body_paragraphs=body_paras[3:5]),
            BriefSection(title="Where the weight sits", kicker="ANALYSIS",
                         body_paragraphs=body_paras[5:7] or body_paras[:1]),
            BriefSection(title="Tensions surfaced", kicker="WHERE IT HURTS",
                         body_paragraphs=body_paras[7:9] or []),
            BriefSection(title="Claim cadence", kicker="WHAT TO TRACK",
                         tables=[t for t in [kpi_table] if t],
                         bullets=([f"{c.get('text','')[:160]}" for c in claims[:6]]
                                  if not kpi_table else [])),
            BriefSection(title="Recommended call", kicker="THE RECOMMENDATION",
                         bullets=_bullets_from_recommendations(recs)),
            BriefSection(title="What gets done", kicker="ACTION",
                         tables=[t for t in [action_table] if t],
                         bullets=(_bullets_from_recommendations(recs)
                                  if not action_table else [])),
            BriefSection(
                title="Validation",
                kicker="HOW WE'RE SURE",
                body_paragraphs=[
                    f"Verdict: {validation.get('verdict','—')}.",
                    f"Confidence: {validation.get('confidence','—')}%.",
                    f"Validator: {validation.get('validator_provider','—')} "
                    f"({validation.get('validator_model','—')}).",
                    *((validation.get("notes") or [])[:3]),
                ],
            ),
            BriefSection(
                title="Provenance",
                kicker="HOW THIS WAS BUILT",
                body_paragraphs=[
                    f"Source: Solva v2 session {session.get('id','—')[:8]}.",
                    f"Submodule: {sub.replace('_', ' ').title()}.",
                    "Voice: Financial Times — dry, professional, peer-toned.",
                ],
            ),
        ]
        brief.closing_recap = (
            f"This deep dive carries a {validation.get('verdict','—')} verdict "
            f"at {validation.get('confidence','—')}% confidence and was synthesised from "
            f"{len(claims)} claims and {len(recs)} recommended actions."
        )
        brief.closing_brand_line = f"{company_label} · {document_type}"
    return brief
