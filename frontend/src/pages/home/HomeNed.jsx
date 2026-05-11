/**
 * HomeNed — Phase E NED Cycle Manager landing.
 *
 * Cross-board landing per spec §4. Four sections stacked vertically:
 *   1. This Week     — meetings within the next 7 days
 *   2. Next 2 Weeks  — meetings days 7–21 ahead
 *   3. Outstanding   — open follow-ups + meetings still in/post state
 *   4. Patterns worth knowing — proxies the E.0.3 cross-board aggregator
 *
 * Privacy contract: every list is account-scoped + Privacy Wall
 * projected; the Patterns section is the metadata-only aggregator
 * with no source-board names.
 *
 * Hard rule: zero LLM calls on this surface (read-only landing).
 */
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Calendar, FileText, Users, Plus, ChevronRight, Search,
  Loader2, MapPin, ListChecks, Globe2, Clock, ArrowRight,
} from "lucide-react";
import AcrossBoardsPanel from "@/components/pulse/AcrossBoardsPanel";
import NedInboxTile from "@/components/cycle/NedInboxTile";

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}
function fmtTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function MeetingCard({ meeting, boards, onClick }) {
  const board = boards.find((b) => b.id === meeting.context_id);
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full text-left border border-[var(--rule)] bg-white rounded-md px-4 py-3 hover:border-[var(--accent)] transition-colors group"
      data-testid={`ned-meeting-card-${meeting.id}`}
    >
      <div className="flex items-baseline justify-between gap-3 mb-1.5 flex-wrap">
        <p className="akki-serif text-[14.5px] text-[var(--ink)]">{meeting.title}</p>
        <p className="text-[11.5px] font-mono text-[var(--muted)]">{fmtDate(meeting.scheduled_at)} · {fmtTime(meeting.scheduled_at)}</p>
      </div>
      <p className="text-[12px] text-[var(--muted)] inline-flex items-center gap-2">
        <MapPin className="w-3 h-3" /> {board?.name || "—"} · <strong className="text-[var(--ink)] font-medium">{meeting.committee}</strong>
        {(meeting.paper_doc_ids?.length || 0) > 0 && (
          <> · <FileText className="w-3 h-3" /> {meeting.paper_doc_ids.length} paper{meeting.paper_doc_ids.length === 1 ? "" : "s"}</>
        )}
      </p>
      <p className="text-[11px] text-[var(--muted)] font-mono mt-1 inline-flex items-center gap-1">
        prep: {meeting.prep_state || "not_started"} · state: {meeting.state}
        <ChevronRight className="w-3 h-3 ml-auto opacity-0 group-hover:opacity-100" />
      </p>
    </button>
  );
}

