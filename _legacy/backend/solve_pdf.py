"""AKKI Solve · narrative PDF export (Wave 4).

Renders a completed Solve session as an editorial one-pager:

  Page 1
    PRIVATE · AKKI SOLVE  · cluster_label · date
    Title: the user's own intent (serif, large)
    "The diagnosis" — synthesis body
    "Comparable diagnoses" — picked corpus (anonymised)
    "Lock-in commitments" — Decide / Watch / Walk in with
    Footer: Synisense-shielded · session id last 8 chars

A single A4 portrait page when content fits (typical), continues onto
page 2 when synthesis + comparables overflow.
"""
from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

# Editorial palette — matches the briefings PDF + frontend cream/oxblood look
AKKI_INK = colors.HexColor("#1F2937")
AKKI_DEEP = colors.HexColor("#3F3530")
AKKI_ACCENT = colors.HexColor("#8B2E2B")  # oxblood
AKKI_MUTED = colors.HexColor("#7B736B")
AKKI_RULE = colors.HexColor("#E2DACF")
AKKI_CREAM = colors.HexColor("#F7F3EA")


def _escape(text: str) -> str:
    """reportlab Paragraph parses XML-like markup."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _strip_md(text: str) -> str:
    """Lightweight markdown bold/italic stripping for the PDF body."""
    if not text:
        return ""
    # bold: **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    # italic: *text* or _text_  (avoid touching list markers)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    return text


def _parse_lockin(lockin_body: str) -> Dict[str, str]:
    """Mirror the parser used by the handoff endpoints."""
    out = {"decide": "", "watch": "", "walk_in": ""}
    if not lockin_body:
        return out
    for raw in lockin_body.splitlines():
        line = raw.strip().lstrip(" \t-•·*")
        if line.startswith("**"):
            line = line[2:]
        if not line:
            continue
        body = line
        label = ""
        if ":" in line:
            label, body = line.split(":", 1)
            label = label.rstrip("* ").strip().lower()
            body = body.lstrip("* ").strip()
        else:
            label = line[:20].lower()
        if label.startswith("decide"):
            out["decide"] = body
        elif label.startswith("watch"):
            out["watch"] = body
        elif label.startswith("walk in") or label.startswith("walk-in"):
            out["walk_in"] = body
    return out


def render_solve_pdf(session: Dict[str, Any]) -> bytes:
    """Render a completed Solve session to PDF bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=22 * mm, bottomMargin=22 * mm,
        title=session.get("intent", "AKKI Solve")[:80],
        author="AKKI Solve",
    )

    styles = getSampleStyleSheet()
    overline = ParagraphStyle(
        "akki-overline", parent=styles["Normal"],
        textColor=AKKI_ACCENT, fontName="Helvetica-Bold",
        fontSize=8, leading=10, spaceAfter=2,
    )
    title = ParagraphStyle(
        "akki-title", parent=styles["Normal"],
        textColor=AKKI_INK, fontName="Times-Roman",
        fontSize=20, leading=24, spaceAfter=10,
    )
    meta = ParagraphStyle(
        "akki-meta", parent=styles["Normal"],
        textColor=AKKI_MUTED, fontName="Helvetica",
        fontSize=8.5, leading=11, spaceAfter=18,
    )
    section_h = ParagraphStyle(
        "akki-section-h", parent=styles["Normal"],
        textColor=AKKI_ACCENT, fontName="Helvetica-Bold",
        fontSize=8, leading=10, spaceBefore=14, spaceAfter=6,
    )
    body = ParagraphStyle(
        "akki-body", parent=styles["Normal"],
        textColor=AKKI_INK, fontName="Times-Roman",
        fontSize=11, leading=17, spaceAfter=10,
    )
    cmp_label = ParagraphStyle(
        "akki-cmp-l", parent=styles["Normal"],
        textColor=AKKI_MUTED, fontName="Helvetica",
        fontSize=7.5, leading=9, spaceAfter=2,
    )
    cmp_body = ParagraphStyle(
        "akki-cmp-b", parent=styles["Normal"],
        textColor=AKKI_INK, fontName="Times-Roman",
        fontSize=10, leading=14, spaceAfter=4,
    )
    cmp_verdict = ParagraphStyle(
        "akki-cmp-v", parent=styles["Normal"],
        textColor=AKKI_DEEP, fontName="Helvetica",
        fontSize=9, leading=13, spaceAfter=1,
        leftIndent=4,
    )
    lockin_lead = ParagraphStyle(
        "akki-lo-lead", parent=styles["Normal"],
        textColor=AKKI_ACCENT, fontName="Helvetica-Bold",
        fontSize=10, leading=14,
    )
    lockin_body = ParagraphStyle(
        "akki-lo-b", parent=styles["Normal"],
        textColor=AKKI_INK, fontName="Times-Roman",
        fontSize=10.5, leading=15, spaceAfter=8,
    )
    footer = ParagraphStyle(
        "akki-footer", parent=styles["Normal"],
        textColor=AKKI_MUTED, fontName="Helvetica",
        fontSize=7.5, leading=10, spaceBefore=18,
    )

    flow: List[Any] = []

    cluster_label = session.get("cluster_label", "Solve session")
    flow.append(Paragraph("PRIVATE · AKKI SOLVE", overline))
    flow.append(Paragraph(_escape(session.get("intent", ""))[:240], title))

    bits: List[str] = [cluster_label]
    completed_at = session.get("completed_at") or session.get("updated_at")
    if completed_at:
        try:
            dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            bits.append(dt.strftime("%-d %B %Y · %H:%M UTC"))
        except Exception:  # noqa: BLE001
            bits.append(str(completed_at)[:10])
    if session.get("synthesis", {}).get("tier") == "deep":
        bits.append("Pro · deep synthesis")
    flow.append(Paragraph(" · ".join(bits), meta))

    # Synthesis
    syn = (session.get("synthesis") or {}).get("body") or ""
    if syn:
        flow.append(Paragraph("THE DIAGNOSIS", section_h))
        for para in _strip_md(syn).split("\n\n"):
            para = para.strip()
            if para:
                flow.append(Paragraph(_escape(para), body))

    # Comparables
    comparables = (session.get("synthesis") or {}).get("comparables") or []
    if comparables:
        flow.append(Paragraph("COMPARABLE DIAGNOSES", section_h))
        for c in comparables[:3]:
            sector = (c.get("sector_tag") or "any").replace("_", " ")
            scale = (c.get("scale_tag") or "—").replace("_", " ")
            flow.append(Paragraph(_escape(f"{sector.upper()} · {scale.upper()}"), cmp_label))
            flow.append(Paragraph(_escape(c.get("diagnosis_summary", "")), cmp_body))
            if c.get("what_worked"):
                flow.append(Paragraph(
                    f"<font color='{AKKI_ACCENT.hexval()}'>Worked:</font> "
                    + _escape(c.get("what_worked", "")),
                    cmp_verdict,
                ))
            if c.get("what_didnt"):
                flow.append(Paragraph(
                    f"<font color='{AKKI_MUTED.hexval()}'>Didn't:</font> "
                    + _escape(c.get("what_didnt", "")),
                    cmp_verdict,
                ))
            flow.append(Spacer(1, 6))

    # Lock-in
    lockin = (session.get("lockin") or {}).get("body") or ""
    if lockin:
        flow.append(Paragraph("LOCK-IN", section_h))
        parsed = _parse_lockin(lockin)
        for label, key in (("Decide", "decide"), ("Watch", "watch"), ("Walk in with", "walk_in")):
            text = parsed[key]
            if not text:
                continue
            t = Table(
                [[
                    Paragraph(label, lockin_lead),
                    Paragraph(_escape(_strip_md(text)), lockin_body),
                ]],
                colWidths=[28 * mm, 130 * mm],
            )
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]))
            flow.append(t)
        if not any(parsed.values()):
            # Fallback — render lock-in body verbatim if our parser couldn't split it.
            for para in _strip_md(lockin).split("\n\n"):
                if para.strip():
                    flow.append(Paragraph(_escape(para.strip()), body))

    # Footer
    sid_short = (session.get("id", "") or "")[:8]
    flow.append(Paragraph(
        f"Synisense-shielded · Solve session {sid_short} · "
        "Every comparable is anonymised. AKKI does not name companies.",
        footer,
    ))

    doc.build(flow)
    buf.seek(0)
    return buf.read()
