"""Sandbox service — parameterised template seeding for pre-auth evaluation.

A prospect answers 4 questions (company, sector, role, region); we pick a
template, substitute their answers into every artefact, and seed a fully
populated context they can explore for 14 days.

Phase 1 scope: ONE well-crafted template (banking / financial services),
plus a generic fallback. Additional sector templates (SaaS, logistics,
healthcare, etc.) ship in a later sprint.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple


Sector = Literal[
    "financial_services", "saas", "logistics", "healthcare",
    "manufacturing", "retail", "real_estate", "other",
]

Role = Literal["ned", "executive", "both"]

Region = Literal[
    "east_africa", "west_africa", "southern_africa", "north_africa",
    "europe", "north_america", "middle_east", "asia_pacific",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.isoformat()


# ---------------------------------------------------------------------------
# Region → currency + regulator profile (drives substitutions in copy)
# ---------------------------------------------------------------------------
REGION_PROFILES: Dict[str, Dict[str, Any]] = {
    "east_africa": {
        "currency_code": "KES", "currency_label": "KSh",
        "primary_country": "Kenya",
        "regulators": {
            "financial_services": "Central Bank of Kenya (CBK)",
            "saas": "Kenya ICT Authority",
            "default": "Capital Markets Authority",
        },
    },
    "west_africa": {
        "currency_code": "NGN", "currency_label": "₦",
        "primary_country": "Nigeria",
        "regulators": {
            "financial_services": "Central Bank of Nigeria (CBN)",
            "default": "SEC Nigeria",
        },
    },
    "southern_africa": {
        "currency_code": "ZAR", "currency_label": "R",
        "primary_country": "South Africa",
        "regulators": {
            "financial_services": "South African Reserve Bank (SARB)",
            "default": "FSCA",
        },
    },
    "north_africa": {
        "currency_code": "EGP", "currency_label": "E£",
        "primary_country": "Egypt",
        "regulators": {"default": "Central Bank of Egypt"},
    },
    "europe": {
        "currency_code": "EUR", "currency_label": "€",
        "primary_country": "United Kingdom",
        "regulators": {
            "financial_services": "Financial Conduct Authority (FCA)",
            "default": "FCA",
        },
    },
    "north_america": {
        "currency_code": "USD", "currency_label": "$",
        "primary_country": "United States",
        "regulators": {
            "financial_services": "OCC / Federal Reserve",
            "default": "SEC",
        },
    },
    "middle_east": {
        "currency_code": "AED", "currency_label": "AED",
        "primary_country": "UAE",
        "regulators": {"default": "Securities and Commodities Authority"},
    },
    "asia_pacific": {
        "currency_code": "SGD", "currency_label": "S$",
        "primary_country": "Singapore",
        "regulators": {
            "financial_services": "Monetary Authority of Singapore (MAS)",
            "default": "MAS",
        },
    },
}


def _regulator_for(region: str, sector: str) -> str:
    prof = REGION_PROFILES.get(region) or REGION_PROFILES["east_africa"]
    regs = prof.get("regulators") or {}
    return regs.get(sector) or regs.get("default") or "the primary regulator"


def _currency_for(region: str) -> str:
    prof = REGION_PROFILES.get(region) or REGION_PROFILES["east_africa"]
    return prof.get("currency_label") or "$"


# ---------------------------------------------------------------------------
# Sector → template id (determines which artefact library we parameterise)
# ---------------------------------------------------------------------------
SECTOR_TO_TEMPLATE: Dict[str, str] = {
    "financial_services": "banking_midcap",
    "saas":               "saas_growth",
    "logistics":          "logistics_panafrican",
    "healthcare":         "healthcare_provider",
    "manufacturing":      "manufacturing_industrial",
    "retail":             "retail_multicategory",
    "real_estate":        "real_estate_developer",
    "other":              "generic_diversified",
}


# ---------------------------------------------------------------------------
# Streaming generation narrative — 10 stages with substitutions
# Each stage has a headline + 1-3 italic sublines that reveal one-by-one
# (serif streaming aesthetic — the "hybrid code-stream" look the user picked).
# ---------------------------------------------------------------------------
STREAMING_STAGES = [
    # (min_ms, max_ms, headline, sublines[])
    (0,     4000,  "Preparing your environment…",
        ["Building your data blocks.",
         "Setting up your avatar so AKKI hosts the chat — your raw identity never reaches the model."]),
    (4000,  10000, "Creating your avatar profile.",
        ["AKKI never sees raw identifiers — your avatar is the layer that keeps it that way.",
         "You'll be able to talk to GPT, Claude and Gemini through one secure surface."]),
    (10000, 16000, "Building {company_name} — a fictional {sector_label} group based in {region_label}.",
        ["Adding committees, cadences, and the right regulator references.",
         "Picking peer companies for benchmark comparisons."]),
    (16000, 24000, "Generating 12 months of realistic operational data…",
        ["Quarterly numbers, audit findings, internal memos.",
         "Wiring AKKI's email handle so it can send checklists and receive responses on your behalf."]),
    (24000, 30000, "Constructing recent board papers and management reports…",
        ["Board pack, management commentary, risk register.",
         "Drafted in a tone you'll recognise from real meetings."]),
    (30000, 36000, "Synisense is verifying the data signals before AKKI sees them.",
        ["A separate model counterchecks every claim — sources verified, hallucinations flagged.",
         "Only what survives validation reaches your brief."]),
    (36000, 42000, "AKKI is reading the pack and surfacing observations worth your attention…",
        ["Looking for risks, opportunities, and gaps in the narrative.",
         "Anchoring each observation to the source paragraph."]),
    (42000, 48000, "Finding cross-board patterns relevant to a {role_label} in {sector_label}…",
        ["What would a sharp committee chair pick up first?",
         "Sequencing the observations so the constructive points land before the concerns."]),
    (48000, 54000, "Preparing your first briefing.",
        ["Drafting the opening paragraph in your voice.",
         "Each section will carry the 'Validated by an independent model' mark."]),
    (54000, 60000, "Ready. Taking you in.",
        ["Your environment is live.",
         "AKKI has read the pack. The first brief is on the home screen."]),
]


def resolve_stage_texts(intake: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Render the 10 stage strings (headline + sublines) with the prospect's
    intake substituted in. Each stage carries its own dwell window so the
    frontend can pace the streaming reveal.
    """
    company_name = (intake.get("company_name") or "Your Company").strip()
    sector = intake.get("sector") or "other"
    region = intake.get("region") or "east_africa"
    role = intake.get("role") or "executive"

    sector_label = {
        "financial_services": "financial services",
        "saas": "SaaS / technology",
        "logistics": "logistics and supply chain",
        "healthcare": "healthcare",
        "manufacturing": "manufacturing",
        "retail": "retail and consumer",
        "real_estate": "real estate",
        "other": (intake.get("other_sector_name") or "diversified").strip() or "diversified",
    }.get(sector, "diversified")

    region_label = (REGION_PROFILES.get(region) or {}).get("primary_country") or "Kenya"
    role_label = {
        "ned": "non-executive director",
        "executive": "CEO / operating executive",
        "both": "dual-role leader",
    }.get(role, "leader")

    ctx = {
        "company_name": company_name,
        "sector_label": sector_label,
        "region_label": region_label,
        "role_label": role_label,
    }

    def fmt(s: str) -> str:
        try:
            return s.format(**ctx)
        except (KeyError, IndexError):
            return s

    stages = []
    for idx, (min_ms, max_ms, head_tmpl, sub_tmpls) in enumerate(STREAMING_STAGES):
        stages.append({
            "index": idx,
            "min_ms": min_ms,
            "max_ms": max_ms,
            "text": fmt(head_tmpl),               # legacy alias
            "headline": fmt(head_tmpl),
            "sublines": [fmt(s) for s in (sub_tmpls or [])],
        })
    return stages


