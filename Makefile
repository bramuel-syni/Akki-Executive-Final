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
#
# Environment overrides:
#   EVIDENCE_BASE_URL=…  (default: http://localhost:3000)

PYTHON       ?= python3
EVIDENCE_DIR ?= memory/bank_qa_evidence/png
EVIDENCE_SCRIPT := scripts/generate_evidence_pngs.py

.PHONY: evidence-pngs evidence-pngs-diagram evidence-pngs-ui evidence-pngs-check

evidence-pngs:
	@$(PYTHON) $(EVIDENCE_SCRIPT)

evidence-pngs-diagram:
	@$(PYTHON) $(EVIDENCE_SCRIPT) --diagram-only

evidence-pngs-ui:
	@$(PYTHON) $(EVIDENCE_SCRIPT) --ui-only

evidence-pngs-check:
	@$(PYTHON) $(EVIDENCE_SCRIPT) --check
