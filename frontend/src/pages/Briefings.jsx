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
  AlertTriangle, TrendingUp, CircleSlash, ShieldCheck, ArrowRight, Share2,
  Check, Eye,
} from "lucide-react";
import { Link } from "react-router-dom";
import CommentThread from "@/components/collab/CommentThread";
import CompositionStrip from "@/components/trace/CompositionStrip";
import ShareModal from "@/components/share/ShareModal";

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

/** Render text with inline [doc:xxx] citations as footnote chips.
 *  Handles `[doc:xxx]` and `[doc:xxx, doc:yyy]` patterns. */
function withCitations(text, sourceMap) {
  if (!text) return null;
  const BLOCK = /\[doc:[a-f0-9-]+(?:[,\s]+doc:[a-f0-9-]+)*\]/g;
  const ID = /[a-f0-9-]{8,}/g;
  const parts = text.split(BLOCK);
  const matches = text.match(BLOCK) || [];
  const out = [];
  parts.forEach((p, i) => {
    if (p) out.push(<span key={`p-${i}`}>{p}</span>);
    if (matches[i]) {
      const ids = matches[i].match(ID) || [];
      ids.forEach((id, j) => {
        const idx = sourceMap.get(id);
        if (idx) {
          out.push(
            <sup
              key={`c-${i}-${j}`}
              className="inline-flex items-center text-[10px] font-bold text-[var(--accent)] mx-0.5"
              title={sourceMap.get(`${id}:name`)}
            >
              [{idx}]
            </sup>
          );
        }
      });
    }
  });
  return out;
}