# ---------------------------------------------------------------------------
# Template: banking_midcap (Phase 1's polished one, derived from Tuli dataset)
# ---------------------------------------------------------------------------
BANKING_TEMPLATE = {
    "id": "banking_midcap",
    "label": "Mid-cap financial services group",
    "context_type": "executive_enterprise",  # sandbox type overlay in create_sandbox
    "industry": "banking",
    "sector_hint": "Multi-vehicle (banking, asset management, insurance, fintech)",
    "committees": [
        {"name": "Audit Committee", "type": "audit", "cadence": "Quarterly",
         "focus": "Provisioning, capital, regulatory reporting, audit findings"},
        {"name": "Risk Committee", "type": "risk", "cadence": "Quarterly",
         "focus": "Credit, liquidity, operational risk, cyber"},
        {"name": "Nominations Committee", "type": "nominations", "cadence": "Biannual",
         "focus": "Board composition, executive succession"},
    ],
    # Each doc is a compact extract — plenty to let AKKI feel "grounded"
    "documents": [
        {
            "name": "Board Pack Q4",
            "description": "CEO's opening, financial overview, provisioning narrative, risk updates.",
            "mime_type": "application/pdf",
            "extracted_text": (
                "{company_name} — Board Pack Q4\n\n"
                "CEO's opening. The period closed with loan book growth of 22% year-on-year, "
                "concentrated in the SME segment. Non-performing loans rose from 3.2% to 6.0%, "
                "while loan-loss coverage fell from 74% to 44% over the same window. Headline "
                "profitability remains strong at a net interest margin of 7.8%, but the gap "
                "between reported profit and normalised provisions is widening.\n\n"
                "Financial overview. Total assets {currency}840B, deposits {currency}602B, "
                "net interest income up 11%. Capital adequacy at 15.4% — above the {regulator} "
                "minimum but down 180 bps from year-end.\n\n"
                "Audit and risk. Audit Committee has asked management to expand the provisioning "
                "note in the next pack, including sector concentration and staging movements. "
                "Risk Committee raised the issue of top-20 depositor concentration, now at "
                "24.0% of total deposits (vs 17.8% a year ago)."
            ),
            "data_trust": "trusted",
        },
        {
            "name": "Management Commentary — Treasury",
            "description": "Internal memo on treasury retention, funding mix, and attrition.",
            "mime_type": "application/pdf",
            "extracted_text": (
                "Treasury Department — Quarterly Commentary\n\n"
                "Retention. Treasury staff attrition rose to 16.5% in the trailing twelve "
                "months, compared with 9.2% bank-wide. No internal successor has been groomed "
                "for the Head of Treasury role — an informal concern flagged to the Nominations "
                "Committee. Market benchmarking shows {company_name} compensation trailing "
                "peers by 18–22% at senior treasury level.\n\n"
                "Funding. Wholesale funding now 34% of liabilities (vs 29% a year ago). "
                "Concentration in the top-20 depositor segment is the binding constraint."
            ),
            "data_trust": "mixed",
        },
        {
            "name": "Risk Committee Minutes — Q4",
            "description": "Minutes of the Risk Committee discussion on cyber and credit.",
            "mime_type": "application/pdf",
            "extracted_text": (
                "Risk Committee Minutes — Q4\n\n"
                "1. Cyber exposure during core-banking migration. Dual-systems running. "
                "Last penetration test completed nine months ago. Management to present a "
                "remediation update at the next meeting.\n"
                "2. Provisioning staging. Stage-2 loans rose from {currency}8.4B to {currency}14.9B. "
                "Committee asked for a waterfall from Stage-2 to Stage-3 in the next pack.\n"
                "3. Country exposure. 5 operating countries; no consolidated FX hedging "
                "summary was tabled. Committee requested one for the next meeting."
            ),
            "data_trust": "trusted",
        },
    ],
    # Seeded signals — pre-generated, no LLM call needed
    "signals": [
        {
            "type": "risk",
            "headline": "Loan-loss coverage fell from 74% to 44% while NPLs doubled to 6.0%.",
            "reasoning": (
                "Provisions have not kept pace with the shift in loan quality. The Audit "
                "Committee should ask for a Stage-2 to Stage-3 waterfall and sector "
                "concentration."
            ),
            "evidence_text": "[doc:0] Loan-loss coverage fell from 74% to 44%. NPLs rose from 3.2% to 6.0%.",
            "confidence": "high",
            "data_trust": "trusted",
        },
        {
            "type": "risk",
            "headline": "Top-20 depositor concentration rose from 17.8% to 24.0%.",
            "reasoning": (
                "Funding has quietly become more concentrated. Risk Committee should map "
                "depositor behaviour under stress and consider a limit."
            ),
            "evidence_text": "[doc:0] Top-20 depositor concentration rose from 17.8% to 24.0% of total deposits.",
            "confidence": "high",
            "data_trust": "trusted",
        },
        {
            "type": "gap",
            "headline": "Treasury attrition hit 16.5% and no internal successor is in training.",
            "reasoning": (
                "Key-person risk at the funding engine. Nominations Committee should close "
                "the succession gap before the next cycle."
            ),
            "evidence_text": "[doc:1] Treasury staff attrition rose to 16.5% and no internal successor has been groomed.",
            "confidence": "medium",
            "data_trust": "mixed",
        },
        {
            "type": "risk",
            "headline": "Cyber exposure during core-banking migration remains unquantified.",
            "reasoning": (
                "Dual systems running; last pen-test nine months old. Risk Committee flagged "
                "this and management has not yet tabled a remediation update."
            ),
            "evidence_text": "[doc:2] Dual-systems running. Last penetration test completed nine months ago.",
            "confidence": "high",
            "data_trust": "trusted",
        },
        {
            "type": "gap",
            "headline": "5 operating countries with no consolidated FX hedging summary.",
            "reasoning": (
                "Country exposure framework is opaque. Risk Committee has asked; worth "
                "raising again if the next pack does not include it."
            ),
            "evidence_text": "[doc:2] 5 operating countries; no consolidated FX hedging summary was tabled.",
            "confidence": "medium",
            "data_trust": "trusted",
        },
        {
            "type": "opportunity",
            "headline": "Net interest margin at 7.8% remains strong — use it to accelerate provisioning.",
            "reasoning": (
                "Profitability gives room to re-base provisions without bruising the P&L. "
                "Audit Committee can frame this positively."
            ),
            "evidence_text": "[doc:0] Net interest margin of 7.8% — headline profitability remains strong.",
            "confidence": "medium",
            "data_trust": "trusted",
        },
    ],
    # One pre-composed briefing
    "briefings": [
        {
            "title": "For the next Audit Committee — what to raise",
            "opening_paragraph": (
                "{company_name}'s Q4 pack shows healthy headline profitability, but two "
                "undercurrents warrant the committee's attention before next quarter: "
                "provisioning has not kept pace with NPL growth, and deposit funding has "
                "quietly become more concentrated."
            ),
            "closing_note": (
                "Three items for the chair: the Stage-2 to Stage-3 waterfall, the top-20 "
                "depositor limit discussion, and the treasury succession plan."
            ),
        },
    ],
}


