"""Seed POST_T5_BACKLOG demo data — backlog-b chunk.

Closes three seed-data gaps surfaced during the T1–T5 horizontal sprint
(see `/app/memory/sprints/POST_T5_BACKLOG.md`):

  1. T4 gap — at least one Board Pack + one Committee Pack in
     `work_studio_exports` with non-null `structured_content` so the W3
     Compiled-Document toolbar's DOCX/PDF/PPTX download buttons are
     browser-observable end-to-end.
  2. T5 gap — one Cycle Manager cycle with a compiled
     `work_studio_exports.structured_content` (kind=cycle_board_pack)
     so the C5 Cycle Page download click-path is browser-observable.
  3. T2.3 gap — at least one objective + one project carrying
     populated `supporting_docs` (≥ 2 doc refs each) so the Monitor
     drawer Citations Card renders live.

Hard rules
----------
* Idempotent: every row uses a deterministic stable id prefixed
  `demo-t5backlog-` and is written via `update_one(..., upsert=True)`.
  Re-running this script yields a zero count delta.
* Every record carries `seed_marker = "DEMO_T5_BACKLOG"` for clean
  identification and bulk removal later.
* Synthetic content only — no real PII. Display names are `[DEMO]`-
  prefixed; emails (where applicable to ancillary rows) use
  `@example.com`.
* No deletions. Only inserts and upserts.

Run
---
    cd /app/backend && python -m scripts.seed_backlog_b_demo
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

SEED_MARKER = "DEMO_T5_BACKLOG"

# Deterministic IDs (do not change once shipped — these are the
# upsert keys).
BOARD_PACK_ID = "demo-t5backlog-bp-001"
COMMITTEE_PACK_ID = "demo-t5backlog-cp-001"
CYCLE_ID = "demo-t5backlog-cycle-001"
CYCLE_COMPILATION_ID = "demo-t5backlog-cycle-compile-001"
OBJECTIVE_ID = "demo-t5backlog-obj-001"
PROJECT_ID = "demo-t5backlog-prj-001"
# Blocker 2 (2026-05-25, backlog-b) — the cycle linkage shell row in
# `cycle_agendas` must share the cycle's ID so the legacy single-cycle
# endpoints continue to resolve it. The Cycle Page renders only when
# the agenda shell is present alongside the cycles row.
CYCLE_AGENDA_ID = CYCLE_ID

# Bramuel accounts + contexts. These are the live tester accounts
# documented in `/app/memory/test_credentials.md`; seeding here makes
# the e1_tester browser session land on rows it can verify directly.
BRAMUEL_ACCOUNT_ID = "b8d20f47-ad59-4e67-8635-653896d56ff1"
BRAMUEL_NED_TULI_CTX = "5afb0f40-0193-4b7d-abd9-75e620aac3c2"      # "Tuli Financial Group" (NED)
BRAMUEL_EXEC_TULI_CTX = "dcc263b1-59f9-4546-ba6a-ea7c54545b3e"     # "Tuli Financial Group (CFO)" (executive)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# --------------------------------------------------------------------------
# Structured content fixtures — realistic but synthetic.
# --------------------------------------------------------------------------
_BOARD_PACK_SECTIONS: List[Dict[str, Any]] = [
    {
        "heading": "Executive Summary",
        "paragraphs": [
            "[DEMO] Tuli Financial Group closed Q1 2026 with revenue 6.4% ahead of the FY plan, "
            "but net interest margin contracted 84 basis points year over year. The Board is "
            "asked to review three decisions surfaced by management.",
            "Cost-of-risk normalisation has stalled; non-performing loans drifted up 40 basis "
            "points in the quarter. Provisioning policy is under review with the Audit Committee.",
        ],
    },
    {
        "heading": "Decisions Requested",
        "paragraphs": [
            "1. Approve the FY26 capital plan with the additional Tier 2 capacity outlined in "
            "Appendix B (impact: +120 bps headroom on CAR).",
            "2. Ratify the revised Risk Appetite Statement (RAS) — proposed by the Risk Committee "
            "on 18 April 2026.",
            "3. Endorse the rollout of the new credit-decisioning engine to the SME book, with a "
            "30-day post-launch review cadence.",
        ],
    },
    {
        "heading": "Risks & Watch-List",
        "paragraphs": [
            "Funding concentration is moderately elevated — top-20 depositors represent 24.0% of "
            "the funding base (regulatory threshold: 25%). Treasury is targeting a 200 bps "
            "reduction over H1.",
            "Cyber: a single high-severity finding from the May penetration test remains open. "
            "Remediation is on track for end-June.",
        ],
    },
]

_COMMITTEE_PACK_SECTIONS: List[Dict[str, Any]] = [
    {
        "heading": "Audit Committee — Agenda",
        "paragraphs": [
            "[DEMO] Standing items: minutes of the prior meeting, action log, external auditor "
            "interim update, internal audit progress against plan, and the Q1 financial review.",
            "Two committee-specific decisions: (a) approval of the FY26 internal audit plan, and "
            "(b) recommendation to the Board on the provisioning-policy revision.",
        ],
    },
    {
        "heading": "Internal Audit Update",
        "paragraphs": [
            "Year-to-date plan completion: 32% (planned: 35%). Four reports issued this quarter — "
            "one with 'satisfactory' opinion, two with 'requires improvement', one with "
            "'unsatisfactory' (Group Treasury — controls remediation in progress).",
            "Three findings outstanding beyond their target close date. Status reviewed with the "
            "Head of Internal Audit on 14 May.",
        ],
    },
    {
        "heading": "External Auditor — Interim",
        "paragraphs": [
            "No material concerns raised in the interim review. Two areas of audit focus for FY26 "
            "year-end: (1) expected credit loss methodology, (2) revenue recognition on the new "
            "trade-finance product line.",
        ],
    },
]

_CYCLE_COMPILE_SECTIONS: List[Dict[str, Any]] = [
    {
        "heading": "Cycle Summary",
        "paragraphs": [
            "[DEMO] Q2 2026 Tuli Financial Group board cycle. Three agenda items closed: "
            "Strategy update, Q1 financial review, and the FY26 risk appetite refresh.",
            "Six contributors landed inputs ahead of the deadline; one contributor (Group Treasury) "
            "delivered late but inside the readiness window.",
        ],
    },
    {
        "heading": "Decisions Compiled",
        "paragraphs": [
            "FY26 capital plan — recommended for Board approval with the revised Tier 2 capacity.",
            "Revised Risk Appetite Statement — ratified by Risk Committee; recommended for Board "
            "endorsement.",
            "Credit-decisioning engine rollout — endorsed by Strategy Committee with a 30-day "
            "post-launch review cadence.",
        ],
    },
    {
        "heading": "Open Items for Follow-up",
        "paragraphs": [
            "Funding concentration remediation — Treasury action plan due 15 July.",
            "May pen-test finding — remediation due 30 June; Risk Committee to verify closure.",
        ],
    },
]


# --------------------------------------------------------------------------
# Audit helper — uses the existing public write_audit so we don't bypass
# the chain. Imported lazily inside seed_async to avoid pulling the
# rest of the app at script import time.
# --------------------------------------------------------------------------
async def _emit_audit(db, action: str, account_id: str, context_id: str,
                      resource_type: str, resource_id: str,
                      metadata: Dict[str, Any]) -> None:
    try:
        from core import write_audit  # type: ignore
        await write_audit(
            context_id, account_id,
            action, resource_type, resource_id, metadata,
        )
    except Exception:
        # Audit is best-effort during seeding; do not fail the seed if
        # the chain layer rejects synthetic markers.
        pass


# --------------------------------------------------------------------------
# Section 1 — Board Pack + Committee Pack (T4 gap)
# --------------------------------------------------------------------------
async def _seed_board_pack(db) -> Dict[str, Any]:
    """Insert/upsert one Board Pack row into `work_studio_exports`.

    Lifecycle: `committed` — exercises the W5 read-only surface and gives
    the lock-icon overlay something to point at on the listing card.
    """
    now = _now()
    doc = {
        "id": BOARD_PACK_ID,
        "context_id": BRAMUEL_EXEC_TULI_CTX,
        "account_id": BRAMUEL_ACCOUNT_ID,
        "kind": "board_pack",
        "title": "[DEMO] Q1 2026 Tuli Financial Group Board Pack",
        "status": "complete",
        "lifecycle_state": "committed",
        "output_format": "docx",
        "source_document_ids": [],
        "structured_content": {
            "sections": _BOARD_PACK_SECTIONS,
        },
        "sensitivity_band": "CONFIDENTIAL",
        "confidence_score": 88,
        "document_intelligence": {
            "source_doc_count": 3,
            "contributor_count": 4,
            "period_covered": "Q1 2026",
            "confidence_score": 88,
        },
        "committed_at": _iso(now),
        "created_at": _iso(now),
        "updated_at": _iso(now),
        "seed_marker": SEED_MARKER,
    }
    await db.work_studio_exports.update_one(
        {"id": BOARD_PACK_ID}, {"$set": doc}, upsert=True
    )
    await _emit_audit(
        db, "demo.seed.board_pack",
        BRAMUEL_ACCOUNT_ID, BRAMUEL_EXEC_TULI_CTX,
        "work_studio_artefact.board_pack", BOARD_PACK_ID,
        {"seed_marker": SEED_MARKER, "lifecycle_state": "committed"},
    )
    return doc


async def _seed_committee_pack(db) -> Dict[str, Any]:
    """Insert/upsert one Committee Pack row.

    Lifecycle: `draft` — exercises the W3 Refine/Decline/Commit footer
    on first open.
    """
    now = _now()
    doc = {
        "id": COMMITTEE_PACK_ID,
        "context_id": BRAMUEL_EXEC_TULI_CTX,
        "account_id": BRAMUEL_ACCOUNT_ID,
        "kind": "committee_pack",
        "title": "[DEMO] May 2026 Audit Committee Pack",
        "status": "complete",
        "lifecycle_state": "draft",
        "output_format": "docx",
        "source_document_ids": [],
        "structured_content": {
            "sections": _COMMITTEE_PACK_SECTIONS,
        },
        "sensitivity_band": "CONFIDENTIAL",
        "confidence_score": 72,
        "document_intelligence": {
            "source_doc_count": 2,
            "contributor_count": 2,
            "period_covered": "May 2026",
            "confidence_score": 72,
        },
        "created_at": _iso(now),
        "updated_at": _iso(now),
        "seed_marker": SEED_MARKER,
    }
    await db.work_studio_exports.update_one(
        {"id": COMMITTEE_PACK_ID}, {"$set": doc}, upsert=True
    )
    await _emit_audit(
        db, "demo.seed.committee_pack",
        BRAMUEL_ACCOUNT_ID, BRAMUEL_EXEC_TULI_CTX,
        "work_studio_artefact.committee_pack", COMMITTEE_PACK_ID,
        {"seed_marker": SEED_MARKER, "lifecycle_state": "draft"},
    )
    return doc


# --------------------------------------------------------------------------
# Section 2 — Cycle with compiled structured_content (T5 gap)
# --------------------------------------------------------------------------
async def _seed_cycle_and_compilation(db) -> Dict[str, Any]:
    """Seed one Cycle Manager cycle + one matching cycle_board_pack
    `work_studio_exports` row carrying `structured_content`.

    The cycle row uses the existing minimal `cycles` schema:
      {id, context_id, account_id, title, status, created_at,
       activated_at}. A `compiled_brief_id` reference is also written
       so the Cycle Page can detect "already compiled" without forcing
       the user to click Compile.

    The companion work_studio_exports row uses `kind=cycle_board_pack`
    so it is picked up by the same T4.1 render endpoint that the
    Cycle Page download buttons hit (G6 parity).
    """
    now = _now()
    activated = now.replace(microsecond=0)

    cycle_doc = {
        "id": CYCLE_ID,
        "context_id": BRAMUEL_NED_TULI_CTX,
        "account_id": BRAMUEL_ACCOUNT_ID,
        "title": "[DEMO] Q2 2026 Tuli Board Cycle",
        "status": "active",
        "compiled_brief_id": CYCLE_COMPILATION_ID,
        "compilation_export_id": CYCLE_COMPILATION_ID,
        "readiness_pct": 95,
        "readiness_target": 85,
        "created_at": _iso(now),
        "activated_at": _iso(activated),
        "seed_marker": SEED_MARKER,
    }
    await db.cycles.update_one(
        {"id": CYCLE_ID}, {"$set": cycle_doc}, upsert=True
    )

    # Blocker 2 (2026-05-25, backlog-b) — also upsert the matching
    # `cycle_agendas` shell row so the legacy single-cycle endpoints
    # (which the Cycle Page detail surface still reads) can resolve
    # the linkage and the agenda count surfaces correctly. The shell
    # IS the contract for `_persist_agenda_shell` in routers/cycles.py.
    agenda_doc = {
        "id": CYCLE_AGENDA_ID,
        "cycle_id": CYCLE_ID,
        "context_id": BRAMUEL_NED_TULI_CTX,
        "account_id": BRAMUEL_ACCOUNT_ID,
        "title": cycle_doc["title"],
        "items": [
            {"id": "demo-t5backlog-agenda-item-1",
             "title": "[DEMO] Strategy update"},
            {"id": "demo-t5backlog-agenda-item-2",
             "title": "[DEMO] Q1 financial review"},
            {"id": "demo-t5backlog-agenda-item-3",
             "title": "[DEMO] FY26 risk appetite refresh"},
        ],
        "status": "active",
        "created_at": _iso(now),
        "updated_at": _iso(now),
        "seed_marker": SEED_MARKER,
    }
    await db.cycle_agendas.update_one(
        {"id": CYCLE_AGENDA_ID}, {"$set": agenda_doc}, upsert=True
    )

    compile_doc = {
        "id": CYCLE_COMPILATION_ID,
        "context_id": BRAMUEL_NED_TULI_CTX,
        "account_id": BRAMUEL_ACCOUNT_ID,
        "kind": "cycle_board_pack",
        "title": "[DEMO] Q2 2026 Tuli Cycle Compilation",
        "file_name": "demo_q2_2026_tuli_cycle_compilation.docx",
        "status": "complete",
        "lifecycle_state": "in_review",
        "output_format": "docx",
        "source_document_ids": [],
        "source_cycle_id": CYCLE_ID,
        "structured_content": {
            "sections": _CYCLE_COMPILE_SECTIONS,
        },
        "sensitivity_band": "CONFIDENTIAL",
        "confidence_score": 81,
        "document_intelligence": {
            "source_doc_count": 4,
            "contributor_count": 6,
            "period_covered": "Q2 2026",
            "confidence_score": 81,
        },
        "created_at": _iso(now),
        "updated_at": _iso(now),
        "seed_marker": SEED_MARKER,
    }
    await db.work_studio_exports.update_one(
        {"id": CYCLE_COMPILATION_ID}, {"$set": compile_doc}, upsert=True
    )

    await _emit_audit(
        db, "demo.seed.cycle_compilation",
        BRAMUEL_ACCOUNT_ID, BRAMUEL_NED_TULI_CTX,
        "work_studio_artefact.cycle_board_pack", CYCLE_COMPILATION_ID,
        {"seed_marker": SEED_MARKER, "cycle_id": CYCLE_ID},
    )
    return {"cycle": cycle_doc, "compilation": compile_doc}


# --------------------------------------------------------------------------
# Section 3 — Objective + Project with populated supporting_docs (T2.3 gap)
# --------------------------------------------------------------------------
async def _pick_two_real_docs(db, context_id: str) -> List[Dict[str, str]]:
    """Pick two real, already-seeded documents in this context so the
    supporting_docs references do not orphan. We DELIBERATELY do not
    create new documents — the gap is about supporting_docs resolving,
    not about adding more docs.

    Falls back to two synthetic refs only if the context has < 2 docs
    (extremely unlikely for Bramuel's Tuli Financial Group ctx which
    ships with the 14-doc strategic pack mirror).
    """
    cursor = db.documents.find(
        {"context_id": context_id},
        {"_id": 0, "id": 1, "name": 1, "original_filename": 1},
    ).limit(2)
    rows = []
    async for r in cursor:
        rows.append({
            "id": r["id"],
            "name": r.get("name") or r.get("original_filename") or r["id"],
        })
    if len(rows) >= 2:
        return rows
    # Synthetic fallback (shouldn't trigger in the live seeded environment).
    return [
        {"id": "demo-doc-synth-1", "name": "[DEMO] Strategic Plan FY26.pdf"},
        {"id": "demo-doc-synth-2", "name": "[DEMO] Risk Appetite Statement.pdf"},
    ]


async def _seed_objective(db, supporting_docs: List[Dict[str, str]]) -> Dict[str, Any]:
    now = _now()
    obj = {
        "id": OBJECTIVE_ID,
        "context_id": BRAMUEL_NED_TULI_CTX,
        "created_at": _iso(now),
        "updated_at": _iso(now),
        "title": "[DEMO] Reduce funding concentration to ≤ 20% top-20 depositors",
        "description": (
            "Top-20 depositor concentration drifted to 24.0% in Q1 2026. "
            "Reduce to ≤ 20% by end-Q4 through diversification of the "
            "wholesale book and growth in retail deposits."
        ),
        "owner_account_id": BRAMUEL_ACCOUNT_ID,
        "shared_with": [],
        "rag_status": "amber",
        "score": 62,
        "trend": "flat",
        "source": "manual",
        "source_refs": [],
        "last_akki_assessment": {
            "status": "amber",
            "rag_status": "amber",
            "confidence": 0.78,
            "rationale": (
                "[DEMO] Q1 progress is mixed: wholesale concentration eased "
                "70 bps but retail growth is behind plan. Sustained execution "
                "on the diversification programme is required."
            ),
            "supporting_signal_ids": [],
            "supporting_doc_ids": [d["id"] for d in supporting_docs],
            "supporting_docs": supporting_docs,
            "audit_id": "demo-audit-" + OBJECTIVE_ID,
            "assessed_at": _iso(now),
        },
        "seed_marker": SEED_MARKER,
    }
    await db.objectives.update_one(
        {"id": OBJECTIVE_ID}, {"$set": obj}, upsert=True
    )
    return obj


async def _seed_project(db, supporting_docs: List[Dict[str, str]]) -> Dict[str, Any]:
    now = _now()
    prj = {
        "id": PROJECT_ID,
        "context_id": BRAMUEL_NED_TULI_CTX,
        "created_at": _iso(now),
        "updated_at": _iso(now),
        "title": "[DEMO] Credit-decisioning engine — SME rollout",
        "description": (
            "Deploy the new credit-decisioning engine across the SME book by "
            "end-Q3 2026. Targeting a 30-day post-launch review cadence with "
            "the Risk Committee."
        ),
        "owner_account_id": BRAMUEL_ACCOUNT_ID,
        "shared_with": [],
        "rag_status": "green",
        "score": 78,
        "trend": "up",
        "source": "manual",
        "source_refs": [],
        "objective_id": None,
        "timeline_events": [],
        "last_akki_assessment": {
            "status": "green",
            "rag_status": "green",
            "confidence": 0.82,
            "rationale": (
                "[DEMO] Pilot tranche is live and tracking model performance "
                "within tolerance bands. No new findings from the controls "
                "review on 12 May."
            ),
            "supporting_signal_ids": [],
            "supporting_doc_ids": [d["id"] for d in supporting_docs],
            "supporting_docs": supporting_docs,
            "audit_id": "demo-audit-" + PROJECT_ID,
            "assessed_at": _iso(now),
        },
        "seed_marker": SEED_MARKER,
    }
    await db.projects.update_one(
        {"id": PROJECT_ID}, {"$set": prj}, upsert=True
    )
    return prj


# --------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------
async def seed_async(verbose: bool = True) -> Dict[str, Any]:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Pre-count for idempotency observation.
    pre_counts = {
        "work_studio_exports.demo": await db.work_studio_exports.count_documents(
            {"seed_marker": SEED_MARKER}
        ),
        "cycles.demo": await db.cycles.count_documents(
            {"seed_marker": SEED_MARKER}
        ),
        "cycle_agendas.demo": await db.cycle_agendas.count_documents(
            {"seed_marker": SEED_MARKER}
        ),
        "objectives.demo": await db.objectives.count_documents(
            {"seed_marker": SEED_MARKER}
        ),
        "projects.demo": await db.projects.count_documents(
            {"seed_marker": SEED_MARKER}
        ),
    }

    bp = await _seed_board_pack(db)
    cp = await _seed_committee_pack(db)
    cyc_bundle = await _seed_cycle_and_compilation(db)
    supporting_docs = await _pick_two_real_docs(db, BRAMUEL_NED_TULI_CTX)
    obj = await _seed_objective(db, supporting_docs)
    prj = await _seed_project(db, supporting_docs)

    post_counts = {
        "work_studio_exports.demo": await db.work_studio_exports.count_documents(
            {"seed_marker": SEED_MARKER}
        ),
        "cycles.demo": await db.cycles.count_documents(
            {"seed_marker": SEED_MARKER}
        ),
        "cycle_agendas.demo": await db.cycle_agendas.count_documents(
            {"seed_marker": SEED_MARKER}
        ),
        "objectives.demo": await db.objectives.count_documents(
            {"seed_marker": SEED_MARKER}
        ),
        "projects.demo": await db.projects.count_documents(
            {"seed_marker": SEED_MARKER}
        ),
    }

    result = {
        "board_pack_id": bp["id"],
        "committee_pack_id": cp["id"],
        "cycle_id": cyc_bundle["cycle"]["id"],
        "cycle_compilation_id": cyc_bundle["compilation"]["id"],
        "objective_id": obj["id"],
        "project_id": prj["id"],
        "supporting_docs": supporting_docs,
        "pre_counts": pre_counts,
        "post_counts": post_counts,
        "delta": {
            k: post_counts[k] - pre_counts[k] for k in pre_counts
        },
    }

    if verbose:
        print("=" * 72)
        print("BACKLOG-B SEED — DEMO_T5_BACKLOG")
        print("=" * 72)
        print(f"Board Pack            : {result['board_pack_id']}")
        print(f"Committee Pack        : {result['committee_pack_id']}")
        print(f"Cycle                 : {result['cycle_id']}")
        print(f"Cycle Compilation     : {result['cycle_compilation_id']}")
        print(f"Objective             : {result['objective_id']}")
        print(f"Project               : {result['project_id']}")
        print(f"Supporting docs (x2)  : "
              + ", ".join(f"{d['id']} ({d['name'][:40]})" for d in supporting_docs))
        print()
        print("Counts (rows tagged DEMO_T5_BACKLOG):")
        for k in pre_counts:
            print(f"  {k:32s}  pre={pre_counts[k]:>3d}  post={post_counts[k]:>3d}  "
                  f"delta={result['delta'][k]:+d}")
        print()
        if all(v == 0 for v in result["delta"].values()) and any(v > 0 for v in post_counts.values()):
            print("Idempotency: OK (re-run, zero delta).")
        elif all(v > 0 for v in post_counts.values()):
            print("Idempotency: first-run inserts complete.")
    return result


def main() -> None:
    asyncio.run(seed_async())


if __name__ == "__main__":
    main()
