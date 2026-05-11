/**
 * AuthEvents — `/admin/auth-events`.
 *
 * Iter61 — companion surface to the iter60 sandbox cookie-poisoning fix.
 * Surfaces 1%-sampled auth attempts so ops can spot rising 401 rates and
 * dual-credential mismatches BEFORE a user reports them. Read-only.
 */
import React, { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { ShieldCheck, RefreshCw, Loader2, AlertTriangle } from "lucide-react";

export default function AuthEvents() {
  const { account, loading: authLoading } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [hours, setHours] = useState("24");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/admin/auth/events?hours=${hours}`);
      setData(data);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [hours]);
  useEffect(() => { load(); }, [load]);

  if (authLoading) return null;
  if (!account?.is_superadmin) return <Navigate to="/app" replace />;

  const failRate = data?.failure_rate_pct ?? 0;
  const dualMismatch = data?.dual_credentials_mismatched ?? 0;

  return (
    <div className="min-h-screen bg-[var(--cream)] py-10 px-6" data-testid="auth-events-dashboard">
      <div className="akki-w-medium">
        <header className="mb-8 flex items-end justify-between gap-6 flex-wrap">
          <div>
            <p className="akki-overline mb-2 flex items-center gap-1.5">
              <ShieldCheck className="w-3 h-3 text-[var(--accent)]" /> Auth observability · superadmin
            </p>
            <h1 className="akki-greeting mb-2">Who got through.</h1>
            <p className="akki-meta max-w-2xl">
              1% sample of auth attempts (failures always logged). Watch
              the failure rate and dual-credential mismatches — that's how
              the sandbox cookie-poisoning bug showed up.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Select value={hours} onValueChange={setHours}>
              <SelectTrigger
                className="h-9 w-[140px] bg-white border-[var(--rule)]"
                data-testid="auth-events-window-select"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1">Last hour</SelectItem>
                <SelectItem value="24">Last 24 hours</SelectItem>
                <SelectItem value="168">Last 7 days</SelectItem>
                <SelectItem value="720">Last 30 days</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="sm"
              onClick={load}
              disabled={loading}
              className="h-9 border-[var(--rule)]"
              data-testid="auth-events-refresh"
            >
              {loading ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
              Refresh
            </Button>
          </div>
        </header>

        <section className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8" data-testid="auth-events-tiles">
          <Tile label="Sampled" value={data ? data.sampled_events.toLocaleString() : "—"} />
          <Tile label="Successes" value={data ? data.success.toLocaleString() : "—"} accent={(data?.success ?? 0) > 0} />
          <Tile label="Failures"  value={data ? data.failure.toLocaleString() : "—"} warn={(data?.failure ?? 0) > 0} />
          <Tile label="Failure rate" value={`${failRate}%`} warn={failRate >= 10} />
        </section>

        {dualMismatch > 0 && (
          <div
            className="mb-8 bg-amber-50 border border-amber-200 rounded-sm px-5 py-4 flex items-start gap-3"
            data-testid="auth-events-dual-mismatch-banner"
          >
            <AlertTriangle className="w-4 h-4 text-amber-700 mt-0.5" />
            <div>
              <p className="akki-serif text-[15px] text-amber-900 mb-1">
                {dualMismatch} dual-credential mismatch{dualMismatch === 1 ? "" : "es"} in window
              </p>
              <p className="text-[12.5px] text-amber-800">
                Users with stale cookies AND fresh Bearer JWTs (or vice versa).
                Self-heals via Bearer-first ordering, but a rising count
                signals a UX glitch worth investigating.
              </p>
            </div>
          </div>
        )}

        <section className="grid md:grid-cols-2 gap-6 mb-8">
          <PanelTable
            title="Failure reasons"
            testid="auth-events-failures"
            rows={data?.by_failure_reason || []}
            keyField="reason"
            countField="count"
            empty="No failures in window."
          />
          <PanelTable
            title="By credential"
            testid="auth-events-credentials"
            rows={data?.by_credential || []}
            keyField="credential"
            countField="count"
            empty="No events in window."
          />
        </section>

        <PanelTable
          title="Top paths"
          testid="auth-events-paths"
          rows={data?.top_paths || []}
          keyField="path"
          countField="count"
          empty="No events in window."
          mono
        />

        <section className="bg-white border border-[var(--rule)] rounded-sm mt-8" data-testid="auth-events-recent">
          <header className="px-5 py-3.5 border-b border-[var(--rule)]">
            <h2 className="akki-serif text-[17px] text-[var(--ink)]">Recent (last 50)</h2>
          </header>
          {(data?.recent || []).length === 0 ? (
            <p className="px-5 py-10 text-center text-[12.5px] italic text-[var(--muted)]">
              No events.
            </p>
          ) : (
            <ul className="divide-y divide-[var(--rule)] text-[12.5px]">
              {data.recent.map((r, i) => (
                <li
                  key={i}
                  className={`px-5 py-2.5 grid grid-cols-12 gap-3 ${r.ok ? "" : "bg-rose-50/50"}`}
                  data-testid={`auth-events-row-${i}`}
                >
                  <span className="col-span-3 font-mono text-[11px] text-[var(--muted)]">
                    {new Date(r.at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                  </span>
                  <span className={`col-span-1 text-[10.5px] uppercase tracking-[0.14em] ${r.ok ? "text-emerald-700" : "text-rose-700"}`}>
                    {r.ok ? "ok" : "fail"}
                  </span>
                  <span className="col-span-2 text-[10.5px] text-[var(--muted)] uppercase tracking-[0.12em]">
                    {(r.credentials || []).join("+") || "none"}
                  </span>
                  <span className="col-span-1 text-[10.5px] text-[var(--accent)] uppercase tracking-[0.12em]">
                    {r.authed_via || (r.dual_mismatch ? "mix" : "")}
                  </span>
                  <span className="col-span-3 font-mono text-[11px] text-[var(--deep)] truncate" title={r.path}>
                    {r.method} {r.path}
                  </span>
                  <span className="col-span-2 text-[11px] text-[var(--muted)] italic truncate" title={r.reason || ""}>
                    {r.reason || ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

function Tile({ label, value, accent = false, warn = false }) {
  return (
    <div
      className={`bg-white border rounded-sm px-5 py-4 ${warn ? "border-amber-300" : accent ? "border-[var(--severity)]/30" : "border-[var(--rule)]"}`}
      data-testid={`auth-events-tile-${label.toLowerCase().replace(/\s+/g, "-")}`}
    >
      <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] font-mono">
        {label}
      </p>
      <p className={`akki-serif text-[26px] mt-1 tabular-nums ${
        warn ? "text-amber-700" : accent ? "text-[var(--severity)]" : "text-[var(--ink)]"
      }`}>
        {value}
      </p>
    </div>
  );
}

function PanelTable({ title, rows, keyField, countField, empty, mono = false, testid }) {
  return (
    <section className="bg-white border border-[var(--rule)] rounded-sm" data-testid={testid}>
      <header className="px-5 py-3.5 border-b border-[var(--rule)]">
        <h2 className="akki-serif text-[17px] text-[var(--ink)]">{title}</h2>
      </header>
      {rows.length === 0 ? (
        <p className="px-5 py-8 text-center text-[12.5px] italic text-[var(--muted)]">{empty}</p>
      ) : (
        <ul className="divide-y divide-[var(--rule)]">
          {rows.map((r, i) => (
            <li key={i} className="px-5 py-2.5 flex items-center justify-between gap-4">
              <span className={`text-[var(--ink)] truncate ${mono ? "font-mono text-[12px]" : "text-[13px]"}`}>
                {r[keyField]}
              </span>
              <span className="akki-serif text-[16px] text-[var(--accent)] tabular-nums">
                {r[countField]}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