# Generic fallback template — simple enough to make "Other" sectors feel live
GENERIC_TEMPLATE = {
    "id": "generic_diversified",
    "label": "Diversified holding",
    "context_type": "executive_enterprise",
    "industry": "other",
    "sector_hint": "Diversified",
    "committees": [
        {"name": "Audit Committee", "type": "audit", "cadence": "Quarterly",
         "focus": "Financial reporting, internal controls"},
        {"name": "Risk Committee", "type": "risk", "cadence": "Quarterly",
         "focus": "Strategic risk, operational risk"},
    ],
    "documents": [
        {
            "name": "Board Pack Q4",
            "description": "Period headline, strategy update, risk summary.",
            "mime_type": "application/pdf",
            "extracted_text": (
                "{company_name} — Board Pack Q4\n\n"
                "Executive summary. Revenue of {currency}312m, up 14% on prior year. "
                "EBITDA margin compressed from 22% to 18.5% driven by input costs. "
                "Operating cash flow {currency}58m.\n\n"
                "Strategy. Three-year plan on track; expansion into a second market "
                "delayed by one quarter due to regulatory engagement with {regulator}.\n\n"
                "Risk. Customer concentration at 34% of revenue (top-5). Cyber incident "
                "in Q3 contained; root cause attributed to a contractor endpoint."
            ),
            "data_trust": "trusted",
        },
    ],
    "signals": [
        {
            "type": "risk",
            "headline": "EBITDA margin compressed from 22% to 18.5% — the board should probe input costs.",
            "reasoning": "Margin erosion is meaningful but not explained in the narrative.",
            "evidence_text": "[doc:0] EBITDA margin compressed from 22% to 18.5% driven by input costs.",
            "confidence": "high",
            "data_trust": "trusted",
        },
        {
            "type": "risk",
            "headline": "Customer concentration of 34% in top-5 warrants a mitigation plan.",
            "reasoning": "Classic exit-risk pattern. Ask for a diversification roadmap.",
            "evidence_text": "[doc:0] Customer concentration at 34% of revenue (top-5).",
            "confidence": "medium",
            "data_trust": "trusted",
        },
        {
            "type": "opportunity",
            "headline": "Revenue up 14% — plenty of room to invest in margin recovery.",
            "reasoning": "Growth continues; the board can support a deliberate margin pass.",
            "evidence_text": "[doc:0] Revenue of {currency}312m, up 14% on prior year.",
            "confidence": "medium",
            "data_trust": "trusted",
        },
    ],
    "briefings": [
        {
            "title": "For the next board meeting — three themes",
            "opening_paragraph": (
                "{company_name}'s most recent pack balances strong top-line growth with "
                "margin pressure and emerging concentration risks. Three themes warrant "
                "framing by the chair before the meeting."
            ),
            "closing_note": "Input costs, customer concentration, and the pace of the second-market launch.",
        },
    ],
}


