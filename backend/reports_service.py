"""Report PDF export — A4 portrait, editorial reportlab build with a chain
of-custody back page. Mirrors the briefing/board-deck visual language so a
finalised report is recognisable as an AKKI artefact.

Used only when a Report has reached `finalised` status (every chain tier
approved). The chain-of-custody back page lists each tier in order with
their action timestamp + note — a referenceable artefact for the board
secretary's filing cabinet."""
from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepInFrame, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)


CREAM = colors.HexColor("#F7F3EA")
INK = colors.HexColor("#1A1A1A")
DEEP = colors.HexColor("#2A2622")
ACCENT = colors.HexColor("#8B2E2B")
CHROME = colors.HexColor("#1A2B4C")
MUTED = colors.HexColor("#8B6F47")
RULE = colors.HexColor("#E8E0D0")


def _escape(text: str) -> str:
    """reportlab Paragraph uses XML-ish parsing; escape the basics."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _short_date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d %b %Y · %H:%M")
    except Exception:
        return iso


def _md_to_paragraphs(body: str, styles: Dict[str, ParagraphStyle]) -> List[Any]:
    """Cheap markdown → reportlab translation. Headings (#, ##), paragraphs,
    bullet lists, italic _x_ and bold **x**. No nested support — sufficient
    for the auto-generated body shape we produce."""
    out: List[Any] = []
    if not body:
        return out
    bullets: List[str] = []

    def _flush_bullets():
        if not bullets:
            return
        for b in bullets:
            out.append(Paragraph(f"&bull;&nbsp;&nbsp;{_inline(b)}", styles["bullet"]))
        out.append(Spacer(1, 4))
        bullets.clear()

    def _inline(s: str) -> str:
        s = _escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"_(.+?)_", r"<i>\1</i>", s)
        s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
        return s

    for raw in body.split("\n"):
        line = raw.rstrip()
        if line.startswith("# "):
            _flush_bullets()
            out.append(Paragraph(_inline(line[2:]), styles["h1"]))
            out.append(Spacer(1, 6))
        elif line.startswith("## "):
            _flush_bullets()
            out.append(Spacer(1, 8))
            out.append(Paragraph(_inline(line[3:]), styles["h2"]))
            out.append(Spacer(1, 4))
        elif line.startswith("### "):
            _flush_bullets()
            out.append(Paragraph(_inline(line[4:]), styles["h3"]))
        elif line.startswith("- ") or line.startswith("* "):
            bullets.append(line[2:])
        elif line.strip() == "":
            _flush_bullets()
            out.append(Spacer(1, 6))
        else:
            _flush_bullets()
            out.append(Paragraph(_inline(line), styles["body"]))
    _flush_bullets()
    return out


STATUS_LABEL = {
    "approved": "Approved",
    "pending": "Pending",
    "blocked": "Awaiting prior tier",
    "sent_back": "Sent back",
    "skipped": "Skipped",
}


def render_report_pdf(report: Dict[str, Any], context_name: str = "") -> bytes:
    """Build the finalised-report PDF. A4 portrait, editorial layout."""
    buf = io.BytesIO()
    pagesize = A4
    margin = 22 * mm
    frame = Frame(margin, margin, pagesize[0] - 2 * margin, pagesize[1] - 2 * margin,
                  id="content", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    def _on_page(canvas, doc):
        canvas.saveState()
        # Top kicker rule
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(2)
        canvas.line(margin, pagesize[1] - 14 * mm, margin + 38 * mm, pagesize[1] - 14 * mm)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(ACCENT)
        canvas.drawString(margin, pagesize[1] - 18 * mm, "AKKI · REPORT")
        # Footer
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(margin, 12 * mm,
                          f"Confidential · {context_name or 'AKKI'} · {report.get('cycle_name', '')}")
        canvas.drawRightString(pagesize[0] - margin, 12 * mm, f"Page {doc.page}")
        canvas.restoreState()

    template = PageTemplate(id="report", frames=[frame], onPage=_on_page, pagesize=pagesize)
    doc = BaseDocTemplate(buf, pageTemplates=[template], pagesize=pagesize)

    styles = {
        "kicker": ParagraphStyle("kicker", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT,
                                 leading=10, spaceAfter=4),
        "title": ParagraphStyle("title", fontName="Times-Roman", fontSize=22, textColor=INK,
                                leading=27, spaceBefore=4, spaceAfter=10),
        "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=9, textColor=MUTED,
                               leading=12, spaceAfter=14),
        "h1": ParagraphStyle("h1", fontName="Times-Roman", fontSize=18, textColor=INK,
                             leading=22, spaceBefore=10, spaceAfter=6),
        "h2": ParagraphStyle("h2", fontName="Times-Roman", fontSize=14, textColor=INK,
                             leading=18, spaceBefore=8, spaceAfter=4),
        "h3": ParagraphStyle("h3", fontName="Times-Bold", fontSize=11, textColor=DEEP,
                             leading=14, spaceBefore=6, spaceAfter=2),
        "body": ParagraphStyle("body", fontName="Times-Roman", fontSize=10.5, textColor=DEEP,
                               leading=14, spaceAfter=4),
        "bullet": ParagraphStyle("bullet", fontName="Times-Roman", fontSize=10.5,
                                 textColor=DEEP, leading=14, leftIndent=12, spaceAfter=2),
        "trail_h": ParagraphStyle("trail_h", fontName="Helvetica-Bold", fontSize=8,
                                  textColor=ACCENT, leading=10, spaceAfter=6),
    }

    story: List[Any] = []
    story.append(Paragraph(report.get("cycle_name", "REPORT").upper(), styles["kicker"]))
    story.append(Paragraph(_escape(report.get("title", "Untitled report")), styles["title"]))
    story.append(Paragraph(
        f"Author: <b>{_escape(report.get('author_name', ''))}</b> · "
        f"Status: <b>{report.get('status', '').replace('_', ' ').title()}</b> · "
        f"Updated: {_short_date(report.get('updated_at'))}",
        styles["meta"],
    ))

    # Body
    story.extend(_md_to_paragraphs(report.get("body", ""), styles))

    # Chain of custody page
    story.append(PageBreak())
    story.append(Paragraph("CHAIN OF CUSTODY", styles["trail_h"]))
    story.append(Paragraph("Sign-off trail", styles["h1"]))
    story.append(Paragraph(
        f"This report was reviewed and approved through {len(report.get('chain') or []) - 1} "
        f"escalation tier(s). Each entry below records the actor, their action, and the timestamp "
        f"of that action — drawn directly from AKKI's audit log, not reconstructed.",
        styles["body"],
    ))
    story.append(Spacer(1, 10))

    chain_rows: List[List[Any]] = [["Tier", "Role", "Name & email", "Action", "When", "Note"]]
    for entry in (report.get("chain") or []):
        action_label = STATUS_LABEL.get(entry.get("status", ""), entry.get("status", "—"))
        contact = f"{entry.get('name', '')}\n{entry.get('email', '') or '—'}"
        chain_rows.append([
            f"#{entry.get('tier', 0)}",
            (entry.get("title") or "").upper(),
            contact,
            action_label,
            _short_date(entry.get("acted_at")) or "—",
            (entry.get("note") or "")[:140] or "—",
        ])
    chain_table = Table(chain_rows, colWidths=[14 * mm, 30 * mm, 50 * mm, 22 * mm, 32 * mm, 38 * mm], repeatRows=1)
    chain_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), CREAM),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("TEXTCOLOR", (0, 1), (-1, -1), DEEP),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, ACCENT),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(KeepInFrame(0, 0, [chain_table], mode="shrink"))

    # Event log (one-liners) below the chain table
    events = report.get("events") or []
    if events:
        story.append(Spacer(1, 16))
        story.append(Paragraph("EVENT LOG", styles["trail_h"]))
        for e in events:
            ts = _short_date(e.get("at"))
            actor = _escape(e.get("actor_name") or "")
            action = _escape(e.get("action") or "")
            extra = ""
            if e.get("to_name"):
                extra = f" → <b>{_escape(e['to_name'])}</b>"
            note = ""
            if e.get("note"):
                note = f" — <i>{_escape(e['note'])}</i>"
            story.append(Paragraph(
                f"<font color='#8b6f47'>{ts}</font> &nbsp; <b>{actor}</b> · {action}{extra}{note}",
                styles["body"],
            ))

    # Trust footer
    story.append(Spacer(1, 18))
    story.append(Paragraph(
        "<font color='#1A2B4C'>Synisense-shielded</font> · "
        "Identities masked before any LLM call · Every signal cites its source · "
        "AKKI never reads private replies sent outside its product surface.",
        ParagraphStyle("trustfoot", fontName="Helvetica", fontSize=7.5,
                       textColor=MUTED, alignment=1, leading=10),
    ))

    doc.build(story)
    return buf.getvalue()
