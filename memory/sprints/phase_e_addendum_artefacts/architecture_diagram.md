# AKKI Architecture — System Overview

**Document type**: Bank-QA reviewer companion (C19-002)
**Audience**: Technical assessor doing a one-page system review
**Anchor**: `/app/memory/product/AKKI_FEATURES_AND_FUNCTIONALITY.md` § 3 for the prose version of this picture.

The diagram below is rendered in Mermaid (live in any GitHub Markdown
viewer, in the Mermaid Live Editor, or via `npx mmdc`). For static
review environments, a rendered PNG sits next to this file at
`architecture_diagram.png` — regenerate with the same Mermaid source
if the diagram drifts.

## Request flow — Shield gateway end-to-end

```mermaid
flowchart LR
    subgraph CLIENT["Client (browser)"]
        SPA["React SPA<br/>frontend/"]
    end

    subgraph EDGE["Edge / Ingress"]
        ING["Kubernetes ingress<br/>/api/* → backend:8001<br/>/* → frontend:3000"]
    end

    subgraph BACKEND["Backend (FastAPI)"]
        direction TB
        ROUTERS["Routers<br/>portfolio · chat · documents ·<br/>cycle · pulse · monitor ·<br/>solva_v2 · work_studio · admin"]
        SHIELD_CLIENT["services.synisense.shield.client.invoke()<br/>1. de-identify<br/>2. route to LLM<br/>3. re-identify<br/>4. write audit + trust receipt"]
        DEID["deidentifier<br/>regex + Presidio +<br/>spaCy NER (local)"]
        ROUTER["llm_router.invoke_with_metering()<br/>(sole approved entry to provider SDKs)"]
        STREAMING["streaming.py<br/>(approved streaming counterpart)"]
        REID["reidentifier<br/>token map → original spans"]
        AUDIT["audit_log.write_audit()<br/>+ trust_receipt.sign()"]
        ENGINE["Engine cron<br/>(APScheduler @ minute=0)<br/>scheduler_lock + scheduler_runs"]
    end

    subgraph DATA["Persistence (MongoDB)"]
        direction TB
        AUDIT_COL[("synisense_audit_log")]
        RECEIPT_COL[("synisense_trust_receipts")]
        RUNS_COL[("synisense_runs")]
        SCHED_LOCKS[("scheduler_locks<br/>(TTL-reaped)")]
        SCHED_RUNS[("scheduler_runs")]
        DOMAIN[("Domain collections<br/>contexts · documents ·<br/>cycles · pulse · solva_v2 ·<br/>solva_phase_d · work_studio")]
    end

    subgraph PROVIDER["LLM provider (Emergent proxy → litellm)"]
        ANTHROPIC["anthropic / claude"]
        OPENAI["openai / gpt"]
        GEMINI["gemini / flash"]
    end

    SPA -->|REACT_APP_BACKEND_URL/api/*| ING
    ING --> ROUTERS
    ROUTERS -->|invoke purpose, content| SHIELD_CLIENT
    SHIELD_CLIENT --> DEID
    DEID -->|de-id'd text| SHIELD_CLIENT
    SHIELD_CLIENT --> ROUTER
    ROUTER -->|opaque tokens only| ANTHROPIC
    ROUTER -->|opaque tokens only| OPENAI
    ROUTER -->|opaque tokens only| GEMINI
    ANTHROPIC -->|response + usage| ROUTER
    OPENAI -->|response + usage| ROUTER
    GEMINI -->|response + usage| ROUTER
    ROUTER --> SHIELD_CLIENT
    SHIELD_CLIENT --> REID
    REID --> SHIELD_CLIENT
    SHIELD_CLIENT --> AUDIT
    AUDIT --> AUDIT_COL
    AUDIT --> RECEIPT_COL
    SHIELD_CLIENT -->|response, audit_id| ROUTERS
    ROUTERS -->|JSON response| SPA

    STREAMING -.->|streaming-only requests| ANTHROPIC
    STREAMING -.-> OPENAI

    ENGINE -.->|claim lock| SCHED_LOCKS
    ENGINE -.->|heartbeat row| SCHED_RUNS
    ENGINE -->|tenant derivations| RUNS_COL
    ENGINE -.->|writes signals/contexts| DOMAIN
    ROUTERS -->|domain read/write| DOMAIN

    classDef shield fill:#e3f2fd,stroke:#1565c0,stroke-width:2px;
    classDef sdk fill:#fff8e1,stroke:#f57c00,stroke-width:2px;
    classDef data fill:#e8f5e9,stroke:#2e7d32,stroke-width:1px;
    class SHIELD_CLIENT,DEID,ROUTER,STREAMING,REID,AUDIT shield;
    class ANTHROPIC,OPENAI,GEMINI sdk;
    class AUDIT_COL,RECEIPT_COL,RUNS_COL,SCHED_LOCKS,SCHED_RUNS,DOMAIN data;
```

## What the colour groups mean

- **Blue** — the Synisense Shield. The ONLY path that touches raw consumer text + provider SDKs. CI guards (`test_no_direct_llm_calls_outside_shield` + `test_no_direct_llm_calls_inside_shield_except_router`) enforce this.
- **Yellow** — outside the trust boundary. The LLM provider sees only de-identified tokens.
- **Green** — persistence. Audit, receipt, scheduler heartbeat, and domain data all sit here.

## Verification of the picture from outside

Three surfaces let a reviewer poke this architecture without reading code:

| Surface | What it confirms |
|---------|------------------|
| `GET /api/admin/synisense/observability?window_days=7` | Audit log is populated; per-consumer rates make sense. |
| `GET /api/admin/synisense/billing?window_days=7` | Cost roll-up uses the per-model rate table; estimated vs exact metering split visible. |
| `GET /api/admin/synisense/cron-health` (Chunk 19, C19-005) | Engine cron actually ran; per-job last-run timestamp visible. |
| `verify_trust_receipt.py --self-test` | HMAC chain on any saved receipt is reproducible with stdlib only. |

## What is NOT shown (deliberately)

- The frontend internals (component tree, state management). Read the `frontend/src/components/` directory for that — the diagram stops at the SPA box on purpose.
- The Presidio internals. Black-box from the diagram's viewpoint; the relevant invariant is "no raw text leaves the Shield".
- The Trust Receipt signing key rotation flow. Out of scope for the system-overview slide; lives in operator runbooks.

---

**Last regenerated**: 2026-05-21 (Chunk 19 close).
**To regenerate the PNG**: paste the Mermaid block into `https://mermaid.live`, export as PNG at 2× resolution, save next to this file as `architecture_diagram.png`.