TEMPLATES: Dict[str, Dict[str, Any]] = {
    "banking_midcap": BANKING_TEMPLATE,
    "generic_diversified": GENERIC_TEMPLATE,
}

# Merge in the sector templates from the dedicated file. They each define
# id/industry/sector_hint/committees/documents/signals/briefings with
# {company_name}/{currency}/{regulator} substitutions.
try:
    from sandbox_templates import ALL_TEMPLATES as _EXTRA_TEMPLATES
    for _tid, _t in _EXTRA_TEMPLATES.items():
        # Default context_type for sandbox contexts created from these templates
        _t.setdefault("context_type", "executive_enterprise")
        TEMPLATES[_tid] = _t
except Exception as _tpl_err:  # pragma: no cover
    # Fallback: Phase 2 templates are a "nice to have" — if the import fails,
    # sector-specific sandboxes fall through to the generic template. We log
    # the exception so a syntax error in sandbox_templates.py doesn't silently
    # degrade the sandbox experience.
    import logging as _l
    _l.getLogger("akki.sandbox").warning(
        f"sandbox_templates import failed, falling back to generic only: {_tpl_err!r}"
    )


def pick_template(sector: str) -> Dict[str, Any]:
    tid = SECTOR_TO_TEMPLATE.get(sector) or "generic_diversified"
    return TEMPLATES.get(tid) or GENERIC_TEMPLATE