function AddMeetingDialog({ open, onClose, boards, onCreated }) {
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    context_id: "", committee: "Audit",
    title: "", scheduled_at: "", paper_doc_ids: [],
  });
  const [docs, setDocs] = useState([]);
  useEffect(() => {
    if (open && boards[0]) setForm((f) => ({ ...f, context_id: boards[0].id }));
  }, [open, boards]);
  useEffect(() => {
    if (!form.context_id) { setDocs([]); return; }
    let alive = true;
    api.get(`/contexts/${form.context_id}/documents`)
      .then(({ data }) => { if (alive) setDocs(data?.items || data || []); })
      .catch(() => { if (alive) setDocs([]); });
    return () => { alive = false; };
  }, [form.context_id]);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.context_id || !form.title.trim() || !form.scheduled_at) {
      toast.error("Board, title, and date are required."); return;
    }
    setBusy(true);
    try {
      const iso = new Date(form.scheduled_at).toISOString();
      const { data } = await api.post(`/ned/meetings`, { ...form, scheduled_at: iso });
      toast.success("Meeting added.");
      onCreated(data);
      onClose();
      setForm({ context_id: boards[0]?.id || "", committee: "Audit",
                title: "", scheduled_at: "", paper_doc_ids: [] });
    } catch (err) { toast.error(apiErrorMessage(err)); } finally { setBusy(false); }
  };

  const togglePaper = (did) => setForm((f) => ({
    ...f,
    paper_doc_ids: f.paper_doc_ids.includes(did)
      ? f.paper_doc_ids.filter((d) => d !== did)
      : [...f.paper_doc_ids, did],
  }));

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl bg-[var(--cream)]" data-testid="ned-add-meeting-dialog">
        <DialogHeader>
          <DialogTitle>Add a meeting</DialogTitle>
          <DialogDescription>Manual entry · v1. Calendar integration arrives later.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <Label className="text-[12px]">Board</Label>
              <select
                value={form.context_id} onChange={(e) => setForm({ ...form, context_id: e.target.value })}
                className="mt-1 w-full border border-[var(--rule)] rounded-sm px-2 py-1.5 text-[13px] bg-white"
                data-testid="ned-add-meeting-board"
              >
                {boards.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </div>
            <div>
              <Label className="text-[12px]">Committee</Label>
              <select
                value={form.committee} onChange={(e) => setForm({ ...form, committee: e.target.value })}
                className="mt-1 w-full border border-[var(--rule)] rounded-sm px-2 py-1.5 text-[13px] bg-white"
                data-testid="ned-add-meeting-committee"
              >
                {["Audit", "Risk", "Remuneration", "Nomination", "Full Board", "Strategy", "Other"].map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <Label className="text-[12px]" htmlFor="ned-mt-title">Title</Label>
            <Input id="ned-mt-title" value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="e.g. Q3 Audit Committee — going-concern review"
              className="rounded-sm" data-testid="ned-add-meeting-title" />
          </div>
          <div>
            <Label className="text-[12px]" htmlFor="ned-mt-date">Date & time</Label>
            <Input id="ned-mt-date" type="datetime-local" value={form.scheduled_at}
              onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })}
              className="rounded-sm" data-testid="ned-add-meeting-date" />
          </div>
          {docs.length > 0 && (
            <div>
              <Label className="text-[12px]">Attach board papers (optional)</Label>
              <div className="mt-1 max-h-36 overflow-y-auto border border-[var(--rule)] rounded-sm p-2 bg-white">
                {docs.slice(0, 30).map((d) => (
                  <label key={d.id} className="flex items-center gap-2 py-1 text-[12.5px] cursor-pointer hover:bg-[var(--cream-deep)]/30 px-1 rounded-sm">
                    <input type="checkbox" checked={form.paper_doc_ids.includes(d.id)}
                      onChange={() => togglePaper(d.id)} />
                    <span className="truncate text-[var(--ink)]">{d.name || d.filename || d.id.slice(0, 8)}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
            <Button type="submit" disabled={busy}
              className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white"
              data-testid="ned-add-meeting-submit">
              {busy && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />}
              Add meeting
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function SearchPanel({ onResultClick }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState([]);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!q.trim()) { setHits([]); return; }
    setBusy(true);
    try {
      const { data } = await api.get(`/ned/search`, { params: { q } });
      setHits(data?.hits || []);
    } catch { setHits([]); }
    finally { setBusy(false); }
  };
  return (
    <section className="border border-[var(--rule)] bg-white rounded-md px-4 py-3 mb-5" data-testid="ned-search">
      <form onSubmit={submit} className="flex items-center gap-2">
        <Search className="w-4 h-4 text-[var(--muted)]" />
        <Input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search your meetings · notes · positions · follow-ups…"
          className="rounded-sm border-0 focus-visible:ring-0 px-0"
          data-testid="ned-search-input" />
        <Button type="submit" disabled={busy} variant="outline" size="sm"
          className="text-[12px]" data-testid="ned-search-submit">
          {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Search"}
        </Button>
      </form>
      {hits.length > 0 && (
        <ul className="mt-3 divide-y divide-[var(--rule)]" data-testid="ned-search-hits">
          {hits.slice(0, 10).map((h) => (
            <li key={`${h.kind}::${h.id}`} className="py-2">
              <button type="button" onClick={() => onResultClick(h)}
                className="text-left w-full hover:bg-[var(--cream-deep)]/30 px-2 py-1 rounded-sm">
                <p className="text-[11px] text-[var(--muted)] uppercase tracking-wider mb-0.5">{h.kind}</p>
                <p className="text-[13px] text-[var(--ink)]">
                  {h.title || h.snippet || h.subject || h.decision_text || h.id.slice(0, 8)}
                </p>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function HomeNed() {
  const { account } = useAuth();
  const navigate = useNavigate();
  const [landing, setLanding] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [boardFilter, setBoardFilter] = useState("all");
  const [addOpen, setAddOpen] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/ned/landing");
      setLanding(data);
    } catch (e) { setErr(apiErrorMessage(e)); }
    finally { setLoading(false); }
  };
  useEffect(() => { refresh(); }, []);

  const boards = landing?.boards || [];
  const filterMeetings = (rows) => {
    if (boardFilter === "all") return rows;
    return rows.filter((m) => m.context_id === boardFilter);
  };
  const thisWeek = filterMeetings(landing?.this_week || []);
  const nextTwo  = filterMeetings(landing?.next_two_weeks || []);
  const outFollowups = filterMeetings(landing?.outstanding?.followups || []);
  const outMeetings  = filterMeetings(landing?.outstanding?.meetings || []);

  const onResultClick = (h) => {
    if (h.kind === "meeting") navigate(`/app/ned/meeting/${h.id}`);
    else if (h.meeting_id) navigate(`/app/ned/meeting/${h.meeting_id}`);
  };

  return (
    <AppShell>
      <div className="max-w-5xl mx-auto px-6 py-8" data-testid="ned-home">
        <div className="flex items-baseline justify-between gap-4 mb-2 flex-wrap">
          <div>
            <p className="akki-overline text-[var(--muted)] mb-1">Non-executive director</p>
            <h1 className="akki-serif text-[26px] text-[var(--ink)]">Hi {account?.name?.split(" ")[0] || "there"}.</h1>
            <p className="akki-meta mt-0.5">
              {boards.length === 0
                ? "Once you're added to a board you'll see your meetings here."
                : <>Across {boards.length} board{boards.length === 1 ? "" : "s"}. Manual entry for v1.</>}
            </p>
          </div>
          {boards.length > 0 && (
            <div className="flex items-center gap-2">
              <select value={boardFilter} onChange={(e) => setBoardFilter(e.target.value)}
                className="border border-[var(--rule)] rounded-sm px-2 py-1.5 text-[12px] bg-white"
                data-testid="ned-home-board-filter">
                <option value="all">All boards</option>
                {boards.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
              <Button type="button" onClick={() => setAddOpen(true)}
                className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]"
                data-testid="ned-home-add-meeting">
                <Plus className="w-3.5 h-3.5 mr-1" /> Add a meeting
              </Button>
            </div>
          )}
        </div>

        {loading && (
          <div className="py-10 text-center text-[var(--muted)]">
            <Loader2 className="w-4 h-4 animate-spin mx-auto" />
          </div>
        )}
        {err && <p className="text-[12.5px] text-amber-900 my-3">{err}</p>}

        {!loading && (
          <>
            {/* Cycle sprint — Inbox tile. Surfaces pending assignments
                from executive boards. Tile is always present; the inner
                pending count is fetched lazily and degrades silently. */}
            <NedInboxTile />

            <SearchPanel onResultClick={onResultClick} />

            {/* Section 1 — This Week */}
            <section className="mb-6" data-testid="ned-section-this-week">
              <div className="flex items-baseline gap-2 mb-2">
                <Calendar className="w-3.5 h-3.5 text-[var(--accent)]" />
                <h2 className="akki-serif text-[16px] text-[var(--ink)] font-medium">This week</h2>
                <span className="text-[11px] font-mono text-[var(--muted)]">
                  {thisWeek.length} meeting{thisWeek.length === 1 ? "" : "s"}
                </span>
              </div>
              {thisWeek.length === 0 ? (
                <p className="text-[12.5px] text-[var(--muted)] italic">Nothing in your diary in the next 7 days.</p>
              ) : (
                <div className="space-y-2">
                  {thisWeek.map((m) => <MeetingCard key={m.id} meeting={m} boards={boards}
                    onClick={() => navigate(`/app/ned/meeting/${m.id}`)} />)}
                </div>
              )}
            </section>

            {/* Section 2 — Next 2 Weeks */}
            <section className="mb-6" data-testid="ned-section-next-2-weeks">
              <div className="flex items-baseline gap-2 mb-2">
                <Clock className="w-3.5 h-3.5 text-[var(--muted)]" />
                <h2 className="akki-serif text-[16px] text-[var(--ink)] font-medium">Next 2 weeks</h2>
                <span className="text-[11px] font-mono text-[var(--muted)]">
                  {nextTwo.length} meeting{nextTwo.length === 1 ? "" : "s"}
                </span>
              </div>
              {nextTwo.length === 0 ? (
                <p className="text-[12.5px] text-[var(--muted)] italic">Window 8–21 days out is empty.</p>
              ) : (
                <div className="space-y-2">
                  {nextTwo.map((m) => <MeetingCard key={m.id} meeting={m} boards={boards}
                    onClick={() => navigate(`/app/ned/meeting/${m.id}`)} />)}
                </div>
              )}
            </section>

            {/* Section 3 — Outstanding */}
            <section className="mb-6" data-testid="ned-section-outstanding">
              <div className="flex items-baseline gap-2 mb-2">
                <ListChecks className="w-3.5 h-3.5 text-[var(--muted)]" />
                <h2 className="akki-serif text-[16px] text-[var(--ink)] font-medium">Outstanding</h2>
                <span className="text-[11px] font-mono text-[var(--muted)]">
                  {(outFollowups.length + outMeetings.length)} item{(outFollowups.length + outMeetings.length) === 1 ? "" : "s"}
                </span>
              </div>
              {(outFollowups.length === 0 && outMeetings.length === 0) ? (
                <p className="text-[12.5px] text-[var(--muted)] italic">Nothing waiting on you. Keep it that way.</p>
              ) : (
                <div className="space-y-2">
                  {outMeetings.map((m) => (
                    <button key={m.id} type="button" onClick={() => navigate(`/app/ned/meeting/${m.id}`)}
                      className="w-full text-left border border-[var(--rule)] bg-white rounded-md px-4 py-2 hover:border-[var(--accent)] transition-colors flex items-baseline gap-3 flex-wrap"
                      data-testid={`ned-outstanding-meeting-${m.id}`}>
                      <span className="akki-serif text-[13.5px] text-[var(--ink)]">{m.title}</span>
                      <span className="text-[11px] font-mono text-[var(--muted)]">{m.committee} · post-meeting · {fmtDate(m.scheduled_at)}</span>
                      <ArrowRight className="w-3 h-3 text-[var(--muted)] ml-auto" />
                    </button>
                  ))}
                  {outFollowups.map((f) => (
                    <button key={f.id} type="button" onClick={() => f.meeting_id && navigate(`/app/ned/meeting/${f.meeting_id}`)}
                      className="w-full text-left border border-[var(--rule)] bg-white rounded-md px-4 py-2 hover:border-[var(--accent)] transition-colors flex items-baseline gap-3 flex-wrap"
                      data-testid={`ned-outstanding-followup-${f.id}`}>
                      <span className="akki-serif text-[13.5px] text-[var(--ink)]">Follow-up: {f.subject}</span>
                      <span className="text-[11px] font-mono text-[var(--muted)]">{f.committee} · status: {f.status}</span>
                      <ArrowRight className="w-3 h-3 text-[var(--muted)] ml-auto" />
                    </button>
                  ))}
                </div>
              )}
            </section>

            {/* Section 4 — Patterns worth knowing */}
            <section className="mb-2" data-testid="ned-section-patterns">
              <div className="flex items-baseline gap-2 mb-2">
                <Globe2 className="w-3.5 h-3.5 text-[var(--muted)]" />
                <h2 className="akki-serif text-[16px] text-[var(--ink)] font-medium">Patterns worth knowing</h2>
              </div>
              {boards[0] ? (
                <AcrossBoardsPanel contextId={boards[0].id} />
              ) : (
                <p className="text-[12.5px] text-[var(--muted)] italic">Patterns surface once you're a NED on at least one board.</p>
              )}
            </section>
          </>
        )}
      </div>

      <AddMeetingDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        boards={boards}
        onCreated={() => refresh()}
      />
    </AppShell>
  );
}
