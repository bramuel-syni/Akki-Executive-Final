/**
 * H3 — Trust Center v1 page.
 *
 * Two tabs:
 *   • "This session" — promise summary + per-turn list, with a
 *     drill-down panel that shows the 4-row "you sent / sent to LLM /
 *     LLM returned / you saw" evidence. The promise is factual, not
 *     marketing.
 *   • "All activity" — cross-conversation aggregate within accessible
 *     contexts, with filters.
 *
 * Conservative plaintext policy
 * -----------------------------
 * The drill-down panel shows the SHA-256 of the user's raw input by
 * default. The "View raw input" button hits a separate endpoint that
 * audit-logs the access, and opens a modal with a clear
 * "This view is audit-logged" notice at the top.
 *
 * No marketing language. Trust Center is factual reporting.
 */
import React, { useEffect, useMemo, useState, useCallback } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import {
  ShieldCheck, Hash, ChevronRight, ChevronDown, Download,
  Eye, AlertTriangle, FileSearch, X, Filter, Lock, Info,
} from "lucide-react";
import axios from "axios";
import {
  Popover, PopoverTrigger, PopoverContent,
} from "../components/ui/popover";
import TrustCenterTour from "../components/trust/TrustCenterTour";

import { resolveBackendOrigin } from "@/lib/api";
const API = resolveBackendOrigin();

