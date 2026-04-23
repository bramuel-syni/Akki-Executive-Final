import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage, API_BASE } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  ArrowLeft, Download, FileText, ShieldCheck, Loader2, List, AlertTriangle,
} from "lucide-react";

const TRUST_STYLE = {
  trusted: "text-emerald-700 bg-emerald-50 border-emerald-200",
  mixed:   "text-amber-700 bg-amber-50 border-amber-200",
  weak:    "text-red-700 bg-red-50 border-red-200",
};

function formatSize(b) {
  if (b == null) return "—";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

/** Parse extracted plain text into a rough outline + paragraphs.
 *  Heuristic: short lines (<= 80 chars) that are followed by at least one longer line,
 *  or lines written in UPPER CASE, become headings. */
function parseOutline(text) {
  if (!text) return { items: [] };
  const lines = text.split(/\n/);
  const items = [];
  let buf = [];
  const flushPara = () => {
    const joined = buf.join(" ").trim();
    if (joined) items.push({ type: "p", text: joined });
    buf = [];
  };
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const line = raw.trim();
    if (!line) { flushPara(); continue; }
    const isShort = line.length <= 80;
    const isUpper = line === line.toUpperCase() && /[A-Z]/.test(line);
    const startsNumbered = /^(\d+(\.\d+)*)\s+\S/.test(line);
    const next = (lines[i + 1] || "").trim();
    const nextLonger = next && next.length > 80;
    const isHeading =
      (isShort && (isUpper || startsNumbered || nextLonger)) && line.length > 2;
    if (isHeading) {
      flushPara();
      items.push({ type: "h", text: line, id: `h-${items.length}` });
    } else {
      buf.push(line);
    }
  }
  flushPara();
  return { items };
}

export default function DocumentViewer() {
  const { id: docId } = useParams();
  const navigate = useNavigate();
  const { activeContext } = useAuth();
  const contextId = activeContext?.id;

  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const bodyRef = useRef(null);

  const load = useCallback(async () => {
    if (!contextId || !docId) return;
    try {
      const { data } = await api.get(`/contexts/${contextId}/documents/${docId}`);
      setDoc(data);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [contextId, docId]);

  useEffect(() => { load(); }, [load]);

  const outline = useMemo(() => parseOutline(doc?.extracted_text), [doc]);
  const headings = outline.items.filter((x) => x.type === "h");

  const scrollTo = (id) => {
    const el = bodyRef.current?.querySelector(`[data-outline-id="${id}"]`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  if (!contextId) {
    return <AppShell><div className="p-12 text-center text-slate-500 text-sm">No context selected.</div></AppShell>;
  }

  return (
    <AppShell>
      <div className="h-[calc(100vh-4rem)] flex flex-col">
        {/* Top meta bar */}
        <div className="border-b border-[#E1E6ED] bg-white px-6 py-4 flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            className="rounded-sm h-8 px-2 text-slate-600 hover:text-[#0A1F44]"
            onClick={() => navigate(-1)}
            data-testid="doc-back-btn"
          >
            <ArrowLeft className="w-4 h-4 mr-1.5" /> Back
          </Button>
          <div className="flex-1 min-w-0">
            {loading ? (
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-[#C9A961]" /> Loading document…
              </div>
            ) : doc ? (
              <>
                <p className="akki-overline mb-0.5">Document · {activeContext?.name}</p>
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="text-xl font-light tracking-tight text-[#0A1F44] truncate" data-testid="doc-title">
                    {doc.name}
                  </h1>
                  <span className="text-[10px] font-mono text-slate-400 truncate">{doc.original_filename}</span>
                  {doc.data_trust && (
                    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[10px] font-medium uppercase tracking-wider border ${TRUST_STYLE[doc.data_trust] || TRUST_STYLE.mixed}`}>
                      <ShieldCheck className="w-3 h-3" /> {doc.data_trust}
                    </span>
                  )}
                  <span className="text-[10px] text-slate-500">{formatSize(doc.size_bytes)}</span>
                  <span className="text-[10px] text-slate-500">{(doc.extracted_chars || 0).toLocaleString()} chars</span>
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-500">Document not found</p>
            )}
          </div>
          {doc && (
            <a
              href={`${API_BASE}/contexts/${contextId}/documents/${doc.id}/download`}
              target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs text-slate-700 border border-[#E1E6ED] hover:bg-slate-50"
              data-testid="doc-download-btn"
            >
              <Download className="w-3.5 h-3.5" /> Download original
            </a>
          )}
        </div>

        {/* Body: content + outline */}
        <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-[1fr_280px]">
          <div
            ref={bodyRef}
            className="overflow-y-auto bg-white px-8 py-10"
            data-testid="doc-body"
          >
            <div className="max-w-3xl mx-auto">
              {loading ? (
                <div className="text-center py-20 text-xs uppercase tracking-widest text-slate-400">Loading…</div>
              ) : !doc ? (
                <div className="text-sm text-slate-500 p-8 text-center">Document not found.</div>
              ) : doc.error ? (
                <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-sm p-4 flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 mt-0.5 shrink-0" />
                  <div>
                    <p className="font-medium">Extraction failed</p>
                    <p className="mt-1 text-xs">{doc.error}</p>
                  </div>
                </div>
              ) : !doc.extracted_text ? (
                <div className="text-sm text-slate-400 italic text-center py-20">
                  No extracted text available for this document.
                </div>
              ) : (
                <article className="akki-doc">
                  {outline.items.map((it, i) =>
                    it.type === "h" ? (
                      <h2
                        key={i}
                        data-outline-id={it.id}
                        className="text-lg font-medium text-[#0A1F44] tracking-tight mt-8 mb-3 scroll-mt-6"
                      >
                        {it.text}
                      </h2>
                    ) : (
                      <p key={i} className="text-[15px] leading-[1.7] text-slate-700 mb-4 whitespace-pre-wrap">
                        {it.text}
                      </p>
                    )
                  )}
                </article>
              )}
            </div>
          </div>

          {/* Outline rail */}
          <aside
            className="hidden md:block border-l border-[#E1E6ED] bg-slate-50/50 overflow-y-auto"
            data-testid="doc-outline-rail"
          >
            <div className="px-4 py-5 sticky top-0 bg-slate-50/90 backdrop-blur-sm border-b border-[#E1E6ED]">
              <div className="flex items-center gap-2">
                <List className="w-3.5 h-3.5 text-[#C9A961]" />
                <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 font-semibold">Outline</p>
              </div>
            </div>
            <div className="p-2">
              {headings.length === 0 ? (
                <p className="text-[11px] text-slate-400 px-3 py-4">No headings detected.</p>
              ) : (
                headings.map((h) => (
                  <button
                    key={h.id}
                    onClick={() => scrollTo(h.id)}
                    className="w-full text-left px-3 py-2 text-[12px] text-slate-600 hover:bg-white hover:text-[#0A1F44] rounded-sm transition-colors border-l-2 border-transparent hover:border-[#C9A961]"
                    data-testid={`outline-${h.id}`}
                  >
                    <span className="line-clamp-2">{h.text}</span>
                  </button>
                ))
              )}
            </div>
            <div className="px-4 py-4 border-t border-[#E1E6ED]">
              <Link
                to="/app/ask"
                className="flex items-center gap-2 text-[11px] text-[#C9A961] hover:underline"
              >
                <FileText className="w-3 h-3" /> Ask about this document →
              </Link>
            </div>
          </aside>
        </div>
      </div>
    </AppShell>
  );
}
