/**
 * SandboxTutorial — first-run guided card for sandbox visitors.
 *
 * Renders only inside a sandbox context (account.is_sandbox === true) until
 * dismissed. Replaces the open-canvas dump-everything pattern with a single,
 * directive card that asks the user to do ONE thing first:
 *   1. Read the seeded brief
 *   2. Try the suggested chat opener
 *   3. Scan the signals
 *
 * Wired to /api/sandbox/contexts/:cid/tutorial.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Sparkles, ArrowRight, X, ScrollText, MessageCircle, Activity } from "lucide-react";

const STEP_ICONS = {
  read_brief: ScrollText,
  ask_chat: MessageCircle,
  scan_signals: Activity,
};

export default function SandboxTutorial({ contextId, isSandbox: _isSandbox }) {
  const [data, setData] = useState(null);
  const [hidden, setHidden] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!contextId) { setData(null); return; }
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get(`/sandbox/contexts/${contextId}/tutorial`);
        if (cancelled) return;
        if (data?.dismissed || (!data?.first_briefing && !data?.objective)) {
          setHidden(true);
        } else {
          setData(data);
        }
      } catch { /* not eligible — silent */ setHidden(true); }
    })();
    return () => { cancelled = true; };
  }, [contextId]);

  const dismiss = async () => {
    if (!contextId) return;
    setBusy(true);
    try {
      await api.post(`/sandbox/contexts/${contextId}/tutorial/dismiss`, { dismissed: true });
      setHidden(true);
    } catch { /* swallow — UI hides regardless */ setHidden(true); }
    finally { setBusy(false); }
  };

  if (!data || hidden) return null;

  return (
    <AnimatePresence>
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
        className="bg-white border border-[var(--rule)] rounded-md p-6 mb-8 shrink-0 relative"
        data-testid="sandbox-tutorial-card"
      >
        <button
          onClick={dismiss}
          disabled={busy}
          aria-label="Dismiss tutorial"
          className="absolute top-3 right-3 text-[var(--muted)] hover:text-[var(--ink)]"
          data-testid="sandbox-tutorial-dismiss"
        >
          <X className="w-4 h-4" />
        </button>

        <p className="akki-overline mb-2 flex items-center gap-2">
          <Sparkles className="w-3 h-3 text-[var(--accent)]" />
          {data.objective ? "Welcome — here's how this plays out for you" : "Welcome — one thing to try first"}
        </p>

        <h2 className="akki-serif text-[22px] md:text-[26px] text-[var(--ink)] leading-snug mb-2">
          {data.objective
            ? "A story shaped to what you came here for."
            : "A story shaped to your sector."}
        </h2>

        {data.objective && (
          <p className="akki-serif italic text-[14px] text-[var(--muted)] leading-relaxed mb-4 border-l-2 border-[var(--rule)] pl-3 max-w-[640px]">
            “{data.objective}”
          </p>
        )}

        {data.first_briefing?.opening_paragraph && (
          <p className="text-[14px] text-[var(--deep)] leading-relaxed mb-5 max-w-[700px]">
            AKKI has already drafted{" "}
            <Link
              to="/app/briefings"
              className="text-[var(--accent)] underline-offset-2 hover:underline"
              data-testid="sandbox-tutorial-brief-link"
            >
              {data.first_briefing.title}
            </Link>
            {" — "}{data.first_briefing.opening_paragraph.split(". ").slice(0, 1).join(". ")}.
          </p>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-2" data-testid="sandbox-tutorial-steps">
          {(data.steps || []).map((s, i) => {
            const Icon = STEP_ICONS[s.key] || ArrowRight;
            return (
              <Link
                key={s.key}
                to={s.href}
                className="block bg-[var(--cream-deep)]/50 border border-[var(--rule)] rounded-md p-4 hover:border-[var(--accent)] transition-colors"
                data-testid={`sandbox-tutorial-step-${s.key}`}
              >
                <div className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-full bg-white border border-[var(--rule)] flex items-center justify-center text-[11px] font-mono text-[var(--accent)] shrink-0">
                    {i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="akki-serif text-[15px] text-[var(--ink)] flex items-center gap-1.5">
                      <Icon className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} /> {s.title}
                    </p>
                    <p className="text-[12px] text-[var(--muted)] mt-1 leading-snug">{s.blurb}</p>
                    <p className="text-[12px] text-[var(--accent)] mt-2 inline-flex items-center gap-1">
                      {s.cta} <ArrowRight className="w-3 h-3" />
                    </p>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>

        {data.suggested_chat_opener && (
          <div className="mt-5 pt-4 border-t border-[var(--rule)] flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] font-mono">
                Suggested chat opener
              </p>
              <p className="akki-serif italic text-[14px] text-[var(--deep)] mt-1 truncate">
                “{data.suggested_chat_opener}”
              </p>
            </div>
            <Link
              to={`/app/chat?prompt=${encodeURIComponent(data.suggested_chat_opener)}`}
              data-testid="sandbox-tutorial-open-chat"
            >
              <Button className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white h-9 text-[13px] whitespace-nowrap">
                Open in Chat <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
              </Button>
            </Link>
          </div>
        )}
      </motion.section>
    </AnimatePresence>
  );
}