function BriefingViewer({ briefing, onArchive, onDraftNotes, notesDrafting, onShare, onMarkRead }) {
  // Build stable citation-to-footnote map from all items+opening
  const { sourceMap, orderedIds, docById } = useMemo(() => {
    const ids = [];
    const collect = (t) => {
      (t || "").replace(/\[doc:[a-f0-9-]+(?:[,\s]+doc:[a-f0-9-]+)*\]/g, (block) => {
        (block.match(/[a-f0-9-]{8,}/g) || []).forEach((d) => {
          if (!ids.includes(d)) ids.push(d);
        });
        return block;
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

  // Scroll-depth tracking — auto mark-as-read when the user reaches ≥70% of
  // the article. The user feedback was explicit: "Without a real signal,
  // the read/unread status is meaningless." 70% is a defensible threshold —
  // they've passed the body of the brief but maybe not the closing CTA.
  const articleRef = React.useRef(null);
  const autoMarkedRef = React.useRef(false);
  React.useEffect(() => {
    autoMarkedRef.current = false;  // reset on briefing change
  }, [briefing.id]);
  React.useEffect(() => {
    if (briefing.is_read || autoMarkedRef.current) return;
    const onScroll = () => {
      const el = articleRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const total = el.scrollHeight;
      const seen = window.innerHeight - rect.top;
      const pct = total > 0 ? seen / total : 0;
      if (pct >= 0.7) {
        autoMarkedRef.current = true;
        onMarkRead && onMarkRead(briefing, "scroll");
      }
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [briefing, onMarkRead]);

  return (
    <article
      ref={articleRef}
      className="bg-white border border-[#E1E6ED] rounded-sm" data-testid={`briefing-${briefing.id}`}>
      {/* Journey block — what am I being briefed on, why, what next?
          Sits at the very top so the user is grounded BEFORE they read.
          (Per user feedback: the page used to land on populated content
          with no context — this answers Before / During / After.) */}
      <section className="px-8 pt-6 pb-5 border-b border-[#E1E6ED] bg-[var(--cream-deep)]/40" data-testid="briefing-journey">
        <p className="akki-overline mb-3">Briefing · what you're walking into</p>
        <dl className="grid grid-cols-1 md:grid-cols-3 gap-x-6 gap-y-3 text-[12.5px]">
          <div>
            <dt className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono mb-1">What this is about</dt>
            <dd className="text-[var(--ink)] akki-serif leading-snug">
              {briefing.title}
            </dd>
          </div>
          <div>
            <dt className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono mb-1">Cycle / company</dt>
            <dd className="text-[var(--deep)] leading-snug">
              {briefing.context_name}
              {briefing.committee_name && <> · {briefing.committee_name}</>}
              <br />
              <span className="text-[11px] text-[var(--muted)]">
                Composed {formatDate(briefing.created_at)}
              </span>
            </dd>
          </div>
          <div>
            <dt className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono mb-1">What you should do after</dt>
            <dd className="text-[var(--deep)] leading-snug">
              Walk in with the {briefing.items?.length || 0} item{(briefing.items?.length || 0) === 1 ? "" : "s"} below in mind.
              Each carries the question to put to management.
            </dd>
          </div>
        </dl>
      </section>

      {/* Header */}
      <header className="px-8 py-6 border-b border-[#E1E6ED]">
        <div className="flex items-baseline justify-between gap-4 mb-3">
          <p className="akki-overline">PRIVATE · AKKI BRIEFING · v{briefing.version}</p>
          <div className="flex items-center gap-1">
            {/* Read state — explicit "Mark as read" toggle, plus a small
                badge once read. This was a real gap: the rail showed
                "X unread" but there was no way for the user to actually
                signal they'd read one. */}
            {briefing.is_read ? (
              <span
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs text-emerald-700 border border-emerald-200 bg-emerald-50"
                data-testid="briefing-read-badge"
                title={`Read ${briefing.read_via === "scroll" ? "via scroll" : "manually"}${briefing.read_at ? ` · ${formatDate(briefing.read_at)}` : ""}`}
              >
                <Check className="w-3 h-3" /> Read
              </span>
            ) : (
              <button
                type="button"
                onClick={() => onMarkRead && onMarkRead(briefing, "manual")}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs text-slate-700 border border-[#E1E6ED] hover:bg-slate-50 hover:border-[var(--accent)]/50 transition-colors"
                data-testid="briefing-mark-read-btn"
                title="Stamp as read"
              >
                <Eye className="w-3 h-3" /> Mark as read
              </button>
            )}
            {/* Briefing slim-down (iter32): "Draft speaking notes" and
                "Board deck" buttons are migrated to Reports. The briefing
                stays as a one-pager — PDF + email send only. */}
            <a
              href={downloadUrl("pdf")} target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs text-slate-700 border border-[#E1E6ED] hover:bg-slate-50 hover:border-[var(--accent)]/50 transition-colors"
              data-testid="briefing-export-pdf"
            >
              <Download className="w-3 h-3" /> PDF
            </a>
            <a
              href={downloadUrl("docx")} target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs text-slate-700 border border-[#E1E6ED] hover:bg-slate-50 hover:border-[var(--accent)]/50 transition-colors"
              data-testid="briefing-export-docx"
            >
              <Download className="w-3 h-3" /> DOCX
            </a>
            <button
              type="button"
              onClick={() => onShare && onShare(briefing)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs text-slate-700 border border-[#E1E6ED] hover:bg-slate-50 hover:border-[var(--accent)]/50 transition-colors"
              data-testid="briefing-share-btn"
              title="Share this briefing with a colleague"
            >
              <Share2 className="w-3 h-3" /> Share
            </button>
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
        <h1 className="text-2xl font-light tracking-tight text-[var(--ink)] mb-2">{briefing.title}</h1>
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
              <h3 className="text-base font-medium text-[var(--ink)] tracking-tight mb-2">{it.signal_headline}</h3>
              {it.evidence && (
                <p className="text-[13.5px] text-slate-700 leading-[1.7] mb-3 whitespace-pre-wrap">
                  {withCitations(it.evidence, sourceMap)}
                </p>
              )}
              {it.question && (
                <div className="border-l-2 border-[var(--accent)] pl-4 py-1">
                  <p className="text-[10px] uppercase tracking-wider text-[var(--accent)] font-semibold mb-1">Ask</p>
                  <p className="text-[14px] italic text-[var(--ink)] leading-relaxed">
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
                  className="flex items-center gap-2 text-[12px] text-slate-600 hover:text-[var(--ink)] transition-colors group"
                  data-testid={`briefing-source-${did}`}
                >
                  <span className="text-[10px] font-bold text-[var(--accent)] tabular-nums w-5">[{i + 1}]</span>
                  <FileText className="w-3 h-3 text-[var(--accent)] shrink-0" />
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

      <CompositionStrip artefact={briefing} kind="briefing" />
      <CommentThread artefactType="briefing" artefactId={briefing.id} />
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
  const [committeeFilter, setCommitteeFilter] = useState("all");
  const committees = activeContext?.committees || [];

  const visibleList = useMemo(() => {
    if (committeeFilter === "all") return list;
    return list.filter((b) => b.committee_id === committeeFilter);
  }, [list, committeeFilter]);

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

  const [notesDrafting, setNotesDrafting] = useState(false);
  const [shareOn, setShareOn] = useState(null);
  const onMarkRead = useCallback(async (briefing, via = "manual") => {
    if (!briefing || briefing.is_read) return;
    try {
      await api.post(
        `/contexts/${contextId}/briefings/${briefing.id}/mark-read`,
        { via },
      );
      // Optimistic local update — both list + selected
      setList((prev) => prev.map((x) => x.id === briefing.id
        ? { ...x, is_read: true, read_via: via, read_at: new Date().toISOString() }
        : x));
      setSelected((prev) => prev && prev.id === briefing.id
        ? { ...prev, is_read: true, read_via: via, read_at: new Date().toISOString() }
        : prev);
      if (via === "manual") toast.success("Marked as read.");
    } catch { /* silent — UI stays unchanged */ }
  }, [contextId]);
  const onDraftNotes = async (b) => {
    setNotesDrafting(true);
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/briefings/${b.id}/speaking-notes`,
        {},
        { timeout: 120000 }
      );
      const updated = data.briefing;
      toast.success(
        `Speaking notes ready — ${data.items_narrated} item${data.items_narrated === 1 ? "" : "s"} narrated.`,
        { description: "They now appear under each slide in your Board deck." }
      );
      // Update list + selected with the freshly-narrated briefing
      setList((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
      setSelected(updated);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setNotesDrafting(false); }
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
            <p className="akki-overline mb-1">Briefings</p>
            <h1 className="text-lg font-medium tracking-tight text-[var(--ink)]">Your 90-second pre-meeting one-pagers</h1>
            <p className="text-[12px] text-[var(--muted)] italic mt-1 max-w-2xl leading-relaxed">
              A briefing is what you read in the lift before the room. The three things to raise. Cited to the document. Not the long-form discussion paper — that's <Link to="/app/cycle?tab=reports" className="text-[var(--accent)] hover:underline">Reports</Link>.
            </p>
            <p className="text-[11px] text-slate-500 mt-1">{visibleList.length} in {activeContext.name}
              {committeeFilter !== "all" && ` · ${committees.find((c) => c.id === committeeFilter)?.name}`}
              {visibleList.length > 0 && (() => {
                const unread = visibleList.filter((b) => !b.is_read).length;
                return unread > 0
                  ? <span className="ml-1.5 text-[var(--accent)]" data-testid="briefings-unread-count">· {unread} unread</span>
                  : <span className="ml-1.5 text-emerald-700" data-testid="briefings-all-read">· all read</span>;
              })()}
            </p>
            {committees.length > 0 && (
              <select
                value={committeeFilter}
                onChange={(e) => setCommitteeFilter(e.target.value)}
                className="mt-3 w-full text-[11px] border border-[var(--rule)] rounded-sm bg-white px-2 py-1.5 text-[var(--deep)] focus:outline-none focus:border-[var(--accent)]"
                data-testid="briefing-committee-filter"
              >
                <option value="all">Full board</option>
                {committees.map((cm) => (
                  <option key={cm.id} value={cm.id}>{cm.name}</option>
                ))}
              </select>
            )}
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
              className="w-full bg-[var(--accent)] hover:bg-[var(--accent)] text-[var(--ink)] rounded-sm h-9 font-medium text-sm"
              data-testid="briefing-create-btn"
            >
              {creating ? <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" /> Composing…</>
                : <><Sparkles className="w-3.5 h-3.5 mr-2" /> New briefing</>}
            </Button>
            {creating && stage && (
              <div className="text-[11px] text-slate-500 italic bg-[var(--accent)]/5 border border-[var(--accent)]/20 rounded-sm px-2 py-1.5 flex items-center gap-1.5" data-testid="briefing-stage">
                <Loader2 className="w-3 h-3 animate-spin text-[var(--accent)] shrink-0" />
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
            ) : visibleList.length === 0 ? (
              <div className="p-6 text-center" data-testid="briefings-empty">
                <ScrollText className="w-8 h-8 text-slate-300 mx-auto mb-3" strokeWidth={1.3} />
                <p className="text-xs text-slate-500 mb-2">
                  {committeeFilter === "all" ? "No briefings yet" : "None for this committee"}
                </p>
                <p className="text-[10.5px] text-slate-400 leading-relaxed max-w-[220px] mx-auto">
                  Generate signals from the Signals page first, then compose your first briefing here.
                </p>
                <Link
                  to="/app/highlights"
                  className="text-[11px] text-[var(--accent)] hover:underline inline-flex items-center gap-1 mt-3"
                >
                  Open Signals <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
            ) : (
              <div className="p-2">
                {visibleList.map((b) => {
                  const active = selectedId === b.id;
                  return (
                    <button
                      key={b.id}
                      onClick={() => { setSelectedId(b.id); setSelected(b); }}
                      className={`w-full text-left px-3 py-3 rounded-sm mb-1 transition-colors ${
                        active ? "bg-white border border-[var(--accent)]/60" : "hover:bg-white border border-transparent"
                      }`}
                      data-testid={`briefing-list-${b.id}`}
                    >
                      <div className="flex items-center gap-1.5 mb-1">
                        <span className="text-[10px] font-mono text-[var(--accent)]">v{b.version}</span>
                        <span className="text-[10px] text-slate-400">·</span>
                        <span className="text-[10px] uppercase tracking-wider text-slate-400">{b.role}</span>
                        {b.is_read ? (
                          <span className="ml-auto inline-flex items-center gap-0.5 text-[10px] text-emerald-700" title="Read">
                            <Check className="w-3 h-3" />
                          </span>
                        ) : (
                          <span className="ml-auto w-1.5 h-1.5 rounded-full bg-[var(--accent)]" title="Unread" />
                        )}
                      </div>
                      <p className={`text-[13px] font-medium leading-snug line-clamp-2 ${active ? "text-[var(--ink)]" : "text-slate-700"}`}>
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
                <Loader2 className="w-8 h-8 animate-spin text-[var(--accent)] mx-auto mb-4" />
                <p className="text-sm text-slate-600 mb-1 font-medium">Composing your briefing…</p>
                <p className="text-xs text-slate-500 italic">{stage || "Working…"}</p>
              </div>
            ) : selected ? (
              <BriefingViewer
                briefing={selected}
                onArchive={onArchive}
                onDraftNotes={onDraftNotes}
                notesDrafting={notesDrafting}
                onShare={setShareOn}
                onMarkRead={onMarkRead}
              />
            ) : list.length === 0 && !loading ? (
              <div className="bg-white border border-[#E1E6ED] rounded-sm p-16 text-center" data-testid="briefings-splash">
                <ScrollText className="w-12 h-12 text-slate-300 mx-auto mb-5" strokeWidth={1.2} />
                <h2 className="text-xl font-medium text-[var(--ink)] tracking-tight mb-2">
                  No briefings yet for {activeContext.name}
                </h2>
                <p className="text-sm text-slate-500 max-w-md mx-auto mb-6 leading-relaxed">
                  A briefing is a 1–2 page printable document — opening paragraph, each signal with evidence, and the one question you should ask in the meeting.
                </p>
                <Button
                  onClick={onCreate}
                  disabled={creating}
                  className="bg-[var(--accent)] hover:bg-[var(--accent)] text-[var(--ink)] rounded-sm h-10 px-5 font-medium"
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

      <ShareModal
        open={!!shareOn}
        onClose={() => setShareOn(null)}
        contextId={contextId}
        itemType="briefing"
        item={shareOn ? { ...shareOn, context_name: activeContext?.name } : null}
      />
    </AppShell>
  );
}
