/**
 * SolvaSessions.jsx — Wave 3.3 (UAT pack 2026-05-10).
 *
 * Full sessions-list page. Mounted at `/app/solva/sessions`. Reads
 * `GET /api/solva/v2/sessions?q=&status=` and renders:
 *   - Header: "Your Solva sessions in <Company>"
 *   - Search input  (debounced; q-substring match against `intent`)
 *   - Filter chips: All / Active / Complete / Refused / Paused
 *   - List with task-tag, intent snippet, status, dates, and Open
 *   - Pagination is left at the backend's limit=100 cap for v1.
 *     (Pagination UI is a follow-up.)
 *
 * Per-row Delete is intentionally omitted in this iteration — the
 * collapsible Recent Sessions block on the picker already exposes
 * Discard for the most-recent 5; a separate dialog for hard-delete
 * is a larger ticket.
 */
import React, { useEffect, useMemo, useState, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Search, ChevronLeft, Pencil } from "lucide-react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";

const STATUS_CHIPS = [
  { key: "",          label: "All",       countKey: "all" },
  { key: "active",    label: "Active",    countKey: "active" },
  { key: "paused",    label: "Paused",    countKey: "paused" },
  { key: "complete",  label: "Complete",  countKey: "complete" },
  { key: "refused",   label: "Refused",   countKey: "refused" },
];

const SUBMODULE_LABEL = {
  seek_clarity:        "Seek Clarity",
  develop_strategy:    "Develop Strategy",
  simulate_hypothesis: "Simulate Hypothesis",
  get_perspective:     "Get Perspective",
};

