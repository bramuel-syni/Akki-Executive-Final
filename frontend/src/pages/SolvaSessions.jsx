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
import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Search, ChevronLeft } from "lucide-react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";

const STATUS_CHIPS = [
  { key: "",          label: "All" },
  { key: "active",    label: "Active" },
  { key: "complete",  label: "Complete" },
  { key: "refused",   label: "Refused" },
  { key: "paused",    label: "Paused" },
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
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const debouncedQ = useDebouncedValue(q, 280);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const params = {};
    if (debouncedQ.trim()) params.q = debouncedQ.trim();
    if (status) params.status = status;
    api.get("/solva/v2/sessions", { params })
      .then((r) => { if (!cancelled) setItems(r.data?.items || []); })
      .catch((e) => { if (!cancelled) toast.error(apiErrorMessage(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [debouncedQ, status]);

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
            placeholder="Search by framing keyword…"
            data-testid="solva-sessions-search-input"
            style={{
              border: "none", outline: "none", flex: 1,
              fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
              fontSize: 14, color: "var(--ink)",
            }}
          />
        </div>

        {/* Filter chips */}
        <div data-testid="solva-sessions-filters" style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 24 }}>
          {STATUS_CHIPS.map((c) => {
            const selected = status === c.key;
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
                }}
              >
                {c.label}
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
            No sessions match.
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
                    <StatusPill status={s.status} />
                  </div>
                  <p
                    style={{
                      fontFamily: "Georgia, serif", fontSize: 15,
                      color: "var(--ink)", lineHeight: 1.5,
                      margin: "0 0 6px 0",
                      whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                    }}
                  >
                    {(s.intent || "(no framing captured)").slice(0, 200)}
                  </p>
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
                  onClick={() => navigate(`/app/solva/session/${s.id}`)}
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
  const palette = {
    active:        { bg: "rgba(50,100,180,0.10)", fg: "var(--graphite)", label: "Active" },
    complete:      { bg: "rgba(50,140,90,0.10)",  fg: "var(--graphite)", label: "Complete" },
    refused:       { bg: "rgba(139,29,44,0.10)",  fg: "var(--oxblood)", label: "Refused" },
    paused:        { bg: "rgba(0,0,0,0.05)",       fg: "var(--graphite)", label: "Paused" },
    blocked_hard:  { bg: "rgba(139,29,44,0.10)",  fg: "var(--oxblood)", label: "Blocked" },
    blocked_soft:  { bg: "rgba(180,130,50,0.10)", fg: "var(--oxblood)", label: "Caution" },
    abandoned:     { bg: "rgba(0,0,0,0.05)",       fg: "var(--graphite)", label: "Abandoned" },
  }[s] || { bg: "rgba(0,0,0,0.05)", fg: "var(--graphite)", label: s || "—" };
  return (
    <span
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
