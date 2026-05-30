/**
 * Phase P2 D.2 (2026-02) — Public status page.
 *
 * Reads /api/health/composite (no auth) and renders coloured dots for
 * each dependency. Refreshes every 60s. Voice-clean copy. Sits at
 * /status (public route).
 *
 * Visual language matches the marketing surface — cream background,
 * oxblood accent for fail, slate for warn, sage for ok. The dot
 * primitive ships from `lucide-react` (Dot icon) at three sizes /
 * three colours.
 */
import React, { useEffect, useState, useCallback } from "react";
import { CheckCircle2, AlertCircle, XCircle, RefreshCw } from "lucide-react";
import WebsiteShell from "../website/WebsiteShell";

const API = process.env.REACT_APP_BACKEND_URL || "";

const PROBE_LABELS = {
  mongo:            "Database",
  llm_key:          "Reasoning models",
  sendgrid:         "Email delivery",
  oauth_google:     "Google sign-in",
  oauth_microsoft:  "Microsoft sign-in",
  solva_engine:     "Solva engine",
};

function StateIcon({ state }) {
  if (state === "ok") {
    return <CheckCircle2 className="w-4 h-4 text-emerald-600" aria-hidden="true" />;
  }
  if (state === "warn") {
    return <AlertCircle className="w-4 h-4 text-amber-600" aria-hidden="true" />;
  }
  return <XCircle className="w-4 h-4 text-[var(--oxblood)]" aria-hidden="true" />;
}

function OverallBanner({ overall }) {
  let bg, fg, copy;
  if (overall === "ok") {
    bg = "bg-emerald-50 border-emerald-200"; fg = "text-emerald-900";
    copy = "All systems operational.";
  } else if (overall === "warn") {
    bg = "bg-amber-50 border-amber-200"; fg = "text-amber-900";
    copy = "Some dependencies are not configured. The product is up.";
  } else {
    bg = "bg-red-50 border-red-200"; fg = "text-red-900";
    copy = "An issue is affecting service. The team has been alerted.";
  }
  return (
    <div
      className={`${bg} ${fg} rounded-sm border px-4 py-3 text-[14px]`}
      data-testid={`status-overall-${overall}`}
    >
      <strong className="font-semibold capitalize">{overall === "ok" ? "Operational" : overall}.</strong>{" "}
      {copy}
    </div>
  );
}

export default function StatusPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      // eslint-disable-next-line no-restricted-syntax -- /status is public; using raw fetch avoids sending auth cookies to an unauthenticated probe.
      const r = await fetch(`${API}/api/health/composite`, {
        method: "GET",
        credentials: "omit",
        headers: { "Accept": "application/json" },
      });
      if (!r.ok) throw new Error(`status ${r.status}`);
      setData(await r.json());
    } catch (e) {
      setErr(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60_000);
    return () => clearInterval(t);
  }, [load]);

  const probes = data?.probes || {};
  const checkedAt = data?.checked_at ? new Date(data.checked_at * 1000) : null;

  return (
    <WebsiteShell
      title="Status — Akki"
      description="Live operational status of Akki's dependencies."
      pathname="/status"
    >
      <section className="website-section section-reveal" data-testid="status-page">
        <p className="kicker">SYSTEM STATUS</p>
        <h1 className="akki-serif text-4xl sm:text-5xl text-[var(--ink)] mb-2" data-testid="status-h1">
          Status.
        </h1>
        <p className="dek mb-6" style={{ maxWidth: "60ch" }}>
          A live read of the services Akki depends on. Each row is the
          dependency, not a marketing tile.
        </p>

        <div className="mb-6">
          {loading && !data && (
            <p className="text-[14px] text-[var(--muted)]" data-testid="status-loading">
              Reading status…
            </p>
          )}
          {err && (
            <p className="text-[14px] text-[var(--oxblood)]" data-testid="status-error">
              Status check failed: {err}
            </p>
          )}
          {data && <OverallBanner overall={data.overall} />}
        </div>

        <ul
          className="divide-y divide-[var(--rule)] border border-[var(--rule)] rounded-sm bg-white"
          data-testid="status-probe-list"
        >
          {Object.entries(probes).map(([key, p]) => (
            <li
              key={key}
              className="flex items-start justify-between gap-3 px-4 py-3"
              data-testid={`status-probe-${key}`}
            >
              <div className="flex items-start gap-3 min-w-0">
                <StateIcon state={p.state} />
                <div className="min-w-0">
                  <p className="text-[14px] text-[var(--ink)] font-medium" data-testid={`status-probe-${key}-label`}>
                    {PROBE_LABELS[key] || key}
                  </p>
                  <p
                    className="text-[12.5px] text-[var(--muted)] mt-0.5"
                    data-testid={`status-probe-${key}-detail`}
                  >
                    {p.detail}
                  </p>
                </div>
              </div>
              <span
                className="text-[11px] font-mono uppercase tracking-wider text-[var(--muted)] flex-shrink-0 pt-0.5"
                data-testid={`status-probe-${key}-state`}
              >
                {p.state}
              </span>
            </li>
          ))}
        </ul>

        <div className="mt-6 flex items-center gap-3 text-[12px] text-[var(--muted)] font-mono">
          {checkedAt && (
            <span data-testid="status-checked-at">
              Checked {checkedAt.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={load}
            className="inline-flex items-center gap-1 text-[var(--deep)] hover:text-[var(--ink)] transition-colors"
            data-testid="status-refresh-btn"
          >
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
        </div>
      </section>
    </WebsiteShell>
  );
}
