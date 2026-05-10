"""Work Studio Phase C exports + Phase C.2 enhance loop."""
from .brief import (
    Brief, BriefSection, BriefTable,
    DEPTHS, DEPTH_EXECUTIVE, DEPTH_BOARD, DEPTH_DEEP,
    FIDELITIES, FIDELITY_LOW, FIDELITY_HIGH,
    FORMATS, FORMAT_DOCX, FORMAT_PPTX, FORMAT_PDF,
    PICKER, build_brief_from_solva,
)
from .docx_generator import render_docx
from .pptx_generator import render_pptx
from .pdf_generator import render_pdf

# Phase C.2 — persistence + enhance loop.
from .persistence import (
    brief_to_dict, dict_to_brief, slugify, compute_brief_id,
    ensure_brief_persisted,
    get_brief, get_revision, get_active_revision, list_revisions,
    insert_revision, set_active_revision,
)
from .enhance import (
    enhance_brief_two_pass,
    compute_section_diff,
    count_uncited_new_claims,
    count_section_changes,
    ALLOWED_TIERS,
)

__all__ = [
    # C.1
    "Brief", "BriefSection", "BriefTable",
    "DEPTHS", "DEPTH_EXECUTIVE", "DEPTH_BOARD", "DEPTH_DEEP",
    "FIDELITIES", "FIDELITY_LOW", "FIDELITY_HIGH",
    "FORMATS", "FORMAT_DOCX", "FORMAT_PPTX", "FORMAT_PDF",
    "PICKER", "build_brief_from_solva",
    "render_docx", "render_pptx", "render_pdf",
    # C.2 persistence
    "brief_to_dict", "dict_to_brief", "slugify", "compute_brief_id",
    "ensure_brief_persisted",
    "get_brief", "get_revision", "get_active_revision", "list_revisions",
    "insert_revision", "set_active_revision",
    # C.2 enhance
    "enhance_brief_two_pass",
    "compute_section_diff",
    "count_uncited_new_claims",
    "count_section_changes",
    "ALLOWED_TIERS",
]
