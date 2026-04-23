import React, { useCallback, useEffect, useMemo, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage, API_BASE } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import {
  ScrollText, FileText, Download, Loader2, Sparkles, Plus, Trash2,
  AlertTriangle, TrendingUp, CircleSlash, ShieldCheck, ArrowRight,
} from "lucide-react";
import { Link } from "react-router-dom";

const TYPE_CFG = {
  risk:        { icon: AlertTriangle, cls: "bg-red-50 text-red-700 border-red-200" },
  opportunity: { icon: TrendingUp,    cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  gap:         { icon: CircleSlash,   cls: "bg-amber-50 text-amber-700 border-amber-200" },
};
const TRUST = {
  trusted: "text-emerald-700", mixed: "text-amber-700", weak: "text-red-700", unrated: "text-slate-500",
};
function formatDate(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); }
  catch { return iso; }
}

/** Render text with inline [doc:xxx] citations as footnote chips */
function withCitations(text, sourceMap) {
  if (!text) return null;
  const parts = text.split(/(\[doc:[a-f0-9-]+\])/g);
  return parts.map((p, i) => {
    const m = p.match(/^\[doc:([a-f0-9-]+)\]$/);
    if (!m) return <span key={i}>{p}</span>;
    const id = m[1];
    const idx = sourceMap.get(id);
    if (!idx) return null;
    return (
      <sup
        key={i}
        className="inline-flex items-center text-[10px] font-bold text-[#C9A961] mx-0.5"
        title={sourceMap.get(`${id}:name`)}
      >
        [{idx}]
      </sup>
    );
  });
}

