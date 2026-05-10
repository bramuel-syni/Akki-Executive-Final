"""Work Studio Phase C exports."""
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

__all__ = [
    "Brief", "BriefSection", "BriefTable",
    "DEPTHS", "DEPTH_EXECUTIVE", "DEPTH_BOARD", "DEPTH_DEEP",
    "FIDELITIES", "FIDELITY_LOW", "FIDELITY_HIGH",
    "FORMATS", "FORMAT_DOCX", "FORMAT_PPTX", "FORMAT_PDF",
    "PICKER", "build_brief_from_solva",
    "render_docx", "render_pptx", "render_pdf",
]
