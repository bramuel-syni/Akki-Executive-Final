"""AKKI Solve · cluster taxonomy v1.

Iter61 — Wave 1 of the Solve module. Clusters are the 12 archetypal
board-grade problems Solve walks the user through. Stored in MongoDB so
adding cluster #13 is an admin task, not a code deploy (per iter58
pushback 4).

Each cluster ships with:
  - id, label, blurb (UI surface)
  - phase prompts (Surface / Depth / Synthesis / Lock-in)
  - banned terms (per-cluster jargon to avoid)
  - example_question (helper to let the user click a prompt instead of typing)

This module is the SOURCE OF TRUTH at server boot. The startup hook
upserts these into `solve_clusters`; admins can edit individual fields
in MongoDB without redeploying. Re-running the seed on boot only
inserts missing clusters and DOES NOT overwrite existing ones — so any
operator edits survive a server restart.
"""
from __future__ import annotations

from typing import Any, Dict, List


SOLVE_CLUSTERS_V1: List[Dict[str, Any]] = [
    {
        "id": "revenue_underperformance",
        "label": "Revenue is underperforming and we're not sure why",
        "blurb": "The number is missing. The story isn't holding up. The room is hesitant to name the cause.",
        "example_question": "Q3 revenue missed by 18%. The CEO blames the macro. Two of us think it's pricing. We can't agree what to ask for next month.",
        "phase_hints": {
            "surface": "Help the user name the gap precisely — what's missing vs what was promised, and the timeframe. Avoid 'why' until Depth.",
            "depth": "Pressure-test the framing. Is it volume, price, or mix? Is the comparison fair? What did each party agree the leading indicator would be?",
            "synthesis": "Diagnose: which of (pricing / mix / channel / segment / macro) is most likely the actual driver, grounded in what the user described. Triangulate against comparable diagnoses.",
            "lockin": "Three commitments: what they ask for at the next exec session; what they'll watch in the next 60 days; what they walk into the next conversation with.",
        },
        "banned_terms": ["synergy", "leverage", "double-click", "north star", "ramping"],
    },
    {
        "id": "ceo_succession",
        "label": "Succession isn't ready and the room knows it",
        "blurb": "The succession plan looks tidy on paper. Nobody around the table believes it.",
        "example_question": "The CEO has flagged retirement in 18 months. Our nominated successor isn't tested. The board chair won't say it openly.",
        "phase_hints": {
            "surface": "Name the gap between the documented succession and the actual readiness. No politics yet.",
            "depth": "Test for: who has been tested at scale, who has board exposure, what the development gap actually is, who is willing to speak the gap.",
            "synthesis": "Diagnose: is this a readiness problem, a willingness problem, or a governance problem? Triangulate against comparable boards.",
            "lockin": "Three commitments — what the audit/nom-co will say, what development the successor needs in the next 90 days, what the chair commits to in writing.",
        },
        "banned_terms": ["talent pipeline", "high-potential", "growth journey", "stretch role"],
    },
    {
        "id": "strategy_drift",
        "label": "The strategy on the wall isn't the strategy being executed",
        "blurb": "What the deck says we're doing and what each function is actually doing have diverged.",
        "example_question": "We're 18 months into a 3-year strategy. Three of the four functions are running their own thing. The CEO insists we're aligned.",
        "phase_hints": {
            "surface": "Where exactly did execution diverge from intent? One sentence per function.",
            "depth": "Test for: was the strategy operationally translated, were goals cascaded, were trade-offs made visible? Is this a comprehension problem or a permission problem?",
            "synthesis": "Diagnose: comprehension / capability / commitment / contradiction (between board ask and real constraints).",
            "lockin": "Three commitments — what's reaffirmed, what's quietly retired, what the board agrees to stop asking for.",
        },
        "banned_terms": ["alignment", "transformation", "journey", "doubling down"],
    },
    {
        "id": "risk_blindspot",
        "label": "There's a risk the room knows about and isn't naming",
        "blurb": "The risk register doesn't reflect the conversation in the corridor before the meeting.",
        "example_question": "We all know our largest customer is shopping us. It's not on the risk register. Audit chair won't escalate without 'evidence'.",
        "phase_hints": {
            "surface": "Name the unspoken risk in one sentence. What would happen if it materialised in 90 days?",
            "depth": "Test for: signal strength, governance pathway, who has standing to raise it, what evidence threshold the board has set elsewhere.",
            "synthesis": "Diagnose: is this an evidence gap, a courage gap, a process gap, or a board-chair-must-act moment?",
            "lockin": "Three commitments — what's added to the next risk paper, who escalates and how, what the chair commits to.",
        },
        "banned_terms": ["risk appetite", "low likelihood", "manageable", "noted"],
    },
    {
        "id": "performance_management",
        "label": "Senior performance is ambiguous and we keep deferring",
        "blurb": "The exec isn't clearly failing — but isn't clearly succeeding either. The board has deferred a real conversation for two cycles.",
        "example_question": "Our COO is 14 months in. Some KPIs are missed; some aren't. The CEO defends them. Two NEDs think we should act.",
        "phase_hints": {
            "surface": "Where exactly is the gap — outputs, outcomes, behaviours, or fit?",
            "depth": "Pressure-test: were goals legible, was support given, has the CEO done their part?",
            "synthesis": "Diagnose: is this a goals problem, a development problem, a CEO accountability problem, or a fit problem?",
            "lockin": "Three commitments — what changes in the next 60 days, what the chair commits to in 1:1, what triggers escalation.",
        },
        "banned_terms": ["alignment", "calibration", "performance journey"],
    },
    {
        "id": "capital_allocation",
        "label": "Capital is being deployed without the room agreeing it should be",
        "blurb": "The allocation looks defensible in isolation. Cumulatively the board didn't sign up for this shape.",
        "example_question": "We've approved three M&A deals in 11 months. The thesis for each made sense. Looking at them together, no NED can articulate the strategy they describe.",
        "phase_hints": {
            "surface": "Describe the cumulative shape of capital allocation in plain English.",
            "depth": "Test for: was each decision made against a stated rule, has the rule changed without a vote, what would a sceptical analyst write?",
            "synthesis": "Diagnose: is this a discipline problem, a strategy problem, or a governance problem?",
            "lockin": "Three commitments — what the board ratifies, what's paused, what becomes a standing agenda item.",
        },
        "banned_terms": ["accretive", "value creation", "synergy", "war chest"],
    },
    {
        "id": "regulatory_change",
        "label": "Regulation is changing and we're not sure we're ahead",
        "blurb": "The regulator's posture has shifted. Our response is in PowerPoint. Real readiness is uncertain.",
        "example_question": "A new regulatory framework lands in 9 months. Our compliance officer says we're ready. Two of us spent time with peers and aren't convinced.",
        "phase_hints": {
            "surface": "Name what specifically changes and what specifically the firm has done.",
            "depth": "Test for: who owns each control, has it been tested under load, what would the regulator find on a Tuesday?",
            "synthesis": "Diagnose: paper readiness vs operational readiness, and which gap the board can actually close.",
            "lockin": "Three commitments — what gets tested before go-live, what's escalated to the regulator early, what the audit committee commits to.",
        },
        "banned_terms": ["compliant", "robust", "fit-for-purpose"],
    },
    {
        "id": "tech_debt_or_outage",
        "label": "Tech is fragile and the board can't get a straight answer",
        "blurb": "Outages are growing. The CTO presents progress decks. NEDs lack the language to challenge them.",
        "example_question": "We've had three outages in six months. Each was 'unrelated'. Our CTO is excellent. I can't tell if we're getting better or worse.",
        "phase_hints": {
            "surface": "Describe the pattern, not any single outage. What's the trend the board can see?",
            "depth": "Test for: is reliability a strategic budget line, are there leading indicators on the board pack, who's accountable for each system?",
            "synthesis": "Diagnose: investment problem / talent problem / accountability problem / architecture problem.",
            "lockin": "Three commitments — what becomes a standing reliability metric, what level of incident triggers a board-level review, what the CTO commits to.",
        },
        "banned_terms": ["resilience journey", "tech debt", "modernization"],
    },
    {
        "id": "people_conduct",
        "label": "There's a conduct issue and the board doesn't know how to handle it",
        "blurb": "An incident has surfaced. The room is conflicted between protecting the business and doing what's right.",
        "example_question": "An anonymous letter arrived describing conduct by a named exec. The chair has it. We're meeting in 11 days. None of us are aligned on response.",
        "phase_hints": {
            "surface": "State the facts as the board has them — separating allegation, evidence, and inference.",
            "depth": "Test for: who has investigated, what the policy actually says, what the firm has done in comparable cases.",
            "synthesis": "Diagnose: is this an investigation question, a precedent question, a culture question, or a chair-must-act moment? Be calm, no inference beyond evidence.",
            "lockin": "Three commitments — process the chair runs, what's documented, what the board itself commits to (e.g. external counsel, special committee).",
        },
        "banned_terms": ["regrettable", "isolated incident", "no further action", "moving on"],
    },
    {
        "id": "ma_thesis",
        "label": "An M&A deal is on the table and the room is being polite",
        "blurb": "The deck is good. The thesis is plausible. Nobody around the table is asking the question that matters.",
        "example_question": "We're being asked to approve a $300m acquisition next month. The thesis is sound. I can't articulate why I'm uneasy.",
        "phase_hints": {
            "surface": "Name the unease. One sentence. No business-speak.",
            "depth": "Test for: integration capacity / cultural fit / cash-flow timing / management depth. Where's the unrehearsed question?",
            "synthesis": "Diagnose: is the unease a thesis problem, an execution problem, a timing problem, or a governance problem?",
            "lockin": "Three commitments — what's asked of management before approval, what conditions sit on the resolution, what the board accepts as kill criteria.",
        },
        "banned_terms": ["accretive", "synergies", "cultural alignment", "step-change"],
    },
    {
        "id": "board_dynamics",
        "label": "The board isn't functioning and we're not naming it",
        "blurb": "Discussions are circular. Decisions don't stick. The chair is good but the room isn't.",
        "example_question": "We've debated the same strategic question across three meetings. The same NED dominates. The chair won't redirect. We are not deciding.",
        "phase_hints": {
            "surface": "Describe the dysfunction in one sentence. What's repeating?",
            "depth": "Test for: skills mix, agenda discipline, chair behaviour, exec-NED contract, what the last evaluation actually said.",
            "synthesis": "Diagnose: composition / chairing / process / contract — which is the binding constraint?",
            "lockin": "Three commitments — what the SID/chair commits to, what the next evaluation will measure, what the board asks itself in 90 days.",
        },
        "banned_terms": ["board journey", "alignment", "engagement"],
    },
    {
        "id": "founder_transition",
        "label": "Founder transition isn't going to plan",
        "blurb": "The founder is technically stepping back. Decisions still flow through them. The professional CEO is being undermined politely.",
        "example_question": "Our founder-chair stepped back 14 months ago. Three of the last six material decisions were re-litigated by them. Our CEO is patient but tiring.",
        "phase_hints": {
            "surface": "Describe the pattern of how decisions actually flow. Who calls whom?",
            "depth": "Test for: was the transition contractually defined, who has standing to enforce it, what are the founder's stated triggers for re-engagement?",
            "synthesis": "Diagnose: contract problem / culture problem / governance problem / role-design problem.",
            "lockin": "Three commitments — what the chair commits to, what the founder commits to in writing, what triggers a formal renegotiation of the role.",
        },
        "banned_terms": ["legacy", "stewardship journey", "evolution"],
    },
]


async def seed_solve_clusters(db) -> Dict[str, Any]:
    """Idempotent — only inserts clusters that don't already exist by id.
    Operator edits in MongoDB survive a redeploy."""
    inserted = []
    for c in SOLVE_CLUSTERS_V1:
        existing = await db.solve_clusters.find_one({"id": c["id"]}, {"_id": 0, "id": 1})
        if existing:
            continue
        await db.solve_clusters.insert_one({**c})
        inserted.append(c["id"])
    return {"seeded_count": len(inserted), "ids": inserted}
