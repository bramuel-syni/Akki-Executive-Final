/**
 * Health Dashboard — `/admin/health`.
 *
 * Superadmin-only one-click pre-deploy / pre-demo green light.
 * Pings every external service AKKI depends on and surfaces a per
 * service PASS · WARN · FAIL grid with the corroborating evidence.
 *
 * Lives outside `/app` because it's a platform tool, not a tenant
 * surface — keep it cleanly separated from the role-scoped product.
 */
import React, { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  CheckCircle2, AlertTriangle, XCircle, MinusCircle,
  RefreshCw, Loader2, ShieldCheck,
} from "lucide-react";

const STATUS = {
  pass: { Icon: CheckCircle2, color: "text-emerald-700", bg: "bg-emerald-50",  border: "border-emerald-200", label: "PASS" },
  warn: { Icon: AlertTriangle, color: "text-amber-700",   bg: "bg-amber-50",    border: "border-amber-200",   label: "WARN" },
  fail: { Icon: XCircle,       color: "text-red-700",     bg: "bg-red-50",      border: "border-red-200",     label: "FAIL" },
  skip: { Icon: MinusCircle,   color: "text-[var(--muted)]", bg: "bg-[var(--cream)]", border: "border-[var(--rule)]", label: "SKIP" },
};

const CHECK_LABEL = {
  mongo:       "MongoDB",
  llm:         "LLM (Emergent key)",
  resend:      "Resend (Email)",
  stripe:      "Stripe (Billing)",
  scheduler:   "APScheduler (Cron)",
  cron_secret: "Cron secret",
};

export default function HealthDashboard() {
  const { account, loading: authLoading } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const run = useCallback(async () => {
    setLoading(true);
    try {
      const { data: d } = await api.get("/admin/health/full", { timeout: 60000 });
      setData(d);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { if (account?.is_superadmin) run(); }, [account?.is_superadmin, run]);

  if (authLoading) return null;
  if (!account?.is_superadmin) return <Navigate to="/" replace />;

  return (
    <div className="min-h-screen bg-[var(--cream)] py-12 px-6" data-testid="health-dashboard">
      <div className="max-w-3xl mx-auto">
        <header className="mb-6">
          <p className="akki-overline mb-2 flex items-center gap-1.5">
            <ShieldCheck className="w-3 h-3 text-[var(--accent)]" /> Platform health · superadmin
          </p>
          <h1 className="akki-greeting mb-2">One-click green light.</h1>
          <p className="akki-meta max-w-xl">
            Every external service AKKI depends on, pinged in parallel. Use this before a deploy
            or demo to catch credential drift before a customer does.
          </p>
        </header>

        <div className="bg-white border border-[var(--rule)] rounded-lg p-5 mb-5 flex items-center justify-between" data-testid="health-summary">
          <div>
            <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] font-mono mb-1">Overall</p>
            {data ? (
              <OverallBadge status={data.overall} />
            ) : (
              <p className="text-[14px] text-[var(--muted)] italic">Not yet run.</p>
            )}
            {data?.elapsed_ms && (
              <p className="text-[11px] text-[var(--muted)] mt-1.5 tabular-nums">
                Checked at {new Date(data.checked_at).toLocaleTimeString()} · {data.elapsed_ms}ms
              </p>
            )}
          </div>
          <Button
            onClick={run}
            disabled={loading}
            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white h-10 px-5"
            data-testid="health-refresh-btn"
          >
            {loading
              ? <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" /> Pinging…</>
              : <><RefreshCw className="w-3.5 h-3.5 mr-2" /> Run checks</>}
          </Button>
        </div>

        {!data && !loading && (
          <p className="text-[13px] text-[var(--muted)] italic text-center py-12">
            Click <strong>Run checks</strong> above.
          </p>
        )}

        {data && (
          <div className="space-y-2.5" data-testid="health-checks">
            {Object.entries(data.checks).map(([key, check]) => (
              <CheckRow key={key} keyName={key} check={check} />
            ))}
          </div>
        )}

        {data?.env && (
          <div className="mt-6 text-[10.5px] text-[var(--muted)] font-mono pt-4 border-t border-[var(--rule)]" data-testid="health-env">
            <span>FRONTEND_ORIGIN: {data.env.frontend_origin || "(unset)"}</span>
            <span className="mx-2">·</span>
            <span>node: {data.env.node}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function OverallBadge({ status }) {
  const s = STATUS[status] || STATUS.skip;
  const { Icon, color, bg, border, label } = s;
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm border ${bg} ${border} ${color}`} data-testid={`health-overall-${status}`}>
      <Icon className="w-4 h-4" strokeWidth={2} />
      <span className="font-mono text-[12px] tracking-wider">{label}</span>
    </span>
  );
}

function CheckRow({ keyName, check }) {
  const s = STATUS[check.status] || STATUS.skip;
  const { Icon, color, bg, border, label } = s;
  const detail = check.error || check.note || check.evidence || "";
  return (
    <div
      className={`bg-white border ${border} rounded-md p-3 flex items-start gap-3`}
      data-testid={`health-check-${keyName}`}
    >
      <div className={`w-8 h-8 rounded-sm shrink-0 flex items-center justify-center ${bg} ${color}`}>
        <Icon className="w-4 h-4" strokeWidth={2} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 flex-wrap">
          <p className="text-[13.5px] text-[var(--ink)] font-medium">
            {CHECK_LABEL[keyName] || keyName}
          </p>
          <span className={`text-[10px] tracking-wider font-mono ${color}`} data-testid={`health-check-${keyName}-status`}>
            {label}
          </span>
          {check.latency_ms != null && (
            <span className="text-[10.5px] text-[var(--muted)] font-mono tabular-nums">
              {check.latency_ms}ms
            </span>
          )}
          {check.mode && (
            <span className="text-[10.5px] text-[var(--muted)] font-mono">
              {check.mode}
            </span>
          )}
        </div>
        {detail && (
          <p className="text-[12px] text-[var(--deep)] mt-1 leading-snug break-words">
            {detail}
          </p>
        )}
        {check.jobs && check.jobs.length > 0 && (
          <ul className="mt-1.5 space-y-0.5">
            {check.jobs.map((j) => (
              <li key={j.id} className="text-[11px] font-mono text-[var(--muted)] tabular-nums">
                · {j.id} → {j.next_run_time || "(no schedule)"}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
