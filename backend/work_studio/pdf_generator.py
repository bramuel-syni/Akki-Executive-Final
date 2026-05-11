"""
PDF generator — WeasyPrint on a programmatic HTML render of the same
Brief the DOCX/PPTX generators consume. This is the chosen "derives
from DOCX-equivalent content by converting" path per the C.1 spec; we
render HTML rather than DOCX→PDF because libreoffice is not present
in this environment, and the WeasyPrint output is byte-deterministic
modulo the metadata timestamp.

Mirrors the WeDeliver concept-note signature:
  - cover block (title, subtitle, framework spine, host org, version,
    date, audience)
  - two-tier numbered headings (§N, §N.M)
  - structured tables at high fidelity
  - distinct heading + body fonts (Georgia + Inter / system fallbacks)
"""
from __future__ import annotations
from html import escape
from typing import List

from weasyprint import HTML, CSS

from .brief import Brief, BriefSection, BriefTable, FIDELITY_HIGH

INK   = "#1A1D20"
OXBLD = "#7A2E2E"
MUTED = "#6F7177"
CREAM = "#F2EFE8"
HAIRLINE = "#B8B6AF"


CSS_BASE = """
@page {
  size: A4;
  margin: 22mm 20mm 22mm 20mm;
  @bottom-center {
    content: counter(page);
    font-family: Inter, "Helvetica Neue", Arial, sans-serif;
    font-size: 9pt;
    color: """ + MUTED + """;
  }
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: Inter, "Helvetica Neue", Arial, sans-serif;
  color: """ + INK + """;
  font-size: 11pt;
  line-height: 1.45;
}
h1, h2, h3 { font-family: Georgia, "Times New Roman", serif; color: """ + INK + """; margin: 0; }
h1 { font-size: 24pt; line-height: 1.1; margin-bottom: 6pt; }
h2 { font-size: 16pt; line-height: 1.15; margin: 18pt 0 6pt 0; }
h3 { font-size: 12pt; margin: 10pt 0 4pt 0; }
.kicker {
  font-family: Inter, "Helvetica Neue", Arial, sans-serif;
  font-weight: 700;
  font-size: 9pt;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: """ + OXBLD + """;
  margin: 8pt 0 2pt 0;
}
.muted-kicker {
  font-family: Inter, "Helvetica Neue", Arial, sans-serif;
  font-weight: 700;
  font-size: 9pt;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: """ + MUTED + """;
  margin: 6pt 0 2pt 0;
}
p  { margin: 0 0 8pt 0; }
ul { margin: 0 0 8pt 18pt; padding: 0; }
li { margin-bottom: 3pt; }

.cover { padding-top: 20mm; page-break-after: always; }
.cover .doctype { font-family: Inter, sans-serif; font-weight: 700;
  font-size: 11pt; letter-spacing: 0.14em; text-transform: uppercase;
  color: """ + OXBLD + """; margin-bottom: 8pt; }
.cover h1 { font-size: 30pt; line-height: 1.05; }
.cover .subtitle { font-style: italic; color: """ + MUTED + """;
  font-size: 13pt; margin: 8pt 0 18pt 0; }
.cover .lead { font-size: 12pt; color: """ + INK + """; margin-bottom: 18pt; }
.cover .spine { font-family: Inter, sans-serif; font-weight: 700;
  font-size: 12pt; letter-spacing: 0.18em; text-transform: uppercase;
  color: """ + OXBLD + """; margin: 10pt 0 18pt 0; }
.cover .meta { color: """ + MUTED + """; font-size: 10pt; margin-top: 12pt; }
.cover .accent-bar { width: 18mm; height: 2pt; background: """ + OXBLD + """;
  margin: 0 0 14pt 0; }

.section { page-break-inside: avoid; padding-top: 4pt; }
.section + .section { border-top: 0.4pt solid """ + HAIRLINE + """;
  margin-top: 12pt; padding-top: 14pt; }

table.brief {
  width: 100%; border-collapse: collapse; margin: 6pt 0 12pt 0;
  font-size: 10pt;
}
table.brief th {
  background: """ + INK + """; color: white; text-align: left;
  font-family: Inter, sans-serif; font-weight: 700; font-size: 9pt;
  letter-spacing: 0.10em; text-transform: uppercase;
  padding: 6pt 8pt; border: 0.4pt solid """ + INK + """;
}
table.brief td {
  padding: 6pt 8pt; border: 0.4pt solid """ + HAIRLINE + """;
  vertical-align: top;
}

.closing { page-break-before: always; padding-top: 16mm; }
.closing .recap { font-family: Georgia, serif; font-size: 18pt;
  line-height: 1.3; margin: 12pt 0 24pt 0; }
.closing .brand { font-family: Inter, sans-serif; font-weight: 700;
  font-size: 10pt; letter-spacing: 0.14em; text-transform: uppercase;
  color: """ + MUTED + """; }
"""


