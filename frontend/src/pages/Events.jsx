/**
 * Events page — Phase I.4.a (2026-05-27).
 *
 * Manual events entry surface for an active company context. The
 * Company Home Card 5 ("Upcoming events") deep-links here.
 *
 * Route: `/app/events?context_id={cid}`
 *
 * I.4.a scope (manual entry only):
 *   • List events for the active context (tabs: Upcoming / Past / All)
 *   • Add event modal (5 fields, 4 of them required: title, type,
 *     start_at; location + notes optional; end_at optional)
 *   • Edit event (same modal, prefilled)
 *   • Delete event (soft-delete via DELETE; backend hides deleted)
 *
 * Out of scope (later I.4 sub-phases):
 *   • I.4.b — doc-extraction (LLM scans board packs for events)
 *   • I.4.c — calendar sync (Google/Outlook OAuth)
 *   • Recurring events, reminders, notifications
 */
import React, { useEffect, useMemo, useState, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api, API_BASE } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import AppShell from "@/components/layout/AppShell";
import {
  Calendar, Plus, ArrowLeft, MapPin, Edit3, Trash2, X, ChevronRight,
  CheckCircle2, FileText, Sparkles, Link2, RefreshCw, AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
// Phase L.b.3 (2026-05-27) — Real backend-driven SSE for calendar sync.
import StreamingLogScene from "@/components/transitions/StreamingLogScene";
import useStreamingProgress from "@/hooks/useStreamingProgress";


const EVENT_TYPES = [
  { id: "board_meeting", label: "Board meeting" },
  { id: "audit_review",  label: "Audit review" },
  { id: "briefing",      label: "Briefing" },
  { id: "deadline",      label: "Deadline" },
  { id: "other",         label: "Other" },
];

const EVENT_TYPE_LABEL = Object.fromEntries(EVENT_TYPES.map(t => [t.id, t.label]));


function fmtDateTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      weekday: "short", month: "short", day: "numeric",
      hour: "numeric", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}


/* ─────────────────────────────────────────────────────────────────── */
/* Add / Edit modal                                                     */
/* ─────────────────────────────────────────────────────────────────── */