function useAuthHeaders() {
  return useMemo(() => {
    const token = localStorage.getItem("akki_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);
}

// ─────────────────────────────────────────────────────────────────────
// Standards footer — single row, subtle. Each segment tooltips
// what it maps to. NO marketing.
// ─────────────────────────────────────────────────────────────────────
const STANDARDS = [
  { code: "SOC2 CC4/CC6/CC7", tip: "Monitoring activities; logical & physical access; system operations." },
  { code: "GDPR Art. 5, 25, 28, 32", tip: "Lawful processing; privacy by design; processor obligations; security of processing." },
  { code: "ISO 27001 A.8.2, A.12.4.1", tip: "Information classification; event logging." },
  { code: "NIST AI RMF Map-3.4", tip: "Risks of AI-generated content tracked & documented." },
  { code: "EU AI Act Art. 50", tip: "Transparency obligations for AI system outputs." },
];

function StandardsFooter() {
  return (
    <footer
      data-testid="tc-standards-footer"
      className="mt-12 pt-6 border-t border-[var(--cream-deep)] text-[11px] text-[var(--muted)]"
    >
      <div className="flex flex-wrap gap-x-4 gap-y-2">
        <span className="text-[var(--deep)]">Standards aligned:</span>
        {STANDARDS.map((s) => (
          <span
            key={s.code}
            title={s.tip}
            className="cursor-help hover:text-[var(--ink)] transition-colors"
            data-testid={`tc-standard-${s.code.split(" ")[0]}`}
          >
            {s.code}
          </span>
        ))}
      </div>
    </footer>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Drill-down panel — 4-row comparison
// ─────────────────────────────────────────────────────────────────────
function DrilldownPanel({ chatId, messageId, onClose }) {
  const hdrs = useAuthHeaders();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [plaintextOpen, setPlaintextOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(
          `${API}/api/trust-center/session/${chatId}/turn/${messageId}`,
          { headers: hdrs },
        );
        if (!cancelled) setData(r.data);
      } catch (e) {
        if (!cancelled) setErr(e?.response?.data?.detail || String(e));
      }
    })();
    return () => { cancelled = true; };
  }, [chatId, messageId, hdrs]);

  if (err) {
    return (
      <div className="border border-[var(--cream-deep)] rounded-lg p-6 mt-3 bg-[var(--cream)] text-[13px] text-[var(--ink)]">
        Could not load drill-down: {err}
      </div>
    );
  }
  if (!data) {
    return (
      <div className="border border-[var(--cream-deep)] rounded-lg p-6 mt-3 bg-[var(--cream)] text-[13px] text-[var(--muted)]">
        Loading evidence…
      </div>
    );
  }

  return (
    <div
      data-testid="tc-drilldown-panel"
      className="border border-[var(--cream-deep)] rounded-lg mt-3 bg-[var(--cream)] overflow-hidden"
    >
      <div className="flex items-start justify-between px-5 py-3 border-b border-[var(--cream-deep)] bg-[var(--cream-deep)]/40">
        <div>
          <div className="text-[12px] uppercase tracking-wide text-[var(--muted)]">
            Turn evidence
          </div>
          <div className="text-[14px] text-[var(--ink)] mt-0.5">
            {new Date(data.ts).toLocaleString()} ·
            <span className="ml-2 text-[var(--deep)]">
              shielded-by: {data.shield_invocation?.shielded_by}
            </span>
            {data.shield_invocation?.duration_ms != null && (
              <span className="ml-2 text-[var(--muted)]">
                · {data.shield_invocation.duration_ms} ms
              </span>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-[var(--muted)] hover:text-[var(--ink)] transition-colors"
          data-testid="tc-drilldown-close"
          aria-label="Close drilldown"
        >
          <X className="w-4 h-4" strokeWidth={1.7} />
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 p-5">
        {/* (1) What YOU sent — hash only */}
        <div data-testid="tc-evidence-input-hash" className="space-y-2">
          <div className="text-[11px] uppercase tracking-wide text-[var(--muted)] flex items-center gap-1">
            <Hash className="w-3 h-3" /> What you sent
          </div>
          <div className="font-mono text-[11px] text-[var(--ink)] break-all leading-relaxed bg-[var(--cream-deep)]/40 p-2.5 rounded">
            {data.what_you_sent_sha256}
          </div>
          <div className="text-[11px] text-[var(--muted)]">
            SHA-256 of raw input. The text itself stays in your tenant.
          </div>
          <button
            onClick={() => setPlaintextOpen(true)}
            data-testid="tc-view-raw-input-btn"
            className="text-[11px] inline-flex items-center gap-1 text-[var(--deep)] hover:text-[var(--ink)] underline decoration-dotted underline-offset-2 transition-colors"
          >
            <Eye className="w-3 h-3" /> View raw input
          </button>
        </div>

        {/* (2) What Synisense sent to LLM — tokenized */}
        <div data-testid="tc-evidence-to-llm" className="space-y-2">
          <div className="text-[11px] uppercase tracking-wide text-[var(--muted)] flex items-center gap-1">
            <Lock className="w-3 h-3" /> Sent to LLM
          </div>
          <div className="text-[12px] text-[var(--ink)] leading-relaxed bg-[var(--cream-deep)]/40 p-2.5 rounded min-h-[80px] whitespace-pre-wrap break-words">
            {data.what_synisense_sent_to_llm || <em className="text-[var(--muted)]">Not retained for this turn (audit chain still verifiable).</em>}
          </div>
          <div className="text-[11px] text-[var(--muted)]">
            Tokenized. Identifiers replaced with placeholders.
          </div>
        </div>

        {/* (3) What LLM returned — tokenized */}
        <div data-testid="tc-evidence-from-llm" className="space-y-2">
          <div className="text-[11px] uppercase tracking-wide text-[var(--muted)] flex items-center gap-1">
            <ChevronRight className="w-3 h-3" /> LLM returned
          </div>
          <div className="text-[12px] text-[var(--ink)] leading-relaxed bg-[var(--cream-deep)]/40 p-2.5 rounded min-h-[80px] whitespace-pre-wrap break-words">
            {data.what_llm_returned || <em className="text-[var(--muted)]">Not retained for this turn.</em>}
          </div>
          <div className="text-[11px] text-[var(--muted)]">
            LLM never saw the underlying identifiers.
          </div>
        </div>

        {/* (4) What you saw — re-identified */}
        <div data-testid="tc-evidence-user-saw" className="space-y-2">
          <div className="text-[11px] uppercase tracking-wide text-[var(--muted)] flex items-center gap-1">
            <Eye className="w-3 h-3" /> What you saw
          </div>
          <div className="text-[12px] text-[var(--ink)] leading-relaxed bg-[var(--cream-deep)]/40 p-2.5 rounded min-h-[80px] whitespace-pre-wrap break-words">
            {data.what_you_saw || <em className="text-[var(--muted)]">No reply retained.</em>}
          </div>
          <div className="text-[11px] text-[var(--muted)]">
            Re-identified locally. Hard PII stays masked.
          </div>
        </div>
      </div>

      {/* Audit chain footer */}
      <div className="px-5 py-3 border-t border-[var(--cream-deep)] bg-[var(--cream-deep)]/40">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-[11px]">
          <div>
            <div className="text-[var(--muted)] uppercase tracking-wide">Shield audit_id</div>
            <div className="font-mono text-[var(--ink)] break-all">
              {data.audit_chain?.audit_id || "—"}
            </div>
          </div>
          <div>
            <div className="text-[var(--muted)] uppercase tracking-wide">Chat audit row</div>
            <div className="font-mono text-[var(--ink)] break-all">
              {data.audit_chain?.chat_audit_id || "—"}
            </div>
          </div>
          <div>
            <div className="text-[var(--muted)] uppercase tracking-wide">Chain</div>
            <div className={data.audit_chain?.chain_valid ? "text-emerald-700" : "text-amber-700"}>
              {data.audit_chain?.chain_valid ? "verified" : "incomplete"}
            </div>
          </div>
        </div>
      </div>

      {/* Plaintext modal */}
      {plaintextOpen && (
        <PlaintextModal
          chatId={chatId}
          messageId={messageId}
          onClose={() => setPlaintextOpen(false)}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Plaintext modal — explicit, audit-logged view of raw input
// ─────────────────────────────────────────────────────────────────────
function PlaintextModal({ chatId, messageId, onClose }) {
  const hdrs = useAuthHeaders();
  const [text, setText] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(
          `${API}/api/trust-center/session/${chatId}/turn/${messageId}/plaintext`,
          { headers: hdrs },
        );
        if (!cancelled) setText(r.data);
      } catch (e) {
        if (!cancelled) setErr(e?.response?.data?.detail || String(e));
      }
    })();
    return () => { cancelled = true; };
  }, [chatId, messageId, hdrs]);

  return (
    <div
      data-testid="tc-plaintext-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="bg-[var(--cream)] border border-[var(--cream-deep)] rounded-lg max-w-2xl w-full max-h-[80vh] overflow-hidden shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="px-5 py-3 border-b border-[var(--cream-deep)] bg-amber-50/60 flex items-start gap-3"
          data-testid="tc-plaintext-audit-notice"
        >
          <AlertTriangle className="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" strokeWidth={1.7} />
          <div className="flex-1">
            <div className="text-[13px] text-[var(--ink)] font-medium">
              This view is audit-logged
            </div>
            <div className="text-[11.5px] text-[var(--deep)] mt-0.5">
              The system has recorded that you (or a context superadmin) opened
              the raw plaintext for this turn. The event itself is in the
              audit chain.
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-[var(--muted)] hover:text-[var(--ink)] transition-colors"
            data-testid="tc-plaintext-modal-close"
          >
            <X className="w-4 h-4" strokeWidth={1.7} />
          </button>
        </div>
        <div className="px-5 py-4 overflow-y-auto max-h-[60vh]">
          {err && <div className="text-[13px] text-rose-700">{err}</div>}
          {text && (
            <pre
              data-testid="tc-plaintext-content"
              className="font-mono text-[12.5px] text-[var(--ink)] whitespace-pre-wrap break-words bg-[var(--cream-deep)]/40 p-3 rounded"
            >
              {text.plaintext}
            </pre>
          )}
          {!text && !err && (
            <div className="text-[13px] text-[var(--muted)]">Loading…</div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// "This session" view
// ─────────────────────────────────────────────────────────────────────
function SessionView({ chatId }) {
  const hdrs = useAuthHeaders();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [openTurn, setOpenTurn] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(
        `${API}/api/trust-center/session/${chatId}`,
        { headers: hdrs },
      );
      setData(r.data);
    } catch (e) {
      setErr(e?.response?.data?.detail || String(e));
    }
  }, [chatId, hdrs]);

  useEffect(() => {
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [load]);

  if (err) {
    return (
      <div data-testid="tc-session-error" className="text-[13px] text-rose-700">
        Could not load Trust Center for this session: {err}
      </div>
    );
  }
  if (!data) return <div className="text-[13px] text-[var(--muted)]">Loading…</div>;

  if (data.shield_status === "pre_shield_v1") {
    return (
      <div data-testid="tc-session-pre-shield-empty" className="space-y-4">
        <div className="text-[14px] text-[var(--ink)]">
          This conversation predates Shield v1.x. Counters will populate
          after maintenance back-fill.
        </div>
        <div className="text-[11.5px] text-[var(--muted)]">
          (Back-fill is tracked in the H4 status page — link will appear here when ready.)
        </div>
      </div>
    );
  }

  const ps = data.promise_summary || {};
  const isBackfilled = data.shield_status === "backfilled";
  const bfMeta = data.backfill_metadata || {};

  return (
    <div data-testid="tc-session-view" className="space-y-6">
      {/* Promise statement */}
      <div>
        <div
          data-testid="tc-promise-statement"
          className="text-[18px] text-[var(--ink)] leading-relaxed"
        >
          Akki kept your sensitive data off the LLM in <span className="font-medium">{data.chat_title}</span>.
        </div>
        <div className="text-[12.5px] text-[var(--muted)] mt-1">
          Context: {data.context_name || "—"}
        </div>
      </div>

      {/* H4 — Back-fill banner. Shows when the chat was reconstructed
          via the maintenance back-fill rather than recorded live. */}
      {isBackfilled && (
        <div
          data-testid="tc-backfill-banner"
          className="bg-amber-50/60 border border-amber-200 rounded-lg p-4 space-y-1"
        >
          <div className="text-[12.5px] text-[var(--ink)]">
            This conversation was back-filled through Shield v1.x on{" "}
            <span className="font-medium">
              {bfMeta.completed_at
                ? new Date(bfMeta.completed_at).toLocaleDateString()
                : "—"}
            </span>
            .{" "}
            <span className="text-[var(--deep)]">
              {ps.identifiers_shielded_total ?? 0} identifier
              {ps.identifiers_shielded_total === 1 ? "" : "s"} detected
              in the historical content.
            </span>
          </div>
          <div className="text-[11px] text-[var(--muted)]">
            Back-fill batch:{" "}
            <span className="font-mono">{bfMeta.batch_id || "—"}</span>{" "}
            · Audit rows derive from a separate ``backfill_chain_v1``
            so the live audit chain stays clean.
          </div>
        </div>
      )}

      {/* Counters grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="tc-promise-counters">
        <Counter
          label="Identifiers shielded"
          value={ps.identifiers_shielded_total ?? 0}
          infoSlot={<DeIdSummaryInfoPopover />}
        />
        <Counter label="Turns with redaction" value={`${ps.turns_with_redaction ?? 0} / ${ps.total_turns ?? 0}`} />
        <Counter label="LLM calls" value={ps.llm_calls ?? 0} />
        <Counter label="Models" value={(ps.models_used || []).join(", ") || "—"} small />
      </div>

      {/* Per-class breakdown */}
      {ps.by_class && Object.keys(ps.by_class).length > 0 && (
        <div data-testid="tc-by-class" className="space-y-1.5">
          <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">
            What Shield removed
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(ps.by_class).map(([k, v]) => (
              <span
                key={k}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-[var(--cream-deep)]/60 text-[12px] text-[var(--ink)] rounded"
              >
                <ShieldCheck className="w-3 h-3 text-emerald-700" />
                {k} <span className="text-[var(--deep)] font-medium">×{v}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Caveats — gray, small, but visible */}
      <div
        data-testid="tc-caveats"
        className="bg-[var(--cream-deep)]/40 border border-[var(--cream-deep)] rounded-lg p-4 space-y-1.5"
      >
        {(data.caveats || []).map((c, i) => (
          <div key={i} className="text-[11.5px] text-[var(--deep)] leading-relaxed">
            • {c}
          </div>
        ))}
      </div>

      {/* Turn list */}
      <div className="space-y-2">
        <div className="text-[11px] uppercase tracking-wide text-[var(--muted)] mb-2">
          Per-turn detail
        </div>
        <div
          data-testid="tc-perturn-deviation-note"
          className="text-[11.5px] text-[var(--muted)] leading-relaxed -mt-1 mb-1"
        >
          Per-turn counts. Session totals above may be larger because they
          include historical context and grounding replay.
        </div>
        {(data.turns || []).map((t) => (
          <div key={t.message_id} data-testid="tc-turn-row">
            <button
              onClick={() => setOpenTurn(openTurn === t.message_id ? null : t.message_id)}
              data-testid="tc-turn-open-btn"
              className="w-full text-left flex items-center gap-3 px-4 py-3 bg-[var(--cream)] border border-[var(--cream-deep)] rounded-lg hover:bg-[var(--cream-deep)]/40 transition-colors"
            >
              {openTurn === t.message_id ? (
                <ChevronDown className="w-4 h-4 text-[var(--muted)]" />
              ) : (
                <ChevronRight className="w-4 h-4 text-[var(--muted)]" />
              )}
              <div className="flex-1 text-[12.5px] text-[var(--ink)]">
                {new Date(t.ts).toLocaleString()}
                {t.shielded && (
                  <span className="ml-3 inline-flex items-center gap-1 text-emerald-700 text-[11.5px]">
                    <ShieldCheck className="w-3 h-3" />
                    {Object.entries(t.by_class).map(([k, v]) => `${k}×${v}`).join(", ")}
                  </span>
                )}
                {!t.shielded && (
                  <span className="ml-3 text-[var(--muted)] text-[11.5px]">
                    no identifiers detected
                  </span>
                )}
                {t.is_backfill && (
                  <span
                    data-testid="tc-turn-backfill-badge"
                    title={`Back-filled in batch ${t.backfill_batch_id || ""} from original ts ${t.original_message_ts || ""}`}
                    className="ml-3 inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-[var(--deep)] border border-[var(--cream-deep)] rounded"
                  >
                    back-filled
                  </span>
                )}
              </div>
              <span className="text-[10.5px] text-[var(--muted)] font-mono">
                {t.audit_id ? t.audit_id.slice(0, 16) + "…" : "—"}
              </span>
            </button>
            {openTurn === t.message_id && (
              <DrilldownPanel
                chatId={chatId}
                messageId={t.message_id}
                onClose={() => setOpenTurn(null)}
              />
            )}
          </div>
        ))}
        {(data.turns || []).length === 0 && (
          <div className="text-[13px] text-[var(--muted)]">
            No turns yet in this conversation.
          </div>
        )}
      </div>
    </div>
  );
}

function Counter({ label, value, small = false, infoSlot = null }) {
  return (
    <div className="bg-[var(--cream)] border border-[var(--cream-deep)] rounded-lg p-4">
      <div className="text-[10.5px] uppercase tracking-wide text-[var(--muted)] flex items-center gap-1.5">
        <span>{label}</span>
        {infoSlot}
      </div>
      <div className={`mt-1 text-[var(--ink)] ${small ? "text-[14px]" : "text-[22px]"} leading-tight`}>
        {value}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Session-totals vs per-turn methodology popover.
//
// Trust Center surfaces two complementary de-identification views:
//   • Session-level headline counters (counted across everything Shield
//     processed for the session — turn input + historical context
//     replay + grounding material).
//   • Per-turn drill-down (counted only at the turn boundary).
//
// The session total is therefore a **superset** of the sum of
// per-turn counts. This popover is the in-product transparency note
// for that gap. The trigger button renders unconditionally per the
// DOM-unconditional rule; popover content opens on click.
//
// Wording is anchored on three audit-anchor phrases:
//   "Session totals", "per-turn", "superset".
// Methodology doc: /app/memory/sprints/TRUST_CENTER_METHODOLOGY.md
// ─────────────────────────────────────────────────────────────────────
function DeIdSummaryInfoPopover() {
  return (
    <Popover>
      <PopoverTrigger
        type="button"
        data-testid="tc-deidsummary-info-button"
        aria-label="What does Identifiers shielded count?"
        className="inline-flex items-center justify-center w-3.5 h-3.5 text-[var(--muted)] hover:text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--deep)] rounded-sm transition-colors"
      >
        <Info className="w-3.5 h-3.5" strokeWidth={1.7} />
      </PopoverTrigger>
      <PopoverContent
        data-testid="tc-deidsummary-info-content"
        align="start"
        sideOffset={6}
        className="w-[340px] text-[12px] text-[var(--ink)] leading-relaxed bg-[var(--cream)] border-[var(--cream-deep)] p-4 space-y-2"
      >
        <div className="text-[10.5px] uppercase tracking-wide text-[var(--muted)]">
          How this count is built
        </div>
        <p>
          Session totals count every place Shield touched data — including
          historical context and grounding replay for this session.
          Per-turn totals below count only what Shield processed at each
          specific turn.
        </p>
        <p>
          Both views are factually accurate to their question; expect
          the session total to be a superset of the sum of per-turn counts.
        </p>
      </PopoverContent>
    </Popover>
  );
}

// ─────────────────────────────────────────────────────────────────────
// "All activity" view
// ─────────────────────────────────────────────────────────────────────
function ActivityView() {
  const hdrs = useAuthHeaders();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [filters, setFilters] = useState({ pii_class: "", model: "" });
  const [openTurn, setOpenTurn] = useState(null);

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      params.set("limit", "50");
      if (filters.pii_class) params.set("pii_class", filters.pii_class);
      if (filters.model) params.set("model", filters.model);
      const r = await axios.get(
        `${API}/api/trust-center/activity?${params.toString()}`,
        { headers: hdrs },
      );
      setData(r.data);
    } catch (e) {
      setErr(e?.response?.data?.detail || String(e));
    }
  }, [filters, hdrs]);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const exportJson = useCallback(async () => {
    const params = new URLSearchParams();
    if (filters.pii_class) params.set("pii_class", filters.pii_class);
    if (filters.model) params.set("model", filters.model);
    const r = await axios.get(
      `${API}/api/trust-center/activity/export?${params.toString()}`,
      { headers: hdrs },
    );
    const blob = new Blob([JSON.stringify(r.data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `trust-center-export-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }, [filters, hdrs]);

  if (err) {
    return <div data-testid="tc-activity-error" className="text-[13px] text-rose-700">{err}</div>;
  }
  if (!data) return <div className="text-[13px] text-[var(--muted)]">Loading…</div>;

  const maxClassVal = Math.max(...Object.values(data.by_class || { _: 1 }), 1);

  return (
    <div data-testid="tc-activity-view" className="space-y-6">
      <div className="flex flex-wrap items-end gap-3" data-testid="tc-activity-filters">
        <div className="flex items-center gap-2 text-[11.5px] text-[var(--muted)]">
          <Filter className="w-3.5 h-3.5" /> Filters:
        </div>
        <input
          value={filters.pii_class}
          onChange={(e) => setFilters({ ...filters, pii_class: e.target.value.toUpperCase() })}
          placeholder="PII class (e.g. CREDIT_CARD)"
          className="text-[12px] border border-[var(--cream-deep)] rounded px-2 py-1 bg-[var(--cream)] focus:outline-none focus:border-[var(--deep)]"
          data-testid="tc-filter-pii-class"
        />
        <input
          value={filters.model}
          onChange={(e) => setFilters({ ...filters, model: e.target.value })}
          placeholder="Model substring"
          className="text-[12px] border border-[var(--cream-deep)] rounded px-2 py-1 bg-[var(--cream)] focus:outline-none focus:border-[var(--deep)]"
          data-testid="tc-filter-model"
        />
        <button
          onClick={exportJson}
          className="ml-auto inline-flex items-center gap-1.5 text-[11.5px] text-[var(--deep)] hover:text-[var(--ink)] underline decoration-dotted underline-offset-2"
          data-testid="tc-export-btn"
        >
          <Download className="w-3.5 h-3.5" /> Export JSON
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="tc-activity-counters">
        <Counter label="Identifiers shielded" value={data.total_identifiers_shielded ?? 0} />
        <Counter label="Conversations" value={data.total_chats ?? 0} />
        <Counter label="Turns" value={data.total_turns ?? 0} />
        <Counter label="Models" value={(data.models_used || []).length} />
      </div>

      {data.by_class && Object.keys(data.by_class).length > 0 && (
        <div data-testid="tc-activity-bars" className="space-y-2">
          <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">
            By PII class
          </div>
          {Object.entries(data.by_class).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
            <div key={k} className="flex items-center gap-3 text-[12px] text-[var(--ink)]">
              <span className="w-32 font-mono text-[11px]">{k}</span>
              <span
                className="h-4 bg-emerald-200 rounded"
                style={{ width: `${Math.round((v / maxClassVal) * 100)}%`, minWidth: "8px" }}
              />
              <span className="text-[var(--deep)] font-medium">{v}</span>
            </div>
          ))}
        </div>
      )}

      <div className="space-y-2">
        <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">
          Recent turns with redactions
        </div>
        {(data.rows || []).map((r) => (
          <div key={`${r.chat_id}-${r.message_id}`} data-testid="tc-activity-row">
            <button
              onClick={() => setOpenTurn(openTurn === r.message_id ? null : r.message_id)}
              className="w-full text-left flex items-center gap-3 px-4 py-3 bg-[var(--cream)] border border-[var(--cream-deep)] rounded-lg hover:bg-[var(--cream-deep)]/40 transition-colors"
            >
              {openTurn === r.message_id ? (
                <ChevronDown className="w-4 h-4 text-[var(--muted)]" />
              ) : (
                <ChevronRight className="w-4 h-4 text-[var(--muted)]" />
              )}
              <div className="flex-1 text-[12.5px] text-[var(--ink)]">
                <span className="text-[var(--muted)]">{new Date(r.ts).toLocaleString()}</span>
                <span className="mx-2 text-[var(--cream-deep)]">·</span>
                <span>{r.chat_title || r.chat_id.slice(0, 8)}</span>
                <span className="ml-3 inline-flex items-center gap-1 text-emerald-700 text-[11.5px]">
                  <ShieldCheck className="w-3 h-3" />
                  {Object.entries(r.by_class || {}).map(([k, v]) => `${k}×${v}`).join(", ")}
                </span>
              </div>
              <span className="text-[10.5px] text-[var(--muted)] font-mono">{r.version}</span>
            </button>
            {openTurn === r.message_id && (
              <DrilldownPanel
                chatId={r.chat_id}
                messageId={r.message_id}
                onClose={() => setOpenTurn(null)}
              />
            )}
          </div>
        ))}
        {(data.rows || []).length === 0 && (
          <div className="text-[13px] text-[var(--muted)]">No activity in the selected window.</div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Phase ZZ.3 (2026-02) — "Reasoning" view.
//
// Hybrid layout: 6 top-line tiles + (day, event_kind) aggregated feed.
// All counts pull from existing audit collections; no per-message
// drill-down (that's SIEM territory). Window selector 7d (default) /
// 30d. Voice: declarative, restrained, banned-vocab clean.
// ─────────────────────────────────────────────────────────────────────
const REASONING_KIND_LABELS = {
  identifiers_protected: "Identifiers protected",
  grounding_check: "Evidence-grounding check",
  unsourced_refused: "Unsourced claim refused",
  escalation_offered: "Solva escalation offered",
  escalation_accepted: "Solva escalation accepted",
};
function _reasoningKindLabel(kind) {
  if (REASONING_KIND_LABELS[kind]) return REASONING_KIND_LABELS[kind];
  if (kind.startsWith("bias.")) return `Bias flag: ${kind.slice(5)}`;
  return kind;
}

// Phase ZZ.4 — Reasoning velocity tile. Reads
// /api/observability/reasoning_velocity for the active window.
function ReasoningVelocityTile({ vel, window }) {
  if (!vel) return null;
  const sessions = vel.session_count || 0;
  if (sessions === 0) {
    return (
      <div data-testid="tc-velocity-tile" className="bg-[var(--cream)] border border-[var(--cream-deep)] rounded-lg p-4 text-[13px] text-[var(--muted)]">
        No completed Solva sessions in the last {window === "7d" ? "7 days" : "30 days"}.
      </div>
    );
  }
  const totalAvgS = ((vel.avg_ms_per_slide || 0) * 16) / 1000;
  const p95S = (vel.p95_ms || 0) / 1000;
  const slow = vel.slowest_slide_kind;
  const fast = vel.fastest_slide_kind;
  const showSlowest = slow && fast && fast.median_ms > 0 && slow.median_ms > 2 * fast.median_ms;
  return (
    <div data-testid="tc-velocity-tile" className="bg-[var(--cream)] border border-[var(--cream-deep)] rounded-lg p-4 space-y-1">
      <div className="text-[10.5px] uppercase tracking-wide text-[var(--muted)]">Reasoning velocity</div>
      <div className="text-[14px] text-[var(--ink)]" data-testid="tc-velocity-copy">
        Solva delivers a fully-cited 16-slide diagnosis in{" "}
        <span className="text-[var(--deep)]" data-testid="tc-velocity-avg">{totalAvgS.toFixed(0)}s</span>{" "}
        on average. p95{" "}
        <span className="text-[var(--deep)]" data-testid="tc-velocity-p95">{p95S.toFixed(0)}s</span>.
      </div>
      {showSlowest && (
        <div className="text-[12px] text-[var(--muted)]" data-testid="tc-velocity-slowest">
          Slowest layer: <span className="text-[var(--ink)]">{slow.kind}</span>.
        </div>
      )}
    </div>
  );
}

function ReasoningView() {
  const hdrs = useAuthHeaders();
  const [window, setWindow] = useState("7d");
  const [data, setData] = useState(null);
  const [vel, setVel] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const [r1, r2] = await Promise.all([
          axios.get(`${API}/api/trust-center/reasoning?window=${window}`, { headers: hdrs }),
          axios.get(`${API}/api/observability/reasoning_velocity?window=${window}`, { headers: hdrs }),
        ]);
        if (cancel) return;
        setData(r1.data);
        setVel(r2.data);
      } catch (e) {
        if (!cancel) setErr(e?.response?.data?.detail || String(e));
      }
    })();
    return () => { cancel = true; };
  }, [window, hdrs]);

  if (err) {
    return <div data-testid="tc-reasoning-error" className="text-[13px] text-rose-700">{err}</div>;
  }
  if (!data) return <div className="text-[13px] text-[var(--muted)]">Loading…</div>;
  const t = data.tiles || {};
  const biasKinds = t.bias_flags_by_kind || {};
  return (
    <div data-testid="tc-reasoning-view" className="space-y-6">
      <div className="flex items-center gap-2 text-[11.5px] text-[var(--muted)]" data-testid="tc-reasoning-window">
        <span>Window:</span>
        {["7d", "30d"].map((w) => (
          <button
            key={w}
            onClick={() => setWindow(w)}
            data-testid={`tc-reasoning-window-${w}`}
            className={`px-2 py-1 rounded-sm border text-[11px] uppercase tracking-wide ${
              window === w
                ? "border-[var(--deep)] text-[var(--ink)]"
                : "border-[var(--cream-deep)] text-[var(--muted)] hover:text-[var(--ink)]"
            }`}
          >
            {w === "7d" ? "Last 7 days" : "Last 30 days"}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3" data-testid="tc-reasoning-tiles">
        <Counter label="Identifiers protected" value={t.identifiers_protected ?? 0} />
        <Counter label="Restored on your view" value={t.restored_on_view ?? 0} />
        <Counter label="Evidence-grounding checks" value={t.grounding_checks ?? 0} />
        <Counter label="Unsourced claims refused" value={t.unsourced_refused ?? 0} />
        <Counter
          label="Bias flags surfaced"
          value={t.bias_flags_total ?? 0}
        />
        <Counter
          label="Solva escalations"
          value={`${t.escalations_offered ?? 0} offered · ${t.escalations_accepted ?? 0} accepted`}
          small
        />
      </div>

      <ReasoningVelocityTile vel={vel} window={window} />

      {Object.keys(biasKinds).length > 0 && (
        <div data-testid="tc-reasoning-bias-breakdown" className="space-y-1.5">
          <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">
            Bias flags by kind
          </div>
          {Object.entries(biasKinds)
            .sort((a, b) => b[1] - a[1])
            .map(([k, v]) => (
              <div key={k} className="flex items-center gap-3 text-[12px] text-[var(--ink)]">
                <span className="w-32 font-mono text-[11px]" data-testid={`tc-reasoning-bias-${k}`}>
                  {k}
                </span>
                <span className="text-[var(--deep)]">{v}</span>
              </div>
            ))}
        </div>
      )}

      <div className="space-y-2">
        <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">
          Aggregated by day
        </div>
        {(data.feed || []).length === 0 && (
          <div className="text-[13px] text-[var(--muted)]" data-testid="tc-reasoning-feed-empty">
            Nothing in the selected window.
          </div>
        )}
        {(data.feed || []).map((row, i) => (
          <div
            key={`${row.day}-${row.event_kind}-${i}`}
            data-testid="tc-reasoning-feed-row"
            data-event-kind={row.event_kind}
            data-day={row.day}
            className="flex items-center gap-3 px-4 py-2 bg-[var(--cream)] border border-[var(--cream-deep)] rounded-lg text-[12.5px] text-[var(--ink)]"
          >
            <span className="text-[var(--muted)] font-mono w-24 shrink-0">{row.day}</span>
            <span className="flex-1">{_reasoningKindLabel(row.event_kind)}</span>
            <span className="text-[var(--deep)] font-medium">{row.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Top-level page
// ─────────────────────────────────────────────────────────────────────
export default function TrustCenter() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Accept chat_id from query string OR from router state (Chat.jsx
  // navigates with { state: { chatId } }).
  const initialChatId = searchParams.get("chat_id") || location.state?.chatId || null;
  const [chatId, setChatId] = useState(initialChatId);
  const [tab, setTab] = useState(initialChatId ? "session" : "activity");
  // J1 — Re-intro deep-link from the AppShell banner. The banner calls
  // /acknowledge BEFORE navigating, so by the time we render this
  // page the user is already permanently opted-in to "I've seen this".
  // The intro card is purely informational — dismissable via X or
  // navigation away.
  const showIntroCard = searchParams.get("intro") === "shield";
  const [introDismissed, setIntroDismissed] = useState(false);
  const hdrs = useAuthHeaders();
  const acknowledgeIntro = useCallback(async () => {
    try {
      await axios.post(
        `${API}/api/users/me/onboarding-status/acknowledge`,
        {},
        { headers: hdrs },
      );
    } catch (_e) { /* non-fatal */ }
    setIntroDismissed(true);
  }, [hdrs]);

  // J3 (2026-05-25, ratified spec §3 Stage 5) — Trust Center tour.
  // Reads `trust_center_tour.show` from the onboarding-status
  // endpoint. The tour scaffolding renders DOM-unconditionally
  // (closeout §5.1) — visibility is governed by the `show` prop
  // inside the overlay component itself.
  const [tourState, setTourState] = useState({ show: false });
  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const { data: status } = await axios.get(
          `${API}/api/users/me/onboarding-status`,
          { headers: hdrs },
        );
        if (cancel) return;
        const tour = status?.trust_center_tour || {};
        setTourState({ show: Boolean(tour.show) });
      } catch (_e) {
        // Non-fatal — tour stays hidden.
      }
    })();
    return () => { cancel = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      data-testid="trust-center-page"
      className="min-h-screen bg-[var(--cream)] text-[var(--ink)]"
    >
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Phase P1 β (2026-02) — back nav. Falls back to home when no
            history exists (deep-link / direct paste). Visible at all
            viewports, plain register, voice-lint clean. */}
        <button
          type="button"
          data-testid="trust-center-back-btn"
          onClick={() => {
            if (window.history.length > 1) {
              window.history.back();
            } else {
              window.location.assign("/");
            }
          }}
          className="inline-flex items-center gap-1.5 mb-6 px-2.5 py-1.5 text-[12.5px] text-[var(--deep)] hover:text-[var(--ink)] border border-[var(--cream-deep)] hover:border-[var(--ink)] rounded-sm transition-colors"
          aria-label="Back"
        >
          <span aria-hidden="true">←</span>
          <span>Back</span>
        </button>

        <header className="mb-8">
          <div className="flex items-center gap-3">
            <ShieldCheck className="w-6 h-6 text-emerald-700" strokeWidth={1.7} />
            <h1 className="text-[26px] tracking-tight text-[var(--ink)]" data-testid="trust-center-title">
              Trust Center
            </h1>
          </div>
          <p className="text-[13px] text-[var(--muted)] mt-2 max-w-2xl">
            Factual reporting of what Akki sent to which model, what was redacted
            beforehand, and the audit chain behind each answer.
          </p>
        </header>

        {/* J1 — One-time intro card shown when user arrives here via
            the re-intro banner (?intro=shield). Acknowledge is implicit
            on first view; the X just hides the card. */}
        {showIntroCard && !introDismissed && (
          <div
            data-testid="tc-intro-card"
            className="mb-6 bg-amber-50/60 border border-amber-200 rounded-lg p-4 flex items-start gap-4"
          >
            <div className="flex-1">
              <div className="text-[13.5px] text-[var(--ink)] font-medium">
                You're seeing Trust Center for the first time.
              </div>
              <div className="text-[12.5px] text-[var(--deep)] mt-1 leading-relaxed">
                This page shows every Shield interaction — what you sent,
                what the LLM saw, what came back, and the cryptographic
                audit chain proving it. Pick "All activity" to scan your
                history, or pass a chat ID to inspect a single
                conversation in detail.
              </div>
            </div>
            <button
              onClick={acknowledgeIntro}
              data-testid="tc-intro-dismiss"
              className="text-[var(--muted)] hover:text-[var(--ink)] transition-colors"
              aria-label="Dismiss intro"
            >
              <X className="w-4 h-4" strokeWidth={1.7} />
            </button>
          </div>
        )}

        <div className="flex items-center gap-1 mb-6 border-b border-[var(--cream-deep)]">
          <TabButton active={tab === "session"} disabled={!chatId} onClick={() => setTab("session")} testid="tc-tab-session">
            This session
          </TabButton>
          <TabButton active={tab === "activity"} onClick={() => setTab("activity")} testid="tc-tab-activity">
            All activity
          </TabButton>
          <TabButton active={tab === "reasoning"} onClick={() => setTab("reasoning")} testid="tc-tab-reasoning">
            Reasoning
          </TabButton>
        </div>

        <main className="min-h-[60vh]">
          {tab === "session" && chatId && <SessionView chatId={chatId} />}
          {tab === "session" && !chatId && (
            <div className="text-[13px] text-[var(--muted)]" data-testid="tc-no-chat">
              No sessions yet. Upload a document or chat with Akki to begin.
            </div>
          )}
          {tab === "activity" && <ActivityView />}
          {tab === "reasoning" && <ReasoningView />}
        </main>

        <StandardsFooter />
      </div>
      {/* J3 (2026-05-25, ratified spec §3 Stage 5) — Trust Center
          tour. DOM-unconditional (closeout §5.1 + §5.7); visibility
          governed by `show` prop. */}
      <TrustCenterTour
        show={tourState.show}
        onDismiss={() => setTourState({ show: false })}
      />
    </div>
  );
}

function TabButton({ active, disabled, children, onClick, testid }) {
  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      data-testid={testid}
      className={`px-4 py-2 text-[13px] border-b-2 -mb-px transition-colors ${
        active
          ? "border-[var(--deep)] text-[var(--ink)]"
          : disabled
          ? "border-transparent text-[var(--muted)]/50 cursor-not-allowed"
          : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
      }`}
    >
      {children}
    </button>
  );
}
