/**
 * ObjectiveCheck — the 24-hour follow-up card.
 *
 * Asks the user "Did AKKI deliver on your objective?" exactly once, ~24h
 * after the sandbox or seeded context was generated. Captures yes/partial/no
 * + an optional note as a per-sector conversion KPI (matches the doc:
 * "we use this to measure later whether AKKI delivered on it").
 *
 * Hidden until eligible=true. After answering or skipping, never re-shows.
 */
import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Sparkles, Check, X } from "lucide-react";

const ANSWERS = [
  { key: "yes",     label: "Yes — sharper than I expected", tone: "emerald" },
  { key: "partial", label: "Partly — useful but not yet there", tone: "amber" },
  { key: "no",      label: "Not really — here's why",        tone: "red" },
];

const TONE_CLS = {
  emerald: "border-emerald-200 hover:bg-emerald-50 text-emerald-800",
  amber:   "border-amber-200 hover:bg-amber-50 text-amber-800",
  red:     "border-red-200 hover:bg-red-50 text-red-800",
};

export default function ObjectiveCheck({ contextId }) {
  const [data, setData] = useState(null);
  const [hidden, setHidden] = useState(false);
  const [answer, setAnswer] = useState(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!contextId) { setData(null); return; }
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get(`/sandbox/contexts/${contextId}/objective-check`);
        if (cancelled) return;
        if (!data?.eligible) { setHidden(true); }
        else setData(data);
      } catch { setHidden(true); }
    })();
    return () => { cancelled = true; };
  }, [contextId]);

  const submit = async (key) => {
    if (busy) return;
    setBusy(true);
    try {
      await api.post(`/sandbox/contexts/${contextId}/objective-check`, {
        answer: key, note: (key === "skip" ? null : note.trim() || null),
      });
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
        className="bg-white border border-[var(--accent)]/30 rounded-md p-5 mb-6 shrink-0 relative"
        data-testid="objective-check-card"
      >
        <button
          onClick={() => submit("skip")}
          disabled={busy}
          aria-label="Skip"
          className="absolute top-3 right-3 text-[var(--muted)] hover:text-[var(--ink)]"
          data-testid="objective-check-skip"
        >
          <X className="w-4 h-4" />
        </button>

        <p className="akki-overline mb-2 flex items-center gap-2">
          <Sparkles className="w-3 h-3 text-[var(--accent)]" />
          24-hour check-in
        </p>

        <h2 className="akki-serif text-[20px] md:text-[22px] text-[var(--ink)] leading-snug mb-2">
          Did AKKI deliver on what you came here for?
        </h2>

        <p className="akki-serif italic text-[13.5px] text-[var(--muted)] leading-relaxed mb-4 border-l-2 border-[var(--rule)] pl-3">
          “{data.objective}”
        </p>

        {!answer ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2" data-testid="objective-check-answers">
            {ANSWERS.map((a) => (
              <button
                key={a.key}
                onClick={() => setAnswer(a.key)}
                disabled={busy}
                className={`text-left px-4 py-3 rounded-md border bg-white text-[13px] transition-colors ${TONE_CLS[a.tone]}`}
                data-testid={`objective-check-${a.key}`}
              >
                {a.label}
              </button>
            ))}
          </div>
        ) : (
          <div data-testid="objective-check-followup">
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={
                answer === "yes"
                  ? "What stood out? (optional)"
                  : answer === "partial"
                    ? "What's missing? (optional)"
                    : "What didn't work? (optional)"
              }
              rows={2}
              maxLength={400}
              className="bg-white rounded-md text-[13px] text-[var(--ink)] placeholder:text-[var(--muted)] border-[var(--rule)] focus:border-[var(--accent)] resize-none mb-3"
              data-testid="objective-check-note"
            />
            <div className="flex gap-2">
              <Button
                onClick={() => submit(answer)}
                disabled={busy}
                className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white h-9 text-[13px]"
                data-testid="objective-check-submit"
              >
                <Check className="w-3.5 h-3.5 mr-1.5" /> Send feedback
              </Button>
              <Button
                onClick={() => setAnswer(null)}
                variant="ghost"
                disabled={busy}
                className="h-9 text-[13px] text-[var(--muted)]"
              >
                Back
              </Button>
            </div>
          </div>
        )}
      </motion.section>
    </AnimatePresence>
  );
}