function EventModal({ open, mode, event, onSave, onDelete, onClose }) {
  const [title,    setTitle]    = useState("");
  const [type,     setType]     = useState("board_meeting");
  const [startAt,  setStartAt]  = useState("");
  const [endAt,    setEndAt]    = useState("");
  const [location, setLocation] = useState("");
  const [notes,    setNotes]    = useState("");
  const [err,      setErr]      = useState(null);
  const [saving,   setSaving]   = useState(false);

  // Prefill on open (edit mode)
  useEffect(() => {
    if (!open) return;
    setErr(null);
    if (mode === "edit" && event) {
      setTitle(event.title || "");
      setType(event.type || "board_meeting");
      setStartAt(event.start_at ? event.start_at.slice(0, 16) : "");
      setEndAt(event.end_at ? event.end_at.slice(0, 16) : "");
      setLocation(event.location || "");
      setNotes(event.notes || "");
    } else {
      setTitle(""); setType("board_meeting"); setStartAt("");
      setEndAt(""); setLocation(""); setNotes("");
    }
  }, [open, mode, event]);

  const handleSave = useCallback(async (e) => {
    e?.preventDefault?.();
    if (!title.trim()) { setErr("Title is required"); return; }
    if (!startAt)      { setErr("Start date/time is required"); return; }
    setSaving(true); setErr(null);
    try {
      // datetime-local inputs are local-naive; convert to ISO with timezone offset.
      const start_iso = new Date(startAt).toISOString();
      const end_iso = endAt ? new Date(endAt).toISOString() : null;
      await onSave({
        title:    title.trim(),
        type,
        start_at: start_iso,
        end_at:   end_iso,
        location: location.trim() || null,
        notes:    notes.trim() || null,
      });
      onClose();
    } catch (e) {
      setErr(e?.response?.data?.detail || e?.message || "Save failed");
    } finally {
      setSaving(false);
    }
  }, [title, type, startAt, endAt, location, notes, onSave, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
      onClick={onClose}
      data-testid="event-modal-backdrop"
    >
      <form
        className="bg-white rounded-md shadow-lg w-full max-w-[540px] max-h-[92vh] overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}
        onSubmit={handleSave}
        data-testid="event-modal"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-serif text-[20px] text-[var(--ink)]">
            {mode === "edit" ? "Edit event" : "Add event"}
          </h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-[var(--muted)] hover:text-[var(--ink)]"
            data-testid="event-modal-close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <Label htmlFor="evt-title" className="text-[11px] uppercase tracking-[0.08em] font-mono text-[var(--muted)]">
              Title *
            </Label>
            <Input
              id="evt-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
              data-testid="event-modal-title"
              required
            />
          </div>

          <div>
            <Label htmlFor="evt-type" className="text-[11px] uppercase tracking-[0.08em] font-mono text-[var(--muted)]">
              Type
            </Label>
            <select
              id="evt-type"
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="w-full border border-[var(--rule)] rounded-md px-3 py-2 text-[14px] bg-white"
              data-testid="event-modal-type"
            >
              {EVENT_TYPES.map(t => (
                <option key={t.id} value={t.id}>{t.label}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="evt-start" className="text-[11px] uppercase tracking-[0.08em] font-mono text-[var(--muted)]">
                Start *
              </Label>
              <Input
                id="evt-start"
                type="datetime-local"
                value={startAt}
                onChange={(e) => setStartAt(e.target.value)}
                data-testid="event-modal-start"
                required
              />
            </div>
            <div>
              <Label htmlFor="evt-end" className="text-[11px] uppercase tracking-[0.08em] font-mono text-[var(--muted)]">
                End (optional)
              </Label>
              <Input
                id="evt-end"
                type="datetime-local"
                value={endAt}
                onChange={(e) => setEndAt(e.target.value)}
                data-testid="event-modal-end"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="evt-location" className="text-[11px] uppercase tracking-[0.08em] font-mono text-[var(--muted)]">
              Location (optional)
            </Label>
            <Input
              id="evt-location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              maxLength={200}
              data-testid="event-modal-location"
            />
          </div>

          <div>
            <Label htmlFor="evt-notes" className="text-[11px] uppercase tracking-[0.08em] font-mono text-[var(--muted)]">
              Notes (optional)
            </Label>
            <Textarea
              id="evt-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={2000}
              rows={4}
              data-testid="event-modal-notes"
            />
          </div>
        </div>

        {err && (
          <p className="text-[12px] text-[var(--accent)] mt-3" data-testid="event-modal-error">
            {err}
          </p>
        )}

        <div className="mt-5 flex items-center justify-between gap-3">
          {mode === "edit" ? (
            <button
              type="button"
              onClick={() => {
                if (window.confirm("Delete this event? This cannot be undone.")) {
                  onDelete(event.id).then(onClose);
                }
              }}
              className="text-[12.5px] text-[var(--accent)] hover:underline inline-flex items-center gap-1"
              data-testid="event-modal-delete"
            >
              <Trash2 className="w-3.5 h-3.5" /> Delete
            </button>
          ) : <span />}
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={onClose} data-testid="event-modal-cancel">
              Cancel
            </Button>
            <Button type="submit" disabled={saving} data-testid="event-modal-save">
              {saving ? "Saving…" : (mode === "edit" ? "Save changes" : "Add event")}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}


/* ─────────────────────────────────────────────────────────────────── */
/* Events page                                                          */
/* ─────────────────────────────────────────────────────────────────── */

export default function Events() {
  const [params, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { activeContext } = useAuth();
  const cid = params.get("context_id") || activeContext?.id;

  const [tab,        setTab]        = useState("upcoming"); // upcoming | past | all | extracted
  const [events,     setEvents]     = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [modalOpen,  setModalOpen]  = useState(false);
  const [modalMode,  setModalMode]  = useState("create"); // create | edit
  const [editTarget, setEditTarget] = useState(null);

  // Phase I.4.c (2026-05-27) — Calendar sync state (Google leg only).
  const [calendarStatus, setCalendarStatus] = useState(null);   // null=loading, {connected:bool,...}
  const [syncing,        setSyncing]        = useState(false);
  const [disconnecting,  setDisconnecting]  = useState(false);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);

  // Phase L.b.3 (2026-05-27) — Backend-driven SSE for sync flow.
  const { state: lbState, stream: lbStream, reset: lbReset } = useStreamingProgress();

  const loadCalendarStatus = useCallback(async () => {
    if (!cid) return;
    try {
      const { data } = await api.get(`/contexts/${cid}/oauth/calendar/status`);
      setCalendarStatus(data);
    } catch {
      setCalendarStatus({ connected: false });
    }
  }, [cid]);

  // Trigger an explicit sync (called by "Sync now" + auto-fired once
  // when the OAuth callback redirects with ?calendar_connected=google).
  const triggerSync = useCallback(async () => {
    if (!cid) return null;
    setSyncing(true);
    lbReset();
    // The stream callback resolves when SSE ends; useEffect below
    // handles complete / error.
    lbStream(
      `${API_BASE}/contexts/${cid}/events/sync-calendar/stream?provider=google`,
      { method: "POST" },
    ).catch(() => { /* error state handled by useEffect */ });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cid, lbStream, lbReset]);

  const connectGoogle = useCallback(async () => {
    if (!cid) return;
    try {
      const { data } = await api.get(`/oauth/google/connect?context_id=${cid}`);
      if (data?.authorize_url) window.location.href = data.authorize_url;
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("[Events] google connect failed:", err?.message);
    }
  }, [cid]);

  const disconnectGoogle = useCallback(async () => {
    if (!cid) return;
    setDisconnecting(true);
    try {
      await api.post(`/contexts/${cid}/oauth/google/disconnect`);
      await loadCalendarStatus();
      setConfirmDisconnect(false);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("[Events] google disconnect failed:", err?.message);
    } finally {
      setDisconnecting(false);
    }
  }, [cid, loadCalendarStatus]);

  const reload = useCallback(async () => {
    if (!cid) return;
    setLoading(true);
    try {
      // We always load `upcoming=false` (all events incl. past + drafts)
      // and filter client-side per tab — keeps the tab switch instant
      // after first load. Drafts (status="draft") are surfaced ONLY on
      // the "extracted" tab (I.4.b 2026-05-27).
      const { data } = await api.get(
        `/contexts/${cid}/events?upcoming=false&limit=100`,
      );
      setEvents(data?.items || []);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("[Events] list fetch failed:", err?.message);
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [cid]);

  useEffect(() => { reload(); }, [reload]);
  useEffect(() => { loadCalendarStatus(); }, [loadCalendarStatus]);

  // Phase L.b.3 (2026-05-27) — React to stream lifecycle: complete →
  // refresh calendar status + event list; error → log + refresh
  // status. `setSyncing(false)` always runs on terminal state.
  useEffect(() => {
    if (lbState.status === "complete" || lbState.status === "error") {
      (async () => {
        await Promise.all([loadCalendarStatus(), reload()]);
        setSyncing(false);
      })();
      if (lbState.status === "error") {
        // eslint-disable-next-line no-console
        console.warn("[Events] calendar sync failed:", lbState.error?.message);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lbState.status]);

  // Phase I.4.c (2026-05-27) — Auto-sync once when the OAuth callback
  // redirects with ?calendar_connected=google. Then strip the param.
  useEffect(() => {
    const flag = params.get("calendar_connected");
    if (flag !== "google" || !cid) return;
    (async () => {
      await triggerSync();
      const sp = new URLSearchParams(params);
      sp.delete("calendar_connected");
      setSearchParams(sp, { replace: true });
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, cid]);

  const now = useMemo(() => Date.now(), []);
  // Confirmed (non-draft) events power upcoming/past/all tabs.
  const nonDrafts = useMemo(
    () => events.filter(e => e.status !== "draft"),
    [events],
  );
  // Drafts (status="draft") power the Extracted tab.
  const drafts = useMemo(
    () => events.filter(e => e.status === "draft"),
    [events],
  );
  const filtered = useMemo(() => {
    if (tab === "extracted") return drafts;
    if (tab === "upcoming")  return nonDrafts.filter(e => new Date(e.start_at).getTime() >= now);
    if (tab === "past")      return nonDrafts.filter(e => new Date(e.start_at).getTime() < now);
    return nonDrafts;
  }, [tab, nonDrafts, drafts, now]);

  const handleCreate = useCallback(async (body) => {
    const { data } = await api.post(`/contexts/${cid}/events`, body);
    setEvents(prev => [...prev, data]);
  }, [cid]);

  const handleUpdate = useCallback(async (body) => {
    const { data } = await api.patch(
      `/contexts/${cid}/events/${editTarget.id}`, body,
    );
    setEvents(prev => prev.map(e => e.id === data.id ? data : e));
  }, [cid, editTarget]);

  const handleDelete = useCallback(async (eventId) => {
    await api.delete(`/contexts/${cid}/events/${eventId}`);
    setEvents(prev => prev.filter(e => e.id !== eventId));
  }, [cid]);

  // I.4.b — promote a draft to confirmed.
  const handleConfirm = useCallback(async (eventId) => {
    const { data } = await api.patch(
      `/contexts/${cid}/events/${eventId}`, { status: "confirmed" },
    );
    setEvents(prev => prev.map(e => e.id === data.id ? data : e));
  }, [cid]);

  // I.4.b — reject a draft = soft delete (same DELETE endpoint).
  const handleReject = useCallback(async (eventId) => {
    await api.delete(`/contexts/${cid}/events/${eventId}`);
    setEvents(prev => prev.filter(e => e.id !== eventId));
  }, [cid]);

  const openCreate = () => { setModalMode("create"); setEditTarget(null); setModalOpen(true); };
  const openEdit   = (e) => { setModalMode("edit"); setEditTarget(e); setModalOpen(true); };

  const companyName = activeContext?.name || "this company";

  return (
    <AppShell>
      <div className="max-w-[1100px] mx-auto px-6 lg:px-8 py-8" data-testid="events-page">
        {/* Breadcrumb */}
        <button
          type="button"
          onClick={() => navigate("/app")}
          aria-label="Back to Company Home"
          className="text-[11.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] hover:text-[var(--ink)] inline-flex items-center gap-1.5 mb-6 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 rounded-sm px-1 py-0.5"
          data-testid="events-back-to-home"
        >
          <ArrowLeft className="w-3 h-3" strokeWidth={1.8} aria-hidden="true" /> Back to Company Home
        </button>

        {/* Eyebrow + H1 + subtitle */}
        <p className="text-[10.5px] uppercase tracking-[0.18em] font-mono text-[var(--muted)] mb-2" data-testid="events-eyebrow">
          Events · {companyName}
        </p>
        <h1
          className="font-serif leading-[1.15] text-[var(--ink)] mb-2"
          style={{ fontSize: "32px" }}
          data-testid="events-h1"
        >
          Upcoming on the calendar.
        </h1>
        <p className="text-[13.5px] text-[var(--muted)] mb-6">
          Manual entries, AI-extracted dates, and your connected calendar — in one place.
        </p>

        {/* Phase I.4.c (2026-05-27) — Calendar sync banner (Google leg).
            States: not-connected | connected-ok | auth-expired | syncing. */}
        <CalendarSyncBanner
          status={calendarStatus}
          syncing={syncing}
          onConnect={connectGoogle}
          onSyncNow={triggerSync}
          onAskDisconnect={() => setConfirmDisconnect(true)}
        />

        {/* Phase L.b.2 (2026-05-27) — Streaming-log shown while a sync
            is in flight. The banner shows the persistent state (connect /
            connected / expired); this row shows live phase advancement. */}
        {syncing && (
          <div
            className="mb-5 bg-white border border-[var(--rule)] rounded-md px-4 py-3 max-w-md"
            data-testid="calendar-sync-streaming-row"
          >
            <StreamingLogScene
              surfaceId="streaming-log-events-calendar-sync"
              state={lbState}
              emptyHint="Reaching Google Calendar…"
            />
          </div>
        )}

        {/* Tabs + Add button */}
        <div className="flex items-center justify-between mb-5">
          <div role="tablist" aria-label="Filter events by time" className="flex gap-1.5" data-testid="events-tabs">
            <button
              type="button"
              role="tab"
              aria-selected={tab === "upcoming"}
              onClick={() => setTab("upcoming")}
              className={`px-3 py-1.5 text-[12px] uppercase tracking-[0.1em] font-mono rounded-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 ${
                tab === "upcoming"
                  ? "bg-[var(--ink)] text-white"
                  : "text-[var(--muted)] hover:text-[var(--ink)] bg-white border border-[var(--rule)]"
              }`}
              data-testid="events-tab-upcoming"
            >
              Upcoming
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "past"}
              onClick={() => setTab("past")}
              className={`px-3 py-1.5 text-[12px] uppercase tracking-[0.1em] font-mono rounded-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 ${
                tab === "past"
                  ? "bg-[var(--ink)] text-white"
                  : "text-[var(--muted)] hover:text-[var(--ink)] bg-white border border-[var(--rule)]"
              }`}
              data-testid="events-tab-past"
            >
              Past
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "all"}
              onClick={() => setTab("all")}
              className={`px-3 py-1.5 text-[12px] uppercase tracking-[0.1em] font-mono rounded-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 ${
                tab === "all"
                  ? "bg-[var(--ink)] text-white"
                  : "text-[var(--muted)] hover:text-[var(--ink)] bg-white border border-[var(--rule)]"
              }`}
              data-testid="events-tab-all"
            >
              All
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "extracted"}
              onClick={() => setTab("extracted")}
              className={`px-3 py-1.5 text-[12px] uppercase tracking-[0.1em] font-mono rounded-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 ${
                tab === "extracted"
                  ? "bg-[var(--ink)] text-white"
                  : "text-[var(--muted)] hover:text-[var(--ink)] bg-white border border-[var(--rule)]"
              }`}
              data-testid="events-tab-extracted"
            >
              <Sparkles className="w-3 h-3 inline mr-1" strokeWidth={1.8} aria-hidden="true" />
              Extracted{drafts.length > 0 ? ` (${drafts.length})` : ""}
            </button>
          </div>

          <Button onClick={openCreate} data-testid="events-add-btn">
            <Plus className="w-3.5 h-3.5 mr-1" />
            Add event
          </Button>
        </div>

        {/* List */}
        {loading ? (
          <p className="text-[13px] italic text-[var(--muted)] py-6" data-testid="events-loading">
            Loading…
          </p>
        ) : filtered.length === 0 ? (
          <div
            className="bg-white border border-dashed border-[var(--rule)] rounded-md px-6 py-12 text-center"
            data-testid="events-empty"
          >
            {tab === "extracted" ? (
              <>
                <Sparkles className="w-5 h-5 mx-auto text-[var(--muted)] mb-3" strokeWidth={1.5} />
                <p className="text-[13px] italic text-[var(--muted)]">
                  No extracted events. Upload a board pack or briefing to surface dates automatically.
                </p>
              </>
            ) : (
              <>
                <Calendar className="w-5 h-5 mx-auto text-[var(--muted)] mb-3" strokeWidth={1.5} />
                <p className="text-[13px] italic text-[var(--muted)]">
                  No events yet. Add your first event to surface it on Company Home.
                </p>
              </>
            )}
          </div>
        ) : tab === "extracted" ? (
          <ul className="space-y-2.5" data-testid="events-extracted-list">
            {filtered.map((ev) => {
              const conf = typeof ev.confidence === "number" ? ev.confidence : null;
              const confPct = conf !== null ? Math.round(conf * 100) : null;
              const confHigh = conf !== null && conf >= 0.8;
              return (
                <li key={ev.id}>
                  <div
                    className="bg-white border border-[var(--rule)] rounded-md px-5 py-3.5"
                    data-testid={`events-draft-row-${ev.id}`}
                  >
                    <div className="flex items-start gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <p className="text-[15.5px] font-medium text-[var(--ink)] truncate">{ev.title}</p>
                          <span className="text-[10px] uppercase tracking-[0.1em] font-mono text-[var(--muted)] border border-[var(--rule)] rounded-sm px-1.5 py-[1px] shrink-0">
                            {EVENT_TYPE_LABEL[ev.type] || ev.type}
                          </span>
                          {confPct !== null && (
                            <span
                              className={`text-[10px] uppercase tracking-[0.08em] font-mono rounded-sm px-1.5 py-[1px] shrink-0 ${
                                confHigh
                                  ? "bg-green-50 text-green-800 border border-green-200"
                                  : "bg-amber-50 text-amber-800 border border-amber-200"
                              }`}
                              data-testid={`events-draft-confidence-${ev.id}`}
                            >
                              {confPct}% match
                            </span>
                          )}
                        </div>
                        <p className="text-[12.5px] text-[var(--muted)]">{fmtDateTime(ev.start_at)}{ev.end_at ? ` → ${fmtDateTime(ev.end_at)}` : ""}</p>
                        {ev.location && (
                          <p className="text-[12px] text-[var(--muted)] inline-flex items-center gap-1 mt-1">
                            <MapPin className="w-3 h-3" /> {ev.location}
                          </p>
                        )}
                        {ev.source_ref && (
                          <button
                            type="button"
                            onClick={() => navigate(`/app/work-studio?doc_id=${ev.source_ref}&context_id=${cid}`)}
                            className="text-[11px] text-[var(--accent)] hover:underline inline-flex items-center gap-1 mt-1.5"
                            data-testid={`events-draft-source-${ev.id}`}
                          >
                            <FileText className="w-3 h-3" strokeWidth={1.7} /> Source document
                          </button>
                        )}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => handleConfirm(ev.id)}
                          className="text-[11.5px] uppercase tracking-[0.08em] font-mono inline-flex items-center gap-1 bg-[var(--ink)] text-white rounded-sm px-2.5 py-1.5 hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50"
                          data-testid={`events-draft-confirm-${ev.id}`}
                          aria-label={`Confirm extracted event: ${ev.title}`}
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.8} aria-hidden="true" />
                          Confirm
                        </button>
                        <button
                          type="button"
                          onClick={() => handleReject(ev.id)}
                          className="text-[var(--muted)] hover:text-[var(--accent)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 rounded-sm p-1"
                          data-testid={`events-draft-reject-${ev.id}`}
                          aria-label={`Reject extracted event: ${ev.title}`}
                          title="Reject"
                        >
                          <Trash2 className="w-4 h-4" strokeWidth={1.7} aria-hidden="true" />
                        </button>
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <ul className="space-y-2.5" data-testid="events-list">
            {filtered.map((ev) => (
              <li key={ev.id}>
                <button
                  type="button"
                  onClick={() => openEdit(ev)}
                  className="w-full text-left bg-white border border-[var(--rule)] hover:border-[var(--ink)]/30 rounded-md px-5 py-3.5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50"
                  data-testid={`events-row-${ev.id}`}
                >
                  <div className="flex items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="text-[15.5px] font-medium text-[var(--ink)] truncate">{ev.title}</p>
                        <span className="text-[10px] uppercase tracking-[0.1em] font-mono text-[var(--muted)] border border-[var(--rule)] rounded-sm px-1.5 py-[1px] shrink-0">
                          {EVENT_TYPE_LABEL[ev.type] || ev.type}
                        </span>
                        {ev.source === "calendar_sync" && (
                          <span
                            className="text-[var(--muted)] shrink-0"
                            title="Synced from Google Calendar"
                            data-testid={`events-row-source-calendar-${ev.id}`}
                            aria-label="Synced from Google Calendar"
                          >
                            <Calendar className="w-3 h-3" strokeWidth={1.7} aria-hidden="true" />
                          </span>
                        )}
                      </div>
                      <p className="text-[12.5px] text-[var(--muted)]">{fmtDateTime(ev.start_at)}{ev.end_at ? ` → ${fmtDateTime(ev.end_at)}` : ""}</p>
                      {ev.location && (
                        <p className="text-[12px] text-[var(--muted)] inline-flex items-center gap-1 mt-1">
                          <MapPin className="w-3 h-3" /> {ev.location}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-1 shrink-0 text-[var(--muted)]">
                      <Edit3 className="w-3.5 h-3.5" strokeWidth={1.7} />
                      <ChevronRight className="w-3.5 h-3.5" strokeWidth={1.7} />
                    </div>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}

        <EventModal
          open={modalOpen}
          mode={modalMode}
          event={editTarget}
          onSave={modalMode === "edit" ? handleUpdate : handleCreate}
          onDelete={handleDelete}
          onClose={() => setModalOpen(false)}
        />

        {/* Phase I.4.c — Disconnect confirmation modal. */}
        {confirmDisconnect && (
          <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" data-testid="calendar-disconnect-modal">
            <div className="bg-white border border-[var(--rule)] rounded-md max-w-md w-full p-6">
              <p className="text-[15.5px] text-[var(--ink)] font-medium mb-2">
                Disconnect Google Calendar?
              </p>
              <p className="text-[13px] text-[var(--muted)] mb-5">
                Synced events will remain on the Events page but won't update with future calendar changes. You can reconnect any time.
              </p>
              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setConfirmDisconnect(false)}
                  className="px-3 py-1.5 text-[12.5px] uppercase tracking-[0.1em] font-mono text-[var(--muted)] hover:text-[var(--ink)] rounded-sm"
                  data-testid="calendar-disconnect-cancel"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={disconnectGoogle}
                  disabled={disconnecting}
                  className="px-3 py-1.5 text-[12.5px] uppercase tracking-[0.1em] font-mono bg-[var(--ink)] text-white rounded-sm hover:opacity-90 disabled:opacity-50"
                  data-testid="calendar-disconnect-confirm"
                >
                  {disconnecting ? "Disconnecting…" : "Disconnect"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}


/* ─────────────────────────────────────────────────────────────────── */
/* Calendar Sync Banner — Phase I.4.c (Google leg, 2026-05-27)          */
/* ─────────────────────────────────────────────────────────────────── */

function _relativeTime(iso) {
  if (!iso) return "—";
  try {
    const then = new Date(iso).getTime();
    const diff = Math.max(0, Date.now() - then);
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  } catch { return "—"; }
}

function CalendarSyncBanner({ status, syncing, onConnect, onSyncNow, onAskDisconnect }) {
  // Loading
  if (!status) {
    return (
      <div
        className="mb-5 flex items-center gap-2 text-[12px] text-[var(--muted)] italic"
        data-testid="calendar-banner-loading"
      >
        <Calendar className="w-3.5 h-3.5" strokeWidth={1.7} aria-hidden="true" />
        Checking calendar connection…
      </div>
    );
  }

  // Not connected
  if (!status.connected) {
    return (
      <div
        className="mb-5 flex items-center justify-between gap-4 bg-white border border-dashed border-[var(--rule)] rounded-md px-4 py-3"
        data-testid="calendar-banner-disconnected"
      >
        <div className="flex items-center gap-2.5">
          <Calendar className="w-4 h-4 text-[var(--muted)]" strokeWidth={1.7} />
          <p className="text-[13px] text-[var(--ink)]">
            <span className="font-medium">Sync your calendar.</span>{" "}
            <span className="text-[var(--muted)]">Pull upcoming meetings, audits and deadlines straight in.</span>
          </p>
        </div>
        <button
          type="button"
          onClick={onConnect}
          className="text-[11.5px] uppercase tracking-[0.1em] font-mono inline-flex items-center gap-1.5 bg-[var(--ink)] text-white rounded-sm px-3 py-1.5 hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50"
          data-testid="calendar-connect-google"
        >
          <Link2 className="w-3.5 h-3.5" strokeWidth={1.8} aria-hidden="true" />
          Connect Google Calendar
        </button>
      </div>
    );
  }

  // Auth expired
  if (status.last_sync_status === "auth_expired") {
    return (
      <div
        className="mb-5 flex items-center justify-between gap-4 bg-amber-50 border border-amber-200 rounded-md px-4 py-3"
        data-testid="calendar-banner-auth-expired"
      >
        <div className="flex items-center gap-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-700" strokeWidth={1.7} />
          <p className="text-[13px] text-amber-900">
            <span className="font-medium">Connection expired.</span>{" "}
            <span>Reconnect Google Calendar to keep syncing.</span>
          </p>
        </div>
        <button
          type="button"
          onClick={onConnect}
          className="text-[11.5px] uppercase tracking-[0.1em] font-mono inline-flex items-center gap-1.5 bg-amber-900 text-white rounded-sm px-3 py-1.5 hover:opacity-90"
          data-testid="calendar-reconnect-google"
        >
          <Link2 className="w-3.5 h-3.5" strokeWidth={1.8} aria-hidden="true" />
          Reconnect
        </button>
      </div>
    );
  }

  // Connected OK
  return (
    <div
      className="mb-5 flex items-center justify-between gap-4 bg-white border border-[var(--rule)] rounded-md px-4 py-3"
      data-testid="calendar-banner-connected"
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" strokeWidth={1.7} />
        <p className="text-[13px] text-[var(--ink)] truncate">
          <span className="font-medium">Connected to Google</span>
          <span className="text-[var(--muted)]"> · {status.synced_count} event{status.synced_count === 1 ? "" : "s"} synced · Last: <span data-testid="calendar-last-sync-relative">{_relativeTime(status.last_sync_at)}</span></span>
        </p>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <button
          type="button"
          onClick={onSyncNow}
          disabled={syncing}
          className="text-[11.5px] uppercase tracking-[0.1em] font-mono inline-flex items-center gap-1.5 text-[var(--ink)] hover:opacity-80 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 rounded-sm px-1"
          data-testid="calendar-sync-now"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${syncing ? "animate-spin" : ""}`} strokeWidth={1.8} aria-hidden="true" />
          {syncing ? "Syncing…" : "Sync now"}
        </button>
        <button
          type="button"
          onClick={onAskDisconnect}
          className="text-[11px] text-[var(--muted)] hover:text-[var(--accent)] underline-offset-2 hover:underline"
          data-testid="calendar-disconnect"
        >
          Disconnect
        </button>
      </div>
    </div>
  );
}
