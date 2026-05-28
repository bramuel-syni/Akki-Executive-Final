# AKKI — Makefile (Phase D autonomous sprint addition)
#
# Currently exposes only the `evidence-pngs` target — the bank-QA
# evidence pack PNG generator (architecture diagram + headless UI
# screenshots). Other dev targets can layer in here over time.
#
# Usage:
#   make evidence-pngs           # regenerate diagram + UI screenshots
#   make evidence-pngs-diagram   # diagram only
#   make evidence-pngs-ui        # UI screenshots only
#   make evidence-pngs-check     # CI guard — verify outputs exist
#   make deploy-check            # Wave8.followup.3 pre-deploy gate
#
# Environment overrides:
#   EVIDENCE_BASE_URL=…  (default: http://localhost:3000)

PYTHON       ?= python3
EVIDENCE_DIR ?= memory/bank_qa_evidence/png
EVIDENCE_SCRIPT := scripts/generate_evidence_pngs.py

.PHONY: evidence-pngs evidence-pngs-diagram evidence-pngs-ui evidence-pngs-check deploy-check

evidence-pngs:
	@$(PYTHON) $(EVIDENCE_SCRIPT)

evidence-pngs-diagram:
	@$(PYTHON) $(EVIDENCE_SCRIPT) --diagram-only

evidence-pngs-ui:
	@$(PYTHON) $(EVIDENCE_SCRIPT) --ui-only

evidence-pngs-check:
	@$(PYTHON) $(EVIDENCE_SCRIPT) --check

# Wave8.followup.3 (2026-02 fork-resume) — pre-deploy orthogonality gate.
#
# Runs the runtime Playwright wire-tests (Phase Z-slice-6 doc-orthogonality
# + Phase AA-slice-7 task-orthogonality) against the configured
# REACT_APP_BACKEND_URL preview. Promotes the strongest single test in
# the suite from CI signal to a deploy-blocker.
#
# Prerequisites (must hold before invoking this target):
#   - Backend + frontend serving the configured REACT_APP_BACKEND_URL
#   - Playwright + browser binaries installed: `python -m playwright install chromium`
#   - test_credentials.md superadmin (admin@akki.ai / AkkiAdmin2026!) seeded
#
# Exit non-zero on any failure → blocks the deploy step that depends on it.
deploy-check:
	@cd backend && $(PYTHON) -m pytest -m runtime_playwright -v
