/**
 * BlockComposer — Phase 8 / Advisory 9.
 *
 * Block-based editing surface for briefings, decks and reports. Standard
 * palette (9 user-facing types):
 *
 *   Heading · Text · Citation/Quote · Signal/Metric · Divider ·
 *   Table · Bulleted list · Callout · Image
 *
 * Internally the heading kind carries content.level (1, 2 or 3) — level
 * 1 is the slide divider in deck mode.
 *
 * Editorial rules (do not break):
 *   - Georgia serif for body and heading levels 1/2/3.
 *   - Cream / oxblood / navy palette only. No gradients. No emojis.
 *   - The slash menu is keyboard-first and does not auto-close on focus
 *     loss — users select with arrow keys + Enter or click.
 *   - Citations resolve to a paragraph anchor; clicking the chip in the
 *     read-only render takes the user to /app/documents/:doc_id#:para.
 *   - Validator badge is rendered ONLY when the surface actually carries
 *     a real second-LLM countercheck. Composer does not display it.
 *
 * Reorder uses the existing `move` endpoint with up/down keyboard
 * affordances. HTML5 drag-and-drop is intentionally deferred to keep
 * the diff reviewable; the `reorder` endpoint is still available for
 * future bulk drag.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Heading1, Heading2, Heading3, Type, List as ListIcon, Quote, BarChart3,
  Minus, Table as TableIcon, Image as ImageIcon, AlertTriangle, ChevronUp,
  ChevronDown, Trash2, Plus, Send, CheckCircle2, FileText, Lock,
} from "lucide-react";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import PreviewDrawer from "@/components/synisense/PreviewDrawer";

// ─────────────────────────────────────────────────────────────────────────
// Block palette — the 9 Standard types. Order is the user-visible order
// in the slash menu.
// ─────────────────────────────────────────────────────────────────────────
const PALETTE = [
  { kind: "heading",       level: 1, label: "Heading 1",     desc: "Slide divider in decks · top-level section.", Icon: Heading1 },
  { kind: "heading",       level: 2, label: "Heading 2",     desc: "Section heading.",                            Icon: Heading2 },
  { kind: "heading",       level: 3, label: "Heading 3",     desc: "Subsection heading.",                         Icon: Heading3 },
  { kind: "paragraph",                label: "Text",          desc: "Plain editorial paragraph.",                   Icon: Type },
  { kind: "bulleted_list",            label: "Bulleted list", desc: "Short list of items, one per line.",          Icon: ListIcon },
  { kind: "callout",                  label: "Callout",       desc: "Info / warn / risk callout.",                  Icon: AlertTriangle },
  { kind: "citation",                 label: "Citation",      desc: "Quote sourced from a company document.",       Icon: Quote },
  { kind: "signal_card",              label: "Signal / metric", desc: "Reference a signal · optional metric.",     Icon: BarChart3 },
  { kind: "divider",                  label: "Divider",       desc: "Horizontal rule.",                             Icon: Minus },
  { kind: "table",                    label: "Table",         desc: "Headers + rows, plain text cells.",            Icon: TableIcon },
  { kind: "image",                    label: "Image",         desc: "Upload an image (≤ 6 MB · scanned by ClamAV).",  Icon: ImageIcon },
];

const CLASS_COLORS = {
  public:       { bg: "bg-emerald-50", border: "border-emerald-300", text: "text-emerald-900",    label: "Public" },
  internal:     { bg: "bg-amber-50",   border: "border-amber-300",   text: "text-amber-900",      label: "Internal" },
  confidential: { bg: "bg-orange-50",  border: "border-orange-400",  text: "text-orange-900",     label: "Confidential" },
  restricted:   { bg: "bg-red-50",     border: "border-red-400",     text: "text-red-900",        label: "Restricted" },
};

// Default content scaffold per kind — used when inserting a new block.
function defaultContentFor(kind, level) {
  switch (kind) {
    case "heading":       return { text: "", level: level || 2 };
    case "paragraph":     return { text: "" };
    case "bulleted_list": return { items: [""] };
    case "callout":       return { text: "", tone: "info" };
    case "citation":      return { doc_id: "", page: 1, paragraph_id: null, text: "" };
    case "signal_card":   return { signal_id: "" };
    case "divider":       return {};
    case "table":         return { headers: ["", ""], rows: [["", ""]] };
    case "image":         return { storage_key: "", alt: "", caption: "" };
    default:              return {};
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Slash menu — keyboard-driven block inserter.
// ─────────────────────────────────────────────────────────────────────────
function SlashMenu({ open, query, anchorRect, onPick, onClose }) {
  const items = useMemo(() => {
    const q = (query || "").toLowerCase().trim();
    if (!q) return PALETTE;
    return PALETTE.filter((p) =>
      p.label.toLowerCase().includes(q) || p.desc.toLowerCase().includes(q)
    );
  }, [query]);
  const [cursor, setCursor] = useState(0);
  useEffect(() => { setCursor(0); }, [query]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); onClose(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => (c + 1) % Math.max(items.length, 1)); return; }
      if (e.key === "ArrowUp")   { e.preventDefault(); setCursor((c) => (c - 1 + items.length) % Math.max(items.length, 1)); return; }
      if (e.key === "Enter")     { e.preventDefault(); if (items[cursor]) onPick(items[cursor]); return; }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open, cursor, items, onPick, onClose]);

  if (!open || !anchorRect) return null;
  return (
    <div
      role="listbox"
      aria-label="Insert block"
      data-testid="block-composer-slash-menu"
      className="fixed z-50 w-[340px] bg-[var(--parchment-light)] border border-[var(--graphite-light)] shadow-lg rounded-sm overflow-hidden"
      style={{ left: anchorRect.left, top: anchorRect.bottom + 6 }}
    >
      <div className="px-3 py-2 text-[10px] uppercase tracking-[0.16em] text-[var(--graphite)] border-b border-[var(--graphite-light)] bg-[var(--parchment-light)]">
        Insert block
      </div>
      <ul className="max-h-[320px] overflow-y-auto">
        {items.length === 0 && (
          <li className="px-3 py-2 text-[12px] text-[var(--graphite)] italic">No blocks match that query.</li>
        )}
        {items.map((p, i) => {
          const active = i === cursor;
          return (
            <li
              key={`${p.kind}-${p.level || 0}-${i}`}
              data-testid={`slash-menu-item-${p.kind}${p.level ? `-${p.level}` : ""}`}
              role="option"
              aria-selected={active}
              onMouseEnter={() => setCursor(i)}
              onMouseDown={(e) => { e.preventDefault(); onPick(p); }}
              className={`flex items-start gap-3 px-3 py-2 cursor-pointer text-[13px] ${active ? "bg-[var(--parchment)]" : "bg-transparent"}`}
            >
              <p.Icon className="w-4 h-4 mt-[2px] text-[var(--ink)] shrink-0" strokeWidth={1.6} />
              <div className="flex-1 min-w-0">
                <div className="text-[var(--ink)]" style={{ fontFamily: "Georgia, serif" }}>{p.label}</div>
                <div className="text-[11.5px] text-[var(--graphite)] leading-snug">{p.desc}</div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Per-block editors. Each receives `content`, `onChange`, `documents`,
// `signals`, `apiCall` (for image upload).
// ─────────────────────────────────────────────────────────────────────────
function HeadingBlock({ content, onChange, readOnly }) {
  const level = content?.level || 2;
  const sizeCls = level === 1 ? "text-[28px]" : level === 2 ? "text-[22px]" : "text-[18px]";
  return (
    <input
      data-testid="block-heading-input"
      readOnly={readOnly}
      value={content?.text || ""}
      onChange={(e) => onChange({ ...content, text: e.target.value, level })}
      placeholder={`Heading ${level}`}
      className={`w-full bg-transparent border-0 outline-none focus:ring-0 ${sizeCls} text-[var(--ink)] placeholder:text-[#A89878]`}
      style={{ fontFamily: "Georgia, serif" }}
    />
  );
}

function ParagraphBlock({ content, onChange, readOnly }) {
  return (
    <textarea
      data-testid="block-paragraph-input"
      readOnly={readOnly}
      value={content?.text || ""}
      onChange={(e) => onChange({ ...content, text: e.target.value })}
      placeholder="Write a paragraph…"
      rows={Math.max(2, Math.min(12, ((content?.text || "").match(/\n/g) || []).length + 2))}
      className="w-full resize-y bg-transparent border-0 outline-none focus:ring-0 text-[15px] leading-[1.65] text-[var(--ink)] placeholder:text-[#A89878]"
      style={{ fontFamily: "Georgia, serif" }}
    />
  );
}

function BulletedListBlock({ content, onChange, readOnly }) {
  const items = Array.isArray(content?.items) ? content.items : [""];
  const update = (i, v) => {
    const next = items.slice();
    next[i] = v;
    onChange({ items: next });
  };
  const addItem = () => onChange({ items: [...items, ""] });
  const removeItem = (i) => {
    const next = items.slice();
    next.splice(i, 1);
    onChange({ items: next.length ? next : [""] });
  };
  return (
    <ul className="space-y-1.5" data-testid="block-list">
      {items.map((it, i) => (
        <li key={i} className="flex gap-2 items-start">
          <span className="mt-[10px] w-1.5 h-1.5 rounded-full bg-[var(--oxblood)] shrink-0" />
          <input
            readOnly={readOnly}
            value={it}
            onChange={(e) => update(i, e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addItem(); } }}
            placeholder="List item"
            className="flex-1 bg-transparent border-0 outline-none focus:ring-0 text-[14.5px] text-[var(--ink)] placeholder:text-[#A89878] py-1"
            style={{ fontFamily: "Georgia, serif" }}
          />
          {!readOnly && items.length > 1 && (
            <button type="button" onClick={() => removeItem(i)} className="text-[var(--graphite)] hover:text-[var(--oxblood)] mt-1.5" aria-label="Remove item">
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </li>
      ))}
      {!readOnly && (
        <li>
          <button type="button" onClick={addItem} className="text-[11px] uppercase tracking-[0.14em] text-[var(--graphite)] hover:text-[var(--ink)]">
            + Add item
          </button>
        </li>
      )}
    </ul>
  );
}

function CalloutBlock({ content, onChange, readOnly }) {
  const tone = content?.tone || "info";
  const tones = [
    { id: "info", label: "Info",  border: "border-[var(--ink)]" },
    { id: "warn", label: "Warn",  border: "border-amber-500" },
    { id: "risk", label: "Risk",  border: "border-[var(--oxblood)]" },
  ];
  const sel = tones.find((t) => t.id === tone) || tones[0];
  return (
    <div className={`pl-4 border-l-[3px] ${sel.border} bg-[#FBF7EC] py-3 pr-3`} data-testid="block-callout">
      {!readOnly && (
        <div className="flex gap-2 mb-2">
          {tones.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => onChange({ ...content, tone: t.id })}
              className={`text-[10px] uppercase tracking-[0.14em] px-1.5 py-[2px] border ${tone === t.id ? "border-[var(--ink)] text-[var(--ink)] bg-[var(--parchment-light)]" : "border-transparent text-[var(--graphite)]"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}
      <textarea
        readOnly={readOnly}
        value={content?.text || ""}
        onChange={(e) => onChange({ ...content, text: e.target.value, tone: sel.id })}
        placeholder="Callout text"
        rows={2}
        className="w-full resize-y bg-transparent border-0 outline-none focus:ring-0 text-[14px] leading-[1.6] text-[var(--ink)] placeholder:text-[#A89878]"
        style={{ fontFamily: "Georgia, serif" }}
      />
    </div>
  );
}

function CitationBlock({ content, onChange, readOnly, documents }) {
  const docId = content?.doc_id || "";
  const selectedDoc = (documents || []).find((d) => d.id === docId);
  const restricted = (selectedDoc?.classification?.classification || selectedDoc?.classification) === "restricted";
  return (
    <figure className="border-l-[3px] border-[var(--oxblood)] pl-4 py-2 bg-[#F9F5EA]" data-testid="block-citation">
      {!readOnly && (
        <div className="flex flex-wrap gap-2 items-center mb-2">
          <select
            data-testid="citation-doc-select"
            value={docId}
            onChange={(e) => onChange({ ...content, doc_id: e.target.value })}
            className="text-[12px] bg-white border border-[var(--graphite-light)] px-2 py-1 max-w-[260px]"
          >
            <option value="">— Pick a source —</option>
            {(documents || []).map((d) => (
              <option key={d.id} value={d.id}>{d.name || "(unnamed)"}</option>
            ))}
          </select>
          <input
            type="number"
            min={1}
            value={content?.page || 1}
            onChange={(e) => onChange({ ...content, page: Math.max(1, parseInt(e.target.value || "1", 10)) })}
            placeholder="page"
            className="w-[68px] text-[12px] bg-white border border-[var(--graphite-light)] px-2 py-1"
            aria-label="Source page number"
          />
          <input
            value={content?.paragraph_id || ""}
            onChange={(e) => onChange({ ...content, paragraph_id: e.target.value || null })}
            placeholder="paragraph anchor (optional)"
            className="flex-1 min-w-[160px] text-[12px] bg-white border border-[var(--graphite-light)] px-2 py-1"
            aria-label="Paragraph anchor"
          />
          {restricted && (
            <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.14em] text-red-900 bg-red-50 border border-red-300 px-1.5 py-0.5">
              <Lock className="w-3 h-3" /> Restricted source
            </span>
          )}
        </div>
      )}
      <textarea
        readOnly={readOnly}
        value={content?.text || ""}
        onChange={(e) => onChange({ ...content, text: e.target.value })}
        placeholder='"Quote from the source."'
        rows={2}
        className="w-full resize-y bg-transparent border-0 outline-none focus:ring-0 text-[14.5px] leading-[1.6] text-[var(--ink)] italic placeholder:text-[#A89878]"
        style={{ fontFamily: "Georgia, serif" }}
      />
      {readOnly && selectedDoc && (
        <a
          href={`/app/documents/${selectedDoc.id}${content?.paragraph_id ? `#${content.paragraph_id}` : ""}`}
          className="block text-[11px] uppercase tracking-[0.14em] text-[var(--ink)] hover:underline mt-2"
        >
          {selectedDoc.name} · p.{content?.page || 1}
        </a>
      )}
    </figure>
  );
}

function SignalCardBlock({ content, onChange, readOnly, signals }) {
  const sigId = content?.signal_id || "";
  const metric = content?.metric || {};
  const trend = (metric.trend || "").toLowerCase();
  const arrow = trend === "up" ? "▲" : trend === "down" ? "▼" : trend === "flat" ? "—" : "";
  return (
    <div className="border border-[var(--graphite-light)] bg-white p-3" data-testid="block-signal-card">
      {!readOnly && (
        <div className="flex flex-wrap gap-2 items-center mb-2">
          <select
            value={sigId}
            onChange={(e) => onChange({ ...content, signal_id: e.target.value })}
            className="text-[12px] bg-white border border-[var(--graphite-light)] px-2 py-1 max-w-[260px]"
          >
            <option value="">— Pick a signal —</option>
            {(signals || []).map((s) => (
              <option key={s.id} value={s.id}>{s.headline || s.id}</option>
            ))}
          </select>
        </div>
      )}
      {sigId && (signals || []).find((s) => s.id === sigId) && (
        <p className="text-[13px] text-[var(--ink)] mb-2" style={{ fontFamily: "Georgia, serif" }}>
          {(signals || []).find((s) => s.id === sigId).headline}
        </p>
      )}
      {!readOnly && (
        <div className="grid grid-cols-2 gap-2 mt-1">
          <input value={metric.label || ""}  onChange={(e) => onChange({ ...content, metric: { ...metric, label: e.target.value } })} placeholder="Metric label" className="text-[12px] bg-[#FBF7EC] border border-[var(--graphite-light)] px-2 py-1" />
          <input value={metric.value || ""}  onChange={(e) => onChange({ ...content, metric: { ...metric, value: e.target.value } })} placeholder="Value (e.g. 12.4)" className="text-[12px] bg-[#FBF7EC] border border-[var(--graphite-light)] px-2 py-1" />
          <input value={metric.unit || ""}   onChange={(e) => onChange({ ...content, metric: { ...metric, unit: e.target.value } })} placeholder="Unit (% / £m)" className="text-[12px] bg-[#FBF7EC] border border-[var(--graphite-light)] px-2 py-1" />
          <input value={metric.delta || ""}  onChange={(e) => onChange({ ...content, metric: { ...metric, delta: e.target.value } })} placeholder="Delta (+1.2pp)" className="text-[12px] bg-[#FBF7EC] border border-[var(--graphite-light)] px-2 py-1" />
          <select value={metric.trend || ""} onChange={(e) => onChange({ ...content, metric: { ...metric, trend: e.target.value || null } })} className="text-[12px] bg-[#FBF7EC] border border-[var(--graphite-light)] px-2 py-1">
            <option value="">trend (optional)</option>
            <option value="up">up</option>
            <option value="down">down</option>
            <option value="flat">flat</option>
          </select>
        </div>
      )}
      {(metric.label || metric.value) && (
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-[10px] uppercase tracking-[0.14em] text-[var(--graphite)]">{metric.label}</span>
          <span className="text-[20px] text-[var(--ink)]" style={{ fontFamily: "Georgia, serif" }}>{metric.value}{metric.unit ? ` ${metric.unit}` : ""}</span>
          {metric.delta && (
            <span className={`text-[12px] ${trend === "up" ? "text-emerald-700" : trend === "down" ? "text-[var(--oxblood)]" : "text-[var(--graphite)]"}`}>
              {arrow} {metric.delta}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function DividerBlock() {
  return <hr className="border-0 border-t border-[var(--graphite-light)] my-2" data-testid="block-divider" />;
}

function TableBlock({ content, onChange, readOnly }) {
  const headers = Array.isArray(content?.headers) ? content.headers : ["", ""];
  const rows = Array.isArray(content?.rows) ? content.rows : [["", ""]];
  const setHeader = (i, v) => { const h = headers.slice(); h[i] = v; onChange({ headers: h, rows: rows.map((r) => { while (r.length < h.length) r.push(""); return r.slice(0, h.length); }) }); };
  const setCell = (r, c, v) => { const next = rows.map((row) => row.slice()); next[r][c] = v; onChange({ headers, rows: next }); };
  const addCol = () => { const h = [...headers, ""]; const r2 = rows.map((r) => [...r, ""]); onChange({ headers: h, rows: r2 }); };
  const addRow = () => { onChange({ headers, rows: [...rows, headers.map(() => "")] }); };
  const removeRow = (r) => { const next = rows.filter((_, i) => i !== r); onChange({ headers, rows: next.length ? next : [headers.map(() => "")] }); };
  return (
    <div className="overflow-x-auto" data-testid="block-table">
      <table className="w-full text-[13px] border border-[var(--graphite-light)]">
        <thead className="bg-[var(--parchment)]">
          <tr>
            {headers.map((h, i) => (
              <th key={i} className="border border-[var(--graphite-light)] px-2 py-1 text-left">
                <input
                  readOnly={readOnly}
                  value={h}
                  onChange={(e) => setHeader(i, e.target.value)}
                  placeholder={`Col ${i + 1}`}
                  className="w-full bg-transparent border-0 outline-none focus:ring-0 text-[12px] uppercase tracking-[0.14em] text-[var(--ink)]"
                />
              </th>
            ))}
            {!readOnly && <th className="w-8" />}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, c) => (
                <td key={c} className="border border-[var(--graphite-light)] px-2 py-1 align-top">
                  <input
                    readOnly={readOnly}
                    value={cell || ""}
                    onChange={(e) => setCell(r, c, e.target.value)}
                    className="w-full bg-transparent border-0 outline-none focus:ring-0"
                  />
                </td>
              ))}
              {!readOnly && (
                <td className="border border-[var(--graphite-light)] px-1 text-center">
                  <button type="button" onClick={() => removeRow(r)} aria-label="Remove row" className="text-[var(--graphite)] hover:text-[var(--oxblood)]">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {!readOnly && (
        <div className="flex gap-3 mt-2 text-[11px] uppercase tracking-[0.14em] text-[var(--graphite)]">
          <button type="button" onClick={addRow} className="hover:text-[var(--ink)]">+ Row</button>
          <button type="button" onClick={addCol} className="hover:text-[var(--ink)]">+ Column</button>
        </div>
      )}
    </div>
  );
}

function ImageBlock({ content, onChange, readOnly, onUpload }) {
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);
  const handlePick = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 6 * 1024 * 1024) {
      toast.error("Image exceeds 6 MB limit.");
      return;
    }
    try {
      setBusy(true);
      const data_base64 = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          const result = String(reader.result || "");
          const idx = result.indexOf(",");
          resolve(idx >= 0 ? result.slice(idx + 1) : result);
        };
        reader.onerror = reject;
        reader.readAsDataURL(f);
      });
      const result = await onUpload({
        filename: f.name,
        mime_type: f.type || "image/png",
        data_base64,
        alt: content?.alt || "",
      });
      onChange({
        ...content,
        storage_key: result.storage_key,
        mime_type: result.mime_type,
        alt: result.alt || content?.alt || "",
        // Persist the scanner provenance so the UI badge reads from
        // the API's `scan` field rather than a hard-coded literal. The
        // backend returns "clamav" on success; the UI never exposes
        // that raw value — it maps known clean values to "Scanned".
        scan: result.scan || null,
      });
    } catch (err) {
      // Advisory 9 honesty rule: the toast reflects what actually
      // happened. A 422 means ClamAV flagged the upload; a 503 means
      // the scanner is offline and the upload is refused. We do not
      // pretend-scan.
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      if (status === 422 && detail?.reason === "malware_suspected") {
        toast.error(`Blocked — suspected malware${detail.signature ? ` (${detail.signature})` : ""}`);
      } else if (status === 503 && detail?.error === "scanner_unavailable") {
        toast.error("Virus scanner offline — upload refused. Try again shortly.");
      } else {
        toast.error(apiErrorMessage(err, "Image upload failed."));
      }
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="bg-[#FBF7EC] border border-dashed border-[var(--graphite-light)] p-3" data-testid="block-image">
      {content?.storage_key ? (
        <div className="flex flex-col gap-2">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--graphite)]">
            Image attached · {content.storage_key.split("/").pop()}
            {/* Scanner provenance: the API returns {scan: "clamav"} on
                success. We map known clean values to "Scanned" and
                never surface the raw scanner name to the user. */}
            {["clamav"].includes((content.scan || "").toString().toLowerCase()) && (
              <span className="ml-2 inline-flex items-center gap-1 normal-case tracking-normal text-[10.5px] text-emerald-800">
                · Scanned
              </span>
            )}
          </p>
          {!readOnly && (
            <input
              value={content?.alt || ""}
              onChange={(e) => onChange({ ...content, alt: e.target.value })}
              placeholder="Alt text (accessibility)"
              className="text-[12px] bg-white border border-[var(--graphite-light)] px-2 py-1"
            />
          )}
          {!readOnly && (
            <input
              value={content?.caption || ""}
              onChange={(e) => onChange({ ...content, caption: e.target.value })}
              placeholder="Caption (optional)"
              className="text-[12px] bg-white border border-[var(--graphite-light)] px-2 py-1"
            />
          )}
        </div>
      ) : (
        <div className="flex flex-col items-start gap-2">
          <p className="text-[12px] text-[var(--graphite)]">No image attached.</p>
          {!readOnly && (
            <>
              <input ref={fileRef} type="file" accept="image/*" onChange={handlePick} className="hidden" data-testid="image-file-input" />
              <button type="button" disabled={busy} onClick={() => fileRef.current?.click()} className="inline-flex items-center gap-1 text-[12px] uppercase tracking-[0.14em] px-2 py-1 border border-[var(--ink)] text-[var(--ink)] hover:bg-[var(--ink)] hover:text-[var(--parchment-light)] disabled:opacity-50">
                <ImageIcon className="w-3.5 h-3.5" /> {busy ? "Scanning…" : "Upload image"}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Composer surface
// ─────────────────────────────────────────────────────────────────────────
const STATE_LABELS = {
  draft:     { label: "Draft",     bar: "bg-[var(--graphite)]" },
  in_review: { label: "In review", bar: "bg-amber-700" },
  approved:  { label: "Approved",  bar: "bg-emerald-700" },
  sent:      { label: "Sent",      bar: "bg-[var(--ink)]" },
};

export default function BlockComposer({ kind, artefactId }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [blocks, setBlocks] = useState([]);
  const [contextId, setContextId] = useState(null);
  const [artefact, setArtefact] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [signals, setSignals] = useState([]);
  const [slashOpen, setSlashOpen] = useState(false);
  const [slashAnchor, setSlashAnchor] = useState(null);
  const [slashQuery, setSlashQuery] = useState("");
  const slashAfterRef = useRef(null);
  const [savingId, setSavingId] = useState(null);
  // Phase 12.2 ITEM C — Synisense preview-drawer state. The drawer
  // opens once on first non-empty save (server tells us via
  // synisense_first_accept_pending=true), and again on later saves
  // ONLY when synisense_drawer_reopen=true (a new entity type was
  // detected since the user's last accept).
  const [synPreview, setSynPreview] = useState(null); // {spans, stats, kind}
  const [synDrawerReopen, setSynDrawerReopen] = useState(false);

  const handleSynisenseResponse = useCallback((data) => {
    if (!data) return;
    if (data.synisense_first_accept_pending && data.synisense) {
      setSynPreview(data.synisense);
      setSynDrawerReopen(false);
    } else if (data.synisense_drawer_reopen && data.synisense) {
      setSynPreview(data.synisense);
      setSynDrawerReopen(true);
    }
  }, []);

  // Load blocks + lifecycle on mount.
  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/studio/${kind}/${artefactId}/blocks`);
      setBlocks(data.blocks || []);
      setContextId(data.context_id);
      setArtefact(data.artefact || null);
      // Pull docs + signals for picker fields.
      if (data.context_id) {
        try {
          const [docs, sigs] = await Promise.all([
            api.get(`/contexts/${data.context_id}/documents`),
            api.get(`/contexts/${data.context_id}/signals`).catch(() => ({ data: { signals: [] } })),
          ]);
          setDocuments(docs.data?.documents || []);
          setSignals(sigs.data?.signals || []);
        } catch {
          // best-effort
        }
      }
      setError(null);
    } catch (e) {
      setError(apiErrorMessage(e, "Failed to load composer."));
    } finally {
      setLoading(false);
    }
  }, [kind, artefactId]);

  useEffect(() => { refresh(); }, [refresh]);

  const lifecycle = artefact?.block_status || "draft";
  const readOnly = lifecycle !== "draft";
  const classification = artefact?.classification?.classification || "internal";
  const cls = CLASS_COLORS[classification] || CLASS_COLORS.internal;

  // ─── Mutations ────────────────────────────────────────────────────────
  const insertBlock = async (paletteEntry, afterId) => {
    const content = defaultContentFor(paletteEntry.kind, paletteEntry.level);
    try {
      const { data } = await api.post(`/studio/${kind}/${artefactId}/blocks`, {
        kind: paletteEntry.kind,
        content,
        after_block_id: afterId || null,
      });
      const newBlock = data.block;
      setBlocks((bs) => {
        const next = bs.slice();
        if (afterId) {
          const idx = next.findIndex((b) => b.id === afterId);
          next.splice(idx + 1, 0, newBlock);
        } else {
          next.push(newBlock);
        }
        return next;
      });
      if (data.classification) setArtefact((a) => ({ ...(a || {}), classification: data.classification }));
      // Phase 12.2 ITEM C — preview drawer state.
      handleSynisenseResponse(data);
    } catch (e) {
      toast.error(apiErrorMessage(e, "Could not insert block."));
    }
  };

  const updateBlockLocal = (blockId, content) => {
    setBlocks((bs) => bs.map((b) => (b.id === blockId ? { ...b, content } : b)));
  };

  // Debounced save per-block. The user is shown a subtle "saving…" hint.
  useEffect(() => {
    const handle = setTimeout(async () => {
      if (!savingId) return;
      const target = blocks.find((b) => b.id === savingId);
      if (!target) return;
      try {
        const { data } = await api.patch(`/studio/${kind}/${artefactId}/blocks/${savingId}`, {
          content: target.content,
        });
        if (data.classification) setArtefact((a) => ({ ...(a || {}), classification: data.classification }));
        // Phase 12.2 ITEM C — preview drawer state on patch.
        handleSynisenseResponse(data);
      } catch (e) {
        toast.error(apiErrorMessage(e, "Save failed."));
      } finally {
        setSavingId(null);
      }
    }, 600);
    return () => clearTimeout(handle);
  }, [savingId, blocks, kind, artefactId]);

  const onBlockChange = (blockId) => (content) => {
    updateBlockLocal(blockId, content);
    setSavingId(blockId);
  };

  const moveBlock = async (blockId, direction) => {
    const idx = blocks.findIndex((b) => b.id === blockId);
    if (idx < 0) return;
    const target = direction === "up" ? Math.max(0, idx - 1) : Math.min(blocks.length - 1, idx + 1);
    if (target === idx) return;
    const next = blocks.slice();
    const [moved] = next.splice(idx, 1);
    next.splice(target, 0, moved);
    setBlocks(next);
    try {
      await api.post(`/studio/${kind}/${artefactId}/blocks/${blockId}/move`, { to_order: target });
    } catch (e) {
      toast.error(apiErrorMessage(e, "Reorder failed."));
      refresh();
    }
  };

  const deleteBlock = async (blockId) => {
    if (!window.confirm("Delete this block?")) return;
    try {
      await api.delete(`/studio/${kind}/${artefactId}/blocks/${blockId}`);
      setBlocks((bs) => bs.filter((b) => b.id !== blockId));
    } catch (e) {
      toast.error(apiErrorMessage(e, "Delete failed."));
    }
  };

  const uploadImage = async (payload) => {
    const { data } = await api.post(`/studio/${kind}/${artefactId}/upload-image`, payload);
    return data;
  };

  const submitForReview = async () => {
    try {
      await api.post(`/studio/${kind}/${artefactId}/submit-review`, { note: "" });
      toast.success("Submitted for review.");
      refresh();
    } catch (e) {
      toast.error(apiErrorMessage(e, "Submit failed."));
    }
  };

  const approve = async () => {
    try {
      await api.post(`/studio/${kind}/${artefactId}/approve`, { note: "" });
      toast.success("Approved.");
      refresh();
    } catch (e) {
      toast.error(apiErrorMessage(e, "Approval failed."));
    }
  };

  const send = async () => {
    const recipients = window.prompt("Recipients (comma-separated email addresses):", "");
    if (!recipients) return;
    const to = recipients.split(",").map((s) => s.trim()).filter(Boolean);
    if (!to.length) return;
    try {
      const { data } = await api.post(`/studio/${kind}/${artefactId}/send`, {
        to,
        subject: artefact?.title || `${kind.toUpperCase()} from AKKI`,
        body_note: "",
      });
      const mode = data?.send_result?.mode;
      if (mode === "sent") toast.success("Sent.");
      else if (mode === "noop") toast.info("Resend not configured. Recorded as 'noop' in audit log.");
      else toast.error("Send error: " + (mode || "unknown"));
      refresh();
    } catch (e) {
      toast.error(apiErrorMessage(e, "Send failed."));
    }
  };

  // ─── Slash menu wire-up ───────────────────────────────────────────────
  const openSlashMenuAt = (e, afterId) => {
    const rect = (e.currentTarget?.getBoundingClientRect && e.currentTarget.getBoundingClientRect()) || null;
    setSlashAnchor(rect);
    slashAfterRef.current = afterId || null;
    setSlashQuery("");
    setSlashOpen(true);
  };

  const onSlashPick = (entry) => {
    setSlashOpen(false);
    insertBlock(entry, slashAfterRef.current || null);
    slashAfterRef.current = null;
  };

  // ─── Render ───────────────────────────────────────────────────────────
  if (loading) {
    return <div className="text-[var(--graphite)] italic" style={{ fontFamily: "Georgia, serif" }}>Reading the draft…</div>;
  }
  if (error) {
    return <div className="text-[var(--oxblood)] text-sm">{error}</div>;
  }

  // Decks: render slide-tray sidebar based on H1 boundaries.
  const slideStarts = kind === "deck"
    ? blocks.map((b, i) => (b.kind === "heading" && (b.content?.level || 2) === 1 ? i : -1)).filter((i) => i >= 0)
    : [];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-6" data-testid="block-composer">
      {/* Slide tray (decks only) ─────────────────────────────────────── */}
      {kind === "deck" && (
        <aside className="border border-[var(--graphite-light)] bg-[#FBF7EC] p-3 self-start sticky top-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--graphite)] mb-2">Slides</div>
          {slideStarts.length === 0 && (
            <p className="text-[12px] text-[var(--graphite)] italic">Insert a Heading 1 to start a new slide.</p>
          )}
          <ol className="space-y-1.5">
            {slideStarts.map((i, slideIdx) => {
              const b = blocks[i];
              return (
                <li key={b.id}>
                  <a
                    href={`#slide-${slideIdx + 1}`}
                    className="block text-[13px] text-[var(--ink)] hover:underline truncate"
                    style={{ fontFamily: "Georgia, serif" }}
                  >
                    {slideIdx + 1}. {b.content?.text || "(untitled slide)"}
                  </a>
                </li>
              );
            })}
          </ol>
        </aside>
      )}

      {/* Main composer ──────────────────────────────────────────────── */}
      <div className="min-w-0">
        {/* Header: classification + lifecycle + actions */}
        <header className="border-b border-[var(--graphite-light)] pb-3 mb-4 flex flex-wrap items-center gap-3">
          <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.16em] px-1.5 py-0.5 border ${cls.bg} ${cls.border} ${cls.text}`} data-testid="composer-classification">
            <Lock className="w-3 h-3" /> {cls.label}
          </span>
          <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.16em] px-1.5 py-0.5 border border-[var(--graphite-light)] text-[var(--graphite)] bg-[var(--parchment-light)]`} data-testid="composer-lifecycle">
            <span className={`inline-block w-1.5 h-1.5 rounded-full ${STATE_LABELS[lifecycle]?.bar || "bg-[var(--graphite)]"}`} />
            {STATE_LABELS[lifecycle]?.label || lifecycle}
          </span>
          <div className="ml-auto flex flex-wrap gap-2">
            {lifecycle === "draft" && (
              <button onClick={submitForReview} data-testid="composer-submit-review" className="inline-flex items-center gap-1 text-[12px] uppercase tracking-[0.14em] px-2.5 py-1 border border-[var(--ink)] text-[var(--ink)] hover:bg-[var(--ink)] hover:text-[var(--parchment-light)]">
                <FileText className="w-3.5 h-3.5" /> Submit for review
              </button>
            )}
            {lifecycle === "in_review" && (
              <button onClick={approve} data-testid="composer-approve" className="inline-flex items-center gap-1 text-[12px] uppercase tracking-[0.14em] px-2.5 py-1 border border-emerald-700 text-emerald-700 hover:bg-emerald-700 hover:text-[var(--parchment-light)]">
                <CheckCircle2 className="w-3.5 h-3.5" /> Approve
              </button>
            )}
            {lifecycle === "approved" && (
              <button onClick={send} data-testid="composer-send" className="inline-flex items-center gap-1 text-[12px] uppercase tracking-[0.14em] px-2.5 py-1 border border-[var(--oxblood)] text-[var(--oxblood)] hover:bg-[var(--oxblood)] hover:text-[var(--parchment-light)]">
                <Send className="w-3.5 h-3.5" /> Send via Resend
              </button>
            )}
            {lifecycle === "sent" && (
              <span className="text-[11px] uppercase tracking-[0.14em] text-[var(--ink)]">Sent · ledger updated</span>
            )}
          </div>
        </header>

        {readOnly && (
          <p className="text-[12px] text-[var(--graphite)] italic mb-3">
            This artefact is no longer editable in {STATE_LABELS[lifecycle]?.label}. Reject from Daily Review to return it to draft.
          </p>
        )}

        {/* Block list */}
        <div className="space-y-3" data-testid="composer-block-list">
          {blocks.map((b, i) => {
            const isSlideStart = kind === "deck" && b.kind === "heading" && (b.content?.level || 2) === 1;
            const slideIdxFromStart = slideStarts.indexOf(i) + 1;
            return (
              <div
                key={b.id}
                id={isSlideStart ? `slide-${slideIdxFromStart}` : undefined}
                className={`group relative ${isSlideStart ? "border-t-2 border-[var(--ink)] pt-4 mt-2" : ""}`}
                data-testid={`block-${b.kind}`}
              >
                {!readOnly && (
                  <div className="absolute -left-9 top-0 hidden group-hover:flex flex-col items-center gap-0.5">
                    <button onClick={() => moveBlock(b.id, "up")} aria-label="Move up" className="text-[var(--graphite)] hover:text-[var(--ink)] p-0.5"><ChevronUp className="w-3.5 h-3.5" /></button>
                    <button onClick={() => moveBlock(b.id, "down")} aria-label="Move down" className="text-[var(--graphite)] hover:text-[var(--ink)] p-0.5"><ChevronDown className="w-3.5 h-3.5" /></button>
                    <button onClick={() => deleteBlock(b.id)} aria-label="Delete block" className="text-[var(--graphite)] hover:text-[var(--oxblood)] p-0.5"><Trash2 className="w-3.5 h-3.5" /></button>
                  </div>
                )}
                {b.kind === "heading"        && <HeadingBlock        content={b.content} onChange={onBlockChange(b.id)} readOnly={readOnly} />}
                {b.kind === "paragraph"      && <ParagraphBlock      content={b.content} onChange={onBlockChange(b.id)} readOnly={readOnly} />}
                {b.kind === "bulleted_list"  && <BulletedListBlock   content={b.content} onChange={onBlockChange(b.id)} readOnly={readOnly} />}
                {b.kind === "callout"        && <CalloutBlock        content={b.content} onChange={onBlockChange(b.id)} readOnly={readOnly} />}
                {b.kind === "citation"       && <CitationBlock       content={b.content} onChange={onBlockChange(b.id)} readOnly={readOnly} documents={documents} />}
                {b.kind === "signal_card"    && <SignalCardBlock     content={b.content} onChange={onBlockChange(b.id)} readOnly={readOnly} signals={signals} />}
                {b.kind === "divider"        && <DividerBlock />}
                {b.kind === "table"          && <TableBlock          content={b.content} onChange={onBlockChange(b.id)} readOnly={readOnly} />}
                {b.kind === "image"          && <ImageBlock          content={b.content} onChange={onBlockChange(b.id)} readOnly={readOnly} onUpload={uploadImage} />}

                {!readOnly && (
                  <div className="opacity-0 group-hover:opacity-100 mt-1 transition-opacity">
                    <button
                      type="button"
                      data-testid={`block-insert-after-${b.id}`}
                      onClick={(e) => openSlashMenuAt(e, b.id)}
                      className="inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.14em] text-[var(--graphite)] hover:text-[var(--ink)]"
                    >
                      <Plus className="w-3 h-3" /> Insert
                    </button>
                  </div>
                )}
              </div>
            );
          })}

          {!readOnly && (
            <div className="pt-3 border-t border-dashed border-[var(--graphite-light)]">
              <button
                type="button"
                data-testid="composer-add-block"
                onClick={(e) => openSlashMenuAt(e, null)}
                className="inline-flex items-center gap-1 text-[12px] uppercase tracking-[0.14em] px-2 py-1 border border-[var(--ink)] text-[var(--ink)] hover:bg-[var(--ink)] hover:text-[var(--parchment-light)]"
              >
                <Plus className="w-3.5 h-3.5" /> Add block · or press &quot;/&quot;
              </button>
            </div>
          )}
        </div>

        <SlashMenu
          open={slashOpen}
          query={slashQuery}
          anchorRect={slashAnchor}
          onPick={onSlashPick}
          onClose={() => setSlashOpen(false)}
        />
      </div>
      {/* Phase 12.2 ITEM C — Synisense preview drawer. Mounted at the
          top level so it overlays the composer regardless of inner
          state. Renders the original concatenated block text with
          highlighted spans. */}
      <PreviewDrawer
        open={!!synPreview}
        kind={kind}
        artefactId={artefactId}
        originalText={(blocks || []).map((b) => (b?.content?.text ?? b?.content?.markdown ?? b?.content?.body ?? "")).filter(Boolean).join("\n\n")}
        spans={synPreview?.spans || []}
        stats={synPreview?.stats || {}}
        hasNewSensitiveContent={synDrawerReopen}
        onAccepted={() => {
          setSynPreview(null);
          setSynDrawerReopen(false);
          toast.success("Screening accepted. Subsequent saves are silent.");
        }}
        onCancel={() => {
          setSynPreview(null);
          setSynDrawerReopen(false);
        }}
      />
    </div>
  );
}