def substitute(text: str, *, company_name: str, currency: str, regulator: str) -> str:
    return (text or "").format(
        company_name=company_name,
        currency=currency,
        regulator=regulator,
    )


def build_seed_payload(
    *, context_id: str, template: Dict[str, Any], intake: Dict[str, Any],
    owner_account_id: str,
) -> Dict[str, List[Dict[str, Any]]]:
    """Return {documents, signals, briefings} ready to `insert_many` into Mongo.

    Each artefact is fully parameterised with the prospect's intake answers.
    """
    company_name = (intake.get("company_name") or "Your Company").strip()
    sector = intake.get("sector") or "other"
    region = intake.get("region") or "east_africa"
    currency = _currency_for(region)
    regulator = _regulator_for(region, sector)

    def sub(s: str) -> str:
        return substitute(s, company_name=company_name, currency=currency, regulator=regulator)

    now_dt = _now()

    # ---- documents ----
    docs: List[Dict[str, Any]] = []
    for idx, d in enumerate(template["documents"]):
        docs.append({
            "id": str(uuid.uuid4()),
            "context_id": context_id,
            "name": sub(d["name"]),
            "description": sub(d.get("description", "")),
            "original_filename": f'{sub(d["name"]).replace(" ", "_").lower()}.pdf',
            "mime_type": d.get("mime_type", "application/pdf"),
            "size_bytes": len(d["extracted_text"]),
            "storage_key": None,
            "status": "extracted",
            "extracted_text": sub(d["extracted_text"]),
            "extracted_chars": len(d["extracted_text"]),
            "preview": sub(d["extracted_text"])[:280],
            "data_trust": d.get("data_trust", "mixed"),
            "uploaded_by": owner_account_id,
            "uploaded_by_email": None,
            "mentioned_account_ids": [],
            "related_doc_id": None,
            "relation_type": None,
            "error": None,
            "created_at": _iso(now_dt - timedelta(hours=24 - idx)),
            "updated_at": _iso(now_dt - timedelta(hours=24 - idx)),
            "sandbox_artefact": True,
        })

    # Map doc indexes (used in template's [doc:0] tokens) to real ids
    doc_id_by_idx = {i: docs[i]["id"] for i in range(len(docs))}

    def resolve_doc_refs(s: str) -> str:
        out = s
        for i, real_id in doc_id_by_idx.items():
            out = out.replace(f"[doc:{i}]", f"[doc:{real_id}]")
        return out

    # ---- signals ----
    sigs: List[Dict[str, Any]] = []
    for idx, s in enumerate(template["signals"]):
        sig_id = str(uuid.uuid4())
        evidence = resolve_doc_refs(sub(s["evidence_text"]))
        sources = [
            {"doc_id": doc_id_by_idx[i], "doc_name": docs[i]["name"], "data_trust": docs[i]["data_trust"]}
            for i in doc_id_by_idx
            if f"[doc:{i}]" in s["evidence_text"]
        ]
        sigs.append({
            "id": sig_id,
            "context_id": context_id,
            "type": s["type"],
            "headline": sub(s["headline"]),
            "reasoning": sub(s["reasoning"]),
            "evidence": evidence,
            "sources": sources,
            "confidence": s.get("confidence", "medium"),
            "data_trust": s.get("data_trust", "mixed"),
            "status": "active",
            "created_by": owner_account_id,
            "created_at": _iso(now_dt - timedelta(minutes=30 - idx * 2)),
            "sandbox_artefact": True,
        })

    # ---- briefings ----
    briefs: List[Dict[str, Any]] = []
    for bidx, b in enumerate(template["briefings"]):
        # Pull the first 3 signals into items so the briefing feels anchored
        items = []
        for i, sig in enumerate(sigs[:3]):
            items.append({
                "signal_id": sig["id"],
                "signal_headline": sig["headline"],
                "signal_type": sig["type"],
                "confidence": sig["confidence"],
                "evidence": sig["evidence"],
                "question": f"How are we mitigating: {sig['headline']}?",
                "sources": sig["sources"],
            })
        briefs.append({
            "id": str(uuid.uuid4()),
            "context_id": context_id,
            "title": sub(b["title"]),
            "opening_paragraph": sub(b["opening_paragraph"]),
            "items": items,
            "closing_note": sub(b["closing_note"]),
            "signal_ids": [sig["id"] for sig in sigs[:3]],
            "source_doc_ids": [docs[i]["id"] for i in doc_id_by_idx],
            "version": 1,
            "mode": "seeded",
            "shielding_masked": 0,
            "shielding": {"identifiers_masked": 0, "by_category": {}, "shielded_by": "sandbox-seed"},
            "created_by": owner_account_id,
            "created_at": _iso(now_dt - timedelta(minutes=10)),
            "status": "active",
            "sandbox_artefact": True,
        })

    return {"documents": docs, "signals": sigs, "briefings": briefs}


def sandbox_expiry_defaults() -> Tuple[datetime, datetime, datetime]:
    """Return (expires_at, read_only_until, hard_delete_at) per spec.

    - 14 days active
    - +7 days read-only grace period (days 14–21)
    - +1 day buffer then hard delete at day 22
    """
    now_dt = _now()
    expires_at = now_dt + timedelta(days=14)
    read_only_until = expires_at + timedelta(days=7)
    hard_delete_at = read_only_until + timedelta(days=1)
    return expires_at, read_only_until, hard_delete_at