def _escape(s: str) -> str:
    return escape(s or "", quote=True)


def _render_section(idx: int, sec: BriefSection, fidelity: str) -> str:
    parts: List[str] = ['<div class="section">']
    parts.append(f'<div class="kicker">§ {idx}</div>')
    parts.append(f"<h1>{_escape(sec.title)}</h1>")
    if sec.kicker:
        parts.append(f'<div class="muted-kicker">{_escape(sec.kicker)}</div>')
    for p in sec.body_paragraphs:
        parts.append(f"<p>{_escape(p)}</p>")
    if sec.bullets:
        parts.append("<ul>")
        for b in sec.bullets:
            parts.append(f"<li>{_escape(b)}</li>")
        parts.append("</ul>")
    for t in sec.tables:
        if fidelity == FIDELITY_HIGH:
            parts.append(f'<div class="kicker" style="color:{OXBLD}">{_escape(t.title)}</div>')
            parts.append('<table class="brief">')
            parts.append("<thead><tr>")
            for h in t.headers:
                parts.append(f"<th>{_escape(h)}</th>")
            parts.append("</tr></thead><tbody>")
            for row in t.rows:
                parts.append("<tr>")
                for c in row:
                    parts.append(f"<td>{_escape(str(c))}</td>")
                parts.append("</tr>")
            parts.append("</tbody></table>")
        else:
            parts.append(f'<div class="muted-kicker">{_escape(t.title)}</div><ul>')
            for row in t.rows:
                parts.append(
                    f"<li>{_escape('  ·  '.join(str(c) for c in row if str(c).strip()))}</li>"
                )
            parts.append("</ul>")
    parts.append("</div>")
    return "\n".join(parts)


def _render_html(brief: Brief) -> str:
    cover_meta_bits = []
    if brief.host_org_line: cover_meta_bits.append(f"Hosted by: {_escape(brief.host_org_line)}")
    if brief.version: cover_meta_bits.append(f"Document version: {_escape(brief.version)}")
    if brief.date_text: cover_meta_bits.append(_escape(brief.date_text))
    if brief.audience: cover_meta_bits.append(f"Audience: {_escape(brief.audience)}")

    sections_html = "\n".join(
        _render_section(i, s, brief.fidelity)
        for i, s in enumerate(brief.sections, start=1)
    )

    closing_html = ""
    if brief.closing_recap or brief.closing_brand_line:
        closing_html = f"""
        <div class="closing">
            <div class="kicker">Recap</div>
            <div class="recap">{_escape(brief.closing_recap or '')}</div>
            <div class="brand">{_escape(brief.closing_brand_line or '')}</div>
        </div>"""

    # STUDIO sprint — W-19: Synisense audit footer line. Only rendered
    # when Brief.audit_summary is set (preserves determinism for
    # fixtures that don't supply one).
    audit_html = ""
    if brief.audit_summary:
        audit_html = (
            f'<div class="audit-footer" style="margin-top:32px;font-family:'
            f'\'JetBrains Mono\', \'Courier New\', monospace;font-size:9px;'
            f'color:#6F7177;font-style:italic;">{_escape(brief.audit_summary)}</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{_escape(brief.title)}</title></head>
<body>
  <div class="cover">
    <div class="accent-bar"></div>
    <div class="doctype">{_escape(brief.document_type)}</div>
    <h1>{_escape(brief.title)}</h1>
    <div class="subtitle">{_escape(brief.subtitle)}</div>
    {f'<div class="lead">{_escape(brief.cover_lead_paragraph)}</div>' if brief.cover_lead_paragraph else ''}
    {f'<div class="spine">{_escape(brief.framework_spine)}</div>' if brief.framework_spine else ''}
    <div class="meta">{'  ·  '.join(cover_meta_bits)}</div>
  </div>
  {sections_html}
  {closing_html}
  {audit_html}
</body>
</html>"""


def render_pdf(brief: Brief) -> bytes:
    html = _render_html(brief)
    return HTML(string=html).write_pdf(stylesheets=[CSS(string=CSS_BASE)])