function useDebouncedValue(value, delay = 280) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export default function SolvaSessions() {
  const { activeContext } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [counts, setCounts] = useState({
    all: 0, active: 0, paused: 0, complete: 0, refused: 0,
  });
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  // Chunk 14 SV-05 (2026-05-21) — debounce dropped to 150ms per
  // verbatim spec ("real-time filter, debounced ~150ms, no submit
  // button"). Previously 280ms which felt sluggish on the live
  // preview. The lower number is fine because the backend `q` regex
  // is anchored to `intent` / `initial_framing` / `title` / synthesis
  // and the route is account-and-context-scoped — the result-set
  // cap is small.
  const debouncedQ = useDebouncedValue(q, 150);

  useEffect(() => {
    let cancelled = false;
    // QA-2026-05-20 SV-02 fix: backend requires `context_id` as a
    // query parameter (see routers/solva_v2.py::list_sessions —
    // WS-R16 privacy hardening makes context_id REQUIRED). Without
    // it FastAPI raises a 422 "Field required" — which is exactly
    // what the QA author observed when clicking "View All Sessions".
    // Skip the call entirely until activeContext resolves; the page
    // renders the no-context empty state in the meantime.
    if (!activeContext?.id) {
      setItems([]);
      setCounts({ all: 0, active: 0, paused: 0, complete: 0, refused: 0 });
      setLoading(false);
      return () => { cancelled = true; };
    }
    setLoading(true);
    const params = { context_id: activeContext.id };
    if (debouncedQ.trim()) params.q = debouncedQ.trim();
    if (status) params.status = status;
    api.get("/solva/v2/sessions", { params })
      .then((r) => {
        if (cancelled) return;
        setItems(r.data?.items || []);
        // Chunk 13 (SV-04) — surface the server-computed
        // `status_counts` so the tab badges show live counts.
        setCounts(r.data?.status_counts || {
          all: 0, active: 0, paused: 0, complete: 0, refused: 0,
        });
      })
      .catch((e) => { if (!cancelled) toast.error(apiErrorMessage(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [debouncedQ, status, activeContext?.id]);

  const ctxName = activeContext?.name || "your active context";

  return (
    <AppShell>
      <main
        data-testid="solva-sessions-page"
        style={{ maxWidth: 920, margin: "0 auto", padding: "24px 24px 60px" }}
      >
        <Link
          to="/app/solva"
          data-testid="solva-sessions-back-link"
          style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
            fontSize: 12, color: "var(--graphite)",
            textDecoration: "none", marginBottom: 14,
          }}
        >
          <ChevronLeft width={14} height={14} />
          Back to Solva
        </Link>
        <h1
          style={{
            fontFamily: "Georgia, serif",
            fontSize: 26, color: "var(--ink)",
            margin: "0 0 4px 0", fontWeight: 600,
          }}
        >
          Your Solva sessions
        </h1>
        <p
          style={{
            fontFamily: "Georgia, serif", fontStyle: "italic",
            fontSize: 14, color: "var(--graphite)",
            margin: "0 0 22px 0",
          }}
        >
          in {ctxName}
        </p>

        {/* Search */}
        <div
          style={{
            display: "flex", alignItems: "center", gap: 8,
            border: "1px solid rgba(0,0,0,0.16)", borderRadius: 2,
            padding: "8px 12px", marginBottom: 14, background: "var(--parchment-light)",
          }}
        >
          <Search width={14} height={14} color="var(--graphite)" />
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by title, framing, or synthesis content…"
            data-testid="solva-sessions-search-input"
            style={{
              border: "none", outline: "none", flex: 1,
              fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
              fontSize: 14, color: "var(--ink)",
            }}
          />
        </div>

        {/* Filter chips with count badges (Chunk 13 SV-04) */}
        <div data-testid="solva-sessions-filters" style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 24 }}>
          {STATUS_CHIPS.map((c) => {
            const selected = status === c.key;
            const count = Number.isFinite(counts?.[c.countKey]) ? counts[c.countKey] : 0;
            return (
              <button
                key={c.key || "all"}
                type="button"
                onClick={() => setStatus(c.key)}
                data-testid={`solva-sessions-filter-${c.key || "all"}`}
                style={{
                  padding: "6px 14px",
                  borderRadius: 999,
                  border: `1px solid ${selected ? "var(--oxblood)" : "rgba(0,0,0,0.18)"}`,
                  background: selected ? "rgba(139,29,44,0.08)" : "var(--parchment-light)",
                  color: selected ? "var(--oxblood)" : "var(--graphite)",
                  fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
                  fontSize: 12, letterSpacing: 0.3,
                  cursor: "pointer",
                  display: "inline-flex", alignItems: "center", gap: 8,
                }}
              >
                <span>{c.label}</span>
                <span
                  data-testid={`solva-sessions-filter-count-${c.key || "all"}`}
                  style={{
                    background: selected ? "rgba(139,29,44,0.12)" : "rgba(0,0,0,0.06)",
                    color: selected ? "var(--oxblood)" : "var(--graphite)",
                    fontSize: 11, letterSpacing: 0.2,
                    padding: "0 7px", borderRadius: 999,
                    minWidth: 18, textAlign: "center",
                    fontWeight: 600,
                  }}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* List */}
        {loading ? (
          <p style={{ color: "var(--graphite)", fontStyle: "italic" }}>Loading…</p>
        ) : items.length === 0 ? (
          <p
            data-testid="solva-sessions-empty"
            style={{ color: "var(--graphite)", fontStyle: "italic", fontFamily: "Georgia, serif" }}
          >
            {/*
             * Chunk 14 SV-05 — verbatim spec copy when a non-empty
             * search query returns zero matches: "No sessions found
             * for '[search term]'. Try a different word or phrase."
             *
             * QA-2026-05-20 SV-02 fix — the original verbatim copy
             * for "no saved sessions" empty state stays untouched.
             */}
            {debouncedQ.trim()
              ? `No sessions found for "${debouncedQ.trim()}". Try a different word or phrase.`
              : (!status
                  ? "No sessions saved yet. Complete a Solva session and it will appear here."
                  : "No sessions match.")}
          </p>
        ) : (
          <ul data-testid="solva-sessions-list" style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {items.map((s) => (
              <li
                key={s.id}
                data-testid={`solva-sessions-item-${s.id}`}
                style={{
                  border: "1px solid rgba(0,0,0,0.06)",
                  borderRadius: 4,
                  background: "var(--parchment-light)",
                  padding: "14px 16px",
                  marginBottom: 10,
                  display: "flex", alignItems: "flex-start",
                  justifyContent: "space-between", gap: 14,
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                    <span
                      style={{
                        fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
                        fontSize: 11, letterSpacing: 0.5,
                        textTransform: "uppercase", color: "var(--oxblood)", fontWeight: 600,
                      }}
                    >
                      {SUBMODULE_LABEL[s.submodule] || s.submodule || "Solva"}
                    </span>
                    <StatusPill status={s.display_status || s.status} />
                  </div>
                  {/* QA-2026-05-20 SV-03 — inline-editable title (Phase D
                       sessions only — legacy v2 sessions retain the
                       intent-only display because they never carried a
                       title field). */}
                  <SessionTitleRow
                    session={s}
                    activeContextId={activeContext?.id}
                    onUpdated={(newTitle) => {
                      setItems((cur) => cur.map((row) => row.id === s.id
                        ? { ...row, title: newTitle }
                        : row));
                    }}
                  />
                  <p
                    style={{
                      fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
                      fontSize: 11, color: "var(--graphite)",
                      margin: 0,
                    }}
                  >
                    {fmtDate(s.updated_at || s.started_at)} · {s.layer || "—"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    // Phase D sessions live at a different route shape than legacy v2.
                    if (s.engine === "phase_d") {
                      navigate(`/app/solva/phase-d/session/${s.id}`);
                    } else {
                      navigate(`/app/solva/session/${s.id}`);
                    }
                  }}
                  data-testid={`solva-sessions-open-${s.id}`}
                  style={{
                    background: "transparent", color: "var(--ink)",
                    border: "1px solid rgba(0,0,0,0.16)",
                    padding: "6px 14px", borderRadius: 2, cursor: "pointer",
                    fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
                    fontSize: 12,
                  }}
                >
                  Open
                </button>
              </li>
            ))}
          </ul>
        )}
      </main>
    </AppShell>
  );
}

function StatusPill({ status }) {
  const s = (status || "").toLowerCase();
  // Chunk 13 (SV-04) — 4-bucket palette per spec:
  //   ACTIVE green · PAUSED amber · COMPLETE blue · REFUSED grey.
  // Legacy raw statuses (blocked_hard, blocked_soft, abandoned) still
  // map to a sensible chip in case a session was migrated mid-flight.
  const palette = {
    active:        { bg: "rgba(50,140,90,0.12)",  fg: "rgb(34,90,55)",     label: "Active" },
    paused:        { bg: "rgba(180,130,50,0.15)", fg: "rgb(120,80,15)",    label: "Paused" },
    complete:      { bg: "rgba(50,100,180,0.12)", fg: "rgb(35,75,140)",    label: "Complete" },
    refused:       { bg: "rgba(0,0,0,0.07)",      fg: "var(--graphite)",   label: "Refused" },
    // Legacy raw-status fallbacks kept for forward compatibility.
    blocked_hard:  { bg: "rgba(0,0,0,0.07)",      fg: "var(--graphite)",   label: "Refused" },
    blocked_soft:  { bg: "rgba(180,130,50,0.15)", fg: "rgb(120,80,15)",    label: "Paused" },
    abandoned:     { bg: "rgba(0,0,0,0.07)",      fg: "var(--graphite)",   label: "Refused" },
    completed:     { bg: "rgba(50,100,180,0.12)", fg: "rgb(35,75,140)",    label: "Complete" },
  }[s] || { bg: "rgba(0,0,0,0.05)", fg: "var(--graphite)", label: (s || "—").toUpperCase() };
  return (
    <span
      data-testid={`solva-sessions-status-pill-${s || "unknown"}`}
      style={{
        display: "inline-block", padding: "1px 8px", borderRadius: 999,
        background: palette.bg, color: palette.fg,
        fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
        fontSize: 10, letterSpacing: 0.4,
        textTransform: "uppercase", fontWeight: 600,
      }}
    >
      {palette.label}
    </span>
  );
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return "—";
  }
}


// QA-2026-05-20 SV-03 — inline-editable title row.
//
// Behaviour matches the Solva brief verbatim: "Clicking the title on a
// session card makes it editable inline." Legacy v2 sessions (which
// never had a title field) fall back to the framing/intent excerpt
// and are NOT editable — we don't write back to the v2 collection
// because the PATCH endpoint lives on the Phase D router and would
// 404 against a v2 session_id. The pencil icon is only shown for
// Phase D rows where editing actually round-trips.
function SessionTitleRow({ session, activeContextId, onUpdated }) {
  const isPhaseD = session.engine === "phase_d";
  const displayed = (session.title || session.intent || "(no framing captured)").slice(0, 200);
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(session.title || "");
  const [saving, setSaving] = useState(false);

  const startEdit = useCallback(() => {
    if (!isPhaseD || !activeContextId) return;
    setValue(session.title || "");
    setEditing(true);
  }, [isPhaseD, activeContextId, session.title]);

  const save = useCallback(async () => {
    if (!isPhaseD || !activeContextId) { setEditing(false); return; }
    const trimmed = (value || "").trim();
    if (!trimmed || trimmed === (session.title || "")) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      const r = await api.patch(
        `/contexts/${activeContextId}/solva/v2/sessions/${session.id}/title`,
        { title: trimmed },
      );
      onUpdated && onUpdated(r.data?.title || trimmed);
      toast.success("Title updated.", { duration: 1800 });
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setSaving(false);
      setEditing(false);
    }
  }, [isPhaseD, activeContextId, value, session.title, session.id, onUpdated]);

  if (editing) {
    return (
      <input
        autoFocus
        type="text"
        value={value}
        disabled={saving}
        onChange={(e) => setValue(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); save(); }
          else if (e.key === "Escape") { setEditing(false); }
        }}
        data-testid={`solva-sessions-title-input-${session.id}`}
        maxLength={80}
        style={{
          width: "100%",
          fontFamily: "Georgia, serif", fontSize: 15,
          color: "var(--ink)", lineHeight: 1.5,
          margin: "0 0 6px 0",
          border: "1px solid var(--oxblood)",
          borderRadius: 3,
          padding: "2px 6px",
          background: "var(--parchment-light)",
        }}
      />
    );
  }

  return (
    <div
      onClick={isPhaseD ? startEdit : undefined}
      data-testid={`solva-sessions-title-${session.id}`}
      data-engine={session.engine || "v2_legacy"}
      role={isPhaseD ? "button" : undefined}
      tabIndex={isPhaseD ? 0 : undefined}
      onKeyDown={isPhaseD ? (e) => { if (e.key === "Enter") startEdit(); } : undefined}
      style={{
        fontFamily: "Georgia, serif", fontSize: 15,
        color: "var(--ink)", lineHeight: 1.5,
        margin: "0 0 6px 0",
        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
        cursor: isPhaseD ? "text" : "default",
        display: "flex", alignItems: "center", gap: 6,
      }}
    >
      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {displayed}
      </span>
      {isPhaseD && (
        <Pencil
          width={11} height={11}
          color="var(--graphite)"
          aria-hidden="true"
          data-testid={`solva-sessions-title-edit-icon-${session.id}`}
        />
      )}
    </div>
  );
}