function BriefingViewer({ briefing, onArchive }) {
  // Build stable citation-to-footnote map from all items+opening
  const { sourceMap, orderedIds, docById } = useMemo(() => {
    const ids = [];
    const collect = (t) => {
      (t || "").replace(/\[doc:([a-f0-9-]+)\]/g, (_, d) => {
        if (!ids.includes(d)) ids.push(d);
      });
    };
    collect(briefing.opening_paragraph);
    (briefing.items || []).forEach((it) => { collect(it.evidence); collect(it.question); });
    const docById = new Map();
    (briefing.items || []).forEach((it) => {
      (it.sources || []).forEach((s) => docById.set(s.doc_id, s));
    });
    const map = new Map();
    ids.forEach((d, i) => {
      map.set(d, i + 1);
      const docName = docById.get(d)?.doc_name || d.slice(0, 8);
      map.set(`${d}:name`, docName);
    });
    return { sourceMap: map, orderedIds: ids, docById };
  }, [briefing]);

  const downloadUrl = (fmt) =>
    `${API_BASE}/contexts/${briefing.context_id}/briefings/${briefing.id}/export?fmt=${fmt}`;

  return (
    <article className="bg-white border border-[#E1E6ED] rounded-sm" data-testid={`briefing-${briefing.id}`}>
      {/* Header */}
      <header className="px-8 py-6 border-b border-[#E1E6ED]">
        <div className="flex items-baseline justify-between gap-4 mb-3">
          <p className="akki-overline">PRIVATE · AKKI BRIEFING · v{briefing.version}</p>
          <div className="flex items-center gap-1">
            <a
              href={downloadUrl("pdf")} target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs text-slate-700 border border-[#E1E6ED] hover:bg-slate-50 hover:border-[#C9A961]/50 transition-colors"
              data-testid="briefing-export-pdf"
            >
              <Download className="w-3 h-3" /> PDF
            </a>
            <a
              href={downloadUrl("docx")} target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs text-slate-700 border border-[#E1E6ED] hover:bg-slate-50 hover:border-[#C9A961]/50 transition-colors"
              data-testid="briefing-export-docx"
            >
              <Download className="w-3 h-3" /> DOCX
            </a>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <button
                  className="p-1.5 text-slate-400 hover:text-red-600 transition-colors rounded-sm"
                  data-testid="briefing-archive-btn"
                  title="Archive"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </AlertDialogTrigger>
              <AlertDialogContent className="rounded-sm">
                <AlertDialogHeader>
                  <AlertDialogTitle>Archive this briefing?</AlertDialogTitle>
                  <AlertDialogDescription>
                    The briefing will be hidden from your list. Previously exported copies are unaffected.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel className="rounded-sm">Cancel</AlertDialogCancel>
                  <AlertDialogAction className="bg-red-600 hover:bg-red-700 rounded-sm" onClick={() => onArchive(briefing)}>
                    Archive
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
        <h1 className="text-2xl font-light tracking-tight text-[#0A1F44] mb-2">{briefing.title}</h1>
        <p className="text-[11px] text-slate-500">
          {briefing.context_name} · {formatDate(briefing.created_at)} · {briefing.items?.length || 0} items · role: {briefing.role}
          <span className={`ml-2 uppercase tracking-wider ${TRUST[briefing.data_trust] || TRUST.unrated}`}>
            <ShieldCheck className="w-3 h-3 inline mr-0.5" />
            data trust: {briefing.data_trust}
          </span>
        </p>
      </header>

      {/* Opening */}
      {briefing.opening_paragraph && (
        <div className="px-8 pt-6 pb-2 text-[14.5px] text-slate-700 leading-[1.7] whitespace-pre-wrap">
          {withCitations(briefing.opening_paragraph, sourceMap)}
        </div>
      )}

      {/* Items */}
      <div className="px-8 pb-4">
        {(briefing.items || []).map((it, i) => {
          const T = TYPE_CFG[it.signal_type] || TYPE_CFG.risk;
          const I = T.icon;
          return (
            <section
              key={it.signal_id}
              className="py-5 border-t border-[#E1E6ED] first:border-t-0"
              data-testid={`briefing-item-${i}`}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[10px] font-mono text-slate-400 tabular-nums">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[10px] font-medium uppercase tracking-wider border ${T.cls}`}>
                  <I className="w-3 h-3" />
                  {it.signal_type}
                </span>
                <span className="text-[10px] uppercase tracking-wider text-slate-400">{it.confidence} confidence</span>
              </div>
              <h3 className="text-base font-medium text-[#0A1F44] tracking-tight mb-2">{it.signal_headline}</h3>
              {it.evidence && (
                <p className="text-[13.5px] text-slate-700 leading-[1.7] mb-3 whitespace-pre-wrap">
                  {withCitations(it.evidence, sourceMap)}
                </p>
              )}
              {it.question && (
                <div className="border-l-2 border-[#C9A961] pl-4 py-1">
                  <p className="text-[10px] uppercase tracking-wider text-[#C9A961] font-semibold mb-1">Ask</p>
                  <p className="text-[14px] italic text-[#0A1F44] leading-relaxed">
                    {withCitations(it.question, sourceMap)}
                  </p>
                </div>
              )}
            </section>
          );
        })}
      </div>

      {/* Closing */}
      {briefing.closing_note && (
        <div className="px-8 py-5 border-t border-[#E1E6ED] bg-slate-50/40">
          <p className="text-[13.5px] italic text-slate-700 leading-[1.7]">{briefing.closing_note}</p>
        </div>
      )}

      {/* Sources footer */}
      {orderedIds.length > 0 && (
        <footer className="px-8 py-5 border-t border-[#E1E6ED] bg-slate-50/60">
          <p className="akki-overline mb-3">Sources</p>
          <div className="space-y-1">
            {orderedIds.map((did, i) => {
              const doc = docById.get(did);
              return (
                <Link
                  key={did}
                  to={`/app/documents/${did}`}
                  className="flex items-center gap-2 text-[12px] text-slate-600 hover:text-[#0A1F44] transition-colors group"
                  data-testid={`briefing-source-${did}`}
                >
                  <span className="text-[10px] font-bold text-[#C9A961] tabular-nums w-5">[{i + 1}]</span>
                  <FileText className="w-3 h-3 text-[#C9A961] shrink-0" />
                  <span className="truncate group-hover:underline">{doc?.doc_name || did}</span>
                  <span className={`ml-auto text-[10px] uppercase tracking-wider ${TRUST[doc?.data_trust] || TRUST.unrated}`}>
                    {doc?.data_trust || "unrated"}
                  </span>
                </Link>
              );
            })}
          </div>
        </footer>
      )}
    </article>
  );
}

export default function Briefings() {
  const { activeContext } = useAuth();
  const contextId = activeContext?.id;

  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [selected, setSelected] = useState(null);
  const [creating, setCreating] = useState(false);
  const [stage, setStage] = useState("");
  const [title, setTitle] = useState("");

  const load = useCallback(async () => {
    if (!contextId) return;
    try {
      const { data } = await api.get(`/contexts/${contextId}/briefings`);
      setList(data);
      if (data.length > 0 && !selectedId) {
        setSelectedId(data[0].id);
        setSelected(data[0]);
      }
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [contextId, selectedId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    // Hydrate selection when selectedId changes and we don't have the full doc
    if (!selectedId) { setSelected(null); return; }
    const already = list.find((b) => b.id === selectedId);
    if (already) setSelected(already);
  }, [selectedId, list]);

  const onCreate = async () => {
    setCreating(true);
    setStage("Gathering your active signals…");
    const timers = [
      setTimeout(() => setStage("Drafting opening paragraph in AKKI's advisor voice…"), 6000),
      setTimeout(() => setStage("Writing evidence and the question you should ask…"), 16000),
      setTimeout(() => setStage("Still working — polishing the brief…"), 32000),
    ];
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/briefings`,
        { title: title.trim() || null },
        { timeout: 120000 }
      );
      toast.success(`Briefing v${data.version} ready`);
      setTitle("");
      setSelectedId(data.id);
      setSelected(data);
      await load();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      timers.forEach(clearTimeout);
      setStage("");
      setCreating(false);
    }
  };

  const onArchive = async (b) => {
    try {
      await api.delete(`/contexts/${contextId}/briefings/${b.id}`);
      toast.success("Briefing archived");
      setList((prev) => prev.filter((x) => x.id !== b.id));
      if (selectedId === b.id) { setSelectedId(null); setSelected(null); }
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  if (!contextId) {
    return <AppShell><div className="p-12 text-center text-slate-500 text-sm">No context selected.</div></AppShell>;
  }

  return (
    <AppShell>
      <div className="max-w-[1400px] mx-auto grid grid-cols-1 lg:grid-cols-[280px_1fr] min-h-[calc(100vh-4rem)]">
        {/* LEFT RAIL — list */}
        <aside className="border-r border-[#E1E6ED] bg-slate-50/50 flex flex-col" data-testid="briefings-rail">
          <div className="px-5 py-5 border-b border-[#E1E6ED] bg-white">
            <p className="akki-overline mb-1">Briefings · Module M12</p>
            <h1 className="text-lg font-medium tracking-tight text-[#0A1F44]">Your briefings</h1>
            <p className="text-[11px] text-slate-500 mt-1">{list.length} in {activeContext.name}</p>
          </div>

          <div className="px-4 py-4 border-b border-[#E1E6ED] bg-white space-y-2">
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Title (optional — AKKI will suggest one)"
              className="rounded-sm h-8 text-xs"
              disabled={creating}
              data-testid="briefing-title-input"
            />
            <Button
              onClick={onCreate}
              disabled={creating}
              className="w-full bg-[#C9A961] hover:bg-[#B39556] text-[#0A1F44] rounded-sm h-9 font-medium text-sm"
              data-testid="briefing-create-btn"
            >
              {creating ? <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" /> Composing…</>
                : <><Sparkles className="w-3.5 h-3.5 mr-2" /> New briefing</>}
            </Button>
            {creating && stage && (
              <div className="text-[11px] text-slate-500 italic bg-[#C9A961]/5 border border-[#C9A961]/20 rounded-sm px-2 py-1.5 flex items-center gap-1.5" data-testid="briefing-stage">
                <Loader2 className="w-3 h-3 animate-spin text-[#C9A961] shrink-0" />
                <span className="flex-1 truncate">{stage}</span>
              </div>
            )}
            <p className="text-[10px] text-slate-400 leading-relaxed">
              A briefing bundles your active signals into a printable 1–2 page document with the question to ask for each.
            </p>
          </div>

          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="p-6 text-center text-xs uppercase tracking-widest text-slate-400">Loading…</div>
            ) : list.length === 0 ? (
              <div className="p-6 text-center" data-testid="briefings-empty">
                <ScrollText className="w-8 h-8 text-slate-300 mx-auto mb-3" strokeWidth={1.3} />
                <p className="text-xs text-slate-500 mb-2">No briefings yet</p>
                <p className="text-[10.5px] text-slate-400 leading-relaxed max-w-[220px] mx-auto">
                  Generate signals from Highlights first, then compose your first briefing here.
                </p>
                <Link
                  to="/app/highlights"
                  className="text-[11px] text-[#C9A961] hover:underline inline-flex items-center gap-1 mt-3"
                >
                  Open Highlights <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
            ) : (
              <div className="p-2">
                {list.map((b) => {
                  const active = selectedId === b.id;
                  return (
                    <button
                      key={b.id}
                      onClick={() => { setSelectedId(b.id); setSelected(b); }}
                      className={`w-full text-left px-3 py-3 rounded-sm mb-1 transition-colors ${
                        active ? "bg-white border border-[#C9A961]/60" : "hover:bg-white border border-transparent"
                      }`}
                      data-testid={`briefing-list-${b.id}`}
                    >
                      <div className="flex items-center gap-1.5 mb-1">
                        <span className="text-[10px] font-mono text-[#C9A961]">v{b.version}</span>
                        <span className="text-[10px] text-slate-400">·</span>
                        <span className="text-[10px] uppercase tracking-wider text-slate-400">{b.role}</span>
                      </div>
                      <p className={`text-[13px] font-medium leading-snug line-clamp-2 ${active ? "text-[#0A1F44]" : "text-slate-700"}`}>
                        {b.title}
                      </p>
                      <p className="text-[10px] text-slate-400 mt-1.5">
                        {b.items?.length || 0} items · {formatDate(b.created_at)}
                      </p>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </aside>

        {/* RIGHT — detail */}
        <main className="bg-[#FAFBFC] overflow-y-auto" data-testid="briefing-detail">
          <div className="max-w-3xl mx-auto py-8 px-6">
            {creating && !selected ? (
              <div className="bg-white border border-[#E1E6ED] rounded-sm p-16 text-center">
                <Loader2 className="w-8 h-8 animate-spin text-[#C9A961] mx-auto mb-4" />
                <p className="text-sm text-slate-600 mb-1 font-medium">Composing your briefing…</p>
                <p className="text-xs text-slate-500 italic">{stage || "Working…"}</p>
              </div>
            ) : selected ? (
              <BriefingViewer briefing={selected} onArchive={onArchive} />
            ) : list.length === 0 && !loading ? (
              <div className="bg-white border border-[#E1E6ED] rounded-sm p-16 text-center" data-testid="briefings-splash">
                <ScrollText className="w-12 h-12 text-slate-300 mx-auto mb-5" strokeWidth={1.2} />
                <h2 className="text-xl font-medium text-[#0A1F44] tracking-tight mb-2">
                  No briefings yet for {activeContext.name}
                </h2>
                <p className="text-sm text-slate-500 max-w-md mx-auto mb-6 leading-relaxed">
                  A briefing is a 1–2 page printable document — opening paragraph, each signal with evidence, and the one question you should ask in the meeting.
                </p>
                <Button
                  onClick={onCreate}
                  disabled={creating}
                  className="bg-[#C9A961] hover:bg-[#B39556] text-[#0A1F44] rounded-sm h-10 px-5 font-medium"
                >
                  <Sparkles className="w-4 h-4 mr-2" /> Compose first briefing
                </Button>
              </div>
            ) : (
              <div className="p-16 text-center text-sm text-slate-500">
                Select a briefing from the left.
              </div>
            )}
          </div>
        </main>
      </div>
    </AppShell>
  );
}
