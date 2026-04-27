/**
 * QuickResults — the "client seeks, client gets" page.
 *
 * Surfaces immediately after a sandbox visitor uploads their own document.
 * Per the strategic addendum (§1.1): focused, high-conversion-strength
 * use-cases tied to THIS document — not a navigation menu, not a flood
 * of features. Three cards. One-click each. Output renders inline.
 *
 * After the user has seen the value, a single "Want more?" CTA opens
 * the full sandbox.
 *
 * Reachable two ways:
 *  - Sandbox: SandboxPackDrop redirects here after a successful upload
 *  - In-product (Tier B, future): topbar QuickResume pill links here
 *    from any screen outside the Document Journal
 */
import React, { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import AppShell from "@/components/layout/AppShell";
import ValidatedBadge from "@/components/trust/ValidatedBadge";
import { Button } from "@/components/ui/button";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import {
  Loader2, BookOpen, ScrollText, AlertTriangle, ArrowRight, FileText,
  Sparkles, Check,
} from "lucide-react";
import { recordContinueWith } from "@/components/layout/ContinueWithPill";

const USE_CASES = [
  {
    key: "summary",
    icon: BookOpen,
    title: "Read me the summary",
    blurb: "AKKI's two-line read of the document, plus what matters and what to ask the room.",
    cta: "Generate summary",
  },
  {
    key: "risks",
    icon: AlertTriangle,
    title: "What does the board need to notice?",
    blurb: "The risks, opportunities, and gaps surfaced from this exact pack — anchored to the source paragraph.",
    cta: "Surface signals",
  },
  {
    key: "briefing",
    icon: ScrollText,
    title: "Draft a briefing for my next meeting",
    blurb: "A complete briefing AKKI would walk into the meeting with — opening paragraph, sections, closing recommendations.",
    cta: "Draft briefing",
  },
];

export default function QuickResults() {
  const { contextId, docId } = useParams();
  const navigate = useNavigate();
  const [doc, setDoc] = useState(null);
  const [busyKey, setBusyKey] = useState(null);
  const [results, setResults] = useState({});  // {key: payload}

  // Load the doc metadata so we can show the user's filename in the hero.
  useEffect(() => {
    if (!contextId || !docId) return;
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get(`/contexts/${contextId}/documents/${docId}`);
        if (!cancelled) {
          setDoc(data);
          // Tier-B Continue-with pill: record this as the user's most-recent
          // doc-anchored read so it's surfaced from the topbar across pages.
          recordContinueWith({
            contextId,
            docId,
            docName: data?.name || data?.original_filename,
          });
        }
      } catch { /* silent — header just renders generic copy */ }
    })();
    return () => { cancelled = true; };
  }, [contextId, docId]);

  // Each use-case maps to an existing endpoint — we don't introduce new
  // backend surface for the Quick-Results card; we just compose the
  // existing primitives in a sequenced, doc-bound way.
  const run = useCallback(async (key) => {
    setBusyKey(key);
    try {
      if (key === "summary") {
        // Backend signature: query param ?refresh, returns the summary
        // payload directly (no nesting).
        const { data } = await api.post(
          `/contexts/${contextId}/documents/${docId}/summary`,
          {},
        );
        setResults((r) => ({ ...r, summary: data }));
      } else if (key === "risks") {
        const { data } = await api.post(
          `/contexts/${contextId}/signals/generate`,
          { focus: `From this exact document, what does the board need to notice?` },
        );
        setResults((r) => ({ ...r, risks: { signals: data?.signals || [] } }));
      } else if (key === "briefing") {
        // Backend expects POST /contexts/{cid}/briefings (no /generate suffix)
        // and runs against the most recent active signals. We trigger a
        // signal generation first if none exist, so the briefing has
        // something to brief on.
        let sigs = [];
        try {
          const { data } = await api.get(`/contexts/${contextId}/signals?limit=20`);
          sigs = Array.isArray(data) ? data : (data?.signals || []);
        } catch { /* ignore */ }
        if (sigs.length === 0) {
          await api.post(
            `/contexts/${contextId}/signals/generate`,
            { focus: `From the document the user just uploaded, surface anything the board needs to notice.` },
          );
        }
        const { data } = await api.post(
          `/contexts/${contextId}/briefings`,
          {},
        );
        setResults((r) => ({ ...r, briefing: data }));
      }
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusyKey(null); }
  }, [contextId, docId]);

  const docName = doc?.name || "the document you uploaded";

  return (
    <AppShell>
      <div className="min-h-[calc(100vh-4rem)] bg-[var(--cream)]">
        <div className="max-w-[860px] mx-auto px-6 py-12">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.2, 0.8, 0.2, 1] }}
          >
            <p className="akki-overline mb-3 flex items-center gap-2">
              <Sparkles className="w-3 h-3 text-[var(--accent)]" />
              AKKI just read {doc?.original_filename || "your file"}
            </p>
            <h1
              className="akki-serif text-[28px] md:text-[34px] leading-[1.15] text-[var(--ink)] mb-2"
              data-testid="quick-results-hero"
            >
              Pick a question. AKKI answers it from <span className="text-[var(--accent)]">{docName}</span>.
            </h1>
            <p className="text-[14.5px] text-[var(--muted)] leading-relaxed mb-2 max-w-[640px]">
              No navigation. No setup. Three concrete things AKKI can do with this exact document right now.
            </p>
            <div className="mb-10">
              <ValidatedBadge size="compact" />
            </div>

            <div className="space-y-4" data-testid="quick-results-cards">
              {USE_CASES.map((uc) => {
                const Icon = uc.icon;
                const result = results[uc.key];
                const isBusy = busyKey === uc.key;
                return (
                  <div
                    key={uc.key}
                    className="bg-white border border-[var(--rule)] rounded-md p-5"
                    data-testid={`quick-results-card-${uc.key}`}
                  >
                    <div className="flex items-start gap-4">
                      <div className="w-9 h-9 rounded-full bg-[var(--accent-soft)] flex items-center justify-center shrink-0">
                        <Icon className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h2 className="akki-serif text-[18px] text-[var(--ink)] leading-snug mb-1">
                          {uc.title}
                        </h2>
                        <p className="text-[13px] text-[var(--muted)] leading-relaxed mb-3 max-w-[600px]">
                          {uc.blurb}
                        </p>
                        {!result && (
                          <Button
                            onClick={() => run(uc.key)}
                            disabled={isBusy}
                            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white h-9 text-[13px] px-4"
                            data-testid={`quick-results-run-${uc.key}`}
                          >
                            {isBusy ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 mr-1.5" />}
                            {isBusy ? "Reading…" : uc.cta}
                          </Button>
                        )}
                        {result && (
                          <div data-testid={`quick-results-output-${uc.key}`}>
                            <p className="text-[10.5px] uppercase tracking-[0.18em] text-emerald-700 inline-flex items-center gap-1 mb-2">
                              <Check className="w-3 h-3" /> Done
                            </p>
                            <ResultBlock kind={uc.key} payload={result} contextId={contextId} navigate={navigate} />
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* "Want more?" CTA — only after the user has triggered at
                least one quick result, so the journey rewards engagement. */}
            {Object.keys(results).length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                className="mt-10 pt-6 border-t border-[var(--rule)] flex items-center justify-between gap-4 flex-wrap"
                data-testid="quick-results-want-more"
              >
                <div>
                  <p className="akki-serif text-[18px] text-[var(--ink)] leading-snug">
                    Want to see more?
                  </p>
                  <p className="text-[13px] text-[var(--muted)] mt-1 max-w-[460px]">
                    Open the full sandbox — committees, simulations, the lens, the cycle. AKKI is ready when you are.
                  </p>
                </div>
                <Button
                  onClick={() => navigate("/app")}
                  className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white h-11 px-6"
                  data-testid="quick-results-open-full"
                >
                  Open my full sandbox <ArrowRight className="w-4 h-4 ml-1.5" />
                </Button>
              </motion.div>
            )}
          </motion.div>
        </div>
      </div>
    </AppShell>
  );
}

/**
 * ResultBlock — inline rendering for each Quick-Result kind. Editorial,
 * compact: 4-5 lines of preview followed by a one-tap "open the full
 * thing" link. We don't try to render the full briefing here — Quick
 * Results is the conversion moment, not the workspace.
 */
function ResultBlock({ kind, payload, contextId, navigate }) {
  if (kind === "summary") {
    const s = payload || {};
    return (
      <div className="bg-[var(--cream-deep)]/40 border border-[var(--rule)] rounded-md p-3">
        {s?.tldr && (
          <p className="akki-serif text-[14px] leading-[1.65] text-[var(--ink)] mb-2">{s.tldr}</p>
        )}
        {(s?.highlights || []).slice(0, 3).map((h, i) => (
          <p key={i} className="text-[12.5px] text-[var(--deep)] leading-relaxed mb-1">
            <span className="text-[var(--accent)] font-mono text-[10px] mr-1.5">0{i + 1}</span>
            {h}
          </p>
        ))}
      </div>
    );
  }
  if (kind === "risks") {
    const sigs = payload?.signals || [];
    return (
      <div className="bg-[var(--cream-deep)]/40 border border-[var(--rule)] rounded-md p-3 space-y-2">
        {sigs.length === 0 && (
          <p className="text-[12.5px] text-[var(--muted)] italic">No new signals from this pack.</p>
        )}
        {sigs.slice(0, 3).map((s) => (
          <div key={s.id} className="flex items-start gap-2">
            <span className="text-[10px] uppercase tracking-wider text-[var(--accent)] mt-0.5 shrink-0">{s.type || s.kind}</span>
            <p className="akki-serif text-[13.5px] text-[var(--ink)] leading-snug">{s.headline || s.title}</p>
          </div>
        ))}
        {sigs.length > 3 && (
          <button
            onClick={() => navigate("/app/prepare")}
            className="text-[11px] text-[var(--accent)] hover:underline"
          >
            See all {sigs.length} signals →
          </button>
        )}
      </div>
    );
  }
  if (kind === "briefing") {
    const b = payload?.briefing || payload;
    return (
      <div className="bg-[var(--cream-deep)]/40 border border-[var(--rule)] rounded-md p-3">
        <p className="akki-serif italic text-[13px] text-[var(--ink)] leading-relaxed line-clamp-4">
          {b?.opening_paragraph || "Briefing drafted."}
        </p>
        {b?.id && (
          <button
            onClick={() => navigate("/app/prepare")}
            className="text-[11px] text-[var(--accent)] hover:underline mt-2 inline-flex items-center gap-1"
            data-testid="quick-results-open-briefing"
          >
            Read the full briefing <FileText className="w-3 h-3" />
          </button>
        )}
      </div>
    );
  }
  return null;
}
