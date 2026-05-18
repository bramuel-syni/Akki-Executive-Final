# Akki + Synisense — Bank-QA Evidence Pack

**Prepared for:** Bank-side technical due-diligence team
**As of:** 2026-05-18
**Maintained by:** Emergent Labs (Akki Sandbox engineering)

This evidence pack documents the architecture, controls, and verifiable artefacts of the Akki executive-AI product and its underlying Synisense privacy-and-governance gateway.

Read in this order:

1. **`01_REWRITE_OVERVIEW.md`** — five-paragraph briefing covering why the rewrite happened, what "privacy by structure" means in our code, what "single voice" means for the reasoning engine, what "signals not narratives" means for the engine, and how a reviewer can validate the system end-to-end.

2. **`02_ARCHITECTURE_DIAGRAM.md`** — diagram of the consumer ↔ Shield ↔ provider data flow, including the de-identification + re-identification path and the audit + trust-receipt return path. Also the Engine side.

3. **`03_SAMPLE_PRIVACY_REPORT.pdf`** — a real privacy report generated from a real chat conversation. This is the kind of artefact a tenant downloads after every conversation and the kind of artefact a regulator will ask to see. The PDF carries natural-language prose per turn AND the full HMAC-SHA256 signature for every audit row, with a verification recipe in the footer.

4. **`04_TRUST_RECEIPT_VERIFICATION.py`** — a standalone Python script (no Akki dependencies, ~50 lines) that takes a Trust Receipt JSON file and a per-tenant key and runs HMAC-SHA256 verification. Run it against any audit log row from the database and the matching trust receipt; if the signatures don't match, something has been tampered with downstream.

5. **`05_DEMO_SCREENSHOTS/`** — annotated screenshots of the five key surfaces: per-message audit panel, Solva session privacy timeline, admin observability dashboard, Monitor "Update goal" assessment, "Trust verified by Synisense" CTA.

6. **`06_API_CONTRACTS.md`** — extracted summary of every Shield + Engine endpoint, with request and response shapes. Pulled from the live OpenAPI spec.

7. **`07_TEST_EVIDENCE.md`** — full test-suite summary covering all 662 passing tests, the CI guard that enforces "no direct LLM calls outside Shield," and the render-smoke results for the frontend. Honest disclosure of what is tested and what is not.

The pack is self-contained and printable. Total page count if rendered: ~30 pages.

For deeper engineering details (per-phase sprint closeouts, system state snapshot, CI guard implementation), see the parent `/app/memory/sprints/` directory.
